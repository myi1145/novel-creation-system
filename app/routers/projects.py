from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.project import CreateProjectRequest
from app.services.project_service import project_service
from app.utils.response import success_response

router = APIRouter()


@router.post("")
def create_project(request: CreateProjectRequest, db: Session = Depends(get_db)) -> dict:
    project = project_service.create_project(db=db, request=request)
    return success_response(data=project.model_dump(mode="json"), message="项目已创建")


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> dict:
    projects = [item.model_dump(mode="json") for item in project_service.list_projects(db=db)]
    return success_response(data=projects)
