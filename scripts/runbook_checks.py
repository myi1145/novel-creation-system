#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.preflight import run_preflight

REVISION_PATTERN = re.compile(r"\b[0-9a-f]{6,}\b", re.IGNORECASE)


@dataclass
class StepOutcome:
    step: str
    passed: bool
    block_startup: bool
    block_prod_release: bool
    message: str


@dataclass
class EvidenceContext:
    generated_at: str
    env: str
    env_file: str
    health_url: str
    stage_suite: str
    overall_result: str
    exit_code: int
    recommended_action: str
    startup_blocked: bool
    prod_release_blocked: bool


def _extract_revisions(text: str) -> set[str]:
    return {match.group(0).lower() for match in REVISION_PATTERN.finditer(text)}


def run_preflight_step(expected_env: str, env_file: Path) -> StepOutcome:
    ok, errors = run_preflight(expected_env=expected_env, env_file=env_file)
    if ok:
        return StepOutcome(
            step="preflight",
            passed=True,
            block_startup=False,
            block_prod_release=False,
            message=f"preflight 通过（env={expected_env}, env_file={env_file}）。",
        )

    return StepOutcome(
        step="preflight",
        passed=False,
        block_startup=True,
        block_prod_release=True,
        message="preflight 未通过，禁止启动。\n - " + "\n - ".join(errors),
    )


def run_migration_check() -> StepOutcome:
    heads = subprocess.run(["alembic", "heads"], text=True, capture_output=True)
    if heads.returncode != 0:
        return StepOutcome(
            step="migration",
            passed=False,
            block_startup=True,
            block_prod_release=True,
            message="无法读取 alembic heads，请先修复迁移链路后再启动。",
        )

    current = subprocess.run(["alembic", "current"], text=True, capture_output=True)
    if current.returncode != 0:
        return StepOutcome(
            step="migration",
            passed=False,
            block_startup=True,
            block_prod_release=True,
            message="alembic current 执行失败：迁移状态未知，禁止启动。",
        )

    head_revisions = _extract_revisions(heads.stdout)
    current_revisions = _extract_revisions(current.stdout)
    if not head_revisions or not head_revisions.issubset(current_revisions):
        missing = ", ".join(sorted(head_revisions - current_revisions)) or "unknown"
        return StepOutcome(
            step="migration",
            passed=False,
            block_startup=True,
            block_prod_release=True,
            message=(
                "数据库迁移未到 head，禁止启动。"
                f" 缺失 revision: {missing}。请先执行 `alembic upgrade head`。"
            ),
        )

    return StepOutcome(
        step="migration",
        passed=True,
        block_startup=False,
        block_prod_release=False,
        message="数据库迁移已在 head。",
    )


def run_health_check(health_url: str, timeout_seconds: float) -> StepOutcome:
    try:
        with urllib.request.urlopen(health_url, timeout=timeout_seconds) as resp:  # noqa: S310
            status = getattr(resp, "status", 200)
    except urllib.error.URLError as exc:
        return StepOutcome(
            step="health",
            passed=False,
            block_startup=True,
            block_prod_release=True,
            message=f"健康检查失败（{health_url}）：{exc}。",
        )

    if status != 200:
        return StepOutcome(
            step="health",
            passed=False,
            block_startup=True,
            block_prod_release=True,
            message=f"健康检查返回非 200（status={status}），禁止放行。",
        )

    return StepOutcome(
        step="health",
        passed=True,
        block_startup=False,
        block_prod_release=False,
        message=f"健康检查通过（{health_url}）。",
    )


def run_stage_acceptance(suite: str) -> StepOutcome:
    cmd = [sys.executable, "tests/run_stage_acceptance.py", "--suite", suite]
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    if completed.returncode != 0:
        return StepOutcome(
            step=f"stage-acceptance:{suite}",
            passed=False,
            block_startup=False,
            block_prod_release=True,
            message=(
                f"{suite} 验收失败，禁止放行 prod。"
                "请回退到 real-provider 联调态排查。"
            ),
        )

    return StepOutcome(
        step=f"stage-acceptance:{suite}",
        passed=True,
        block_startup=False,
        block_prod_release=False,
        message=f"{suite} 验收通过。",
    )


def _latest_stage_acceptance_summary() -> str | None:
    candidates = sorted(Path("output").glob("stage_acceptance_summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    return str(candidates[0])


def _build_evidence_context(args: argparse.Namespace, outcomes: list[StepOutcome], exit_code: int) -> EvidenceContext:
    startup_blocked = any(item.block_startup and not item.passed for item in outcomes)
    prod_release_blocked = any(item.block_prod_release and not item.passed for item in outcomes)
    overall_result = "passed"
    recommended_action = "验收通过，可按主流程继续执行放行与发布。"
    if startup_blocked:
        overall_result = "startup_blocked"
        recommended_action = "存在启动阻断项，请先修复 preflight/migration/health 后重跑 runbook。"
    elif prod_release_blocked:
        overall_result = "prod_release_blocked"
        recommended_action = "可继续联调但禁止 prod 放行，请回到 real-provider 联调态排查并重跑验收。"

    return EvidenceContext(
        generated_at=datetime.now(timezone.utc).isoformat(),
        env=args.env,
        env_file=str(Path(args.env_file)),
        health_url=args.health_url,
        stage_suite=args.stage_suite,
        overall_result=overall_result,
        exit_code=exit_code,
        recommended_action=recommended_action,
        startup_blocked=startup_blocked,
        prod_release_blocked=prod_release_blocked,
    )


def _build_linked_artifacts(args: argparse.Namespace) -> dict[str, str]:
    linked_artifacts: dict[str, str] = {}
    stage_summary = _latest_stage_acceptance_summary() if not args.skip_stage_acceptance else None
    if stage_summary:
        linked_artifacts["stage_acceptance_summary"] = stage_summary

    current_manifest = Path("output") / "current_real_provider_sequence_artifact.json"
    if current_manifest.exists():
        linked_artifacts["current_real_provider_sequence_artifact_manifest"] = str(current_manifest)
    return linked_artifacts


def _build_linked_docs() -> dict[str, str]:
    return {
        "runbook": "md/status/runbook_real_provider_prod.md",
        "handoff": "md/status/current_stage_handoff.md",
    }


def write_evidence_pack(*, args: argparse.Namespace, outcomes: list[StepOutcome], exit_code: int) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = Path("output") / "runbook_evidence" / f"{ts}_{args.env}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    context = _build_evidence_context(args=args, outcomes=outcomes, exit_code=exit_code)
    payload = {
        "generated_at": context.generated_at,
        "env": context.env,
        "env_file": context.env_file,
        "health_url": context.health_url,
        "stage_suite": context.stage_suite,
        "overall_result": context.overall_result,
        "exit_code": context.exit_code,
        "steps": [
            {
                "step": item.step,
                "passed": item.passed,
                "block_startup": item.block_startup,
                "block_prod_release": item.block_prod_release,
                "message": item.message,
            }
            for item in outcomes
        ],
        "recommended_action": context.recommended_action,
        "linked_docs": _build_linked_docs(),
        "linked_artifacts": _build_linked_artifacts(args=args),
    }

    summary_json = evidence_dir / "runbook_summary.json"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    step_lines: list[str] = []
    for item in outcomes:
        icon = "✅" if item.passed else "❌"
        step_lines.append(
            f"- {icon} `{item.step}` | passed={item.passed} | block_startup={item.block_startup} | "
            f"block_prod_release={item.block_prod_release}\n  - {item.message}"
        )

    linked_docs_lines = "\n".join(f"- {key}: `{value}`" for key, value in payload["linked_docs"].items())
    linked_artifact_lines = "\n".join(f"- {key}: `{value}`" for key, value in payload["linked_artifacts"].items()) or "- (none)"
    summary_md = "\n".join(
        [
            "# Runbook Runtime Evidence Summary",
            "",
            "## 结论",
            f"- overall_result: **{context.overall_result}**",
            f"- exit_code: `{context.exit_code}`",
            f"- startup_blocked: `{context.startup_blocked}`",
            f"- prod_release_blocked: `{context.prod_release_blocked}`",
            "",
            "## 运行上下文",
            f"- generated_at: `{context.generated_at}`",
            f"- env: `{context.env}`",
            f"- env_file: `{context.env_file}`",
            f"- health_url: `{context.health_url or '(not set)'}`",
            f"- stage_suite: `{context.stage_suite}`",
            "",
            "## 步骤结果",
            *step_lines,
            "",
            "## 建议动作",
            f"- {context.recommended_action}",
            "",
            "## 关联文档",
            linked_docs_lines,
            "",
            "## 关联工件",
            linked_artifact_lines,
            "",
        ]
    )
    (evidence_dir / "runbook_summary.md").write_text(summary_md, encoding="utf-8")
    return evidence_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="real-provider/prod 运行期最小验收与回滚演练入口")
    parser.add_argument("--env", required=True, choices=["real-provider", "prod"], help="运行模式")
    parser.add_argument("--env-file", default=".env", help="env 文件路径")
    parser.add_argument("--skip-migration-check", action="store_true", help="跳过 migration 检查")
    parser.add_argument("--health-url", default="", help="可选：服务健康检查地址，例如 http://127.0.0.1:8000/health")
    parser.add_argument("--health-timeout-seconds", type=float, default=5.0, help="健康检查超时")
    parser.add_argument(
        "--stage-suite",
        choices=["core", "real-smoke", "real-acceptance"],
        default="real-smoke",
        help="可选验收套件；失败时阻断 prod 放行",
    )
    parser.add_argument("--skip-stage-acceptance", action="store_true", help="跳过阶段验收")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    outcomes: list[StepOutcome] = []

    outcomes.append(run_preflight_step(expected_env=args.env, env_file=Path(args.env_file)))
    if not args.skip_migration_check:
        outcomes.append(run_migration_check())
    if args.health_url:
        outcomes.append(run_health_check(health_url=args.health_url, timeout_seconds=args.health_timeout_seconds))
    if not args.skip_stage_acceptance:
        outcomes.append(run_stage_acceptance(suite=args.stage_suite))

    print("\n[runbook-checks] 结果汇总")
    for item in outcomes:
        icon = "✅" if item.passed else "❌"
        print(f"{icon} {item.step}: {item.message}")

    startup_blocked = any(item.block_startup and not item.passed for item in outcomes)
    prod_release_blocked = any(item.block_prod_release and not item.passed for item in outcomes)
    exit_code = 0
    if startup_blocked:
        print("\n结论：存在启动阻断项（禁止启动）。")
        exit_code = 2
    elif prod_release_blocked:
        print("\n结论：可继续联调，但禁止放行 prod；请回到 real-provider 联调态排查。")
        exit_code = 3
    else:
        print("\n结论：最小运行期验收通过，可按流程放行。")

    evidence_dir = write_evidence_pack(args=args, outcomes=outcomes, exit_code=exit_code)
    print(f"[runbook-checks] 证据包已输出：{evidence_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
