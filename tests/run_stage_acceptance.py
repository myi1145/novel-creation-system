"""阶段验收统一入口：收口 core / real-smoke / real-acceptance。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_SEQUENCE_ARTIFACT_MANIFEST = Path("output") / "current_real_provider_sequence_artifact.json"
REAL_SMOKE_REQUIRED_FILES_FALLBACK = (
    "stage_acceptance_summary.json",
    "agent_calls_summary.json",
    "provider_governance_snapshot.json",
    "diagnostics_overview.json",
    "failure_summary.json",
    "failure_summary.md",
)

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
        "failed_tests": _extract_failed_test_nodes(merged_output),
        "raw_output": merged_output,
    }


def _extract_failed_test_nodes(output: str) -> list[str]:
    pattern = re.compile(r"^(?:FAIL|ERROR):\s+(.+)$", re.MULTILINE)
    return [item.strip() for item in pattern.findall(output)]


def _write_summary(summary_items: list[dict[str, Any]], suite_arg: str, summary_file: Path | None) -> Path:
    output_path = summary_file
    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = Path("output") / f"stage_acceptance_summary_{suite_arg}_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_suite": suite_arg,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [{k: v for k, v in item.items() if k != "raw_output"} for item in summary_items],
        "overall_exit_code": 0 if all(item["exit_code"] == 0 for item in summary_items) else 1,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path




def _detect_provider_mode() -> str:
    provider = os.getenv("AGENT_PROVIDER", "").strip()
    return provider or "unknown"


def _detect_fallback_disabled() -> bool:
    fallback = os.getenv("AGENT_FALLBACK_TO_MOCK", "").strip().lower()
    return fallback == "false"


def _load_real_smoke_required_files() -> list[str]:
    try:
        from tests.validate_real_smoke_artifacts import REQUIRED_FILES

        return [str(item) for item in REQUIRED_FILES]
    except Exception:  # noqa: BLE001
        return list(REAL_SMOKE_REQUIRED_FILES_FALLBACK)


def _count_real_smoke_required_artifacts(artifact_dir: Path | None) -> tuple[bool, int]:
    if artifact_dir is None:
        return False, 0

    required_files = _load_real_smoke_required_files()

    count = 0
    for file_name in required_files:
        if (artifact_dir / file_name).exists():
            count += 1
    return bool(required_files) and count == len(required_files), count


def _infer_failure_bucket(*, overall_exit_code: int, output_artifact_present: bool, raw_output: str) -> str:
    if overall_exit_code == 0 and output_artifact_present:
        return "passed"
    if overall_exit_code == 0 and not output_artifact_present:
        return "artifact_missing"

    lowered = raw_output.lower()
    config_keywords = [
        "未配置",
        "must be",
        "missing",
        "precondition",
        "environment",
        "agent_api_key",
        "agent_api_base_url",
        "agent_model",
        "agent_provider",
    ]
    runtime_keywords = [
        "timeout",
        "timed out",
        "connection",
        "network",
        "provider",
        "rate",
        "circuit",
        "api",
    ]

    if any(keyword in lowered for keyword in config_keywords):
        return "config_or_precondition"
    if any(keyword in lowered for keyword in runtime_keywords):
        return "provider_or_runtime"
    return "unknown_failure"


def _write_real_smoke_stability_record(
    *,
    summary_path: Path,
    suite_results: list[dict[str, Any]],
    artifact_dir: Path | None,
) -> Path:
    smoke_result = next((item for item in suite_results if item.get("suite") == "real-smoke"), None)
    modules = list(smoke_result.get("modules", [])) if smoke_result else []
    contains_skip = bool(smoke_result.get("contains_skip")) if smoke_result else False
    raw_output = str(smoke_result.get("raw_output") or "") if smoke_result else ""
    overall_exit_code = 0 if all(item.get("exit_code") == 0 for item in suite_results) else 1
    output_artifact_present, output_artifact_count = _count_real_smoke_required_artifacts(artifact_dir)

    payload = {
        "suite": "real-smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary_file": summary_path.as_posix(),
        "overall_exit_code": overall_exit_code,
        "contains_skip": contains_skip,
        "modules": modules,
        "output_artifact_present": output_artifact_present,
        "output_artifact_count": output_artifact_count,
        "failure_bucket": _infer_failure_bucket(
            overall_exit_code=overall_exit_code,
            output_artifact_present=output_artifact_present,
            raw_output=raw_output,
        ),
        "provider_mode": _detect_provider_mode(),
        "fallback_disabled": _detect_fallback_disabled(),
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = Path("output") / f"real_smoke_stability_record_{ts}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = Path("output") / "real_smoke_stability_record_latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _classify_agent_call_failures(agent_calls: list[dict[str, Any]]) -> dict[str, int]:
    stats = {
        "provider_call_failures": 0,
        "structured_output_failures": 0,
        "governance_blocked": 0,
        "fallback_violations": 0,
    }
    for item in agent_calls:
        error_type = str(item.get("error_type") or "").strip().lower()
        call_status = str(item.get("call_status") or "").strip().lower()
        fallback_used = bool(item.get("fallback_used"))
        active_provider = str(item.get("active_provider") or "").strip().lower()
        response_summary = item.get("response_summary") if isinstance(item.get("response_summary"), dict) else {}
        parse_report = response_summary.get("parse_report") if isinstance(response_summary, dict) else None

        if call_status == "error":
            if error_type in {"rate_limited", "circuit_open"}:
                stats["governance_blocked"] += 1
            elif error_type.startswith("parse_"):
                stats["structured_output_failures"] += 1
            else:
                stats["provider_call_failures"] += 1

        if isinstance(parse_report, dict):
            decision = str(parse_report.get("decision") or "").strip().lower()
            degraded = bool(parse_report.get("degraded"))
            if decision in {"failed", "rejected"} or degraded:
                stats["structured_output_failures"] += 1

        if fallback_used or call_status == "fallback_success" or active_provider == "mock":
            stats["fallback_violations"] += 1
    return stats


def _build_failure_summary(
    suite_results: list[dict[str, Any]],
    agent_call_summary: dict[str, Any],
) -> dict[str, Any]:
    failed_suites = [item for item in suite_results if item["exit_code"] != 0]
    failed_test_nodes = [node for suite in failed_suites for node in suite.get("failed_tests", [])]

    agent_fail_stats = _classify_agent_call_failures(agent_call_summary.get("recent_calls", []))
    likely_categories: list[str] = []
    recommendations: list[str] = []

    if agent_fail_stats["provider_call_failures"] > 0:
        likely_categories.append("provider_call_failure")
        recommendations.append("优先检查 provider config/secret（AGENT_API_BASE_URL、AGENT_API_KEY、AGENT_MODEL）与网络连通性。")
    if agent_fail_stats["structured_output_failures"] > 0:
        likely_categories.append("structured_output_failure")
        recommendations.append("优先检查 prompt 输出契约与 parser（结构化输出格式、字段完整性、parse_report）。")
    if agent_fail_stats["governance_blocked"] > 0:
        likely_categories.append("governance_blocked")
        recommendations.append("优先检查 governance 限流/熔断参数与 provider circuit state。")
    if agent_fail_stats["fallback_violations"] > 0:
        likely_categories.append("fallback_violation")
        recommendations.append("优先检查 gateway fallback 配置（AGENT_FALLBACK_TO_MOCK）与调用日志 fallback_used/call_status。")
    if not likely_categories and failed_suites:
        likely_categories.append("unknown")
        recommendations.append("先查看 diagnostics overview 与最近 agent 调用记录，定位失败阶段。")

    return {
        "failed_suites": [item["suite"] for item in failed_suites],
        "failed_test_nodes": failed_test_nodes,
        "failure_categories": likely_categories,
        "agent_failure_stats": agent_fail_stats,
        "recommendations": recommendations,
    }


def _render_failure_summary_markdown(failure_summary: dict[str, Any]) -> str:
    failed_suites = failure_summary.get("failed_suites") or []
    failed_nodes = failure_summary.get("failed_test_nodes") or []
    categories = failure_summary.get("failure_categories") or ["unknown"]
    recommendations = failure_summary.get("recommendations") or []
    stats = failure_summary.get("agent_failure_stats") or {}
    return "\n".join(
        [
            "# Real Provider Smoke Failure Summary",
            "",
            f"- failed_suites: {', '.join(failed_suites) if failed_suites else 'none'}",
            f"- failed_tests_or_stages: {', '.join(failed_nodes) if failed_nodes else 'none'}",
            f"- failure_categories: {', '.join(categories)}",
            "",
            "## Agent Failure Stats",
            f"- provider_call_failures: {stats.get('provider_call_failures', 0)}",
            f"- structured_output_failures: {stats.get('structured_output_failures', 0)}",
            f"- governance_blocked: {stats.get('governance_blocked', 0)}",
            f"- fallback_violations: {stats.get('fallback_violations', 0)}",
            "",
            "## Suggested First Checks",
            *[f"- {item}" for item in recommendations],
            "",
        ]
    )


def _collect_real_provider_runtime_artifacts() -> dict[str, Any]:
    try:
        from app.db.session import SessionLocal
        from app.services.workflow_service import workflow_service
    except Exception as exc:  # noqa: BLE001
        return {"collection_error": str(exc)}

    db = SessionLocal()
    try:
        diagnostics_overview = workflow_service.get_diagnostics_overview(db=db)
        governance_snapshot = workflow_service.get_agent_governance(db=db)
        recent_calls = workflow_service.list_agent_calls(db=db, limit=200)
        call_stats = workflow_service.get_agent_call_stats(db=db)
    finally:
        db.close()

    return {
        "diagnostics_overview": diagnostics_overview,
        "provider_governance_snapshot": governance_snapshot,
        "agent_calls_summary": {
            "stats": call_stats,
            "recent_calls": recent_calls[:50],
            "total_calls_collected": len(recent_calls),
        },
    }


def _write_real_provider_artifacts(
    *,
    suite_arg: str,
    summary_path: Path,
    suite_results: list[dict[str, Any]],
    suite_started_at: datetime,
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = Path("output") / f"{suite_arg}_artifacts_{ts}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    runtime_artifacts = _collect_real_provider_runtime_artifacts()
    failure_summary = _build_failure_summary(suite_results=suite_results, agent_call_summary=runtime_artifacts.get("agent_calls_summary", {}))
    failure_markdown = _render_failure_summary_markdown(failure_summary)

    (artifact_dir / "stage_acceptance_summary.json").write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")
    (artifact_dir / "agent_calls_summary.json").write_text(
        json.dumps(runtime_artifacts.get("agent_calls_summary", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "provider_governance_snapshot.json").write_text(
        json.dumps(runtime_artifacts.get("provider_governance_snapshot", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "diagnostics_overview.json").write_text(
        json.dumps(runtime_artifacts.get("diagnostics_overview", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "failure_summary.json").write_text(json.dumps(failure_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifact_dir / "failure_summary.md").write_text(failure_markdown, encoding="utf-8")
    sequence_binding = _resolve_current_sequence_artifact_binding(suite_started_at=suite_started_at)
    sequence_artifact_dir = Path(sequence_binding["artifact_dir"]) if sequence_binding.get("artifact_dir") else None
    if sequence_artifact_dir is not None:
        for file_name in ["acceptance_summary.json", "sequence_batch_report.json"]:
            source_file = sequence_artifact_dir / file_name
            if source_file.exists():
                (artifact_dir / f"real_provider_{file_name}").write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")

    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "requested_suite": suite_arg,
                "summary_file": summary_path.as_posix(),
                "files": [
                    "stage_acceptance_summary.json",
                    "agent_calls_summary.json",
                    "provider_governance_snapshot.json",
                    "diagnostics_overview.json",
                    "failure_summary.json",
                    "failure_summary.md",
                    "real_provider_acceptance_summary.json",
                    "real_provider_sequence_batch_report.json",
                ],
                "sequence_artifact_binding": sequence_binding,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifact_dir


def _resolve_current_sequence_artifact_binding(*, suite_started_at: datetime) -> dict[str, Any]:
    if not CURRENT_SEQUENCE_ARTIFACT_MANIFEST.exists():
        return {"status": "missing_manifest", "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix()}

    try:
        payload = json.loads(CURRENT_SEQUENCE_ARTIFACT_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "status": "invalid_manifest",
            "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
            "reason": str(exc),
        }

    artifact_dir = payload.get("artifact_dir")
    generated_at = payload.get("generated_at")
    if not artifact_dir or not generated_at:
        return {
            "status": "invalid_manifest",
            "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
            "reason": "missing artifact_dir or generated_at",
        }

    try:
        manifest_generated_at = datetime.fromisoformat(str(generated_at))
    except ValueError:
        return {
            "status": "invalid_manifest",
            "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
            "reason": "generated_at is not ISO datetime",
        }
    if manifest_generated_at.tzinfo is None:
        manifest_generated_at = manifest_generated_at.replace(tzinfo=timezone.utc)

    if manifest_generated_at < suite_started_at:
        return {
            "status": "stale_manifest",
            "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
            "generated_at": manifest_generated_at.isoformat(),
            "suite_started_at": suite_started_at.isoformat(),
        }

    artifact_path = Path(str(artifact_dir))
    acceptance_summary_path = artifact_path / "acceptance_summary.json"
    sequence_batch_report_path = artifact_path / "sequence_batch_report.json"
    if not acceptance_summary_path.exists() or not sequence_batch_report_path.exists():
        return {
            "status": "invalid_manifest",
            "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
            "artifact_dir": artifact_path.as_posix(),
            "reason": "required sequence artifact files not found",
        }

    return {
        "status": "bound",
        "manifest_path": CURRENT_SEQUENCE_ARTIFACT_MANIFEST.as_posix(),
        "artifact_dir": artifact_path.as_posix(),
        "acceptance_summary_path": acceptance_summary_path.as_posix(),
        "sequence_batch_report_path": sequence_batch_report_path.as_posix(),
        "workflow_run_id": payload.get("workflow_run_id"),
        "generated_at": manifest_generated_at.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage acceptance suites.")
    parser.add_argument("--suite", choices=["core", "real-smoke", "real-acceptance", "all"], default="core")
    parser.add_argument("--summary-file", default="", help="Optional JSON summary output path.")
    args = parser.parse_args()

    suite_started_at = datetime.now(timezone.utc)
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

    artifact_dir: Path | None = None
    if any(item[0] in {"real-smoke", "real-acceptance"} for item in execution_plan):
        artifact_dir = _write_real_provider_artifacts(
            suite_arg=args.suite,
            summary_path=summary_path,
            suite_results=suite_results,
            suite_started_at=suite_started_at,
        )
        print(f"[stage-acceptance] real_provider_artifact_dir={artifact_dir}")

    if args.suite == "real-smoke":
        stability_record_path = _write_real_smoke_stability_record(
            summary_path=summary_path,
            suite_results=suite_results,
            artifact_dir=artifact_dir,
        )
        print(f"[stage-acceptance] real_smoke_stability_record={stability_record_path}")

    return 0 if all(item["exit_code"] == 0 for item in suite_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
