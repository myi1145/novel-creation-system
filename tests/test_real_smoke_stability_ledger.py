import json
import os
import tempfile
import unittest
from pathlib import Path

from tests import run_stage_acceptance


def _write_record(path: Path, *, generated_at: str, failure_bucket: str, artifact_present: bool = True, artifact_count: int = 6) -> None:
    path.write_text(
        json.dumps(
            {
                "suite": "real-smoke",
                "generated_at": generated_at,
                "summary_file": "output/stage_acceptance_summary_real-smoke_demo.json",
                "overall_exit_code": 0 if failure_bucket == "passed" else 1,
                "contains_skip": False,
                "modules": ["tests.test_real_provider_single_chapter_smoke"],
                "output_artifact_present": artifact_present,
                "output_artifact_count": artifact_count,
                "failure_bucket": failure_bucket,
                "provider_mode": "unknown",
                "fallback_disabled": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class RealSmokeStabilityLedgerTest(unittest.TestCase):
    def test_should_aggregate_multiple_records_into_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_record(output_dir / "real_smoke_stability_record_1.json", generated_at="2026-04-01T00:00:00+00:00", failure_bucket="passed")
            _write_record(
                output_dir / "real_smoke_stability_record_2.json",
                generated_at="2026-04-02T00:00:00+00:00",
                failure_bucket="artifact_missing",
                artifact_present=False,
                artifact_count=2,
            )
            _write_record(
                output_dir / "real_smoke_stability_record_3.json",
                generated_at="2026-04-03T00:00:00+00:00",
                failure_bucket="unknown_failure",
                artifact_present=False,
                artifact_count=0,
            )

            ledger_path, _ = run_stage_acceptance._write_real_smoke_stability_ledger(output_dir=output_dir)
            payload = json.loads(ledger_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["record_count"], 3)
            self.assertEqual(payload["pass_count"], 1)
            self.assertEqual(payload["fail_count"], 2)
            self.assertEqual(payload["failure_bucket_breakdown"]["passed"], 1)
            self.assertEqual(payload["failure_bucket_breakdown"]["artifact_missing"], 1)
            self.assertEqual(payload["failure_bucket_breakdown"]["unknown_failure"], 1)

    def test_should_sort_by_generated_at_and_compute_latest_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_record(
                output_dir / "real_smoke_stability_record_b.json",
                generated_at="2026-04-03T00:00:00+00:00",
                failure_bucket="artifact_missing",
                artifact_present=False,
                artifact_count=0,
            )
            _write_record(output_dir / "real_smoke_stability_record_a.json", generated_at="2026-04-01T00:00:00+00:00", failure_bucket="passed")
            _write_record(
                output_dir / "real_smoke_stability_record_c.json",
                generated_at="2026-04-02T00:00:00+00:00",
                failure_bucket="unknown_failure",
                artifact_present=False,
                artifact_count=0,
            )

            ledger_path, _ = run_stage_acceptance._write_real_smoke_stability_ledger(output_dir=output_dir)
            payload = json.loads(ledger_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["records"][0]["generated_at"], "2026-04-01T00:00:00+00:00")
            self.assertEqual(payload["latest_success_at"], "2026-04-01T00:00:00+00:00")
            self.assertEqual(payload["latest_failure_at"], "2026-04-03T00:00:00+00:00")
            self.assertEqual(payload["consecutive_failure_count"], 2)

    def test_latest_markdown_should_include_key_summary_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_record(output_dir / "real_smoke_stability_record_1.json", generated_at="2026-04-01T00:00:00+00:00", failure_bucket="passed")
            _write_record(
                output_dir / "real_smoke_stability_record_2.json",
                generated_at="2026-04-02T00:00:00+00:00",
                failure_bucket="artifact_missing",
                artifact_present=False,
                artifact_count=0,
            )

            _, latest_path = run_stage_acceptance._write_real_smoke_stability_ledger(output_dir=output_dir)
            content = latest_path.read_text(encoding="utf-8")

            self.assertIn("pass_rate:", content)
            self.assertIn("latest_success_at:", content)
            self.assertIn("consecutive_failure_count:", content)

    def test_empty_input_should_generate_stable_empty_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            os.chdir(tmp)
            try:
                output_dir = Path("output")
                output_dir.mkdir(parents=True, exist_ok=True)
                ledger_path, latest_path = run_stage_acceptance._write_real_smoke_stability_ledger(output_dir=output_dir)
                payload = json.loads(ledger_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["record_count"], 0)
                self.assertEqual(payload["pass_count"], 0)
                self.assertEqual(payload["fail_count"], 0)
                self.assertEqual(payload["pass_rate"], 0.0)
                self.assertEqual(payload["consecutive_failure_count"], 0)
                self.assertEqual(payload["failure_bucket_breakdown"], {})
                self.assertIn("sample_count: 0", latest_path.read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
