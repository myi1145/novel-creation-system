import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import CanonSnapshotORM, ChangeSetORM
from app.db.session import SessionLocal
from app.main import create_app


class StructuredCardsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"structured-cards-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            canon_count = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
            changeset_count = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()
            return canon_count, changeset_count

    def test_character_cards_crud_and_isolation_and_not_found(self):
        project_a = self._create_project("a")
        project_b = self._create_project("b")

        before_counts = self._count_canon_and_changesets(project_a)
        create = self.client.post(
            f"/api/v1/projects/{project_a}/character-cards",
            json={
                "name": "顾长渊",
                "aliases": ["顾师兄"],
                "role_position": "主角 / 阵法天才 / 清虚宗弟子",
                "profile": "人物简介",
                "personality_keywords": ["稳", "克制", "重情"],
                "relationship_notes": "重要关系备注",
                "current_status": "当前状态",
                "first_appearance_chapter": 1,
            },
        )
        self.assertEqual(create.status_code, 200)
        card = create.json()["data"]
        self.assertEqual(card["last_update_source"], "manual")
        self.assertFalse(card["is_canon"])

        list_resp = self.client.get(f"/api/v1/projects/{project_a}/character-cards")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["data"]), 1)

        detail_resp = self.client.get(f"/api/v1/projects/{project_a}/character-cards/{card['id']}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["name"], "顾长渊")

        update_resp = self.client.patch(
            f"/api/v1/projects/{project_a}/character-cards/{card['id']}",
            json={"current_status": "已进入内门", "aliases": ["顾师兄", "顾师弟"]},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["data"]["current_status"], "已进入内门")

        isolated = self.client.get(f"/api/v1/projects/{project_b}/character-cards")
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["data"], [])

        not_found = self.client.get(f"/api/v1/projects/{project_b}/character-cards/{card['id']}")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found.json()["error"]["code"], "NOT_FOUND")

        after_counts = self._count_canon_and_changesets(project_a)
        self.assertEqual(before_counts, after_counts)

    def test_terminology_cards_crud_and_isolation_and_not_found(self):
        project_a = self._create_project("c")
        project_b = self._create_project("d")

        before_counts = self._count_canon_and_changesets(project_a)
        create = self.client.post(
            f"/api/v1/projects/{project_a}/terminology-cards",
            json={
                "term": "灵脉回流",
                "term_type": "修炼术语",
                "definition": "术语定义",
                "usage_rules": "使用规则",
                "examples": ["例句或用法"],
                "first_appearance_chapter": 1,
            },
        )
        self.assertEqual(create.status_code, 200)
        card = create.json()["data"]
        self.assertEqual(card["last_update_source"], "manual")
        self.assertFalse(card["is_canon"])

        list_resp = self.client.get(f"/api/v1/projects/{project_a}/terminology-cards")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["data"]), 1)

        detail_resp = self.client.get(f"/api/v1/projects/{project_a}/terminology-cards/{card['id']}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["term"], "灵脉回流")

        update_resp = self.client.patch(
            f"/api/v1/projects/{project_a}/terminology-cards/{card['id']}",
            json={"usage_rules": "仅用于灵脉逆转场景"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["data"]["usage_rules"], "仅用于灵脉逆转场景")

        isolated = self.client.get(f"/api/v1/projects/{project_b}/terminology-cards")
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["data"], [])

        not_found = self.client.get(f"/api/v1/projects/{project_b}/terminology-cards/{card['id']}")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found.json()["error"]["code"], "NOT_FOUND")

        after_counts = self._count_canon_and_changesets(project_a)
        self.assertEqual(before_counts, after_counts)


if __name__ == "__main__":
    unittest.main()
