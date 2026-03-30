from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentCallLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    workflow_name: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None
    agent_type: str
    action_name: str
    configured_provider: str
    active_provider: str
    model_name: str
    prompt_template_id: str | None = None
    prompt_template_key: str | None = None
    prompt_template_version: int | None = None
    prompt_scope_type: str | None = None
    prompt_scope_key: str | None = None
    prompt_provider_scope: str | None = None
    fallback_used: bool
    call_status: str
    attempt_count: int = 1
    error_type: str | None = None
    circuit_state_at_call: str | None = None
    rate_limited: bool = False
    latency_ms: int
    request_summary: dict
    response_summary: dict
    source_metadata: dict
    error_message: str | None = None
    parse_decision: str | None = None
    parse_issue_count: int = 0
    parse_reask_count: int = 0
    parse_degraded: bool = False
    created_at: datetime


class AgentCallStats(BaseModel):
    total_calls: int
    success_calls: int
    fallback_success_calls: int
    error_calls: int
    timeout_error_calls: int = 0
    rate_limited_calls: int = 0
    parse_error_calls: int = 0
    degraded_success_calls: int = 0
    human_review_routed_calls: int = 0
    reask_calls: int = 0


class ProviderCircuitState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_name: str
    current_state: str
    consecutive_failures: int
    half_open_call_count: int
    opened_at: datetime | None = None
    cooldown_until: datetime | None = None
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_type: str | None = None
    last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentParseIssue(BaseModel):
    code: str
    severity: str
    level: str
    message: str
    field_path: str | None = None


class AgentParseReport(BaseModel):
    output_type: str
    expected_root: str
    decision: str
    route: str
    envelope_status: str
    issue_count: int = 0
    reask_count: int = 0
    degraded: bool = False
    repair_actions: list[str] = Field(default_factory=list)
    issues: list[AgentParseIssue] = Field(default_factory=list)



class AgentGatewayGovernanceSnapshot(BaseModel):
    configured_provider: str
    active_provider: str
    fallback_enabled: bool
    timeout_seconds: float
    max_retries: int
    retry_backoff_ms: int
    retry_backoff_multiplier: float
    retryable_status_codes: list[int] = Field(default_factory=list)
    rate_limit_enabled: bool
    rate_limit_per_minute: int
    circuit_breaker_enabled: bool
    circuit_failure_threshold: int
    circuit_cooldown_seconds: int
    half_open_max_calls: int
    provider_state: ProviderCircuitState | None = None
    recent_call_stats: AgentCallStats | None = None
