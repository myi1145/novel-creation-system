import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import release_signoff


class ReleaseSignoffTest(unittest.TestCase):
    def _write_runbook_summary(self, evidence_dir: Path, overall_result: str) -> None:
        payload = {
            "overall_result": overall_result,
            "recommended_action": "test recommendation",
            "steps": [
                {
                    "step": "preflight",
                    "passed": overall_result == "passed",
                    "block_startup": True,
                    "block_prod_release": True,
                    "message": "test",
                }
            ],
            "linked_artifacts": {
                "stage_acceptance_summary": "output/stage_acceptance_summary_20260101T000000Z.json"
            },
        }
        (evidence_dir / "runbook_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_passed_allows_approve(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                evidence_dir = Path("output/runbook_evidence/20260101T000000Z_prod")
                evidence_dir.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(evidence_dir=evidence_dir, overall_result="passed")

                signoff_dir = release_signoff.create_signoff_record(
                    decision="approve",
                    env="prod",
                    operator="alice",
                    evidence_dir=evidence_dir,
                    reason="all checks passed",
                    notes="",
                )
                payload = json.loads((signoff_dir / "release_signoff.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["decision"], "approve")
                self.assertEqual(payload["operator"], "alice")
            finally:
                os.chdir(old_cwd)

    def test_startup_blocked_reject_allowed_and_approve_blocked(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                evidence_dir = Path("output/runbook_evidence/20260101T000000Z_prod")
                evidence_dir.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(evidence_dir=evidence_dir, overall_result="startup_blocked")

                signoff_dir = release_signoff.create_signoff_record(
                    decision="reject",
                    env="prod",
                    operator="bob",
                    evidence_dir=evidence_dir,
                    reason="startup blocked",
                    notes="",
                )
                self.assertTrue((signoff_dir / "release_signoff.md").exists())

                with self.assertRaisesRegex(ValueError, "只允许 decision=reject"):
                    release_signoff.create_signoff_record(
                        decision="approve",
                        env="prod",
                        operator="bob",
                        evidence_dir=evidence_dir,
                        reason="invalid approve",
                        notes="",
                    )
            finally:
                os.chdir(old_cwd)

    def test_prod_release_blocked_disallows_approve_prod(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                evidence_dir = Path("output/runbook_evidence/20260101T000000Z_prod")
                evidence_dir.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(evidence_dir=evidence_dir, overall_result="prod_release_blocked")

                with self.assertRaisesRegex(ValueError, "只有 runbook_summary.overall_result=passed"):
                    release_signoff.create_signoff_record(
                        decision="approve",
                        env="prod",
                        operator="carol",
                        evidence_dir=evidence_dir,
                        reason="invalid approve",
                        notes="",
                    )
            finally:
                os.chdir(old_cwd)

    def test_outputs_json_and_md_with_required_fields(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                evidence_dir = Path("output/runbook_evidence/20260101T000000Z_real-provider")
                evidence_dir.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(evidence_dir=evidence_dir, overall_result="passed")

                signoff_dir = release_signoff.create_signoff_record(
                    decision="rollback",
                    env="real-provider",
                    operator="dave",
                    evidence_dir=evidence_dir,
                    reason="post-release rollback drill",
                    notes="drill only",
                )

                json_path = signoff_dir / "release_signoff.json"
                md_path = signoff_dir / "release_signoff.md"
                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())

                payload = json.loads(json_path.read_text(encoding="utf-8"))
                required_fields = {
                    "generated_at",
                    "decided_at",
                    "env",
                    "decision",
                    "operator",
                    "reason",
                    "notes",
                    "linked_evidence_dir",
                    "linked_runbook_summary_json",
                    "linked_stage_acceptance_summary",
                    "required_checks_status",
                    "recommendation_source",
                }
                self.assertTrue(required_fields.issubset(set(payload.keys())))
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
