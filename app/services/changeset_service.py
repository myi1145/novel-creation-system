from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import (
    CanonSnapshotORM,
    ChangeSetORM,
    CharacterCardORM,
    ChapterBlueprintORM,
    GateReviewORM,
    ImmutableLogORM,
    OpenLoopCardORM,
    ProjectORM,
    PublishedChapterORM,
    RelationshipEdgeORM,
    RuleCardORM,
    ChapterDraftORM,
)
from app.domain.enums import ChangeSetStatus, ChapterStatus, GateName
from app.schemas.changeset import ChangeSet, ChangeSetProposal, GenerateChangeSetProposalRequest, ProposeChangeSetRequest
from app.services.agent_gateway import AgentGatewayError, agent_gateway
from app.services.chapter_state_service import chapter_state_service
from app.services.object_service import object_service
from app.services.workflow_run_service import workflow_run_service

_ALLOWED_SNAPSHOT_FIELDS = {
    "timeline_events",
}

_OBJECT_TYPE_TO_MODEL = {
    "character_card": CharacterCardORM,
    "rule_card": RuleCardORM,
    "open_loop_card": OpenLoopCardORM,
    "relationship_edge": RelationshipEdgeORM,
}

_CHAPTER_CHANGESET_PREFIXES = ("chapter_", "draft_")
logger = get_logger("workflow")


class ChangeSetService:
    _REQUIRED_PROPOSAL_GATES = [GateName.SCHEMA.value, GateName.CANON.value, GateName.NARRATIVE.value]

    def generate_proposal(self, db: Session, request: GenerateChangeSetProposalRequest) -> ChangeSetProposal:
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法生成 ChangeSet 提议")
        draft = db.get(ChapterDraftORM, request.draft_id)
        if draft is None or draft.project_id != request.project_id:
            raise NotFoundError("章节草稿不存在，无法生成 ChangeSet 提议")
        blueprint = db.get(ChapterBlueprintORM, draft.blueprint_id)
        if blueprint is None or blueprint.project_id != request.project_id:
            raise NotFoundError("章蓝图不存在，无法生成 ChangeSet 提议")
        if not blueprint.selected:
            raise ConflictError("只能基于已选定的正式章蓝图生成 ChangeSet 提议")
        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == request.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        if latest_snapshot is None:
            raise ConflictError("当前项目尚未初始化 Canon Snapshot，无法生成 ChangeSet 提议")
        self._ensure_proposal_gate_requirements(db=db, project_id=request.project_id, draft_id=draft.id)

        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or draft.workflow_run_id,
            trace_id=request.trace_id or draft.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="changeset_proposal_generation",
            source_type="chapter_draft",
            source_ref=draft.id,
        )

        content = (draft.content or "").strip()
        excerpt = content[:220] if content else ""
        context = {
            "project_id": request.project_id,
            "draft_id": draft.id,
            "blueprint_id": blueprint.id,
            "chapter_no": draft.draft_metadata.get("chapter_no") if isinstance(draft.draft_metadata, dict) else None,
            "content": content,
            "blueprint": {
                "title_hint": blueprint.title_hint,
                "summary": blueprint.summary,
                "advances": blueprint.advances,
                "risks": blueprint.risks,
            },
            "canon_summary_json": {
                "snapshot_id": latest_snapshot.id,
                "version_no": latest_snapshot.version_no,
                "character_count": len(latest_snapshot.character_cards or []),
                "rule_count": len(latest_snapshot.rule_cards or []),
                "relationship_count": len(latest_snapshot.relationship_edges or []),
                "open_loop_count": len(latest_snapshot.open_loops or []),
                "timeline_event_count": len(latest_snapshot.timeline_events or []),
            },
            "genre_name": project.genre_id or "unknown",
        }

        generated_by = "agent"
        provider = None
        model = None
        try:
            invocation = agent_gateway.propose_changeset(
                db=db,
                context=context,
                audit_context={
                    "project_id": request.project_id,
                    "workflow_name": "chapter_cycle_workflow_v1",
                    "workflow_run_id": run.id,
                    "trace_id": run.trace_id,
                    "draft_id": draft.id,
                    "blueprint_id": blueprint.id,
                },
            )
            payload = dict(invocation.payload or {})
            patch_operations = [dict(op) for op in list(payload.get("patch_operations") or []) if isinstance(op, dict)]
            self._validate_patch_operations(patch_operations)
            proposal_summary = str(payload.get("proposal_summary") or "已生成 ChangeSet 提议。")
            rationale = str((request.rationale or payload.get("rationale") or "从章节正文中提取最小可验证状态变化。").strip())
            extracted_changes = [str(item) for item in list(payload.get("extracted_changes") or [])]
            uncertain_items = [str(item) for item in list(payload.get("uncertain_items") or [])]
            evidence_refs = [dict(item) for item in list(payload.get("evidence_refs") or []) if isinstance(item, dict)]
            review_recommendation = str(payload.get("review_recommendation") or ("human_review" if uncertain_items else "semi_auto_review"))
            provider = invocation.active_provider
            model = invocation.model
        except Exception as exc:  # noqa: BLE001
            fallback = self._build_rule_based_proposal(draft=draft, blueprint=blueprint, request=request, excerpt=excerpt)
            proposal_summary = fallback["proposal_summary"]
            rationale = fallback["rationale"]
            extracted_changes = fallback["extracted_changes"]
            uncertain_items = fallback["uncertain_items"]
            evidence_refs = fallback["evidence_refs"]
            review_recommendation = fallback["review_recommendation"]
            patch_operations = fallback["patch_operations"]
            self._validate_patch_operations(patch_operations)
            generated_by = "service"
            provider = "service_fallback"
            model = exc.__class__.__name__

        proposal = ChangeSetProposal(
            project_id=request.project_id,
            draft_id=draft.id,
            blueprint_id=blueprint.id,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            proposal_summary=proposal_summary,
            rationale=rationale,
            patch_operations=patch_operations,
            extracted_changes=extracted_changes,
            uncertain_items=uncertain_items,
            evidence_refs=evidence_refs,
            affected_domains=self._infer_affected_domains(patch_operations),
            review_recommendation=review_recommendation,
            generated_by=generated_by,
            provider=provider,
            model=model,
        )

        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="changeset_proposal_generated",
            extra_metadata={
                "draft_id": draft.id,
                "proposal_patch_count": len(proposal.patch_operations),
                "proposal_review_recommendation": proposal.review_recommendation,
                "proposal_generated_by": proposal.generated_by,
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="changeset_proposal_generated",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "draft_id": draft.id,
                    "blueprint_id": blueprint.id,
                    "proposal_summary": proposal.proposal_summary,
                    "patch_count": len(proposal.patch_operations),
                    "review_recommendation": proposal.review_recommendation,
                    "generated_by": proposal.generated_by,
                },
            )
        )

        if request.auto_create_changeset:
            proposal.changeset = self.propose(
                db=db,
                request=ProposeChangeSetRequest(
                    project_id=request.project_id,
                    source_type="chapter_draft",
                    source_ref=draft.id,
                    rationale=proposal.rationale,
                    patch_operations=proposal.patch_operations,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
            )
        else:
            db.commit()
        return proposal

    def propose(self, db: Session, request: ProposeChangeSetRequest) -> ChangeSet:
        set_log_context(project_id=request.project_id, workflow_run_id=request.workflow_run_id, module="changeset_service", event="changeset.propose", status="started")
        logger.info("开始创建 ChangeSet 提案")
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法创建 ChangeSet")
        self._validate_patch_operations(request.patch_operations)
        draft = db.get(ChapterDraftORM, request.source_ref) if request.source_ref else None
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or getattr(draft, "workflow_run_id", None),
            trace_id=request.trace_id or getattr(draft, "trace_id", None),
            workflow_name="chapter_cycle_workflow_v1",
            current_step="changeset_proposed",
            source_type=request.source_type,
            source_ref=request.source_ref,
        )
        changeset = ChangeSetORM(
            project_id=request.project_id,
            source_type=request.source_type,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            source_ref=request.source_ref,
            rationale=request.rationale,
            patch_operations=request.patch_operations,
            required_gate_names=self._infer_required_gate_names(request.source_type, request.patch_operations),
            status=ChangeSetStatus.PROPOSED.value,
        )
        db.add(changeset)
        db.flush()
        if draft is not None and draft.project_id == request.project_id:
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.CHANGESET_PROPOSED.value,
                trigger_type="changeset_proposed",
                trigger_ref=changeset.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                reason="正文草稿已生成 ChangeSet 提案",
                metadata={"changeset_id": changeset.id},
            )
        workflow_run_service.update_progress(db=db, run=run, current_step="changeset_proposed", source_ref=changeset.id)
        db.add(ImmutableLogORM(event_type="changeset_proposed", project_id=request.project_id, workflow_run_id=run.id, trace_id=run.trace_id, event_payload={"changeset_id": changeset.id, "source_type": request.source_type, "source_ref": request.source_ref}))
        db.commit()
        db.refresh(changeset)
        logger.info("ChangeSet 提案创建成功", extra={"extra_fields": {"event": "changeset.propose", "status": "success", "workflow_run_id": run.id, "summary": f"changeset_id={changeset.id}"}})
        return ChangeSet.model_validate(changeset)

    def approve(self, db: Session, changeset_id: str, approved_by: str) -> ChangeSet:
        set_log_context(module="changeset_service", event="changeset.approve", status="started")
        logger.info("开始审批 ChangeSet", extra={"extra_fields": {"changeset_id": changeset_id}})
        changeset = db.get(ChangeSetORM, changeset_id)
        if changeset is None:
            raise NotFoundError("ChangeSet 不存在")
        if changeset.status != ChangeSetStatus.PROPOSED.value:
            raise ConflictError("只有 proposed 状态的 ChangeSet 才能审批")
        changeset.status = ChangeSetStatus.APPROVED.value
        changeset.approved_by = approved_by
        changeset.approved_at = datetime.now(timezone.utc)
        draft = db.get(ChapterDraftORM, changeset.source_ref)
        if draft is not None and draft.project_id == changeset.project_id:
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.CHANGESET_APPROVED.value,
                trigger_type="changeset_approved",
                trigger_ref=changeset.id,
                workflow_run_id=changeset.workflow_run_id,
                trace_id=changeset.trace_id,
                reason="ChangeSet 已审批通过",
                metadata={"approved_by": approved_by},
            )
        workflow_run_service.update_progress(db=db, run=changeset.workflow_run_id, current_step="changeset_approved")
        db.add(ImmutableLogORM(event_type="changeset_approved", project_id=changeset.project_id, workflow_run_id=changeset.workflow_run_id, trace_id=changeset.trace_id, event_payload={"changeset_id": changeset.id, "approved_by": approved_by}))
        db.commit()
        db.refresh(changeset)
        logger.info("ChangeSet 审批通过", extra={"extra_fields": {"event": "changeset.approve", "status": "success", "workflow_run_id": changeset.workflow_run_id, "summary": f"changeset_id={changeset.id}"}})
        return ChangeSet.model_validate(changeset)

    def reject(self, db: Session, changeset_id: str, rejected_by: str, reason: str | None = None) -> ChangeSet:
        set_log_context(module="changeset_service", event="changeset.reject", status="started")
        logger.info("开始驳回 ChangeSet", extra={"extra_fields": {"changeset_id": changeset_id}})
        changeset = db.get(ChangeSetORM, changeset_id)
        if changeset is None:
            raise NotFoundError("ChangeSet 不存在")
        if changeset.status not in {ChangeSetStatus.PROPOSED.value, ChangeSetStatus.APPROVED.value}:
            raise ConflictError("只有 proposed 或 approved 状态的 ChangeSet 才能驳回")
        changeset.status = ChangeSetStatus.REJECTED.value
        draft = db.get(ChapterDraftORM, changeset.source_ref)
        if draft is not None and draft.project_id == changeset.project_id:
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.APPROVED.value,
                trigger_type="changeset_rejected",
                trigger_ref=changeset.id,
                workflow_run_id=changeset.workflow_run_id,
                trace_id=changeset.trace_id,
                reason=reason or "ChangeSet 被驳回，返回已审稿状态",
                metadata={"rejected_by": rejected_by},
            )
        workflow_run_service.mark_attention(
            db=db,
            run=changeset.workflow_run_id,
            current_step="changeset_rejected",
            reason=reason or "ChangeSet 被驳回",
            extra_metadata={"changeset_id": changeset.id, "rejected_by": rejected_by},
        )
        db.add(ImmutableLogORM(event_type="changeset_rejected", project_id=changeset.project_id, workflow_run_id=changeset.workflow_run_id, trace_id=changeset.trace_id, event_payload={"changeset_id": changeset.id, "rejected_by": rejected_by, "reason": reason}))
        db.commit()
        db.refresh(changeset)
        logger.info("ChangeSet 已驳回", extra={"extra_fields": {"event": "changeset.reject", "status": "success", "workflow_run_id": changeset.workflow_run_id, "summary": f"changeset_id={changeset.id}"}})
        return ChangeSet.model_validate(changeset)

    def apply(self, db: Session, changeset_id: str) -> ChangeSet:
        set_log_context(module="changeset_service", event="changeset.apply", status="started")
        logger.info("开始应用 ChangeSet", extra={"extra_fields": {"changeset_id": changeset_id}})
        changeset = db.get(ChangeSetORM, changeset_id)
        if changeset is None:
            raise NotFoundError("ChangeSet 不存在")
        if changeset.status != ChangeSetStatus.APPROVED.value:
            raise ConflictError("只有 approved 状态的 ChangeSet 才能应用")
        draft = db.get(ChapterDraftORM, changeset.source_ref)
        try:
            self._ensure_gate_requirements(db=db, changeset=changeset)

            latest_snapshot = (
                db.query(CanonSnapshotORM)
                .filter(CanonSnapshotORM.project_id == changeset.project_id)
                .order_by(CanonSnapshotORM.version_no.desc())
                .first()
            )
            if latest_snapshot is None:
                raise ConflictError("当前项目尚未初始化 Canon Snapshot，无法应用 ChangeSet")

            snapshot_payload = {
                "rule_cards": deepcopy(latest_snapshot.rule_cards),
                "character_cards": deepcopy(latest_snapshot.character_cards),
                "relationship_edges": deepcopy(latest_snapshot.relationship_edges),
                "open_loops": deepcopy(latest_snapshot.open_loops),
                "timeline_events": deepcopy(latest_snapshot.timeline_events),
            }
            created_object_versions: list[Any] = []
            object_operations_applied = False

            for operation in changeset.patch_operations:
                kind = str(operation.get("kind", "snapshot")).lower()
                if kind == "snapshot":
                    self._apply_snapshot_patch_operation(snapshot_payload=snapshot_payload, operation=operation)
                elif kind == "object":
                    new_entity = self._apply_object_patch_operation(db=db, project_id=changeset.project_id, operation=operation, changeset=changeset)
                    if new_entity is not None:
                        created_object_versions.append(new_entity)
                        object_operations_applied = True
                else:
                    raise ConflictError(f"不支持的 patch kind: {kind}")

            if object_operations_applied:
                object_payload = object_service.build_current_canon_payload(
                    db=db,
                    project_id=changeset.project_id,
                    timeline_events=snapshot_payload["timeline_events"],
                )
                snapshot_payload.update(object_payload)

            new_snapshot = CanonSnapshotORM(
                project_id=latest_snapshot.project_id,
                title=f"{latest_snapshot.title}_from_{changeset.id[:8]}",
                version_no=latest_snapshot.version_no + 1,
                rule_cards=snapshot_payload["rule_cards"],
                character_cards=snapshot_payload["character_cards"],
                relationship_edges=snapshot_payload["relationship_edges"],
                open_loops=snapshot_payload["open_loops"],
                timeline_events=snapshot_payload["timeline_events"],
            )
            db.add(new_snapshot)
            db.flush()

            for entity in created_object_versions:
                if getattr(entity, "is_canon_bound", False) and getattr(entity, "lifecycle_status", "active") == "active":
                    entity.snapshot_id = new_snapshot.id

            changeset.status = ChangeSetStatus.APPLIED.value
            changeset.base_snapshot_id = latest_snapshot.id
            changeset.result_snapshot_id = new_snapshot.id
            changeset.applied_at = datetime.now(timezone.utc)
            if draft is not None and draft.project_id == changeset.project_id:
                chapter_state_service.transition(
                    db=db,
                    draft=draft,
                    to_status=ChapterStatus.CANON_APPLIED.value,
                    trigger_type="changeset_applied",
                    trigger_ref=changeset.id,
                    workflow_run_id=changeset.workflow_run_id,
                    trace_id=changeset.trace_id,
                    reason="ChangeSet 已落入 Canon Snapshot",
                    metadata={"result_snapshot_id": new_snapshot.id},
                )

            workflow_run_service.update_progress(db=db, run=changeset.workflow_run_id, current_step="changeset_applied")
            db.add(
                ImmutableLogORM(
                    event_type="changeset_applied",
                    project_id=changeset.project_id,
                    workflow_run_id=changeset.workflow_run_id,
                    trace_id=changeset.trace_id,
                    event_payload={
                        "changeset_id": changeset.id,
                        "base_snapshot_id": latest_snapshot.id,
                        "result_snapshot_id": new_snapshot.id,
                        "patch_count": len(changeset.patch_operations),
                        "object_version_count": len(created_object_versions),
                        "required_gate_names": changeset.required_gate_names,
                    },
                )
            )
            db.commit()
            db.refresh(changeset)
            logger.info("ChangeSet 应用成功", extra={"extra_fields": {"event": "changeset.apply", "status": "success", "workflow_run_id": changeset.workflow_run_id, "summary": f"changeset_id={changeset.id}"}})
            return ChangeSet.model_validate(changeset)
        except Exception as exc:
            db.rollback()
            workflow_run_service.mark_attention(
                db=db,
                run=changeset.workflow_run_id,
                current_step="changeset_apply_failed",
                reason="ChangeSet 应用失败，可修正后重试",
                extra_metadata={"changeset_id": changeset.id, "error": str(exc)},
            )
            db.commit()
            logger.exception("ChangeSet 应用失败", extra={"extra_fields": {"event": "changeset.apply", "status": "failed", "error_message": "ChangeSet 应用失败，请检查闸门与快照状态"}})
            raise

    def rollback(
        self,
        db: Session,
        changeset_id: str,
        *,
        rolled_back_by: str,
        reason: str,
        workflow_run_id: str | None = None,
        trace_id: str | None = None,
    ) -> ChangeSet:
        set_log_context(workflow_run_id=workflow_run_id, module="changeset_service", event="changeset.rollback", status="started")
        logger.info("开始回滚 ChangeSet", extra={"extra_fields": {"changeset_id": changeset_id}})
        changeset = db.get(ChangeSetORM, changeset_id)
        if changeset is None:
            raise NotFoundError("ChangeSet 不存在")
        if changeset.status != ChangeSetStatus.APPLIED.value:
            raise ConflictError("只有 applied 状态的 ChangeSet 才能回滚")
        if not changeset.base_snapshot_id or not changeset.result_snapshot_id:
            raise ConflictError("当前 ChangeSet 缺少快照引用，无法执行回滚")

        published = db.query(PublishedChapterORM).filter(PublishedChapterORM.changeset_id == changeset.id).first()
        if published is not None:
            raise ConflictError("当前 ChangeSet 已关联已发布章节，不能直接回滚；请先处理发布记录")

        base_snapshot = db.get(CanonSnapshotORM, changeset.base_snapshot_id)
        result_snapshot = db.get(CanonSnapshotORM, changeset.result_snapshot_id)
        if base_snapshot is None or result_snapshot is None:
            raise ConflictError("回滚所需的 Canon Snapshot 不存在")

        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == changeset.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        if latest_snapshot is None or latest_snapshot.id != result_snapshot.id:
            raise ConflictError("当前仅支持回滚最新一次已应用且仍是当前 Canon 的 ChangeSet")

        run = workflow_run_service.ensure_run(
            db=db,
            project_id=changeset.project_id,
            workflow_run_id=workflow_run_id or changeset.workflow_run_id,
            trace_id=trace_id or changeset.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="changeset_rollback",
            source_type="changeset",
            source_ref=changeset.id,
        )

        rollback_time = datetime.now(timezone.utc)
        reverted_object_count = 0
        for object_type, model_class in _OBJECT_TYPE_TO_MODEL.items():
            applied_versions = (
                db.query(model_class)
                .filter(model_class.project_id == changeset.project_id, model_class.source_ref == changeset.id)
                .order_by(model_class.logical_object_id.asc(), model_class.version_no.asc())
                .all()
            )
            grouped: dict[str, list[Any]] = {}
            for entity in applied_versions:
                grouped.setdefault(entity.logical_object_id, []).append(entity)
            for logical_object_id, versions in grouped.items():
                earliest = versions[0]
                predecessor = db.get(model_class, earliest.predecessor_version_id) if earliest.predecessor_version_id else None
                for entity in versions:
                    entity.is_current_version = False
                    entity.superseded_at = entity.superseded_at or rollback_time
                    if entity.predecessor_version_id is None:
                        entity.retired_at = entity.retired_at or rollback_time
                        entity.lifecycle_status = "retired"
                if predecessor is not None:
                    predecessor.is_current_version = True
                    predecessor.superseded_at = None
                reverted_object_count += len(versions)
                db.add(
                    ImmutableLogORM(
                        event_type="object_versions_rolled_back",
                        project_id=changeset.project_id,
                        workflow_run_id=run.id,
                        trace_id=run.trace_id,
                        event_payload={
                            "changeset_id": changeset.id,
                            "object_type": object_type,
                            "logical_object_id": logical_object_id,
                            "rolled_back_version_ids": [entity.id for entity in versions],
                            "restored_predecessor_version_id": getattr(predecessor, "id", None),
                        },
                    )
                )

        rollback_snapshot = CanonSnapshotORM(
            project_id=base_snapshot.project_id,
            title=f"{base_snapshot.title}_rollback_{changeset.id[:8]}",
            version_no=latest_snapshot.version_no + 1,
            rule_cards=deepcopy(base_snapshot.rule_cards),
            character_cards=deepcopy(base_snapshot.character_cards),
            relationship_edges=deepcopy(base_snapshot.relationship_edges),
            open_loops=deepcopy(base_snapshot.open_loops),
            timeline_events=deepcopy(base_snapshot.timeline_events),
        )
        db.add(rollback_snapshot)
        db.flush()

        changeset.status = ChangeSetStatus.ROLLED_BACK.value

        draft = db.get(ChapterDraftORM, changeset.source_ref)
        if draft is not None and draft.project_id == changeset.project_id and draft.status != ChapterStatus.PUBLISHED.value:
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.APPROVED.value,
                trigger_type="changeset_rolled_back",
                trigger_ref=changeset.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                reason="ChangeSet 已回滚，正文返回已审稿状态",
                metadata={
                    "rollback_snapshot_id": rollback_snapshot.id,
                    "rolled_back_by": rolled_back_by,
                    "rollback_reason": reason,
                },
            )

        workflow_run_service.mark_attention(
            db=db,
            run=run,
            current_step="changeset_rolled_back",
            reason="ChangeSet 已回滚，请重新审阅后再决定是否生成新的 ChangeSet",
            extra_metadata={
                "changeset_id": changeset.id,
                "rollback_snapshot_id": rollback_snapshot.id,
                "rolled_back_by": rolled_back_by,
                "rollback_reason": reason,
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="changeset_rolled_back",
                project_id=changeset.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "changeset_id": changeset.id,
                    "base_snapshot_id": changeset.base_snapshot_id,
                    "result_snapshot_id": changeset.result_snapshot_id,
                    "rollback_snapshot_id": rollback_snapshot.id,
                    "rolled_back_by": rolled_back_by,
                    "rollback_reason": reason,
                    "reverted_object_count": reverted_object_count,
                },
            )
        )
        db.commit()
        db.refresh(changeset)
        logger.info("ChangeSet 回滚完成", extra={"extra_fields": {"event": "changeset.rollback", "status": "success", "workflow_run_id": run.id, "summary": f"changeset_id={changeset.id}"}})
        schema = ChangeSet.model_validate(changeset)
        return schema.model_copy(update={
            "rolled_back_at": rollback_time,
            "rolled_back_by": rolled_back_by,
            "rollback_reason": reason,
            "rollback_snapshot_id": rollback_snapshot.id,
        })

    def list_changesets(self, db: Session) -> list[ChangeSet]:
        items = db.query(ChangeSetORM).order_by(ChangeSetORM.created_at.desc()).all()
        return [ChangeSet.model_validate(item) for item in items]

    def _ensure_proposal_gate_requirements(self, db: Session, project_id: str, draft_id: str) -> None:
        reviews = (
            db.query(GateReviewORM)
            .filter(
                GateReviewORM.project_id == project_id,
                GateReviewORM.draft_id == draft_id,
                GateReviewORM.passed.is_(True),
            )
            .order_by(GateReviewORM.created_at.desc())
            .all()
        )
        passed_gate_names = {review.gate_name for review in reviews}
        missing = [gate_name for gate_name in self._REQUIRED_PROPOSAL_GATES if gate_name not in passed_gate_names]
        if missing:
            raise ConflictError(f"ChangeSet 提议尚未满足前置 Gate，缺少通过的 Gate: {', '.join(missing)}")

    def _infer_affected_domains(self, patch_operations: list[dict[str, Any]]) -> list[str]:
        domains: list[str] = []
        for operation in patch_operations:
            kind = str(operation.get("kind", "snapshot")).lower()
            if kind == "snapshot":
                field = str(operation.get("field") or operation.get("path") or "")
                if field and field not in domains:
                    domains.append(field)
            elif kind == "object":
                object_type = str(operation.get("object_type") or "object")
                if object_type and object_type not in domains:
                    domains.append(object_type)
        return domains

    def _build_rule_based_proposal(self, draft: ChapterDraftORM, blueprint: ChapterBlueprintORM, request: GenerateChangeSetProposalRequest, excerpt: str) -> dict[str, Any]:
        chapter_no = draft.draft_metadata.get("chapter_no") if isinstance(draft.draft_metadata, dict) else None
        uncertain_items: list[str] = []
        if "占位" in (draft.content or ""):
            uncertain_items.append("正文仍带占位痕迹，建议人工核对后再审批 ChangeSet")
        return {
            "proposal_summary": f"基于第{chapter_no or '?'}章正文，生成最小 ChangeSet 提议。",
            "rationale": (request.rationale or "以最小可验证原则提取本章的时间线推进事件，避免在 P0 阶段过度自动入史。"),
            "extracted_changes": [
                f"第{chapter_no or '?'}章发生了新的章节推进事件",
                f"章蓝图《{blueprint.title_hint or '未命名蓝图'}》在正文中得到承接",
            ],
            "uncertain_items": uncertain_items,
            "evidence_refs": [
                {
                    "source_type": "chapter_draft",
                    "source_ref": draft.id,
                    "excerpt": excerpt,
                    "note": "正文开头片段，可用于人工复核 ChangeSet 提议。",
                }
            ],
            "review_recommendation": "human_review" if uncertain_items else "semi_auto_review",
            "patch_operations": [
                {
                    "kind": "snapshot",
                    "op": "append",
                    "field": "timeline_events",
                    "value": {
                        "chapter_no": chapter_no,
                        "event_type": "chapter_progress",
                        "title": blueprint.title_hint or f"第{chapter_no or '?'}章推进",
                        "summary": blueprint.summary or "本章推进了当前卷目标。",
                        "source_draft_id": draft.id,
                        "source_blueprint_id": blueprint.id,
                    },
                }
            ],
        }

    def _validate_patch_operations(self, patch_operations: list[dict[str, Any]]) -> None:
        if not patch_operations:
            raise ConflictError("ChangeSet 至少需要一个 patch operation")
        for operation in patch_operations:
            kind = str(operation.get("kind", "snapshot")).lower()
            if kind == "snapshot":
                field = operation.get("field") or operation.get("path")
                if field not in _ALLOWED_SNAPSHOT_FIELDS:
                    raise ConflictError(f"不支持的 Canon 字段更新: {field}")
            elif kind == "object":
                object_type = str(operation.get("object_type", ""))
                if object_type not in _OBJECT_TYPE_TO_MODEL:
                    raise ConflictError(f"不支持的对象类型: {object_type}")
                op = str(operation.get("op", "")).lower()
                if op not in {"create_object", "create_version", "restore_version", "retire_version"}:
                    raise ConflictError(f"不支持的对象 patch op: {op}")
            else:
                raise ConflictError(f"不支持的 patch kind: {kind}")

    def _infer_required_gate_names(self, source_type: str, patch_operations: list[dict[str, Any]]) -> list[str]:
        has_snapshot_patch = any(str(operation.get("kind", "snapshot")).lower() == "snapshot" for operation in patch_operations)
        source_type_lower = source_type.lower()
        if has_snapshot_patch or source_type_lower.startswith(_CHAPTER_CHANGESET_PREFIXES):
            return [GateName.SCHEMA.value, GateName.CANON.value]
        return []

    def _ensure_gate_requirements(self, db: Session, changeset: ChangeSetORM) -> None:
        if not changeset.required_gate_names:
            return
        reviews = (
            db.query(GateReviewORM)
            .filter(
                GateReviewORM.project_id == changeset.project_id,
                GateReviewORM.draft_id == changeset.source_ref,
                GateReviewORM.passed.is_(True),
            )
            .order_by(GateReviewORM.created_at.desc())
            .all()
        )
        passed_gate_names = {review.gate_name for review in reviews}
        missing = [gate_name for gate_name in changeset.required_gate_names if gate_name not in passed_gate_names]
        if missing:
            raise ConflictError(f"ChangeSet 尚未满足 Gate 前置条件，缺少通过的 Gate: {', '.join(missing)}")

    def _apply_snapshot_patch_operation(self, snapshot_payload: dict[str, Any], operation: dict[str, Any]) -> None:
        op = str(operation.get("op", "append")).lower()
        field = operation.get("field") or operation.get("path")
        if field not in _ALLOWED_SNAPSHOT_FIELDS:
            raise ConflictError(f"不支持的 Canon 字段更新: {field}")
        value = operation.get("value")
        if op == "append":
            snapshot_payload[field].append(value)
        elif op == "extend":
            if not isinstance(value, list):
                raise ConflictError(f"extend 操作要求 value 为列表: {field}")
            snapshot_payload[field].extend(value)
        elif op == "replace":
            snapshot_payload[field] = value
        else:
            raise ConflictError(f"不支持的 patch op: {op}")

    def _apply_object_patch_operation(self, db: Session, project_id: str, operation: dict[str, Any], changeset: ChangeSetORM) -> Any:
        op = str(operation.get("op", "")).lower()
        if op == "create_object":
            return self._apply_object_create_initial(db=db, project_id=project_id, operation=operation, changeset=changeset)
        if op == "create_version":
            return self._apply_object_create_version(db=db, project_id=project_id, operation=operation, changeset=changeset)
        if op == "restore_version":
            return self._apply_object_restore_version(db=db, project_id=project_id, operation=operation, changeset=changeset)
        if op == "retire_version":
            return self._apply_object_retire_version(db=db, project_id=project_id, operation=operation, changeset=changeset)
        raise ConflictError(f"不支持的对象 patch op: {op}")

    def _apply_object_create_initial(self, db: Session, project_id: str, operation: dict[str, Any], changeset: ChangeSetORM) -> Any:
        object_type = str(operation.get("object_type", ""))
        model_class = _OBJECT_TYPE_TO_MODEL.get(object_type)
        if model_class is None:
            raise ConflictError(f"不支持的对象类型: {object_type}")
        bind_to_canon = bool(operation.get("bind_to_canon", True))
        payload = dict(operation.get("value") or {})
        logical_object_id = operation.get("logical_object_id")
        if logical_object_id:
            existing = (
                db.query(model_class)
                .filter(model_class.project_id == project_id, model_class.logical_object_id == logical_object_id, model_class.is_current_version.is_(True))
                .first()
            )
            if existing is not None:
                raise ConflictError(f"逻辑对象已存在当前版本: {logical_object_id}")
        if object_type == "relationship_edge":
            payload["source_character_id"] = object_service.resolve_character_logical_id(db, project_id, payload["source_character_id"])
            payload["target_character_id"] = object_service.resolve_character_logical_id(db, project_id, payload["target_character_id"])
        entity = model_class(
            logical_object_id=logical_object_id,
            predecessor_version_id=None,
            project_id=project_id,
            snapshot_id=None,
            version_no=1,
            is_current_version=True,
            superseded_at=None,
            retired_at=datetime.now(timezone.utc) if payload.get("lifecycle_status") == "retired" else None,
            lifecycle_status=payload.get("lifecycle_status", "active"),
            change_reason=changeset.rationale,
            source_type="changeset_create",
            source_ref=changeset.id,
            is_canon_bound=bind_to_canon,
            **self._serialize_object_fields(object_type, payload),
        )
        db.add(entity)
        db.flush()
        db.add(
            ImmutableLogORM(
                event_type="object_initial_version_created",
                project_id=project_id,
                workflow_run_id=changeset.workflow_run_id,
                trace_id=changeset.trace_id,
                event_payload={
                    "changeset_id": changeset.id,
                    "object_type": object_type,
                    "logical_object_id": entity.logical_object_id,
                    "new_version_id": entity.id,
                    "new_version_no": entity.version_no,
                    "lifecycle_status": entity.lifecycle_status,
                },
            )
        )
        return entity

    def _apply_object_create_version(self, db: Session, project_id: str, operation: dict[str, Any], changeset: ChangeSetORM) -> Any:
        object_type, logical_object_id, model_class, current_entity = self._resolve_current_entity(db=db, project_id=project_id, operation=operation)
        expected_version_no = operation.get("expected_version_no")
        if expected_version_no is not None and int(expected_version_no) != int(current_entity.version_no):
            raise ConflictError(f"对象版本冲突: logical_object_id={logical_object_id}, expected={expected_version_no}, actual={current_entity.version_no}")

        payload = dict(operation.get("value") or {})
        bind_to_canon = operation.get("bind_to_canon")
        if bind_to_canon is None:
            bind_to_canon = bool(current_entity.is_canon_bound)

        base_payload = self._extract_entity_payload(current_entity, object_type)
        merged_payload = {**base_payload, **payload}

        return self._spawn_object_version(
            db=db,
            changeset=changeset,
            project_id=project_id,
            object_type=object_type,
            model_class=model_class,
            current_entity=current_entity,
            payload=merged_payload,
            bind_to_canon=bool(bind_to_canon),
            lifecycle_status=merged_payload.get("lifecycle_status", "active"),
            event_type="object_version_created",
            event_extra={},
            source_type="changeset_apply",
        )

    def _apply_object_restore_version(self, db: Session, project_id: str, operation: dict[str, Any], changeset: ChangeSetORM) -> Any:
        object_type, logical_object_id, model_class, current_entity = self._resolve_current_entity(db=db, project_id=project_id, operation=operation)
        expected_current_version_no = operation.get("expected_current_version_no")
        if expected_current_version_no is not None and int(expected_current_version_no) != int(current_entity.version_no):
            raise ConflictError(f"对象当前版本冲突: logical_object_id={logical_object_id}, expected={expected_current_version_no}, actual={current_entity.version_no}")

        target_entity = self._resolve_restore_target(
            db=db,
            model_class=model_class,
            project_id=project_id,
            logical_object_id=logical_object_id,
            restore_from_version_id=operation.get("restore_from_version_id"),
            restore_from_version_no=operation.get("restore_from_version_no"),
        )
        if target_entity.id == current_entity.id:
            raise ConflictError("恢复目标已经是当前版本，无需回滚")

        bind_to_canon = operation.get("bind_to_canon")
        if bind_to_canon is None:
            bind_to_canon = bool(current_entity.is_canon_bound)

        payload = self._extract_entity_payload(target_entity, object_type)
        restored_status = payload.get("lifecycle_status", "active")
        if restored_status == "retired":
            restored_status = "active"
            payload["lifecycle_status"] = restored_status
            bind_to_canon = True

        return self._spawn_object_version(
            db=db,
            changeset=changeset,
            project_id=project_id,
            object_type=object_type,
            model_class=model_class,
            current_entity=current_entity,
            payload=payload,
            bind_to_canon=bool(bind_to_canon),
            lifecycle_status=restored_status,
            event_type="object_version_restored",
            event_extra={
                "restored_from_version_id": target_entity.id,
                "restored_from_version_no": target_entity.version_no,
            },
            source_type="changeset_restore",
        )

    def _apply_object_retire_version(self, db: Session, project_id: str, operation: dict[str, Any], changeset: ChangeSetORM) -> Any:
        object_type, logical_object_id, model_class, current_entity = self._resolve_current_entity(db=db, project_id=project_id, operation=operation)
        expected_current_version_no = operation.get("expected_current_version_no")
        if expected_current_version_no is not None and int(expected_current_version_no) != int(current_entity.version_no):
            raise ConflictError(f"对象当前版本冲突: logical_object_id={logical_object_id}, expected={expected_current_version_no}, actual={current_entity.version_no}")
        if getattr(current_entity, "lifecycle_status", "active") == "retired":
            raise ConflictError("对象当前版本已经是 retired 状态，无需重复失效")

        payload = self._extract_entity_payload(current_entity, object_type)
        payload["lifecycle_status"] = "retired"

        return self._spawn_object_version(
            db=db,
            changeset=changeset,
            project_id=project_id,
            object_type=object_type,
            model_class=model_class,
            current_entity=current_entity,
            payload=payload,
            bind_to_canon=False,
            lifecycle_status="retired",
            event_type="object_version_retired",
            event_extra={"retire_reason": operation.get("retire_reason")},
            source_type="changeset_retire",
        )

    def _resolve_current_entity(self, db: Session, project_id: str, operation: dict[str, Any]) -> tuple[str, str, Any, Any]:
        object_type = str(operation.get("object_type", ""))
        logical_object_id = str(operation.get("logical_object_id", ""))
        model_class = _OBJECT_TYPE_TO_MODEL.get(object_type)
        if model_class is None:
            raise ConflictError(f"不支持的对象类型: {object_type}")
        if not logical_object_id:
            raise ConflictError("对象 patch 必须包含 logical_object_id")

        current_entity = (
            db.query(model_class)
            .filter(
                model_class.project_id == project_id,
                model_class.logical_object_id == logical_object_id,
                model_class.is_current_version.is_(True),
            )
            .first()
        )
        if current_entity is None:
            raise NotFoundError(f"对象不存在或当前版本不可用: {logical_object_id}")
        return object_type, logical_object_id, model_class, current_entity

    def _resolve_restore_target(self, db: Session, model_class: Any, project_id: str, logical_object_id: str, restore_from_version_id: str | None, restore_from_version_no: int | None) -> Any:
        selector_count = sum([restore_from_version_id is not None, restore_from_version_no is not None])
        if selector_count != 1:
            raise ConflictError("恢复版本必须且只能指定 version_id 或 version_no 其中之一")

        query = db.query(model_class).filter(model_class.project_id == project_id, model_class.logical_object_id == logical_object_id)
        if restore_from_version_id is not None:
            query = query.filter(model_class.id == str(restore_from_version_id))
        else:
            query = query.filter(model_class.version_no == int(restore_from_version_no))

        target_entity = query.first()
        if target_entity is None:
            raise NotFoundError(f"未找到要恢复的历史版本: logical_object_id={logical_object_id}")
        return target_entity

    def _spawn_object_version(
        self,
        db: Session,
        changeset: ChangeSetORM,
        project_id: str,
        object_type: str,
        model_class: Any,
        current_entity: Any,
        payload: dict[str, Any],
        bind_to_canon: bool,
        lifecycle_status: str,
        event_type: str,
        event_extra: dict[str, Any],
        source_type: str,
    ) -> Any:
        if object_type == "relationship_edge":
            payload["source_character_id"] = object_service.resolve_character_logical_id(db, project_id, payload["source_character_id"])
            payload["target_character_id"] = object_service.resolve_character_logical_id(db, project_id, payload["target_character_id"])

        current_entity.is_current_version = False
        current_entity.superseded_at = datetime.now(timezone.utc)

        new_entity = model_class(
            logical_object_id=current_entity.logical_object_id,
            predecessor_version_id=current_entity.id,
            project_id=current_entity.project_id,
            snapshot_id=None,
            version_no=current_entity.version_no + 1,
            is_current_version=True,
            superseded_at=None,
            retired_at=datetime.now(timezone.utc) if lifecycle_status == "retired" else None,
            lifecycle_status=lifecycle_status,
            change_reason=changeset.rationale,
            source_type=source_type,
            source_ref=changeset.id,
            is_canon_bound=bool(bind_to_canon),
            **self._serialize_object_fields(object_type, payload),
        )
        db.add(new_entity)
        db.flush()

        event_payload = {
            "changeset_id": changeset.id,
            "object_type": object_type,
            "logical_object_id": current_entity.logical_object_id,
            "previous_version_id": current_entity.id,
            "new_version_id": new_entity.id,
            "new_version_no": new_entity.version_no,
            "lifecycle_status": lifecycle_status,
            **event_extra,
        }
        db.add(ImmutableLogORM(event_type=event_type, project_id=project_id, workflow_run_id=changeset.workflow_run_id, trace_id=changeset.trace_id, event_payload=event_payload))
        return new_entity

    def _extract_entity_payload(self, entity: Any, object_type: str) -> dict[str, Any]:
        if object_type == "character_card":
            return {
                "character_name": entity.character_name,
                "role_tags": list(entity.role_tags),
                "current_state": deepcopy(entity.current_state),
                "lifecycle_status": getattr(entity, "lifecycle_status", "active"),
            }
        if object_type == "rule_card":
            return {
                "rule_name": entity.rule_name,
                "description": entity.description,
                "severity": entity.severity,
                "lifecycle_status": getattr(entity, "lifecycle_status", "active"),
            }
        if object_type == "open_loop_card":
            return {
                "loop_name": entity.loop_name,
                "status": entity.status,
                "lifecycle_status": getattr(entity, "lifecycle_status", "active"),
            }
        if object_type == "relationship_edge":
            return {
                "source_character_id": entity.source_character_id,
                "target_character_id": entity.target_character_id,
                "relation_type": entity.relation_type,
                "relation_stage": entity.relation_stage,
                "metadata": deepcopy(entity.relation_metadata),
                "lifecycle_status": getattr(entity, "lifecycle_status", "active"),
            }
        raise ConflictError(f"不支持的对象类型: {object_type}")

    def _serialize_object_fields(self, object_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if object_type == "character_card":
            return {
                "character_name": payload["character_name"],
                "role_tags": payload.get("role_tags", []),
                "current_state": payload.get("current_state", {}),
            }
        if object_type == "rule_card":
            return {
                "rule_name": payload["rule_name"],
                "description": payload["description"],
                "severity": payload.get("severity", "hard"),
            }
        if object_type == "open_loop_card":
            return {
                "loop_name": payload["loop_name"],
                "status": payload.get("status", "open"),
            }
        if object_type == "relationship_edge":
            return {
                "source_character_id": payload["source_character_id"],
                "target_character_id": payload["target_character_id"],
                "relation_type": payload["relation_type"],
                "relation_stage": payload.get("relation_stage", "established"),
                "relation_metadata": payload.get("metadata", {}),
            }
        raise ConflictError(f"不支持的对象类型: {object_type}")


changeset_service = ChangeSetService()
