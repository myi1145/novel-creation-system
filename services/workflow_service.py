from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models import (
    AgentCallLogORM,
    ChapterBlueprintORM,
    ChapterDraftORM,
    ChapterGoalORM,
    ChapterStateTransitionORM,
    ChangeSetORM,
    GateReviewORM,
    ImmutableLogORM,
    ProjectORM,
    PublishRecordORM,
    PublishedChapterORM,
    SceneCardORM,
    WorkflowRunORM,
)
from app.domain.enums import ChangeSetStatus, GateName
from app.schemas.chapter import (
    ChapterBlueprint,
    ChapterDraft,
    ChapterGoal,
    CreateChapterGoalRequest,
    DecomposeScenesRequest,
    GenerateBlueprintsRequest,
    GenerateDraftRequest,
    PublishDraftRequest,
    ReviseDraftRequest,
    SceneCard,
    SelectBlueprintRequest,
)
from app.schemas.changeset import ChangeSet, ChangeSetProposal, GenerateChangeSetProposalRequest, ProposeChangeSetRequest
from app.schemas.continuity import ResolveContinuityPackRequest
from app.schemas.derived_update import RunDerivedUpdatesRequest
from app.schemas.gate import RunGateReviewRequest, GateReviewResult
from app.schemas.workflow import (
    ChapterSequenceAcceptanceCheck,
    ChapterSequenceAttentionItem,
    ChapterSequenceBatchReport,
    ChapterSequenceChapterReport,
    ChapterSequenceGateStat,
    ChapterSequenceItemResult,
    ExecuteChapterCycleRequest,
    ExecuteChapterCycleResult,
    ExecuteChapterSequenceRequest,
    ExecuteChapterSequenceResult,
    ManualContinueWorkflowRunRequest,
    ManualTakeoverRequest,
    MarkHumanReviewedRequest,
    PauseWorkflowRunRequest,
    ResumeWorkflowRunRequest,
    WorkflowRun,
    WorkflowRunControlResult,
)
from app.services.agent_call_service import agent_call_service
from app.services.agent_gateway import agent_gateway
from app.services.chapter_service import chapter_service
from app.services.continuity_service import continuity_service
from app.services.changeset_service import changeset_service
from app.services.derived_update_service import derived_update_service
from app.services.gate_service import gate_service
from app.services.provider_governance_service import provider_governance_service
from app.services.publish_service import publish_service
from app.services.workflow_run_service import workflow_run_service


class WorkflowStatusResponse(BaseModel):
    workflow_name: str
    status: str
    current_step: str
    project_count: int = 0
    chapter_goal_count: int = 0
    changeset_count: int = 0
    agent_call_count: int = 0


class WorkflowService:
    def _build_recent_issues(self, db: Session, project_id: str | None = None, workflow_run_id: str | None = None, limit: int = 20) -> list[dict]:
        issues: list[dict] = []

        gate_query = db.query(GateReviewORM).filter(GateReviewORM.passed.is_(False))
        if project_id:
            gate_query = gate_query.filter(GateReviewORM.project_id == project_id)
        if workflow_run_id:
            gate_query = gate_query.filter(GateReviewORM.workflow_run_id == workflow_run_id)
        for row in gate_query.order_by(GateReviewORM.created_at.desc()).limit(limit).all():
            issues.append({
                "issue_type": "gate_failure",
                "severity": row.highest_severity or "S2",
                "message": f"{row.gate_name} 未通过，建议路径：{row.recommended_route}",
                "related_id": row.id,
                "related_type": "gate_review",
                "created_at": row.created_at,
                "metadata": {"draft_id": row.draft_id, "gate_name": row.gate_name, "pass_status": row.pass_status},
            })

        call_query = db.query(AgentCallLogORM).filter(AgentCallLogORM.call_status == "error")
        if project_id:
            call_query = call_query.filter(AgentCallLogORM.project_id == project_id)
        if workflow_run_id:
            call_query = call_query.filter(AgentCallLogORM.workflow_run_id == workflow_run_id)
        for row in call_query.order_by(AgentCallLogORM.created_at.desc()).limit(limit).all():
            issues.append({
                "issue_type": "agent_error",
                "severity": "S2" if row.error_type != "timeout" else "S1",
                "message": row.error_message or f"{row.agent_type}.{row.action_name} 调用失败",
                "related_id": row.id,
                "related_type": "agent_call",
                "created_at": row.created_at,
                "metadata": {"agent_type": row.agent_type, "action_name": row.action_name, "error_type": row.error_type},
            })

        publish_query = db.query(PublishRecordORM).filter(PublishRecordORM.publish_status != "published")
        if project_id:
            publish_query = publish_query.filter(PublishRecordORM.project_id == project_id)
        if workflow_run_id:
            publish_query = publish_query.filter(PublishRecordORM.workflow_run_id == workflow_run_id)
        for row in publish_query.order_by(PublishRecordORM.created_at.desc()).limit(limit).all():
            issues.append({
                "issue_type": "publish_issue",
                "severity": "S2",
                "message": f"发布记录状态为 {row.publish_status}",
                "related_id": row.id,
                "related_type": "publish_record",
                "created_at": row.created_at,
                "metadata": {"published_chapter_id": row.published_chapter_id, "snapshot_id": row.snapshot_id},
            })

        state_query = db.query(WorkflowRunORM).filter(WorkflowRunORM.status.in_(["failed", "attention_required", "paused", "manual_review"]))
        if project_id:
            state_query = state_query.filter(WorkflowRunORM.project_id == project_id)
        if workflow_run_id:
            state_query = state_query.filter(WorkflowRunORM.id == workflow_run_id)
        for row in state_query.order_by(WorkflowRunORM.updated_at.desc()).limit(limit).all():
            issues.append({
                "issue_type": "workflow_attention",
                "severity": "S1" if row.status in {"attention_required", "manual_review", "paused"} else "S2",
                "message": f"工作流状态为 {row.status}，当前步骤 {row.current_step}",
                "related_id": row.id,
                "related_type": "workflow_run",
                "created_at": row.updated_at,
                "metadata": {"current_step": row.current_step, "run_metadata": row.run_metadata or {}},
            })

        issues.sort(key=lambda item: item.get("created_at") or datetime.now(timezone.utc), reverse=True)
        return issues[:limit]



    def _log_sequence_event(self, db: Session, run: WorkflowRunORM, *, event_type: str, payload: dict) -> None:
        db.add(
            ImmutableLogORM(
                event_type=event_type,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                project_id=run.project_id,
                event_payload=payload,
            )
        )

    def _build_sequence_item(self, result: ExecuteChapterCycleResult) -> ChapterSequenceItemResult:
        published_chapter_id = None
        if result.publish_result is not None:
            published_chapter_id = result.publish_result.published_chapter.id
        return ChapterSequenceItemResult(
            chapter_no=result.goal.chapter_no if result.goal else (result.run.chapter_no or 0),
            workflow_run_id=result.run.id,
            trace_id=result.run.trace_id,
            stage_status=result.stage_status,
            next_action=result.next_action,
            chapter_goal_id=result.goal.id if result.goal else None,
            selected_blueprint_id=result.selected_blueprint.id if result.selected_blueprint else None,
            draft_id=result.draft.id if result.draft else None,
            changeset_id=result.changeset.id if result.changeset else None,
            published_chapter_id=published_chapter_id,
            chapter_summary=result.chapter_summary,
            chapter_result=result,
        )

    def _append_sequence_result(self, db: Session, run: WorkflowRunORM, item: ChapterSequenceItemResult) -> None:
        metadata = dict(run.run_metadata or {})
        results = list(metadata.get("chapter_results") or [])
        summary = {
            "chapter_no": item.chapter_no,
            "workflow_run_id": item.workflow_run_id,
            "trace_id": item.trace_id,
            "stage_status": item.stage_status,
            "next_action": item.next_action,
            "chapter_goal_id": item.chapter_goal_id,
            "selected_blueprint_id": item.selected_blueprint_id,
            "draft_id": item.draft_id,
            "changeset_id": item.changeset_id,
            "published_chapter_id": item.published_chapter_id,
        }
        replaced = False
        for idx, existing in enumerate(results):
            if existing.get("chapter_no") == item.chapter_no:
                results[idx] = summary
                replaced = True
                break
        if not replaced:
            results.append(summary)
        results.sort(key=lambda value: value.get("chapter_no") or 0)
        metadata["chapter_results"] = results[-50:]
        metadata["processed_chapter_count"] = len(results)
        metadata["completed_chapter_count"] = sum(1 for value in results if value.get("stage_status") == "completed")
        metadata["attention_chapter_count"] = sum(1 for value in results if value.get("stage_status") == "attention_required")
        metadata["failed_chapter_count"] = sum(1 for value in results if value.get("stage_status") == "failed")
        run.run_metadata = metadata
        db.flush()

    def _build_sequence_batch_report(self, db: Session, sequence_run: WorkflowRunORM) -> ChapterSequenceBatchReport:
        if sequence_run.source_type != "chapter_sequence":
            raise ValidationError("指定的 workflow_run 不是 chapter sequence run")

        metadata = dict(sequence_run.run_metadata or {})
        chapter_results_meta = sorted(list(metadata.get("chapter_results") or []), key=lambda item: item.get("chapter_no") or 0)
        child_run_ids = [item.get("workflow_run_id") for item in chapter_results_meta if item.get("workflow_run_id")]

        child_runs = {}
        gate_rows: list[GateReviewORM] = []
        agent_rows: list[AgentCallLogORM] = []
        draft_rows: list[ChapterDraftORM] = []
        changeset_rows: list[ChangeSetORM] = []
        publish_rows: list[PublishRecordORM] = []
        published_rows: list[PublishedChapterORM] = []
        if child_run_ids:
            child_runs = {row.id: row for row in db.query(WorkflowRunORM).filter(WorkflowRunORM.id.in_(child_run_ids)).all()}
            gate_rows = db.query(GateReviewORM).filter(GateReviewORM.workflow_run_id.in_(child_run_ids)).all()
            agent_rows = db.query(AgentCallLogORM).filter(AgentCallLogORM.workflow_run_id.in_(child_run_ids)).all()
            draft_rows = db.query(ChapterDraftORM).filter(ChapterDraftORM.workflow_run_id.in_(child_run_ids)).all()
            changeset_rows = db.query(ChangeSetORM).filter(ChangeSetORM.workflow_run_id.in_(child_run_ids)).all()
            publish_rows = db.query(PublishRecordORM).filter(PublishRecordORM.workflow_run_id.in_(child_run_ids)).all()
            published_rows = db.query(PublishedChapterORM).filter(PublishedChapterORM.workflow_run_id.in_(child_run_ids)).all()

        gate_by_run: dict[str, list[GateReviewORM]] = {}
        gate_severity_counters: dict[str, Counter] = {}
        for row in gate_rows:
            gate_by_run.setdefault(row.workflow_run_id or "", []).append(row)
            severity_counter = gate_severity_counters.setdefault(row.gate_name, Counter())
            severity_counter[row.highest_severity or "S0"] += 1

        agent_by_run: dict[str, list[AgentCallLogORM]] = {}
        for row in agent_rows:
            agent_by_run.setdefault(row.workflow_run_id or "", []).append(row)

        drafts_by_run: dict[str, list[ChapterDraftORM]] = {}
        for row in draft_rows:
            drafts_by_run.setdefault(row.workflow_run_id or "", []).append(row)

        changesets_by_run: dict[str, list[ChangeSetORM]] = {}
        for row in changeset_rows:
            changesets_by_run.setdefault(row.workflow_run_id or "", []).append(row)

        publish_by_run: dict[str, list[PublishRecordORM]] = {}
        for row in publish_rows:
            publish_by_run.setdefault(row.workflow_run_id or "", []).append(row)

        published_by_run: dict[str, list[PublishedChapterORM]] = {}
        published_by_id = {row.id: row for row in published_rows}
        for row in published_rows:
            published_by_run.setdefault(row.workflow_run_id or "", []).append(row)

        chapter_reports: list[ChapterSequenceChapterReport] = []
        attention_items: list[ChapterSequenceAttentionItem] = []
        for item in chapter_results_meta:
            child_run_id = item.get("workflow_run_id")
            child_run = child_runs.get(child_run_id)
            gates = gate_by_run.get(child_run_id or "", [])
            failed_gates = [gate for gate in gates if not gate.passed]
            failed_gate_names = sorted({gate.gate_name for gate in failed_gates})
            agent_calls = agent_by_run.get(child_run_id or "", [])
            failed_agent_calls = [call for call in agent_calls if call.call_status == "error"]
            run_drafts = drafts_by_run.get(child_run_id or "", [])
            revision_numbers = [int((row.draft_metadata or {}).get("revision_no") or 1) for row in run_drafts]
            revision_count = max(revision_numbers) - 1 if revision_numbers else 0
            run_changesets = changesets_by_run.get(child_run_id or "", [])
            run_publish_records = publish_by_run.get(child_run_id or "", [])
            run_published = published_by_run.get(child_run_id or "", [])
            published_row = None
            if item.get("published_chapter_id"):
                published_row = published_by_id.get(item.get("published_chapter_id"))
            if published_row is None and run_published:
                published_row = sorted(run_published, key=lambda row: row.created_at, reverse=True)[0]
            published_metadata = dict((published_row.publish_metadata if published_row is not None else {}) or {})
            continuity_applied = bool(((child_run.run_metadata or {}) if child_run is not None else {}).get("continuity_pack"))
            summary_generated = bool(published_metadata.get("chapter_summary"))
            derived_update_status = published_metadata.get("derived_update_status")
            notes: list[str] = []
            if failed_gate_names:
                notes.append(f"失败 Gate：{', '.join(failed_gate_names)}")
            if failed_agent_calls:
                notes.append(f"Agent 调用失败 {len(failed_agent_calls)} 次")
            if child_run is not None:
                run_metadata = dict(child_run.run_metadata or {})
                if run_metadata.get("attention_reason"):
                    notes.append(run_metadata["attention_reason"])
                if run_metadata.get("failure_reason"):
                    notes.append(run_metadata["failure_reason"])
                if child_run.status in {"manual_review", "paused"}:
                    notes.append(f"工作流当前处于 {child_run.status}")
            if published_row is not None and not summary_generated:
                notes.append("已发布但缺少 chapter_summary")
            if child_run is not None and not continuity_applied:
                notes.append("本章 workflow metadata 中未记录 continuity_pack")

            chapter_no = int(item.get("chapter_no") or (child_run.chapter_no if child_run is not None and child_run.chapter_no is not None else 0))
            report = ChapterSequenceChapterReport(
                chapter_no=chapter_no,
                workflow_run_id=child_run_id or "",
                trace_id=item.get("trace_id") or (child_run.trace_id if child_run is not None else ""),
                run_status=child_run.status if child_run is not None else item.get("stage_status") or "unknown",
                current_step=child_run.current_step if child_run is not None else "unknown",
                stage_status=item.get("stage_status") or (child_run.status if child_run is not None else "unknown"),
                next_action=item.get("next_action"),
                published=published_row is not None,
                published_chapter_id=published_row.id if published_row is not None else item.get("published_chapter_id"),
                gate_review_count=len(gates),
                failed_gate_count=len(failed_gates),
                failed_gate_names=failed_gate_names,
                agent_call_count=len(agent_calls),
                failed_agent_call_count=len(failed_agent_calls),
                revision_count=max(revision_count, 0),
                changeset_count=len(run_changesets),
                published_record_count=len(run_publish_records),
                continuity_applied=continuity_applied,
                summary_generated=summary_generated,
                derived_update_status=derived_update_status,
                notes=notes,
            )
            chapter_reports.append(report)

            if report.stage_status in {"attention_required", "failed"} or report.run_status in {"manual_review", "paused"}:
                severity = "S2" if report.stage_status == "failed" or report.run_status == "failed" else "S1"
                reason = "章节序列已停止，需人工处理当前章节"
                details: dict[str, object] = {
                    "current_step": report.current_step,
                    "failed_gate_names": report.failed_gate_names,
                    "failed_agent_call_count": report.failed_agent_call_count,
                    "notes": report.notes,
                }
                if child_run is not None:
                    run_metadata = dict(child_run.run_metadata or {})
                    reason = run_metadata.get("attention_reason") or run_metadata.get("failure_reason") or reason
                    if report.run_status in {"manual_review", "paused"}:
                        reason = run_metadata.get("manual_takeover_reason") or run_metadata.get("pause_reason") or reason
                attention_items.append(
                    ChapterSequenceAttentionItem(
                        chapter_no=report.chapter_no,
                        severity=severity,
                        reason=reason,
                        next_action=report.next_action,
                        workflow_run_id=report.workflow_run_id,
                        related_type="workflow_run",
                        related_id=report.workflow_run_id,
                        details=details,
                    )
                )

        gate_stats: list[ChapterSequenceGateStat] = []
        gates_grouped: dict[str, list[GateReviewORM]] = {}
        for row in gate_rows:
            gates_grouped.setdefault(row.gate_name, []).append(row)
        for gate_name in sorted(gates_grouped.keys()):
            rows = gates_grouped[gate_name]
            severity_counts = dict(sorted(gate_severity_counters.get(gate_name, Counter()).items()))
            gate_stats.append(
                ChapterSequenceGateStat(
                    gate_name=gate_name,
                    total_reviews=len(rows),
                    passed_reviews=sum(1 for row in rows if row.passed),
                    failed_reviews=sum(1 for row in rows if not row.passed),
                    highest_severity_counts=severity_counts,
                )
            )

        summary = {
            "processed_chapter_count": len(chapter_reports),
            "completed_chapter_count": sum(1 for item in chapter_reports if item.stage_status == "completed"),
            "attention_chapter_count": sum(1 for item in chapter_reports if item.stage_status == "attention_required"),
            "failed_chapter_count": sum(1 for item in chapter_reports if item.stage_status == "failed"),
            "published_chapter_count": sum(1 for item in chapter_reports if item.published),
            "summary_generated_count": sum(1 for item in chapter_reports if item.summary_generated),
            "continuity_applied_count": sum(1 for item in chapter_reports if item.continuity_applied),
            "revision_chapter_count": sum(1 for item in chapter_reports if item.revision_count > 0),
            "total_revision_count": sum(item.revision_count for item in chapter_reports),
            "failed_gate_count": sum(item.failed_gate_count for item in chapter_reports),
            "failed_agent_call_count": sum(item.failed_agent_call_count for item in chapter_reports),
            "manual_or_paused_chapter_count": sum(1 for item in chapter_reports if item.run_status in {"manual_review", "paused"}),
            "derived_updates_ready_count": sum(1 for item in chapter_reports if item.derived_update_status in {"completed", "partial"}),
        }

        acceptance_checks: list[ChapterSequenceAcceptanceCheck] = []
        published_count = summary["published_chapter_count"]
        processed_count = summary["processed_chapter_count"]
        completed_count = summary["completed_chapter_count"]
        continuity_count = summary["continuity_applied_count"]
        summary_count = summary["summary_generated_count"]
        failed_gate_count = summary["failed_gate_count"]
        failed_agent_call_count = summary["failed_agent_call_count"]
        derived_ready_count = summary["derived_updates_ready_count"]

        chapter_completion_status = "pass" if processed_count == completed_count and processed_count > 0 else ("fail" if summary["failed_chapter_count"] > 0 else "warning")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="chapter_completion",
                status=chapter_completion_status,
                message="所有已调度章节都已完成发布" if chapter_completion_status == "pass" else "仍有章节未完成完整主链，当前序列更适合继续联调而非验收",
                metrics={"processed": processed_count, "completed": completed_count, "attention": summary["attention_chapter_count"], "failed": summary["failed_chapter_count"]},
            )
        )
        continuity_status = "pass" if continuity_count == processed_count else ("warning" if continuity_count >= max(processed_count - 1, 0) else "fail")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="continuity_coverage",
                status=continuity_status,
                message="每章都记录了 continuity pack" if continuity_status == "pass" else "存在章节未写入 continuity pack，需要检查连续上下文解析链路",
                metrics={"processed": processed_count, "continuity_applied": continuity_count},
            )
        )
        summary_status = "pass" if published_count == summary_count else ("warning" if summary_count > 0 else "fail")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="publish_summary_coverage",
                status=summary_status,
                message="所有已发布章节都生成了 chapter_summary" if summary_status == "pass" else "部分已发布章节缺少 chapter_summary，后续 continuity 质量会受影响",
                metrics={"published": published_count, "summary_generated": summary_count},
            )
        )
        gate_health_status = "pass" if failed_gate_count == 0 else ("warning" if summary["failed_chapter_count"] == 0 else "fail")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="gate_health",
                status=gate_health_status,
                message="本批次 Gate 审查没有失败记录" if gate_health_status == "pass" else "本批次存在 Gate 失败，需要聚焦失败 Gate 分布和修订回路",
                metrics={"failed_gate_count": failed_gate_count, "gate_stats": [item.model_dump(mode="json") for item in gate_stats]},
            )
        )
        agent_health_status = "pass" if failed_agent_call_count == 0 else ("warning" if failed_agent_call_count <= max(processed_count, 1) else "fail")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="agent_call_health",
                status=agent_health_status,
                message="本批次 Agent 调用未出现 error" if agent_health_status == "pass" else "本批次存在 Agent error，需要检查 provider fallback / prompt / timeout",
                metrics={"failed_agent_call_count": failed_agent_call_count, "processed_chapter_count": processed_count},
            )
        )
        derived_status = "pass" if derived_ready_count == published_count else ("warning" if derived_ready_count > 0 else "fail")
        acceptance_checks.append(
            ChapterSequenceAcceptanceCheck(
                check_name="post_publish_updates",
                status=derived_status,
                message="所有已发布章节都完成了 post-publish derived updates" if derived_status == "pass" else "部分已发布章节的 derived update 未完整完成，需要检查 post-publish 任务壳层",
                metrics={"published": published_count, "derived_updates_ready": derived_ready_count},
            )
        )

        recommendations: list[str] = []
        if summary["attention_chapter_count"]:
            stalled = ", ".join(str(item.chapter_no) for item in chapter_reports if item.stage_status == "attention_required")
            recommendations.append(f"优先处理 attention_required 的章节：{stalled}。建议先完成蓝图选择或人工审阅，再继续 sequence 验证。")
        if summary["failed_chapter_count"]:
            failed = ", ".join(str(item.chapter_no) for item in chapter_reports if item.stage_status == "failed")
            recommendations.append(f"存在失败章节：{failed}。建议先查看这些章节的 workflow run detail 与 immutable logs，再决定是否重跑。")
        narrative_failures = next((item.failed_reviews for item in gate_stats if item.gate_name == GateName.NARRATIVE.value), 0)
        if narrative_failures:
            recommendations.append("Narrative Gate 仍是主要阻塞点之一，建议优先检查 blueprint 与 draft 的叙事目标对齐，以及 revision 指令是否足够具体。")
        if failed_agent_call_count:
            recommendations.append("检测到 Agent 调用错误，建议查看 agent-call stats 和 provider governance 快照，确认是否需要收紧超时或补 provider fallback。")
        if continuity_count < processed_count:
            recommendations.append("存在章节未记录 continuity pack，建议在继续多章样书验证前先排查 continuity resolver 与 workflow metadata 回写。")
        if summary_count < published_count:
            recommendations.append("部分已发布章节缺少 chapter_summary，建议重新执行 post-publish derived updates，避免后续章节缺少稳定 continuity 输入。")
        if not recommendations:
            recommendations.append("本批次 sequence 报告未发现明显阻塞，可进入更长序列的样书联调或扩大到 5~10 章验证。")

        start_chapter_no = chapter_results_meta[0].get("chapter_no") if chapter_results_meta else sequence_run.chapter_no
        end_chapter_no = chapter_results_meta[-1].get("chapter_no") if chapter_results_meta else sequence_run.chapter_no
        return ChapterSequenceBatchReport(
            run=WorkflowRun.model_validate(sequence_run),
            project_id=sequence_run.project_id,
            generated_at=datetime.now(timezone.utc),
            start_chapter_no=start_chapter_no,
            end_chapter_no=end_chapter_no,
            stop_reason=metadata.get("stop_reason") or metadata.get("attention_reason") or metadata.get("failure_reason"),
            summary=summary,
            chapter_reports=chapter_reports,
            gate_stats=gate_stats,
            attention_items=attention_items,
            acceptance_checks=acceptance_checks,
            recommendations=recommendations,
        )

    def get_chapter_sequence_report(self, db: Session, workflow_run_id: str) -> dict:
        sequence_run = db.get(WorkflowRunORM, workflow_run_id)
        if sequence_run is None:
            raise NotFoundError("workflow_run 不存在")
        report = self._build_sequence_batch_report(db=db, sequence_run=sequence_run)
        return report.model_dump(mode="json")

    def get_chapter_pipeline_status(self, db: Session) -> WorkflowStatusResponse:
        return WorkflowStatusResponse(
            workflow_name="chapter_cycle_workflow_v1",
            status="ready",
            current_step="chapter_goal_input",
            project_count=db.query(ProjectORM).count(),
            chapter_goal_count=db.query(ChapterGoalORM).count(),
            changeset_count=db.query(ChangeSetORM).count(),
            agent_call_count=db.query(AgentCallLogORM).count(),
        )

    def get_agent_gateway_status(self) -> dict:
        return agent_gateway.status().__dict__

    def get_agent_governance(self, db: Session) -> dict:
        return agent_gateway.governance_snapshot(db=db)

    def list_agent_calls(self, db: Session, project_id: str | None = None, agent_type: str | None = None, call_status: str | None = None, workflow_run_id: str | None = None, limit: int = 50) -> list[dict]:
        return [item.model_dump(mode="json") for item in agent_call_service.list_logs(db=db, project_id=project_id, agent_type=agent_type, call_status=call_status, workflow_run_id=workflow_run_id, limit=limit)]

    def get_agent_call_stats(self, db: Session, project_id: str | None = None, workflow_run_id: str | None = None) -> dict:
        return agent_call_service.get_stats(db=db, project_id=project_id, workflow_run_id=workflow_run_id).model_dump(mode="json")

    def list_workflow_runs(self, db: Session, project_id: str | None = None, limit: int = 50) -> list[dict]:
        return [item.model_dump(mode="json") for item in workflow_run_service.list_runs(db=db, project_id=project_id, limit=limit)]

    def get_workflow_run_detail(self, db: Session, workflow_run_id: str) -> dict:
        return workflow_run_service.get_run_detail(db=db, workflow_run_id=workflow_run_id).model_dump(mode="json")

    def get_diagnostics_overview(self, db: Session, project_id: str | None = None, workflow_run_id: str | None = None) -> dict:
        counts = {
            "projects": db.query(ProjectORM).count() if project_id is None else db.query(ProjectORM).filter(ProjectORM.id == project_id).count(),
            "chapter_goals": db.query(ChapterGoalORM).filter(ChapterGoalORM.project_id == project_id).count() if project_id else db.query(ChapterGoalORM).count(),
            "workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.project_id == project_id).count() if project_id else db.query(WorkflowRunORM).count(),
            "running_workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.status == "running", *( [WorkflowRunORM.project_id == project_id] if project_id else [])).count(),
            "paused_workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.status == "paused", *( [WorkflowRunORM.project_id == project_id] if project_id else [])).count(),
            "manual_review_workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.status == "manual_review", *( [WorkflowRunORM.project_id == project_id] if project_id else [])).count(),
            "attention_workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.status == "attention_required", *( [WorkflowRunORM.project_id == project_id] if project_id else [])).count(),
            "failed_workflow_runs": db.query(WorkflowRunORM).filter(WorkflowRunORM.status == "failed", *( [WorkflowRunORM.project_id == project_id] if project_id else [])).count(),
            "agent_calls": db.query(AgentCallLogORM).filter(AgentCallLogORM.project_id == project_id).count() if project_id else db.query(AgentCallLogORM).count(),
            "failed_agent_calls": db.query(AgentCallLogORM).filter(AgentCallLogORM.call_status == "error", *( [AgentCallLogORM.project_id == project_id] if project_id else [])).count(),
            "gate_failures": db.query(GateReviewORM).filter(GateReviewORM.passed.is_(False), *( [GateReviewORM.project_id == project_id] if project_id else [])).count(),
            "changesets": db.query(ChangeSetORM).filter(ChangeSetORM.project_id == project_id).count() if project_id else db.query(ChangeSetORM).count(),
            "published_records": db.query(PublishRecordORM).filter(PublishRecordORM.project_id == project_id).count() if project_id else db.query(PublishRecordORM).count(),
            "publish_failures": db.query(PublishRecordORM).filter(PublishRecordORM.publish_status != "published", *( [PublishRecordORM.project_id == project_id] if project_id else [])).count(),
        }
        issues = self._build_recent_issues(db=db, project_id=project_id, workflow_run_id=workflow_run_id, limit=20)
        health_status = "healthy"
        if counts["failed_workflow_runs"] or counts["failed_agent_calls"] or counts["publish_failures"]:
            health_status = "degraded"
        if counts["attention_workflow_runs"] and health_status == "healthy":
            health_status = "warning"
        recent_runs = self.list_workflow_runs(db=db, project_id=project_id, limit=10)
        provider_name = agent_gateway.status().active_provider
        return {
            "project_id": project_id,
            "workflow_run_id": workflow_run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health_status": health_status,
            "counts": counts,
            "provider_governance": provider_governance_service.get_governance_snapshot(db=db, provider_name=provider_name),
            "recent_run_statuses": recent_runs,
            "recent_issues": issues,
        }

    def get_run_diagnostics(self, db: Session, workflow_run_id: str) -> dict:
        detail = workflow_run_service.get_run_detail(db=db, workflow_run_id=workflow_run_id).model_dump(mode="json")
        run = db.get(WorkflowRunORM, workflow_run_id)
        issues = self._build_recent_issues(db=db, workflow_run_id=workflow_run_id, limit=20)
        counts = {
            "agent_calls": db.query(AgentCallLogORM).filter(AgentCallLogORM.workflow_run_id == workflow_run_id).count(),
            "failed_agent_calls": db.query(AgentCallLogORM).filter(AgentCallLogORM.workflow_run_id == workflow_run_id, AgentCallLogORM.call_status == "error").count(),
            "gate_reviews": db.query(GateReviewORM).filter(GateReviewORM.workflow_run_id == workflow_run_id).count(),
            "failed_gates": db.query(GateReviewORM).filter(GateReviewORM.workflow_run_id == workflow_run_id, GateReviewORM.passed.is_(False)).count(),
            "changesets": db.query(ChangeSetORM).filter(ChangeSetORM.workflow_run_id == workflow_run_id).count(),
            "state_transitions": db.query(ChapterStateTransitionORM).filter(ChapterStateTransitionORM.workflow_run_id == workflow_run_id).count(),
            "publish_records": db.query(PublishRecordORM).filter(PublishRecordORM.workflow_run_id == workflow_run_id).count(),
        }
        health_status = "healthy"
        if counts["failed_agent_calls"] or counts["failed_gates"]:
            health_status = "degraded"
        if run and run.status in {"failed", "attention_required", "paused", "manual_review"}:
            if run.status == "failed":
                health_status = "degraded"
            else:
                health_status = "warning"
        return {
            "run": detail["run"],
            "health_status": health_status,
            "summary": {
                **counts,
                "run_status": run.status if run else None,
                "current_step": run.current_step if run else None,
                "trace_id": run.trace_id if run else None,
                "control_mode": (run.run_metadata or {}).get("control_mode") if run else None,
            },
            "recent_issues": issues,
            "nodes": detail["nodes"],
        }


    def pause_workflow_run(self, db: Session, request: PauseWorkflowRunRequest) -> dict:
        run = workflow_run_service.pause_run(
            db=db,
            workflow_run_id=request.workflow_run_id,
            paused_by=request.paused_by,
            reason=request.reason,
            pause_at_step=request.pause_at_step,
            notes=request.notes,
        )
        db.commit()
        return WorkflowRunControlResult(run=WorkflowRun.model_validate(run), control_action="pause", message="workflow paused", generated_at=datetime.now(timezone.utc)).model_dump(mode="json")

    def resume_workflow_run(self, db: Session, request: ResumeWorkflowRunRequest) -> dict:
        run = workflow_run_service.resume_run(
            db=db,
            workflow_run_id=request.workflow_run_id,
            resumed_by=request.resumed_by,
            resume_from_step=request.resume_from_step,
            notes=request.notes,
        )
        db.commit()
        return WorkflowRunControlResult(run=WorkflowRun.model_validate(run), control_action="resume", message="workflow resumed", generated_at=datetime.now(timezone.utc)).model_dump(mode="json")

    def request_manual_takeover(self, db: Session, request: ManualTakeoverRequest) -> dict:
        run = workflow_run_service.request_manual_takeover(
            db=db,
            workflow_run_id=request.workflow_run_id,
            requested_by=request.requested_by,
            reason=request.reason,
            take_over_step=request.take_over_step,
            handoff_notes=request.handoff_notes,
        )
        db.commit()
        return WorkflowRunControlResult(run=WorkflowRun.model_validate(run), control_action="manual_takeover", message="workflow moved to manual_review", generated_at=datetime.now(timezone.utc)).model_dump(mode="json")

    def mark_human_reviewed(self, db: Session, request: MarkHumanReviewedRequest) -> dict:
        run = workflow_run_service.mark_human_reviewed(
            db=db,
            workflow_run_id=request.workflow_run_id,
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes,
            next_action=request.next_action,
            resume_run=request.resume_run,
            resume_from_step=request.resume_from_step,
        )
        db.commit()
        return WorkflowRunControlResult(run=WorkflowRun.model_validate(run), control_action="mark_human_reviewed", message="human review recorded", generated_at=datetime.now(timezone.utc)).model_dump(mode="json")

    def manual_continue_workflow_run(self, db: Session, request: ManualContinueWorkflowRunRequest) -> dict:
        run = workflow_run_service.manual_continue(
            db=db,
            workflow_run_id=request.workflow_run_id,
            continued_by=request.continued_by,
            reason=request.reason,
            continue_from_step=request.continue_from_step,
            notes=request.notes,
        )
        db.commit()
        return WorkflowRunControlResult(run=WorkflowRun.model_validate(run), control_action="manual_continue", message="workflow manually continued", generated_at=datetime.now(timezone.utc)).model_dump(mode="json")

    def _get_goal_for_execution(self, db: Session, request: ExecuteChapterCycleRequest) -> ChapterGoal:
        if request.chapter_goal_id:
            goal = db.get(ChapterGoalORM, request.chapter_goal_id)
            if goal is None or goal.project_id != request.project_id:
                raise NotFoundError("章目标不存在")
            return ChapterGoal.model_validate(goal)
        if request.chapter_no is None:
            raise ValidationError("chapter_no 不能为空")
        if not request.current_volume_goal or not request.current_volume_goal.strip():
            raise ValidationError("current_volume_goal 不能为空")
        return chapter_service.create_goal(
            db=db,
            request=CreateChapterGoalRequest(
                project_id=request.project_id,
                chapter_no=request.chapter_no,
                current_volume_goal=request.current_volume_goal.strip(),
                previous_chapter_summary=request.previous_chapter_summary,
                unresolved_open_loops=request.unresolved_open_loops,
                workflow_run_id=request.workflow_run_id,
                trace_id=request.trace_id,
            ),
        )

    def _list_scenes(self, db: Session, project_id: str, blueprint_id: str) -> list[SceneCard]:
        items = (
            db.query(SceneCardORM)
            .filter(SceneCardORM.project_id == project_id, SceneCardORM.blueprint_id == blueprint_id)
            .order_by(SceneCardORM.created_at.asc())
            .all()
        )
        return [SceneCard.model_validate(item) for item in items]

    def _get_latest_draft(self, db: Session, project_id: str, blueprint_id: str) -> ChapterDraft | None:
        entity = (
            db.query(ChapterDraftORM)
            .filter(ChapterDraftORM.project_id == project_id, ChapterDraftORM.blueprint_id == blueprint_id)
            .order_by(ChapterDraftORM.created_at.desc())
            .first()
        )
        if entity is None:
            return None
        metadata = dict(entity.draft_metadata or {})
        return ChapterDraft(
            id=entity.id,
            project_id=entity.project_id,
            blueprint_id=entity.blueprint_id,
            workflow_run_id=entity.workflow_run_id,
            trace_id=entity.trace_id,
            content=entity.content,
            status=entity.status,
            metadata=metadata,
            parent_draft_id=metadata.get("parent_draft_id"),
            revision_no=int(metadata.get("revision_no") or 1),
            revision_reason=metadata.get("revision_reason"),
            source_gate_review_ids=list(metadata.get("source_gate_review_ids") or []),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _get_latest_changeset(self, db: Session, project_id: str, draft_id: str) -> ChangeSet | None:
        entity = (
            db.query(ChangeSetORM)
            .filter(ChangeSetORM.project_id == project_id, ChangeSetORM.source_ref == draft_id)
            .order_by(ChangeSetORM.created_at.desc())
            .first()
        )
        return ChangeSet.model_validate(entity) if entity is not None else None


    def _get_latest_gate_reviews(self, db: Session, project_id: str, draft_id: str) -> list[GateReviewResult]:
        rows = (
            db.query(GateReviewORM)
            .filter(GateReviewORM.project_id == project_id, GateReviewORM.draft_id == draft_id)
            .order_by(GateReviewORM.created_at.desc())
            .limit(12)
            .all()
        )
        return [GateReviewResult.model_validate(row) for row in rows]

    def execute_chapter_cycle(self, db: Session, request: ExecuteChapterCycleRequest) -> dict:
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在")
        existing_run = db.get(WorkflowRunORM, request.workflow_run_id) if request.workflow_run_id else None
        initial_run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=request.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=request.chapter_no,
            source_type="chapter_cycle",
            current_step=(existing_run.current_step if existing_run else "chapter_cycle_started"),
            run_metadata={"entry": "execute_chapter_cycle"},
        )
        if request.workflow_run_id:
            if initial_run.status == "paused":
                raise ConflictError("工作流已暂停，请先执行 resume 再继续章节主链")
            if initial_run.status == "manual_review" and (initial_run.run_metadata or {}).get("manual_review_required", True):
                raise ConflictError("工作流处于人工接管状态，请先 mark_human_reviewed 或 manual_continue")
            if initial_run.status == "completed":
                raise ConflictError("当前 workflow_run 已完成；如需新一轮执行，请创建新的 workflow_run")
        db.commit()
        goal = self._get_goal_for_execution(db=db, request=request)
        run_id = goal.workflow_run_id or initial_run.id
        run = db.get(WorkflowRunORM, run_id) or initial_run
        continuity_pack = None
        if request.auto_resolve_continuity:
            continuity_pack = continuity_service.resolve_pack(
                db=db,
                request=ResolveContinuityPackRequest(
                    project_id=request.project_id,
                    target_chapter_no=goal.chapter_no,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    previous_chapter_summary=request.previous_chapter_summary,
                    unresolved_open_loops=request.unresolved_open_loops,
                    recent_limit=request.continuity_recent_limit,
                ),
                commit=False,
            )
            run = db.get(WorkflowRunORM, run.id) or run

        blueprints = chapter_service.list_blueprints(db=db, project_id=request.project_id, chapter_goal_id=goal.id)
        if not blueprints:
            blueprints = chapter_service.generate_blueprints(
                db=db,
                request=GenerateBlueprintsRequest(
                    project_id=request.project_id,
                    chapter_goal_id=goal.id,
                    candidate_count=request.candidate_count,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
            )
            run = db.get(WorkflowRunORM, run.id) or run

        selected_blueprint = next((item for item in blueprints if item.selected), None)
        if request.selected_blueprint_id:
            if selected_blueprint is None or selected_blueprint.id != request.selected_blueprint_id:
                if not request.selected_by or not request.selected_by.strip():
                    raise ValidationError("selected_by 不能为空；执行蓝图确认时必须显式提供选择人")
                selected_blueprint = chapter_service.select_blueprint(
                    db=db,
                    request=SelectBlueprintRequest(
                        project_id=request.project_id,
                        blueprint_id=request.selected_blueprint_id,
                        selected_by=request.selected_by.strip(),
                        selection_reason=request.selection_reason,
                        workflow_run_id=run.id,
                        trace_id=run.trace_id,
                    ),
                )
                blueprints = chapter_service.list_blueprints(db=db, project_id=request.project_id, chapter_goal_id=goal.id)
                run = db.get(WorkflowRunORM, run.id) or run
            else:
                selected_blueprint = next((item for item in blueprints if item.id == request.selected_blueprint_id), selected_blueprint)

        result = ExecuteChapterCycleResult(
            run=WorkflowRun.model_validate(run),
            stage_status="running",
            continuity_pack=continuity_pack,
            goal=goal,
            blueprints=blueprints,
            selected_blueprint=selected_blueprint,
        )

        if selected_blueprint is None:
            workflow_run_service.mark_attention(
                db=db,
                run=run,
                current_step="blueprint_selection_required",
                reason="候选章蓝图已生成，等待人工确认正式蓝图",
                extra_metadata={"chapter_goal_id": goal.id, "candidate_blueprint_ids": [item.id for item in blueprints]},
            )
            db.commit()
            result.run = WorkflowRun.model_validate(db.get(WorkflowRunORM, run.id) or run)
            result.stage_status = "attention_required"
            result.next_action = "select_blueprint"
            return result.model_dump(mode="json")

        scenes = self._list_scenes(db=db, project_id=request.project_id, blueprint_id=selected_blueprint.id)
        if not scenes:
            scenes = chapter_service.decompose_scenes(
                db=db,
                request=DecomposeScenesRequest(
                    project_id=request.project_id,
                    blueprint_id=selected_blueprint.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
            )
            run = db.get(WorkflowRunORM, run.id) or run
        result.selected_blueprint = selected_blueprint
        result.scenes = scenes

        draft = self._get_latest_draft(db=db, project_id=request.project_id, blueprint_id=selected_blueprint.id)
        if draft is None:
            draft = chapter_service.generate_draft(
                db=db,
                request=GenerateDraftRequest(
                    project_id=request.project_id,
                    blueprint_id=selected_blueprint.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
            )
            run = db.get(WorkflowRunORM, run.id) or run
        result.draft = draft

        gate_results: list[GateReviewResult] = []
        if request.auto_run_gates:
            gate_results = gate_service.run_reviews(
                db=db,
                request=RunGateReviewRequest(
                    project_id=request.project_id,
                    draft_id=draft.id,
                    gate_names=request.review_gate_names,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
            )
            run = db.get(WorkflowRunORM, run.id) or run
            result.gate_results = gate_results
            result.draft = self._get_latest_draft(db=db, project_id=request.project_id, blueprint_id=selected_blueprint.id) or draft
            if any(item.pass_status == "failed" for item in gate_results):
                if request.auto_revise_on_gate_failure:
                    current_revision_no = int((result.draft.metadata or {}).get("revision_no") or 1)
                    if current_revision_no - 1 >= request.max_revision_rounds:
                        result.run = WorkflowRun.model_validate(run)
                        result.stage_status = "attention_required"
                        result.next_action = "review_revision_limit"
                        return result.model_dump(mode="json")
                    revised_draft = chapter_service.revise_draft(
                        db=db,
                        request=ReviseDraftRequest(
                            project_id=request.project_id,
                            draft_id=draft.id,
                            revision_instruction=request.revision_instruction,
                            source_gate_review_ids=[item.id for item in gate_results if item.pass_status == "failed"],
                            revised_by=request.revised_by,
                            workflow_run_id=run.id,
                            trace_id=run.trace_id,
                        ),
                    )
                    run = db.get(WorkflowRunORM, run.id) or run
                    result.draft = revised_draft
                    result.gate_results = gate_results
                    rerun_results = gate_service.run_reviews(
                        db=db,
                        request=RunGateReviewRequest(
                            project_id=request.project_id,
                            draft_id=revised_draft.id,
                            gate_names=request.review_gate_names,
                            workflow_run_id=run.id,
                            trace_id=run.trace_id,
                        ),
                    )
                    run = db.get(WorkflowRunORM, run.id) or run
                    result.gate_results = rerun_results
                    result.draft = self._get_latest_draft(db=db, project_id=request.project_id, blueprint_id=selected_blueprint.id) or revised_draft
                    if any(item.pass_status == "failed" for item in rerun_results):
                        result.run = WorkflowRun.model_validate(run)
                        result.stage_status = "attention_required"
                        result.next_action = "review_revised_draft"
                        return result.model_dump(mode="json")
                    gate_results = rerun_results
                    draft = result.draft
                else:
                    result.run = WorkflowRun.model_validate(run)
                    result.stage_status = "attention_required"
                    result.next_action = "revise_draft"
                    return result.model_dump(mode="json")

        changeset = self._get_latest_changeset(db=db, project_id=request.project_id, draft_id=draft.id)
        proposal: ChangeSetProposal | None = None
        if request.auto_propose_changeset:
            resolved_patch_operations = list(request.patch_operations)
            if not resolved_patch_operations:
                if request.auto_generate_changeset_proposal:
                    proposal = changeset_service.generate_proposal(
                        db=db,
                        request=GenerateChangeSetProposalRequest(
                            project_id=request.project_id,
                            draft_id=draft.id,
                            rationale=request.changeset_rationale,
                            auto_create_changeset=False,
                            workflow_run_id=run.id,
                            trace_id=run.trace_id,
                        ),
                    )
                    result.changeset_proposal = proposal
                    resolved_patch_operations = list(proposal.patch_operations)
                    run = db.get(WorkflowRunORM, run.id) or run
                else:
                    workflow_run_service.mark_attention(
                        db=db,
                        run=run,
                        current_step="changeset_proposal_required",
                        reason="缺少 ChangeSet Proposal，无法自动生成 ChangeSet",
                        extra_metadata={"draft_id": draft.id},
                    )
                    db.commit()
                    result.run = WorkflowRun.model_validate(db.get(WorkflowRunORM, run.id) or run)
                    result.stage_status = "attention_required"
                    result.next_action = "generate_changeset_proposal"
                    return result.model_dump(mode="json")
            if not resolved_patch_operations:
                workflow_run_service.mark_attention(
                    db=db,
                    run=run,
                    current_step="changeset_patch_required",
                    reason="ChangeSet Proposal 未生成有效 patch_operations",
                    extra_metadata={"draft_id": draft.id},
                )
                db.commit()
                result.run = WorkflowRun.model_validate(db.get(WorkflowRunORM, run.id) or run)
                result.stage_status = "attention_required"
                result.next_action = "review_changeset_proposal"
                return result.model_dump(mode="json")
            if changeset is None or changeset.status == ChangeSetStatus.REJECTED.value:
                rationale = (request.changeset_rationale or getattr(proposal, "rationale", None) or "基于本章正文推进 Canon / 对象状态").strip()
                changeset = changeset_service.propose(
                    db=db,
                    request=ProposeChangeSetRequest(
                        project_id=request.project_id,
                        source_type="chapter_draft",
                        source_ref=draft.id,
                        rationale=rationale,
                        patch_operations=resolved_patch_operations,
                        workflow_run_id=run.id,
                        trace_id=run.trace_id,
                    ),
                )
                run = db.get(WorkflowRunORM, run.id) or run

        if changeset is not None and request.auto_approve_changeset and changeset.status == ChangeSetStatus.PROPOSED.value:
            if not request.approved_by or not request.approved_by.strip():
                raise ValidationError("approved_by 不能为空；自动审批 ChangeSet 时必须显式提供审批人")
            changeset = changeset_service.approve(db=db, changeset_id=changeset.id, approved_by=request.approved_by.strip())
            run = db.get(WorkflowRunORM, run.id) or run

        if changeset is not None and request.auto_apply_changeset and changeset.status == ChangeSetStatus.APPROVED.value:
            changeset = changeset_service.apply(db=db, changeset_id=changeset.id)
            run = db.get(WorkflowRunORM, run.id) or run

        result.changeset = changeset

        result.draft = self._get_latest_draft(db=db, project_id=request.project_id, blueprint_id=selected_blueprint.id) or draft

        if request.auto_publish:
            if changeset is None or changeset.status != ChangeSetStatus.APPLIED.value:
                workflow_run_service.mark_attention(
                    db=db,
                    run=run,
                    current_step="publish_precondition_missing",
                    reason="自动发布前必须存在已 applied 的 ChangeSet",
                    extra_metadata={"draft_id": draft.id, "changeset_id": getattr(changeset, "id", None)},
                )
                db.commit()
                result.run = WorkflowRun.model_validate(db.get(WorkflowRunORM, run.id) or run)
                result.stage_status = "attention_required"
                result.next_action = "apply_changeset"
                return result.model_dump(mode="json")
            published = db.query(PublishedChapterORM).filter(PublishedChapterORM.draft_id == draft.id).first()
            if published is None:
                if not request.published_by or not request.published_by.strip():
                    raise ValidationError("published_by 不能为空；自动发布时必须显式提供发布人")
                result.publish_result = publish_service.publish_draft(
                    db=db,
                    request=PublishDraftRequest(
                        project_id=request.project_id,
                        draft_id=draft.id,
                        published_by=request.published_by.strip(),
                        publish_title=request.publish_title,
                        notes=request.notes,
                        workflow_run_id=run.id,
                        trace_id=run.trace_id,
                    ),
                )
                run = db.get(WorkflowRunORM, run.id) or run
                if request.auto_generate_chapter_summary and result.publish_result is not None:
                    result.chapter_summary = result.publish_result.chapter_summary
                if request.auto_run_post_publish_updates and result.publish_result is not None:
                    if result.publish_result.derived_update_result is not None:
                        result.derived_update_result = result.publish_result.derived_update_result
                    else:
                        result.derived_update_result = derived_update_service.run_post_publish_updates(
                            db=db,
                            request=RunDerivedUpdatesRequest(
                                project_id=request.project_id,
                                published_chapter_id=result.publish_result.published_chapter.id,
                                workflow_run_id=run.id,
                                trace_id=run.trace_id,
                                task_names=request.post_publish_task_names,
                            ),
                            commit=True,
                        )
                    run = db.get(WorkflowRunORM, run.id) or run
            result.run = WorkflowRun.model_validate(run)
            result.stage_status = "completed"
            result.next_action = None
            return result.model_dump(mode="json")

        result.run = WorkflowRun.model_validate(db.get(WorkflowRunORM, run.id) or run)
        if changeset is not None and changeset.status == ChangeSetStatus.APPLIED.value:
            result.stage_status = "canon_applied"
            result.next_action = "publish"
        elif changeset is not None and changeset.status == ChangeSetStatus.APPROVED.value:
            result.stage_status = "changeset_approved"
            result.next_action = "apply_changeset"
        elif changeset is not None and changeset.status == ChangeSetStatus.PROPOSED.value:
            result.stage_status = "changeset_proposed"
            result.next_action = "approve_changeset"
        elif gate_results:
            result.stage_status = "review_passed"
            result.next_action = "generate_changeset_proposal"
        else:
            result.stage_status = "draft_ready"
            result.next_action = "run_gates"
        return result.model_dump(mode="json")


    def execute_chapter_sequence(self, db: Session, request: ExecuteChapterSequenceRequest) -> dict:
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在")
        sequence_run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=request.trace_id,
            workflow_name="chapter_sequence_workflow_v1",
            chapter_no=request.start_chapter_no,
            source_type="chapter_sequence",
            current_step="chapter_sequence_started",
            run_metadata={
                "entry": "execute_chapter_sequence",
                "start_chapter_no": request.start_chapter_no,
                "chapter_count": request.chapter_count,
                "stop_on_attention": request.stop_on_attention,
                "stop_on_failure": request.stop_on_failure,
                "advance_only_on_completed": request.advance_only_on_completed,
                "testing_auto_select_first_blueprint": request.testing_auto_select_first_blueprint,
            },
        )
        if request.workflow_run_id:
            if sequence_run.status == "paused":
                raise ConflictError("章节序列工作流已暂停，请先 resume")
            if sequence_run.status == "manual_review" and (sequence_run.run_metadata or {}).get("manual_review_required", True):
                raise ConflictError("章节序列工作流处于人工接管状态，请先 mark_human_reviewed 或 manual_continue")
            if sequence_run.status == "completed":
                raise ConflictError("当前章节序列 workflow_run 已完成；如需新一轮执行，请创建新的 workflow_run")
        workflow_run_service.update_progress(
            db=db,
            run=sequence_run,
            current_step="chapter_sequence_running",
            status="running",
            extra_metadata={
                "sequence_started_at": datetime.now(timezone.utc).isoformat(),
                "current_chapter_no": request.start_chapter_no,
            },
        )
        self._log_sequence_event(
            db=db,
            run=sequence_run,
            event_type="workflow_run_sequence_started",
            payload={
                "start_chapter_no": request.start_chapter_no,
                "chapter_count": request.chapter_count,
                "testing_auto_select_first_blueprint": request.testing_auto_select_first_blueprint,
            },
        )
        db.commit()

        chapter_results: list[ChapterSequenceItemResult] = []
        stop_reason: str | None = None
        next_action: str | None = None
        final_status = "completed"

        for offset in range(request.chapter_count):
            chapter_no = request.start_chapter_no + offset
            sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
            workflow_run_service.update_progress(
                db=db,
                run=sequence_run,
                current_step=f"chapter_{chapter_no}_running",
                status="running",
                extra_metadata={"current_chapter_no": chapter_no, "last_dispatched_chapter_no": chapter_no},
            )
            db.flush()

            cycle_request = ExecuteChapterCycleRequest(
                project_id=request.project_id,
                chapter_no=chapter_no,
                current_volume_goal=request.current_volume_goal,
                auto_resolve_continuity=request.auto_resolve_continuity,
                continuity_recent_limit=request.continuity_recent_limit,
                candidate_count=request.candidate_count,
                auto_run_gates=request.auto_run_gates,
                review_gate_names=request.review_gate_names,
                auto_revise_on_gate_failure=request.auto_revise_on_gate_failure,
                revision_instruction=request.revision_instruction,
                revised_by=request.revised_by,
                max_revision_rounds=request.max_revision_rounds,
                auto_propose_changeset=request.auto_propose_changeset,
                auto_generate_changeset_proposal=request.auto_generate_changeset_proposal,
                changeset_rationale=request.changeset_rationale,
                auto_approve_changeset=request.auto_approve_changeset,
                approved_by=request.approved_by,
                auto_apply_changeset=request.auto_apply_changeset,
                auto_publish=request.auto_publish,
                auto_generate_chapter_summary=request.auto_generate_chapter_summary,
                auto_run_post_publish_updates=request.auto_run_post_publish_updates,
                post_publish_task_names=request.post_publish_task_names,
                published_by=request.published_by,
                publish_title=request.publish_title,
                notes=request.notes,
                trace_id=sequence_run.trace_id,
            )
            cycle_result = ExecuteChapterCycleResult.model_validate(self.execute_chapter_cycle(db=db, request=cycle_request))

            if (
                cycle_result.stage_status == "attention_required"
                and cycle_result.next_action == "select_blueprint"
                and request.testing_auto_select_first_blueprint
                and cycle_result.goal is not None
                and cycle_result.blueprints
            ):
                auto_selected = cycle_result.blueprints[0]
                cycle_result = ExecuteChapterCycleResult.model_validate(
                    self.execute_chapter_cycle(
                        db=db,
                        request=ExecuteChapterCycleRequest(
                            project_id=request.project_id,
                            chapter_goal_id=cycle_result.goal.id,
                            selected_blueprint_id=auto_selected.id,
                            selected_by=(request.testing_selected_by or "sequence_runner"),
                            selection_reason=(request.testing_selection_reason or "sequence_test_auto_selected_first_candidate"),
                            auto_resolve_continuity=request.auto_resolve_continuity,
                            continuity_recent_limit=request.continuity_recent_limit,
                            candidate_count=request.candidate_count,
                            auto_run_gates=request.auto_run_gates,
                            review_gate_names=request.review_gate_names,
                            auto_revise_on_gate_failure=request.auto_revise_on_gate_failure,
                            revision_instruction=request.revision_instruction,
                            revised_by=request.revised_by,
                            max_revision_rounds=request.max_revision_rounds,
                            auto_propose_changeset=request.auto_propose_changeset,
                            auto_generate_changeset_proposal=request.auto_generate_changeset_proposal,
                            changeset_rationale=request.changeset_rationale,
                            auto_approve_changeset=request.auto_approve_changeset,
                            approved_by=request.approved_by,
                            auto_apply_changeset=request.auto_apply_changeset,
                            auto_publish=request.auto_publish,
                            auto_generate_chapter_summary=request.auto_generate_chapter_summary,
                            auto_run_post_publish_updates=request.auto_run_post_publish_updates,
                            post_publish_task_names=request.post_publish_task_names,
                            published_by=request.published_by,
                            publish_title=request.publish_title,
                            notes=request.notes,
                            workflow_run_id=cycle_result.run.id,
                            trace_id=cycle_result.run.trace_id,
                        ),
                    )
                )

            item = self._build_sequence_item(cycle_result)
            chapter_results.append(item)
            sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
            self._append_sequence_result(db=db, run=sequence_run, item=item)
            self._log_sequence_event(
                db=db,
                run=sequence_run,
                event_type="workflow_run_sequence_chapter_processed",
                payload={
                    "chapter_no": chapter_no,
                    "chapter_workflow_run_id": item.workflow_run_id,
                    "stage_status": item.stage_status,
                    "next_action": item.next_action,
                    "published_chapter_id": item.published_chapter_id,
                },
            )
            db.commit()

            if item.stage_status == "failed" and request.stop_on_failure:
                stop_reason = f"chapter_{chapter_no}_failed"
                next_action = item.next_action or "inspect_failure"
                final_status = "failed"
                sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
                workflow_run_service.fail_run(
                    db=db,
                    run=sequence_run,
                    current_step=f"chapter_{chapter_no}_failed",
                    reason="章节序列执行中某一章失败，已停止后续章节调度",
                    extra_metadata={"stopped_chapter_no": chapter_no, "stop_reason": stop_reason},
                )
                self._log_sequence_event(db=db, run=sequence_run, event_type="workflow_run_sequence_stopped", payload={"chapter_no": chapter_no, "stop_reason": stop_reason, "next_action": next_action})
                db.commit()
                break

            if item.stage_status == "attention_required" and request.stop_on_attention:
                stop_reason = f"chapter_{chapter_no}_attention_required"
                next_action = item.next_action
                final_status = "attention_required"
                sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
                workflow_run_service.mark_attention(
                    db=db,
                    run=sequence_run,
                    current_step=f"chapter_{chapter_no}_attention_required",
                    reason="章节序列执行遇到人工节点，已按 stop_on_attention 停止",
                    extra_metadata={"stopped_chapter_no": chapter_no, "stop_reason": stop_reason, "next_action": next_action},
                )
                self._log_sequence_event(db=db, run=sequence_run, event_type="workflow_run_sequence_stopped", payload={"chapter_no": chapter_no, "stop_reason": stop_reason, "next_action": next_action})
                db.commit()
                break

            if request.advance_only_on_completed and item.stage_status != "completed":
                stop_reason = f"chapter_{chapter_no}_not_completed"
                next_action = item.next_action or "complete_current_chapter"
                final_status = "attention_required"
                sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
                workflow_run_service.mark_attention(
                    db=db,
                    run=sequence_run,
                    current_step=f"chapter_{chapter_no}_not_completed",
                    reason="当前章节尚未完成发布，序列执行不会推进到下一章",
                    extra_metadata={"stopped_chapter_no": chapter_no, "stop_reason": stop_reason, "next_action": next_action},
                )
                self._log_sequence_event(db=db, run=sequence_run, event_type="workflow_run_sequence_stopped", payload={"chapter_no": chapter_no, "stop_reason": stop_reason, "next_action": next_action})
                db.commit()
                break

        sequence_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
        if stop_reason is None:
            workflow_run_service.update_progress(
                db=db,
                run=sequence_run,
                current_step="chapter_sequence_completed",
                status="completed",
                complete=True,
                extra_metadata={
                    "sequence_completed_at": datetime.now(timezone.utc).isoformat(),
                    "last_completed_chapter_no": request.start_chapter_no + request.chapter_count - 1,
                },
            )
            self._log_sequence_event(
                db=db,
                run=sequence_run,
                event_type="workflow_run_sequence_completed",
                payload={
                    "processed_chapter_count": len(chapter_results),
                    "completed_chapter_count": sum(1 for item in chapter_results if item.stage_status == "completed"),
                },
            )
            db.commit()

        final_run = db.get(WorkflowRunORM, sequence_run.id) or sequence_run
        return ExecuteChapterSequenceResult(
            run=WorkflowRun.model_validate(final_run),
            stage_status=final_status,
            next_action=next_action,
            stop_reason=stop_reason,
            processed_chapter_count=len(chapter_results),
            completed_chapter_count=sum(1 for item in chapter_results if item.stage_status == "completed"),
            failed_chapter_count=sum(1 for item in chapter_results if item.stage_status == "failed"),
            attention_chapter_count=sum(1 for item in chapter_results if item.stage_status == "attention_required"),
            chapter_results=chapter_results,
        ).model_dump(mode="json")


workflow_service = WorkflowService()
