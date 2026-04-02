from pydantic import BaseModel, Field


class RevisionPolicyInput(BaseModel):
    gate_failures_before_revision: int
    gate_failures_after_revision: int
    highest_severity_before_revision: str = "S0"
    highest_severity_after_revision: str = "S0"
    revision_target_issue_types: list[str] = Field(default_factory=list)
    improved_issue_types: list[str] = Field(default_factory=list)
    revision_attempt_count: int = 0
    max_auto_revision_rounds: int = 1
    no_improvement_reason: str | None = None
    hard_blocking_exists: bool = False


class RevisionPolicyDecision(BaseModel):
    decision: str
    reason: str
    allow_next_revision: bool = False
    continue_pipeline: bool = False
    require_manual_review: bool = False
    improvement_detected: bool = False
    improvement_signals: list[str] = Field(default_factory=list)
    max_revision_reached: bool = False


class WorkflowRevisionPolicyService:
    _SEVERITY_ORDER = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}

    def _severity_decreased(self, before: str, after: str) -> bool:
        return self._SEVERITY_ORDER.get(str(after).upper(), 0) < self._SEVERITY_ORDER.get(str(before).upper(), 0)

    def evaluate(self, payload: RevisionPolicyInput) -> RevisionPolicyDecision:
        improvement_signals: list[str] = []
        if payload.gate_failures_after_revision < payload.gate_failures_before_revision:
            improvement_signals.append("gate_failures_reduced")
        if self._severity_decreased(payload.highest_severity_before_revision, payload.highest_severity_after_revision):
            improvement_signals.append("highest_severity_decreased")
        if payload.improved_issue_types:
            improvement_signals.append("targeted_issue_improved")
        improvement_detected = bool(improvement_signals)
        max_reached = payload.revision_attempt_count >= payload.max_auto_revision_rounds

        if payload.hard_blocking_exists:
            return RevisionPolicyDecision(
                decision="stop_for_manual_review",
                reason="hard_blocking_failure_after_revision",
                require_manual_review=True,
                improvement_detected=improvement_detected,
                improvement_signals=improvement_signals,
                max_revision_reached=max_reached,
            )
        if payload.gate_failures_after_revision == 0:
            return RevisionPolicyDecision(
                decision="continue_pipeline",
                reason="gates_passed_after_revision",
                continue_pipeline=True,
                improvement_detected=improvement_detected,
                improvement_signals=improvement_signals,
                max_revision_reached=max_reached,
            )
        if max_reached:
            return RevisionPolicyDecision(
                decision="stop_for_manual_review",
                reason="max_revision_rounds_reached",
                require_manual_review=True,
                improvement_detected=improvement_detected,
                improvement_signals=improvement_signals,
                max_revision_reached=True,
            )
        if not improvement_detected:
            return RevisionPolicyDecision(
                decision="stop_for_manual_review",
                reason=payload.no_improvement_reason or "no_improvement_detected",
                require_manual_review=True,
                improvement_detected=False,
                improvement_signals=[],
                max_revision_reached=max_reached,
            )
        return RevisionPolicyDecision(
            decision="retry_revision",
            reason="improvement_detected_but_gates_still_failed",
            allow_next_revision=True,
            improvement_detected=True,
            improvement_signals=improvement_signals,
            max_revision_reached=max_reached,
        )


workflow_revision_policy_service = WorkflowRevisionPolicyService()
