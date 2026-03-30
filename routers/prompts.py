from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.prompt import CreatePromptTemplateRequest, PromptResolvePreviewRequest
from app.services.prompt_template_service import prompt_template_service
from app.utils.response import success_response

router = APIRouter()


@router.post('/templates/seed-defaults')
def seed_default_templates(db: Session = Depends(get_db)) -> dict:
    prompt_template_service.ensure_default_templates(db)
    return success_response(data={"seeded": True}, message='default prompt templates ensured')


@router.get('/templates')
def list_prompt_templates(
    template_key: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    action_name: str | None = Query(default=None),
    scope_type: str | None = Query(default=None),
    scope_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    items = prompt_template_service.list_templates(
        db=db,
        template_key=template_key,
        agent_type=agent_type,
        action_name=action_name,
        scope_type=scope_type,
        scope_key=scope_key,
        status=status,
    )
    return success_response(data=[item.model_dump(mode='json') for item in items], message='prompt templates fetched')


@router.post('/templates')
def create_prompt_template(request: CreatePromptTemplateRequest, db: Session = Depends(get_db)) -> dict:
    item = prompt_template_service.create_template(db=db, request=request)
    return success_response(data=item.model_dump(mode='json'), message='prompt template created')


@router.post('/templates/{template_id}/activate')
def activate_prompt_template(template_id: str, db: Session = Depends(get_db)) -> dict:
    item = prompt_template_service.activate_template(db=db, template_id=template_id)
    return success_response(data=item.model_dump(mode='json'), message='prompt template activated')


@router.post('/templates/resolve-preview')
def resolve_prompt_preview(request: PromptResolvePreviewRequest, db: Session = Depends(get_db)) -> dict:
    item = prompt_template_service.get_resolution_preview(
        db=db,
        project_id=request.project_id,
        genre_id=request.genre_id,
        agent_type=request.agent_type,
        action_name=request.action_name,
        provider_scope=request.provider_scope,
        render_context=request.render_context,
    )
    return success_response(data=item.model_dump(mode='json'), message='prompt template resolved')
