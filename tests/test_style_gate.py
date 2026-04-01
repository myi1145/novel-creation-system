import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM
from app.db.session import SessionLocal
from app.main import create_app
from app.services.style_gate_service import StyleGateContext, style_gate_service


class StyleGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        cls._orig_enable = settings.enable_style_gate
        cls._orig_strict = settings.style_gate_strict
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True
        settings.enable_style_gate = True
        settings.style_gate_strict = False

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback
        settings.enable_style_gate = cls._orig_enable
        settings.style_gate_strict = cls._orig_strict

    def test_style_drift_and_register_shift_detection(self):
        report = style_gate_service.evaluate(
            StyleGateContext(
                chapter_no=2,
                target_genre="default",
                draft_text="因此我们必须立即封锁现场，哈哈哈这波真是离谱。",
                previous_summary="",
                genre_style={"tone": "冷峻克制"},
            )
        )
        issue_types = {item.issue_type for item in report.issues}
        self.assertIn("style_drift", issue_types)
        self.assertIn("register_shift", issue_types)

    def test_genre_tone_mismatch_and_terminology_inconsistency(self):
        report = style_gate_service.evaluate(
            StyleGateContext(
                chapter_no=2,
                target_genre="mystery",
                draft_text="他在停尸间里讲段子哈哈，顺手用芯片激活法阵并重启服务器。",
                previous_summary="",
                genre_style={"tone": "高压悬疑"},
            )
        )
        issue_types = {item.issue_type for item in report.issues}
        self.assertIn("genre_tone_mismatch", issue_types)
        self.assertIn("terminology_tone_inconsistency", issue_types)

    def test_normal_sample_should_not_over_report(self):
        report = style_gate_service.evaluate(
            StyleGateContext(
                chapter_no=2,
                target_genre="mystery",
                draft_text="走廊尽头的灯忽明忽暗，他压低呼吸，沿着墙角一步步逼近档案室。",
                previous_summary="",
                genre_style={"tone": "冷峻克制"},
            )
        )
        self.assertEqual(report.issue_count, 0)

    def test_style_gate_result_contains_style_report(self):
        project_resp = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"style-gate-{uuid4().hex[:8]}", "premise": "style gate test", "genre_id": "default"},
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]
        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "style-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "推进剧情"})
        self.assertEqual(goal.status_code, 200)
        bp = self.client.post("/api/v1/chapters/blueprints/generate", json={"project_id": project_id, "chapter_goal_id": goal.json()["data"]["id"], "candidate_count": 1})
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
            row.content = "因此你先别急，哈哈哈这也太离谱了。"
            db.commit()
        gate = self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id})
        self.assertEqual(gate.status_code, 200)
        style = [item for item in gate.json()["data"]["results"] if item["gate_name"] == "style_gate"][0]
        self.assertIsInstance(style.get("style_report"), dict)
        categories = {item.get("category") for item in style.get("issues", [])}
        self.assertTrue("style_drift" in categories or "register_shift" in categories)


if __name__ == "__main__":
    unittest.main()
