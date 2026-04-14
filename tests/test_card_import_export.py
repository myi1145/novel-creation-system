import io
import json
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import CanonSnapshotORM, ChangeSetORM, StructuredCharacterCardORM
from app.db.session import SessionLocal
from app.main import create_app


class CardImportExportApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"card-import-export-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _count_canon_and_changesets(self, project_id: str) -> tuple[int, int]:
        with SessionLocal() as db:
            canon_count = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
            changeset_count = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()
            return canon_count, changeset_count

    def test_json_export_contains_all_cards(self):
        project_id = self._create_project("json-export")
        self.client.post(
            f"/api/v1/projects/{project_id}/character-cards",
            json={
                "name": "顾长渊",
                "aliases": ["顾师兄"],
                "role_position": "主角",
                "profile": "简介",
                "personality_keywords": ["稳"],
                "relationship_notes": "",
                "current_status": "",
                "first_appearance_chapter": 1,
            },
        )

        resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/export.json")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["project_id"], project_id)
        self.assertIn("characters", payload["cards"])
        self.assertIn("terminologies", payload["cards"])
        self.assertIn("factions", payload["cards"])
        self.assertIn("locations", payload["cards"])

    def test_json_import_create_skip_and_error(self):
        project_id = self._create_project("json-import")
        self.client.post(
            f"/api/v1/projects/{project_id}/character-cards",
            json={
                "name": "顾长渊",
                "aliases": [],
                "role_position": "主角",
                "profile": "简介",
                "personality_keywords": [],
                "relationship_notes": "",
                "current_status": "",
                "first_appearance_chapter": 1,
            },
        )
        before_counts = self._count_canon_and_changesets(project_id)

        bad_payload = {
            "cards": {
                "characters": [{"name": "", "role_position": "主角", "profile": "x"}],
                "terminologies": [],
                "factions": [],
                "locations": [],
            }
        }
        bad_resp = self.client.post(
            f"/api/v1/projects/{project_id}/structured-cards/import.json",
            data={"payload": json.dumps(bad_payload, ensure_ascii=False)},
        )
        self.assertEqual(bad_resp.status_code, 200)
        self.assertGreaterEqual(bad_resp.json()["data"]["error_count"], 1)

        payload = {
            "cards": {
                "characters": [
                    {
                        "name": "顾长渊",
                        "aliases": [],
                        "role_position": "主角",
                        "profile": "重复",
                        "personality_keywords": [],
                        "relationship_notes": "",
                        "current_status": "",
                        "first_appearance_chapter": 1,
                    },
                    {
                        "name": "林清玄",
                        "aliases": ["林师姐"],
                        "role_position": "配角",
                        "profile": "简介",
                        "personality_keywords": ["冷静"],
                        "relationship_notes": "",
                        "current_status": "",
                        "first_appearance_chapter": 2,
                    },
                ],
                "terminologies": [
                    {
                        "term": "灵脉回流",
                        "term_type": "修炼术语",
                        "definition": "定义",
                        "usage_rules": "规则",
                        "examples": ["例子"],
                        "first_appearance_chapter": 2,
                    }
                ],
                "factions": [
                    {
                        "name": "清虚宗",
                        "aliases": ["清虚山门"],
                        "faction_type": "宗门",
                        "description": "描述",
                        "core_members": ["掌门"],
                        "territory": "东岭",
                        "stance": "中立",
                        "goals": "守护",
                        "relationship_notes": "",
                        "current_status": "稳定",
                        "first_appearance_chapter": 1,
                    }
                ],
                "locations": [
                    {
                        "name": "青石镇",
                        "aliases": ["青石古镇"],
                        "location_type": "城镇",
                        "description": "描述",
                        "region": "东岭",
                        "key_features": ["古井"],
                        "related_factions": ["清虚宗"],
                        "narrative_role": "据点",
                        "current_status": "平稳",
                        "first_appearance_chapter": 1,
                    }
                ],
            }
        }
        resp = self.client.post(
            f"/api/v1/projects/{project_id}/structured-cards/import.json",
            files={"file": ("cards.json", io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), "application/json")},
        )
        self.assertEqual(resp.status_code, 200)
        report = resp.json()["data"]
        self.assertEqual(report["card_type"], "all")
        self.assertEqual(report["created_count"], 4)
        self.assertEqual(report["skipped_count"], 1)

        after_counts = self._count_canon_and_changesets(project_id)
        self.assertEqual(before_counts, after_counts)

    def test_csv_export_import_template_and_invalid_type(self):
        project_id = self._create_project("csv")

        template_resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/characters/template.csv")
        self.assertEqual(template_resp.status_code, 200)
        self.assertIn("name,aliases,role_position,profile", template_resp.text)

        csv_content = (
            "name,aliases,role_position,profile,personality_keywords,relationship_notes,current_status,first_appearance_chapter,is_canon\n"
            "顾长渊,顾师兄;长渊,主角,人物简介,稳;克制,关系备注,修炼中,1,false\n"
        )
        import_resp = self.client.post(
            f"/api/v1/projects/{project_id}/structured-cards/characters/import.csv",
            files={"file": ("characters.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        )
        self.assertEqual(import_resp.status_code, 200)
        self.assertEqual(import_resp.json()["data"]["created_count"], 1)

        with SessionLocal() as db:
            count = db.query(StructuredCharacterCardORM).filter(StructuredCharacterCardORM.project_id == project_id).count()
            self.assertEqual(count, 1)

        export_resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/characters/export.csv")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("顾长渊", export_resp.text)

        invalid_resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/invalid/export.csv")
        self.assertEqual(invalid_resp.status_code, 422)
        self.assertEqual(invalid_resp.json()["error"]["code"], "VALIDATION_ERROR")

    def test_csv_endpoints_cover_all_card_types(self):
        project_id = self._create_project("csv-all")
        cases = {
            "characters": "name,aliases,role_position,profile,personality_keywords,relationship_notes,current_status,first_appearance_chapter,is_canon\nA,,主角,简介,,,,,false\n",
            "terminologies": "term,term_type,definition,usage_rules,examples,first_appearance_chapter,is_canon\n术语A,类型A,定义,,,1,false\n",
            "factions": "name,aliases,faction_type,description,core_members,territory,stance,goals,relationship_notes,current_status,first_appearance_chapter,is_canon\n势力A,,组织,描述,,东岭,,,,,1,false\n",
            "locations": "name,aliases,location_type,description,region,key_features,related_factions,narrative_role,current_status,first_appearance_chapter,is_canon\n地点A,,城镇,描述,东岭,,,,,1,false\n",
        }
        for card_type, sample_csv in cases.items():
            template_resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/{card_type}/template.csv")
            self.assertEqual(template_resp.status_code, 200)
            export_resp = self.client.get(f"/api/v1/projects/{project_id}/structured-cards/{card_type}/export.csv")
            self.assertEqual(export_resp.status_code, 200)
            import_resp = self.client.post(
                f"/api/v1/projects/{project_id}/structured-cards/{card_type}/import.csv",
                files={"file": (f"{card_type}.csv", io.BytesIO(sample_csv.encode("utf-8")), "text/csv")},
            )
            self.assertEqual(import_resp.status_code, 200)
            self.assertGreaterEqual(import_resp.json()["data"]["created_count"], 1)


if __name__ == "__main__":
    unittest.main()
