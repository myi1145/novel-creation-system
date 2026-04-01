import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM, PublishedChapterORM
from app.db.session import SessionLocal
from app.main import create_app
from app.services.seed_consumption_service import SeedConsumptionContext, seed_consumption_service


class SeedConsumptionGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_enable = settings.enable_seed_consumption_gate
        cls._orig_strict = settings.seed_consumption_require_strict
        cls._orig_min = settings.seed_consumption_min_matched_fragments
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True

    @classmethod
    def tearDownClass(cls):
        settings.enable_seed_consumption_gate = cls._orig_enable
        settings.seed_consumption_require_strict = cls._orig_strict
        settings.seed_consumption_min_matched_fragments = cls._orig_min
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback

    def setUp(self):
        settings.enable_seed_consumption_gate = True
        settings.seed_consumption_require_strict = False
        settings.seed_consumption_min_matched_fragments = 1

    def _create_project(self) -> str:
        project_resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"seed-gate-{uuid4().hex[:8]}", "premise": "seed gate tests", "genre_id": "default"},
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]
        snapshot_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "seed-gate-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        return project_id

    def _publish_chapter(self, project_id: str, chapter_no: int) -> dict:
        goal = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": chapter_no, "current_volume_goal": f"第{chapter_no}章推进"},
        )
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        blueprint = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(blueprint.status_code, 200)
        blueprint_id = blueprint.json()["data"][0]["id"]
        self.assertEqual(
            self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"}).status_code,
            200,
        )
        self.assertEqual(self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id}).status_code, 200)
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(draft.status_code, 200)
        draft_id = draft.json()["data"]["id"]
        self.assertEqual(self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id}).status_code, 200)
        proposal = self.client.post(f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate", json={"project_id": project_id})
        self.assertEqual(proposal.status_code, 200)
        changeset = self.client.post(
            "/api/v1/changesets/propose",
            json={
                "project_id": project_id,
                "source_type": "chapter_draft",
                "source_ref": draft_id,
                "rationale": proposal.json()["data"]["rationale"],
                "patch_operations": proposal.json()["data"]["patch_operations"],
            },
        )
        self.assertEqual(changeset.status_code, 200)
        changeset_id = changeset.json()["data"]["id"]
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply").status_code, 200)
        publish = self.client.post("/api/v1/chapters/drafts/publish", json={"project_id": project_id, "draft_id": draft_id, "published_by": "tester"})
        self.assertEqual(publish.status_code, 200)
        return publish.json()["data"]

    def test_seed_consumption_decision_consumed(self):
        report = seed_consumption_service.evaluate(
            SeedConsumptionContext(
                chapter_no=2,
                previous_next_chapter_seed="去码头调查失踪的黑匣子，并决定是否公开真相",
                previous_summary="上一章留下黑匣子线索。",
                current_chapter_text="她决定连夜去码头调查黑匣子失踪案，并在冲突后决定公开真相。",
                current_summary="本章行动推进",
            )
        )
        self.assertEqual(report.decision, "consumed")

    def test_seed_consumption_decision_weak_and_missing(self):
        weak = seed_consumption_service.evaluate(
            SeedConsumptionContext(
                chapter_no=2,
                previous_next_chapter_seed="去码头调查失踪的黑匣子",
                previous_summary="",
                current_chapter_text="他在茶馆提到黑匣子和码头传闻，但没有继续行动。",
                current_summary="只是提及线索",
            )
        )
        self.assertEqual(weak.decision, "weak")
        missing = seed_consumption_service.evaluate(
            SeedConsumptionContext(
                chapter_no=2,
                previous_next_chapter_seed="去码头调查失踪的黑匣子",
                previous_summary="",
                current_chapter_text="本章围绕家族宴会展开，角色讨论旧怨。",
                current_summary="没有承接前章种子",
            )
        )
        self.assertEqual(missing.decision, "missing")

    def test_strict_mode_blocks_on_narrative_gate_missing_seed(self):
        settings.seed_consumption_require_strict = True
        project_id = self._create_project()
        chapter1 = self._publish_chapter(project_id=project_id, chapter_no=1)
        published_id = chapter1["published_chapter"]["id"]

        with SessionLocal() as db:
            published = db.get(PublishedChapterORM, published_id)
            self.assertIsNotNone(published)
            metadata = dict(published.publish_metadata or {})
            chapter_summary = dict(metadata.get("chapter_summary") or {})
            chapter_summary["next_chapter_seed"] = "去码头调查失踪的黑匣子并决定公开真相"
            metadata["chapter_summary"] = chapter_summary
            metadata["next_chapter_seed"] = chapter_summary["next_chapter_seed"]
            published.publish_metadata = metadata
            db.commit()

        goal = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": 2, "current_volume_goal": "推进第二章"},
        )
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        blueprint = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(blueprint.status_code, 200)
        blueprint_id = blueprint.json()["data"][0]["id"]
        self.assertEqual(
            self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"}).status_code,
            200,
        )
        self.assertEqual(self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id}).status_code, 200)
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(draft.status_code, 200)
        draft_id = draft.json()["data"]["id"]

        with SessionLocal() as db:
            row = db.get(ChapterDraftORM, draft_id)
            self.assertIsNotNone(row)
            row.content = "本章只写节日庆典与旁支人物闲聊，围绕家族旧账争执，没有承接上一章线索。"
            db.commit()

        gate_resp = self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id})
        self.assertEqual(gate_resp.status_code, 200)
        narrative = [item for item in gate_resp.json()["data"]["results"] if item["gate_name"] == "narrative_gate"][0]
        self.assertEqual(narrative["pass_status"], "failed")
        self.assertEqual(narrative["seed_consumption_report"]["decision"], "missing")

        proposal = self.client.post(f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate", json={"project_id": project_id})
        self.assertEqual(proposal.status_code, 409)
        err_msg = (proposal.json().get("error") or {}).get("message") or ""
        self.assertIn("缺少通过的 Gate", err_msg)


if __name__ == "__main__":
    unittest.main()
