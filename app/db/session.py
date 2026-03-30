from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PROJECT_ROOT, settings


def _normalize_sqlite_url(raw_url: str) -> str:
    if raw_url.startswith("sqlite:///./"):
        relative = raw_url.removeprefix("sqlite:///./")
        absolute_path = (PROJECT_ROOT / relative).resolve()
        return f"sqlite:///{absolute_path.as_posix()}"
    return raw_url


normalized_database_url = _normalize_sqlite_url(settings.database_url)
if normalized_database_url.startswith("sqlite:///"):
    sqlite_path = normalized_database_url.removeprefix("sqlite:///")
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if normalized_database_url.startswith("sqlite") else {}
engine = create_engine(normalized_database_url, future=True, echo=False, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        return


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
