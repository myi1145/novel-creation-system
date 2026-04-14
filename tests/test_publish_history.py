import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import PublishRecordORM
from app.db.session import SessionLocal
from app.main import create_app


class PublishHistoryTest(unittest.TestCase):
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
            json={"project_name": f"publish-history-{uuid4().hex[:8]}", "premise": "ph", "genre_id": "default"},
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

    def _prepare_chain_without_publish(self) -> tuple[str, str, str]:
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

    def _publish_ready_draft(self) -> tuple[str, str, str]:
        project_id, blueprint_id, draft_id = self._prepare_chain_without_publish()
        self.assertEqual(
            self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
            ).status_code,
            200,
        )
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "ph", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={}).status_code, 200)
        publish = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft_id, "published_by": "tester", "notes": "首次发布"},
        )
        self.assertEqual(publish.status_code, 200)
        return project_id, blueprint_id, publish.json()["data"]["publish_record"]["id"]

    def _get_publish_history(self, project_id: str) -> dict:
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/publish-history")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def test_never_published_when_no_publish_record(self):
        project_id, _, _ = self._prepare_chain_without_publish()
        payload = self._get_publish_history(project_id)
        self.assertIsNone(payload["latest_published"])
        self.assertEqual(payload["working_state_relation"]["status"], "never_published")
        self.assertEqual(payload["history"], [])

    def test_should_return_latest_published_and_history(self):
        project_id, _, publish_record_id = self._publish_ready_draft()
        payload = self._get_publish_history(project_id)
        self.assertEqual(payload["latest_published"]["publish_record_id"], publish_record_id)
        self.assertGreaterEqual(len(payload["history"]), 1)
        first = payload["history"][0]
        self.assertIn("draft_ref_id", first)
        self.assertIn("changeset_ref_id", first)
        self.assertIn("summary", first)
        self.assertEqual(first["status"], "published")

    def test_should_return_work_in_progress_after_publish_when_new_working_state_exists(self):
        project_id, blueprint_id, _ = self._publish_ready_draft()
        self.assertEqual(
            self.client.patch(
                f"/api/v1/chapters/blueprints/{blueprint_id}",
                json={"project_id": project_id, "summary": "publish 后修订", "edit_reason": "manual", "edited_by": "tester"},
            ).status_code,
            200,
        )
        payload = self._get_publish_history(project_id)
        self.assertEqual(payload["working_state_relation"]["status"], "work_in_progress_after_publish")

    def test_should_return_up_to_date_when_no_new_working_state_after_publish(self):
        project_id, _, _ = self._publish_ready_draft()
        payload = self._get_publish_history(project_id)
        self.assertEqual(payload["working_state_relation"]["status"], "up_to_date")

    def test_response_shape_should_be_stable(self):
        project_id, _, _ = self._publish_ready_draft()
        payload = self._get_publish_history(project_id)
        self.assertEqual(set(payload.keys()), {"project_id", "chapter_no", "latest_published", "working_state_relation", "history"})
        self.assertEqual(set(payload["working_state_relation"].keys()), {"status", "message"})

    def test_history_should_be_sorted_by_published_at_desc(self):
        project_id, _, publish_record_id = self._publish_ready_draft()
        with SessionLocal() as db:
            record = db.get(PublishRecordORM, publish_record_id)
            self.assertIsNotNone(record)
            db.add(
                PublishRecordORM(
                    project_id=record.project_id,
                    published_chapter_id=record.published_chapter_id,
                    workflow_run_id=record.workflow_run_id,
                    trace_id=record.trace_id,
                    draft_id=record.draft_id,
                    snapshot_id=record.snapshot_id,
                    changeset_id=record.changeset_id,
                    publish_gate_review_id=record.publish_gate_review_id,
                    published_by="tester-2",
                    publish_status="published",
                    notes="补录记录",
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                )
            )
            db.commit()

        payload = self._get_publish_history(project_id)
        published_at_list = [datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")) for item in payload["history"]]
        self.assertEqual(published_at_list, sorted(published_at_list, reverse=True))


if __name__ == "__main__":
    unittest.main()
