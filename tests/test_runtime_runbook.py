import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
