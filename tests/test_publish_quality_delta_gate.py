import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterDraftORM
from app.db.session import SessionLocal
from app.main import create_app
from app.services.quality_delta_service import QualityDeltaContext, quality_delta_service


class PublishQualityDeltaGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        cls._orig_provider = settings.agent_provider
        cls._orig_fallback = settings.agent_fallback_to_mock
        cls._orig_require_delta = settings.publish_require_quality_delta
        cls._orig_similarity_threshold = settings.publish_delta_similarity_threshold
        cls._orig_min_changed_paragraphs = settings.publish_delta_min_changed_paragraphs

        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._orig_provider
        settings.agent_fallback_to_mock = cls._orig_fallback
        settings.publish_require_quality_delta = cls._orig_require_delta
        settings.publish_delta_similarity_threshold = cls._orig_similarity_threshold
        settings.publish_delta_min_changed_paragraphs = cls._orig_min_changed_paragraphs

    def setUp(self):
        settings.publish_require_quality_delta = False
        settings.publish_delta_similarity_threshold = 0.98
        settings.publish_delta_min_changed_paragraphs = 1

    def _create_project_and_snapshot(self) -> str:
        project_resp = self.client.post(
            "/api/v1/projects",
            json={
                "project_name": f"publish-delta-{uuid4().hex[:8]}",
                "premise": "测试 Draft→Published Delta Gate",
                "genre_id": "default",
            },
        )
        self.assertEqual(project_resp.status_code, 200)
        project_id = project_resp.json()["data"]["id"]

        init_resp = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "delta-gate-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init_resp.status_code, 200)
        return project_id

    def _prepare_draft(self, project_id: str) -> dict:
        goal_resp = self.client.post(
            "/api/v1/chapters/goals",
            json={
                "project_id": project_id,
                "chapter_no": 1,
                "current_volume_goal": "第一章推进主线并留下悬念",
            },
        )
        self.assertEqual(goal_resp.status_code, 200)
        goal_id = goal_resp.json()["data"]["id"]

        blueprint_resp = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(blueprint_resp.status_code, 200)
        blueprint_id = blueprint_resp.json()["data"][0]["id"]

        select_resp = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": blueprint_id, "selected_by": "tester"},
        )
        self.assertEqual(select_resp.status_code, 200)

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
        return draft_resp.json()["data"]

    def _complete_changeset_chain(self, project_id: str, draft_id: str) -> None:
        gate_resp = self.client.post("/api/v1/gates/reviews", json={"project_id": project_id, "draft_id": draft_id})
        self.assertEqual(gate_resp.status_code, 200)

        proposal_resp = self.client.post(
            f"/api/v1/chapters/drafts/{draft_id}/changeset-proposals/generate",
            json={"project_id": project_id},
        )
        self.assertEqual(proposal_resp.status_code, 200)
        proposal = proposal_resp.json()["data"]

        changeset_resp = self.client.post(
            "/api/v1/changesets/propose",
            json={
                "project_id": project_id,
                "source_type": "chapter_draft",
                "source_ref": draft_id,
                "rationale": proposal["rationale"],
                "patch_operations": proposal["patch_operations"],
            },
        )
        self.assertEqual(changeset_resp.status_code, 200)
        changeset_id = changeset_resp.json()["data"]["id"]

        approve_resp = self.client.post(f"/api/v1/changesets/{changeset_id}/approve", json={"approved_by": "tester"})
        self.assertEqual(approve_resp.status_code, 200)

        apply_resp = self.client.post(f"/api/v1/changesets/{changeset_id}/apply")
        self.assertEqual(apply_resp.status_code, 200)

    def _revise_draft(self, project_id: str, draft_id: str) -> dict:
        revise_resp = self.client.post(
            "/api/v1/chapters/drafts/revise",
            json={
                "project_id": project_id,
                "draft_id": draft_id,
                "revision_instruction": "最小修订",
                "revised_by": "tester",
            },
        )
        self.assertEqual(revise_resp.status_code, 200)
        return revise_resp.json()["data"]

    def test_delta_report_generation_identical_text(self):
        report = quality_delta_service.evaluate(
            QualityDeltaContext(
                draft_text="第一段。\n\n第二段。",
                candidate_published_text="第一段。\n\n第二段。",
                unresolved_critical_issues_count=1,
            )
        )
        self.assertGreaterEqual(report.similarity_score, 0.99)
        self.assertFalse(report.has_meaningful_delta)
        self.assertIn(report.decision, {"warn", "fail"})

    def test_warn_mode_allows_publish_and_returns_delta_report(self):
        project_id = self._create_project_and_snapshot()
        draft = self._prepare_draft(project_id)
        self._complete_changeset_chain(project_id=project_id, draft_id=draft["id"])

        publish_resp = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft["id"], "published_by": "tester"},
        )
        self.assertEqual(publish_resp.status_code, 200)
        payload = publish_resp.json()["data"]
        delta = payload.get("delta_report")
        self.assertIsInstance(delta, dict)
        self.assertEqual(delta.get("decision"), "pass")
        self.assertTrue(delta.get("has_meaningful_delta"))
        metadata = payload.get("published_chapter", {}).get("publish_metadata") or {}
        self.assertEqual(metadata.get("delta_baseline_source"), "baseline_unavailable")
        self.assertEqual(metadata.get("delta_baseline_ref_id"), "")
        self.assertIn("降级", metadata.get("delta_baseline_reason") or "")

    def test_strict_mode_should_not_be_falsely_blocked_by_self_comparison_when_baseline_missing(self):
        settings.publish_require_quality_delta = True

        project_id = self._create_project_and_snapshot()
        draft = self._prepare_draft(project_id)
        self._complete_changeset_chain(project_id=project_id, draft_id=draft["id"])

        publish_resp = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": draft["id"], "published_by": "tester"},
        )
        self.assertEqual(publish_resp.status_code, 200)
        payload = publish_resp.json()["data"]
        delta = payload.get("delta_report") or {}
        self.assertLess(delta.get("similarity_score", 1.0), 0.98)
        metadata = payload.get("published_chapter", {}).get("publish_metadata") or {}
        self.assertEqual(metadata.get("delta_baseline_source"), "baseline_unavailable")

    def test_delta_should_use_predecessor_draft_as_real_baseline(self):
        project_id = self._create_project_and_snapshot()
        first_draft = self._prepare_draft(project_id)
        revised_draft = self._revise_draft(project_id=project_id, draft_id=first_draft["id"])

        with SessionLocal() as db:
            first_row = db.get(ChapterDraftORM, first_draft["id"])
            revised_row = db.get(ChapterDraftORM, revised_draft["id"])
            self.assertIsNotNone(first_row)
            self.assertIsNotNone(revised_row)
            revised_row.content = first_row.content
            db.commit()

        self._complete_changeset_chain(project_id=project_id, draft_id=revised_draft["id"])
        publish_resp = self.client.post(
            "/api/v1/chapters/drafts/publish",
            json={"project_id": project_id, "draft_id": revised_draft["id"], "published_by": "tester"},
        )
        self.assertEqual(publish_resp.status_code, 200)
        payload = publish_resp.json()["data"]
        delta = payload.get("delta_report") or {}
        self.assertGreaterEqual(delta.get("similarity_score", 0.0), 0.99)
        metadata = payload.get("published_chapter", {}).get("publish_metadata") or {}
        self.assertEqual(metadata.get("delta_baseline_source"), "predecessor_draft")
        self.assertEqual(metadata.get("delta_baseline_ref_id"), first_draft["id"])

    def test_visible_text_changes_should_not_fail_delta_gate(self):
        report = quality_delta_service.evaluate(
            QualityDeltaContext(
                draft_text="林远推开旧档案室的门，尘灰扑面。\n\n他只看见一张泛黄照片。",
                candidate_published_text="林远推开旧档案室的门，尘灰像冷雨一样扑面。\n\n他在照片背面发现“0719”和一行父亲手写警告。",
                unresolved_critical_issues_count=0,
            )
        )
        self.assertTrue(report.has_meaningful_delta)
        self.assertEqual(report.decision, "pass")
        self.assertGreaterEqual(report.changed_paragraph_count, 1)


if __name__ == "__main__":
    unittest.main()
