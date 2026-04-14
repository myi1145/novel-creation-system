from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import ProjectORM, StoryPlanningORM
from app.schemas.story_planning import StoryPlanningResponse, StoryPlanningUpsert


class StoryPlanningService:
    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    def get_story_planning(self, db: Session, project_id: str) -> StoryPlanningResponse | None:
        self._ensure_project_exists(db=db, project_id=project_id)
        item = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        if item is None:
            return None
        return StoryPlanningResponse.model_validate(item)

    def upsert_story_planning(self, db: Session, project_id: str, request: StoryPlanningUpsert) -> StoryPlanningResponse:
        self._ensure_project_exists(db=db, project_id=project_id)
        item = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        if item is None:
            item = StoryPlanningORM(
                project_id=project_id,
                worldview=request.worldview,
                main_outline=request.main_outline,
                volume_plan=request.volume_plan,
                core_seed_summary=request.core_seed_summary,
                planning_status=request.planning_status,
                last_update_source="manual",
            )
            db.add(item)
        else:
            item.worldview = request.worldview
            item.main_outline = request.main_outline
            item.volume_plan = request.volume_plan
            item.core_seed_summary = request.core_seed_summary
            item.planning_status = request.planning_status
            item.last_update_source = "manual"
            item.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(item)
        return StoryPlanningResponse.model_validate(item)


story_planning_service = StoryPlanningService()
