import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM
from app.db.session import SessionLocal
from app.main import create_app
from app.services.character_voice_service import CharacterVoiceContext, character_voice_service


class CharacterVoiceGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        cls._orig_enable = settings.enable_character_voice_gate
        cls._orig_strict = settings.character_voice_gate_strict
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True
        settings.enable_character_voice_gate = True
        settings.character_voice_gate_strict = False

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback
        settings.enable_character_voice_gate = cls._orig_enable
        settings.character_voice_gate_strict = cls._orig_strict

    def test_detect_four_issue_types(self):
        cards = [
            {"character_name": "林远", "role_tags": ["lead"], "current_state": {"temper": "calm", "strategy": "谨慎低调"}},
            {"character_name": "苏棠", "role_tags": ["ally"], "current_state": {"temper": "calm"}},
        ]
        report = character_voice_service.evaluate(
            CharacterVoiceContext(
                chapter_no=2,
                previous_summary="上一章发生死亡与背叛。",
                character_cards=cards,
                relationship_edges=[],
                draft_text=(
                    "林远说：你们都闭嘴，必须听我说教完这一切。"
                    "林远说：我决定当众公开身份，主动暴露全部计划。"
                    "苏棠哈哈一笑，像没事一样继续吃饭。"
                    "林远说：也就是说这个设定机制证明了真相是既定结论。"
                ),
            )
        )
        issue_types = {item.issue_type for item in report.issues}
        self.assertIn("voice_drift", issue_types)
        self.assertIn("motivation_gap", issue_types)
        self.assertIn("emotion_mismatch", issue_types)
        self.assertIn("authorial_override", issue_types)

    def test_plain_sample_should_not_over_report(self):
        report = character_voice_service.evaluate(
            CharacterVoiceContext(
                chapter_no=2,
                previous_summary="",
                character_cards=[{"character_name": "林远", "role_tags": ["lead"], "current_state": {"temper": "calm"}}],
                relationship_edges=[],
                draft_text="林远推开门，沉默了两秒，然后低声问苏棠是否安全。",
            )
        )
        self.assertEqual(report.issue_count, 0)
        self.assertEqual(report.highest_severity, "S0")

    def test_gate_result_contains_character_voice_report_and_taxonomy(self):
        project_resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"voice-gate-{uuid4().hex[:8]}", "premise": "character voice gate test", "genre_id": "default"},
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]
        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "voice-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [
                    {"character_name": "林远", "role_tags": ["lead"], "current_state": {"temper": "calm", "strategy": "谨慎低调"}},
                    {"character_name": "苏棠", "role_tags": ["ally"], "current_state": {"temper": "calm"}},
                ],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "推进剧情"})
        self.assertEqual(goal.status_code, 200)
        bp = self.client.post("/api/v1/chapters/blueprints/generate", json={"project_id": project_id, "chapter_goal_id": goal.json()['data']['id'], "candidate_count": 1})
        self.assertEqual(bp.status_code, 200)
        blueprint_id = bp.json()["data"][0]["id"]
        self.assertEqual(self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/chapters/scenes/decompose", json={"project_id": project_id, "blueprint_id": blueprint_id}).status_code, 200)
        draft = self.client.post("/api/v1/chapters/drafts/generate", json={"project_id": project_id, "blueprint_id": blueprint_id})
        self.assertEqual(draft.status_code, 200)
        draft_id = draft.json()["data"]["id"]
        with SessionLocal() as db:
            row = db.get(ChapterDraftORM, draft_id)
            self.assertIsNotNone(row)
            row.content = "林远说：你们都闭嘴，必须听我把机制说明白。"
            db.commit()
        gate = self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id})
        self.assertEqual(gate.status_code, 200)
        narrative = [item for item in gate.json()["data"]["results"] if item["gate_name"] == "narrative_gate"][0]
        self.assertIsInstance(narrative.get("character_voice_report"), dict)
        categories = {item.get("category") for item in narrative.get("issues", [])}
        self.assertIn("voice_drift", categories)


if __name__ == "__main__":
    unittest.main()
