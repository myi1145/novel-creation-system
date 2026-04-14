from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def pytest_sessionstart(session) -> None:  # pragma: no cover - pytest hook
    """Ensure test DB schema is aligned with latest Alembic migrations."""

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
