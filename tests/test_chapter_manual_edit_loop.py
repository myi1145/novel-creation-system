import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


class ChapterManualEditLoopTest(unittest.TestCase):
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

    def _prepare_draft(self) -> tuple[str, str]:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"manual-edit-{uuid4().hex[:8]}", "premise": "manual-edit", "genre_id": "default"},
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

        goal = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "goal"},
        )
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]

        blueprints = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(blueprints.status_code, 200)
        blueprint_id = blueprints.json()["data"][0]["id"]

        selected = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(selected.status_code, 200)
        scenes = self.client.post(
            "/api/v1/chapters/scenes/decompose",
            json={"project_id": project_id, "blueprint_id": blueprint_id},
        )
        self.assertEqual(scenes.status_code, 200)

        draft = self.client.post(
            "/api/v1/chapters/drafts/generate",
            json={"project_id": project_id, "blueprint_id": blueprint_id},
        )
        self.assertEqual(draft.status_code, 200)
        draft_id = draft.json()["data"]["id"]
        return project_id, draft_id

    def test_manual_edit_should_update_draft_and_keep_chain_path_available(self):
        project_id, draft_id = self._prepare_draft()

        edited_content = "这是作者人工修订后的正文内容。"
        manual_edit = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/manual-edit",
            json={
                "project_id": project_id,
                "content": edited_content,
                "edit_reason": "人工接管修正文风与信息密度",
                "edited_by": "unit_tester",
            },
        )
        self.assertEqual(manual_edit.status_code, 200)
        edited = manual_edit.json()["data"]
        self.assertEqual(edited["content"], edited_content)
        self.assertEqual(edited["metadata"].get("edit_reason"), "人工接管修正文风与信息密度")
        self.assertEqual(edited["metadata"].get("source_type"), "human_edited")
        self.assertEqual(edited["metadata"].get("edited_by"), "unit_tester")
        self.assertTrue(edited["metadata"].get("edited_at"))

        history = self.client.get(f"/api/v1/chapters/drafts/{draft_id}/state-history?project_id={project_id}")
        self.assertEqual(history.status_code, 200)
        trigger_types = [item.get("trigger_type") for item in history.json()["data"]]
        self.assertIn("human_edit", trigger_types)

        gate = self.client.post(
            "/api/v1/gates/reviews",
            json={
                "project_id": project_id,
                "draft_id": draft_id,
                "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"],
            },
        )
        self.assertEqual(gate.status_code, 200)

        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "manual-edit-loop", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)

        proposal_data = proposal.json()["data"]
        changeset_payload = proposal_data.get("changeset") or {}
        changeset_id = changeset_payload.get("id")

        if not changeset_id:
            changesets_resp = self.client.get("/api/v1/changesets")
            self.assertEqual(changesets_resp.status_code, 200)
            changesets = changesets_resp.json()["data"]
            target = next(
                (
                    item
                    for item in changesets
                    if item.get("project_id") == project_id and item.get("source_ref") == draft_id
                ),
                None,
            )
            self.assertIsNotNone(target)
            changeset_id = target["id"]

        approve = self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "unit_tester"})
        self.assertEqual(approve.status_code, 200)
        apply_resp = self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={})
        self.assertEqual(apply_resp.status_code, 200)

        publish = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft_id, "published_by": "unit_tester"},
        )
        self.assertEqual(publish.status_code, 200)
        publish_data = publish.json()["data"]
        published_chapter = publish_data.get("published_chapter") or {}
        self.assertEqual(published_chapter.get("draft_id"), draft_id)


if __name__ == "__main__":
    unittest.main()
