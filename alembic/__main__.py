"""Repository-local shim for `python -m alembic`.

This repo has an `alembic/` migration folder at project root, which can shadow
the Alembic package module resolution in some environments. This shim forwards
execution to the installed Alembic package entrypoint.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _forward_to_installed_alembic() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cleaned_sys_path: list[str] = []
    for item in sys.path:
        resolved = Path(item or ".").resolve()
        if resolved == repo_root:
            continue
        cleaned_sys_path.append(item)
    sys.path[:] = cleaned_sys_path

    sys.modules.pop("alembic", None)
    sys.modules.pop("alembic.__main__", None)
    runpy.run_module("alembic", run_name="__main__")


if __name__ == "__main__":
    _forward_to_installed_alembic()
