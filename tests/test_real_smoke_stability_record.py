import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import run_stage_acceptance
from tests.validate_real_smoke_artifacts import REQUIRED_FILES


class RealSmokeStabilityRecordTest(unittest.TestCase):
    def test_should_generate_single_stability_record_with_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            os.chdir(tmp)
            try:
                output_dir = Path("output")
                output_dir.mkdir(parents=True, exist_ok=True)
                summary_path = output_dir / "stage_acceptance_summary_real-smoke_demo.json"
                summary_path.write_text('{"requested_suite": "real-smoke"}', encoding="utf-8")

                artifact_dir = output_dir / "real-smoke_artifacts_demo"
                artifact_dir.mkdir(parents=True, exist_ok=True)
                for name in REQUIRED_FILES:
                    (artifact_dir / name).write_text("{}", encoding="utf-8")

                suite_results = [
                    {
                        "suite": "real-smoke",
                        "modules": ["tests.test_real_provider_single_chapter_smoke"],
                        "exit_code": 0,
                        "contains_skip": False,
                        "raw_output": "ok",
                    }
                ]
                with patch.dict(os.environ, {"AGENT_PROVIDER": "openai_compatible", "AGENT_FALLBACK_TO_MOCK": "false"}, clear=False):
                    record_path = run_stage_acceptance._write_real_smoke_stability_record(
                        summary_path=summary_path,
                        suite_results=suite_results,
                        artifact_dir=artifact_dir,
                    )

                payload = json.loads(record_path.read_text(encoding="utf-8"))
                for field in [
                    "suite",
                    "generated_at",
                    "summary_file",
                    "overall_exit_code",
                    "contains_skip",
                    "modules",
                    "output_artifact_present",
                    "output_artifact_count",
                    "failure_bucket",
                    "provider_mode",
                    "fallback_disabled",
                ]:
                    self.assertIn(field, payload)
                self.assertEqual(payload["suite"], "real-smoke")
                self.assertEqual(payload["failure_bucket"], "passed")
                self.assertEqual(payload["output_artifact_count"], len(REQUIRED_FILES))
                self.assertTrue((output_dir / "real_smoke_stability_record_latest.json").exists())
            finally:
                os.chdir(cwd)

    def test_main_real_smoke_should_generate_stability_record_without_breaking_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            os.chdir(tmp)
            try:
                def _fake_artifacts(**kwargs):
                    artifact_dir = Path("output") / "real-smoke_artifacts_fake"
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    for name in REQUIRED_FILES:
                        (artifact_dir / name).write_text("{}", encoding="utf-8")
                    return artifact_dir

                with patch.object(
                    run_stage_acceptance,
                    "_run_single_suite",
                    return_value={
                        "suite": "real-smoke",
                        "modules": ["tests.test_real_provider_single_chapter_smoke"],
                        "exit_code": 0,
                        "contains_skip": False,
                        "failed_tests": [],
                        "raw_output": "OK",
                    },
                ), patch.object(run_stage_acceptance, "_write_real_provider_artifacts", side_effect=_fake_artifacts), patch.object(
                    run_stage_acceptance.sys,
                    "argv",
                    ["run_stage_acceptance.py", "--suite", "real-smoke"],
                ), patch.dict(os.environ, {"AGENT_PROVIDER": "openai_compatible", "AGENT_FALLBACK_TO_MOCK": "false"}, clear=False):
                    exit_code = run_stage_acceptance.main()

                self.assertEqual(exit_code, 0)
                summary_files = list(Path("output").glob("stage_acceptance_summary_real-smoke_*.json"))
                self.assertEqual(len(summary_files), 1)
                summary_payload = json.loads(summary_files[0].read_text(encoding="utf-8"))
                self.assertIn("results", summary_payload)
                self.assertEqual(summary_payload["requested_suite"], "real-smoke")

                stability_files = [
                    item
                    for item in Path("output").glob("real_smoke_stability_record_*.json")
                    if item.name != "real_smoke_stability_record_latest.json"
                ]
                self.assertEqual(len(stability_files), 1)
                stability_payload = json.loads(stability_files[0].read_text(encoding="utf-8"))
                self.assertEqual(stability_payload["summary_file"], summary_files[0].as_posix())
                self.assertEqual(stability_payload["output_artifact_count"], len(REQUIRED_FILES))
                self.assertEqual(stability_payload["failure_bucket"], "passed")
            finally:
                os.chdir(cwd)

    def test_count_should_not_be_zero_when_validator_import_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            for name in REQUIRED_FILES:
                (artifact_dir / name).write_text("{}", encoding="utf-8")

            with patch.object(run_stage_acceptance, "_load_real_smoke_required_files", return_value=list(REQUIRED_FILES)):
                present, count = run_stage_acceptance._count_real_smoke_required_artifacts(artifact_dir)

            self.assertTrue(present)
            self.assertEqual(count, len(REQUIRED_FILES))

    def test_missing_env_should_not_affect_passed_bucket_when_artifacts_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            os.chdir(tmp)
            try:
                output_dir = Path("output")
                output_dir.mkdir(parents=True, exist_ok=True)
                summary_path = output_dir / "stage_acceptance_summary_real-smoke_demo.json"
                summary_path.write_text('{"requested_suite": "real-smoke"}', encoding="utf-8")

                artifact_dir = output_dir / "real-smoke_artifacts_demo"
                artifact_dir.mkdir(parents=True, exist_ok=True)
                for name in REQUIRED_FILES:
                    (artifact_dir / name).write_text("{}", encoding="utf-8")

                suite_results = [
                    {
                        "suite": "real-smoke",
                        "modules": ["tests.test_real_provider_single_chapter_smoke"],
                        "exit_code": 0,
                        "contains_skip": False,
                        "raw_output": "ok",
                    }
                ]
                with patch.dict(os.environ, {}, clear=True):
                    record_path = run_stage_acceptance._write_real_smoke_stability_record(
                        summary_path=summary_path,
                        suite_results=suite_results,
                        artifact_dir=artifact_dir,
                    )

                payload = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["provider_mode"], "unknown")
                self.assertFalse(payload["fallback_disabled"])
                self.assertEqual(payload["failure_bucket"], "passed")
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
