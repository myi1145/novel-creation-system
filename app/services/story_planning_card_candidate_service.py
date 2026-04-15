from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import (
    ProjectORM,
    StoryDirectoryORM,
    StoryPlanningORM,
    StructuredCardCandidateORM,
    StructuredCharacterCardORM,
    StructuredFactionCardORM,
    StructuredLocationCardORM,
    TerminologyCardORM,
)
from app.schemas.structured_cards import (
    CardCandidateActionResponse,
    CardCandidateGenerateItem,
    CardCandidateGenerateReport,
    CardCandidateResponse,
)

CARD_TYPES = {"character", "terminology", "faction", "location"}
CANDIDATE_STATUS = {"pending", "confirmed", "skipped"}
SOURCE_TYPE = "story_planning_directory"

PREFIX_TO_TYPE = {
    "角色": "character",
    "术语": "terminology",
    "势力": "faction",
    "地点": "location",
}

ENTITY_FACTION_HINTS = ("宗", "门", "盟", "派", "帮", "会", "国", "朝", "宫", "殿", "阁", "府", "团", "军")
ENTITY_LOCATION_HINTS = ("镇", "城", "村", "山", "谷", "岭", "江", "河", "湖", "海", "岛", "洲", "原", "林", "境")


class StoryPlanningCardCandidateService:
    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"\s+", "", name).strip()

    @staticmethod
    def _split_bar(text: str) -> list[str]:
        return [part.strip() for part in re.split(r"[｜|]", text) if part.strip()]

    @classmethod
    def _infer_entity_card_type(cls, entity: str) -> str | None:
        name = cls._normalize_name(entity)
        if not name:
            return None
        if any(hint in name for hint in ENTITY_FACTION_HINTS):
            return "faction"
        if any(hint in name for hint in ENTITY_LOCATION_HINTS):
            return "location"
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            return "character"
        return None

    def _formal_card_exists(self, db: Session, project_id: str, card_type: str, name: str) -> bool:
        if card_type == "character":
            return db.query(StructuredCharacterCardORM.id).filter(
                StructuredCharacterCardORM.project_id == project_id,
                StructuredCharacterCardORM.name == name,
            ).first() is not None
        if card_type == "terminology":
            return db.query(TerminologyCardORM.id).filter(
                TerminologyCardORM.project_id == project_id,
                TerminologyCardORM.term == name,
            ).first() is not None
        if card_type == "faction":
            return db.query(StructuredFactionCardORM.id).filter(
                StructuredFactionCardORM.project_id == project_id,
                StructuredFactionCardORM.name == name,
            ).first() is not None
        return db.query(StructuredLocationCardORM.id).filter(
            StructuredLocationCardORM.project_id == project_id,
            StructuredLocationCardORM.name == name,
        ).first() is not None

    def _pending_candidate_exists(self, db: Session, project_id: str, card_type: str, name: str) -> bool:
        return db.query(StructuredCardCandidateORM.id).filter(
            StructuredCardCandidateORM.project_id == project_id,
            StructuredCardCandidateORM.card_type == card_type,
            StructuredCardCandidateORM.name == name,
            StructuredCardCandidateORM.status == "pending",
        ).first() is not None

    def _create_candidate(
        self,
        db: Session,
        project_id: str,
        source_id: str,
        card_type: str,
        name: str,
        summary: str,
        payload: dict[str, Any],
    ) -> StructuredCardCandidateORM:
        candidate = StructuredCardCandidateORM(
            project_id=project_id,
            source_type=SOURCE_TYPE,
            source_id=source_id,
            card_type=card_type,
            name=name,
            summary=summary,
            payload=payload,
            status="pending",
        )
        db.add(candidate)
        return candidate

    def generate_candidates(self, db: Session, project_id: str) -> CardCandidateGenerateReport:
        self._ensure_project_exists(db, project_id)
        planning = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        directory = db.query(StoryDirectoryORM).filter(StoryDirectoryORM.project_id == project_id).first()
        if planning is None and directory is None:
            raise ValidationError("未找到可用于生成候选卡的全书规划或章节目录")

        source_id = planning.id if planning else directory.id
        assert source_id is not None

        report = CardCandidateGenerateReport(generated_count=0, skipped_count=0, errors=[], items=[])
        seen_keys: set[tuple[str, str]] = set()

        def process_candidate(card_type: str | None, raw_name: str, summary: str, payload: dict[str, Any]) -> None:
            name = self._normalize_name(raw_name)
            if not card_type or card_type not in CARD_TYPES or not name:
                return
            key = (card_type, name)
            if key in seen_keys:
                report.skipped_count += 1
                report.items.append(CardCandidateGenerateItem(card_type=card_type, name=name, status="skipped", message="本次生成内重复，已跳过"))
                return
            seen_keys.add(key)

            if self._pending_candidate_exists(db, project_id, card_type, name):
                report.skipped_count += 1
                report.items.append(CardCandidateGenerateItem(card_type=card_type, name=name, status="skipped", message="存在待处理候选卡，已跳过"))
                return
            if self._formal_card_exists(db, project_id, card_type, name):
                report.skipped_count += 1
                report.items.append(CardCandidateGenerateItem(card_type=card_type, name=name, status="skipped", message="存在同名正式卡槽，已跳过"))
                return

            self._create_candidate(db, project_id, source_id, card_type, name, summary, payload)
            report.generated_count += 1
            report.items.append(CardCandidateGenerateItem(card_type=card_type, name=name, status="created", message="已生成候选卡"))

        if planning and planning.core_seed_summary:
            for line in planning.core_seed_summary.splitlines():
                raw = line.strip()
                if not raw:
                    continue
                matched = re.match(r"^(角色|术语|势力|地点)\s*[：:]\s*(.+)$", raw)
                if not matched:
                    continue
                card_type = PREFIX_TO_TYPE[matched.group(1)]
                parts = self._split_bar(matched.group(2))
                if not parts:
                    continue
                name = parts[0]
                summary = "｜".join(parts[1:]) if len(parts) > 1 else ""
                process_candidate(
                    card_type,
                    name,
                    summary,
                    {
                        "source_refs": ["story_planning"],
                        "raw_line": raw,
                        "suggested_fields": {"parts": parts},
                    },
                )

        if directory:
            for chapter in (directory.chapter_items or []):
                chapter_no = chapter.get("chapter_no")
                chapter_title = chapter.get("chapter_title", "")
                chapter_role = chapter.get("chapter_role", "")
                chapter_goal = chapter.get("chapter_goal", "")
                stage_label = chapter.get("stage_label", "")

                chapter_context = "；".join(filter(None, [chapter_title, chapter_role, chapter_goal, stage_label]))

                for entity in chapter.get("required_entities") or []:
                    card_type = self._infer_entity_card_type(str(entity))
                    process_candidate(
                        card_type,
                        str(entity),
                        f"来自章节目录第{chapter_no}章：{chapter_context}" if chapter_context else f"来自章节目录第{chapter_no}章",
                        {
                            "source_refs": ["story_directory"],
                            "source_chapters": [chapter_no] if isinstance(chapter_no, int) else [],
                            "raw_line": str(entity),
                            "suggested_fields": {
                                "chapter_title": chapter_title,
                                "chapter_role": chapter_role,
                                "chapter_goal": chapter_goal,
                                "stage_label": stage_label,
                            },
                        },
                    )

                for seed_point in chapter.get("required_seed_points") or []:
                    name = self._normalize_name(str(seed_point))
                    process_candidate(
                        "terminology",
                        name,
                        f"来自章节目录第{chapter_no}章设定点：{chapter_context}" if chapter_context else f"来自章节目录第{chapter_no}章设定点",
                        {
                            "source_refs": ["story_directory"],
                            "source_chapters": [chapter_no] if isinstance(chapter_no, int) else [],
                            "raw_line": str(seed_point),
                            "suggested_fields": {
                                "chapter_title": chapter_title,
                                "chapter_role": chapter_role,
                                "chapter_goal": chapter_goal,
                                "stage_label": stage_label,
                            },
                        },
                    )

        db.commit()
        return report

    def list_candidates(
        self,
        db: Session,
        project_id: str,
        status: str | None = None,
        card_type: str | None = None,
    ) -> list[CardCandidateResponse]:
        self._ensure_project_exists(db, project_id)
        query = db.query(StructuredCardCandidateORM).filter(StructuredCardCandidateORM.project_id == project_id)
        if status:
            if status not in CANDIDATE_STATUS:
                raise ValidationError("不支持的候选状态")
            query = query.filter(StructuredCardCandidateORM.status == status)
        if card_type:
            if card_type not in CARD_TYPES:
                raise ValidationError("不支持的候选类型")
            query = query.filter(StructuredCardCandidateORM.card_type == card_type)

        items = query.order_by(StructuredCardCandidateORM.created_at.desc()).all()
        return [CardCandidateResponse.model_validate(item) for item in items]

    def get_candidate(self, db: Session, project_id: str, candidate_id: str) -> CardCandidateResponse:
        self._ensure_project_exists(db, project_id)
        item = db.query(StructuredCardCandidateORM).filter(
            StructuredCardCandidateORM.id == candidate_id,
            StructuredCardCandidateORM.project_id == project_id,
        ).first()
        if item is None:
            raise NotFoundError("候选卡不存在")
        return CardCandidateResponse.model_validate(item)

    def confirm_candidate(self, db: Session, project_id: str, candidate_id: str) -> CardCandidateActionResponse:
        self._ensure_project_exists(db, project_id)
        candidate = db.query(StructuredCardCandidateORM).filter(
            StructuredCardCandidateORM.id == candidate_id,
            StructuredCardCandidateORM.project_id == project_id,
        ).first()
        if candidate is None:
            raise NotFoundError("候选卡不存在")
        if candidate.status != "pending":
            raise ValidationError("仅 pending 候选卡可确认")

        name = candidate.name
        now = datetime.now(timezone.utc)

        if self._formal_card_exists(db, project_id, candidate.card_type, name):
            candidate.status = "skipped"
            candidate.updated_at = now
            db.add(candidate)
            db.commit()
            return CardCandidateActionResponse(
                candidate_id=candidate.id,
                card_type=candidate.card_type,
                status="skipped",
                message="已存在同名卡，已跳过",
            )

        payload = candidate.payload or {}
        created_card_id: str | None = None
        if candidate.card_type == "character":
            row = StructuredCharacterCardORM(
                project_id=project_id,
                name=name,
                aliases=[],
                role_position=payload.get("suggested_fields", {}).get("role_position", "待补充"),
                profile=candidate.summary or "待补充",
                personality_keywords=[],
                relationship_notes="",
                current_status="",
                first_appearance_chapter=(payload.get("source_chapters") or [None])[0],
                last_update_source="card_candidate_confirm",
                is_canon=False,
            )
            db.add(row)
            db.flush()
            created_card_id = str(row.id)
        elif candidate.card_type == "terminology":
            row = TerminologyCardORM(
                project_id=project_id,
                term=name,
                term_type=payload.get("suggested_fields", {}).get("term_type", "待补充"),
                definition=candidate.summary or "待补充",
                usage_rules="",
                examples=[],
                first_appearance_chapter=(payload.get("source_chapters") or [None])[0],
                last_update_source="card_candidate_confirm",
                is_canon=False,
            )
            db.add(row)
            db.flush()
            created_card_id = str(row.id)
        elif candidate.card_type == "faction":
            row = StructuredFactionCardORM(
                project_id=project_id,
                name=name,
                aliases=[],
                faction_type=payload.get("suggested_fields", {}).get("faction_type", "待补充"),
                description=candidate.summary or "待补充",
                core_members=[],
                territory="",
                stance="",
                goals="",
                relationship_notes="",
                current_status="",
                first_appearance_chapter=(payload.get("source_chapters") or [None])[0],
                last_update_source="card_candidate_confirm",
                is_canon=False,
            )
            db.add(row)
            db.flush()
            created_card_id = str(row.id)
        else:
            row = StructuredLocationCardORM(
                project_id=project_id,
                name=name,
                aliases=[],
                location_type=payload.get("suggested_fields", {}).get("location_type", "待补充"),
                description=candidate.summary or "待补充",
                region="",
                key_features=[],
                related_factions=[],
                narrative_role="",
                current_status="",
                first_appearance_chapter=(payload.get("source_chapters") or [None])[0],
                last_update_source="card_candidate_confirm",
                is_canon=False,
            )
            db.add(row)
            db.flush()
            created_card_id = str(row.id)

        candidate.status = "confirmed"
        candidate.created_card_id = created_card_id
        candidate.updated_at = now
        db.add(candidate)
        db.commit()
        return CardCandidateActionResponse(
            candidate_id=candidate.id,
            card_type=candidate.card_type,
            status="confirmed",
            created_card_id=created_card_id,
            message=f"候选卡已确认并写入{self._card_type_label(candidate.card_type)}。",
        )

    @staticmethod
    def _card_type_label(card_type: str) -> str:
        return {
            "character": "角色卡",
            "terminology": "术语卡",
            "faction": "势力卡",
            "location": "地点卡",
        }[card_type]

    def skip_candidate(self, db: Session, project_id: str, candidate_id: str) -> CardCandidateActionResponse:
        self._ensure_project_exists(db, project_id)
        candidate = db.query(StructuredCardCandidateORM).filter(
            StructuredCardCandidateORM.id == candidate_id,
            StructuredCardCandidateORM.project_id == project_id,
        ).first()
        if candidate is None:
            raise NotFoundError("候选卡不存在")
        if candidate.status != "pending":
            raise ValidationError("仅 pending 候选卡可跳过")

        candidate.status = "skipped"
        candidate.updated_at = datetime.now(timezone.utc)
        db.add(candidate)
        db.commit()
        return CardCandidateActionResponse(
            candidate_id=candidate.id,
            card_type=candidate.card_type,
            status="skipped",
            message="候选卡已跳过。",
        )


story_planning_card_candidate_service = StoryPlanningCardCandidateService()
