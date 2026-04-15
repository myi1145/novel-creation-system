import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import CanonSnapshotORM, ChangeSetORM, ImmutableLogORM, StoryDirectoryORM
from app.db.session import SessionLocal
from app.main import create_app


class StoryDirectoryGenerateApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"story-directory-generate-{suffix}-{uuid4().hex[:6]}", "premise": "边陲少年被迫入局", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _save_story_planning(self, project_id: str) -> None:
        resp = self.client.put(
            f"/api/v1/projects/{project_id}/story-planning",
            json={
                "worldview": "宗门与王朝并立，力量体系分层。",
                "main_outline": "主角从求生到破局，逐步对抗旧秩序。",
                "volume_plan": "第一卷 10 章起势，第二卷扩张。",
                "core_seed_summary": "角色、势力、地点、术语四类种子齐备。",
                "planning_status": "confirmed",
            },
        )
        self.assertEqual(resp.status_code, 200)

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            return (
                db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count(),
                db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count(),
            )

    def _count_stale_events(self, project_id: str) -> int:
        with SessionLocal() as db:
            return (
                db.query(ImmutableLogORM)
                .filter(
                    ImmutableLogORM.project_id == project_id,
                    ImmutableLogORM.event_type == "chapter_dependency_stale_marked",
                )
                .count()
            )

    def test_generate_story_directory_returns_draft_without_persisting(self):
        project_id = self._create_project("ok")
        self._save_story_planning(project_id)
        before_counts = self._count_canon_and_changesets(project_id)
        stale_before = self._count_stale_events(project_id)

        with patch.object(settings, "agent_provider", "mock"), patch.object(settings, "agent_fallback_to_mock", True):
            resp = self.client.post(
                f"/api/v1/projects/{project_id}/story-directory/generate",
                json={"target_chapter_count": 6},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["project_id"], project_id)
        self.assertTrue(data["generated"])
        self.assertEqual(data["data"]["directory_status"], "draft")
        self.assertTrue(data["data"]["directory_title"].strip())
        self.assertTrue(data["data"]["directory_summary"].strip())
        self.assertGreaterEqual(len(data["data"]["chapter_items"]), 1)

        chapter = data["data"]["chapter_items"][0]
        for key in (
            "chapter_no",
            "chapter_title",
            "chapter_role",
            "chapter_goal",
            "stage_label",
            "required_entities",
            "required_seed_points",
            "foreshadow_constraints",
        ):
            self.assertIn(key, chapter)

        with SessionLocal() as db:
            rows = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_id).count()
            self.assertEqual(rows, 0)

        after_counts = self._count_canon_and_changesets(project_id)
        stale_after = self._count_stale_events(project_id)
        self.assertEqual(before_counts, after_counts)
        self.assertEqual(stale_before, stale_after)

    def test_generate_story_directory_without_planning_returns_stable_error(self):
        project_id = self._create_project("no-planning")
        resp = self.client.post(f"/api/v1/projects/{project_id}/story-directory/generate", json={})
        self.assertEqual(resp.status_code, 422)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(payload["error"]["message"], "请先生成或保存全书规划")

    def test_generate_story_directory_invalid_provider_payload_returns_stable_error(self):
        project_id = self._create_project("invalid")
        self._save_story_planning(project_id)

        with patch(
            "app.services.story_directory_service.agent_gateway.generate_story_directory",
            return_value=type("Obj", (), {"payload": {"directory_title": "x", "directory_summary": "x", "chapter_items": [{"chapter_title": "x"}]}})(),
        ):
            resp = self.client.post(f"/api/v1/projects/{project_id}/story-directory/generate", json={})

        self.assertEqual(resp.status_code, 422)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(payload["error"]["message"], "生成失败，请先确认已保存全书规划，或稍后重试。")


if __name__ == "__main__":
    unittest.main()
