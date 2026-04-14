import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import (
    ProjectORM,
    StructuredCharacterCardORM,
    StructuredFactionCardORM,
    StructuredLocationCardORM,
    TerminologyCardORM,
)
from app.schemas.structured_cards import (
    CharacterCardCreate,
    CharacterCardResponse,
    CharacterCardUpdate,
    FactionCardCreate,
    FactionCardResponse,
    FactionCardUpdate,
    LocationCardCreate,
    LocationCardResponse,
    LocationCardUpdate,
    StructuredCardImportError,
    StructuredCardImportReport,
    StructuredCardImportSkipped,
    StructuredCardsExportCards,
    StructuredCardsExportResponse,
    TerminologyCardCreate,
    TerminologyCardResponse,
    TerminologyCardUpdate,
)

CARD_TYPE_CHARACTERS = "characters"
CARD_TYPE_TERMINOLOGIES = "terminologies"
CARD_TYPE_FACTIONS = "factions"
CARD_TYPE_LOCATIONS = "locations"
ALLOWED_CARD_TYPES = {CARD_TYPE_CHARACTERS, CARD_TYPE_TERMINOLOGIES, CARD_TYPE_FACTIONS, CARD_TYPE_LOCATIONS}

CSV_FIELDS: dict[str, list[str]] = {
    CARD_TYPE_CHARACTERS: [
        "name",
        "aliases",
        "role_position",
        "profile",
        "personality_keywords",
        "relationship_notes",
        "current_status",
        "first_appearance_chapter",
        "is_canon",
    ],
    CARD_TYPE_TERMINOLOGIES: [
        "term",
        "term_type",
        "definition",
        "usage_rules",
        "examples",
        "first_appearance_chapter",
        "is_canon",
    ],
    CARD_TYPE_FACTIONS: [
        "name",
        "aliases",
        "faction_type",
        "description",
        "core_members",
        "territory",
        "stance",
        "goals",
        "relationship_notes",
        "current_status",
        "first_appearance_chapter",
        "is_canon",
    ],
    CARD_TYPE_LOCATIONS: [
        "name",
        "aliases",
        "location_type",
        "description",
        "region",
        "key_features",
        "related_factions",
        "narrative_role",
        "current_status",
        "first_appearance_chapter",
        "is_canon",
    ],
}

CSV_EXAMPLE_ROWS: dict[str, dict[str, str]] = {
    CARD_TYPE_CHARACTERS: {
        "name": "顾长渊",
        "aliases": "顾师兄;长渊",
        "role_position": "主角",
        "profile": "清虚宗弟子，天赋过人",
        "personality_keywords": "稳;克制;重情",
        "relationship_notes": "与师门关系密切",
        "current_status": "修炼中",
        "first_appearance_chapter": "1",
        "is_canon": "false",
    },
    CARD_TYPE_TERMINOLOGIES: {
        "term": "灵脉回流",
        "term_type": "修炼术语",
        "definition": "灵力在体内逆向循环的现象",
        "usage_rules": "仅用于高阶修士",
        "examples": "灵脉回流;逆转行功",
        "first_appearance_chapter": "1",
        "is_canon": "false",
    },
    CARD_TYPE_FACTIONS: {
        "name": "清虚宗",
        "aliases": "清虚山门",
        "faction_type": "宗门",
        "description": "东岭名门，守序中立",
        "core_members": "掌门;长老",
        "territory": "东岭群山",
        "stance": "中立",
        "goals": "守护山门",
        "relationship_notes": "与青岚宗紧张",
        "current_status": "备战",
        "first_appearance_chapter": "1",
        "is_canon": "false",
    },
    CARD_TYPE_LOCATIONS: {
        "name": "青石镇",
        "aliases": "青石古镇",
        "location_type": "城镇",
        "description": "主角前期活动地点",
        "region": "东岭",
        "key_features": "古井;灵药田",
        "related_factions": "清虚宗",
        "narrative_role": "初期据点",
        "current_status": "平稳",
        "first_appearance_chapter": "1",
        "is_canon": "false",
    },
}


class StructuredCardService:
    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    @staticmethod
    def _split_list_value(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(";") if item.strip()]

    @staticmethod
    def _join_list_value(values: list[str]) -> str:
        return ";".join(values)

    @staticmethod
    def _parse_optional_int(value: str | None) -> int | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            parsed = int(stripped)
        except ValueError as exc:
            raise ValidationError("首次出现章节必须为整数") from exc
        if parsed < 1:
            raise ValidationError("首次出现章节必须大于等于 1")
        return parsed

    @staticmethod
    def _parse_bool(value: str | bool | None) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "是"}:
            return True
        if normalized in {"false", "0", "no", "n", "否", ""}:
            return False
        raise ValidationError("is_canon 仅支持 true/false/是/否")

    @staticmethod
    def _ensure_card_type(card_type: str) -> None:
        if card_type not in ALLOWED_CARD_TYPES:
            raise ValidationError("不支持的 card_type")

    @staticmethod
    def _build_report(card_type: str) -> StructuredCardImportReport:
        return StructuredCardImportReport(
            card_type=card_type,
            total_rows=0,
            created_count=0,
            skipped_count=0,
            error_count=0,
            errors=[],
            skipped=[],
        )

    @staticmethod
    def _to_error(row: int, field: str, message: str) -> StructuredCardImportError:
        return StructuredCardImportError(row=row, field=field, message=message)

    @staticmethod
    def _find_validation_issue(exc: PydanticValidationError) -> tuple[str, str]:
        issue = exc.errors()[0]
        field = str(issue.get("loc", ["unknown"])[-1])
        message = issue.get("msg", "字段校验失败")
        return field, message

    def export_cards_json(self, db: Session, project_id: str) -> StructuredCardsExportResponse:
        self._ensure_project_exists(db, project_id)
        return StructuredCardsExportResponse(
            project_id=project_id,
            exported_at=datetime.now(timezone.utc),
            version="1.0",
            cards=StructuredCardsExportCards(
                characters=[
                    CharacterCardCreate(
                        name=item.name,
                        aliases=item.aliases,
                        role_position=item.role_position,
                        profile=item.profile,
                        personality_keywords=item.personality_keywords,
                        relationship_notes=item.relationship_notes,
                        current_status=item.current_status,
                        first_appearance_chapter=item.first_appearance_chapter,
                    )
                    for item in db.query(StructuredCharacterCardORM).filter(StructuredCharacterCardORM.project_id == project_id).all()
                ],
                terminologies=[
                    TerminologyCardCreate(
                        term=item.term,
                        term_type=item.term_type,
                        definition=item.definition,
                        usage_rules=item.usage_rules,
                        examples=item.examples,
                        first_appearance_chapter=item.first_appearance_chapter,
                    )
                    for item in db.query(TerminologyCardORM).filter(TerminologyCardORM.project_id == project_id).all()
                ],
                factions=[
                    FactionCardCreate(
                        name=item.name,
                        aliases=item.aliases,
                        faction_type=item.faction_type,
                        description=item.description,
                        core_members=item.core_members,
                        territory=item.territory,
                        stance=item.stance,
                        goals=item.goals,
                        relationship_notes=item.relationship_notes,
                        current_status=item.current_status,
                        first_appearance_chapter=item.first_appearance_chapter,
                    )
                    for item in db.query(StructuredFactionCardORM).filter(StructuredFactionCardORM.project_id == project_id).all()
                ],
                locations=[
                    LocationCardCreate(
                        name=item.name,
                        aliases=item.aliases,
                        location_type=item.location_type,
                        description=item.description,
                        region=item.region,
                        key_features=item.key_features,
                        related_factions=item.related_factions,
                        narrative_role=item.narrative_role,
                        current_status=item.current_status,
                        first_appearance_chapter=item.first_appearance_chapter,
                    )
                    for item in db.query(StructuredLocationCardORM).filter(StructuredLocationCardORM.project_id == project_id).all()
                ],
            ),
        )

    def import_cards_json(self, db: Session, project_id: str, payload: dict[str, Any]) -> StructuredCardImportReport:
        self._ensure_project_exists(db, project_id)
        cards = payload.get("cards")
        if not isinstance(cards, dict):
            raise ValidationError("JSON 结构非法: 缺少 cards 对象")

        report = self._build_report("all")
        row_no = 1

        existing_character_names = {
            item[0]
            for item in db.query(StructuredCharacterCardORM.name)
            .filter(StructuredCharacterCardORM.project_id == project_id)
            .all()
        }
        existing_terms = {item[0] for item in db.query(TerminologyCardORM.term).filter(TerminologyCardORM.project_id == project_id).all()}
        existing_faction_names = {
            item[0] for item in db.query(StructuredFactionCardORM.name).filter(StructuredFactionCardORM.project_id == project_id).all()
        }
        existing_location_names = {
            item[0] for item in db.query(StructuredLocationCardORM.name).filter(StructuredLocationCardORM.project_id == project_id).all()
        }

        grouped = [
            (CARD_TYPE_CHARACTERS, cards.get(CARD_TYPE_CHARACTERS, [])),
            (CARD_TYPE_TERMINOLOGIES, cards.get(CARD_TYPE_TERMINOLOGIES, [])),
            (CARD_TYPE_FACTIONS, cards.get(CARD_TYPE_FACTIONS, [])),
            (CARD_TYPE_LOCATIONS, cards.get(CARD_TYPE_LOCATIONS, [])),
        ]

        for group_type, rows in grouped:
            if not isinstance(rows, list):
                raise ValidationError(f"JSON 结构非法: {group_type} 必须为数组")

            for row in rows:
                report.total_rows += 1
                try:
                    if group_type == CARD_TYPE_CHARACTERS:
                        model = CharacterCardCreate.model_validate(row)
                        if model.name in existing_character_names:
                            report.skipped.append(StructuredCardImportSkipped(row=row_no, reason="已存在同名卡片，已跳过"))
                            report.skipped_count += 1
                            row_no += 1
                            continue
                        db.add(
                            StructuredCharacterCardORM(
                                project_id=project_id,
                                name=model.name,
                                aliases=model.aliases,
                                role_position=model.role_position,
                                profile=model.profile,
                                personality_keywords=model.personality_keywords,
                                relationship_notes=model.relationship_notes,
                                current_status=model.current_status,
                                first_appearance_chapter=model.first_appearance_chapter,
                                last_update_source="manual",
                                is_canon=False,
                            )
                        )
                        existing_character_names.add(model.name)
                    elif group_type == CARD_TYPE_TERMINOLOGIES:
                        model = TerminologyCardCreate.model_validate(row)
                        if model.term in existing_terms:
                            report.skipped.append(StructuredCardImportSkipped(row=row_no, reason="已存在同名卡片，已跳过"))
                            report.skipped_count += 1
                            row_no += 1
                            continue
                        db.add(
                            TerminologyCardORM(
                                project_id=project_id,
                                term=model.term,
                                term_type=model.term_type,
                                definition=model.definition,
                                usage_rules=model.usage_rules,
                                examples=model.examples,
                                first_appearance_chapter=model.first_appearance_chapter,
                                last_update_source="manual",
                                is_canon=False,
                            )
                        )
                        existing_terms.add(model.term)
                    elif group_type == CARD_TYPE_FACTIONS:
                        model = FactionCardCreate.model_validate(row)
                        if model.name in existing_faction_names:
                            report.skipped.append(StructuredCardImportSkipped(row=row_no, reason="已存在同名卡片，已跳过"))
                            report.skipped_count += 1
                            row_no += 1
                            continue
                        db.add(
                            StructuredFactionCardORM(
                                project_id=project_id,
                                name=model.name,
                                aliases=model.aliases,
                                faction_type=model.faction_type,
                                description=model.description,
                                core_members=model.core_members,
                                territory=model.territory,
                                stance=model.stance,
                                goals=model.goals,
                                relationship_notes=model.relationship_notes,
                                current_status=model.current_status,
                                first_appearance_chapter=model.first_appearance_chapter,
                                last_update_source="manual",
                                is_canon=False,
                            )
                        )
                        existing_faction_names.add(model.name)
                    else:
                        model = LocationCardCreate.model_validate(row)
                        if model.name in existing_location_names:
                            report.skipped.append(StructuredCardImportSkipped(row=row_no, reason="已存在同名卡片，已跳过"))
                            report.skipped_count += 1
                            row_no += 1
                            continue
                        db.add(
                            StructuredLocationCardORM(
                                project_id=project_id,
                                name=model.name,
                                aliases=model.aliases,
                                location_type=model.location_type,
                                description=model.description,
                                region=model.region,
                                key_features=model.key_features,
                                related_factions=model.related_factions,
                                narrative_role=model.narrative_role,
                                current_status=model.current_status,
                                first_appearance_chapter=model.first_appearance_chapter,
                                last_update_source="manual",
                                is_canon=False,
                            )
                        )
                        existing_location_names.add(model.name)

                    report.created_count += 1
                except PydanticValidationError as exc:
                    field, message = self._find_validation_issue(exc)
                    report.errors.append(self._to_error(row=row_no, field=field, message=message))
                    report.error_count += 1
                row_no += 1

        db.commit()
        return report

    def export_cards_csv(self, db: Session, project_id: str, card_type: str) -> str:
        self._ensure_project_exists(db, project_id)
        self._ensure_card_type(card_type)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS[card_type], quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()

        if card_type == CARD_TYPE_CHARACTERS:
            rows = db.query(StructuredCharacterCardORM).filter(StructuredCharacterCardORM.project_id == project_id).all()
            for row in rows:
                writer.writerow(
                    {
                        "name": row.name,
                        "aliases": self._join_list_value(row.aliases),
                        "role_position": row.role_position,
                        "profile": row.profile,
                        "personality_keywords": self._join_list_value(row.personality_keywords),
                        "relationship_notes": row.relationship_notes,
                        "current_status": row.current_status,
                        "first_appearance_chapter": row.first_appearance_chapter or "",
                        "is_canon": "true" if row.is_canon else "false",
                    }
                )

        if card_type == CARD_TYPE_TERMINOLOGIES:
            rows = db.query(TerminologyCardORM).filter(TerminologyCardORM.project_id == project_id).all()
            for row in rows:
                writer.writerow(
                    {
                        "term": row.term,
                        "term_type": row.term_type,
                        "definition": row.definition,
                        "usage_rules": row.usage_rules,
                        "examples": self._join_list_value(row.examples),
                        "first_appearance_chapter": row.first_appearance_chapter or "",
                        "is_canon": "true" if row.is_canon else "false",
                    }
                )

        if card_type == CARD_TYPE_FACTIONS:
            rows = db.query(StructuredFactionCardORM).filter(StructuredFactionCardORM.project_id == project_id).all()
            for row in rows:
                writer.writerow(
                    {
                        "name": row.name,
                        "aliases": self._join_list_value(row.aliases),
                        "faction_type": row.faction_type,
                        "description": row.description,
                        "core_members": self._join_list_value(row.core_members),
                        "territory": row.territory,
                        "stance": row.stance,
                        "goals": row.goals,
                        "relationship_notes": row.relationship_notes,
                        "current_status": row.current_status,
                        "first_appearance_chapter": row.first_appearance_chapter or "",
                        "is_canon": "true" if row.is_canon else "false",
                    }
                )

        if card_type == CARD_TYPE_LOCATIONS:
            rows = db.query(StructuredLocationCardORM).filter(StructuredLocationCardORM.project_id == project_id).all()
            for row in rows:
                writer.writerow(
                    {
                        "name": row.name,
                        "aliases": self._join_list_value(row.aliases),
                        "location_type": row.location_type,
                        "description": row.description,
                        "region": row.region,
                        "key_features": self._join_list_value(row.key_features),
                        "related_factions": self._join_list_value(row.related_factions),
                        "narrative_role": row.narrative_role,
                        "current_status": row.current_status,
                        "first_appearance_chapter": row.first_appearance_chapter or "",
                        "is_canon": "true" if row.is_canon else "false",
                    }
                )

        return output.getvalue()

    def build_csv_template(self, card_type: str) -> str:
        self._ensure_card_type(card_type)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS[card_type], quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerow(CSV_EXAMPLE_ROWS[card_type])
        return output.getvalue()

    def import_cards_csv(self, db: Session, project_id: str, card_type: str, content: str) -> StructuredCardImportReport:
        self._ensure_project_exists(db, project_id)
        self._ensure_card_type(card_type)

        reader = csv.DictReader(io.StringIO(content))
        actual_fields = reader.fieldnames or []
        expected_fields = CSV_FIELDS[card_type]
        if actual_fields != expected_fields:
            raise ValidationError("CSV 表头不匹配模板，请先下载模板并按模板填写")

        report = self._build_report(card_type)

        if card_type == CARD_TYPE_CHARACTERS:
            existing_names = {
                item[0]
                for item in db.query(StructuredCharacterCardORM.name)
                .filter(StructuredCharacterCardORM.project_id == project_id)
                .all()
            }
        elif card_type == CARD_TYPE_TERMINOLOGIES:
            existing_names = {item[0] for item in db.query(TerminologyCardORM.term).filter(TerminologyCardORM.project_id == project_id).all()}
        elif card_type == CARD_TYPE_FACTIONS:
            existing_names = {item[0] for item in db.query(StructuredFactionCardORM.name).filter(StructuredFactionCardORM.project_id == project_id).all()}
        else:
            existing_names = {
                item[0] for item in db.query(StructuredLocationCardORM.name).filter(StructuredLocationCardORM.project_id == project_id).all()
            }

        for csv_index, row in enumerate(reader, start=2):
            report.total_rows += 1
            try:
                if card_type == CARD_TYPE_CHARACTERS:
                    model = CharacterCardCreate(
                        name=(row.get("name") or "").strip(),
                        aliases=self._split_list_value(row.get("aliases")),
                        role_position=(row.get("role_position") or "").strip(),
                        profile=(row.get("profile") or "").strip(),
                        personality_keywords=self._split_list_value(row.get("personality_keywords")),
                        relationship_notes=(row.get("relationship_notes") or "").strip(),
                        current_status=(row.get("current_status") or "").strip(),
                        first_appearance_chapter=self._parse_optional_int(row.get("first_appearance_chapter")),
                    )
                    name = model.name
                    if name in existing_names:
                        report.skipped.append(StructuredCardImportSkipped(row=csv_index, reason="已存在同名卡片，已跳过"))
                        report.skipped_count += 1
                        continue
                    db.add(
                        StructuredCharacterCardORM(
                            project_id=project_id,
                            name=model.name,
                            aliases=model.aliases,
                            role_position=model.role_position,
                            profile=model.profile,
                            personality_keywords=model.personality_keywords,
                            relationship_notes=model.relationship_notes,
                            current_status=model.current_status,
                            first_appearance_chapter=model.first_appearance_chapter,
                            last_update_source="manual",
                            is_canon=self._parse_bool(row.get("is_canon")),
                        )
                    )
                    existing_names.add(name)

                elif card_type == CARD_TYPE_TERMINOLOGIES:
                    model = TerminologyCardCreate(
                        term=(row.get("term") or "").strip(),
                        term_type=(row.get("term_type") or "").strip(),
                        definition=(row.get("definition") or "").strip(),
                        usage_rules=(row.get("usage_rules") or "").strip(),
                        examples=self._split_list_value(row.get("examples")),
                        first_appearance_chapter=self._parse_optional_int(row.get("first_appearance_chapter")),
                    )
                    if model.term in existing_names:
                        report.skipped.append(StructuredCardImportSkipped(row=csv_index, reason="已存在同名卡片，已跳过"))
                        report.skipped_count += 1
                        continue
                    db.add(
                        TerminologyCardORM(
                            project_id=project_id,
                            term=model.term,
                            term_type=model.term_type,
                            definition=model.definition,
                            usage_rules=model.usage_rules,
                            examples=model.examples,
                            first_appearance_chapter=model.first_appearance_chapter,
                            last_update_source="manual",
                            is_canon=self._parse_bool(row.get("is_canon")),
                        )
                    )
                    existing_names.add(model.term)

                elif card_type == CARD_TYPE_FACTIONS:
                    model = FactionCardCreate(
                        name=(row.get("name") or "").strip(),
                        aliases=self._split_list_value(row.get("aliases")),
                        faction_type=(row.get("faction_type") or "").strip(),
                        description=(row.get("description") or "").strip(),
                        core_members=self._split_list_value(row.get("core_members")),
                        territory=(row.get("territory") or "").strip(),
                        stance=(row.get("stance") or "").strip(),
                        goals=(row.get("goals") or "").strip(),
                        relationship_notes=(row.get("relationship_notes") or "").strip(),
                        current_status=(row.get("current_status") or "").strip(),
                        first_appearance_chapter=self._parse_optional_int(row.get("first_appearance_chapter")),
                    )
                    if model.name in existing_names:
                        report.skipped.append(StructuredCardImportSkipped(row=csv_index, reason="已存在同名卡片，已跳过"))
                        report.skipped_count += 1
                        continue
                    db.add(
                        StructuredFactionCardORM(
                            project_id=project_id,
                            name=model.name,
                            aliases=model.aliases,
                            faction_type=model.faction_type,
                            description=model.description,
                            core_members=model.core_members,
                            territory=model.territory,
                            stance=model.stance,
                            goals=model.goals,
                            relationship_notes=model.relationship_notes,
                            current_status=model.current_status,
                            first_appearance_chapter=model.first_appearance_chapter,
                            last_update_source="manual",
                            is_canon=self._parse_bool(row.get("is_canon")),
                        )
                    )
                    existing_names.add(model.name)

                else:
                    model = LocationCardCreate(
                        name=(row.get("name") or "").strip(),
                        aliases=self._split_list_value(row.get("aliases")),
                        location_type=(row.get("location_type") or "").strip(),
                        description=(row.get("description") or "").strip(),
                        region=(row.get("region") or "").strip(),
                        key_features=self._split_list_value(row.get("key_features")),
                        related_factions=self._split_list_value(row.get("related_factions")),
                        narrative_role=(row.get("narrative_role") or "").strip(),
                        current_status=(row.get("current_status") or "").strip(),
                        first_appearance_chapter=self._parse_optional_int(row.get("first_appearance_chapter")),
                    )
                    if model.name in existing_names:
                        report.skipped.append(StructuredCardImportSkipped(row=csv_index, reason="已存在同名卡片，已跳过"))
                        report.skipped_count += 1
                        continue
                    db.add(
                        StructuredLocationCardORM(
                            project_id=project_id,
                            name=model.name,
                            aliases=model.aliases,
                            location_type=model.location_type,
                            description=model.description,
                            region=model.region,
                            key_features=model.key_features,
                            related_factions=model.related_factions,
                            narrative_role=model.narrative_role,
                            current_status=model.current_status,
                            first_appearance_chapter=model.first_appearance_chapter,
                            last_update_source="manual",
                            is_canon=self._parse_bool(row.get("is_canon")),
                        )
                    )
                    existing_names.add(model.name)

                report.created_count += 1
            except ValidationError as exc:
                report.errors.append(self._to_error(row=csv_index, field="row", message=exc.message))
                report.error_count += 1
            except PydanticValidationError as exc:
                field, message = self._find_validation_issue(exc)
                report.errors.append(self._to_error(row=csv_index, field=field, message=message))
                report.error_count += 1

        db.commit()
        return report

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

    def list_faction_cards(self, db: Session, project_id: str) -> list[FactionCardResponse]:
        self._ensure_project_exists(db, project_id)
        items = (
            db.query(StructuredFactionCardORM)
            .filter(StructuredFactionCardORM.project_id == project_id)
            .order_by(StructuredFactionCardORM.updated_at.desc())
            .all()
        )
        return [FactionCardResponse.model_validate(item) for item in items]

    def get_faction_card(self, db: Session, project_id: str, card_id: int) -> FactionCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredFactionCardORM)
            .filter(StructuredFactionCardORM.project_id == project_id, StructuredFactionCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("势力卡不存在")
        return FactionCardResponse.model_validate(item)

    def create_faction_card(self, db: Session, project_id: str, request: FactionCardCreate) -> FactionCardResponse:
        self._ensure_project_exists(db, project_id)
        item = StructuredFactionCardORM(
            project_id=project_id,
            name=request.name,
            aliases=request.aliases,
            faction_type=request.faction_type,
            description=request.description,
            core_members=request.core_members,
            territory=request.territory,
            stance=request.stance,
            goals=request.goals,
            relationship_notes=request.relationship_notes,
            current_status=request.current_status,
            first_appearance_chapter=request.first_appearance_chapter,
            last_update_source="manual",
            is_canon=False,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return FactionCardResponse.model_validate(item)

    def update_faction_card(self, db: Session, project_id: str, card_id: int, request: FactionCardUpdate) -> FactionCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredFactionCardORM)
            .filter(StructuredFactionCardORM.project_id == project_id, StructuredFactionCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("势力卡不存在")

        for key, value in request.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.last_update_source = "manual"
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        db.refresh(item)
        return FactionCardResponse.model_validate(item)

    def list_location_cards(self, db: Session, project_id: str) -> list[LocationCardResponse]:
        self._ensure_project_exists(db, project_id)
        items = (
            db.query(StructuredLocationCardORM)
            .filter(StructuredLocationCardORM.project_id == project_id)
            .order_by(StructuredLocationCardORM.updated_at.desc())
            .all()
        )
        return [LocationCardResponse.model_validate(item) for item in items]

    def get_location_card(self, db: Session, project_id: str, card_id: int) -> LocationCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredLocationCardORM)
            .filter(StructuredLocationCardORM.project_id == project_id, StructuredLocationCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("地点卡不存在")
        return LocationCardResponse.model_validate(item)

    def create_location_card(self, db: Session, project_id: str, request: LocationCardCreate) -> LocationCardResponse:
        self._ensure_project_exists(db, project_id)
        item = StructuredLocationCardORM(
            project_id=project_id,
            name=request.name,
            aliases=request.aliases,
            location_type=request.location_type,
            description=request.description,
            region=request.region,
            key_features=request.key_features,
            related_factions=request.related_factions,
            narrative_role=request.narrative_role,
            current_status=request.current_status,
            first_appearance_chapter=request.first_appearance_chapter,
            last_update_source="manual",
            is_canon=False,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return LocationCardResponse.model_validate(item)

    def update_location_card(self, db: Session, project_id: str, card_id: int, request: LocationCardUpdate) -> LocationCardResponse:
        self._ensure_project_exists(db, project_id)
        item = (
            db.query(StructuredLocationCardORM)
            .filter(StructuredLocationCardORM.project_id == project_id, StructuredLocationCardORM.id == card_id)
            .first()
        )
        if not item:
            raise NotFoundError("地点卡不存在")

        for key, value in request.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.last_update_source = "manual"
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        db.refresh(item)
        return LocationCardResponse.model_validate(item)


structured_card_service = StructuredCardService()
