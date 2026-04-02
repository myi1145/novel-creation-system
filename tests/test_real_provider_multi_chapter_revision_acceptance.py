"""阶段三：真实 provider 下连续章节 + revise loop 协同验收。"""

import unittest
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


class RealProviderMultiChapterRevisionAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"real-provider-seq-revision-{uuid4().hex[:8]}",
                "premise": "阶段三真实 provider 多章+revision 验收",
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
                "title": "real-provider-seq-revision-initial-snapshot",
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
        problems = []
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
                "真实 provider 预检不通过（fail fast）：\n"
                f"gateway_status={data}\n"
                f"异常项={'; '.join(problems)}\n"
                "本测试禁止 fallback/mock，请先修复环境后重试。"
            )
        return data

    def _list_agent_calls(self, project_id: str, limit: int = 300) -> list[dict[str, Any]]:
        resp = self.client.get("/api/v1/workflows/agent-calls", params={"project_id": project_id, "limit": limit})
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def _diagnostic_recent_calls(self, calls: list[dict[str, Any]], limit: int = 12) -> str:
        rows = []
        for item in calls[:limit]:
            summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
            rows.append(
                (
                    f"action={item.get('action_name')} "
                    f"configured={item.get('configured_provider')} "
                    f"active={item.get('active_provider')} "
                    f"status={item.get('call_status')} "
                    f"fallback_used={item.get('fallback_used')} "
                    f"error_type={item.get('error_type')} "
                    f"parse_report={summary.get('parse_report')}"
                )
            )
        return "\n".join(rows)

    def _chapter_digest(self, chapter_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        digest = []
        for item in chapter_results:
            run_meta = ((item.get("chapter_result") or {}).get("run") or {}).get("run_metadata") or {}
            digest.append(
                {
                    "chapter_no": item.get("chapter_no"),
                    "stage_status": item.get("stage_status"),
                    "next_action": item.get("next_action"),
                    "published_chapter_id": item.get("published_chapter_id"),
                    "latest_summary": bool(item.get("latest_summary")),
                    "latest_next_chapter_seed": bool(item.get("latest_next_chapter_seed")),
                    "derived_update_status": item.get("derived_update_status"),
                    "revision_attempt_count": run_meta.get("revision_attempt_count"),
                    "auto_revised": run_meta.get("auto_revised"),
                }
            )
        return digest

    def test_real_provider_multi_chapter_revision_acceptance(self):
        gateway_status = self._gateway_preflight()
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        try:
            seq_resp = self.client.post(
                "/api/v1/workflows/chapter-sequence/execute",
                json={
                    "project_id": project_id,
                    "start_chapter_no": 1,
                    "chapter_count": 2,
                    "current_volume_goal": "前两章建立主冲突并推进主角选择",
                    "testing_auto_select_first_blueprint": True,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                    "auto_propose_changeset": True,
                    "auto_approve_changeset": True,
                    "auto_apply_changeset": True,
                    "auto_publish": True,
                    "auto_run_post_publish_updates": True,
                    "approved_by": "stage3-real-seq-revision",
                    "published_by": "stage3-real-seq-revision",
                },
            )
            self.assertEqual(seq_resp.status_code, 200, msg=f"sequence 执行失败: {seq_resp.text}")
            data = seq_resp.json()["data"]
            chapter_results = list(data.get("chapter_results") or [])
            self.assertGreaterEqual(len(chapter_results), 1, msg=f"sequence 未返回章节结果: {data}")

            # D. 多章结果可解释
            chapter_nos = [int(item.get("chapter_no") or 0) for item in chapter_results]
            self.assertEqual(chapter_nos, sorted(chapter_nos), msg=f"chapter_no 非递增: {chapter_nos}")

            completed_items = [item for item in chapter_results if item.get("stage_status") == "completed"]
            for item in completed_items:
                self.assertTrue(item.get("published_chapter_id"), msg=f"已完成章缺少 published_chapter_id: {item}")
                self.assertTrue(item.get("latest_summary"), msg=f"已完成章缺少 latest_summary: {item}")
                self.assertTrue(item.get("latest_next_chapter_seed"), msg=f"已完成章缺少 latest_next_chapter_seed: {item}")
                self.assertIn(item.get("derived_update_status"), {"completed", "completed_with_warnings"}, msg=f"derived 状态异常: {item}")

            if len(completed_items) >= 2:
                first = completed_items[0]
                second_cycle = completed_items[1].get("chapter_result") or {}
                continuity_pack = second_cycle.get("continuity_pack") or {}
                self.assertEqual(
                    continuity_pack.get("source_published_chapter_id"),
                    first.get("published_chapter_id"),
                    msg=f"第2章 continuity 未承接第1章发布态: continuity={continuity_pack}, first={first}",
                )

            # E. revise-aware：允许触发或不触发 revise，但结构语义必须合理
            revised_items = []
            for item in chapter_results:
                run_meta = ((item.get("chapter_result") or {}).get("run") or {}).get("run_metadata") or {}
                if bool(run_meta.get("auto_revised")) or int(run_meta.get("revision_attempt_count") or 0) > 0:
                    revised_items.append(item)
            if revised_items:
                for item in revised_items:
                    run_meta = ((item.get("chapter_result") or {}).get("run") or {}).get("run_metadata") or {}
                    self.assertGreaterEqual(int(run_meta.get("revision_attempt_count") or 0), 1, msg=f"auto_revised 章缺少 revision_attempt_count: {item}")
            else:
                # 本次真实样例可不触发 revise，但要明确记录并检查字段语义
                self.assertTrue(
                    all(
                        "revision_attempt_count" in (((item.get("chapter_result") or {}).get("run") or {}).get("run_metadata") or {})
                        or ((item.get("chapter_result") or {}).get("run") or {}).get("run_metadata") is not None
                        for item in chapter_results
                    ),
                    msg=f"本次未触发 revise，但 run_metadata 结构异常: {self._chapter_digest(chapter_results)}",
                )

            if data.get("batch_status") == "attention_required":
                self.assertIsNotNone(data.get("stopped_at_chapter_no"), msg=f"attention_required 但缺少 stopped_at_chapter_no: {data}")
                self.assertTrue(data.get("next_action"), msg=f"attention_required 但缺少 next_action: {data}")

            # B + C. agent calls 不允许 mock/fallback/degraded
            calls = self._list_agent_calls(project_id=project_id, limit=300)
            self.assertGreaterEqual(len(calls), 1, msg=f"未查询到 agent 调用日志，project_id={project_id}")
            diagnostics = self._diagnostic_recent_calls(calls)
            for item in calls:
                self.assertNotEqual(item.get("active_provider"), "mock", msg=f"检测到 mock provider 调用。\n{diagnostics}")
                self.assertFalse(bool(item.get("fallback_used")), msg=f"检测到 fallback_used=True。\n{diagnostics}")
                self.assertNotEqual(item.get("call_status"), "fallback_success", msg=f"检测到 call_status=fallback_success。\n{diagnostics}")
                summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
                parse_report = summary.get("parse_report") if isinstance(summary, dict) else None
                if isinstance(parse_report, dict):
                    self.assertFalse(bool(parse_report.get("degraded")), msg=f"parse_report.degraded=True。\n{diagnostics}")
                    self.assertNotEqual(parse_report.get("route"), "provider_fallback", msg=f"parse_report.route=provider_fallback。\n{diagnostics}")
                    self.assertNotEqual(parse_report.get("decision"), "failed", msg=f"parse_report.decision=failed。\n{diagnostics}")

        except Exception as exc:  # noqa: BLE001
            calls = self._list_agent_calls(project_id=project_id, limit=60)
            fail_payload = {
                "project_id": project_id,
                "gateway_status": gateway_status,
                "error": f"{type(exc).__name__}: {exc}",
                "sequence_workflow_run_id": (seq_resp.json().get("data", {}).get("run", {}).get("id") if "seq_resp" in locals() and seq_resp.status_code == 200 else None),
                "stopped_at_chapter_no": (seq_resp.json().get("data", {}).get("stopped_at_chapter_no") if "seq_resp" in locals() and seq_resp.status_code == 200 else None),
                "next_action": (seq_resp.json().get("data", {}).get("next_action") if "seq_resp" in locals() and seq_resp.status_code == 200 else None),
                "chapter_digest": (
                    self._chapter_digest(seq_resp.json().get("data", {}).get("chapter_results") or [])
                    if "seq_resp" in locals() and seq_resp.status_code == 200
                    else []
                ),
                "recent_agent_calls": self._diagnostic_recent_calls(calls, limit=15),
            }
            self.fail(f"真实 provider 多章+revision 验收失败:\n{fail_payload}")


if __name__ == "__main__":
    unittest.main()
