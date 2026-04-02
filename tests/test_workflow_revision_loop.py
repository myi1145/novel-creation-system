import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.enums import GateName
from app.main import create_app
from app.schemas.gate import GateReviewResult
from app.services.chapter_service import chapter_service
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


def _base_pass_results(project_id: str, draft_id: str) -> list[GateReviewResult]:
    return [
        _gate_result(project_id, draft_id, GateName.SCHEMA, passed=True, severity="S0", category="pass", message="通过"),
        _gate_result(project_id, draft_id, GateName.CANON, passed=True, severity="S0", category="pass", message="通过"),
    ]


class WorkflowRevisionLoopTest(unittest.TestCase):
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

    def _create_project_and_snapshot(self) -> str:
        project = self.client.post(
            "/api/v1/projects",
            json={"project_name": f"revision-loop-{uuid4().hex[:8]}", "premise": "测试 gate 修订回路", "genre_id": "default"},
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]
        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "revision-loop-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        return project_id

    def _prepare_goal_and_blueprint(self, project_id: str, chapter_no: int = 1) -> tuple[str, str]:
        goal = self.client.post(
            "/api/v1/chapters/goals",
            json={"project_id": project_id, "chapter_no": chapter_no, "current_volume_goal": "推进剧情"},
        )
        self.assertEqual(goal.status_code, 200)
        goal_id = goal.json()["data"]["id"]
        bp = self.client.post(
            "/api/v1/chapters/blueprints/generate",
            json={"project_id": project_id, "chapter_goal_id": goal_id, "candidate_count": 1},
        )
        self.assertEqual(bp.status_code, 200)
        bp_id = bp.json()["data"][0]["id"]
        selected = self.client.post(
            "/api/v1/chapters/blueprints/select",
            json={"project_id": project_id, "blueprint_id": bp_id, "selected_by": "tester"},
        )
        self.assertEqual(selected.status_code, 200)
        return goal_id, bp_id

    def test_cycle_should_auto_revise_when_gate_failure_is_fixable(self):
        project_id = self._create_project_and_snapshot()
        goal_id, bp_id = self._prepare_goal_and_blueprint(project_id)
        call_state = {"calls": 0}

        def fake_run_reviews(db, request):
            call_state["calls"] += 1
            if call_state["calls"] == 1:
                return _base_pass_results(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="叙事偏离")
                ]
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=True, severity="S0", category="pass", message="通过")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=fake_run_reviews):
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
        self.assertEqual(data["next_action"], "generate_changeset_proposal")
        self.assertEqual(data["run"]["run_metadata"].get("auto_revised"), True)
        self.assertEqual(data["run"]["run_metadata"].get("revision_attempt_count"), 1)
        self.assertEqual(data["run"]["run_metadata"].get("gate_failures_before_revision"), 1)
        self.assertEqual(data["run"]["run_metadata"].get("gate_failures_after_revision"), 0)

    def test_cycle_should_stop_when_revise_exhausted_or_still_failing(self):
        project_id = self._create_project_and_snapshot()
        goal_id, bp_id = self._prepare_goal_and_blueprint(project_id)

        def always_fail(db, request):
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="仍未通过")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=always_fail):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_goal_id": goal_id,
                    "selected_blueprint_id": bp_id,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "review_revised_draft")
        self.assertEqual(data["run"]["run_metadata"].get("revision_attempt_count"), 1)
        self.assertGreaterEqual(data["run"]["run_metadata"].get("gate_failures_after_revision") or 0, 1)

    def test_cycle_should_not_auto_revise_hard_blocking_failures(self):
        project_id = self._create_project_and_snapshot()
        goal_id, bp_id = self._prepare_goal_and_blueprint(project_id)

        def schema_fail(db, request):
            return [_gate_result(project_id, request.draft_id, GateName.SCHEMA, passed=False, severity="S3", category="schema_integrity", message="结构缺失")]

        with patch.object(gate_service, "run_reviews", side_effect=schema_fail), patch.object(chapter_service, "revise_draft", wraps=chapter_service.revise_draft) as revise_mock:
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_goal_id": goal_id,
                    "selected_blueprint_id": bp_id,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "revise_draft")
        self.assertEqual(revise_mock.call_count, 0)

    def test_cycle_should_persist_manual_node_when_revision_limit_reached(self):
        project_id = self._create_project_and_snapshot()
        goal_id, bp_id = self._prepare_goal_and_blueprint(project_id)

        def first_round_fail(db, request):
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="需要修订")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=first_round_fail):
            resp = self.client.post(
                "/api/v1/workflows/chapter-cycle/execute",
                json={
                    "project_id": project_id,
                    "chapter_goal_id": goal_id,
                    "selected_blueprint_id": bp_id,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 0,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "review_revision_limit")
        run = data["run"]
        self.assertEqual(run["status"], "attention_required")
        self.assertEqual(run["current_step"], "review_revision_limit_required")
        metadata = run.get("run_metadata") or {}
        self.assertEqual(metadata.get("stop_reason"), "revision_limit_reached")
        self.assertEqual(metadata.get("manual_review_required"), True)
        self.assertEqual(metadata.get("max_revision_rounds"), 0)
        self.assertEqual(metadata.get("revision_attempt_count"), 0)
        self.assertTrue(metadata.get("draft_id"))

    def test_sequence_should_continue_after_successful_revision_of_previous_chapter(self):
        project_id = self._create_project_and_snapshot()
        call_state = {"calls": 0}

        def sequence_reviews(db, request):
            call_state["calls"] += 1
            if call_state["calls"] == 1:
                return _base_pass_results(project_id, request.draft_id) + [
                    _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="首轮失败")
                ]
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=True, severity="S0", category="pass", message="通过")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=sequence_reviews):
            resp = self.client.post(
                "/api/v1/workflows/chapter-sequence/execute",
                json={
                    "project_id": project_id,
                    "start_chapter_no": 1,
                    "chapter_count": 2,
                    "current_volume_goal": "两章推进",
                    "testing_auto_select_first_blueprint": True,
                    "auto_revise_on_gate_failure": True,
                    "max_revision_rounds": 1,
                    "auto_propose_changeset": False,
                    "stop_on_attention": False,
                    "advance_only_on_completed": False,
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["processed_chapter_count"], 2)
        self.assertGreaterEqual(data["revised_chapter_count"], 1)

    def test_sequence_should_stop_when_revision_fails_on_a_chapter(self):
        project_id = self._create_project_and_snapshot()

        def always_fail(db, request):
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="持续失败")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=always_fail):
            resp = self.client.post(
                "/api/v1/workflows/chapter-sequence/execute",
                json={
                    "project_id": project_id,
                    "start_chapter_no": 1,
                    "chapter_count": 2,
                    "current_volume_goal": "两章推进",
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
        self.assertEqual(data["attention_chapter_count"], 1)


if __name__ == "__main__":
    unittest.main()
