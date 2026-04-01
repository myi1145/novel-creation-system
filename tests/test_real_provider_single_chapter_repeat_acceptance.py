"""阶段三：真实 provider 单章黄金样例重复验收（3 次串行）。"""

import time
import unittest
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


class RealProviderSingleChapterRepeatAcceptanceTest(unittest.TestCase):
    ITERATIONS = 3

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _timed_post(self, url: str, payload: dict[str, Any]) -> tuple[Any, int]:
        start = time.perf_counter()
        resp = self.client.post(url, json=payload)
        cost_ms = int((time.perf_counter() - start) * 1000)
        return resp, cost_ms

    def _create_project(self) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"real-provider-repeat-{uuid4().hex[:8]}",
                "premise": "阶段三真实 provider 单章黄金样例重复验收",
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
                "title": "real-provider-repeat-initial-snapshot",
                "initial_rules": [{"rule_name": "世界规则", "description": "基础规则", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _gateway_preflight(self) -> dict[str, Any]:
        resp = self.client.get("/api/v1/workflows/agent-gateway/status")
        self.assertEqual(resp.status_code, 200, msg="真实 provider 预检失败：无法读取 gateway 状态。")
        data = resp.json()["data"]
        errors = []
        if data.get("configured_provider") != "openai_compatible":
            errors.append(f"configured_provider={data.get('configured_provider')}")
        if data.get("active_provider") != "openai_compatible":
            errors.append(f"active_provider={data.get('active_provider')}")
        if bool(data.get("fallback_active")):
            errors.append(f"fallback_active={data.get('fallback_active')}")
        if not bool(data.get("available")):
            errors.append(f"available={data.get('available')}")
        if errors:
            self.fail(
                "真实 provider 重复验收预检不通过（fail fast）：\n"
                f"gateway_status={data}\n"
                f"异常项={'; '.join(errors)}\n"
                "请先修复真实 provider 配置后再执行重复验收。"
            )
        return data

    def _diagnostic_recent_calls(self, calls: list[dict[str, Any]], limit: int = 8) -> str:
        rows: list[str] = []
        for item in calls[:limit]:
            response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
            parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
            provider_error_details = response_summary.get("provider_error_details") if isinstance(response_summary, dict) else None
            rows.append(
                " ".join(
                    [
                        f"action={item.get('action_name')}",
                        f"active={item.get('active_provider')}",
                        f"model={item.get('model_name')}",
                        f"status={item.get('call_status')}",
                        f"fallback_used={item.get('fallback_used')}",
                        f"error_type={item.get('error_type')}",
                        f"provider_error_details={provider_error_details}",
                        f"parse_report={parse_report}",
                    ]
                )
            )
        return "\n".join(rows)

    def _run_single_iteration(self, iteration_no: int) -> dict[str, Any]:
        self._gateway_preflight()
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)
        iteration = {
            "iteration_no": iteration_no,
            "project_id": project_id,
            "success": False,
            "error": None,
            "gateway_status": None,
            "durations": {
                "total_duration_ms": 0,
                "generate_blueprints_duration_ms": 0,
                "decompose_scenes_duration_ms": 0,
                "generate_draft_duration_ms": 0,
                "review_gate_duration_ms": 0,
                "summary_duration_ms": 0,
            },
            "agent_call_count": 0,
            "parse_report_count": 0,
            "degraded_count": 0,
            "fallback_count": 0,
            "recent_calls": [],
        }

        start_total = time.perf_counter()
        try:
            gateway_resp = self.client.get("/api/v1/workflows/agent-gateway/status")
            self.assertEqual(gateway_resp.status_code, 200)
            iteration["gateway_status"] = gateway_resp.json().get("data")

            goal_resp, _ = self._timed_post(
                "/api/v1/chapters/goals",
                {"project_id": project_id, "chapter_no": 1, "current_volume_goal": "第一章建立冲突"},
            )
            self.assertEqual(goal_resp.status_code, 200)
            goal = goal_resp.json()["data"]

            blueprints_resp, blueprints_cost = self._timed_post(
                "/api/v1/chapters/blueprints/generate",
                {"project_id": project_id, "chapter_goal_id": goal["id"], "candidate_count": 3},
            )
            iteration["durations"]["generate_blueprints_duration_ms"] = blueprints_cost
            self.assertEqual(blueprints_resp.status_code, 200)
            blueprints = blueprints_resp.json()["data"]
            self.assertGreaterEqual(len(blueprints), 1)

            selected_resp, _ = self._timed_post(
                "/api/v1/chapters/blueprints/select",
                {"project_id": project_id, "blueprint_id": blueprints[0]["id"], "selected_by": "stage3-repeat"},
            )
            self.assertEqual(selected_resp.status_code, 200)
            selected_blueprint = selected_resp.json()["data"]

            scenes_resp, scenes_cost = self._timed_post(
                "/api/v1/chapters/scenes/decompose",
                {"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            iteration["durations"]["decompose_scenes_duration_ms"] = scenes_cost
            self.assertEqual(scenes_resp.status_code, 200)
            self.assertGreaterEqual(len(scenes_resp.json()["data"]), 1)

            draft_resp, draft_cost = self._timed_post(
                "/api/v1/chapters/drafts/generate",
                {"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
            )
            iteration["durations"]["generate_draft_duration_ms"] = draft_cost
            self.assertEqual(draft_resp.status_code, 200)
            draft = draft_resp.json()["data"]

            gate_resp, gate_cost = self._timed_post(
                "/api/v1/gates/reviews",
                {"project_id": project_id, "draft_id": draft["id"]},
            )
            iteration["durations"]["review_gate_duration_ms"] = gate_cost
            self.assertEqual(gate_resp.status_code, 200)

            proposal_resp, _ = self._timed_post(
                f"/api/v1/chapters/drafts/{draft['id']}/changeset-proposals/generate",
                {"project_id": project_id},
            )
            self.assertEqual(proposal_resp.status_code, 200)
            proposal = proposal_resp.json()["data"]

            changeset_resp, _ = self._timed_post(
                "/api/v1/changesets/propose",
                {
                    "project_id": project_id,
                    "source_type": "chapter_draft",
                    "source_ref": draft["id"],
                    "rationale": proposal["rationale"],
                    "patch_operations": proposal["patch_operations"],
                },
            )
            self.assertEqual(changeset_resp.status_code, 200)
            changeset = changeset_resp.json()["data"]

            approve_resp, _ = self._timed_post(
                f"/api/v1/changesets/{changeset['id']}/approve",
                {"approved_by": "stage3-repeat"},
            )
            self.assertEqual(approve_resp.status_code, 200)

            apply_resp, _ = self._timed_post(f"/api/v1/changesets/{changeset['id']}/apply", {})
            self.assertEqual(apply_resp.status_code, 200)

            publish_resp, _ = self._timed_post(
                "/api/v1/chapters/drafts/publish",
                {"project_id": project_id, "draft_id": draft["id"], "published_by": "stage3-repeat"},
            )
            self.assertEqual(publish_resp.status_code, 200)
            publish_data = publish_resp.json()["data"]
            self.assertEqual(publish_data["publish_record"]["publish_status"], "published")

            published_id = publish_data["published_chapter"]["id"]
            summary_resp, summary_cost = self._timed_post(
                f"/api/v1/chapters/published/{published_id}/summary/generate",
                {"project_id": project_id, "published_chapter_id": published_id},
            )
            iteration["durations"]["summary_duration_ms"] = summary_cost
            self.assertEqual(summary_resp.status_code, 200)
            summary = summary_resp.json()["data"]
            self.assertTrue(summary.get("summary"))
            self.assertTrue(summary.get("next_chapter_seed"))

            derived_resp, _ = self._timed_post(
                f"/api/v1/chapters/published/{published_id}/derived-updates/run",
                {"project_id": project_id, "published_chapter_id": published_id},
            )
            self.assertEqual(derived_resp.status_code, 200)
            derived = derived_resp.json()["data"]
            self.assertGreaterEqual(len(derived.get("tasks") or []), 1)

            calls_resp = self.client.get("/api/v1/workflows/agent-calls", params={"project_id": project_id, "limit": 300})
            self.assertEqual(calls_resp.status_code, 200)
            calls = calls_resp.json()["data"]
            iteration["recent_calls"] = calls[:10]
            self.assertGreaterEqual(len(calls), 1)

            parse_report_count = 0
            degraded_count = 0
            fallback_count = 0
            for item in calls:
                self.assertNotEqual(item.get("active_provider"), "mock")
                self.assertFalse(bool(item.get("fallback_used")))
                self.assertNotEqual(item.get("call_status"), "fallback_success")
                if bool(item.get("fallback_used")) or item.get("call_status") == "fallback_success":
                    fallback_count += 1

                response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
                parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None
                if isinstance(parse_report, dict):
                    parse_report_count += 1
                    self.assertFalse(bool(parse_report.get("degraded")))
                    self.assertNotEqual(parse_report.get("route"), "provider_fallback")
                    self.assertNotEqual(parse_report.get("decision"), "failed")
                    if bool(parse_report.get("degraded")):
                        degraded_count += 1

            iteration["agent_call_count"] = len(calls)
            iteration["parse_report_count"] = parse_report_count
            iteration["degraded_count"] = degraded_count
            iteration["fallback_count"] = fallback_count
            iteration["success"] = True
        except Exception as exc:  # noqa: BLE001
            iteration["error"] = f"{type(exc).__name__}: {exc}"
            calls_resp = self.client.get("/api/v1/workflows/agent-calls", params={"project_id": project_id, "limit": 30})
            if calls_resp.status_code == 200:
                iteration["recent_calls"] = calls_resp.json().get("data", [])
        finally:
            iteration["durations"]["total_duration_ms"] = int((time.perf_counter() - start_total) * 1000)
        return iteration

    def test_real_provider_single_chapter_repeat_acceptance(self):
        results: list[dict[str, Any]] = []
        for idx in range(1, self.ITERATIONS + 1):
            results.append(self._run_single_iteration(idx))

        successes = [item for item in results if item.get("success")]
        failures = [item for item in results if not item.get("success")]

        total_durations = [item["durations"]["total_duration_ms"] for item in results]
        drift_hint = ""
        if total_durations and min(total_durations) > 0:
            ratio = max(total_durations) / min(total_durations)
            if ratio > 2.5:
                drift_hint = f"注意：总耗时出现明显漂移，最慢/最快={ratio:.2f} (>2.5)。"

        if failures:
            success_brief = [
                {
                    "iteration": item["iteration_no"],
                    "project_id": item["project_id"],
                    "total_duration_ms": item["durations"]["total_duration_ms"],
                    "agent_call_count": item["agent_call_count"],
                }
                for item in successes
            ]
            failed = failures[0]
            self.fail(
                "真实 provider 单章重复验收失败：\n"
                f"- 失败轮次: 第{failed['iteration_no']}次\n"
                f"- 失败 project_id: {failed['project_id']}\n"
                f"- 失败原因: {failed['error']}\n"
                f"- 失败轮 gateway_status: {failed.get('gateway_status')}\n"
                f"- 已成功轮次: {success_brief}\n"
                f"- 耗时统计: {[item['durations'] for item in results]}\n"
                f"- 解析统计: {[{'iteration': r['iteration_no'], 'parse_report_count': r['parse_report_count'], 'degraded_count': r['degraded_count'], 'fallback_count': r['fallback_count']} for r in results]}\n"
                f"- 最近 agent 调用摘要:\n{self._diagnostic_recent_calls(failed.get('recent_calls') or [])}\n"
                f"- 漂移提示: {drift_hint or '无'}"
            )

        self.assertEqual(len(successes), self.ITERATIONS, msg=f"重复验收要求 3/3 成功，实际为 {len(successes)}/{self.ITERATIONS}")
        self.assertTrue(all(item["degraded_count"] == 0 for item in results), msg=f"存在 degraded 调用：{results}")
        self.assertTrue(all(item["fallback_count"] == 0 for item in results), msg=f"存在 fallback 调用：{results}")


if __name__ == "__main__":
    unittest.main()
