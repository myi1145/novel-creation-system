from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import ProjectORM, StructuredCharacterCardORM, TerminologyCardORM
from app.schemas.structured_cards import (
    CharacterCardCreate,
    CharacterCardResponse,
    CharacterCardUpdate,
    TerminologyCardCreate,
    TerminologyCardResponse,
    TerminologyCardUpdate,
)


class StructuredCardService:
    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    def list_character_cards(self, db: Session, project_id: str) -> list[CharacterCardResponse]:
        self._ensure_project_exists(db, project_id)
        items = (
            db.query(StructuredCharacterCardORM)
            .filter(StructuredCharacterCardORM.project_id == project_id)
            .order_by(StructuredCharacterCardORM.updated_at.desc())
            .all()
        )
        return [CharacterCardResponse.model_validate(item) for item in items]

    def get_character_card(self, db: Session, project_id: str, card_id: int) -> CharacterCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredCharacterCardORM)
            .filter(StructuredCharacterCardORM.project_id == project_id, StructuredCharacterCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("角色卡不存在")
        return CharacterCardResponse.model_validate(item)

    def create_character_card(self, db: Session, project_id: str, request: CharacterCardCreate) -> CharacterCardResponse:
        self._ensure_project_exists(db, project_id)
        item = StructuredCharacterCardORM(
            project_id=project_id,
            name=request.name,
            aliases=request.aliases,
            role_position=request.role_position,
            profile=request.profile,
            personality_keywords=request.personality_keywords,
            relationship_notes=request.relationship_notes,
            current_status=request.current_status,
            first_appearance_chapter=request.first_appearance_chapter,
            last_update_source="manual",
            is_canon=False,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return CharacterCardResponse.model_validate(item)

    def update_character_card(self, db: Session, project_id: str, card_id: int, request: CharacterCardUpdate) -> CharacterCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredCharacterCardORM)
            .filter(StructuredCharacterCardORM.project_id == project_id, StructuredCharacterCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("角色卡不存在")

        for key, value in request.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.last_update_source = "manual"
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        db.refresh(item)
        return CharacterCardResponse.model_validate(item)

    def list_terminology_cards(self, db: Session, project_id: str) -> list[TerminologyCardResponse]:
        self._ensure_project_exists(db, project_id)
        items = (
            db.query(TerminologyCardORM)
            .filter(TerminologyCardORM.project_id == project_id)
            .order_by(TerminologyCardORM.updated_at.desc())
            .all()
        )
        return [TerminologyCardResponse.model_validate(item) for item in items]

    def get_terminology_card(self, db: Session, project_id: str, card_id: int) -> TerminologyCardResponse:
        self._ensure_project_exists(db, project_id)
        item = db.query(TerminologyCardORM).filter(TerminologyCardORM.project_id == project_id, TerminologyCardORM.id == card_id).first()
        if not item:
            raise NotFoundError("术语卡不存在")
        return TerminologyCardResponse.model_validate(item)

    def create_terminology_card(self, db: Session, project_id: str, request: TerminologyCardCreate) -> TerminologyCardResponse:
        self._ensure_project_exists(db, project_id)
        item = TerminologyCardORM(
            project_id=project_id,
            term=request.term,
            term_type=request.term_type,
            definition=request.definition,
            usage_rules=request.usage_rules,
            examples=request.examples,
            first_appearance_chapter=request.first_appearance_chapter,
            last_update_source="manual",
            is_canon=False,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return TerminologyCardResponse.model_validate(item)

    def update_terminology_card(self, db: Session, project_id: str, card_id: int, request: TerminologyCardUpdate) -> TerminologyCardResponse:
        self._ensure_project_exists(db, project_id)
        item = db.query(TerminologyCardORM).filter(TerminologyCardORM.project_id == project_id, TerminologyCardORM.id == card_id).first()
        if not item:
            raise NotFoundError("术语卡不存在")

        for key, value in request.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.last_update_source = "manual"
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        db.refresh(item)
        return TerminologyCardResponse.model_validate(item)


structured_card_service = StructuredCardService()
