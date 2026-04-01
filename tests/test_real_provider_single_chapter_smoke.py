"""阶段三第一刀：真实 provider + 禁 fallback + 单章黄金样例冒烟验收。"""

import unittest
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


class RealProviderSingleChapterSmokeTest(unittest.TestCase):
    """验证真实 provider 下单章主链可闭环，且全程无 fallback。"""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"real-provider-smoke-{uuid4().hex[:8]}",
                "premise": "阶段三真实 provider 单章黄金样例冒烟验收",
                "genre_id": "default",
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _init_canon_snapshot(self, project_id: str) -> str:
        resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "real-provider-smoke-initial-snapshot",
                "initial_rules": [{"rule_name": "世界规则", "description": "基础规则", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _diagnostic_recent_calls(self, agent_calls: list[dict[str, Any]], limit: int = 8) -> str:
        lines: list[str] = []
        for item in agent_calls[:limit]:
            response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
            parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
            provider_error_details = response_summary.get("provider_error_details") if isinstance(response_summary, dict) else None
            provider_status_code = None
            provider_error_body = None
            provider_model = item.get("model_name")
            message_count = None
            system_prompt_length = None
            user_prompt_length = None
            if isinstance(provider_error_details, dict):
                provider_status_code = provider_error_details.get("provider_status_code") or provider_error_details.get("status_code")
                provider_error_body = provider_error_details.get("provider_error_body")
                provider_model = provider_error_details.get("model") or provider_model
                message_count = provider_error_details.get("message_count")
                system_prompt_length = provider_error_details.get("system_prompt_length")
                user_prompt_length = provider_error_details.get("user_prompt_length")
            lines.append(
                (
                    f"action={item.get('action_name')} "
                    f"configured={item.get('configured_provider')} "
                    f"active={item.get('active_provider')} "
                    f"model={provider_model} "
                    f"status={item.get('call_status')} "
                    f"fallback_used={item.get('fallback_used')} "
                    f"error_type={item.get('error_type')} "
                    f"provider_status_code={provider_status_code} "
                    f"message_count={message_count} "
                    f"system_prompt_length={system_prompt_length} "
                    f"user_prompt_length={user_prompt_length} "
                    f"provider_error_body={provider_error_body} "
                    f"parse_report={parse_report}"
                )
            )
        return "\n".join(lines)

    def _assert_gateway_preflight(self) -> dict[str, Any]:
        resp = self.client.get("/api/v1/workflows/agent-gateway/status")
        self.assertEqual(resp.status_code, 200, msg="真实 provider 预检失败：无法读取 gateway 状态。")
        data = resp.json()["data"]

        problems: list[str] = []
        if data.get("configured_provider") != "openai_compatible":
            problems.append(f"configured_provider={data.get('configured_provider')}")
        if data.get("active_provider") != "openai_compatible":
            problems.append(f"active_provider={data.get('active_provider')}")
        if bool(data.get("fallback_active")):
            problems.append(f"fallback_active={data.get('fallback_active')}")
        if not bool(data.get("available")):
            problems.append(f"available={data.get('available')}")

        if problems:
            self.fail(
                "真实 provider 预检不通过：\n"
                "- 期望 configured_provider/active_provider 都是 openai_compatible，fallback_active=False，available=True。\n"
                f"- 实际状态：{data}\n"
                f"- 异常项：{'; '.join(problems)}\n"
                "- 本测试禁止 fallback/mock 自动降级，请先修复环境配置后重试。"
            )
        return data

    def _extract_provider_error_snapshot(self, agent_calls: list[dict[str, Any]]) -> dict[str, Any]:
        for item in agent_calls:
            response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
            details = response_summary.get("provider_error_details") if isinstance(response_summary, dict) else None
            if isinstance(details, dict):
                return {
                    "action_name": item.get("action_name"),
                    "active_provider": item.get("active_provider"),
                    "model": details.get("model") or item.get("model_name"),
                    "provider_status_code": details.get("provider_status_code") or details.get("status_code"),
                    "message_count": details.get("message_count"),
                    "system_prompt_length": details.get("system_prompt_length"),
                    "user_prompt_length": details.get("user_prompt_length"),
                    "retryable": details.get("retryable"),
                    "provider_error_body": details.get("provider_error_body"),
                }
        return {}

    def test_real_provider_single_chapter_smoke(self):
        gateway_status = self._assert_gateway_preflight()
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        try:
            goal_resp = self.client.post(
                "/api/v1/chapters/goals",
                json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "第一章建立冲突"},
            )
            self.assertEqual(goal_resp.status_code, 200)
            goal = goal_resp.json()["data"]

            blueprints_resp = self.client.post(
                "/api/v1/chapters/blueprints/generate",
                json={"project_id": project_id, "chapter_goal_id": goal["id"], "candidate_count": 3},
            )
            self.assertEqual(blueprints_resp.status_code, 200)
            blueprints = blueprints_resp.json()["data"]
            self.assertGreaterEqual(len(blueprints), 1)

            selected_resp = self.client.post(
                "/api/v1/chapters/blueprints/select",
                json={"project_id": project_id, "blueprint_id": blueprints[0]["id"], "selected_by": "stage3-smoke"},
            )
            self.assertEqual(selected_resp.status_code, 200)
            selected_blueprint = selected_resp.json()["data"]

            scenes_resp = self.client.post(
                "/api/v1/chapters/scenes/decompose",
                json={"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            self.assertEqual(scenes_resp.status_code, 200)
            self.assertGreaterEqual(len(scenes_resp.json()["data"]), 1)

            draft_resp = self.client.post(
                "/api/v1/chapters/drafts/generate",
                json={"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            self.assertEqual(draft_resp.status_code, 200)
            draft = draft_resp.json()["data"]

            gate_resp = self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft["id"]},
            )
            self.assertEqual(gate_resp.status_code, 200)

            proposal_resp = self.client.post(
                f"/api/v1/chapters/drafts/{draft['id']}/changeset-proposals/generate",
                json={"project_id": project_id},
            )
            self.assertEqual(proposal_resp.status_code, 200)
            proposal = proposal_resp.json()["data"]

            changeset_resp = self.client.post(
                "/api/v1/changesets/propose",
                json={
                    "project_id": project_id,
                    "source_type": "chapter_draft",
                    "source_ref": draft["id"],
                    "rationale": proposal["rationale"],
                    "patch_operations": proposal["patch_operations"],
                },
            )
            self.assertEqual(changeset_resp.status_code, 200)
            changeset = changeset_resp.json()["data"]

            approve_resp = self.client.post(
                f"/api/v1/changesets/{changeset['id']}/approve",
                json={"approved_by": "stage3-smoke"},
            )
            self.assertEqual(approve_resp.status_code, 200)

            apply_resp = self.client.post(f"/api/v1/changesets/{changeset['id']}/apply")
            self.assertEqual(apply_resp.status_code, 200)

            publish_resp = self.client.post(
                "/api/v1/chapters/drafts/publish",
                json={"project_id": project_id, "draft_id": draft["id"], "published_by": "stage3-smoke"},
            )
            self.assertEqual(publish_resp.status_code, 200)
            publish_data = publish_resp.json()["data"]
            self.assertEqual(
                publish_data["publish_record"]["publish_status"],
                "published",
                msg=f"发布失败，gateway={gateway_status}，publish={publish_data}",
            )

            published_id = publish_data["published_chapter"]["id"]
            summary_resp = self.client.post(
                f"/api/v1/chapters/published/{published_id}/summary/generate",
                json={"project_id": project_id, "published_chapter_id": published_id},
            )
            self.assertEqual(summary_resp.status_code, 200)
            summary = summary_resp.json()["data"]
            self.assertTrue(summary.get("summary"), msg=f"summary 为空，返回数据：{summary}")
            self.assertTrue(summary.get("next_chapter_seed"), msg=f"next_chapter_seed 为空，返回数据：{summary}")

            derived_resp = self.client.post(
                f"/api/v1/chapters/published/{published_id}/derived-updates/run",
                json={"project_id": project_id, "published_chapter_id": published_id},
            )
            self.assertEqual(derived_resp.status_code, 200)
            derived = derived_resp.json()["data"]
            self.assertGreaterEqual(len(derived.get("tasks") or []), 1, msg=f"derived updates 任务为空：{derived}")
            for task in derived["tasks"]:
                self.assertTrue(task.get("task_name"), msg=f"derived task 缺少 task_name：{task}")
                self.assertTrue(task.get("status"), msg=f"derived task 缺少 status：{task}")
                self.assertTrue(task.get("summary"), msg=f"derived task 缺少 summary：{task}")
                self.assertIsInstance(task.get("details"), dict, msg=f"derived task details 非对象：{task}")

            calls_resp = self.client.get(
                "/api/v1/workflows/agent-calls",
                params={"project_id": project_id, "limit": 200},
            )
            self.assertEqual(calls_resp.status_code, 200)
            agent_calls = calls_resp.json()["data"]
            self.assertGreaterEqual(len(agent_calls), 1, msg=f"未查询到 agent 调用日志，project_id={project_id}")

            diagnostics = self._diagnostic_recent_calls(agent_calls)
            for item in agent_calls:
                self.assertNotEqual(item.get("active_provider"), "mock", msg=f"检测到 mock provider 调用，违反真实 provider 验收。\n{diagnostics}")
                self.assertFalse(bool(item.get("fallback_used")), msg=f"检测到 fallback_used=True，违反禁 fallback 要求。\n{diagnostics}")
                self.assertNotEqual(item.get("call_status"), "fallback_success", msg=f"检测到 call_status=fallback_success，违反禁 fallback 要求。\n{diagnostics}")

                response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
                parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
                if isinstance(parse_report, dict):
                    self.assertFalse(bool(parse_report.get("degraded")), msg=f"结构化输出 degraded=True，不满足阶段三冒烟要求。\nparse_report={parse_report}\n{diagnostics}")
                    self.assertNotEqual(parse_report.get("route"), "provider_fallback", msg=f"结构化输出 route=provider_fallback，违反禁 fallback 要求。\nparse_report={parse_report}\n{diagnostics}")
                    self.assertNotEqual(parse_report.get("decision"), "failed", msg=f"结构化输出 decision=failed，冒烟验收失败。\nparse_report={parse_report}\n{diagnostics}")
        except Exception as exc:  # noqa: BLE001
            status_resp = self.client.get("/api/v1/workflows/agent-gateway/status")
            status_data = status_resp.json().get("data") if status_resp.status_code == 200 else {"status_code": status_resp.status_code}
            calls_resp = self.client.get("/api/v1/workflows/agent-calls", params={"project_id": project_id, "limit": 20})
            recent_calls = calls_resp.json().get("data", []) if calls_resp.status_code == 200 else []
            provider_error_snapshot = self._extract_provider_error_snapshot(recent_calls)
            exc_details = getattr(exc, "details", {}) if isinstance(getattr(exc, "details", {}), dict) else {}
            self.fail(
                "真实 provider 冒烟链路执行失败，请排查以下诊断信息：\n"
                f"- 异常类型: {type(exc).__name__}\n"
                f"- 异常信息: {exc}\n"
                f"- 异常 details: {exc_details}\n"
                f"- gateway_status(执行前): {gateway_status}\n"
                f"- gateway_status(失败时): {status_data}\n"
                f"- provider 错误快照: {provider_error_snapshot}\n"
                f"- 最近 agent 调用:\n{self._diagnostic_recent_calls(recent_calls)}"
            )


if __name__ == "__main__":
    unittest.main()
