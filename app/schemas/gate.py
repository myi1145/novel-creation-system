from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import GateName
from app.schemas.chapter import SeedConsumptionReport
from app.schemas.creative_object import StructuredCreativeObject


def _dedupe_ids(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


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
    metadata: dict = Field(default_factory=dict)


class CharacterVoiceIssue(BaseModel):
    issue_type: str
    character_name: str
    related_character_name: str | None = None
    severity: str
    location_hint: str
    evidence_excerpt: str
    explanation: str
    suggested_action: str


class CharacterVoiceReport(BaseModel):
    chapter_no: int
    evaluated_characters: list[str] = Field(default_factory=list)
    issue_count: int = 0
    highest_severity: str = "S0"
    issues: list[CharacterVoiceIssue] = Field(default_factory=list)
    summary: str = ""


class GateReviewResult(StructuredCreativeObject):
    object_type: str = "gate_review_result"
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
    seed_consumption_report: SeedConsumptionReport | None = None
    character_voice_report: CharacterVoiceReport | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def normalize_protocol(self) -> "GateReviewResult":
        self.lifecycle_stage = self.pass_status
        self.source_type = self.source_type or "gate_service"
        self.source_ref = self.source_ref or self.draft_id
        self.related_object_ids = _dedupe_ids([*self.related_object_ids, self.draft_id])
        self.extension_fields = {
            **self.extension_fields,
            "gate_name": self.gate_name.value if hasattr(self.gate_name, "value") else str(self.gate_name),
        }
        return self
