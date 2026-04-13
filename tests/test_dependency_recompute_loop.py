import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


class DependencyRecomputeLoopTest(unittest.TestCase):
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

    def _prepare_blueprint_and_scene(self) -> tuple[str, str, str, str]:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"dependency-{uuid4().hex[:8]}", "premise": "dependency", "genre_id": "default"},
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "init",
                "initial_rules": [{"rule_name": "r", "description": "d", "severity": "hard"}],
                "initial_characters": [{"character_name": "c", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "goal"})
        goal_id = goal.json()["data"]["id"]
        blueprints = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        blueprint_id = blueprints.json()["data"][0]["id"]
        self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"})
        scenes = self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id})
        scene_id = scenes.json()["data"][0]["id"]
        return project_id, goal_id, blueprint_id, scene_id

    def test_dependency_stale_query_and_recompute(self):
        project_id, _, blueprint_id, scene_id = self._prepare_blueprint_and_scene()

        blueprint_edit = self.client.patch(
            f"/api/v1/chapters/blueprints/{blueprint_id}",
            json={"project_id": project_id, "summary": "manual blueprint edit", "edit_reason": "手工改蓝图", "edited_by": "tester"},
        )
        self.assertEqual(blueprint_edit.status_code, 200)

        chapter_dependency = self.client.get(f"/api/v1/chapters/dependency-status?project_id={project_id}&chapter_no=1")
        self.assertEqual(chapter_dependency.status_code, 200)
        chapter_items = chapter_dependency.json()["data"]["items"]
        self.assertTrue(any(item["affected_type"] == "scenes" for item in chapter_items))
        self.assertTrue(any(item["affected_type"] == "draft" for item in chapter_items))

        recompute_scenes = self.client.post(
            "/api/v1/chapters/dependency-status/recompute",
            json={"project_id": project_id, "chapter_no": 1, "action": "recompute_scenes", "confirmed_by": "tester"},
        )
        self.assertEqual(recompute_scenes.status_code, 200)
        self.assertGreaterEqual(len(recompute_scenes.json()["data"]["resolved_stale_ids"]), 1)

        scene_edit = self.client.patch(
            f"/api/v1/chapters/scenes/{scene_id}",
            json={"project_id": project_id, "scene_goal": "manual scene edit", "edit_reason": "手工改场景", "edited_by": "tester"},
        )
        self.assertEqual(scene_edit.status_code, 200)

        scene_dependency = self.client.get(f"/api/v1/chapters/dependency-status?project_id={project_id}&scene_id={scene_id}")
        self.assertEqual(scene_dependency.status_code, 200)
        scene_items = scene_dependency.json()["data"]["items"]
        self.assertTrue(any(item["affected_type"] == "draft" for item in scene_items))

        recompute_draft = self.client.post(
            "/api/v1/chapters/dependency-status/recompute",
            json={"project_id": project_id, "scene_id": scene_id, "source_id": scene_id, "action": "recompute_draft", "confirmed_by": "tester"},
        )
        self.assertEqual(recompute_draft.status_code, 200)
        draft_id = recompute_draft.json()["data"]["recompute_result"]["draft_id"]
        self.assertTrue(draft_id)

        scene_dependency_after = self.client.get(f"/api/v1/chapters/dependency-status?project_id={project_id}&scene_id={scene_id}")
        self.assertEqual(scene_dependency_after.status_code, 200)
        self.assertEqual(scene_dependency_after.json()["data"]["items"], [])

        gate = self.client.post(
            "/api/v1/gates/reviews",
            json={"project_id": project_id, "draft_id": draft_id, "gate_names": ["schema_gate", "canon_gate", "narrative_gate", "style_gate"]},
        )
        self.assertEqual(gate.status_code, 200)
        proposal = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id, "rationale": "dependency-recompute", "auto_create_changeset": True},
        )
        self.assertEqual(proposal.status_code, 200)
        changeset_id = str((proposal.json()["data"].get("changeset") or {}).get("id") or "")
        self.assertTrue(changeset_id)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/changesets/{changeset_id}/apply", json={}).status_code, 200)
        self.assertEqual(
            self.client.post("/api/v1/chapters/drafts/publish", json={"project_id": project_id, "draft_id": draft_id, "published_by": "tester"}).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
