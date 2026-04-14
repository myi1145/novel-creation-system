import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM, ChangeSetORM, GateReviewORM, PublishRecordORM
from app.db.session import SessionLocal
from app.main import create_app


class VersionDiffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback

    def _create_project(self) -> str:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"version-diff-{uuid4().hex[:8]}", "premise": "vd", "genre_id": "default"},
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "init",
                "initial_rules": [{"rule_name": "r", "description": "d", "severity": "hard"}],
                "initial_characters": [{"character_name": "c", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        return project_id

    def _prepare_chain(self) -> tuple[str, str, str]:
        project_id = self._create_project()
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "goal"})
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        blueprints = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(blueprints.status_code, 200)
        blueprint_id = blueprints.json()["data"][0]["id"]
        self.assertEqual(
            self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"}).status_code,
            200,
        )
        self.assertEqual(self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id}).status_code, 200)
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(draft.status_code, 200)
        return project_id, blueprint_id, draft.json()["data"]["id"]

    def _publish_draft(self, project_id: str, draft_id: str) -> str:
        self.assertEqual(
            self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
            ).status_code,
            200,
        )
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "vd", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={}).status_code, 200)
        publish = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft_id, "published_by": "tester"},
        )
        self.assertEqual(publish.status_code, 200)
        return publish.json()["data"]["publish_record"]["id"]

    def _get_diff(self, project_id: str) -> dict:
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/version-diff")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def test_should_return_never_published_and_cannot_compare(self):
        project_id, _, _ = self._prepare_chain()
        payload = self._get_diff(project_id)
        self.assertEqual(payload["comparison_status"], "never_published")
        self.assertEqual(payload["recommendation"], "cannot_compare")

    def test_should_return_no_current_work_and_cannot_compare(self):
        project_id, _, draft_id = self._prepare_chain()
        self._publish_draft(project_id, draft_id)
        payload = self._get_diff(project_id)
        self.assertEqual(payload["comparison_status"], "no_current_work")
        self.assertEqual(payload["recommendation"], "cannot_compare")

    def test_should_return_republish_not_needed_when_no_significant_diff(self):
        project_id, blueprint_id, draft_id = self._prepare_chain()
        self._publish_draft(project_id, draft_id)
        regenerated = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(regenerated.status_code, 200)

        payload = self._get_diff(project_id)
        self.assertEqual(payload["comparison_status"], "comparable")
        self.assertEqual(payload["recommendation"], "republish_not_needed")

    def test_should_return_republish_recommended_when_significant_diff(self):
        project_id, blueprint_id, draft_id = self._prepare_chain()
        self._publish_draft(project_id, draft_id)
        regenerated = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(regenerated.status_code, 200)
        latest_draft_id = regenerated.json()["data"]["id"]

        edited = self.client.post(
            f"/api/v1/chapters/drafts/{latest_draft_id}/manual-edit",
            json={
                "project_id": project_id,
                "content": "\n\n".join(["这是发布后的重大改写段落" for _ in range(30)]),
                "edit_reason": "publish 后大改",
                "edited_by": "tester",
            },
        )
        self.assertEqual(edited.status_code, 200)

        payload = self._get_diff(project_id)
        self.assertEqual(payload["comparison_status"], "comparable")
        self.assertEqual(payload["recommendation"], "republish_recommended")
        self.assertIn(payload["diff"]["change_level"], ["moderate", "major"])

    def test_should_return_length_and_paragraph_delta(self):
        project_id, blueprint_id, draft_id = self._prepare_chain()
        self._publish_draft(project_id, draft_id)
        regenerated = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(regenerated.status_code, 200)
        latest_draft_id = regenerated.json()["data"]["id"]
        edited = self.client.post(
            f"/api/v1/chapters/drafts/{latest_draft_id}/manual-edit",
            json={
                "project_id": project_id,
                "content": "第一段\n\n第二段\n\n第三段",
                "edit_reason": "test delta",
                "edited_by": "tester",
            },
        )
        self.assertEqual(edited.status_code, 200)

        payload = self._get_diff(project_id)
        self.assertIn("length_delta", payload["diff"])
        self.assertIn("paragraph_delta", payload["diff"])
        self.assertIsInstance(payload["diff"]["length_delta"], int)
        self.assertIsInstance(payload["diff"]["paragraph_delta"], int)

    def test_response_shape_should_be_stable(self):
        project_id, _, _ = self._prepare_chain()
        payload = self._get_diff(project_id)
        self.assertEqual(
            set(payload.keys()),
            {"project_id", "chapter_no", "comparison_status", "recommendation", "summary", "published_ref", "current_ref", "diff", "checks"},
        )

    def test_version_diff_should_be_readonly(self):
        project_id, _, draft_id = self._prepare_chain()
        self._publish_draft(project_id, draft_id)

        with SessionLocal() as db:
            before_records = db.query(PublishRecordORM).filter(PublishRecordORM.project_id == project_id).count()
            before_drafts = db.query(ChapterDraftORM).filter(ChapterDraftORM.project_id == project_id).count()
            before_gates = db.query(GateReviewORM).filter(GateReviewORM.project_id == project_id).count()
            before_changesets = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()

        _ = self._get_diff(project_id)

        with SessionLocal() as db:
            after_records = db.query(PublishRecordORM).filter(PublishRecordORM.project_id == project_id).count()
            after_drafts = db.query(ChapterDraftORM).filter(ChapterDraftORM.project_id == project_id).count()
            after_gates = db.query(GateReviewORM).filter(GateReviewORM.project_id == project_id).count()
            after_changesets = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_drafts, after_drafts)
        self.assertEqual(before_gates, after_gates)
        self.assertEqual(before_changesets, after_changesets)


if __name__ == "__main__":
    unittest.main()
