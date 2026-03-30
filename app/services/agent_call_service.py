from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AgentCallLogORM
from app.schemas.agent import AgentCallLog, AgentCallStats


class AgentCallService:
    def list_logs(
        self,
        db: Session,
        project_id: str | None = None,
        agent_type: str | None = None,
        call_status: str | None = None,
        workflow_run_id: str | None = None,
        limit: int = 50,
    ) -> list[AgentCallLog]:
        query = db.query(AgentCallLogORM)
        if project_id:
            query = query.filter(AgentCallLogORM.project_id == project_id)
        if agent_type:
            query = query.filter(AgentCallLogORM.agent_type == agent_type)
        if call_status:
            query = query.filter(AgentCallLogORM.call_status == call_status)
        if workflow_run_id:
            query = query.filter(AgentCallLogORM.workflow_run_id == workflow_run_id)
        rows = query.order_by(AgentCallLogORM.created_at.desc()).limit(max(1, min(limit, 200))).all()
        items: list[AgentCallLog] = []
        for row in rows:
            data = AgentCallLog.model_validate(row).model_dump()
            parse_report = ((row.response_summary or {}) if isinstance(row.response_summary, dict) else {}).get("parse_report") or {}
            data["parse_decision"] = parse_report.get("decision")
            data["parse_issue_count"] = int(parse_report.get("issue_count") or 0)
            data["parse_reask_count"] = int(parse_report.get("reask_count") or 0)
            data["parse_degraded"] = bool(parse_report.get("degraded", False))
            items.append(AgentCallLog.model_validate(data))
        return items

    def get_log(self, db: Session, log_id: str) -> AgentCallLog | None:
        row = db.get(AgentCallLogORM, log_id)
        if row is None:
            return None
        return AgentCallLog.model_validate(row)

    def get_stats(self, db: Session, project_id: str | None = None, workflow_run_id: str | None = None) -> AgentCallStats:
        query = db.query(AgentCallLogORM)
        if project_id:
            query = query.filter(AgentCallLogORM.project_id == project_id)
        if workflow_run_id:
            query = query.filter(AgentCallLogORM.workflow_run_id == workflow_run_id)

        total_calls = query.count()
        success_calls = query.filter(AgentCallLogORM.call_status == "success").count()
        fallback_success_calls = query.filter(AgentCallLogORM.call_status == "fallback_success").count()
        error_calls = query.filter(AgentCallLogORM.call_status == "error").count()
        timeout_error_calls = query.filter(AgentCallLogORM.error_type == "timeout").count()
        rate_limited_calls = query.filter(AgentCallLogORM.rate_limited.is_(True)).count()

        rows = query.all()
        parse_error_calls = 0
        degraded_success_calls = 0
        human_review_routed_calls = 0
        reask_calls = 0
        for row in rows:
            if (row.error_type or "").startswith("parse_"):
                parse_error_calls += 1
            parse_report = ((row.response_summary or {}) if isinstance(row.response_summary, dict) else {}).get("parse_report") or {}
            if parse_report.get("degraded"):
                degraded_success_calls += 1
            if parse_report.get("decision") == "human_review":
                human_review_routed_calls += 1
            reask_calls += int(parse_report.get("reask_count") or 0)

        return AgentCallStats(
            total_calls=total_calls,
            success_calls=success_calls,
            fallback_success_calls=fallback_success_calls,
            error_calls=error_calls,
            timeout_error_calls=timeout_error_calls,
            rate_limited_calls=rate_limited_calls,
            parse_error_calls=parse_error_calls,
            degraded_success_calls=degraded_success_calls,
            human_review_routed_calls=human_review_routed_calls,
            reask_calls=reask_calls,
        )


agent_call_service = AgentCallService()
