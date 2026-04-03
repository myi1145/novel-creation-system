import unittest
from uuid import uuid4

from app.core.exceptions import ConflictError
from app.core.config import settings
from app.db.models import ChapterBlueprintORM, ChapterGoalORM, ProjectORM, WorkflowRunORM
from app.db.session import SessionLocal
from app.schemas.workflow import ExecuteChapterCycleRequest
from app.services.workflow_run_service import workflow_run_service
from app.services.workflow_service import workflow_service


class WorkflowRunIntentControlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_provider = settings.agent_provider
        cls._original_fallback = settings.agent_fallback_to_mock
        settings.agent_provider = "mock"
        settings.agent_fallback_to_mock = True

    @classmethod
    def tearDownClass(cls):
        settings.agent_provider = cls._original_provider
        settings.agent_fallback_to_mock = cls._original_fallback

    def _create_project(self, db) -> ProjectORM:
        project = ProjectORM(
            project_name=f"intent-control-{uuid4().hex[:8]}",
            premise="验证 chapter cycle 运行意图收口",
            genre_id="default",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def test_ensure_run_reuses_same_active_run_for_same_intent(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            run1 = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            run2 = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            self.assertEqual(run1.id, run2.id)

    def test_ensure_run_rejects_conflicting_active_run_for_same_chapter(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            with self.assertRaises(ConflictError) as ctx:
                workflow_run_service.ensure_run(
                    db=db,
                    project_id=project.id,
                    workflow_run_id=None,
                    trace_id=None,
                    workflow_name="chapter_cycle_workflow_v1",
                    chapter_no=1,
                    source_type="chapter_cycle",
                    run_metadata={"idempotency_key": f"manual:{project.id}:1:other"},
                )
            self.assertIn("existing_workflow_run_id", str(ctx.exception))

    def test_ensure_run_does_not_create_new_run_when_paused_run_exists(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            run = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            workflow_run_service.pause_run(
                db=db,
                workflow_run_id=run.id,
                paused_by="tester",
                reason="hold",
            )
            reused = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            run_count = (
                db.query(WorkflowRunORM)
                .filter(
                    WorkflowRunORM.project_id == project.id,
                    WorkflowRunORM.workflow_name == "chapter_cycle_workflow_v1",
                    WorkflowRunORM.chapter_no == 1,
                )
                .count()
            )
            self.assertEqual(reused.id, run.id)
            self.assertEqual(reused.status, "paused")
            self.assertEqual(run_count, 1)

    def test_sequence_child_run_is_reused_for_same_chapter_dispatch(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            sequence_run = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_sequence_workflow_v1",
                chapter_no=1,
                source_type="chapter_sequence",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            db.commit()

            payload = ExecuteChapterCycleRequest(
                project_id=project.id,
                chapter_no=1,
                current_volume_goal="第一章建立冲突",
                auto_run_gates=False,
                auto_propose_changeset=False,
                trace_id=sequence_run.trace_id,
            )
            first = workflow_service.execute_chapter_cycle(db=db, request=payload)
            second = workflow_service.execute_chapter_cycle(db=db, request=payload)
            self.assertEqual(first["run"]["id"], second["run"]["id"])

    def test_resolve_cycle_entry_run_context_should_ignore_completed_goal_linked_run(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            run = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            run.status = "completed"
            db.flush()
            goal = ChapterGoalORM(
                project_id=project.id,
                chapter_no=1,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                current_volume_goal="推进主线",
                structure_goal="起承转合",
                conflict_level="medium",
                info_reveal_level="medium",
                required_elements=["冲突"],
                banned_elements=[],
            )
            db.add(goal)
            db.commit()
            db.refresh(goal)
            request = ExecuteChapterCycleRequest(project_id=project.id, chapter_goal_id=goal.id, trace_id="req-trace")
            resolved_run_id, resolved_trace_id = workflow_service._resolve_cycle_entry_run_context(db=db, request=request)
            self.assertIsNone(resolved_run_id)
            self.assertEqual(resolved_trace_id, "req-trace")

    def test_resolve_cycle_entry_run_context_should_ignore_failed_blueprint_linked_run(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            run = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
                run_metadata={"idempotency_key": f"manual:{project.id}:1"},
            )
            run.status = "failed"
            db.flush()
            goal = ChapterGoalORM(
                project_id=project.id,
                chapter_no=1,
                workflow_run_id=None,
                trace_id=None,
                current_volume_goal="推进主线",
                structure_goal="起承转合",
                conflict_level="medium",
                info_reveal_level="medium",
                required_elements=["冲突"],
                banned_elements=[],
            )
            db.add(goal)
            db.flush()
            blueprint = ChapterBlueprintORM(
                project_id=project.id,
                chapter_goal_id=goal.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                title_hint="蓝图",
                summary="摘要",
                advances=["推进"],
                risks=["风险"],
                selected=True,
            )
            db.add(blueprint)
            db.commit()
            db.refresh(blueprint)
            request = ExecuteChapterCycleRequest(project_id=project.id, selected_blueprint_id=blueprint.id, trace_id="req-trace-bp")
            resolved_run_id, resolved_trace_id = workflow_service._resolve_cycle_entry_run_context(db=db, request=request)
            self.assertIsNone(resolved_run_id)
            self.assertEqual(resolved_trace_id, "req-trace-bp")

    def test_resolve_cycle_entry_run_context_should_reuse_paused_run(self):
        with SessionLocal() as db:
            project = self._create_project(db)
            run = workflow_run_service.ensure_run(
                db=db,
                project_id=project.id,
                workflow_run_id=None,
                trace_id=None,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=1,
                source_type="chapter_cycle",
            )
            run.status = "paused"
            db.flush()
            goal = ChapterGoalORM(
                project_id=project.id,
                chapter_no=1,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                current_volume_goal="推进主线",
                structure_goal="起承转合",
                conflict_level="medium",
                info_reveal_level="medium",
                required_elements=["冲突"],
                banned_elements=[],
            )
            db.add(goal)
            db.commit()
            request = ExecuteChapterCycleRequest(project_id=project.id, chapter_goal_id=goal.id)
            resolved_run_id, resolved_trace_id = workflow_service._resolve_cycle_entry_run_context(db=db, request=request)
            self.assertEqual(resolved_run_id, run.id)
            self.assertEqual(resolved_trace_id, run.trace_id)


if __name__ == "__main__":
    unittest.main()
