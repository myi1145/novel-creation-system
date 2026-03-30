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
        return [AgentCallLog.model_validate(row) for row in rows]

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

        return AgentCallStats(
            total_calls=total_calls,
            success_calls=success_calls,
            fallback_success_calls=fallback_success_calls,
            error_calls=error_calls,
            timeout_error_calls=timeout_error_calls,
            rate_limited_calls=rate_limited_calls,
        )


agent_call_service = AgentCallService()
