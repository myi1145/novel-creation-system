"""阶段验收统一入口：收口 core / real-smoke / real-acceptance。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORE_TESTS = [
    "tests.test_workflow_revision_effectiveness",
    "tests.test_publish_quality_delta_gate",
    "tests.test_workflow_sequence_cycle_closure",
    "tests.test_workflow_revision_loop",
    "tests.test_workflow_revision_policy",
    "tests.test_workflow_chapter_cycle_strategy",
    "tests.test_workflow_automation_validation",
    "tests.test_workflow_sequence_idempotency",
    "tests.test_chapter_goal_api",
    "tests.test_seed_consumption_gate",
    "tests.test_character_voice_gate",
    "tests.test_style_gate",
    "tests.test_over_explained_rewrite_changeset",
]

REAL_SMOKE_TESTS = [
    "tests.test_real_provider_single_chapter_smoke",
]

REAL_ACCEPTANCE_TESTS = [
    "tests.test_real_provider_single_chapter_repeat_acceptance",
    "tests.test_real_provider_multi_chapter_continuity",
    "tests.test_real_provider_multi_chapter_revision_acceptance",
]

SUITE_MODULES = {
    "core": CORE_TESTS,
    "real-smoke": REAL_SMOKE_TESTS,
    "real-acceptance": REAL_ACCEPTANCE_TESTS,
}


def build_execution_plan(suite: str) -> list[tuple[str, list[str]]]:
    if suite == "all":
        return [
            ("core", CORE_TESTS),
            ("real-smoke", REAL_SMOKE_TESTS),
            ("real-acceptance", REAL_ACCEPTANCE_TESTS),
        ]
    return [(suite, SUITE_MODULES[suite])]


def _contains_skip(output: str) -> bool:
    if "skipped=" in output:
        return True
    return bool(re.search(r"\\bskipped\\s+\\d+", output))


def _run_single_suite(suite_name: str, modules: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "unittest", *modules]
    print(f"[stage-acceptance] suite={suite_name} running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, text=True, capture_output=True)

    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    merged_output = f"{completed.stdout}\n{completed.stderr}"
    return {
        "suite": suite_name,
        "modules": modules,
        "exit_code": completed.returncode,
        "contains_skip": _contains_skip(merged_output),
    }


def _write_summary(summary_items: list[dict[str, Any]], suite_arg: str, summary_file: Path | None) -> Path:
    output_path = summary_file
    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = Path("output") / f"stage_acceptance_summary_{suite_arg}_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_suite": suite_arg,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": summary_items,
        "overall_exit_code": 0 if all(item["exit_code"] == 0 for item in summary_items) else 1,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage acceptance suites.")
    parser.add_argument("--suite", choices=["core", "real-smoke", "real-acceptance", "all"], default="core")
    parser.add_argument("--summary-file", default="", help="Optional JSON summary output path.")
    args = parser.parse_args()

    execution_plan = build_execution_plan(args.suite)
    suite_results = [_run_single_suite(name, modules) for name, modules in execution_plan]

    print("\n[stage-acceptance] summary")
    for item in suite_results:
        print(
            f"- suite={item['suite']} modules={len(item['modules'])} exit_code={item['exit_code']} contains_skip={item['contains_skip']}"
        )

    summary_path = _write_summary(
        suite_results,
        suite_arg=args.suite,
        summary_file=(Path(args.summary_file) if args.summary_file else None),
    )
    print(f"[stage-acceptance] summary_file={summary_path}")

    return 0 if all(item["exit_code"] == 0 for item in suite_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
