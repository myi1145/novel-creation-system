import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import PublishedChapterORM
from app.db.session import SessionLocal
from app.main import create_app


class WorkflowSequenceCycleClosureTest(unittest.TestCase):
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
        project = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"sequence-cycle-{uuid4().hex[:8]}",
                "premise": "验证 sequence 复用 chapter cycle 闭环",
                "genre_id": "default",
            },
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]

        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "sequence-cycle-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        return project_id

    def _execute_sequence(self, project_id: str, **overrides):
        payload = {
            "project_id": project_id,
            "start_chapter_no": 1,
            "chapter_count": 2,
            "current_volume_goal": "连续两章推进主线并形成承接",
            "testing_auto_select_first_blueprint": True,
            "auto_propose_changeset": True,
            "auto_approve_changeset": True,
            "auto_apply_changeset": True,
            "approved_by": "tester",
        }
        payload.update(overrides)
        resp = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=payload)
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def test_sequence_should_stop_at_manual_publish_when_auto_publish_disabled(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=False)

        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "publish")
        self.assertEqual(data["stopped_at_chapter_no"], 1)
        self.assertEqual(data["processed_chapter_count"], 1)
        self.assertEqual(len(data["chapter_results"]), 1)
        self.assertEqual(data["chapter_results"][0]["stage_status"], "attention_required")
        self.assertEqual(data["chapter_results"][0]["next_action"], "publish")

    def test_sequence_should_continue_to_next_chapter_after_successful_publish(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester")

        self.assertEqual(data["stage_status"], "completed")
        self.assertEqual(data["completed_chapter_count"], 2)
        self.assertEqual(len(data["chapter_results"]), 2)
        ch1 = data["chapter_results"][0]
        ch2 = data["chapter_results"][1]
        self.assertEqual(ch1["stage_status"], "completed")
        self.assertEqual(ch2["stage_status"], "completed")
        self.assertTrue(ch1["published_chapter_id"])
        self.assertEqual(ch2["chapter_result"]["continuity_pack"]["source_published_chapter_id"], ch1["published_chapter_id"])
        self.assertEqual(ch2["chapter_result"]["continuity_pack"]["previous_chapter_summary"], ch1["latest_summary"])

    def test_sequence_should_surface_next_action_and_stopped_chapter(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=False)

        self.assertEqual(data["batch_status"], "attention_required")
        self.assertEqual(data["next_action"], "publish")
        self.assertEqual(data["stopped_at_chapter_no"], 1)
        self.assertEqual(data["attention_chapter_count"], 1)
        self.assertIn("停止", data["summary_message"])

    def test_sequence_should_include_publish_and_post_publish_outputs(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester", auto_run_post_publish_updates=True)

        chapter = data["chapter_results"][0]
        self.assertTrue(chapter["published_chapter_id"])
        self.assertTrue(chapter["latest_summary"])
        self.assertTrue(chapter["latest_next_chapter_seed"])
        self.assertIn(chapter["derived_update_status"], {"completed", "completed_with_warnings"})

    def test_sequence_should_not_double_run_post_publish_updates(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester", auto_run_post_publish_updates=True)

        first = data["chapter_results"][0]["chapter_result"]
        derived = first["derived_update_result"] or first["publish_result"]["derived_update_result"]
        task_names = [task["task_name"] for task in derived["tasks"]]
        self.assertEqual(len(task_names), len(set(task_names)))

        with SessionLocal() as db:
            published = db.get(PublishedChapterORM, data["chapter_results"][0]["published_chapter_id"])
            self.assertIsNotNone(published)
            payload = dict(published.publish_metadata or {})
            stored = list(payload.get("derived_update_tasks") or [])
            stored_names = [item.get("task_name") for item in stored if isinstance(item, dict)]
            self.assertEqual(len(stored_names), len(set(stored_names)))


if __name__ == "__main__":
    unittest.main()
