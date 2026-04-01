import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM
from app.db.session import SessionLocal
from app.main import create_app
from app.services.narrative_rewrite_service import narrative_rewrite_service


class OverExplainedRewriteChangeSetTest(unittest.TestCase):
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
        project_resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"reveal-rewrite-{uuid4().hex[:8]}", "premise": "test over explained reveal", "genre_id": "default"},
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]
        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "rewrite-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        return project_id

    def _prepare_draft(self, project_id: str, chapter_no: int = 1) -> str:
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": chapter_no, "current_volume_goal": "推进剧情"})
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        bp = self.client.post("/api/v1/chapters/blueprints/generate", json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1})
        self.assertEqual(bp.status_code, 200)
        blueprint_id = bp.json()["data"][0]["id"]
        self.assertEqual(self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id}).status_code, 200)
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(draft.status_code, 200)
        return draft.json()["data"]["id"]

    def test_detect_over_explained_reveal_issue(self):
        issues = narrative_rewrite_service.detect_over_explained_reveal(
            "其实这场灾变就是王朝实验失控，原来真相是议会故意放任，也就是说所有牺牲都意味着一场清洗。"
        )
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, "over_explained_reveal")

    def test_proposal_contains_structured_rewrite_suggestion(self):
        project_id = self._create_project()
        draft_id = self._prepare_draft(project_id)
        with SessionLocal() as db:
            draft = db.get(ChapterDraftORM, draft_id)
            self.assertIsNotNone(draft)
            draft.content = (
                "其实这场灾变就是王朝实验失控，原来真相是议会故意放任，"
                "也就是说主角家族不是受害者而是执行者，这意味着他必须背负全部罪名。"
            )
            db.commit()

        gate = self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id})
        self.assertEqual(gate.status_code, 200)
        narrative = [item for item in gate.json()["data"]["results"] if item["gate_name"] == "narrative_gate"][0]
        reveal_issues = [item for item in narrative["issues"] if item.get("category") == "over_explained_reveal"]
        self.assertGreaterEqual(len(reveal_issues), 1)

        proposal = self.client.post(f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate", json={"project_id": project_id})
        self.assertEqual(proposal.status_code, 200)
        payload = proposal.json()["data"]
        rewrite_suggestions = payload.get("rewrite_suggestions") or []
        self.assertGreaterEqual(len(rewrite_suggestions), 1)
        first = rewrite_suggestions[0]
        self.assertEqual(first.get("rewrite_issue_type"), "over_explained_reveal")
        self.assertTrue(first.get("rewrite_goal"))
        self.assertTrue(first.get("rewrite_strategy"))
        self.assertTrue(first.get("expected_effect"))

    def test_plain_paragraph_should_not_trigger_false_positive(self):
        issues = narrative_rewrite_service.detect_over_explained_reveal(
            "林远推开旧门，灰尘落在肩上。他停了两秒，听见楼梯尽头有脚步声。"
        )
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()
