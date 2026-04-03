import unittest
from argparse import Namespace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import runbook_checks


class RuntimeRunbookTest(unittest.TestCase):
    @patch("scripts.runbook_checks.run_preflight", return_value=(True, []))
    def test_preflight_success_path(self, mocked_preflight):
        outcome = runbook_checks.run_preflight_step(expected_env="real-provider", env_file=Path(".env"))
        self.assertTrue(outcome.passed)
        self.assertFalse(outcome.block_startup)
        mocked_preflight.assert_called_once()

    @patch("scripts.runbook_checks.run_preflight", return_value=(False, ["AGENT_API_KEY missing"]))
    def test_preflight_failure_blocks_startup(self, mocked_preflight):
        outcome = runbook_checks.run_preflight_step(expected_env="prod", env_file=Path(".env"))
        self.assertFalse(outcome.passed)
        self.assertTrue(outcome.block_startup)
        self.assertIn("禁止启动", outcome.message)
        mocked_preflight.assert_called_once()

    @patch("scripts.runbook_checks.subprocess.run")
    def test_migration_not_ready_blocks_startup(self, mocked_run):
        mocked_run.side_effect = [
            unittest.mock.Mock(returncode=0, stdout="abc123 (head)\n", stderr=""),
            unittest.mock.Mock(returncode=0, stdout="xyz999\n", stderr=""),
        ]
        outcome = runbook_checks.run_migration_check()
        self.assertFalse(outcome.passed)
        self.assertTrue(outcome.block_startup)
        self.assertIn("alembic upgrade head", outcome.message)

    def test_evidence_generated_when_all_passed(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            args = Namespace(
                env="real-provider",
                env_file=".env",
                health_url="http://127.0.0.1:8000/health",
                stage_suite="real-smoke",
                skip_stage_acceptance=False,
            )
            outcomes = [
                runbook_checks.StepOutcome("preflight", True, False, False, "ok"),
                runbook_checks.StepOutcome("migration", True, False, False, "ok"),
                runbook_checks.StepOutcome("stage-acceptance:real-smoke", True, False, False, "ok"),
            ]
            try:
                evidence_dir = runbook_checks.write_evidence_pack(args=args, outcomes=outcomes, exit_code=0)
                summary_json = evidence_dir / "runbook_summary.json"
                summary_md = evidence_dir / "runbook_summary.md"
                self.assertTrue(summary_json.exists())
                self.assertTrue(summary_md.exists())
                payload = json.loads(summary_json.read_text(encoding="utf-8"))
                self.assertEqual(payload["overall_result"], "passed")
                self.assertEqual(payload["exit_code"], 0)
                self.assertIn("steps", payload)
                self.assertIn("recommended_action", payload)
            finally:
                os.chdir(old_cwd)

    def test_evidence_marks_startup_blocked_on_preflight_failure(self):
        args = Namespace(env="prod", env_file=".env", health_url="", stage_suite="real-acceptance", skip_stage_acceptance=True)
        outcomes = [
            runbook_checks.StepOutcome("preflight", False, True, True, "preflight 未通过"),
        ]
        context = runbook_checks._build_evidence_context(args=args, outcomes=outcomes, exit_code=2)
        self.assertEqual(context.overall_result, "startup_blocked")
        self.assertTrue(context.startup_blocked)
        self.assertIn("启动阻断", context.recommended_action)

    def test_evidence_marks_prod_release_blocked_on_stage_failure(self):
        args = Namespace(env="real-provider", env_file=".env", health_url="", stage_suite="real-acceptance", skip_stage_acceptance=False)
        outcomes = [
            runbook_checks.StepOutcome("preflight", True, False, False, "ok"),
            runbook_checks.StepOutcome("stage-acceptance:real-acceptance", False, False, True, "failed"),
        ]
        context = runbook_checks._build_evidence_context(args=args, outcomes=outcomes, exit_code=3)
        self.assertEqual(context.overall_result, "prod_release_blocked")
        self.assertFalse(context.startup_blocked)
        self.assertTrue(context.prod_release_blocked)


if __name__ == "__main__":
    unittest.main()
