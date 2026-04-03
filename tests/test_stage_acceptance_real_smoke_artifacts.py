import unittest

from tests.run_stage_acceptance import (
    _build_failure_summary,
    _classify_agent_call_failures,
    _extract_failed_test_nodes,
    _render_failure_summary_markdown,
)


class StageAcceptanceRealSmokeArtifactsTest(unittest.TestCase):
    def test_extract_failed_test_nodes_should_parse_unittest_output(self):
        output = """
FAIL: test_smoke_path (tests.test_real_provider_single_chapter_smoke.RealProviderSingleChapterSmokeTest)
ERROR: test_other_path (tests.test_other_module.OtherTest)
"""
        self.assertEqual(
            _extract_failed_test_nodes(output),
            [
                "test_smoke_path (tests.test_real_provider_single_chapter_smoke.RealProviderSingleChapterSmokeTest)",
                "test_other_path (tests.test_other_module.OtherTest)",
            ],
        )

    def test_classify_agent_call_failures_should_group_failure_types(self):
        calls = [
            {"call_status": "error", "error_type": "timeout", "fallback_used": False, "active_provider": "openai_compatible"},
            {"call_status": "error", "error_type": "parse_e002", "fallback_used": False, "active_provider": "openai_compatible"},
            {"call_status": "error", "error_type": "rate_limited", "fallback_used": False, "active_provider": "openai_compatible"},
            {"call_status": "fallback_success", "error_type": None, "fallback_used": True, "active_provider": "mock"},
            {
                "call_status": "success",
                "error_type": None,
                "fallback_used": False,
                "active_provider": "openai_compatible",
                "response_summary": {"parse_report": {"decision": "failed", "degraded": True}},
            },
        ]
        stats = _classify_agent_call_failures(calls)
        self.assertEqual(stats["provider_call_failures"], 1)
        self.assertEqual(stats["structured_output_failures"], 2)
        self.assertEqual(stats["governance_blocked"], 1)
        self.assertEqual(stats["fallback_violations"], 1)

    def test_build_failure_summary_should_produce_readable_signals(self):
        suite_results = [
            {"suite": "real-smoke", "exit_code": 1, "failed_tests": ["test_a (tests.x.X)"]},
            {"suite": "core", "exit_code": 0, "failed_tests": []},
        ]
        agent_call_summary = {
            "recent_calls": [
                {"call_status": "error", "error_type": "timeout", "fallback_used": False, "active_provider": "openai_compatible"}
            ]
        }
        summary = _build_failure_summary(suite_results=suite_results, agent_call_summary=agent_call_summary)
        markdown = _render_failure_summary_markdown(summary)
        self.assertIn("real-smoke", summary["failed_suites"])
        self.assertIn("provider_call_failure", summary["failure_categories"])
        self.assertIn("test_a (tests.x.X)", markdown)
        self.assertIn("provider config/secret", markdown)


if __name__ == "__main__":
    unittest.main()
