import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


class ChapterGoalApiRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def test_create_goal_should_not_reference_scene_entities_before_scene_stage(self):
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


if __name__ == "__main__":
    unittest.main()
