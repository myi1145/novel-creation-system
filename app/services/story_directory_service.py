from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import ProjectORM, StoryDirectoryORM, StoryPlanningORM
from app.schemas.story_directory import (
    StoryDirectoryGenerateData,
    StoryDirectoryGenerateRequest,
    StoryDirectoryGenerateResponse,
    StoryDirectoryResponse,
    StoryDirectoryUpsert,
)
from app.services.agent_gateway import AgentGatewayError, agent_gateway


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

    def generate_story_directory(
        self,
        db: Session,
        project_id: str,
        request: StoryDirectoryGenerateRequest | None = None,
    ) -> StoryDirectoryGenerateResponse:
        project = db.get(ProjectORM, project_id)
        if project is None:
            raise NotFoundError("项目不存在")

        planning = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        if planning is None:
            raise ValidationError("请先生成或保存全书规划")

        payload = request or StoryDirectoryGenerateRequest()
        context = self._build_generation_context(project=project, planning=planning, request=payload)
        try:
            result = agent_gateway.generate_story_directory(
                db=db,
                context=context,
                audit_context={
                    "project_id": project.id,
                    "genre_id": project.genre_id,
                    "workflow_name": "story_directory_generate",
                },
            )
            generated = self._normalize_generated_payload(result.payload)
        except ValidationError:
            raise
        except AgentGatewayError as exc:
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。") from exc
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。") from exc

        return StoryDirectoryGenerateResponse(
            project_id=project_id,
            generated=True,
            data=generated,
            message="章节目录草稿已生成。",
        )

    def _build_generation_context(
        self,
        *,
        project: ProjectORM,
        planning: StoryPlanningORM,
        request: StoryDirectoryGenerateRequest,
    ) -> dict[str, Any]:
        target_chapter_count = request.target_chapter_count
        if not isinstance(target_chapter_count, int) or target_chapter_count <= 0:
            target_chapter_count = self._infer_target_chapter_count(planning)
        return {
            "project_id": project.id,
            "project_name": project.project_name,
            "premise": project.premise,
            "genre_id": project.genre_id or "unknown",
            "worldview": planning.worldview,
            "main_outline": planning.main_outline,
            "volume_plan": planning.volume_plan,
            "core_seed_summary": planning.core_seed_summary,
            "target_chapter_count": target_chapter_count,
        }

    def _normalize_generated_payload(self, payload: Any) -> StoryDirectoryGenerateData:
        if not isinstance(payload, dict):
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")
        directory_title = str(payload.get("directory_title") or "").strip()
        directory_summary = str(payload.get("directory_summary") or "").strip()
        chapter_items = payload.get("chapter_items")
        if not directory_title or not directory_summary or not isinstance(chapter_items, list):
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")

        normalized_items: list[dict[str, Any]] = []
        for item in chapter_items:
            if not isinstance(item, dict):
                raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")
            chapter_no = item.get("chapter_no")
            chapter_title = str(item.get("chapter_title") or "").strip()
            if not isinstance(chapter_no, int) or chapter_no <= 0 or not chapter_title:
                raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")

            normalized_items.append(
                {
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "chapter_role": str(item.get("chapter_role") or "").strip(),
                    "chapter_goal": str(item.get("chapter_goal") or "").strip(),
                    "stage_label": str(item.get("stage_label") or "").strip(),
                    "required_entities": self._normalize_string_list(item.get("required_entities")),
                    "required_seed_points": self._normalize_string_list(item.get("required_seed_points")),
                    "foreshadow_constraints": self._normalize_string_list(item.get("foreshadow_constraints")),
                }
            )
        if not normalized_items:
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")

        return StoryDirectoryGenerateData(
            directory_title=directory_title,
            directory_summary=directory_summary,
            directory_status="draft",
            chapter_items=normalized_items,
        )

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValidationError("生成失败，请先确认已保存全书规划，或稍后重试。")
            text = item.strip()
            if text:
                normalized.append(text)
        return normalized

    @staticmethod
    def _infer_target_chapter_count(planning: StoryPlanningORM) -> int:
        match = re.search(r"(\d{1,3})", planning.volume_plan or "")
        if match:
            parsed = int(match.group(1))
            if parsed > 0:
                return parsed
        return 10


story_directory_service = StoryDirectoryService()
