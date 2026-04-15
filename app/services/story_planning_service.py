from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import GenreProfileORM, ProjectORM, StoryPlanningORM
from app.schemas.story_planning import (
    StoryPlanningGenerateData,
    StoryPlanningGenerateRequest,
    StoryPlanningGenerateResponse,
    StoryPlanningResponse,
    StoryPlanningUpsert,
)
from app.services.agent_gateway import AgentGatewayError, agent_gateway


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

    def generate_story_planning(
        self,
        db: Session,
        project_id: str,
        request: StoryPlanningGenerateRequest | None = None,
    ) -> StoryPlanningGenerateResponse:
        project = db.get(ProjectORM, project_id)
        if project is None:
            raise NotFoundError("项目不存在")

        context = self._build_generation_context(db=db, project=project, request=request or StoryPlanningGenerateRequest())
        try:
            raw_payload = self._invoke_generation_gateway(db=db, context=context, project=project)
            generated = self._normalize_generated_payload(raw_payload)
        except ValidationError:
            raise
        except AgentGatewayError as exc:
            raise ValidationError("生成失败，请稍后重试。") from exc
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("生成失败，请稍后重试。") from exc

        return StoryPlanningGenerateResponse(
            project_id=project_id,
            generated=True,
            data=generated,
            message="全书规划草稿已生成。",
        )

    def _build_generation_context(
        self,
        db: Session,
        project: ProjectORM,
        request: StoryPlanningGenerateRequest,
    ) -> dict[str, Any]:
        genre_profile = None
        if project.genre_id:
            genre_profile = db.get(GenreProfileORM, project.genre_id)
        return {
            "project_id": project.id,
            "project_name": project.project_name,
            "premise": project.premise,
            "genre_id": project.genre_id or "unknown",
            "genre_name": (genre_profile.genre_name if genre_profile else project.genre_id) or "未指定题材",
            "genre_rule_summary": self._build_genre_rule_summary(genre_profile),
            "target_chapter_count": request.target_chapter_count,
            "tone": request.tone or "",
        }

    def _invoke_generation_gateway(self, db: Session, context: dict[str, Any], project: ProjectORM) -> Any:
        result = agent_gateway.generate_story_planning(
            db=db,
            context=context,
            audit_context={
                "project_id": project.id,
                "genre_id": project.genre_id,
                "workflow_name": "story_planning_generate",
            },
        )
        return result.payload

    def _normalize_generated_payload(self, payload: Any) -> StoryPlanningGenerateData:
        if not isinstance(payload, dict):
            raise ValidationError("生成失败，请稍后重试。")
        fields = ("worldview", "main_outline", "volume_plan", "core_seed_summary")
        values: dict[str, str] = {}
        for field in fields:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError("生成失败，请稍后重试。")
            values[field] = value.strip()
        return StoryPlanningGenerateData(**values)

    @staticmethod
    def _build_genre_rule_summary(genre_profile: GenreProfileORM | None) -> str:
        if genre_profile is None:
            return "未加载题材规则包，按项目题材与前提进行通用规划。"
        world_rules = genre_profile.world if isinstance(genre_profile.world, dict) else {}
        narrative_rules = genre_profile.narrative if isinstance(genre_profile.narrative, dict) else {}
        style_rules = genre_profile.style if isinstance(genre_profile.style, dict) else {}
        world_keywords = ", ".join(str(key) for key in list(world_rules.keys())[:5]) or "无"
        narrative_keywords = ", ".join(str(key) for key in list(narrative_rules.keys())[:5]) or "无"
        style_keywords = ", ".join(str(key) for key in list(style_rules.keys())[:5]) or "无"
        return (
            f"题材：{genre_profile.genre_name}。"
            f"世界规则关键词：{world_keywords}。"
            f"叙事规则关键词：{narrative_keywords}。"
            f"风格规则关键词：{style_keywords}。"
        )


story_planning_service = StoryPlanningService()
