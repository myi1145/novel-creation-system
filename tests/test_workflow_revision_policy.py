import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.enums import GateName
from app.main import create_app
from app.schemas.gate import GateReviewResult
from app.services.gate_service import gate_service
from app.services.workflow_revision_policy import RevisionPolicyInput, workflow_revision_policy_service


def _gate_result(project_id: str, draft_id: str, gate_name: GateName, *, passed: bool, severity: str, category: str) -> GateReviewResult:
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
            else [{"severity": severity, "category": category, "message": category, "summary": category, "suggestion": "revise", "metadata": {}}]
        ),
    )


def _base_pass(project_id: str, draft_id: str) -> list[GateReviewResult]:
    return [
        _gate_result(project_id, draft_id, GateName.SCHEMA, passed=True, severity="S0", category="pass"),
        _gate_result(project_id, draft_id, GateName.CANON, passed=True, severity="S0", category="pass"),
    ]


class WorkflowRevisionPolicyTest(unittest.TestCase):
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

    def _prepare(self) -> tuple[str, str, str]:
        project = self.client.post("/api/v1/projects", json={"project_name": f"policy-{uuid4().hex[:8]}", "premise": "policy", "genre_id": "default"})
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "policy-init",
                "initial_rules": [{"rule_name": "r", "description": "d", "severity": "hard"}],
                "initial_characters": [{"character_name": "c", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        goal = self.client.post("/api/v1/chapters/goals", json={"project_id": project_id, "chapter_no": 1, "current_volume_goal": "goal"})
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        bp = self.client.post("/api/v1/chapters/blueprints/generate", json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1})
        self.assertEqual(bp.status_code, 200)
        bp_id = bp.json()["data"][0]["id"]
        self.assertEqual(self.client.post("/api/v1/chapters/blueprints/select", json={"project_id": project_id, "blueprint_id": bp_id, "selected_by": "tester"}).status_code, 200)
        return project_id, goal_id, bp_id

    def _create_project_and_snapshot(self) -> str:
        project = self.client.post("/api/v1/projects", json={"project_name": f"policy-{uuid4().hex[:8]}", "premise": "policy", "genre_id": "default"})
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "policy-init",
                "initial_rules": [{"rule_name": "r", "description": "d", "severity": "hard"}],
                "initial_characters": [{"character_name": "c", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        return project_id

    def test_policy_should_continue_pipeline_when_improvement_detected(self):
        decision = workflow_revision_policy_service.evaluate(
            RevisionPolicyInput(
                gate_failures_before_revision=2,
                gate_failures_after_revision=0,
                highest_severity_before_revision="S2",
                highest_severity_after_revision="S0",
                improved_issue_types=["style_issue"],
                revision_attempt_count=1,
                max_auto_revision_rounds=2,
            )
        )
        self.assertEqual(decision.decision, "continue_pipeline")
        self.assertTrue(decision.continue_pipeline)
        self.assertTrue(decision.improvement_detected)

    def test_policy_should_stop_for_manual_review_when_no_improvement(self):
        decision = workflow_revision_policy_service.evaluate(
            RevisionPolicyInput(
                gate_failures_before_revision=1,
                gate_failures_after_revision=1,
                highest_severity_before_revision="S1",
                highest_severity_after_revision="S1",
                improved_issue_types=[],
                revision_attempt_count=1,
                max_auto_revision_rounds=3,
                no_improvement_reason="no_improvement_detected",
            )
        )
        self.assertEqual(decision.decision, "stop_for_manual_review")
        self.assertTrue(decision.require_manual_review)

    def test_policy_should_stop_when_max_revision_rounds_reached(self):
        decision = workflow_revision_policy_service.evaluate(
            RevisionPolicyInput(
                gate_failures_before_revision=2,
                gate_failures_after_revision=1,
                highest_severity_before_revision="S2",
                highest_severity_after_revision="S1",
                improved_issue_types=["voice_flat"],
                revision_attempt_count=2,
                max_auto_revision_rounds=2,
            )
        )
        self.assertEqual(decision.decision, "stop_for_manual_review")
        self.assertEqual(decision.reason, "max_revision_rounds_reached")
        self.assertTrue(decision.max_revision_reached)

    def test_cycle_should_use_revision_policy_result_to_stop_or_continue(self):
        project_id, goal_id, bp_id = self._prepare()
        state = {"n": 0}

        def no_improvement(db, request):
            state["n"] += 1
            return _base_pass(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=no_improvement):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={"project_id": project_id, "chapter_goal_id": goal_id, "selected_blueprint_id": bp_id, "auto_revise_on_gate_failure": True, "max_revision_rounds": 2},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "review_revised_draft")
        self.assertEqual(data["run"]["run_metadata"].get("revision_policy_decision"), "stop_for_manual_review")

    def test_sequence_should_surface_policy_driven_stop_from_cycle(self):
        project_id = self._create_project_and_snapshot()

        def no_improvement(db, request):
            return _base_pass(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=no_improvement):
            resp = self.client.post(
                "/api/v1/workflows/chapter-sequence/execute",
                json={
                    "project_id": project_id,
                    "start_chapter_no": 1,
                    "chapter_count": 2,
                    "current_volume_goal": "goal",
                    "testing_auto_select_first_blueprint": True,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                    "auto_propose_changeset": False,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["batch_status"], "attention_required")
        self.assertEqual(data["stopped_at_chapter_no"], 1)
        self.assertEqual(data["next_action"], "review_revised_draft")


if __name__ == "__main__":
    unittest.main()
