import unittest

from pydantic import ValidationError

from app.core.config import Settings


class ConfigProfilesTest(unittest.TestCase):
    def _build(self, **overrides) -> Settings:
        return Settings(_env_file=None, **overrides)

    def test_dev_mode_allows_mock_and_fallback(self):
        settings = self._build(
            app_env="dev",
            agent_provider="mock",
            agent_fallback_to_mock=True,
            auto_create_tables=True,
        )
        self.assertEqual(settings.app_env, "dev")
        self.assertEqual(settings.agent_provider, "mock")
        self.assertTrue(settings.agent_fallback_to_mock)
        self.assertTrue(settings.auto_create_tables)

    def test_ci_mode_rejects_auto_create_tables(self):
        with self.assertRaises(ValidationError) as ctx:
            self._build(app_env="ci", auto_create_tables=True)
        self.assertIn("CI 模式禁止 AUTO_CREATE_TABLES=true", str(ctx.exception))

    def test_real_provider_mode_rejects_mock_or_fallback(self):
        with self.assertRaises(ValidationError) as ctx_mock:
            self._build(app_env="real-provider", agent_provider="mock", agent_fallback_to_mock=False)
        self.assertIn("real-provider 模式禁止 AGENT_PROVIDER=mock", str(ctx_mock.exception))

        with self.assertRaises(ValidationError) as ctx_fallback:
            self._build(
                app_env="real-provider",
                agent_provider="openai_compatible",
                agent_fallback_to_mock=True,
            )
        self.assertIn("real-provider 模式禁止 AGENT_FALLBACK_TO_MOCK=true", str(ctx_fallback.exception))

    def test_prod_mode_requires_non_mock_provider_and_no_auto_create(self):
        with self.assertRaises(ValidationError) as ctx:
            self._build(
                app_env="prod",
                agent_provider="openai_compatible",
                agent_fallback_to_mock=False,
                auto_create_tables=True,
            )
        self.assertIn("prod 模式禁止 AUTO_CREATE_TABLES=true", str(ctx.exception))

        settings = self._build(
            app_env="prod",
            agent_provider="openai_compatible",
            agent_fallback_to_mock=False,
            auto_create_tables=False,
        )
        self.assertEqual(settings.app_env, "prod")


if __name__ == "__main__":
    unittest.main()
