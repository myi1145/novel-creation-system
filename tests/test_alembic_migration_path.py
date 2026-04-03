import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AlembicMigrationPathTest(unittest.TestCase):
    def _run(
        self,
        command: list[str],
        extra_env: dict[str, str] | None = None,
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            command,
            cwd=cwd or REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_alembic_upgrade_head_on_empty_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "migration_smoke.db"
            db_url = f"sqlite:///{db_path.as_posix()}"
            alembic_ini = (REPO_ROOT / "alembic.ini").as_posix()
            cmd = [
                sys.executable,
                "-c",
                (
                    "from alembic.config import main; "
                    f"main(argv=['-c', r'{alembic_ini}', 'upgrade', 'head'])"
                ),
            ]
            result = self._run(cmd, {"DATABASE_URL": db_url}, cwd=Path(tmpdir))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(db_path.exists())

            with sqlite3.connect(db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("alembic_version", tables)
            self.assertIn("projects", tables)
            self.assertIn("prompt_templates", tables)

    def test_app_startup_without_schema_should_fail_when_auto_create_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "no_schema.db"
            db_url = f"sqlite:///{db_path.as_posix()}"
            code = (
                "from fastapi.testclient import TestClient\n"
                "from app.main import create_app\n"
                "with TestClient(create_app()) as client:\n"
                "    client.get('/health')\n"
            )
            result = self._run(
                ["python", "-c", code],
                {"DATABASE_URL": db_url, "AUTO_CREATE_TABLES": "false"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("alembic upgrade head", result.stderr)

    def test_app_startup_should_allow_dev_fallback_auto_create_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fallback.db"
            db_url = f"sqlite:///{db_path.as_posix()}"
            code = (
                "from fastapi.testclient import TestClient\n"
                "from app.main import create_app\n"
                "with TestClient(create_app()) as client:\n"
                "    response = client.get('/health')\n"
                "    assert response.status_code == 200\n"
            )
            result = self._run(
                ["python", "-c", code],
                {"DATABASE_URL": db_url, "AUTO_CREATE_TABLES": "true"},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
