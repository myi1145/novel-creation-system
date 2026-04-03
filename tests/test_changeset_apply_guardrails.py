import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import CanonSnapshotORM, ChangeSetORM
from app.db.session import SessionLocal
from app.main import create_app


class ChangeSetApplyGuardrailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_provider = settings.agent_provider
        cls._original_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._original_provider
        settings.agent_fallback_to_mock = cls._original_fallback

    def _create_project_with_canon(self) -> str:
        project_resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"changeset-apply-{uuid4().hex[:8]}",
                "premise": "验证 ChangeSet apply 幂等与并发互斥边界",
                "genre_id": "default",
            },
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]

        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "init",
                "initial_rules": [{"rule_name": "规则", "description": "初始规则", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        return project_id

    def _prepare_approved_changeset(self, project_id: str) -> dict:
        goal_resp = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "开篇目标"},
        )
        self.assertEqual(goal_resp.status_code, 200)
        goal = goal_resp.json()["data"]

        blueprints_resp = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal["id"], "candidate_count": 2},
        )
        self.assertEqual(blueprints_resp.status_code, 200)
        blueprint_id = blueprints_resp.json()["data"][0]["id"]

        selected_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(selected_resp.status_code, 200)

        scenes_resp = self.client.post(
            "/api/v1/chapters/scenes/decompose",
            json={"project_id": project_id, "blueprint_id": blueprint_id},
        )
        self.assertEqual(scenes_resp.status_code, 200)

        draft_resp = self.client.post(
            "/api/v1/chapters/drafts/generate",
            json={"project_id": project_id, "blueprint_id": blueprint_id},
        )
        self.assertEqual(draft_resp.status_code, 200)
        draft = draft_resp.json()["data"]

        gate_resp = self.client.post(
            "/api/v1/gates/reviews",
            json={"project_id": project_id, "draft_id": draft["id"]},
        )
        self.assertEqual(gate_resp.status_code, 200)

        proposal_resp = self.client.post(
            f"/api/v1/chapters/drafts/{draft['id']}/changeset-proposals/generate",
            json={"project_id": project_id},
        )
        self.assertEqual(proposal_resp.status_code, 200)
        proposal = proposal_resp.json()["data"]

        changeset_resp = self.client.post(
            "/api/v1/changesets/propose",
            json={
                "project_id": project_id,
                "source_type": "chapter_draft",
                "source_ref": draft["id"],
                "rationale": proposal["rationale"],
                "patch_operations": proposal["patch_operations"],
            },
        )
        self.assertEqual(changeset_resp.status_code, 200)
        changeset = changeset_resp.json()["data"]

        approve_resp = self.client.post(
            f"/api/v1/changesets/{changeset['id']}/approve",
            json={"approved_by": "tester"},
        )
        self.assertEqual(approve_resp.status_code, 200)
        return approve_resp.json()["data"]

    def test_apply_should_be_idempotent_after_successful_commit(self):
        project_id = self._create_project_with_canon()
        approved_changeset = self._prepare_approved_changeset(project_id)

        first_apply = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(first_apply.status_code, 200)
        first_data = first_apply.json()["data"]
        self.assertEqual(first_data["status"], "applied")
        self.assertTrue(first_data["result_snapshot_id"])

        with SessionLocal() as db:
            snapshot_count_after_first = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()

        second_apply = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(second_apply.status_code, 200)
        second_data = second_apply.json()["data"]
        self.assertEqual(second_data["status"], "applied")
        self.assertEqual(second_data["result_snapshot_id"], first_data["result_snapshot_id"])

        with SessionLocal() as db:
            snapshot_count_after_second = db.query(CanonSnapshotORM).filter(CanonSnapshotORM.project_id == project_id).count()
        self.assertEqual(snapshot_count_after_second, snapshot_count_after_first)

    def test_apply_should_reject_when_changeset_is_inflight(self):
        project_id = self._create_project_with_canon()
        approved_changeset = self._prepare_approved_changeset(project_id)

        with SessionLocal() as db:
            changeset_row = db.get(ChangeSetORM, approved_changeset["id"])
            changeset_row.status = "applying"
            db.commit()

        inflight_resp = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(inflight_resp.status_code, 409)
        self.assertIn("正在应用中", inflight_resp.json()["error"]["message"])

    def test_apply_should_recover_to_applied_when_snapshot_already_exists(self):
        project_id = self._create_project_with_canon()
        approved_changeset = self._prepare_approved_changeset(project_id)

        first_apply = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(first_apply.status_code, 200)
        applied = first_apply.json()["data"]
        self.assertTrue(applied["result_snapshot_id"])

        with SessionLocal() as db:
            changeset_row = db.get(ChangeSetORM, approved_changeset["id"])
            changeset_row.status = "applying"
            db.commit()

        recovered_resp = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(recovered_resp.status_code, 200)
        recovered = recovered_resp.json()["data"]
        self.assertEqual(recovered["status"], "applied")
        self.assertEqual(recovered["result_snapshot_id"], applied["result_snapshot_id"])

    def test_apply_should_recover_stale_applying_back_to_approved_and_continue(self):
        project_id = self._create_project_with_canon()
        approved_changeset = self._prepare_approved_changeset(project_id)
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)

        with SessionLocal() as db:
            (
                db.query(ChangeSetORM)
                .filter(ChangeSetORM.id == approved_changeset["id"])
                .update(
                    {
                        ChangeSetORM.status: "applying",
                        ChangeSetORM.updated_at: stale_time,
                    },
                    synchronize_session=False,
                )
            )
            db.commit()

        recovered_apply = self.client.post(f"/api/v1/changesets/{approved_changeset['id']}/apply")
        self.assertEqual(recovered_apply.status_code, 200)
        data = recovered_apply.json()["data"]
        self.assertEqual(data["status"], "applied")
        self.assertTrue(data["result_snapshot_id"])


if __name__ == "__main__":
    unittest.main()
