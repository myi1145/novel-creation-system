"""chapter cycle 运行层唯一活跃 run 约束回归测试。"""

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import WorkflowRunORM
from app.db.session import SessionLocal
from app.main import create_app


class WorkflowChapterCycleActiveRunGuardTest(unittest.TestCase):
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
                "project_name": f"chapter-cycle-guard-{uuid4().hex[:8]}",
                "premise": "验证 chapter cycle 同对象唯一活跃运行约束",
                "genre_id": "default",
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def test_duplicate_chapter_cycle_should_return_409_when_existing_run_is_active(self):
        project_id = self._create_project()
        payload = {
            "project_id": project_id,
            "chapter_no": 1,
            "current_volume_goal": "第一章建立核心冲突",
            "auto_run_gates": False,
            "auto_propose_changeset": False,
        }
        first = self.client.post("/api/v1/workflows/chapter-cycle/execute", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["data"]["run"]["status"], "attention_required")

        second = self.client.post("/api/v1/workflows/chapter-cycle/execute", json=payload)
        self.assertEqual(second.status_code, 409)
        second_body = second.json()
        self.assertFalse(second_body["success"])
        self.assertEqual(second_body["error"]["code"], "CONFLICT")
        self.assertIn("已有活跃 chapter_cycle 运行", second_body["error"]["message"])
        self.assertNotIn("UNIQUE constraint failed", second_body["error"]["message"])

    def test_completed_or_failed_old_runs_should_not_block_new_chapter_cycle_run(self):
        project_id = self._create_project()
        with SessionLocal() as db:
            db.add(
                WorkflowRunORM(
                    project_id=project_id,
                    workflow_name="chapter_cycle_workflow_v1",
                    trace_id=str(uuid4()),
                    chapter_no=2,
                    source_type="chapter_cycle",
                    status="completed",
                    current_step="published",
                    completed_at=datetime.now(timezone.utc),
                    run_metadata={"seed": "completed-run"},
                )
            )
            db.add(
                WorkflowRunORM(
                    project_id=project_id,
                    workflow_name="chapter_cycle_workflow_v1",
                    trace_id=str(uuid4()),
                    chapter_no=3,
                    source_type="chapter_cycle",
                    status="failed",
                    current_step="draft_generation",
                    run_metadata={"seed": "failed-run"},
                )
            )
            db.commit()

        for chapter_no in (2, 3):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_no": chapter_no,
                    "current_volume_goal": f"第 {chapter_no} 章继续推进",
                    "auto_run_gates": False,
                    "auto_propose_changeset": False,
                },
            )
            self.assertEqual(resp.status_code, 200, msg=f"chapter_no={chapter_no}, body={resp.json()}")

    def test_explicit_workflow_run_id_resume_path_should_keep_existing_semantics(self):
        project_id = self._create_project()
        first = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_no": 1,
                "current_volume_goal": "第一章建立核心冲突",
                "auto_run_gates": False,
                "auto_propose_changeset": False,
            },
        )
        self.assertEqual(first.status_code, 200)
        first_data = first.json()["data"]
        run_id = first_data["run"]["id"]
        goal_id = first_data["goal"]["id"]
        blueprint_id = first_data["blueprints"][0]["id"]

        select_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(select_resp.status_code, 200)

        manual_continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "已完成人工蓝图选择"},
        )
        self.assertEqual(manual_continue_resp.status_code, 200)

        resume = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "workflow_run_id": run_id,
                "auto_run_gates": False,
                "auto_propose_changeset": False,
            },
        )
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(resume.json()["data"]["run"]["id"], run_id)


if __name__ == "__main__":
    unittest.main()
