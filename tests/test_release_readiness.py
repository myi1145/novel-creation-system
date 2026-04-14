import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import GateReviewORM
from app.db.session import SessionLocal
from app.main import create_app


class ReleaseReadinessTest(unittest.TestCase):
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
            json={"project_name": f"release-readiness-{uuid4().hex[:8]}", "premise": "rr", "genre_id": "default"},
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

    def _prepare_draft_chain(self) -> tuple[str, str, str]:
        project_id = self._create_project()
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "goal"})
        goal_id = goal.json()["data"]["id"]
        blueprints = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        blueprint_id = blueprints.json()["data"][0]["id"]
        self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"})
        self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id})
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        draft_id = draft.json()["data"]["id"]
        return project_id, blueprint_id, draft_id

    def _get_readiness(self, project_id: str) -> dict:
        resp = self.client.get(f"/api/v1/chapters/projects/{project_id}/chapters/1/release-readiness")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def test_open_stale_makes_overall_needs_attention(self):
        project_id, blueprint_id, _ = self._prepare_draft_chain()
        self.assertEqual(
            self.client.patch(
                f"/api/v1/chapters/blueprints/{blueprint_id}",
                json={"project_id": project_id, "summary": "edit", "edit_reason": "manual", "edited_by": "tester"},
            ).status_code,
            200,
        )
        payload = self._get_readiness(project_id)
        self.assertEqual(payload["overall_status"], "needs_attention")
        stale = next(item for item in payload["checks"] if item["key"] == "stale")
        self.assertEqual(stale["status"], "warning")

    def test_gate_missing_makes_overall_needs_attention(self):
        project_id, _, _ = self._prepare_draft_chain()
        payload = self._get_readiness(project_id)
        self.assertEqual(payload["overall_status"], "needs_attention")
        gate = next(item for item in payload["checks"] if item["key"] == "gate")
        self.assertEqual(gate["status"], "missing")

    def test_gate_failed_makes_overall_needs_attention(self):
        project_id, _, draft_id = self._prepare_draft_chain()
        with SessionLocal() as db:
            db.add(
                GateReviewORM(
                    project_id=project_id,
                    draft_id=draft_id,
                    gate_name="schema_gate",
                    pass_status="failed",
                    passed=False,
                    highest_severity="S2",
                    recommended_route="revise",
                    can_override=False,
                    issues=[{"message": "failed"}],
                )
            )
            db.commit()
        payload = self._get_readiness(project_id)
        self.assertEqual(payload["overall_status"], "needs_attention")
        gate = next(item for item in payload["checks"] if item["key"] == "gate")
        self.assertEqual(gate["status"], "warning")

    def test_unapplied_changeset_makes_overall_needs_attention(self):
        project_id, _, draft_id = self._prepare_draft_chain()
        self.assertEqual(
            self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
            ).status_code,
            200,
        )
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "rr", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        payload = self._get_readiness(project_id)
        self.assertEqual(payload["overall_status"], "needs_attention")
        changeset = next(item for item in payload["checks"] if item["key"] == "changeset")
        self.assertEqual(changeset["status"], "warning")

    def test_ready_to_publish_when_stale_empty_gate_pass_and_changeset_processed(self):
        project_id, _, draft_id = self._prepare_draft_chain()
        self.assertEqual(
            self.client.post(
                "/api/v1/gates/reviews",
                json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
            ).status_code,
            200,
        )
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "rr-ready", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={}).status_code, 200)

        payload = self._get_readiness(project_id)
        self.assertEqual(payload["overall_status"], "ready_to_publish")
        checks = {item["key"]: item for item in payload["checks"]}
        self.assertEqual(checks["stale"]["status"], "ok")
        self.assertEqual(checks["gate"]["status"], "ok")
        self.assertEqual(checks["changeset"]["status"], "ok")
        self.assertIn("publish", checks)

    def test_response_contains_four_checks(self):
        project_id, _, _ = self._prepare_draft_chain()
        payload = self._get_readiness(project_id)
        keys = sorted([item["key"] for item in payload["checks"]])
        self.assertEqual(keys, ["changeset", "gate", "publish", "stale"])


if __name__ == "__main__":
    unittest.main()
