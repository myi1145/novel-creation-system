from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import AgentCallLogORM
from app.services.prompt_template_service import PromptTemplateResolution, prompt_template_service
from app.services.provider_governance_service import ProviderPreflightResult, provider_governance_service
from app.services.rulepack_service import rulepack_service

logger = get_logger("agent")


class AgentGatewayError(RuntimeError):
    pass


class AgentProviderRequestError(AgentGatewayError):
    def __init__(self, message: str, *, error_type: str, retryable: bool, status_code: int | None = None, attempt_count: int = 1) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code
        self.attempt_count = attempt_count


class AgentStructuredOutputError(AgentGatewayError):
    def __init__(self, message: str, *, error_code: str, severity: str, decision: str, parse_report: dict[str, Any]) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.severity = severity
        self.decision = decision
        self.parse_report = parse_report


@dataclass
class GatewayStatus:
    configured_provider: str
    active_provider: str
    model: str
    fallback_enabled: bool
    fallback_active: bool
    available: bool
    reason: str | None = None


@dataclass
class AgentInvocationResult:
    payload: Any
    configured_provider: str
    active_provider: str
    model: str
    prompt_template_id: str | None
    prompt_template_key: str | None
    prompt_template_version: int | None
    prompt_scope_type: str | None
    prompt_scope_key: str | None
    prompt_provider_scope: str | None
    fallback_used: bool
    call_status: str
    latency_ms: int
    attempt_count: int
    error_type: str | None = None
    error_message: str | None = None
    circuit_state_at_call: str | None = None
    rate_limited: bool = False
    parse_report: dict[str, Any] | None = None


class AgentProvider(Protocol):
    name: str

    def generate_blueprints(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> Any: ...
    def decompose_scenes(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> Any: ...
    def generate_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def revise_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def review_gate(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> Any: ...
    def propose_changeset(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> Any: ...
    def summarize_chapter(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> Any: ...


class MockAgentProvider:
    name = "mock"

    def generate_blueprints(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]:
        goal = context["goal"]
        open_loops = context.get("open_loops") or []
        count = int(context.get("candidate_count", 3))
        results: list[dict[str, Any]] = []
        for idx in range(count):
            results.append(
                {
                    "title_hint": f"候选章蓝图 {idx + 1}",
                    "summary": f"围绕第{goal['chapter_no']}章目标推进主线，并处理伏笔：{', '.join(open_loops[:2]) or '无'}。",
                    "advances": ["主线推进", "关系微增量"],
                    "risks": ["需进一步校验 Canon 一致性"],
                    "selected": idx == 0,
                }
            )
        return results

    def decompose_scenes(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]:
        return [
            {
                "scene_goal": "建立本章起始情境",
                "participating_entities": ["主角", "核心配角"],
                "conflict_type": "external",
                "emotional_curve": "steady_rise",
                "information_delta": "introduce_context",
            },
            {
                "scene_goal": "推进冲突并制造章末钩子",
                "participating_entities": ["主角", "对手"],
                "conflict_type": "mixed",
                "emotional_curve": "tension_peak",
                "information_delta": "reveal_partial_truth",
            },
        ]

    def generate_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        blueprint = context["blueprint"]
        open_loops = context.get("open_loops") or []
        scenes = context.get("scenes") or []
        content = (
            "【正文草稿占位】\n"
            f"当前蓝图：{blueprint['title_hint']}\n"
            f"当前摘要：{blueprint['summary']}\n"
            f"场景数量：{len(scenes)}\n"
            f"关联伏笔：{', '.join(open_loops) if open_loops else '无'}\n"
            f"Prompt 模板：{prompt.template_key}@v{prompt.template_version}\n"
            "当前使用 mock provider；后续可切换到 openai_compatible provider。"
        )
        return {
            "content": content,
            "metadata": {
                "provider": self.name,
                "model": settings.agent_model,
                "scene_count": len(scenes),
                "open_loop_count": len(open_loops),
            },
        }

    def revise_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        original_content = str(context.get("content") or "").strip()
        blueprint = context.get("blueprint") or {}
        issues = list(context.get("gate_issues") or [])
        issue_summaries = [str(item.get("summary") or item.get("message") or "待修订问题") for item in issues[:5]]
        revision_instruction = str(context.get("revision_instruction") or "根据失败闸门完成修订").strip()
        revised_content = original_content.replace("占位", "修订版") if original_content else ""
        if not revised_content:
            revised_content = (
                "【修订版正文草稿】\n"
                f"当前蓝图：{blueprint.get('title_hint') or '未命名蓝图'}\n"
                f"当前摘要：{blueprint.get('summary') or '无'}\n"
            )
        revised_content += (
            "\n\n【修订说明】\n"
            f"修订指令：{revision_instruction}\n"
            f"重点处理：{'; '.join(issue_summaries) if issue_summaries else '根据 Gate 结果补强叙事与结构。'}\n"
            f"Prompt 模板：{prompt.template_key}@v{prompt.template_version}\n"
            "当前使用 mock provider 生成修订版。"
        )
        return {
            "content": revised_content,
            "metadata": {
                "provider": self.name,
                "model": settings.agent_model,
                "revision_issue_count": len(issues),
            },
        }

    def review_gate(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        gate_name = context["gate_name"]
        content = (context.get("content") or "").strip()
        issues: list[dict[str, Any]] = []
        pass_status = "passed"
        recommended_route = "pass"
        can_override = False
        override_role = None

        if gate_name == "canon_gate":
            issues.append({"severity": "S0", "message": "当前为 mock Canon 预检查，占位通过。", "suggestion": "后续可替换为真实 Canon 审查器。"})
        elif gate_name == "style_gate" and len(content) < 120:
            issues.append({"severity": "S1", "message": "正文偏短，风格判断样本有限。", "suggestion": "可增加更多正文后再做风格判断。"})
        elif gate_name == "publish_gate" and "占位" in content:
            issues.append({"severity": "S1", "message": "正文仍带有占位痕迹。", "suggestion": "接入真实 writer provider 后再发布正式样章。"})
        elif gate_name not in {"schema_gate", "canon_gate", "style_gate", "publish_gate", "narrative_gate", "voice_gate"}:
            issues.append({"severity": "S1", "message": f"{gate_name} 当前走 mock review。", "suggestion": "后续替换为真实 reviewer agent。"})

        highest_severity = _highest_severity_value(issues)
        if highest_severity in {"S3", "S4"}:
            pass_status = "failed"
            recommended_route = "rewrite"
        elif highest_severity == "S2":
            pass_status = "warning"
            recommended_route = "revise"
            can_override = True
            override_role = "author"
        elif highest_severity == "S1":
            pass_status = "warning"
            recommended_route = "review"
            can_override = True
            override_role = "editor"

        return {
            "issues": issues,
            "pass_status": pass_status,
            "highest_severity": highest_severity,
            "recommended_route": recommended_route,
            "can_override": can_override,
            "override_role": override_role,
            "provider": self.name,
            "model": settings.agent_model,
        }


    def propose_changeset(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        blueprint = context["blueprint"]
        content = str(context.get("content") or "").strip()
        chapter_no = context.get("chapter_no")
        excerpt = content[:180] if content else ""
        proposal_summary = f"基于第{chapter_no or '?'}章正文，提议写入章节推进事件。"
        extracted_changes = [
            f"第{chapter_no or '?'}章发生了新的章节事件推进",
            f"章蓝图《{blueprint.get('title_hint') or '未命名蓝图'}》已在正文中得到承接",
        ]
        uncertain_items: list[str] = []
        if "占位" in content:
            uncertain_items.append("正文仍带占位痕迹，建议人工核对后再审批 ChangeSet")
        timeline_event = {
            "chapter_no": chapter_no,
            "event_type": "chapter_progress",
            "title": blueprint.get("title_hint") or f"第{chapter_no or '?'}章推进",
            "summary": blueprint.get("summary") or "本章推进了当前卷目标。",
            "source_draft_id": context.get("draft_id"),
            "source_blueprint_id": context.get("blueprint_id"),
        }
        return {
            "proposal_summary": proposal_summary,
            "rationale": "从已过 Gate 的章节正文中提取最小可验证事件推进，先写入时间线事件，避免过度自动入史。",
            "extracted_changes": extracted_changes,
            "uncertain_items": uncertain_items,
            "evidence_refs": [
                {
                    "source_type": "chapter_draft",
                    "source_ref": context.get("draft_id"),
                    "excerpt": excerpt,
                    "note": "正文开头片段，可用于人工复核 ChangeSet 提议。",
                }
            ],
            "review_recommendation": "human_review" if uncertain_items else "semi_auto_review",
            "patch_operations": [
                {
                    "kind": "snapshot",
                    "op": "append",
                    "field": "timeline_events",
                    "value": timeline_event,
                }
            ],
            "provider": self.name,
            "model": settings.agent_model,
        }

    def summarize_chapter(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        chapter_no = context.get("chapter_no")
        title = str(context.get("chapter_title") or f"第{chapter_no or '?'}章")
        blueprint = context.get("blueprint") or {}
        summary = str(blueprint.get("summary") or f"第{chapter_no or '?'}章完成了一次主线推进。")
        unresolved = [str(item) for item in list(context.get("open_loops") or [])[:5]]
        return {
            "summary": summary,
            "state_summary": f"{title} 已发布，并将 Canon 推进到新状态。",
            "key_plot_points": [summary, f"发布标题：{title}"],
            "canon_updates": [f"第{chapter_no or '?'}章形成新的章节推进事实"],
            "unresolved_open_loops": unresolved,
            "carry_over_constraints": [f"下一章继续处理：{item}" for item in unresolved[:3]],
            "next_chapter_seed": f"下一章建议承接：{'；'.join(unresolved[:3]) if unresolved else '主线后续反应与新冲突。'}",
            "provider": self.name,
            "model": settings.agent_model,
        }


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str | None, model: str, timeout_seconds: float, temperature: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def generate_blueprints(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> str:
        return self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)

    def decompose_scenes(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> str:
        return self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)

    def generate_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        content = self._chat_text(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        return {
            "content": content.strip(),
            "metadata": {
                "provider": self.name,
                "model": self.model,
                "scene_count": len(context.get("scenes") or []),
                "open_loop_count": len(context.get("open_loops") or []),
            },
        }

    def revise_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        content = self._chat_text(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        return {
            "content": content.strip(),
            "metadata": {
                "provider": self.name,
                "model": self.model,
                "revision_issue_count": len(context.get("gate_issues") or []),
            },
        }

    def review_gate(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> str:
        return self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)

    def propose_changeset(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> str:
        return self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)

    def summarize_chapter(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> str:
        return self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)

    def _chat_json(self, system_prompt: str, user_prompt: str) -> str:
        return self._chat([
            {"role": "system", "content": system_prompt + "\n你必须只返回 JSON，不要解释。"},
            {"role": "user", "content": user_prompt},
        ])

    def _chat_text(self, system_prompt: str, user_prompt: str) -> str:
        return self._chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

    def _chat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AgentProviderRequestError(f"Provider 调用超时: {exc}", error_type="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_type = "http_5xx" if status_code >= 500 else "http_4xx"
            retryable = status_code in settings.agent_retryable_status_codes
            raise AgentProviderRequestError(
                f"provider HTTP 错误: {status_code}",
                error_type=error_type,
                retryable=retryable,
                status_code=status_code,
            ) from exc
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError) as exc:
            raise AgentProviderRequestError(f"Provider 网络错误: {exc}", error_type="network", retryable=True) from exc
        except Exception as exc:  # noqa: BLE001
            raise AgentProviderRequestError(f"调用 openai_compatible provider 失败: {exc}", error_type="provider_error", retryable=False) from exc

        try:
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            raise AgentProviderRequestError("Provider 返回结构无法解析", error_type="parse", retryable=False) from exc


# 辅助函数

def _extract_json_fragment(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
    if match:
        return match.group(1)
    return stripped


def _ensure_dict(text: str) -> dict[str, Any]:
    fragment = _extract_json_fragment(text)
    data = json.loads(fragment)
    if not isinstance(data, dict):
        raise AgentGatewayError("期望 JSON 对象，但模型返回了其他结构")
    return data


def _ensure_list(text: str) -> list[dict[str, Any]]:
    fragment = _extract_json_fragment(text)
    data = json.loads(fragment)
    if not isinstance(data, list):
        raise AgentGatewayError("期望 JSON 数组，但模型返回了其他结构")
    return [dict(item) for item in data]


STRUCTURED_OUTPUT_SPECS: dict[str, dict[str, Any]] = {
    "generate_blueprints": {"output_type": "CandidateBlueprintList", "expected_root": "list"},
    "decompose_scenes": {"output_type": "ScenePlanResult", "expected_root": "list"},
    "review_gate": {"output_type": "GateDecisionDraft", "expected_root": "object"},
    "propose_changeset": {"output_type": "ChangeProposalDraft", "expected_root": "object"},
    "summarize_chapter": {"output_type": "ChapterSummary", "expected_root": "object"},
}


def _build_parse_issue(code: str, severity: str, level: str, message: str, field_path: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "level": level,
        "message": message,
        "field_path": field_path,
    }


def _build_parse_report(method_name: str, *, decision: str, route: str, envelope_status: str = "not_present", issues: list[dict[str, Any]] | None = None, repair_actions: list[str] | None = None, reask_count: int = 0) -> dict[str, Any]:
    spec = STRUCTURED_OUTPUT_SPECS[method_name]
    issues = list(issues or [])
    repair_actions = list(repair_actions or [])
    return {
        "output_type": spec["output_type"],
        "expected_root": spec["expected_root"],
        "decision": decision,
        "route": route,
        "envelope_status": envelope_status,
        "issue_count": len(issues),
        "reask_count": reask_count,
        "degraded": decision in {"degraded", "human_review"},
        "repair_actions": repair_actions,
        "issues": issues,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _detect_forbidden_write_keys(data: Any) -> list[str]:
    forbidden = {"write_canon", "apply_changeset", "apply_now", "snapshot_after", "canon_snapshot", "canon_write", "auto_approve"}
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key) in forbidden:
                    found.append(str(key))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def _normalize_gate_review_payload(data: dict[str, Any], *, provider: str, model: str) -> dict[str, Any]:
    issues = []
    for item in list(data.get("issues") or []):
        issues.append({
            "severity": str(item.get("severity") or "S1"),
            "message": str(item.get("message") or item.get("summary") or "模型未给出详细问题"),
            "suggestion": item.get("suggestion"),
        })
    highest = str(data.get("highest_severity") or _highest_severity_value(issues) or "S0")
    pass_status = str(data.get("pass_status") or ("failed" if highest in {"S3", "S4"} else "warning" if highest in {"S1", "S2"} else "passed"))
    return {
        "pass_status": pass_status,
        "highest_severity": highest,
        "recommended_route": str(data.get("recommended_route") or ("rewrite" if pass_status == "failed" else "review" if pass_status == "warning" else "pass")),
        "can_override": bool(data.get("can_override", False)),
        "override_role": data.get("override_role"),
        "issues": issues,
        "provider": provider,
        "model": model,
    }


def _normalize_changeset_proposal(data: dict[str, Any], *, provider: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
    patch_operations = []
    for item in list(data.get("patch_operations") or []):
        if isinstance(item, dict):
            patch_operations.append({
                "kind": str(item.get("kind") or "snapshot"),
                "op": str(item.get("op") or "append"),
                "field": str(item.get("field") or "timeline_events"),
                "value": item.get("value"),
            })
    excerpt = str(data.get("excerpt") or str(context.get("content") or "")[:180]).strip()
    return {
        "proposal_summary": str(data.get("proposal_summary") or "已生成 ChangeSet 提议。"),
        "rationale": str(data.get("rationale") or "从正文中提取最小可验证变更。"),
        "extracted_changes": [str(item) for item in list(data.get("extracted_changes") or [])],
        "uncertain_items": [str(item) for item in list(data.get("uncertain_items") or [])],
        "evidence_refs": [
            {
                "source_type": str(item.get("source_type") or "chapter_draft"),
                "source_ref": item.get("source_ref") or context.get("draft_id"),
                "excerpt": str(item.get("excerpt") or excerpt),
                "note": item.get("note"),
            }
            for item in list(data.get("evidence_refs") or [{"source_ref": context.get("draft_id"), "excerpt": excerpt}])
            if isinstance(item, dict)
        ],
        "review_recommendation": str(data.get("review_recommendation") or ("human_review" if not patch_operations else "semi_auto_review")),
        "patch_operations": patch_operations,
        "provider": provider,
        "model": model,
    }


def _coerce_json_like_payload(payload: Any) -> tuple[Any, str, list[str]]:
    envelope_status = "not_present"
    repair_actions: list[str] = []
    data = payload
    if isinstance(payload, str):
        fragment = _extract_json_fragment(payload)
        repair_actions.append("extract_json_fragment")
        data = json.loads(fragment)
    if isinstance(data, dict) and "payload" in data and any(key in data for key in ("output_type", "status", "agent_name")):
        envelope_status = "present"
        repair_actions.append("extract_envelope_payload")
        return data, envelope_status, repair_actions
    return data, envelope_status, repair_actions


def _highest_severity_value(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "S0"
    ranking = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}
    return max((str(item.get("severity") or "S0") for item in issues), key=lambda severity: ranking.get(severity, 0))


def _normalize_blueprint_item(item: dict[str, Any], selected: bool) -> dict[str, Any]:
    return {
        "title_hint": str(item.get("title_hint") or "候选章蓝图"),
        "summary": str(item.get("summary") or "围绕当前章目标推进主线。"),
        "advances": [str(x) for x in list(item.get("advances") or [])],
        "risks": [str(x) for x in list(item.get("risks") or [])],
        "selected": bool(item.get("selected", selected)),
    }


def _normalize_scene_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "scene_goal": str(item.get("scene_goal") or "推进当前章节目标"),
        "participating_entities": [str(x) for x in list(item.get("participating_entities") or [])],
        "conflict_type": str(item.get("conflict_type") or "mixed"),
        "emotional_curve": str(item.get("emotional_curve") or "steady_rise"),
        "information_delta": str(item.get("information_delta") or "reveal_partial_truth"),
    }


def _normalize_chapter_summary_payload(data: dict[str, Any], *, provider: str, model: str) -> dict[str, Any]:
    return {
        "summary": str(data.get("summary") or "已生成章节摘要。"),
        "state_summary": str(data.get("state_summary") or "章节已发布。"),
        "key_plot_points": [str(item) for item in list(data.get("key_plot_points") or [])],
        "canon_updates": [str(item) for item in list(data.get("canon_updates") or [])],
        "unresolved_open_loops": [str(item) for item in list(data.get("unresolved_open_loops") or [])],
        "carry_over_constraints": [str(item) for item in list(data.get("carry_over_constraints") or [])],
        "next_chapter_seed": str(data.get("next_chapter_seed") or ""),
        "provider": provider,
        "model": model,
    }


def _truncate_string(value: str) -> str:
    value = value.strip()
    if len(value) <= settings.agent_log_string_limit:
        return value
    return value[: settings.agent_log_string_limit] + "..."


def _summarize(value: Any) -> Any:
    if isinstance(value, str):
        return _truncate_string(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _summarize(v) for k, v in list(value.items())[: settings.agent_log_collection_limit]}
    if isinstance(value, list):
        return [_summarize(v) for v in value[: settings.agent_log_collection_limit]]
    return _truncate_string(str(value))


class AgentGateway:
    def __init__(self) -> None:
        self._mock_provider = MockAgentProvider()

    def _build_reask_prompt_resolution(self, prompt_resolution: PromptTemplateResolution, parse_report: dict[str, Any]) -> PromptTemplateResolution:
        issue_lines = [f"- {item.get('code')}: {item.get('message')}" for item in list(parse_report.get('issues') or [])[:5]]
        extra_system = (
            "\n\n[结构化输出修复要求]\n"
            "上一次输出未通过解析层校验。你必须只返回合法 JSON，且只返回一个根对象或数组，不要解释，不要 Markdown。"
        )
        extra_user = (
            "\n\n[解析失败反馈]\n"
            f"目标输出类型：{parse_report.get('output_type')}\n"
            f"期望根结构：{parse_report.get('expected_root')}\n"
            f"问题摘要：{'；'.join(issue_lines) if issue_lines else '请修复结构化输出格式与必填字段。'}\n"
            "请重答，只修复结构与缺失字段，不要改变已确认业务含义。"
        )
        return PromptTemplateResolution(
            template=prompt_resolution.template,
            system_prompt=prompt_resolution.system_prompt + extra_system,
            user_prompt=prompt_resolution.user_prompt + extra_user,
        )

    def _process_structured_payload(self, *, method_name: str, payload: Any, provider_name: str, model_name: str, context: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        repair_actions: list[str] = []
        try:
            data, envelope_status, repair_actions = _coerce_json_like_payload(payload)
        except json.JSONDecodeError as exc:
            report = _build_parse_report(
                method_name,
                decision="reask",
                route="reask",
                issues=[_build_parse_issue("E002", "P1", "L1", f"结构化输出无法解析为合法 JSON: {exc}")],
                repair_actions=["extract_json_fragment"],
            )
            raise AgentStructuredOutputError("结构化输出解析失败", error_code="parse_e002", severity="P1", decision="reask", parse_report=report) from exc
        except Exception as exc:  # noqa: BLE001
            report = _build_parse_report(
                method_name,
                decision="reask",
                route="reask",
                issues=[_build_parse_issue("E002", "P1", "L1", f"结构化输出解析异常: {exc}")],
                repair_actions=repair_actions,
            )
            raise AgentStructuredOutputError("结构化输出解析异常", error_code="parse_e002", severity="P1", decision="reask", parse_report=report) from exc

        envelope = data if isinstance(data, dict) and envelope_status == "present" else None
        business_payload = data.get("payload") if envelope is not None else data
        if envelope is not None and envelope.get("output_type") and str(envelope.get("output_type")) != STRUCTURED_OUTPUT_SPECS[method_name]["output_type"]:
            issues.append(_build_parse_issue("E010", "P1", "L3", "输出类型与当前工作流节点不匹配", "output_type"))
        if envelope is not None and str(envelope.get("status") or "success") in {"partial", "failed"}:
            issues.append(_build_parse_issue("E013", "P1", "L3", "模型自报结果不完整或失败，需人工关注", "status"))

        expected_root = STRUCTURED_OUTPUT_SPECS[method_name]["expected_root"]
        if expected_root == "list":
            if not isinstance(business_payload, list):
                report = _build_parse_report(method_name, decision="reask", route="reask", envelope_status=envelope_status, issues=issues + [_build_parse_issue("E014", "P1", "L1", "期望数组输出，但模型返回了其他结构")], repair_actions=repair_actions)
                raise AgentStructuredOutputError("结构化输出根结构不匹配", error_code="parse_e014", severity="P1", decision="reask", parse_report=report)
            if method_name == "generate_blueprints":
                normalized = [_normalize_blueprint_item(dict(item), False) for item in business_payload if isinstance(item, dict)]
                if not normalized:
                    report = _build_parse_report(method_name, decision="reask", route="reask", envelope_status=envelope_status, issues=issues + [_build_parse_issue("E003", "P1", "L2", "候选蓝图列表为空")], repair_actions=repair_actions)
                    raise AgentStructuredOutputError("候选蓝图为空", error_code="parse_e003", severity="P1", decision="reask", parse_report=report)
                return normalized, _build_parse_report(method_name, decision="accepted" if not issues else "degraded", route="continue", envelope_status=envelope_status, issues=issues, repair_actions=repair_actions)
            normalized = [_normalize_scene_item(dict(item)) for item in business_payload if isinstance(item, dict)]
            if not normalized:
                report = _build_parse_report(method_name, decision="reask", route="reask", envelope_status=envelope_status, issues=issues + [_build_parse_issue("E003", "P1", "L2", "场景列表为空")], repair_actions=repair_actions)
                raise AgentStructuredOutputError("场景列表为空", error_code="parse_e003", severity="P1", decision="reask", parse_report=report)
            return normalized, _build_parse_report(method_name, decision="accepted" if not issues else "degraded", route="continue", envelope_status=envelope_status, issues=issues, repair_actions=repair_actions)

        if not isinstance(business_payload, dict):
            report = _build_parse_report(method_name, decision="reask", route="reask", envelope_status=envelope_status, issues=issues + [_build_parse_issue("E002", "P1", "L1", "期望对象输出，但模型返回了其他结构")], repair_actions=repair_actions)
            raise AgentStructuredOutputError("结构化输出根结构不匹配", error_code="parse_e002", severity="P1", decision="reask", parse_report=report)

        forbidden_keys = _detect_forbidden_write_keys(business_payload)
        if forbidden_keys:
            report = _build_parse_report(method_name, decision="rejected", route="human_review", envelope_status=envelope_status, issues=issues + [_build_parse_issue("E009", "P0", "L4", f"输出包含越权写入信号: {', '.join(forbidden_keys)}")], repair_actions=repair_actions)
            raise AgentStructuredOutputError("检测到越权写入信号", error_code="parse_e009", severity="P0", decision="rejected", parse_report=report)

        if method_name == "review_gate":
            normalized = _normalize_gate_review_payload(business_payload, provider=provider_name, model=model_name)
            allowed = {"passed", "warning", "failed"}
            if normalized["pass_status"] not in allowed:
                issues.append(_build_parse_issue("E005", "P1", "L2", "pass_status 枚举越界", "pass_status"))
                normalized["pass_status"] = "warning"
            return normalized, _build_parse_report(method_name, decision="accepted" if not issues else "degraded", route="continue" if not issues else "human_review", envelope_status=envelope_status, issues=issues, repair_actions=repair_actions)

        if method_name == "propose_changeset":
            normalized = _normalize_changeset_proposal(business_payload, provider=provider_name, model=model_name, context=context)
            decision = "accepted"
            route = "continue"
            if not normalized.get("patch_operations"):
                issues.append(_build_parse_issue("E003", "P1", "L2", "ChangeSet 提议缺少 patch_operations，已转人工审阅", "patch_operations"))
                normalized["review_recommendation"] = "human_review"
                decision = "human_review"
                route = "human_review"
            return normalized, _build_parse_report(method_name, decision=decision if not issues else decision, route=route, envelope_status=envelope_status, issues=issues, repair_actions=repair_actions)

        normalized = _normalize_chapter_summary_payload(business_payload, provider=provider_name, model=model_name)
        if not str(normalized.get("next_chapter_seed") or "").strip():
            issues.append(_build_parse_issue("E003", "P2", "L2", "章节摘要缺少 next_chapter_seed，已用摘要降级补齐", "next_chapter_seed"))
            normalized["next_chapter_seed"] = normalized["summary"][:120]
        return normalized, _build_parse_report(method_name, decision="accepted" if not issues else "degraded", route="continue", envelope_status=envelope_status, issues=issues, repair_actions=repair_actions)

    def status(self) -> GatewayStatus:
        configured = settings.agent_provider.strip().lower() or "mock"
        fallback_enabled = settings.agent_fallback_to_mock
        if configured == "openai_compatible":
            if settings.agent_api_base_url and settings.agent_model:
                return GatewayStatus(configured_provider=configured, active_provider=configured, model=settings.agent_model, fallback_enabled=fallback_enabled, fallback_active=False, available=True)
            reason = "缺少 AGENT_API_BASE_URL 或 AGENT_MODEL，已回退到 mock provider。"
            return GatewayStatus(configured_provider=configured, active_provider="mock", model=settings.agent_model, fallback_enabled=fallback_enabled, fallback_active=True, available=fallback_enabled, reason=reason)
        return GatewayStatus(configured_provider=configured, active_provider="mock", model=settings.agent_model, fallback_enabled=fallback_enabled, fallback_active=False, available=True, reason="当前使用内置 mock provider。")

    def governance_snapshot(self, db: Session | None) -> dict[str, Any]:
        provider = self._resolve_provider()
        snapshot = provider_governance_service.get_governance_snapshot(db=db, provider_name=provider.name)
        if db is not None:
            from app.services.agent_call_service import agent_call_service
            snapshot["recent_call_stats"] = agent_call_service.get_stats(db=db).model_dump(mode="json")
        return snapshot

    def generate_blueprints(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="generate_blueprints", agent_type="planner", method_name="generate_blueprints", context=context, audit_context=audit_context)

    def decompose_scenes(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="decompose_scenes", agent_type="scene_decomposer", method_name="decompose_scenes", context=context, audit_context=audit_context)

    def generate_draft(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="generate_draft", agent_type="writer", method_name="generate_draft", context=context, audit_context=audit_context)

    def revise_draft(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="revise_draft", agent_type="writer", method_name="revise_draft", context=context, audit_context=audit_context)

    def review_gate(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="review_gate", agent_type="gate_reviewer", method_name="review_gate", context=context, audit_context=audit_context)

    def propose_changeset(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="propose_changeset", agent_type="changeset_proposer", method_name="propose_changeset", context=context, audit_context=audit_context)

    def summarize_chapter(self, db: Session | None, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        return self._invoke(db=db, action_name="summarize_chapter", agent_type="summarizer", method_name="summarize_chapter", context=context, audit_context=audit_context)

    def _invoke(self, db: Session | None, action_name: str, agent_type: str, method_name: str, context: dict[str, Any], audit_context: dict[str, Any]) -> AgentInvocationResult:
        set_log_context(
            project_id=str(audit_context.get("project_id") or context.get("project_id") or None),
            workflow_run_id=str(audit_context.get("workflow_run_id") or ""),
            trace_id=str(audit_context.get("trace_id") or ""),
            module="agent_gateway",
            event="agent_gateway.invoke",
            status="started",
        )
        if action_name != "review_gate":
            logger.info(
                "开始调用 Agent Gateway",
                extra={
                    "extra_fields": {
                        "project_id": audit_context.get("project_id") or context.get("project_id"),
                        "workflow_run_id": audit_context.get("workflow_run_id"),
                        "trace_id": audit_context.get("trace_id"),
                        "agent_type": agent_type,
                        "action": action_name,
                    }
                },
            )
        configured_provider = settings.agent_provider.strip().lower() or "mock"
        provider = self._resolve_provider()
        resolved_project_id = str(audit_context.get("project_id") or context.get("project_id") or "") or None
        resolved_genre_id = str(audit_context.get("genre_id") or context.get("genre_id") or "") or None
        try:
            enriched_context = rulepack_service.extend_agent_context(
                db=db,
                project_id=resolved_project_id,
                genre_id=resolved_genre_id,
                context=context,
            )
        except Exception:
            enriched_context = dict(context)
        prompt_resolution = prompt_template_service.resolve_template(
            db=db,
            project_id=resolved_project_id,
            genre_id=resolved_genre_id,
            agent_type=agent_type,
            action_name=action_name,
            provider_scope=configured_provider if configured_provider else "all",
            render_context=enriched_context,
        )

        preflight = provider_governance_service.preflight(db=db, provider_name=provider.name)
        if not preflight.allowed:
            return self._handle_preflight_block(
                db=db,
                preflight=preflight,
                provider=provider,
                action_name=action_name,
                agent_type=agent_type,
                method_name=method_name,
                context=enriched_context,
                audit_context=audit_context,
                configured_provider=configured_provider,
                prompt_resolution=prompt_resolution,
            )

        start = time.perf_counter()
        payload: Any = None
        parse_report: dict[str, Any] | None = None
        fallback_used = False
        error_message: str | None = None
        error_type: str | None = None
        call_status = "success"
        active_provider = provider.name
        model_name = self._resolve_model_name(provider)
        attempt_count = 0
        circuit_state_at_call = preflight.circuit_state
        rate_limited = False

        try:
            payload, attempt_count = self._invoke_with_retry(provider=provider, method_name=method_name, context=enriched_context, prompt_resolution=prompt_resolution)
            provider_governance_service.record_success(db=db, provider_name=provider.name)

            if method_name in STRUCTURED_OUTPUT_SPECS:
                try:
                    payload, parse_report = self._process_structured_payload(method_name=method_name, payload=payload, provider_name=provider.name, model_name=model_name, context=enriched_context)
                except AgentStructuredOutputError as exc:
                    parse_report = dict(exc.parse_report)
                    if exc.decision == "reask" and provider.name != "mock":
                        repaired_prompt = self._build_reask_prompt_resolution(prompt_resolution, parse_report)
                        retry_payload = getattr(provider, method_name)(enriched_context, repaired_prompt)
                        attempt_count += 1
                        payload, parse_report = self._process_structured_payload(method_name=method_name, payload=retry_payload, provider_name=provider.name, model_name=model_name, context=enriched_context)
                        parse_report["reask_count"] = int(parse_report.get("reask_count") or 0) + 1
                        parse_report.setdefault("repair_actions", []).append("structured_reask")
                    elif provider.name != "mock" and settings.agent_fallback_to_mock:
                        fallback_used = True
                        call_status = "fallback_success"
                        error_type = exc.error_code
                        error_message = str(exc)
                        provider_governance_service.record_failure(db=db, provider_name=provider.name, error_type=exc.error_code, error_message=str(exc))
                        provider = self._mock_provider
                        active_provider = provider.name
                        model_name = self._resolve_model_name(provider)
                        payload = getattr(provider, method_name)(enriched_context, prompt_resolution)
                        if method_name in STRUCTURED_OUTPUT_SPECS:
                            payload, parse_report = self._process_structured_payload(method_name=method_name, payload=payload, provider_name=provider.name, model_name=model_name, context=enriched_context)
                            parse_report["decision"] = "degraded"
                            parse_report["route"] = "provider_fallback"
                            parse_report["degraded"] = True
                            parse_report.setdefault("repair_actions", []).append("provider_fallback_to_mock")
                            parse_report.setdefault("issues", []).append(_build_parse_issue("E002", "P1", "L1", "主 provider 结构化输出失败，已回退到 mock provider"))
                    else:
                        raise AgentProviderRequestError(str(exc), error_type=exc.error_code, retryable=False, attempt_count=attempt_count) from exc
        except AgentProviderRequestError as exc:
            error_message = str(exc)
            error_type = exc.error_type
            attempt_count = max(attempt_count, getattr(exc, "attempt_count", 1))
            provider_governance_service.record_failure(db=db, provider_name=provider.name, error_type=error_type, error_message=error_message)
            if provider.name != "mock" and settings.agent_fallback_to_mock:
                fallback_used = True
                call_status = "fallback_success"
                provider = self._mock_provider
                active_provider = provider.name
                model_name = self._resolve_model_name(provider)
                payload = getattr(provider, method_name)(enriched_context, prompt_resolution)
                if method_name in STRUCTURED_OUTPUT_SPECS:
                    payload, parse_report = self._process_structured_payload(method_name=method_name, payload=payload, provider_name=provider.name, model_name=model_name, context=enriched_context)
                    parse_report["decision"] = "degraded"
                    parse_report["route"] = "provider_fallback"
                    parse_report["degraded"] = True
                    parse_report.setdefault("repair_actions", []).append("provider_fallback_to_mock")
            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=False, latency_ms=latency_ms, request_summary=_summarize({"context": enriched_context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary={"parse_report": parse_report} if parse_report else {}, source_metadata=_summarize(audit_context), error_message=error_message)
                logger.exception(
                    "Agent 调用失败",
                    extra={"extra_fields": {"agent_type": agent_type, "action": action_name, "provider": active_provider, "model": model_name, "error_type": error_type}},
                )
                raise
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            error_type = "unexpected"
            attempt_count = max(attempt_count, getattr(exc, "attempt_count", 1))
            provider_governance_service.record_failure(db=db, provider_name=provider.name, error_type=error_type, error_message=error_message)
            if provider.name != "mock" and settings.agent_fallback_to_mock:
                fallback_used = True
                call_status = "fallback_success"
                provider = self._mock_provider
                active_provider = provider.name
                model_name = self._resolve_model_name(provider)
                payload = getattr(provider, method_name)(enriched_context, prompt_resolution)
                if method_name in STRUCTURED_OUTPUT_SPECS:
                    payload, parse_report = self._process_structured_payload(method_name=method_name, payload=payload, provider_name=provider.name, model_name=model_name, context=enriched_context)
                    parse_report["decision"] = "degraded"
                    parse_report["route"] = "provider_fallback"
                    parse_report["degraded"] = True
                    parse_report.setdefault("repair_actions", []).append("provider_fallback_to_mock")
            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=False, latency_ms=latency_ms, request_summary=_summarize({"context": enriched_context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary={"parse_report": parse_report} if parse_report else {}, source_metadata=_summarize(audit_context), error_message=error_message)
                logger.exception(
                    "Agent 调用失败",
                    extra={"extra_fields": {"agent_type": agent_type, "action": action_name, "provider": active_provider, "model": model_name, "error_type": error_type}},
                )
                raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        response_summary = _summarize(payload)
        if isinstance(response_summary, dict) and parse_report is not None:
            response_summary["parse_report"] = _summarize(parse_report)
        elif parse_report is not None:
            response_summary = {"value": response_summary, "parse_report": _summarize(parse_report)}
        self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=fallback_used, call_status=call_status, attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": enriched_context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary=response_summary, source_metadata=_summarize(audit_context), error_message=error_message)
        if fallback_used or (parse_report or {}).get("degraded"):
            logger.warning(
                "Agent 调用降级",
                extra={
                    "extra_fields": {
                        "agent_type": agent_type,
                        "action": action_name,
                        "provider": active_provider,
                        "model": model_name,
                        "fallback_used": fallback_used,
                        "call_status": call_status,
                        "latency_ms": latency_ms,
                        "stop_reason": (parse_report or {}).get("route"),
                    }
                },
            )
        return AgentInvocationResult(payload=payload, configured_provider=configured_provider, active_provider=active_provider, model=model_name, prompt_template_id=prompt_resolution.template_id, prompt_template_key=prompt_resolution.template_key, prompt_template_version=prompt_resolution.template_version, prompt_scope_type=prompt_resolution.scope_type, prompt_scope_key=prompt_resolution.scope_key, prompt_provider_scope=prompt_resolution.provider_scope, fallback_used=fallback_used, call_status=call_status, latency_ms=latency_ms, attempt_count=attempt_count, error_type=error_type, error_message=error_message, circuit_state_at_call=circuit_state_at_call, rate_limited=rate_limited, parse_report=parse_report)

    def _handle_preflight_block(self, db: Session | None, preflight: ProviderPreflightResult, provider: AgentProvider, action_name: str, agent_type: str, method_name: str, context: dict[str, Any], audit_context: dict[str, Any], configured_provider: str, prompt_resolution: PromptTemplateResolution) -> AgentInvocationResult:
        start = time.perf_counter()
        if settings.agent_fallback_to_mock and provider.name != "mock":
            payload = getattr(self._mock_provider, method_name)(context, prompt_resolution)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Agent 调用触发治理降级，已回退到 mock provider",
                extra={
                    "extra_fields": {
                        "agent_type": agent_type,
                        "action": action_name,
                        "provider": provider.name,
                        "fallback_provider": "mock",
                        "stop_reason": preflight.reason,
                        "rate_limited": preflight.rate_limited,
                    }
                },
            )
            self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider="mock", model_name=settings.agent_model, prompt_resolution=prompt_resolution, fallback_used=True, call_status="fallback_success", attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": context}), response_summary=_summarize(payload), source_metadata=_summarize(audit_context), error_message=preflight.reason)
            return AgentInvocationResult(payload=payload, configured_provider=configured_provider, active_provider="mock", model=settings.agent_model, prompt_template_id=prompt_resolution.template_id, prompt_template_key=prompt_resolution.template_key, prompt_template_version=prompt_resolution.template_version, prompt_scope_type=prompt_resolution.scope_type, prompt_scope_key=prompt_resolution.scope_key, prompt_provider_scope=prompt_resolution.provider_scope, fallback_used=True, call_status="fallback_success", latency_ms=latency_ms, attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", error_message=preflight.reason, circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited)
        latency_ms = int((time.perf_counter() - start) * 1000)
        self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=provider.name, model_name=self._resolve_model_name(provider), prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": context}), response_summary={}, source_metadata=_summarize(audit_context), error_message=preflight.reason)
        logger.error(
            "Agent 调用被治理策略阻断",
            extra={
                "extra_fields": {
                    "agent_type": agent_type,
                    "action": action_name,
                    "provider": provider.name,
                    "stop_reason": preflight.reason,
                    "rate_limited": preflight.rate_limited,
                }
            },
        )
        raise AgentGatewayError(preflight.reason or "Provider 当前不可用")

    def _invoke_with_retry(self, provider: AgentProvider, method_name: str, context: dict[str, Any], prompt_resolution: PromptTemplateResolution) -> tuple[Any, int]:
        attempt = 0
        while True:
            attempt += 1
            try:
                payload = getattr(provider, method_name)(context, prompt_resolution)
                return payload, attempt
            except AgentProviderRequestError as exc:
                exc.attempt_count = attempt
                if attempt > settings.agent_max_retries or not exc.retryable:
                    raise
                sleep_seconds = (settings.agent_retry_backoff_ms / 1000.0) * (settings.agent_retry_backoff_multiplier ** (attempt - 1))
                time.sleep(min(sleep_seconds, 10.0))

    def _record_call(self, db: Session | None, project_id: str, workflow_name: str | None, workflow_run_id: str | None, trace_id: str | None, agent_type: str, action_name: str, configured_provider: str, active_provider: str, model_name: str, prompt_resolution: PromptTemplateResolution, fallback_used: bool, call_status: str, attempt_count: int, error_type: str | None, circuit_state_at_call: str | None, rate_limited: bool, latency_ms: int, request_summary: Any, response_summary: Any, source_metadata: Any, error_message: str | None) -> None:
        if db is None or not project_id:
            return
        log = AgentCallLogORM(
            project_id=project_id,
            workflow_name=workflow_name,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            agent_type=agent_type,
            action_name=action_name,
            configured_provider=configured_provider,
            active_provider=active_provider,
            model_name=model_name,
            prompt_template_id=prompt_resolution.template_id,
            prompt_template_key=prompt_resolution.template_key,
            prompt_template_version=prompt_resolution.template_version,
            prompt_scope_type=prompt_resolution.scope_type,
            prompt_scope_key=prompt_resolution.scope_key,
            prompt_provider_scope=prompt_resolution.provider_scope,
            fallback_used=fallback_used,
            call_status=call_status,
            attempt_count=attempt_count,
            error_type=error_type,
            circuit_state_at_call=circuit_state_at_call,
            rate_limited=rate_limited,
            latency_ms=latency_ms,
            request_summary=request_summary if isinstance(request_summary, dict) else {"value": request_summary},
            response_summary=response_summary if isinstance(response_summary, dict) else {"value": response_summary},
            source_metadata=source_metadata if isinstance(source_metadata, dict) else {"value": source_metadata},
            error_message=_truncate_string(error_message) if error_message else None,
        )
        db.add(log)
        db.flush()

    def _resolve_provider(self) -> AgentProvider:
        configured = settings.agent_provider.strip().lower()
        if configured == "openai_compatible" and settings.agent_api_base_url and settings.agent_model:
            return OpenAICompatibleProvider(base_url=settings.agent_api_base_url, api_key=settings.agent_api_key, model=settings.agent_model, timeout_seconds=settings.agent_timeout_seconds, temperature=settings.agent_temperature)
        return self._mock_provider

    def _resolve_model_name(self, provider: AgentProvider) -> str:
        return getattr(provider, "model", settings.agent_model) or settings.agent_model


agent_gateway = AgentGateway()
