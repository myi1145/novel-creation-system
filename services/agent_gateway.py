from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AgentCallLogORM
from app.services.prompt_template_service import PromptTemplateResolution, prompt_template_service
from app.services.provider_governance_service import ProviderPreflightResult, provider_governance_service


class AgentGatewayError(RuntimeError):
    pass


class AgentProviderRequestError(AgentGatewayError):
    def __init__(self, message: str, *, error_type: str, retryable: bool, status_code: int | None = None, attempt_count: int = 1) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code
        self.attempt_count = attempt_count


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


class AgentProvider(Protocol):
    name: str

    def generate_blueprints(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]: ...
    def decompose_scenes(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]: ...
    def generate_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def revise_draft(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def review_gate(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def propose_changeset(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...
    def summarize_chapter(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]: ...


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
            "当前使用 Mock Agent Provider；后续可切换为 OpenAI Compatible Provider。"
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
            "当前使用 Mock Agent Provider 生成修订版。"
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
            issues.append({"severity": "S0", "message": "当前为 Mock Canon 预检查，占位通过。", "suggestion": "后续可替换为真实 Canon Judge。"})
        elif gate_name == "style_gate" and len(content) < 120:
            issues.append({"severity": "S1", "message": "正文偏短，风格判断样本有限。", "suggestion": "可增加更多正文后再做风格判断。"})
        elif gate_name == "publish_gate" and "占位" in content:
            issues.append({"severity": "S1", "message": "正文仍带有占位痕迹。", "suggestion": "接入真实 Writer Provider 后再发布正式样章。"})
        elif gate_name not in {"schema_gate", "canon_gate", "style_gate", "publish_gate", "narrative_gate", "voice_gate"}:
            issues.append({"severity": "S1", "message": f"{gate_name} 当前走 Mock Review。", "suggestion": "后续替换为真实 Reviewer Agent。"})

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

    def generate_blueprints(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]:
        text = self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        items = _ensure_list(text)
        count = int(context.get("candidate_count", 3))
        return [_normalize_blueprint_item(item, idx == 0) for idx, item in enumerate(items[:count])]

    def decompose_scenes(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> list[dict[str, Any]]:
        text = self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        items = _ensure_list(text)
        return [_normalize_scene_item(item) for item in items]

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

    def review_gate(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        text = self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        data = _ensure_dict(text)
        return {
            "pass_status": str(data.get("pass_status") or "passed"),
            "highest_severity": str(data.get("highest_severity") or "S0"),
            "recommended_route": str(data.get("recommended_route") or "pass"),
            "can_override": bool(data.get("can_override", False)),
            "override_role": data.get("override_role"),
            "issues": [
                {
                    "severity": str(item.get("severity") or "S1"),
                    "message": str(item.get("message") or "模型未给出详细问题"),
                    "suggestion": item.get("suggestion"),
                }
                for item in list(data.get("issues") or [])
            ],
            "provider": self.name,
            "model": self.model,
        }

    def propose_changeset(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        text = self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        data = _ensure_dict(text)
        return _normalize_changeset_proposal(data, provider=self.name, model=self.model, context=context)

    def summarize_chapter(self, context: dict[str, Any], prompt: PromptTemplateResolution) -> dict[str, Any]:
        text = self._chat_json(system_prompt=prompt.system_prompt, user_prompt=prompt.user_prompt)
        data = _ensure_dict(text)
        return _normalize_chapter_summary_payload(data, provider=self.name, model=self.model)

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
                f"Provider HTTP 错误: {status_code}",
                error_type=error_type,
                retryable=retryable,
                status_code=status_code,
            ) from exc
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError) as exc:
            raise AgentProviderRequestError(f"Provider 网络错误: {exc}", error_type="network", retryable=True) from exc
        except Exception as exc:  # noqa: BLE001
            raise AgentProviderRequestError(f"调用 OpenAI Compatible Provider 失败: {exc}", error_type="provider_error", retryable=False) from exc

        try:
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            raise AgentProviderRequestError("Provider 返回结构无法解析", error_type="parse", retryable=False) from exc


# helpers

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
        configured_provider = settings.agent_provider.strip().lower() or "mock"
        provider = self._resolve_provider()
        prompt_resolution = prompt_template_service.resolve_template(
            db=db,
            project_id=str(audit_context.get("project_id") or context.get("project_id") or "") or None,
            genre_id=str(audit_context.get("genre_id") or context.get("genre_id") or "") or None,
            agent_type=agent_type,
            action_name=action_name,
            provider_scope=configured_provider if configured_provider else "all",
            render_context=context,
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
                context=context,
                audit_context=audit_context,
                configured_provider=configured_provider,
                prompt_resolution=prompt_resolution,
            )

        start = time.perf_counter()
        payload: Any = None
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
            payload, attempt_count = self._invoke_with_retry(provider=provider, method_name=method_name, context=context, prompt_resolution=prompt_resolution)
            provider_governance_service.record_success(db=db, provider_name=provider.name)
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
                payload = getattr(provider, method_name)(context, prompt_resolution)
            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=False, latency_ms=latency_ms, request_summary=_summarize({"context": context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary={}, source_metadata=_summarize(audit_context), error_message=error_message)
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
                payload = getattr(provider, method_name)(context, prompt_resolution)
            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=False, latency_ms=latency_ms, request_summary=_summarize({"context": context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary={}, source_metadata=_summarize(audit_context), error_message=error_message)
                raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=active_provider, model_name=model_name, prompt_resolution=prompt_resolution, fallback_used=fallback_used, call_status=call_status, attempt_count=attempt_count, error_type=error_type, circuit_state_at_call=circuit_state_at_call, rate_limited=rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": context, "system_prompt": prompt_resolution.system_prompt, "user_prompt": prompt_resolution.user_prompt}), response_summary=_summarize(payload), source_metadata=_summarize(audit_context), error_message=error_message)
        return AgentInvocationResult(payload=payload, configured_provider=configured_provider, active_provider=active_provider, model=model_name, prompt_template_id=prompt_resolution.template_id, prompt_template_key=prompt_resolution.template_key, prompt_template_version=prompt_resolution.template_version, prompt_scope_type=prompt_resolution.scope_type, prompt_scope_key=prompt_resolution.scope_key, prompt_provider_scope=prompt_resolution.provider_scope, fallback_used=fallback_used, call_status=call_status, latency_ms=latency_ms, attempt_count=attempt_count, error_type=error_type, error_message=error_message, circuit_state_at_call=circuit_state_at_call, rate_limited=rate_limited)

    def _handle_preflight_block(self, db: Session | None, preflight: ProviderPreflightResult, provider: AgentProvider, action_name: str, agent_type: str, method_name: str, context: dict[str, Any], audit_context: dict[str, Any], configured_provider: str, prompt_resolution: PromptTemplateResolution) -> AgentInvocationResult:
        start = time.perf_counter()
        if settings.agent_fallback_to_mock and provider.name != "mock":
            payload = getattr(self._mock_provider, method_name)(context, prompt_resolution)
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider="mock", model_name=settings.agent_model, prompt_resolution=prompt_resolution, fallback_used=True, call_status="fallback_success", attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": context}), response_summary=_summarize(payload), source_metadata=_summarize(audit_context), error_message=preflight.reason)
            return AgentInvocationResult(payload=payload, configured_provider=configured_provider, active_provider="mock", model=settings.agent_model, prompt_template_id=prompt_resolution.template_id, prompt_template_key=prompt_resolution.template_key, prompt_template_version=prompt_resolution.template_version, prompt_scope_type=prompt_resolution.scope_type, prompt_scope_key=prompt_resolution.scope_key, prompt_provider_scope=prompt_resolution.provider_scope, fallback_used=True, call_status="fallback_success", latency_ms=latency_ms, attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", error_message=preflight.reason, circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited)
        latency_ms = int((time.perf_counter() - start) * 1000)
        self._record_call(db=db, project_id=str(audit_context.get("project_id") or context.get("project_id") or ""), workflow_name=audit_context.get("workflow_name"), workflow_run_id=audit_context.get("workflow_run_id"), trace_id=audit_context.get("trace_id"), agent_type=agent_type, action_name=action_name, configured_provider=configured_provider, active_provider=provider.name, model_name=self._resolve_model_name(provider), prompt_resolution=prompt_resolution, fallback_used=False, call_status="error", attempt_count=0, error_type="rate_limited" if preflight.rate_limited else "circuit_open", circuit_state_at_call=preflight.circuit_state, rate_limited=preflight.rate_limited, latency_ms=latency_ms, request_summary=_summarize({"context": context}), response_summary={}, source_metadata=_summarize(audit_context), error_message=preflight.reason)
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
