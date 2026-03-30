import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import GenreProfileORM
from app.schemas.genre import GenreProfile, LoadGenreRequest


class GenreService:
    def load_genre(self, db: Session, request: LoadGenreRequest) -> GenreProfile:
        base_path = Path(__file__).resolve().parents[2] / "data" / "genres"
        target = base_path / request.file_name
        if not target.exists():
            raise NotFoundError(f"题材文件不存在: {request.file_name}")

        with target.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        genre = GenreProfile.model_validate(raw)

        entity = db.get(GenreProfileORM, genre.genre_id)
        if entity is None:
            entity = GenreProfileORM(genre_id=genre.genre_id)
            db.add(entity)
        entity.genre_name = genre.genre_name
        entity.base_genre = genre.base_genre
        entity.tags = genre.tags
        entity.world = genre.world
        entity.narrative = genre.narrative
        entity.style = genre.style
        db.commit()
        db.refresh(entity)
        return GenreProfile.model_validate(entity)

    def list_genres(self, db: Session) -> list[GenreProfile]:
        items = db.query(GenreProfileORM).order_by(GenreProfileORM.genre_id.asc()).all()
        return [GenreProfile.model_validate(item) for item in items]


genre_service = GenreService()
