import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ChapterBlueprintORM, ChapterDraftORM, ChapterGoalORM, PublishedChapterORM
from app.db.session import SessionLocal
from app.domain.enums import GateName
from app.main import create_app
from app.schemas.gate import GateReviewResult
from app.services.gate_service import gate_service
from app.services.workflow_service import workflow_service


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


class WorkflowSequenceCycleClosureTest(unittest.TestCase):
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
            json={
                "project_name": f"sequence-cycle-{uuid4().hex[:8]}",
                "premise": "验证 sequence 复用 chapter cycle 闭环",
                "genre_id": "default",
            },
        )
        self.assertEqual(project.status_code, 200)
        project_id = project.json()["data"]["id"]

        init = self.client.post(
            "/api/v1/canon/snapshots/init",
            json={
                "project_id": project_id,
                "title": "sequence-cycle-init",
                "initial_rules": [{"rule_name": "基础规则", "description": "约束", "severity": "hard"}],
                "initial_characters": [{"character_name": "主角", "role_tags": ["lead"], "current_state": {"mood": "calm"}}],
            },
        )
        self.assertEqual(init.status_code, 200)
        return project_id

    def _execute_sequence(self, project_id: str, **overrides):
        payload = {
            "project_id": project_id,
            "start_chapter_no": 1,
            "chapter_count": 2,
            "current_volume_goal": "连续两章推进主线并形成承接",
            "testing_auto_select_first_blueprint": True,
            "auto_propose_changeset": True,
            "auto_approve_changeset": True,
            "approved_by": "tester",
            "auto_apply_changeset": True,
            "approved_by": "tester",
        }
        payload.update(overrides)
        resp = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=payload)
        self.assertEqual(resp.status_code, 200)
        return resp.json()["data"]

    def test_sequence_should_stop_at_manual_publish_when_auto_publish_disabled(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=False)

        self.assertEqual(data["stage_status"], "attention_required")
        self.assertEqual(data["next_action"], "publish")
        self.assertEqual(data["stopped_at_chapter_no"], 1)
        self.assertEqual(data["processed_chapter_count"], 1)
        self.assertEqual(len(data["chapter_results"]), 1)
        self.assertEqual(data["chapter_results"][0]["stage_status"], "attention_required")
        self.assertEqual(data["chapter_results"][0]["next_action"], "publish")

    def test_sequence_should_continue_to_next_chapter_after_successful_publish(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester")

        self.assertEqual(data["stage_status"], "completed")
        self.assertEqual(data["completed_chapter_count"], 2)
        self.assertEqual(len(data["chapter_results"]), 2)
        ch1 = data["chapter_results"][0]
        ch2 = data["chapter_results"][1]
        self.assertEqual(ch1["stage_status"], "completed")
        self.assertEqual(ch2["stage_status"], "completed")
        self.assertTrue(ch1["published_chapter_id"])
        self.assertEqual(ch2["chapter_result"]["continuity_pack"]["source_published_chapter_id"], ch1["published_chapter_id"])
        self.assertEqual(ch2["chapter_result"]["continuity_pack"]["previous_chapter_summary"], ch1["latest_summary"])

    def test_sequence_should_surface_next_action_and_stopped_chapter(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=False)

        self.assertEqual(data["batch_status"], "attention_required")
        self.assertEqual(data["next_action"], "publish")
        self.assertEqual(data["stopped_at_chapter_no"], 1)
        self.assertEqual(data["attention_chapter_count"], 1)
        self.assertIn("停止", data["summary_message"])

    def test_sequence_should_include_publish_and_post_publish_outputs(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester", auto_run_post_publish_updates=True)

        chapter = data["chapter_results"][0]
        self.assertTrue(chapter["published_chapter_id"])
        self.assertTrue(chapter["latest_summary"])
        self.assertTrue(chapter["latest_next_chapter_seed"])
        self.assertIn(chapter["derived_update_status"], {"completed", "completed_with_warnings"})

    def test_sequence_should_not_double_run_post_publish_updates(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, auto_publish=True, published_by="tester", auto_run_post_publish_updates=True)

        first = data["chapter_results"][0]["chapter_result"]
        derived = first["derived_update_result"] or first["publish_result"]["derived_update_result"]
        task_names = [task["task_name"] for task in derived["tasks"]]
        self.assertEqual(len(task_names), len(set(task_names)))

        with SessionLocal() as db:
            published = db.get(PublishedChapterORM, data["chapter_results"][0]["published_chapter_id"])
            self.assertIsNotNone(published)
            payload = dict(published.publish_metadata or {})
            stored = list(payload.get("derived_update_tasks") or [])
            stored_names = [item.get("task_name") for item in stored if isinstance(item, dict)]
            self.assertEqual(len(stored_names), len(set(stored_names)))

    def test_sequence_report_should_surface_revision_manual_review_decisions(self):
        project_id = self._create_project_and_snapshot()

        def always_fail(db, request):
            return _base_pass_results(project_id, request.draft_id) + [
                _gate_result(project_id, request.draft_id, GateName.NARRATIVE, passed=False, severity="S1", category="narrative_alignment", message="持续失败")
            ]

        with patch.object(gate_service, "run_reviews", side_effect=always_fail):
            data = self._execute_sequence(
                project_id,
                auto_publish=False,
                auto_revise_on_gate_failure=True,
                max_revision_rounds=1,
            )
        report_resp = self.client.get(f"/api/v1/workflows/chapter-sequence/reports/{data['run']['id']}")
        self.assertEqual(report_resp.status_code, 200)
        report = report_resp.json()["data"]
        chapter_report = report["chapter_reports"][0]
        self.assertEqual(chapter_report["revision_policy_decision"], "stop_for_manual_review")
        self.assertTrue(chapter_report["revision_policy_reason"])
        self.assertEqual(chapter_report["revision_attempt_count"], 1)
        self.assertIn("revision_policy_reason", report["attention_items"][0]["details"])

    def test_sequence_report_should_surface_publish_delta_decision_and_baseline(self):
        project_id = self._create_project_and_snapshot()
        data = self._execute_sequence(project_id, chapter_count=1, auto_publish=True, published_by="tester")
        report_resp = self.client.get(f"/api/v1/workflows/chapter-sequence/reports/{data['run']['id']}")
        self.assertEqual(report_resp.status_code, 200)
        report = report_resp.json()["data"]
        chapter_report = report["chapter_reports"][0]
        self.assertTrue(chapter_report["quality_delta_decision"])
        self.assertTrue(chapter_report["delta_baseline_source"])
        self.assertIn("quality_delta_non_pass_count", report["summary"])

    def _execute_sequence_with_gate_fail_once_on_ch2(self, project_id: str, **overrides):
        failed_once = {"ch2": False}

        original_evaluate = gate_service._evaluate_gate

        def evaluate_fail_once_on_ch2(db, gate_name, draft, blueprint, latest_snapshot, genre_context, run_id, trace_id):
            result = original_evaluate(
                db=db,
                gate_name=gate_name,
                draft=draft,
                blueprint=blueprint,
                latest_snapshot=latest_snapshot,
                genre_context=genre_context,
                run_id=run_id,
                trace_id=trace_id,
            )
            chapter_no = 0
            if draft is not None:
                blueprint = db.get(ChapterBlueprintORM, draft.blueprint_id)
                if blueprint is not None:
                    goal = db.get(ChapterGoalORM, blueprint.chapter_goal_id)
                    chapter_no = goal.chapter_no if goal is not None else 0
            if gate_name == GateName.NARRATIVE.value and chapter_no == 2 and not failed_once["ch2"]:
                failed_once["ch2"] = True
                return _gate_result(
                    project_id,
                    draft.id,
                    GateName.NARRATIVE,
                    passed=False,
                    severity="S1",
                    category="narrative_alignment",
                    message="第二章首次执行触发人工处理",
                )
            return result

        payload = {
            "project_id": project_id,
            "start_chapter_no": 1,
            "chapter_count": 3,
            "current_volume_goal": "连续三章推进主线并保留恢复能力",
            "testing_auto_select_first_blueprint": True,
            "auto_propose_changeset": True,
            "auto_approve_changeset": True,
            "approved_by": "tester",
            "auto_apply_changeset": True,
            "auto_publish": True,
            "published_by": "tester",
            "review_gate_names": ["schema_gate", "canon_gate", "narrative_gate"],
        }
        payload.update(overrides)
        with patch.object(gate_service, "_evaluate_gate", side_effect=evaluate_fail_once_on_ch2):
            first = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=payload)
            self.assertEqual(first.status_code, 200)
            return payload, first.json()["data"]

    def test_sequence_should_resume_from_stopped_chapter_without_rerunning_completed_chapters(self):
        project_id = self._create_project_and_snapshot()
        payload, first = self._execute_sequence_with_gate_fail_once_on_ch2(project_id)
        self.assertEqual(first["stage_status"], "attention_required")
        self.assertEqual(first["stopped_at_chapter_no"], 2)
        run_id = first["run"]["id"]

        continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "已人工处理第二章"},
        )
        self.assertEqual(continue_resp.status_code, 200)

        dispatched_chapters: list[int] = []
        original_execute = workflow_service.execute_chapter_cycle

        def capture_execute(db, request):
            chapter_no = request.chapter_no
            if chapter_no is None and request.chapter_goal_id:
                goal = db.get(ChapterGoalORM, request.chapter_goal_id)
                chapter_no = goal.chapter_no if goal else None
            if chapter_no is not None:
                dispatched_chapters.append(chapter_no)
            return original_execute(db=db, request=request)

        with patch.object(workflow_service, "execute_chapter_cycle", side_effect=capture_execute):
            resume_payload = dict(payload)
            resume_payload["workflow_run_id"] = run_id
            resumed = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=resume_payload)
        self.assertEqual(resumed.status_code, 200)
        resumed_data = resumed.json()["data"]
        self.assertEqual(resumed_data["run"]["id"], run_id)
        self.assertNotIn(1, dispatched_chapters)
        self.assertIn(2, dispatched_chapters)
        self.assertEqual(resumed_data["stage_status"], "completed")

    def test_sequence_should_skip_completed_chapters_recorded_in_chapter_results(self):
        project_id = self._create_project_and_snapshot()
        payload, first = self._execute_sequence_with_gate_fail_once_on_ch2(project_id)
        run_id = first["run"]["id"]

        continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "继续序列"},
        )
        self.assertEqual(continue_resp.status_code, 200)

        chapter_calls: list[int] = []
        original_execute = workflow_service.execute_chapter_cycle

        def record_calls(db, request):
            if request.chapter_no is not None:
                chapter_calls.append(request.chapter_no)
            return original_execute(db=db, request=request)

        with patch.object(workflow_service, "execute_chapter_cycle", side_effect=record_calls):
            resume_payload = dict(payload)
            resume_payload["workflow_run_id"] = run_id
            resume_resp = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=resume_payload)
        self.assertEqual(resume_resp.status_code, 200)
        self.assertTrue(all(ch != 1 for ch in chapter_calls))

    def test_sequence_batch_report_should_remain_clean_after_resume(self):
        project_id = self._create_project_and_snapshot()
        payload, first = self._execute_sequence_with_gate_fail_once_on_ch2(project_id)
        run_id = first["run"]["id"]

        continue_resp = self.client.post(
            "/api/v1/workflows/runs/manual-continue",
            json={"workflow_run_id": run_id, "continued_by": "tester", "reason": "继续完成序列"},
        )
        self.assertEqual(continue_resp.status_code, 200)

        resume_payload = dict(payload)
        resume_payload["workflow_run_id"] = run_id
        resume_resp = self.client.post("/api/v1/workflows/chapter-sequence/execute", json=resume_payload)
        self.assertEqual(resume_resp.status_code, 200)

        report_resp = self.client.get(f"/api/v1/workflows/chapter-sequence/reports/{run_id}")
        self.assertEqual(report_resp.status_code, 200)
        report = report_resp.json()["data"]
        chapter_nos = [item["chapter_no"] for item in report["chapter_reports"]]
        self.assertEqual(len(chapter_nos), len(set(chapter_nos)))
        self.assertEqual(report["summary"]["processed_chapter_count"], 3)
        self.assertEqual(report["summary"]["completed_chapter_count"], 3)
        self.assertEqual(report["summary"]["attention_chapter_count"], 0)
        self.assertEqual(report["summary"]["failed_chapter_count"], 0)


if __name__ == "__main__":
    unittest.main()
