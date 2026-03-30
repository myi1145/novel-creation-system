from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import CanonSnapshotORM, ChapterBlueprintORM, ChapterDraftORM, GateReviewORM, PublishedChapterORM
from app.domain.enums import ChapterStatus
from app.schemas.gate import GateIssue, GateReviewResult, RunGateReviewRequest
from app.services.agent_gateway import agent_gateway
from app.services.chapter_state_service import chapter_state_service
from app.services.workflow_run_service import workflow_run_service


class GateService:
    REQUIRED_REVIEW_GATES = {"schema_gate", "canon_gate", "narrative_gate"}

    def run_reviews(self, db: Session, request: RunGateReviewRequest) -> list[GateReviewResult]:
        draft = db.get(ChapterDraftORM, request.draft_id)
        if draft is None or draft.project_id != request.project_id:
            raise NotFoundError("正文草稿不存在")
        if draft.status == ChapterStatus.PUBLISHED.value:
            raise ConflictError("已发布草稿不允许再次进入审查")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or draft.workflow_run_id,
            trace_id=request.trace_id or draft.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="gate_reviewing",
            source_type="chapter_draft",
            source_ref=draft.id,
        )
        if draft.status in {
            ChapterStatus.DRAFTING.value,
            ChapterStatus.REVIEW_FAILED.value,
            ChapterStatus.APPROVED.value,
            ChapterStatus.FAILED.value,
        }:
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.REVIEWING.value,
                trigger_type="gate_review_started",
                trigger_ref=draft.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                reason="进入 Gate 审查阶段",
                metadata={"gate_names": [gate.value for gate in request.gate_names]},
            )
        results: list[GateReviewResult] = []
        for gate_name in request.gate_names:
            results.append(
                self.run_single_gate(
                    db=db,
                    project_id=request.project_id,
                    draft_id=request.draft_id,
                    gate_name=gate_name.value,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                )
            )
        failed = any(item.pass_status == "failed" for item in results)
        if failed:
            failed_gate_names = [item.gate_name for item in results if item.pass_status == "failed"]
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.REVIEW_FAILED.value,
                trigger_type="gate_review_completed",
                trigger_ref=draft.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                reason="Gate 审查未通过",
                metadata={"failed_gate_names": failed_gate_names},
            )
            workflow_run_service.mark_attention(
                db=db,
                run=run,
                current_step="gate_failed",
                reason="Gate 审查存在失败项",
                extra_metadata={"failed_gate_names": failed_gate_names},
            )
        else:
            requested_names = {gate.value for gate in request.gate_names}
            if self.REQUIRED_REVIEW_GATES.issubset(requested_names):
                chapter_state_service.transition(
                    db=db,
                    draft=draft,
                    to_status=ChapterStatus.APPROVED.value,
                    trigger_type="gate_review_completed",
                    trigger_ref=draft.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    reason="关键 Gate 已通过",
                    metadata={"gate_names": sorted(requested_names)},
                )
                workflow_run_service.update_progress(db=db, run=run, current_step="gate_passed", status="running")
            else:
                workflow_run_service.update_progress(db=db, run=run, current_step="gate_partial_passed", status="running")
        db.commit()
        return results

    def run_single_gate(self, db: Session, project_id: str, draft_id: str, gate_name: str, workflow_run_id: str | None = None, trace_id: str | None = None) -> GateReviewResult:
        draft = db.get(ChapterDraftORM, draft_id)
        if draft is None or draft.project_id != project_id:
            raise NotFoundError("正文草稿不存在")
        blueprint = db.get(ChapterBlueprintORM, draft.blueprint_id)
        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=project_id,
            workflow_run_id=workflow_run_id or draft.workflow_run_id,
            trace_id=trace_id or draft.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step=f"gate_{gate_name}",
            source_type="chapter_draft",
            source_ref=draft.id,
        )
        result = self._evaluate_gate(db=db, gate_name=gate_name, draft=draft, blueprint=blueprint, latest_snapshot=latest_snapshot, run_id=run.id, trace_id=run.trace_id)
        review = GateReviewORM(
            project_id=project_id,
            draft_id=draft_id,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            gate_name=gate_name,
            pass_status=result.pass_status,
            passed=result.passed,
            highest_severity=result.highest_severity,
            recommended_route=result.recommended_route,
            can_override=result.can_override,
            override_role=result.override_role,
            issues=[issue.model_dump(mode="json") for issue in result.issues],
        )
        db.add(review)
        db.flush()
        workflow_run_service.update_progress(db=db, run=run, current_step=f"gate_{gate_name}_done")
        return GateReviewResult.model_validate(review)

    def _issue(
        self,
        *,
        severity: str,
        message: str,
        suggestion: str | None = None,
        category: str | None = None,
        summary: str | None = None,
        suggested_actions: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> GateIssue:
        return GateIssue(
            severity=severity,
            message=message,
            suggestion=suggestion,
            category=category,
            summary=summary,
            suggested_actions=suggested_actions or ([] if suggestion is None else [suggestion]),
            evidence_refs=evidence_refs or [],
        )

    def _evaluate_gate(self, db: Session, gate_name: str, draft: ChapterDraftORM, blueprint: ChapterBlueprintORM | None, latest_snapshot: CanonSnapshotORM | None, run_id: str, trace_id: str) -> GateReviewResult:
        issues: list[GateIssue] = []
        content = (draft.content or "").strip()

        if gate_name == "schema_gate":
            if not content:
                issues.append(self._issue(severity="S3", message="草稿内容为空", suggestion="重新生成正文草稿", category="schema_integrity", summary="正文主体缺失", evidence_refs=[f"draft:{draft.id}"]))
            if not draft.blueprint_id:
                issues.append(self._issue(severity="S3", message="草稿未关联章蓝图", suggestion="重新走章节生成链路", category="schema_integrity", summary="缺少蓝图引用", evidence_refs=[f"draft:{draft.id}"]))
        elif gate_name == "canon_gate":
            if latest_snapshot is None:
                issues.append(self._issue(severity="S3", message="项目尚未初始化 Canon Snapshot", suggestion="先初始化 Canon", category="canon_consistency", summary="Canon 基线缺失", evidence_refs=[f"project:{draft.project_id}"]))
            if blueprint is None:
                issues.append(self._issue(severity="S2", message="草稿缺少章蓝图上下文", suggestion="重新生成蓝图后再审查", category="canon_consistency", summary="上下文不足", evidence_refs=[f"draft:{draft.id}"]))
        elif gate_name == "narrative_gate":
            if blueprint is None:
                issues.append(self._issue(severity="S3", message="缺少正式章蓝图，无法确认叙事任务是否完成", suggestion="先完成蓝图选择后再进入正文与审查", category="narrative_completion", summary="未绑定正式蓝图", evidence_refs=[f"draft:{draft.id}"]))
            if not content:
                issues.append(self._issue(severity="S3", message="草稿为空，无法完成叙事目标", suggestion="先生成正文草稿", category="narrative_completion", summary="正文为空", evidence_refs=[f"draft:{draft.id}"]))
            elif len(content) < 120:
                issues.append(self._issue(severity="S2", message="草稿内容偏短，叙事任务完成度不足", suggestion="补充完整场景与推进段落后再审查", category="narrative_completion", summary="正文长度不足", evidence_refs=[f"draft:{draft.id}"]))
            if blueprint is not None and content:
                summary_tokens = {token for token in blueprint.summary.replace("，", " ").replace("。", " ").split() if token}
                overlap = sum(1 for token in summary_tokens if token in content)
                if summary_tokens and overlap == 0:
                    issues.append(self._issue(severity="S2", message="正文与蓝图摘要几乎无对应，存在偏题风险", suggestion="对照蓝图补齐本章功能、冲突与信息增量", category="narrative_alignment", summary="与蓝图对齐度偏低", evidence_refs=[f"blueprint:{blueprint.id}", f"draft:{draft.id}"]))
        elif gate_name == "style_gate":
            if len(content) < 40:
                issues.append(self._issue(severity="S2", message="草稿内容过短，无法进行稳定风格判断", suggestion="补充至少一段完整正文", category="style_quality", summary="样本不足", evidence_refs=[f"draft:{draft.id}"]))
        elif gate_name == "publish_gate":
            existing_publish = db.query(PublishedChapterORM).filter(PublishedChapterORM.draft_id == draft.id).first()
            if existing_publish is not None:
                issues.append(self._issue(severity="S3", message="该草稿已经存在已发布章节", suggestion="不要重复发布同一草稿", category="publish_integrity", summary="重复发布", evidence_refs=[f"published_chapter:{existing_publish.id}"]))
            if not content:
                issues.append(self._issue(severity="S3", message="空草稿不能发布", suggestion="先生成正文", category="publish_integrity", summary="空正文", evidence_refs=[f"draft:{draft.id}"]))
            elif len(content) < 80:
                issues.append(self._issue(severity="S2", message="草稿内容偏短，发布风险较高", suggestion="补充正文后再发布", category="publish_quality", summary="正文长度偏短", evidence_refs=[f"draft:{draft.id}"]))
            if blueprint is None:
                issues.append(self._issue(severity="S3", message="草稿缺少章蓝图，不能发布", suggestion="重新走章节生成链路", category="publish_integrity", summary="缺少蓝图引用", evidence_refs=[f"draft:{draft.id}"]))
        else:
            issues.append(self._issue(severity="S1", message=f"{gate_name} 当前缺少硬规则，仅执行 Agent Review。", suggestion="补充对应规则后可降低误报。", category="rule_coverage", summary="缺少硬规则实现"))

        hard_highest = self._highest_severity(issues)
        pass_status = "passed"
        recommended_route = "pass"
        can_override = False
        override_role = None
        if hard_highest in {"S3", "S4"}:
            pass_status = "failed"
            recommended_route = "rewrite"
        elif hard_highest == "S2":
            pass_status = "warning"
            recommended_route = "revise"
            can_override = True
            override_role = "author"
        elif hard_highest == "S1":
            pass_status = "warning"
            recommended_route = "review"
            can_override = True
            override_role = "editor"

        if content:
            review_result = agent_gateway.review_gate(
                db=db,
                context={
                    "project_id": draft.project_id,
                    "gate_name": gate_name,
                    "content": content,
                    "blueprint_summary": blueprint.summary if blueprint is not None else "",
                    "canon_summary": {
                        "version_no": getattr(latest_snapshot, "version_no", 0),
                        "character_count": len(getattr(latest_snapshot, "character_cards", []) or []),
                        "rule_count": len(getattr(latest_snapshot, "rule_cards", []) or []),
                        "open_loop_count": len(getattr(latest_snapshot, "open_loops", []) or []),
                    },
                },
                audit_context={
                    "project_id": draft.project_id,
                    "workflow_name": "chapter_cycle_workflow_v1",
                    "workflow_run_id": run_id,
                    "trace_id": trace_id,
                    "draft_id": draft.id,
                    "gate_name": gate_name,
                },
            )
            for item in review_result.payload.get("issues", []):
                issues.append(
                    self._issue(
                        severity=item.get("severity", "S1"),
                        message=item.get("message") or item.get("summary") or "Agent Review issue",
                        suggestion=item.get("suggestion"),
                        category=item.get("category"),
                        summary=item.get("summary"),
                        suggested_actions=item.get("suggested_actions") or ([item.get("suggestion")] if item.get("suggestion") else []),
                        evidence_refs=item.get("evidence_refs") or [],
                    )
                )
            combined_highest = self._highest_severity(issues)
            if combined_highest in {"S3", "S4"}:
                pass_status = "failed"
                recommended_route = "rewrite"
                can_override = False
                override_role = None
            elif combined_highest == "S2" and pass_status == "passed":
                pass_status = "warning"
                recommended_route = "revise"
                can_override = True
                override_role = "author"
            elif combined_highest == "S1" and pass_status == "passed":
                pass_status = "warning"
                recommended_route = "review"
                can_override = True
                override_role = "editor"
        highest_severity = self._highest_severity(issues)
        return GateReviewResult(
            id="",
            project_id=draft.project_id,
            draft_id=draft.id,
            workflow_run_id=run_id,
            trace_id=trace_id,
            gate_name=gate_name,
            pass_status=pass_status,
            passed=pass_status != "failed",
            highest_severity=highest_severity,
            recommended_route=recommended_route,
            can_override=can_override,
            override_role=override_role,
            issues=issues,
        )

    def _highest_severity(self, issues: list[GateIssue]) -> str:
        order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}
        highest = "S0"
        for issue in issues:
            if order.get(issue.severity, 0) > order.get(highest, 0):
                highest = issue.severity
        return highest


gate_service = GateService()
