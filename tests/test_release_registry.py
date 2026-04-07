import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import release_signoff


class ReleaseRegistryTest(unittest.TestCase):
    def _write_runbook_summary(self, evidence_dir: Path, overall_result: str, stage_suffix: str) -> None:
        payload = {
            "overall_result": overall_result,
            "recommended_action": f"recommended for {overall_result}",
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
                "stage_acceptance_summary": f"output/stage_acceptance_summary_{stage_suffix}.json"
            },
        }
        (evidence_dir / "runbook_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_registry_updates_latest_pointers_and_index_links(self):
        with TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                prod_evidence = Path("output/runbook_evidence/20260101T000000Z_prod")
                prod_evidence.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(prod_evidence, "passed", "20260101T000000Z")

                release_signoff.create_signoff_record(
                    decision="approve",
                    env="prod",
                    operator="alice",
                    evidence_dir=prod_evidence,
                    reason="prod approved",
                    notes="",
                    decided_at="2026-01-01T00:00:00+00:00",
                )

                real_provider_evidence = Path("output/runbook_evidence/20260101T010000Z_real-provider")
                real_provider_evidence.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(real_provider_evidence, "startup_blocked", "20260101T010000Z")

                release_signoff.create_signoff_record(
                    decision="reject",
                    env="real-provider",
                    operator="bob",
                    evidence_dir=real_provider_evidence,
                    reason="rollback drill rejected",
                    notes="",
                    decided_at="2026-01-01T01:00:00+00:00",
                )

                latest_prod = json.loads(
                    Path("output/release_registry/latest_prod_signoff.json").read_text(encoding="utf-8")
                )
                self.assertEqual(latest_prod["env"], "prod")
                self.assertEqual(latest_prod["decision"], "approve")
                self.assertEqual(latest_prod["operator"], "alice")

                latest_real_provider = json.loads(
                    Path("output/release_registry/latest_real_provider_signoff.json").read_text(encoding="utf-8")
                )
                self.assertEqual(latest_real_provider["env"], "real-provider")
                self.assertEqual(latest_real_provider["decision"], "reject")
                self.assertEqual(latest_real_provider["operator"], "bob")

                release_index = json.loads(
                    Path("output/release_registry/release_index.json").read_text(encoding="utf-8")
                )
                self.assertGreaterEqual(len(release_index["entries"]), 2)
                first_entry = release_index["entries"][0]
                self.assertEqual(first_entry["env"], "real-provider")
                self.assertTrue(first_entry["linked_evidence_dir"].endswith("_real-provider"))
                self.assertTrue(first_entry["linked_runbook_summary_json"].endswith("runbook_summary.json"))
                self.assertIn("stage_acceptance_summary", first_entry["linked_stage_acceptance_summary"])
                self.assertIn("latest_status_summary", release_index["latest_pointers"]["latest_runbook_evidence"])
                self.assertIn("recommended_action", release_index["latest_pointers"]["latest_runbook_evidence"])

                latest_runbook_evidence = json.loads(
                    Path("output/release_registry/latest_runbook_evidence.json").read_text(encoding="utf-8")
                )
                self.assertIn("linked_runbook_summary_json", latest_runbook_evidence)
                self.assertIn("linked_stage_acceptance_summary", latest_runbook_evidence)
                self.assertIn("overall_result", latest_runbook_evidence)
                self.assertIn("recommended_action", latest_runbook_evidence)

                newer_prod_evidence = Path("output/runbook_evidence/20260101T020000Z_prod")
                newer_prod_evidence.mkdir(parents=True, exist_ok=True)
                self._write_runbook_summary(newer_prod_evidence, "passed", "20260101T020000Z")
                release_signoff.create_signoff_record(
                    decision="approve",
                    env="prod",
                    operator="carol",
                    evidence_dir=newer_prod_evidence,
                    reason="newer prod approved",
                    notes="",
                    decided_at="2026-01-01T02:00:00+00:00",
                )

                refreshed_latest_prod = json.loads(
                    Path("output/release_registry/latest_prod_signoff.json").read_text(encoding="utf-8")
                )
                self.assertEqual(refreshed_latest_prod["operator"], "carol")
                self.assertTrue(refreshed_latest_prod["linked_evidence_dir"].endswith("_prod"))
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
