import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


class SceneManualEditLoopTest(unittest.TestCase):
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

    def _prepare_scene(self) -> tuple[str, str, str]:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"scene-edit-{uuid4().hex[:8]}", "premise": "scene-edit", "genre_id": "default"},
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
        scene_id = scenes.json()["data"][0]["id"]
        return project_id, blueprint_id, scene_id

    def test_scene_manual_edit_should_be_auditable_and_chain_continuable(self):
        project_id, blueprint_id, scene_id = self._prepare_scene()

        edited = self.client.patch(
            f"/api/v1/chapters/scenes/{scene_id}",
            json={
                "project_id": project_id,
                "scene_goal": "作者人工接管后的场景目标：强化冲突并推进伏笔。",
                "participating_entities": ["主角", "对手"],
                "conflict_type": "value_clash",
                "emotional_curve": "tension_to_doubt",
                "information_delta": "揭示对手真实动机线索",
                "edit_reason": "自动拆解冲突强度不足，需要人工增强",
                "edited_by": "unit_tester",
            },
        )
        self.assertEqual(edited.status_code, 200)
        payload = edited.json()["data"]
        self.assertEqual(payload["scene_goal"], "作者人工接管后的场景目标：强化冲突并推进伏笔。")
        self.assertEqual(payload["extension_fields"].get("edit_reason"), "自动拆解冲突强度不足，需要人工增强")
        self.assertEqual(payload["extension_fields"].get("source_type"), "human_edited")
        self.assertEqual(payload["extension_fields"].get("edited_by"), "unit_tester")
        self.assertTrue(payload["extension_fields"].get("edited_at"))

        scene_get = self.client.get(f"/api/v1/chapters/scenes/{scene_id}?project_id={project_id}")
        self.assertEqual(scene_get.status_code, 200)
        self.assertEqual(scene_get.json()["data"]["extension_fields"].get("source_type"), "human_edited")

        history = self.client.get(f"/api/v1/chapters/scenes/{scene_id}/state-history?project_id={project_id}")
        self.assertEqual(history.status_code, 200)
        trigger_types = [item.get("trigger_type") for item in history.json()["data"]]
        self.assertIn("human_edit", trigger_types)

        draft = self.client.post(
            "/api/v1/chapters/drafts/generate",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "scene_ids": [scene_id]},
        )
        self.assertEqual(draft.status_code, 200)
        draft_id = draft.json()["data"]["id"]

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
            json={"project_id": project_id, "rationale": "scene-manual-edit-loop", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)

        approve = self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "unit_tester"})
        self.assertEqual(approve.status_code, 200)
        apply_result = self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={})
        self.assertEqual(apply_result.status_code, 200)

        publish = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft_id, "published_by": "unit_tester"},
        )
        self.assertEqual(publish.status_code, 200)


if __name__ == "__main__":
    unittest.main()
