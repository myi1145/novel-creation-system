import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import CanonSnapshotORM, ChangeSetORM, StoryPlanningORM
from app.db.session import SessionLocal
from app.main import create_app


class StoryPlanningApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"story-planning-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            canon_count = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
            changeset_count = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()
            return canon_count, changeset_count

    def test_story_planning_minimal_loop(self):
        project_a = self._create_project("a")
        project_b = self._create_project("b")

        before_counts = self._count_canon_and_changesets(project_a)

        empty_resp = self.client.get(f"/api/v1/projects/{project_a}/story-planning")
        self.assertEqual(empty_resp.status_code, 200)
        self.assertIsNone(empty_resp.json()["data"])

        create_payload = {
            "worldview": "世界观-初稿",
            "main_outline": "主线-初稿",
            "volume_plan": "卷规划-初稿",
            "core_seed_summary": "核心种子-初稿",
            "planning_status": "draft",
        }
        create_resp = self.client.put(f"/api/v1/projects/{project_a}/story-planning", json=create_payload)
        self.assertEqual(create_resp.status_code, 200)
        create_data = create_resp.json()["data"]
        self.assertEqual(create_data["planning_status"], "draft")
        self.assertEqual(create_data["last_update_source"], "manual")

        update_payload = {
            "worldview": "世界观-更新",
            "main_outline": "主线-更新",
            "volume_plan": "卷规划-更新",
            "core_seed_summary": "核心种子-更新",
            "planning_status": "confirmed",
        }
        update_resp = self.client.put(f"/api/v1/projects/{project_a}/story-planning", json=update_payload)
        self.assertEqual(update_resp.status_code, 200)
        update_data = update_resp.json()["data"]
        self.assertEqual(update_data["id"], create_data["id"])
        self.assertEqual(update_data["planning_status"], "confirmed")
        self.assertEqual(update_data["last_update_source"], "manual")

        get_resp = self.client.get(f"/api/v1/projects/{project_a}/story-planning")
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()["data"]
        self.assertEqual(get_data["id"], create_data["id"])
        self.assertEqual(get_data["worldview"], "世界观-更新")

        invalid_status = self.client.put(
            f"/api/v1/projects/{project_a}/story-planning",
            json={
                "worldview": "x",
                "main_outline": "x",
                "volume_plan": "x",
                "core_seed_summary": "x",
                "planning_status": "archived",
            },
        )
        self.assertEqual(invalid_status.status_code, 422)

        isolation_resp = self.client.get(f"/api/v1/projects/{project_b}/story-planning")
        self.assertEqual(isolation_resp.status_code, 200)
        self.assertIsNone(isolation_resp.json()["data"])

        with SessionLocal() as db:
            rows_a = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_a).all()
            rows_b = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_b).all()
            self.assertEqual(len(rows_a), 1)
            self.assertEqual(len(rows_b), 0)
            self.assertEqual(rows_a[0].last_update_source, "manual")

        after_counts = self._count_canon_and_changesets(project_a)
        self.assertEqual(before_counts, after_counts)


if __name__ == "__main__":
    unittest.main()
