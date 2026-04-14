import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM, ChangeSetORM, GateReviewORM, PublishRecordORM
from app.db.session import SessionLocal
from app.main import create_app


class PublishedReaderExportTest(unittest.TestCase):
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
            json={"project_name": f"published-reader-{uuid4().hex[:8]}", "premise": "pre", "genre_id": "default"},
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

    def _prepare_chain_without_publish(self) -> tuple[str, str]:
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
        return project_id, draft.json()["data"]["id"]

    def _publish_ready_draft(self) -> tuple[str, str]:
        project_id, draft_id = self._prepare_chain_without_publish()
        self.assertEqual(
            self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
            ).status_code,
            200,
        )
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "pre", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={}).status_code, 200)
        publish = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft_id, "published_by": "tester", "notes": "reader-export"},
        )
        self.assertEqual(publish.status_code, 200)
        return project_id, publish.json()["data"]["publish_record"]["id"]

    def test_reader_should_return_latest_published_payload(self):
        project_id, publish_record_id = self._publish_ready_draft()
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()["data"]
        self.assertEqual(payload["publish_record_id"], publish_record_id)
        self.assertEqual(payload["chapter_no"], 1)
        self.assertIn("title", payload)
        self.assertIn("content", payload)
        self.assertIn("published_at", payload)
        self.assertIn("draft_ref_id", payload)
        self.assertIn("changeset_ref_id", payload)
        self.assertEqual(payload["status"], "published")
        self.assertEqual(payload["word_count"], len(payload["content"]))

    def test_reader_should_return_404_when_never_published(self):
        project_id, _ = self._prepare_chain_without_publish()
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader")
        self.assertEqual(resp.status_code, 404)

    def test_markdown_export_should_include_title_time_and_content(self):
        project_id, _ = self._publish_ready_draft()
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader/export.md")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/markdown", resp.headers.get("content-type", ""))
        text = resp.text
        self.assertIn("# 第 1 章", text)
        self.assertIn("> 发布时间：", text)
        self.assertNotIn("publish_record_id", text)
        self.assertNotIn("changeset_ref_id", text)

    def test_txt_export_should_include_title_time_and_content(self):
        project_id, _ = self._publish_ready_draft()
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader/export.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers.get("content-type", ""))
        text = resp.text
        self.assertIn("第 1 章", text)
        self.assertIn("发布时间：", text)
        self.assertNotIn("publish_record_id", text)
        self.assertNotIn("changeset_ref_id", text)

    def test_reader_and_exports_should_be_readonly(self):
        project_id, _ = self._publish_ready_draft()
        with SessionLocal() as db:
            before_records = db.query(PublishRecordORM).filter(PublishRecordORM.project_id == project_id).count()
            before_drafts = db.query(ChapterDraftORM).filter(ChapterDraftORM.project_id == project_id).count()
            before_gates = db.query(GateReviewORM).filter(GateReviewORM.project_id == project_id).count()
            before_changesets = db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count()

        self.assertEqual(self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader/export.md").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/published-reader/export.txt").status_code, 200)

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
