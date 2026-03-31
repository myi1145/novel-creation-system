from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
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
    data = workflow_service.execute_chapter_cycle(db=db, request=request)
    stage_status = data.get("stage_status")
    message = "单章主链执行成功" if stage_status == "completed" else "单章主链本轮执行结束"
    return success_response(data=data, message=message)




@router.post("/chapter-sequence/execute")
def execute_chapter_sequence(request: ExecuteChapterSequenceRequest, db: Session = Depends(get_db)) -> dict:
    data = workflow_service.execute_chapter_sequence(db=db, request=request)
    stage_status = data.get("stage_status")
    if stage_status == "completed":
        message = "连续章节工作流执行成功"
    elif stage_status == "attention_required":
        message = "连续章节工作流已暂停，等待人工处理"
    elif stage_status == "failed":
        message = "连续章节工作流执行失败"
    else:
        message = "连续章节工作流本轮执行结束"
    return success_response(data=data, message=message)

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
