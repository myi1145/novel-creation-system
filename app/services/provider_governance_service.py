from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AgentCallLogORM, ProviderCircuitStateORM
from app.schemas.agent import ProviderCircuitState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ProviderPreflightResult:
    allowed: bool
    provider_name: str
    circuit_state: str
    reason: str | None = None
    rate_limited: bool = False


class ProviderGovernanceService:
    def get_or_create_state(self, db: Session, provider_name: str) -> ProviderCircuitStateORM:
        row = db.get(ProviderCircuitStateORM, provider_name)
        if row is None:
            row = ProviderCircuitStateORM(provider_name=provider_name)
            db.add(row)
            db.flush()
        return row

    def get_state(self, db: Session, provider_name: str) -> ProviderCircuitState | None:
        row = db.get(ProviderCircuitStateORM, provider_name)
        if row is None:
            return None
        return ProviderCircuitState.model_validate(row)

    def preflight(self, db: Session | None, provider_name: str) -> ProviderPreflightResult:
        if db is None or provider_name == "mock":
            return ProviderPreflightResult(allowed=True, provider_name=provider_name, circuit_state="closed")

        state = self.get_or_create_state(db, provider_name)
        now = utc_now()

        if settings.agent_enable_circuit_breaker:
            if state.current_state == "open":
                if state.cooldown_until and state.cooldown_until > now:
                    return ProviderPreflightResult(
                        allowed=False,
                        provider_name=provider_name,
                        circuit_state="open",
                        reason=f"熔断器打开中，冷却至 {state.cooldown_until.isoformat()}",
                    )
                state.current_state = "half_open"
                state.half_open_call_count = 0
                db.flush()

            if state.current_state == "half_open" and state.half_open_call_count >= settings.agent_circuit_half_open_max_calls:
                return ProviderPreflightResult(
                    allowed=False,
                    provider_name=provider_name,
                    circuit_state="half_open",
                    reason="半开状态探测次数已达上限，请等待下一轮冷却后再尝试。",
                )

        if settings.agent_enable_rate_limit:
            minute_ago = now - timedelta(minutes=1)
            count = (
                db.query(func.count(AgentCallLogORM.id))
                .filter(AgentCallLogORM.active_provider == provider_name)
                .filter(AgentCallLogORM.created_at >= minute_ago)
                .scalar()
            ) or 0
            if count >= settings.agent_rate_limit_per_minute:
                return ProviderPreflightResult(
                    allowed=False,
                    provider_name=provider_name,
                    circuit_state=state.current_state,
                    reason=f"最近一分钟请求数已达到 {settings.agent_rate_limit_per_minute} 次上限。",
                    rate_limited=True,
                )

        if state.current_state == "half_open":
            state.half_open_call_count += 1
            db.flush()

        return ProviderPreflightResult(allowed=True, provider_name=provider_name, circuit_state=state.current_state)

    def record_success(self, db: Session | None, provider_name: str) -> None:
        if db is None or provider_name == "mock":
            return
        state = self.get_or_create_state(db, provider_name)
        state.current_state = "closed"
        state.consecutive_failures = 0
        state.half_open_call_count = 0
        state.opened_at = None
        state.cooldown_until = None
        state.last_success_at = utc_now()
        db.flush()

    def record_failure(self, db: Session | None, provider_name: str, error_type: str | None, error_message: str | None) -> None:
        if db is None or provider_name == "mock":
            return
        state = self.get_or_create_state(db, provider_name)
        now = utc_now()
        state.last_failure_at = now
        state.last_error_type = error_type
        state.last_error_message = error_message
        state.consecutive_failures += 1
        state.half_open_call_count = 0
        if settings.agent_enable_circuit_breaker and state.consecutive_failures >= settings.agent_circuit_failure_threshold:
            state.current_state = "open"
            state.opened_at = now
            state.cooldown_until = now + timedelta(seconds=settings.agent_circuit_cooldown_seconds)
        db.flush()

    def get_governance_snapshot(self, db: Session | None, provider_name: str) -> dict:
        provider_state = self.get_state(db, provider_name) if db is not None else None
        return {
            "configured_provider": settings.agent_provider.strip().lower() or "mock",
            "active_provider": provider_name,
            "fallback_enabled": settings.agent_fallback_to_mock,
            "timeout_seconds": settings.agent_timeout_seconds,
            "max_retries": settings.agent_max_retries,
            "retry_backoff_ms": settings.agent_retry_backoff_ms,
            "retry_backoff_multiplier": settings.agent_retry_backoff_multiplier,
            "retryable_status_codes": sorted(settings.agent_retryable_status_codes),
            "rate_limit_enabled": settings.agent_enable_rate_limit,
            "rate_limit_per_minute": settings.agent_rate_limit_per_minute,
            "circuit_breaker_enabled": settings.agent_enable_circuit_breaker,
            "circuit_failure_threshold": settings.agent_circuit_failure_threshold,
            "circuit_cooldown_seconds": settings.agent_circuit_cooldown_seconds,
            "half_open_max_calls": settings.agent_circuit_half_open_max_calls,
            "provider_state": provider_state.model_dump(mode="json") if provider_state else None,
        }


provider_governance_service = ProviderGovernanceService()
