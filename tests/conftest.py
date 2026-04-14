from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.core.config import settings


def _is_obviously_test_database(database_url: str, app_env: str) -> bool:
    normalized_env = app_env.strip().lower()
    if normalized_env in {"ci", "test"}:
        return True

    normalized_url = database_url.strip().lower()
    if normalized_url == "sqlite:///:memory:":
        return True

    if normalized_url.startswith("sqlite:///"):
        sqlite_path = normalized_url.removeprefix("sqlite:///")
        filename = Path(sqlite_path).name.lower()
        return "test" in filename or "pytest" in filename

    parsed = urlparse(normalized_url)
    db_name = Path(parsed.path).name.lower()
    return "test" in db_name or "pytest" in db_name


def _assert_test_database_or_abort(database_url: str, app_env: str) -> None:
    if _is_obviously_test_database(database_url=database_url, app_env=app_env):
        return

    raise pytest.UsageError(
        "Refuse to run pytest auto-migration on non-test database. "
        f"Resolved APP_ENV={app_env!r}, DATABASE_URL={database_url!r}. "
        "Use a dedicated test DB (e.g. sqlite test file / :memory:) "
        "or set APP_ENV=ci/test explicitly."
    )


def pytest_sessionstart(session) -> None:  # pragma: no cover - pytest hook
    """Ensure test DB schema is aligned with latest Alembic migrations."""

    _assert_test_database_or_abort(database_url=settings.database_url, app_env=settings.app_env)

    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{existing_pythonpath}" if existing_pythonpath else str(project_root)

    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=project_root,
        env=env,
        check=True,
    )
