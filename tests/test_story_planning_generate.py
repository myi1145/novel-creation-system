import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import CanonSnapshotORM, ChangeSetORM, ImmutableLogORM, StoryPlanningORM
from app.db.session import SessionLocal
from app.main import create_app


class StoryPlanningGenerateApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"story-planning-generate-{suffix}-{uuid4().hex[:6]}", "premise": "少年在边陲城镇觉醒异能", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

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

    def test_generate_story_planning_returns_structured_architecture_sections_without_persisting(self):
        project_id = self._create_project("ok")
        before_counts = self._count_canon_and_changesets(project_id)
        stale_before = self._count_stale_events(project_id)

        with patch.object(settings, "agent_provider", "mock"), patch.object(settings, "agent_fallback_to_mock", True):
            resp = self.client.post(
                f"/api/v1/projects/{project_id}/story-planning/generate",
                json={"target_chapter_count": 120, "tone": "克制、冷峻"},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["project_id"], project_id)
        self.assertTrue(data["generated"])
        self.assertTrue(data["data"]["worldview"].strip())
        self.assertTrue(data["data"]["main_outline"].strip())
        self.assertTrue(data["data"]["volume_plan"].strip())
        self.assertTrue(data["data"]["core_seed_summary"].strip())
        self.assertIn("[世界背景]", data["data"]["worldview"])
        self.assertIn("[规则边界]", data["data"]["worldview"])
        self.assertIn("[阅读承诺]", data["data"]["main_outline"])
        self.assertIn("[关键角色关系张力]", data["data"]["main_outline"])
        self.assertIn("[卷一职责]", data["data"]["volume_plan"])
        self.assertIn("[卷末承接]", data["data"]["volume_plan"])
        self.assertIn("[初始状态快照]", data["data"]["core_seed_summary"])
        self.assertIn("[前期不可随意改写的状态边界]", data["data"]["core_seed_summary"])

        with SessionLocal() as db:
            planning_rows = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).count()
            self.assertEqual(planning_rows, 0)

        after_counts = self._count_canon_and_changesets(project_id)
        stale_after = self._count_stale_events(project_id)
        self.assertEqual(before_counts, after_counts)
        self.assertEqual(stale_before, stale_after)

    def test_generate_story_planning_project_not_found(self):
        missing_id = str(uuid4())
        resp = self.client.post(f"/api/v1/projects/{missing_id}/story-planning/generate", json={})
        self.assertEqual(resp.status_code, 404)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")

    def test_generate_story_planning_invalid_provider_payload_returns_stable_error(self):
        project_id = self._create_project("invalid")

        with patch(
            "app.services.story_planning_service.StoryPlanningService._invoke_generation_gateway",
            return_value={"worldview": "x", "main_outline": "x", "volume_plan": "x"},
        ):
            resp = self.client.post(f"/api/v1/projects/{project_id}/story-planning/generate", json={})

        self.assertEqual(resp.status_code, 422)
        payload = resp.json()
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(payload["error"]["message"], "生成失败，请稍后重试。")

    def test_generate_story_planning_auto_completes_contract_sections_when_provider_is_sparse(self):
        project_id = self._create_project("sparse")
        sparse_payload = {
            "worldview": "[世界背景] 仅提供一条背景。",
            "main_outline": "[阅读承诺] 仅提供一个承诺。",
            "volume_plan": "[分卷规划原则] 仅提供一个规则。",
            "core_seed_summary": "[核心种子] 仅提供一个种子。",
        }
        with patch(
            "app.services.story_planning_service.StoryPlanningService._invoke_generation_gateway",
            return_value=sparse_payload,
        ):
            resp = self.client.post(f"/api/v1/projects/{project_id}/story-planning/generate", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]["data"]
        self.assertIn("[规则边界]", data["worldview"])
        self.assertIn("[关键角色关系张力]", data["main_outline"])
        self.assertIn("[卷三职责]", data["volume_plan"])
        self.assertIn("[初始状态快照]", data["core_seed_summary"])


if __name__ == "__main__":
    unittest.main()
