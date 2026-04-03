import tempfile
import textwrap
import unittest
from pathlib import Path

from app.core.preflight import run_preflight


class PreflightEnvTest(unittest.TestCase):
    def _write_env(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        tmp.write(textwrap.dedent(content).strip() + "\n")
        tmp.flush()
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_dev_example_passes(self):
        env_file = self._write_env(
            """
            APP_ENV=dev
            AGENT_PROVIDER=mock
            AGENT_FALLBACK_TO_MOCK=true
            AUTO_CREATE_TABLES=true
            """
        )
        ok, errors = run_preflight("dev", env_file=env_file)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_real_provider_missing_required_fields_fails(self):
        env_file = self._write_env(
            """
            APP_ENV=real-provider
            AGENT_PROVIDER=openai_compatible
            AGENT_MODEL=
            AGENT_FALLBACK_TO_MOCK=false
            AUTO_CREATE_TABLES=false
            """
        )
        ok, errors = run_preflight("real-provider", env_file=env_file)
        self.assertFalse(ok)
        joined = "\n".join(errors)
        self.assertIn("AGENT_API_BASE_URL", joined)
        self.assertIn("AGENT_API_KEY", joined)
        self.assertIn("AGENT_MODEL", joined)

    def test_prod_rejects_mock_and_fallback_and_auto_create(self):
        env_file = self._write_env(
            """
            APP_ENV=prod
            AGENT_PROVIDER=mock
            AGENT_FALLBACK_TO_MOCK=true
            AUTO_CREATE_TABLES=true
            AGENT_API_BASE_URL=https://api.openai.com/v1
            AGENT_API_KEY=test-key
            AGENT_MODEL=gpt-4.1-mini
            """
        )
        ok, errors = run_preflight("prod", env_file=env_file)
        self.assertFalse(ok)
        joined = "\n".join(errors)
        self.assertIn("AGENT_PROVIDER=mock", joined)
        self.assertIn("AGENT_FALLBACK_TO_MOCK=true", joined)
        self.assertIn("AUTO_CREATE_TABLES=true", joined)


if __name__ == "__main__":
    unittest.main()
