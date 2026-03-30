from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.domain.enums import GateName
from app.schemas.common import IdentifiedModel


class RunGateReviewRequest(BaseModel):
    project_id: str
    draft_id: str
    gate_names: list[GateName] = Field(default_factory=lambda: [GateName.SCHEMA, GateName.CANON, GateName.NARRATIVE, GateName.STYLE])
    workflow_run_id: str | None = None
    trace_id: str | None = None


class GateIssue(BaseModel):
    severity: str
    message: str
    suggestion: str | None = None
    category: str | None = None
    summary: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class GateReviewResult(IdentifiedModel):
    project_id: str
    draft_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    gate_name: GateName
    pass_status: str
    passed: bool
    highest_severity: str = "S0"
    recommended_route: str = "pass"
    can_override: bool = False
    override_role: str | None = None
    issues: list[GateIssue] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
