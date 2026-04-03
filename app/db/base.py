from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.services.prompt_template_service import prompt_template_service


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_defaults()


def ensure_runtime_defaults() -> None:
    db = SessionLocal()
    try:
        prompt_template_service.ensure_default_templates(db)
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Database schema is not ready. Run `alembic upgrade head` first, "
            "or set AUTO_CREATE_TABLES=true for local development fallback."
        ) from exc
    finally:
        db.close()
