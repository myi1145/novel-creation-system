import unittest
from unittest.mock import patch

from app.core.config import settings
from tests.real_provider_test_helper import evaluate_real_provider_readiness


class RealProviderTestHelperTest(unittest.TestCase):
    def test_readiness_should_fail_when_provider_not_configured(self):
        with patch.object(settings, "agent_provider", "mock"), patch.object(settings, "agent_fallback_to_mock", True):
            result = evaluate_real_provider_readiness()
        self.assertFalse(result.ready)
        self.assertTrue(any("AGENT_PROVIDER" in reason for reason in result.reasons))

    def test_readiness_should_pass_with_required_real_provider_config(self):
        with (
            patch.object(settings, "agent_provider", "openai_compatible"),
            patch.object(settings, "agent_fallback_to_mock", False),
            patch.object(settings, "agent_api_base_url", "https://example.com/v1"),
            patch.object(settings, "agent_api_key", "sk-test"),
            patch.object(settings, "agent_model", "gpt-test"),
        ):
            result = evaluate_real_provider_readiness()
        self.assertTrue(result.ready)
        self.assertEqual(result.reasons, [])


if __name__ == "__main__":
    unittest.main()
