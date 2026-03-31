from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.business_logging import StepLogScope
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import ImmutableLogORM, ProjectORM, PublishedChapterORM
from app.schemas.chapter import GenerateChapterSummaryRequest
from app.schemas.derived_update import DerivedUpdateBatchResult, DerivedUpdateTask, RunDerivedUpdatesRequest
from app.services.chapter_summary_service import chapter_summary_service
from app.services.workflow_run_service import workflow_run_service

logger = get_logger("workflow")

class DerivedUpdateService:
    def _new_task(self, *, request: RunDerivedUpdatesRequest, published: PublishedChapterORM, run_id: str | None, trace_id: str | None, task_name: str) -> DerivedUpdateTask:
        now = datetime.now(timezone.utc)
        return DerivedUpdateTask(
            task_id=str(uuid4()),
            task_name=task_name,
            project_id=request.project_id,
            published_chapter_id=published.id,
            workflow_run_id=run_id,
            trace_id=trace_id,
            source_ref=published.id,
            status="running",
            summary="派生更新任务执行中",
            details={},
            derived_at=now,
            started_at=now,
        )

    def _task_from_existing(self, payload: dict) -> DerivedUpdateTask:
        return DerivedUpdateTask.model_validate(payload)

    def _persist_result(self, db: Session, published: PublishedChapterORM, result: DerivedUpdateBatchResult) -> None:
        metadata = dict(published.publish_metadata or {})
        metadata["derived_update_status"] = result.status
        metadata["derived_update_generated_at"] = result.generated_at.isoformat()
        metadata["derived_update_tasks"] = [task.model_dump(mode="json") for task in result.tasks]
        metadata["post_publish_stage"] = "completed" if result.status == "completed" else "completed_with_warnings"
        published.publish_metadata = metadata
        db.flush()

    def _execute_task(self, db: Session, request: RunDerivedUpdatesRequest, published: PublishedChapterORM, *, run_id: str | None, trace_id: str | None, task_name: str) -> DerivedUpdateTask:
        task = self._new_task(request=request, published=published, run_id=run_id, trace_id=trace_id, task_name=task_name)
        try:
            if task_name == "refresh_chapter_summary":
                force_regenerate = request.force_refresh_summary or request.force_rerun_tasks
                existing_summary_payload = dict(published.publish_metadata or {}).get("chapter_summary")
                if existing_summary_payload and not force_regenerate:
                    summary = chapter_summary_service.get_published_summary(
                        db=db,
                        project_id=request.project_id,
                        published_chapter_id=published.id,
                        force_regenerate=False,
                    )
                else:
                    summary = chapter_summary_service.generate_for_published(
                        db=db,
                        request=GenerateChapterSummaryRequest(
                            project_id=request.project_id,
                            published_chapter_id=published.id,
                            workflow_run_id=run_id,
                            trace_id=trace_id,
                            force_regenerate=force_regenerate,
                        ),
                        commit=False,
                    )
                task.status = "completed"
                task.summary = "章节摘要已刷新"
                task.details = {
                    "summary": summary.summary,
                    "state_summary": summary.state_summary,
                    "next_chapter_seed": summary.next_chapter_seed,
                    "generated_by": summary.generated_by,
                }
            elif task_name == "refresh_next_chapter_seed":
                current_summary = chapter_summary_service.get_published_summary(
                    db=db,
                    project_id=request.project_id,
                    published_chapter_id=published.id,
                    force_regenerate=False,
                )
                metadata = dict(published.publish_metadata or {})
                metadata["next_chapter_seed"] = current_summary.next_chapter_seed
                metadata["latest_state_summary"] = current_summary.state_summary
                published.publish_metadata = metadata
                db.flush()
                task.status = "completed"
                task.summary = "下一章输入种子已刷新"
                task.details = {
                    "next_chapter_seed": current_summary.next_chapter_seed,
                    "state_summary": current_summary.state_summary,
                }
            elif task_name in {"refresh_vector_index", "refresh_graph_index", "refresh_search_index"}:
                task.status = "skipped"
                task.summary = f"{task_name} 当前为 P0 占位任务"
                task.details = {
                    "mode": "placeholder",
                    "reason": "索引/图谱子系统尚未接入，当前仅保留正式派生任务壳层，不阻断发布闭环。",
                }
            else:
                task.status = "skipped"
                task.summary = f"未识别的派生任务：{task_name}"
                task.details = {"reason": "task_name 未纳入当前 P0 任务白名单"}
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.summary = f"派生更新任务失败：{task_name}"
            task.details = {"error": str(exc)}
        task.completed_at = datetime.now(timezone.utc)
        task.derived_at = task.completed_at
        db.add(
            ImmutableLogORM(
                event_type=("derived_update_task_completed" if task.status in {"completed", "skipped"} else "derived_update_task_failed"),
                project_id=request.project_id,
                workflow_run_id=run_id,
                trace_id=trace_id,
                event_payload={
                    "published_chapter_id": published.id,
                    "task_id": task.task_id,
                    "task_name": task.task_name,
                    "status": task.status,
                    "summary": task.summary,
                },
            )
        )
        return task

    def run_post_publish_updates(self, db: Session, request: RunDerivedUpdatesRequest, *, commit: bool = True) -> DerivedUpdateBatchResult:
        set_log_context(project_id=request.project_id, workflow_run_id=request.workflow_run_id, module="derived_update_service", event="derived_updates.run", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="derived_update_service",
            event="derived_updates.run",
            message_started="开始执行发布后派生更新",
            start_fields={"project_id": request.project_id, "published_chapter_id": request.published_chapter_id, "workflow_run_id": request.workflow_run_id},
        )
        try:
            published = db.get(PublishedChapterORM, request.published_chapter_id)
            if published is None or published.project_id != request.project_id:
                raise NotFoundError("已发布章节不存在")
            project = db.get(ProjectORM, request.project_id)
            if project is None:
                raise NotFoundError("项目不存在")
            run = workflow_run_service.ensure_run(
                db=db,
                project_id=request.project_id,
                workflow_run_id=request.workflow_run_id or published.workflow_run_id,
                trace_id=request.trace_id or published.trace_id,
                workflow_name="chapter_cycle_workflow_v1",
                chapter_no=published.chapter_no,
                source_type="derived_update_task",
                source_ref=published.id,
                current_step="post_publish_updates_running",
            )
            existing_payloads = list(dict(published.publish_metadata or {}).get("derived_update_tasks") or [])
            existing_by_name = {}
            for payload in existing_payloads:
                try:
                    item = self._task_from_existing(payload)
                except Exception:
                    continue
                existing_by_name[item.task_name] = item

            tasks: list[DerivedUpdateTask] = []
            for task_name in request.task_names:
                should_rerun = request.force_rerun_tasks or (request.force_refresh_summary and task_name in {"refresh_chapter_summary", "refresh_next_chapter_seed"})
                existing = existing_by_name.get(task_name)
                if existing is not None and not should_rerun:
                    tasks.append(existing)
                    continue
                tasks.append(self._execute_task(db=db, request=request, published=published, run_id=run.id, trace_id=run.trace_id, task_name=task_name))

            overall_status = "completed_with_warnings" if any(task.status == "failed" for task in tasks) else "completed"
            generated_at = datetime.now(timezone.utc)
            result = DerivedUpdateBatchResult(
                project_id=request.project_id,
                published_chapter_id=published.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                status=overall_status,
                tasks=tasks,
                generated_at=generated_at,
            )
            self._persist_result(db=db, published=published, result=result)
            workflow_run_service.update_progress(
                db=db,
                run=run,
                current_step="post_publish_updates_completed",
                status=run.status,
                extra_metadata={
                    "derived_update_status": overall_status,
                    "derived_update_task_count": len(tasks),
                    "latest_published_chapter_id": published.id,
                },
            )
            db.add(
                ImmutableLogORM(
                    event_type="post_publish_updates_completed",
                    project_id=request.project_id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    event_payload={
                        "published_chapter_id": published.id,
                        "status": overall_status,
                        "task_names": [task.task_name for task in tasks],
                    },
                )
            )
            if commit:
                db.commit()
                db.refresh(published)
            else:
                db.flush()
            scope.success(
                "发布后派生更新完成",
                workflow_run_id=run.id,
                published_chapter_id=published.id,
                summary=f"task_count={len(tasks)}",
                stop_reason=("completed_with_warnings" if overall_status == "completed_with_warnings" else None),
            )
            return result
        except Exception as exc:
            scope.failure("发布后派生更新失败", exc, project_id=request.project_id, published_chapter_id=request.published_chapter_id)
            raise

    def get_post_publish_updates(self, db: Session, *, project_id: str, published_chapter_id: str) -> DerivedUpdateBatchResult | None:
        published = db.get(PublishedChapterORM, published_chapter_id)
        if published is None or published.project_id != project_id:
            raise NotFoundError("已发布章节不存在")
        metadata = dict(published.publish_metadata or {})
        payloads = list(metadata.get("derived_update_tasks") or [])
        if not payloads:
            return None
        tasks = [self._task_from_existing(item) for item in payloads]
        generated_at_raw = metadata.get("derived_update_generated_at")
        generated_at = datetime.fromisoformat(generated_at_raw) if isinstance(generated_at_raw, str) else datetime.now(timezone.utc)
        return DerivedUpdateBatchResult(
            project_id=project_id,
            published_chapter_id=published.id,
            workflow_run_id=published.workflow_run_id,
            trace_id=published.trace_id,
            status=str(metadata.get("derived_update_status") or "completed"),
            tasks=tasks,
            generated_at=generated_at,
        )


derived_update_service = DerivedUpdateService()
