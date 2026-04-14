import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import CanonSnapshotORM, ChangeSetORM
from app.db.session import SessionLocal
from app.main import create_app


class FactionLocationCardsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"faction-location-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            canon_count = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
            changeset_count = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()
            return canon_count, changeset_count

    def test_faction_cards_crud_and_isolation_and_not_found(self):
        project_a = self._create_project("a")
        project_b = self._create_project("b")

        before_counts = self._count_canon_and_changesets(project_a)
        create = self.client.post(
            f"/api/v1/projects/{project_a}/faction-cards",
            json={
                "name": "清虚宗",
                "aliases": ["清虚山门"],
                "faction_type": "宗门",
                "description": "势力简介",
                "core_members": ["掌门", "长老", "核心弟子"],
                "territory": "东岭群山",
                "stance": "守序中立",
                "goals": "守护山门",
                "relationship_notes": "与青岚宗关系紧张",
                "current_status": "闭关备战",
                "first_appearance_chapter": 1,
            },
        )
        self.assertEqual(create.status_code, 200)
        card = create.json()["data"]
        self.assertEqual(card["last_update_source"], "manual")
        self.assertFalse(card["is_canon"])

        list_resp = self.client.get(f"/api/v1/projects/{project_a}/faction-cards")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["data"]), 1)

        detail_resp = self.client.get(f"/api/v1/projects/{project_a}/faction-cards/{card['id']}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["name"], "清虚宗")

        update_resp = self.client.patch(
            f"/api/v1/projects/{project_a}/faction-cards/{card['id']}",
            json={"current_status": "开放山门", "goals": "稳定边境"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["data"]["current_status"], "开放山门")

        isolated = self.client.get(f"/api/v1/projects/{project_b}/faction-cards")
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["data"], [])

        not_found = self.client.get(f"/api/v1/projects/{project_b}/faction-cards/{card['id']}")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found.json()["error"]["code"], "NOT_FOUND")

        after_counts = self._count_canon_and_changesets(project_a)
        self.assertEqual(before_counts, after_counts)

    def test_location_cards_crud_and_isolation_and_not_found(self):
        project_a = self._create_project("c")
        project_b = self._create_project("d")

        before_counts = self._count_canon_and_changesets(project_a)
        create = self.client.post(
            f"/api/v1/projects/{project_a}/location-cards",
            json={
                "name": "青石镇",
                "aliases": ["青石古镇"],
                "location_type": "城镇",
                "description": "地点简介",
                "region": "东岭",
                "key_features": ["灵药田", "古井", "山门"],
                "related_factions": ["清虚宗"],
                "narrative_role": "主角初期据点",
                "current_status": "平稳",
                "first_appearance_chapter": 1,
            },
        )
        self.assertEqual(create.status_code, 200)
        card = create.json()["data"]
        self.assertEqual(card["last_update_source"], "manual")
        self.assertFalse(card["is_canon"])

        list_resp = self.client.get(f"/api/v1/projects/{project_a}/location-cards")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["data"]), 1)

        detail_resp = self.client.get(f"/api/v1/projects/{project_a}/location-cards/{card['id']}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["name"], "青石镇")

        update_resp = self.client.patch(
            f"/api/v1/projects/{project_a}/location-cards/{card['id']}",
            json={"current_status": "封禁", "narrative_role": "过渡战场"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["data"]["current_status"], "封禁")

        isolated = self.client.get(f"/api/v1/projects/{project_b}/location-cards")
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["data"], [])

        not_found = self.client.get(f"/api/v1/projects/{project_b}/location-cards/{card['id']}")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found.json()["error"]["code"], "NOT_FOUND")

        after_counts = self._count_canon_and_changesets(project_a)
        self.assertEqual(before_counts, after_counts)


if __name__ == "__main__":
    unittest.main()
