import unittest
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from tests.run_stage_acceptance import (
    _build_failure_summary,
    _classify_agent_call_failures,
    _extract_failed_test_nodes,
    _render_failure_summary_markdown,
    _write_real_provider_artifacts,
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

    def test_run_stage_acceptance_should_use_manifest_bound_sequence_artifact_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            os.chdir(temp_dir)
            try:
                output_dir = Path("output")
                old_dir = output_dir / "real_provider_sequence_acceptance" / "old_dir"
                new_dir = output_dir / "real_provider_sequence_acceptance" / "new_dir"
                old_dir.mkdir(parents=True, exist_ok=True)
                new_dir.mkdir(parents=True, exist_ok=True)
                (old_dir / "acceptance_summary.json").write_text('{"source":"old"}', encoding="utf-8")
                (old_dir / "sequence_batch_report.json").write_text('{"source":"old"}', encoding="utf-8")
                (new_dir / "acceptance_summary.json").write_text('{"source":"new"}', encoding="utf-8")
                (new_dir / "sequence_batch_report.json").write_text('{"source":"new"}', encoding="utf-8")

                started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
                (output_dir / "current_real_provider_sequence_artifact.json").write_text(
                    json.dumps(
                        {
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "artifact_dir": new_dir.as_posix(),
                            "acceptance_summary_path": (new_dir / "acceptance_summary.json").as_posix(),
                            "sequence_batch_report_path": (new_dir / "sequence_batch_report.json").as_posix(),
                            "workflow_run_id": "wf-new",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                summary_path = output_dir / "summary.json"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text('{"results":[]}', encoding="utf-8")
                with patch("tests.run_stage_acceptance._collect_real_provider_runtime_artifacts", return_value={}):
                    artifact_dir = _write_real_provider_artifacts(
                        suite_arg="real-acceptance",
                        summary_path=summary_path,
                        suite_results=[],
                        suite_started_at=started_at,
                    )

                acceptance_payload = json.loads((artifact_dir / "real_provider_acceptance_summary.json").read_text(encoding="utf-8"))
                batch_payload = json.loads((artifact_dir / "real_provider_sequence_batch_report.json").read_text(encoding="utf-8"))
                self.assertEqual(acceptance_payload["source"], "new")
                self.assertEqual(batch_payload["source"], "new")
            finally:
                os.chdir(original_cwd)

    def test_run_stage_acceptance_should_not_fallback_to_stale_sequence_dir_without_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            os.chdir(temp_dir)
            try:
                output_dir = Path("output")
                stale_dir = output_dir / "real_provider_sequence_acceptance" / "stale_dir"
                stale_dir.mkdir(parents=True, exist_ok=True)
                (stale_dir / "acceptance_summary.json").write_text('{"source":"stale"}', encoding="utf-8")
                (stale_dir / "sequence_batch_report.json").write_text('{"source":"stale"}', encoding="utf-8")

                started_at = datetime.now(timezone.utc)
                summary_path = output_dir / "summary.json"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text('{"results":[]}', encoding="utf-8")
                with patch("tests.run_stage_acceptance._collect_real_provider_runtime_artifacts", return_value={}):
                    artifact_dir = _write_real_provider_artifacts(
                        suite_arg="real-smoke",
                        summary_path=summary_path,
                        suite_results=[],
                        suite_started_at=started_at,
                    )

                self.assertFalse((artifact_dir / "real_provider_acceptance_summary.json").exists())
                self.assertFalse((artifact_dir / "real_provider_sequence_batch_report.json").exists())
                manifest_payload = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest_payload["sequence_artifact_binding"]["status"], "missing_manifest")
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
