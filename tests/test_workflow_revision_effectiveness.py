import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.enums import GateName
from app.main import create_app
from app.schemas.gate import GateReviewResult
from app.services.agent_gateway import AgentInvocationResult, agent_gateway
from app.services.gate_service import gate_service


def _gate_result(project_id: str, draft_id: str, gate_name: GateName, *, passed: bool, severity: str, category: str, message: str) -> GateReviewResult:
    return GateReviewResult(
        project_id=project_id,
        draft_id=draft_id,
        gate_name=gate_name,
        pass_status=("passed" if passed else "failed"),
        passed=passed,
        highest_severity=("S0" if passed else severity),
        recommended_route=("pass" if passed else "rewrite"),
        issues=(
            []
            if passed
            else [
                {
                    "severity": severity,
                    "category": category,
                    "message": message,
                    "summary": message,
                    "suggestion": "修订文本后重试",
                    "metadata": {},
                }
            ]
        ),
    )


def _base_pass(project_id: str, draft_id: str) -> list[GateReviewResult]:
    return [
        _gate_result(project_id, draft_id, GateName.SCHEMA, passed=True, severity="S0", category="pass", message="通过"),
        _gate_result(project_id, draft_id, GateName.CANON, passed=True, severity="S0", category="pass", message="通过"),
    ]


class WorkflowRevisionEffectivenessTest(unittest.TestCase):
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

    def _create_project_and_blueprint(self) -> tuple[str, str, str]:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"revision-effect-{uuid4().hex[:8]}", "premise": "修订效果回归", "genre_id": "default"},
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "revision-effect-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "推进剧情"})
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        bp = self.client.post("/api/v1/chapters/blueprints/generate", json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1})
        self.assertEqual(bp.status_code, 200)
        bp_id = bp.json()["data"][0]["id"]
        selected = self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": bp_id, "selected_by": "tester"})
        self.assertEqual(selected.status_code, 200)
        return project_id, goal_id, bp_id

    def test_revision_should_reduce_or_not_worsen_gate_failures(self):
        project_id, goal_id, bp_id = self._create_project_and_blueprint()
        state = {"n": 0}

        def side_effect(db, request):
            state["n"] += 1
            if state["n"] == 1:
                return _base_pass(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S2", category="style_overwrite", message="风格问题"),
                    _gate_result(project_id, request.draft_id, GateName.STYLE, passed=False, severity="S1", category="voice_flat", message="声音问题"),
                ]
            return _base_pass(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="style_overwrite", message="仅剩轻微问题")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=side_effect):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={"project_id": project_id, "chapter_goal_id": goal_id, "selected_blueprint_id": bp_id, "auto_revise_on_gate_failure": True, "max_revision_rounds": 1},
            )
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()["data"]["run"]["run_metadata"]
        self.assertLessEqual(meta.get("gate_failures_after_revision"), meta.get("gate_failures_before_revision"))
        before = meta.get("highest_severity_before_revision")
        after = meta.get("highest_severity_after_revision")
        self.assertIn(before, {"S1", "S2", "S3"})
        self.assertIn(after, {"S0", "S1", "S2", "S3"})
        rank = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
        self.assertLessEqual(rank[after], rank[before])

    def test_revision_should_improve_targeted_issue_signal_when_possible(self):
        project_id, goal_id, bp_id = self._create_project_and_blueprint()
        state = {"n": 0}

        def side_effect(db, request):
            state["n"] += 1
            if state["n"] == 1:
                return _base_pass(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="over_explained_reveal", message="信息揭露过直")
                ]
            return _base_pass(project_id, request.draft_id)

        with patch.object(gate_service, "run_reviews", side_effect=side_effect):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_goal_id": goal_id,
                    "selected_blueprint_id": bp_id,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                    "auto_propose_changeset": False,
                },
            )
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()["data"]["run"]["run_metadata"]
        self.assertIn("over_explained_reveal", meta.get("revision_target_issue_types") or [])
        self.assertIn("over_explained_reveal", meta.get("improved_issue_types") or [])

    def test_revision_success_should_leave_traceable_before_after_metadata(self):
        project_id, goal_id, bp_id = self._create_project_and_blueprint()
        state = {"n": 0}

        def side_effect(db, request):
            state["n"] += 1
            if state["n"] == 1:
                return _base_pass(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="偏离主线")
                ]
            return _base_pass(project_id, request.draft_id)

        with patch.object(gate_service, "run_reviews", side_effect=side_effect):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={"project_id": project_id, "chapter_goal_id": goal_id, "selected_blueprint_id": bp_id, "auto_revise_on_gate_failure": True, "max_revision_rounds": 1},
            )
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()["data"]["run"]["run_metadata"]
        self.assertEqual(meta.get("auto_revised"), True)
        self.assertEqual(meta.get("revision_attempt_count"), 1)
        self.assertTrue(meta.get("revised_draft_id"))
        self.assertIsNotNone(meta.get("highest_severity_before_revision"))
        self.assertIsNotNone(meta.get("highest_severity_after_revision"))
        self.assertIsInstance(meta.get("revision_target_issue_types"), list)
        self.assertIsInstance(meta.get("improved_issue_types"), list)

    def test_revision_failure_should_surface_no_improvement_or_stop_reason(self):
        project_id, goal_id, bp_id = self._create_project_and_blueprint()

        def always_fail(db, request):
            return _base_pass(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="仍失败")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=always_fail):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={"project_id": project_id, "chapter_goal_id": goal_id, "selected_blueprint_id": bp_id, "auto_revise_on_gate_failure": True, "max_revision_rounds": 1},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "review_revised_draft")
        meta = data["run"]["run_metadata"]
        self.assertEqual(meta.get("no_improvement_reason"), "gate_failures_not_reduced")

    def test_revision_policy_should_stop_when_text_not_changed_even_if_gate_mock_turns_pass(self):
        project_id, goal_id, bp_id = self._create_project_and_blueprint()
        call_state = {"n": 0}

        def review_side_effect(db, request):
            call_state["n"] += 1
            if call_state["n"] == 1:
                return _base_pass(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="首轮失败")
                ]
            return _base_pass(project_id, request.draft_id)

        def same_text_revision(db, context, audit_context):
            return AgentInvocationResult(
                payload={"content": str(context.get("content") or ""), "metadata": {"provider": "mock", "model": settings.agent_model}},
                configured_provider="mock",
                active_provider="mock",
                model=settings.agent_model,
                prompt_template_id=None,
                prompt_template_key="chapter_revise",
                prompt_template_version=1,
                prompt_scope_type="default",
                prompt_scope_key=None,
                prompt_provider_scope="mock",
                fallback_used=False,
                call_status="success",
                latency_ms=1,
                attempt_count=1,
            )

        with (
            patch.object(gate_service, "run_reviews", side_effect=review_side_effect),
            patch.object(agent_gateway, "revise_draft", side_effect=same_text_revision),
        ):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_goal_id": goal_id,
                    "selected_blueprint_id": bp_id,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                    "auto_propose_changeset": False,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "review_revised_draft")
        meta = data["run"]["run_metadata"]
        self.assertEqual(meta.get("revision_policy_decision"), "stop_for_manual_review")
        self.assertEqual(meta.get("revision_policy_reason"), "revision_text_not_changed")
        self.assertEqual(meta.get("revision_text_changed"), False)


if __name__ == "__main__":
    unittest.main()
