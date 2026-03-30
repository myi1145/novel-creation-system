import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


class ChapterWorkflowApiRegressionTest(unittest.TestCase):
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

    def test_goal_and_blueprint_generation_should_not_raise_name_error(self):
        project_payload = {
            "project_name": f"goal-regression-{uuid4().hex[:8]}",
            "premise": "用于验证章目标创建阶段不依赖 scene_entities",
            "genre_id": "default",
        }
        project_resp = self.client.post("/api/v1/projects", json=project_payload)
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]

        goal_payload = {
            "project_id": project_id,
            "chapter_no": 1,
            "current_volume_goal": "第一章建立主冲突",
        }
        goal_resp = self.client.post("/api/v1/chapters/goals", json=goal_payload)

        self.assertEqual(goal_resp.status_code, 200)
        body = goal_resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["project_id"], project_id)
        self.assertEqual(body["data"]["chapter_no"], 1)
        self.assertEqual(body["data"]["object_type"], "chapter_goal")

        blueprint_payload = {
            "project_id": project_id,
            "chapter_goal_id": body["data"]["id"],
            "candidate_count": 2,
        }
        blueprint_resp = self.client.post("/api/v1/chapters/blueprints/generate", json=blueprint_payload)
        self.assertEqual(blueprint_resp.status_code, 200)
        blueprint_body = blueprint_resp.json()
        self.assertTrue(blueprint_body["success"])
        self.assertIsInstance(blueprint_body["data"], list)
        self.assertGreaterEqual(len(blueprint_body["data"]), 1)


if __name__ == "__main__":
    unittest.main()
