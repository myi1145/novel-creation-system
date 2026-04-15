from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import ProjectORM, StoryDirectoryORM, StoryPlanningORM
from app.schemas.story_directory import StoryDirectoryResponse, StoryDirectoryUpsert


class StoryDirectoryService:
    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    @staticmethod
    def _ensure_story_planning_exists(db: Session, story_planning_id: str, project_id: str) -> None:
        exists = (
            db.query(StoryPlanningORM.id)
            .filter(StoryPlanningORM.id == story_planning_id, StoryPlanningORM.project_id == project_id)
            .first()
        )
        if not exists:
            raise NotFoundError("关联的全书规划不存在")

    def get_story_directory(self, db: Session, project_id: str) -> StoryDirectoryResponse | None:
        self._ensure_project_exists(db=db, project_id=project_id)
        item = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_id).first()
        if item is None:
            return None
        return StoryDirectoryResponse.model_validate(item)

    def upsert_story_directory(self, db: Session, project_id: str, request: StoryDirectoryUpsert) -> StoryDirectoryResponse:
        self._ensure_project_exists(db=db, project_id=project_id)
        if request.story_planning_id:
            self._ensure_story_planning_exists(
                db=db,
                story_planning_id=request.story_planning_id,
                project_id=project_id,
            )

        item = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_id).first()
        chapter_items = [chapter.model_dump(mode="json") for chapter in request.chapter_items]
        if item is None:
            item = StoryDirectoryORM(
                project_id=project_id,
                story_planning_id=request.story_planning_id,
                directory_title=request.directory_title,
                directory_summary=request.directory_summary,
                directory_status=request.directory_status,
                chapter_items=chapter_items,
                last_update_source="manual",
            )
            db.add(item)
        else:
            item.story_planning_id = request.story_planning_id
            item.directory_title = request.directory_title
            item.directory_summary = request.directory_summary
            item.directory_status = request.directory_status
            item.chapter_items = chapter_items
            item.last_update_source = "manual"
            item.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(item)
        return StoryDirectoryResponse.model_validate(item)


story_directory_service = StoryDirectoryService()
