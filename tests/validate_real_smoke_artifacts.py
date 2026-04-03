"""校验 real-smoke artifacts/manifest 完整性。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FILES = [
    "stage_acceptance_summary.json",
    "agent_calls_summary.json",
    "provider_governance_snapshot.json",
    "diagnostics_overview.json",
    "failure_summary.json",
    "failure_summary.md",
]


def validate_artifact_path(*, artifact_dir: Path | None = None, manifest_path: Path | None = None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    validated_files: list[str] = []

    if manifest_path is None and artifact_dir is None:
        return False, ["必须传入 --artifact-dir 或 --manifest-path。"]

    if manifest_path is None and artifact_dir is not None:
        manifest_path = artifact_dir / "manifest.json"
    if manifest_path is None:
        return False, ["manifest 路径解析失败。"]

    root_dir = manifest_path.parent

    if not manifest_path.exists():
        return False, [f"manifest.json 不存在：{manifest_path}"]

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"manifest.json 解析失败：{exc}"]

    files = payload.get("files")
    if not isinstance(files, list) or not files:
        return False, ["manifest.json 字段 files 缺失或为空。"]

    declared_set = {str(item) for item in files}
    for required in REQUIRED_FILES:
        if required not in declared_set:
            errors.append(f"manifest.json.files 缺少必需文件声明：{required}")

    for required in REQUIRED_FILES:
        candidate = root_dir / required
        if not candidate.exists():
            errors.append(f"artifact 目录缺少必需文件：{candidate}")
        else:
            validated_files.append(required)

    if errors:
        return False, errors
    return True, validated_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real-smoke artifact manifest completeness.")
    parser.add_argument("--artifact-dir", default="", help="Artifact directory path containing manifest.json")
    parser.add_argument("--manifest-path", default="", help="Direct manifest.json path")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else None
    manifest_path = Path(args.manifest_path) if args.manifest_path else None

    ok, details = validate_artifact_path(artifact_dir=artifact_dir, manifest_path=manifest_path)
    if not ok:
        print("[artifact-validate] FAILED")
        for item in details:
            print(f"- {item}")
        return 1

    print("[artifact-validate] OK")
    print("- validated_files:")
    for item in details:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
