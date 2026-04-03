import json
import tempfile
import unittest
from pathlib import Path

from tests.validate_real_smoke_artifacts import REQUIRED_FILES, validate_artifact_path


class ValidateRealSmokeArtifactsTest(unittest.TestCase):
    def _build_valid_artifact_dir(self, root: Path) -> Path:
        artifact_dir = root / "real-smoke_artifacts_20260101T000000Z"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "generated_at": "2026-01-01T00:00:00Z",
            "requested_suite": "real-smoke",
            "summary_file": "output/stage_acceptance_summary_real-smoke_x.json",
            "files": list(REQUIRED_FILES),
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for name in REQUIRED_FILES:
            (artifact_dir / name).write_text("{}", encoding="utf-8")
        return artifact_dir

    def test_should_fail_when_manifest_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, details = validate_artifact_path(artifact_dir=Path(tmp))
            self.assertFalse(ok)
            self.assertIn("manifest.json 不存在", details[0])

    def test_should_fail_when_manifest_json_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "manifest.json").write_text("{invalid-json", encoding="utf-8")
            ok, details = validate_artifact_path(artifact_dir=artifact_dir)
            self.assertFalse(ok)
            self.assertIn("manifest.json 解析失败", details[0])

    def test_should_fail_when_files_field_missing_or_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "manifest.json").write_text(json.dumps({"generated_at": "x"}), encoding="utf-8")
            ok, details = validate_artifact_path(artifact_dir=artifact_dir)
            self.assertFalse(ok)
            self.assertIn("files 缺失或为空", details[0])

    def test_should_fail_when_required_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = self._build_valid_artifact_dir(Path(tmp))
            missing = artifact_dir / REQUIRED_FILES[-1]
            missing.unlink()
            ok, details = validate_artifact_path(artifact_dir=artifact_dir)
            self.assertFalse(ok)
            self.assertTrue(any("artifact 目录缺少必需文件" in item for item in details))

    def test_should_pass_when_manifest_and_files_are_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = self._build_valid_artifact_dir(Path(tmp))
            ok, details = validate_artifact_path(artifact_dir=artifact_dir)
            self.assertTrue(ok)
            self.assertEqual(set(details), set(REQUIRED_FILES))


if __name__ == "__main__":
    unittest.main()
