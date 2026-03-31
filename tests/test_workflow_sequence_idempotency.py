import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterGoalORM
from app.db.session import SessionLocal
from app.main import create_app


class WorkflowSequenceIdempotencyTest(unittest.TestCase):
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
        payload = {
            "project_name": f"sequence-idempotency-{uuid4().hex[:8]}",
            "premise": "验证 sequence 恢复执行与幂等收口",
            "genre_id": "default",
        }
        resp = self.client.post("/api/v1/projects", json=payload)
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def test_sequence_first_run_should_stop_on_blueprint_selection(self):
        project_id = self._create_project()
        resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突与目标",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["stage_status"], "attention_required")
        self.assertEqual(body["data"]["next_action"], "select_blueprint")
        self.assertEqual(body["data"]["run"]["status"], "attention_required")

    def test_select_blueprint_then_continue_should_not_duplicate_goal(self):
        project_id = self._create_project()
        sequence_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突与目标",
                "auto_run_gates": False,
                "auto_propose_changeset": False,
            },
        )
        self.assertEqual(sequence_resp.status_code, 200)
        item = sequence_resp.json()["data"]["chapter_results"][0]["chapter_result"]
        cycle_run_id = item["run"]["id"]
        chapter_goal_id = item["goal"]["id"]
        blueprint_id = item["blueprints"][0]["id"]

        select_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(select_resp.status_code, 200)

        continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": cycle_run_id, "continued_by": "tester", "reason": "已完成人工蓝图选择"},
        )
        self.assertEqual(continue_resp.status_code, 200)

        execute_resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={"project_id": project_id, "chapter_goal_id": chapter_goal_id, "workflow_run_id": cycle_run_id, "auto_run_gates": False, "auto_propose_changeset": False},
        )
        self.assertEqual(execute_resp.status_code, 200)
        self.assertNotEqual(execute_resp.json()["data"]["stage_status"], "failed")

        with SessionLocal() as db:
            goal_count = (
                db.query(ChapterGoalORM)
                .filter(ChapterGoalORM.project_id == project_id, ChapterGoalORM.chapter_no == 1)
                .count()
            )
        self.assertEqual(goal_count, 1)

    def test_repeat_sequence_execute_should_return_business_conflict(self):
        project_id = self._create_project()
        first_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突与目标",
            },
        )
        self.assertEqual(first_resp.status_code, 200)

        second_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突与目标",
            },
        )
        self.assertEqual(second_resp.status_code, 409)
        body = second_resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "CONFLICT")
        self.assertIn("请不要重复执行 sequence", body["error"]["message"])

    def test_illegal_resume_and_manual_continue_should_return_business_conflict(self):
        project_id = self._create_project()
        sequence_resp = self.client.post(
            "/api/v1/workflows/chapter-sequence/execute",
            json={
                "project_id": project_id,
                "start_chapter_no": 1,
                "chapter_count": 1,
                "current_volume_goal": "第一章建立冲突与目标",
            },
        )
        self.assertEqual(sequence_resp.status_code, 200)
        run_id = sequence_resp.json()["data"]["chapter_results"][0]["chapter_result"]["run"]["id"]

        resume_resp = self.client.post(
            "/api/v1/workflows/runs/resume",
            json={"workflow_run_id": run_id, "resumed_by": "tester"},
        )
        self.assertEqual(resume_resp.status_code, 409)
        self.assertIn("不是可恢复状态", resume_resp.json()["error"]["message"])

        manual_continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "非法重复续跑"},
        )
        self.assertEqual(manual_continue_resp.status_code, 200)

        second_manual_continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "运行中再次续跑"},
        )
        self.assertEqual(second_manual_continue_resp.status_code, 409)
        self.assertIn("不是可恢复状态", second_manual_continue_resp.json()["error"]["message"])


if __name__ == "__main__":
    unittest.main()
