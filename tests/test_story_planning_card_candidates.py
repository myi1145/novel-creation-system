import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import (
    CanonSnapshotORM,
    ChangeSetORM,
    ImmutableLogORM,
    StructuredCardCandidateORM,
    StructuredCharacterCardORM,
    StructuredFactionCardORM,
    StructuredLocationCardORM,
    TerminologyCardORM,
)
from app.db.session import SessionLocal
from app.main import create_app


class StoryPlanningCardCandidatesApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def _create_project(self, suffix: str) -> str:
        resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"card-candidates-{suffix}-{uuid4().hex[:6]}", "premise": "test", "genre_id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]["id"]

    def _seed_planning_and_directory(self, project_id: str) -> None:
        planning_payload = {
            "worldview": "修真世界",
            "main_outline": "主线推进",
            "volume_plan": "卷计划",
            "core_seed_summary": "\n".join(
                [
                    "角色：顾长渊｜主角｜稳重克制｜清虚宗弟子",
                    "术语：灵脉回流｜阵法术语｜灵气沿阵纹反向回流",
                    "势力：清虚宗｜宗门｜正道宗门",
                    "地点：青石镇｜城镇｜主角出身地",
                ]
            ),
            "planning_status": "confirmed",
        }
        directory_payload = {
            "directory_title": "全书章节目录",
            "directory_summary": "目录摘要",
            "directory_status": "confirmed",
            "chapter_items": [
                {
                    "chapter_no": 1,
                    "chapter_title": "灵根初现",
                    "chapter_role": "起势",
                    "chapter_goal": "主角入局",
                    "stage_label": "第一卷",
                    "required_entities": ["顾长渊", "青岚盟", "黑风谷", "未知实体123"],
                    "required_seed_points": ["禁术反噬", "灵脉回流"],
                    "foreshadow_constraints": ["不揭露幕后黑手"],
                }
            ],
        }
        self.assertEqual(self.client.put(f"/api/v1/projects/{project_id}/story-planning", json=planning_payload).status_code, 200)
        self.assertEqual(self.client.put(f"/api/v1/projects/{project_id}/story-directory", json=directory_payload).status_code, 200)

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

    def test_generate_candidates_from_planning_and_directory_and_filters(self):
        project_id = self._create_project("gen")
        self._seed_planning_and_directory(project_id)

        with SessionLocal() as db:
            db.add(
                StructuredCharacterCardORM(
                    project_id=project_id,
                    name="顾长渊",
                    aliases=[],
                    role_position="主角",
                    profile="描述",
                    personality_keywords=[],
                    relationship_notes="",
                    current_status="",
                    first_appearance_chapter=1,
                    last_update_source="manual",
                    is_canon=False,
                )
            )
            db.commit()

        generate_resp = self.client.post(f"/api/v1/projects/{project_id}/story-planning/card-candidates/generate")
        self.assertEqual(generate_resp.status_code, 200)
        report = generate_resp.json()["data"]
        self.assertGreaterEqual(report["generated_count"], 5)
        self.assertGreaterEqual(report["skipped_count"], 2)

        all_resp = self.client.get(f"/api/v1/projects/{project_id}/story-planning/card-candidates")
        self.assertEqual(all_resp.status_code, 200)
        items = all_resp.json()["data"]
        self.assertTrue(any(item["card_type"] == "terminology" and item["name"] == "禁术反噬" for item in items))
        self.assertFalse(any(item["name"] == "未知实体123" for item in items))

        pending_resp = self.client.get(f"/api/v1/projects/{project_id}/story-planning/card-candidates?status=pending")
        self.assertEqual(pending_resp.status_code, 200)
        self.assertTrue(all(item["status"] == "pending" for item in pending_resp.json()["data"]))

        terminology_resp = self.client.get(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates?card_type=terminology"
        )
        self.assertEqual(terminology_resp.status_code, 200)
        self.assertTrue(all(item["card_type"] == "terminology" for item in terminology_resp.json()["data"]))

        first_id = items[0]["id"]
        detail_resp = self.client.get(f"/api/v1/projects/{project_id}/story-planning/card-candidates/{first_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["data"]["id"], first_id)

        duplicate_generate = self.client.post(f"/api/v1/projects/{project_id}/story-planning/card-candidates/generate")
        self.assertEqual(duplicate_generate.status_code, 200)
        self.assertGreater(duplicate_generate.json()["data"]["skipped_count"], 0)

    def test_confirm_and_skip_candidate_flow(self):
        project_id = self._create_project("confirm")
        self._seed_planning_and_directory(project_id)

        before_counts = self._count_canon_and_changesets(project_id)
        stale_before = self._count_stale_events(project_id)

        generate_resp = self.client.post(f"/api/v1/projects/{project_id}/story-planning/card-candidates/generate")
        self.assertEqual(generate_resp.status_code, 200)

        list_resp = self.client.get(f"/api/v1/projects/{project_id}/story-planning/card-candidates?status=pending")
        self.assertEqual(list_resp.status_code, 200)
        pending = list_resp.json()["data"]

        by_type = {}
        for item in pending:
            by_type.setdefault(item["card_type"], item)

        character_confirm = self.client.post(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates/{by_type['character']['id']}/confirm"
        )
        self.assertEqual(character_confirm.status_code, 200)
        self.assertEqual(character_confirm.json()["data"]["status"], "confirmed")

        terminology_confirm = self.client.post(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates/{by_type['terminology']['id']}/confirm"
        )
        self.assertEqual(terminology_confirm.status_code, 200)
        self.assertEqual(terminology_confirm.json()["data"]["status"], "confirmed")

        faction_confirm = self.client.post(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates/{by_type['faction']['id']}/confirm"
        )
        self.assertEqual(faction_confirm.status_code, 200)
        self.assertEqual(faction_confirm.json()["data"]["status"], "confirmed")

        location_confirm = self.client.post(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates/{by_type['location']['id']}/confirm"
        )
        self.assertEqual(location_confirm.status_code, 200)
        self.assertEqual(location_confirm.json()["data"]["status"], "confirmed")

        with SessionLocal() as db:
            self.assertGreater(db.query(StructuredCharacterCardORM).filter(StructuredCharacterCardORM.project_id == project_id).count(), 0)
            self.assertGreater(db.query(TerminologyCardORM).filter(TerminologyCardORM.project_id == project_id).count(), 0)
            self.assertGreater(db.query(StructuredFactionCardORM).filter(StructuredFactionCardORM.project_id == project_id).count(), 0)
            self.assertGreater(db.query(StructuredLocationCardORM).filter(StructuredLocationCardORM.project_id == project_id).count(), 0)

        self.client.post(f"/api/v1/projects/{project_id}/story-planning/card-candidates/generate")
        # select one pending candidate from regenerated list
        new_pending = self.client.get(f"/api/v1/projects/{project_id}/story-planning/card-candidates?status=pending").json()["data"]
        if new_pending:
            skip_resp = self.client.post(
                f"/api/v1/projects/{project_id}/story-planning/card-candidates/{new_pending[0]['id']}/skip"
            )
            self.assertEqual(skip_resp.status_code, 200)
            self.assertEqual(skip_resp.json()["data"]["status"], "skipped")

        repeat_confirm = self.client.post(
            f"/api/v1/projects/{project_id}/story-planning/card-candidates/{by_type['character']['id']}/confirm"
        )
        self.assertEqual(repeat_confirm.status_code, 422)

        # confirm candidate when formal card already exists -> skipped
        extra_project = self._create_project("skip-existing")
        self._seed_planning_and_directory(extra_project)
        self.client.post(f"/api/v1/projects/{extra_project}/story-planning/card-candidates/generate")
        with SessionLocal() as db:
            db.add(
                TerminologyCardORM(
                    project_id=extra_project,
                    term="灵脉回流",
                    term_type="术语",
                    definition="已存在",
                    usage_rules="",
                    examples=[],
                    first_appearance_chapter=1,
                    last_update_source="manual",
                    is_canon=False,
                )
            )
            db.commit()
        terminology_candidates = self.client.get(
            f"/api/v1/projects/{extra_project}/story-planning/card-candidates?status=pending&card_type=terminology"
        ).json()["data"]
        pending_term = next(item for item in terminology_candidates if item["name"] == "灵脉回流")
        skip_existing = self.client.post(
            f"/api/v1/projects/{extra_project}/story-planning/card-candidates/{pending_term['id']}/confirm"
        )
        self.assertEqual(skip_existing.status_code, 200)
        self.assertEqual(skip_existing.json()["data"]["status"], "skipped")

        after_counts = self._count_canon_and_changesets(project_id)
        stale_after = self._count_stale_events(project_id)
        self.assertEqual(before_counts, after_counts)
        self.assertEqual(stale_before, stale_after)

        with SessionLocal() as db:
            candidate_rows = db.query(StructuredCardCandidateORM).filter(StructuredCardCandidateORM.project_id == project_id).all()
            self.assertTrue(any(row.status == "confirmed" for row in candidate_rows))


if __name__ == "__main__":
    unittest.main()
