import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import WorkflowRunORM
from app.db.session import SessionLocal
from app.main import create_app


class WorkflowChapterCycleStrategyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback

    def _create_project_and_snapshot(self) -> str:
        project_resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"cycle-strategy-{uuid4().hex[:8]}",
                "premise": "验证 execute_chapter_cycle 自动策略接入",
                "genre_id": "default",
            },
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]
        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "workflow-strategy-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        return project_id

    def _prepare_goal_and_selected_blueprint(self, project_id: str, chapter_no: int = 1) -> tuple[str, str]:
        goal_resp = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": chapter_no, "current_volume_goal": "推进剧情并引入冲突"},
        )
        self.assertEqual(goal_resp.status_code, 200)
        goal_id = goal_resp.json()["data"]["id"]

        bp_resp = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(bp_resp.status_code, 200)
        blueprint_id = bp_resp.json()["data"][0]["id"]

        select_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(select_resp.status_code, 200)
        return goal_id, blueprint_id

    def test_auto_changeset_path_should_stop_at_manual_publish(self):
        project_id = self._create_project_and_snapshot()
        goal_id, blueprint_id = self._prepare_goal_and_selected_blueprint(project_id)

        resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "selected_blueprint_id": blueprint_id,
                "auto_propose_changeset": True,
                "auto_approve_changeset": True,
                "auto_apply_changeset": True,
                "approved_by": "tester",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "publish")
        self.assertIsNotNone(data["changeset"])
        self.assertEqual(data["changeset"]["status"], "applied")
        self.assertTrue(data["changeset"]["result_snapshot_id"])
        self.assertEqual(data["run"]["status"], "attention_required")
        self.assertEqual(data["run"]["current_step"], "publish_required")

    def test_auto_publish_path_should_complete_and_record_publish(self):
        project_id = self._create_project_and_snapshot()
        goal_id, blueprint_id = self._prepare_goal_and_selected_blueprint(project_id)

        resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "selected_blueprint_id": blueprint_id,
                "auto_propose_changeset": True,
                "auto_approve_changeset": True,
                "auto_apply_changeset": True,
                "auto_publish": True,
                "approved_by": "tester",
                "published_by": "tester",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "completed")
        self.assertIsNone(data["next_action"])
        self.assertEqual(data["run"]["status"], "completed")
        self.assertIsNotNone(data["publish_result"])
        self.assertEqual(data["publish_result"]["publish_status"], "published")
        self.assertTrue(data["publish_result"]["published_chapter"]["id"])

    def test_default_manual_stop_should_require_changeset_proposal(self):
        project_id = self._create_project_and_snapshot()
        goal_id, blueprint_id = self._prepare_goal_and_selected_blueprint(project_id)

        resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "selected_blueprint_id": blueprint_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "generate_changeset_proposal")
        self.assertEqual(data["run"]["status"], "attention_required")
        self.assertEqual(data["run"]["current_step"], "changeset_proposal_required")
        self.assertEqual(data["run"]["run_metadata"].get("manual_review_required"), True)

    def test_post_publish_updates_should_be_included_once_in_workflow_result(self):
        project_id = self._create_project_and_snapshot()
        goal_id, blueprint_id = self._prepare_goal_and_selected_blueprint(project_id)

        resp = self.client.post(
            "/api/v1/workflows/chapter-cycle/execute",
            json={
                "project_id": project_id,
                "chapter_goal_id": goal_id,
                "selected_blueprint_id": blueprint_id,
                "auto_propose_changeset": True,
                "auto_approve_changeset": True,
                "auto_apply_changeset": True,
                "auto_publish": True,
                "auto_run_post_publish_updates": True,
                "approved_by": "tester",
                "published_by": "tester",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "completed")
        derived = data["derived_update_result"]
        self.assertIsNotNone(derived)
        task_names = [item["task_name"] for item in derived["tasks"]]
        self.assertEqual(len(task_names), len(set(task_names)))
        self.assertIn(derived["status"], {"completed", "completed_with_warnings"})

        with SessionLocal() as db:
            run = db.get(WorkflowRunORM, data["run"]["id"])
            self.assertIsNotNone(run)
            metadata = dict(run.run_metadata or {})
            self.assertIn(metadata.get("derived_update_status"), {"completed", "completed_with_warnings"})


if __name__ == "__main__":
    unittest.main()
