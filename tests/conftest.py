from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

_ALLOWED_APP_ENVS = {"ci", "test"}
_SQLITE_TEMP_PATH_MARKERS = (
    "/tmp/",
    "/private/tmp/",
    "/var/folders/",
)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _is_allowed_test_database(database_url: str, app_env: str) -> tuple[bool, str]:
    normalized_env = app_env.strip().lower()
    if normalized_env in _ALLOWED_APP_ENVS:
        return True, f"APP_ENV={app_env}"

    normalized_url = database_url.strip().lower()
    parsed = urlparse(database_url)

    if ":memory:" in normalized_url:
        return True, "SQLite in-memory test database"

    if parsed.scheme.startswith("sqlite"):
        sqlite_path = (parsed.path or "").lower()
        if "test" in sqlite_path:
            return True, "SQLite filename/path contains 'test'"
        if sqlite_path.startswith(_SQLITE_TEMP_PATH_MARKERS):
            return True, "SQLite temporary directory"

    if "test" in (parsed.path or "").lower():
        return True, "database name/path contains 'test'"

    return False, "database URL does not look like a dedicated test database"


def _validate_pytest_migration_target(project_root: Path) -> None:
    env_file_values = _read_env_file(project_root / ".env")
    database_url = os.getenv("DATABASE_URL") or env_file_values.get("DATABASE_URL") or "sqlite:///./data/app.db"
    app_env = os.getenv("APP_ENV") or env_file_values.get("APP_ENV") or "dev"

    allowed, reason = _is_allowed_test_database(database_url, app_env)
    if not allowed:
        raise RuntimeError(
            "Refusing to run pytest auto-migration on non-test database. "
            f"Detected APP_ENV={app_env!r}, DATABASE_URL={database_url!r}. "
            f"Validation reason: {reason}. "
            "Only test databases are allowed (SQLite temp DB, URL/path containing 'test', "
            "or APP_ENV in {'ci', 'test'})."
        )


def pytest_sessionstart(session) -> None:  # pragma: no cover - pytest hook
    """Ensure test DB schema is aligned with latest Alembic migrations."""

    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{existing_pythonpath}" if existing_pythonpath else str(project_root)

    _validate_pytest_migration_target(project_root)

    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=project_root,
        env=env,
        check=True,
    )
