from sqlalchemy.orm import Session

from app.db.models import ProjectORM
from app.schemas.project import CreateProjectRequest, Project


class ProjectService:
    def create_project(self, db: Session, request: CreateProjectRequest) -> Project:
        project = ProjectORM(
            project_name=request.project_name,
            premise=request.premise,
            genre_id=request.genre_id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return Project.model_validate(project)

    def list_projects(self, db: Session) -> list[Project]:
        items = db.query(ProjectORM).order_by(ProjectORM.created_at.desc()).all()
        return [Project.model_validate(item) for item in items]


project_service = ProjectService()
