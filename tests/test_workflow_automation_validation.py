import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterGoalORM, WorkflowRunORM
from app.db.session import SessionLocal
from app.main import create_app


class WorkflowAutomationValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_provider = settings.agent_provider
        cls._original_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._original_provider
        settings.agent_fallback_to_mock = cls._original_fallback

    def _create_project(self) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"auto-validation-{uuid4().hex[:8]}",
                "premise": "自动化验证主链与 sequence 人工节点恢复",
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
                "title": "test-initial-snapshot",
                "initial_rules": [{"rule_name": "世界规则", "description": "基础规则", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def test_single_chapter_mainline_full_automation(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

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
            json={"project_id": project_id, "blueprint_id": blueprints[0]["id"], "selected_by": "tester"},
        )
        self.assertEqual(selected_resp.status_code, 200)
        selected_blueprint = selected_resp.json()["data"]

        scenes_resp = self.client.post(
            "/api/v1/chapters/scenes/decompose",
            json={"project_id": project_id, "blueprint_id": selected_blueprint["id"]},
        )
        self.assertEqual(scenes_resp.status_code, 200)
        scenes = scenes_resp.json()["data"]
        self.assertGreaterEqual(len(scenes), 1)

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
        gate_results = gate_resp.json()["data"]["results"]
        self.assertGreaterEqual(len(gate_results), 1)

        proposal_resp = self.client.post(
            f"/api/v1/chapters/drafts/{draft['id']}/changeset-proposals/generate",
            json={"project_id": project_id},
        )
        self.assertEqual(proposal_resp.status_code, 200)
        proposal = proposal_resp.json()["data"]
        self.assertGreaterEqual(len(proposal["patch_operations"]), 1)

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
        self.assertEqual(changeset["status"], "proposed")

        approve_resp = self.client.post(
            f"/api/v1/changesets/{changeset['id']}/approve",
            json={"approved_by": "tester"},
        )
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.json()["data"]["status"], "approved")

        apply_resp = self.client.post(f"/api/v1/changesets/{changeset['id']}/apply")
        self.assertEqual(apply_resp.status_code, 200)
        applied_changeset = apply_resp.json()["data"]
        self.assertEqual(applied_changeset["status"], "applied")
        self.assertTrue(applied_changeset.get("result_snapshot_id"))

        publish_resp = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft["id"], "published_by": "tester"},
        )
        self.assertEqual(publish_resp.status_code, 200)
        publish_data = publish_resp.json()["data"]
        self.assertEqual(publish_data["publish_record"]["publish_status"], "published")

        published_id = publish_data["published_chapter"]["id"]
        summary_resp = self.client.post(
            f"/api/v1/chapters/published/{published_id}/summary/generate",
            json={"project_id": project_id, "published_chapter_id": published_id},
        )
        self.assertEqual(summary_resp.status_code, 200)
        summary = summary_resp.json()["data"]
        self.assertTrue(summary["summary"])
        self.assertTrue(summary["state_summary"])

        derived_resp = self.client.post(
            f"/api/v1/chapters/published/{published_id}/derived-updates/run",
            json={"project_id": project_id, "published_chapter_id": published_id},
        )
        self.assertEqual(derived_resp.status_code, 200)
        derived = derived_resp.json()["data"]
        self.assertIn(derived["status"], ["completed", "completed_with_warnings"])
        self.assertGreaterEqual(len(derived["tasks"]), 1)

        # 对 gate 输出不做全量通过断言（不同规则/题材下可能有软失败），改为断言结构和关键链路状态。
        self.assertTrue(all("pass_status" in item for item in gate_results))
        self.assertEqual(publish_data["published_chapter"]["changeset_id"], applied_changeset["id"])

    def test_sequence_should_stop_at_attention_required_with_next_action(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()["data"]

        self.assertIn(body["stage_status"], ["attention_required", "completed"])
        # 默认 stop_on_attention=True，当前工程联调实现应停在人工选蓝图。
        self.assertEqual(body["stage_status"], "attention_required")
        self.assertEqual(body["next_action"], "select_blueprint")
        self.assertEqual(body["run"]["status"], "attention_required")
        self.assertIsInstance(body["chapter_results"], list)
        self.assertGreaterEqual(len(body["chapter_results"]), 1)
        chapter_result = body["chapter_results"][0]["chapter_result"]
        self.assertGreaterEqual(len(chapter_result["blueprints"]), 1)
        self.assertIn("stop_reason", body)

    def test_resume_after_manual_blueprint_selection_should_reuse_same_run_and_goal(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        sequence_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突",
                "auto_run_gates": False,
                "auto_propose_changeset": False,
            },
        )
        self.assertEqual(sequence_resp.status_code, 200)
        item = sequence_resp.json()["data"]["chapter_results"][0]["chapter_result"]
        run_id = item["run"]["id"]
        goal_id = item["goal"]["id"]
        blueprint_id = item["blueprints"][0]["id"]

        self.assertEqual(item["stage_status"], "attention_required")
        self.assertEqual(item["next_action"], "select_blueprint")

        select_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(select_resp.status_code, 200)

        reviewed_resp = self.client.post(
            "/api/v1/workflows/runs/mark-human-reviewed",
            json={
                "workflow_run_id": run_id,
                "reviewed_by": "tester",
                "review_notes": "已完成人工蓝图确认",
                "next_action": "manual_continue",
                "resume_run": False,
            },
        )
        self.assertEqual(reviewed_resp.status_code, 200)

        continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "继续执行后续节点"},
        )
        self.assertEqual(continue_resp.status_code, 200)
        self.assertEqual(continue_resp.json()["data"]["run"]["id"], run_id)

        resume_cycle_resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "workflow_run_id": run_id,
                "auto_run_gates": False,
                "auto_propose_changeset": False,
            },
        )
        self.assertEqual(resume_cycle_resp.status_code, 200)
        resumed = resume_cycle_resp.json()["data"]
        self.assertEqual(resumed["run"]["id"], run_id)
        self.assertNotEqual(resumed["stage_status"], "attention_required")
        self.assertIsNotNone(resumed["draft"])

        with SessionLocal() as db:
            goal_count = (
                db.query(ChapterGoalORM)
                .filter(ChapterGoalORM.project_id == project_id, ChapterGoalORM.chapter_no == 1)
                .count()
            )
            run_count = db.query(WorkflowRunORM).filter(WorkflowRunORM.id == run_id).count()

        self.assertEqual(goal_count, 1)
        self.assertEqual(run_count, 1)

    def test_conflict_and_illegal_resume_should_return_business_errors(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        goal_resp = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "第一章建立冲突"},
        )
        self.assertEqual(goal_resp.status_code, 200)

        duplicate_goal_resp = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "重复创建"},
        )
        self.assertEqual(duplicate_goal_resp.status_code, 409)
        duplicate_body = duplicate_goal_resp.json()
        self.assertFalse(duplicate_body["success"])
        self.assertEqual(duplicate_body["error"]["code"], "CONFLICT")
        self.assertIn("已存在", duplicate_body["error"]["message"])
        self.assertNotIn("UNIQUE constraint failed", duplicate_body["error"]["message"])

        seq_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 2,
                "chapter_count": 1,
                "current_volume_goal": "第二章推进",
            },
        )
        self.assertEqual(seq_resp.status_code, 200)
        run_id = seq_resp.json()["data"]["chapter_results"][0]["chapter_result"]["run"]["id"]

        illegal_resume = self.client.post(
            "/api/v1/workflows/runs/resume",
            json={"workflow_run_id": run_id, "resumed_by": "tester"},
        )
        self.assertEqual(illegal_resume.status_code, 409)
        self.assertIn("不是可恢复状态", illegal_resume.json()["error"]["message"])

    def test_logging_trace_for_sequence_started_and_success(self):
        project_id = self._create_project()
        self._init_canon_snapshot(project_id)

        with self.assertLogs("novel.workflow", level="INFO") as cm:
            resp = self.client.post(
                "/api/v1/workflows/chapter-sequence/execute",
                json={
                    "project_id": project_id,
                    "start_chapter_no": 1,
                    "chapter_count": 1,
                    "current_volume_goal": "第一章建立冲突",
                },
            )
        self.assertEqual(resp.status_code, 200)
        joined = "\n".join(cm.output)

        self.assertIn("开始执行连续章节工作流", joined)
        self.assertIn("连续章节工作流执行完成", joined)


if __name__ == "__main__":
    unittest.main()
