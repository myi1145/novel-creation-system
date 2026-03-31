from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.business_logging import StepLogScope
from app.core.exceptions import NotFoundError
from app.core.logging_context import set_log_context
from app.db.session import get_db
from app.schemas.workflow import (
    ExecuteChapterCycleRequest,
    ExecuteChapterSequenceRequest,
    ManualContinueWorkflowRunRequest,
    ManualTakeoverRequest,
    MarkHumanReviewedRequest,
    PauseWorkflowRunRequest,
    ResumeWorkflowRunRequest,
)
from app.services.agent_call_service import agent_call_service
from app.services.workflow_service import workflow_service
from app.utils.response import success_response

router = APIRouter()


@router.get("/chapter-cycle/status")
def get_chapter_cycle_status(db: Session = Depends(get_db)) -> dict:
    status = workflow_service.get_chapter_pipeline_status(db=db)
    return success_response(data=status.model_dump(mode="json"))


@router.post("/chapter-cycle/execute")
def execute_chapter_cycle(request: ExecuteChapterCycleRequest, db: Session = Depends(get_db)) -> dict:
    set_log_context(project_id=request.project_id, chapter_no=request.chapter_no, workflow_run_id=request.workflow_run_id, module="workflow_router", event="execute_chapter_cycle", status="started")
    scope = StepLogScope(
        logger_name="workflow",
        module="workflow_router",
        event="execute_chapter_cycle",
        message_started="开始执行单章工作流",
        start_fields={"project_id": request.project_id, "chapter_no": request.chapter_no, "workflow_run_id": request.workflow_run_id},
    )
    try:
        data = workflow_service.execute_chapter_cycle(db=db, request=request)
        scope.success("单章工作流执行完成", workflow_run_id=data.get("run", {}).get("id"), chapter_no=request.chapter_no, current_step=data.get("run", {}).get("current_step"), next_action=data.get("next_action"))
        return success_response(data=data, message="单章主链执行完成")
    except Exception as exc:
        scope.failure("单章工作流执行失败", exc, workflow_run_id=request.workflow_run_id, chapter_no=request.chapter_no)
        raise




@router.post("/chapter-sequence/execute")
def execute_chapter_sequence(request: ExecuteChapterSequenceRequest, db: Session = Depends(get_db)) -> dict:
    set_log_context(project_id=request.project_id, chapter_no=request.start_chapter_no, workflow_run_id=request.workflow_run_id, module="workflow_router", event="execute_chapter_sequence", status="started")
    scope = StepLogScope(
        logger_name="workflow",
        module="workflow_router",
        event="execute_chapter_sequence",
        message_started="开始执行连续章节工作流",
        start_fields={"project_id": request.project_id, "chapter_no": request.start_chapter_no, "workflow_run_id": request.workflow_run_id},
    )
    try:
        data = workflow_service.execute_chapter_sequence(db=db, request=request)
        scope.success("连续章节工作流执行完成", workflow_run_id=data.get("run", {}).get("id"), chapter_no=request.start_chapter_no, stop_reason=data.get("stop_reason"), next_action=data.get("next_action"))
        return success_response(data=data, message="连续章节执行完成")
    except Exception as exc:
        scope.failure("连续章节工作流执行失败", exc, workflow_run_id=request.workflow_run_id, chapter_no=request.start_chapter_no)
        raise

@router.get("/chapter-sequence/reports/{workflow_run_id}")
def get_chapter_sequence_report(workflow_run_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.get_chapter_sequence_report(db=db, workflow_run_id=workflow_run_id))


@router.get("/agent-gateway/status")
def get_agent_gateway_status() -> dict:
    return success_response(data=workflow_service.get_agent_gateway_status())


@router.get("/agent-gateway/governance")
def get_agent_gateway_governance(db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.get_agent_governance(db=db))


@router.get("/agent-calls")
def list_agent_calls(
    project_id: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    call_status: str | None = Query(default=None),
    workflow_run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    data = workflow_service.list_agent_calls(db=db, project_id=project_id, agent_type=agent_type, call_status=call_status, workflow_run_id=workflow_run_id, limit=limit)
    return success_response(data=data)


@router.get("/agent-calls/stats")
def get_agent_call_stats(project_id: str | None = Query(default=None), workflow_run_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.get_agent_call_stats(db=db, project_id=project_id, workflow_run_id=workflow_run_id))


@router.get("/agent-calls/{log_id}")
def get_agent_call(log_id: str, db: Session = Depends(get_db)) -> dict:
    log = agent_call_service.get_log(db=db, log_id=log_id)
    if log is None:
        raise NotFoundError("Agent 调用日志不存在")
    return success_response(data=log.model_dump(mode="json"))


@router.get("/runs")
def list_workflow_runs(project_id: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.list_workflow_runs(db=db, project_id=project_id, limit=limit))


@router.get("/runs/{workflow_run_id}")
def get_workflow_run_detail(workflow_run_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.get_workflow_run_detail(db=db, workflow_run_id=workflow_run_id))


@router.post("/runs/pause")
def pause_workflow_run(request: PauseWorkflowRunRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.pause_workflow_run(db=db, request=request), message="工作流已暂停")


@router.post("/runs/resume")
def resume_workflow_run(request: ResumeWorkflowRunRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.resume_workflow_run(db=db, request=request), message="工作流已恢复")


@router.post("/runs/manual-takeover")
def request_manual_takeover(request: ManualTakeoverRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.request_manual_takeover(db=db, request=request), message="工作流已切换到人工审阅")


@router.post("/runs/mark-human-reviewed")
def mark_human_reviewed(request: MarkHumanReviewedRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.mark_human_reviewed(db=db, request=request), message="人工审阅结果已记录")


@router.post("/runs/manual-continue")
def manual_continue_workflow_run(request: ManualContinueWorkflowRunRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.manual_continue_workflow_run(db=db, request=request), message="工作流已人工续跑")


@router.get("/diagnostics/overview")
def get_workflow_diagnostics_overview(
    project_id: str | None = Query(default=None),
    workflow_run_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=workflow_service.get_diagnostics_overview(db=db, project_id=project_id, workflow_run_id=workflow_run_id))


@router.get("/diagnostics/runs/{workflow_run_id}")
def get_workflow_run_diagnostics(workflow_run_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(data=workflow_service.get_run_diagnostics(db=db, workflow_run_id=workflow_run_id))
