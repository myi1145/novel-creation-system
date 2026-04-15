from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.db.session import get_db
from app.schemas.project import CreateProjectRequest
from app.schemas.story_directory import StoryDirectoryUpsert
from app.schemas.story_planning import StoryPlanningUpsert
from app.schemas.structured_cards import (
    CharacterCardCreate,
    CharacterCardUpdate,
    FactionCardCreate,
    FactionCardUpdate,
    LocationCardCreate,
    LocationCardUpdate,
    TerminologyCardCreate,
    TerminologyCardUpdate,
)
from app.services.project_service import project_service
from app.services.story_directory_service import story_directory_service
from app.services.story_planning_service import story_planning_service
from app.services.structured_card_service import structured_card_service
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




@router.get("/{project_id}/story-directory")
def get_story_directory(project_id: str, db: Session = Depends(get_db)) -> dict:
    item = story_directory_service.get_story_directory(db=db, project_id=project_id)
    if item is None:
        return success_response(data=None, message="尚未创建章节目录")
    return success_response(data=item.model_dump(mode="json"))


@router.put("/{project_id}/story-directory")
def upsert_story_directory(project_id: str, request: StoryDirectoryUpsert, db: Session = Depends(get_db)) -> dict:
    item = story_directory_service.upsert_story_directory(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="章节目录已保存")


@router.get("/{project_id}/story-planning")
def get_story_planning(project_id: str, db: Session = Depends(get_db)) -> dict:
    item = story_planning_service.get_story_planning(db=db, project_id=project_id)
    if item is None:
        return success_response(data=None, message="尚未创建全书规划")
    return success_response(data=item.model_dump(mode="json"))


@router.put("/{project_id}/story-planning")
def upsert_story_planning(project_id: str, request: StoryPlanningUpsert, db: Session = Depends(get_db)) -> dict:
    item = story_planning_service.upsert_story_planning(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="全书规划已保存")

@router.get("/{project_id}/structured-cards/export.json")
def export_structured_cards_json(project_id: str, db: Session = Depends(get_db)) -> Response:
    payload = structured_card_service.export_cards_json(db=db, project_id=project_id)
    content = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2)
    date_suffix = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"structured-cards-{project_id}-{date_suffix}.json"
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/structured-cards/import.json")
async def import_structured_cards_json(
    project_id: str,
    file: UploadFile | None = File(default=None),
    payload: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    parsed_payload: dict
    if file is not None:
        try:
            raw_content = (await file.read()).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("JSON 文件必须为 UTF-8 编码") from exc
        try:
            parsed_payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValidationError("JSON 文件格式非法") from exc
    elif payload:
        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError("payload 不是合法 JSON") from exc
    else:
        raise ValidationError("请提供 JSON 文件或 payload")

    if "cards" not in parsed_payload:
        raise ValidationError("JSON 必须包含 cards 字段")

    report = structured_card_service.import_cards_json(db=db, project_id=project_id, payload=parsed_payload)
    return success_response(data=report.model_dump(mode="json"), message="导入完成")


@router.get("/{project_id}/structured-cards/{card_type}/export.csv")
def export_structured_cards_csv(project_id: str, card_type: str, db: Session = Depends(get_db)) -> Response:
    content = structured_card_service.export_cards_csv(db=db, project_id=project_id, card_type=card_type)
    date_suffix = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"structured-cards-{project_id}-{card_type}-{date_suffix}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/structured-cards/{card_type}/import.csv")
async def import_structured_cards_csv(
    project_id: str,
    card_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV 文件必须为 UTF-8 编码") from exc
    report = structured_card_service.import_cards_csv(db=db, project_id=project_id, card_type=card_type, content=content)
    return success_response(data=report.model_dump(mode="json"), message="导入完成")


@router.get("/{project_id}/structured-cards/{card_type}/template.csv")
def download_structured_cards_template(project_id: str, card_type: str, db: Session = Depends(get_db)) -> Response:
    structured_card_service._ensure_project_exists(db=db, project_id=project_id)
    content = structured_card_service.build_csv_template(card_type=card_type)
    filename = f"structured-cards-{card_type}-template.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/character-cards")
def list_character_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_character_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/character-cards")
def create_character_card(project_id: str, request: CharacterCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_character_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="角色卡已创建")


@router.get("/{project_id}/character-cards/{card_id}")
def get_character_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_character_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/character-cards/{card_id}")
def update_character_card(project_id: str, card_id: int, request: CharacterCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_character_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="角色卡已更新")


@router.get("/{project_id}/terminology-cards")
def list_terminology_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_terminology_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/terminology-cards")
def create_terminology_card(project_id: str, request: TerminologyCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_terminology_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="术语卡已创建")


@router.get("/{project_id}/terminology-cards/{card_id}")
def get_terminology_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_terminology_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/terminology-cards/{card_id}")
def update_terminology_card(project_id: str, card_id: int, request: TerminologyCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_terminology_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="术语卡已更新")


@router.get("/{project_id}/faction-cards")
def list_faction_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_faction_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/faction-cards")
def create_faction_card(project_id: str, request: FactionCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_faction_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="势力卡已创建")


@router.get("/{project_id}/faction-cards/{card_id}")
def get_faction_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_faction_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/faction-cards/{card_id}")
def update_faction_card(project_id: str, card_id: int, request: FactionCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_faction_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="势力卡已更新")


@router.get("/{project_id}/location-cards")
def list_location_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_location_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/location-cards")
def create_location_card(project_id: str, request: LocationCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_location_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="地点卡已创建")


@router.get("/{project_id}/location-cards/{card_id}")
def get_location_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_location_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/location-cards/{card_id}")
def update_location_card(project_id: str, card_id: int, request: LocationCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_location_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="地点卡已更新")
