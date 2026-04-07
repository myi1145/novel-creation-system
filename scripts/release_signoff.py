#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.release_registry import update_release_registry


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_evidence_dir(env: str) -> Path:
    candidates = sorted(
        Path("output").glob(f"runbook_evidence/*_{env}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"未找到 env={env} 的 runbook 证据目录，请先执行 scripts/runbook_checks.py。"
        )
    return candidates[0]


def _load_runbook_summary(evidence_dir: Path) -> tuple[dict, Path]:
    summary_path = evidence_dir / "runbook_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"缺少 runbook_summary.json：{summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8")), summary_path


def _validate_decision(*, decision: str, env: str, runbook_summary: dict) -> None:
    overall_result = runbook_summary.get("overall_result", "")
    startup_blocked = overall_result == "startup_blocked"
    prod_release_blocked = overall_result == "prod_release_blocked"

    if startup_blocked and decision != "reject":
        raise ValueError("runbook_summary.overall_result=startup_blocked 时只允许 decision=reject。")
    if decision == "approve":
        if overall_result != "passed":
            raise ValueError("只有 runbook_summary.overall_result=passed 时才允许 decision=approve。")
        if env == "prod" and prod_release_blocked:
            raise ValueError("runbook_summary.overall_result=prod_release_blocked 时不允许 approve prod。")


def _build_required_checks_status(runbook_summary: dict) -> dict:
    steps = runbook_summary.get("steps", [])
    return {
        item.get("step", "unknown"): {
            "passed": bool(item.get("passed", False)),
            "block_startup": bool(item.get("block_startup", False)),
            "block_prod_release": bool(item.get("block_prod_release", False)),
        }
        for item in steps
    }


def create_signoff_record(
    *,
    decision: str,
    env: str,
    operator: str,
    evidence_dir: Path,
    reason: str,
    notes: str,
    decided_at: str | None = None,
) -> Path:
    runbook_summary, runbook_summary_path = _load_runbook_summary(evidence_dir=evidence_dir)
    _validate_decision(decision=decision, env=env, runbook_summary=runbook_summary)

    generated_at = _utc_now_iso()
    decided_at_value = decided_at or generated_at
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    signoff_dir = Path("output") / "release_signoff" / f"{ts}_{env}"
    signoff_dir.mkdir(parents=True, exist_ok=True)

    linked_artifacts = runbook_summary.get("linked_artifacts", {})
    payload = {
        "generated_at": generated_at,
        "decided_at": decided_at_value,
        "env": env,
        "decision": decision,
        "operator": operator,
        "reason": reason,
        "notes": notes,
        "linked_evidence_dir": str(evidence_dir),
        "linked_runbook_summary_json": str(runbook_summary_path),
        "linked_stage_acceptance_summary": linked_artifacts.get("stage_acceptance_summary", ""),
        "required_checks_status": _build_required_checks_status(runbook_summary),
        "recommendation_source": {
            "source_file": str(runbook_summary_path),
            "overall_result": runbook_summary.get("overall_result", ""),
            "recommended_action": runbook_summary.get("recommended_action", ""),
        },
    }

    json_path = signoff_dir / "release_signoff.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_content = "\n".join(
        [
            "# Release Signoff Record",
            "",
            "## 决策摘要",
            f"- decision: **{decision}**",
            f"- env: `{env}`",
            f"- operator: `{operator}`",
            f"- generated_at: `{generated_at}`",
            f"- decided_at: `{decided_at_value}`",
            "",
            "## 决策依据",
            f"- overall_result: `{payload['recommendation_source']['overall_result']}`",
            f"- recommended_action: {payload['recommendation_source']['recommended_action']}",
            f"- linked_evidence_dir: `{payload['linked_evidence_dir']}`",
            f"- linked_runbook_summary_json: `{payload['linked_runbook_summary_json']}`",
            f"- linked_stage_acceptance_summary: `{payload['linked_stage_acceptance_summary'] or '(none)'}`",
            "",
            "## 人工说明",
            f"- reason: {reason}",
            f"- notes: {notes or '(none)'}",
            "",
            "## required_checks_status",
            *[
                f"- {step}: passed={status['passed']}, block_startup={status['block_startup']}, "
                f"block_prod_release={status['block_prod_release']}"
                for step, status in payload["required_checks_status"].items()
            ],
            "",
        ]
    )
    (signoff_dir / "release_signoff.md").write_text(md_content, encoding="utf-8")
    update_release_registry()
    return signoff_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="release signoff 最小记录入口（本地/仓库级）")
    parser.add_argument("--decision", required=True, choices=["approve", "reject", "rollback"], help="人工决策")
    parser.add_argument("--env", required=True, choices=["real-provider", "prod"], help="目标环境")
    parser.add_argument("--operator", required=True, help="执行人")
    parser.add_argument("--reason", required=True, help="决策原因（简述）")
    parser.add_argument("--notes", default="", help="补充说明")
    parser.add_argument("--evidence-dir", default="", help="runbook 证据目录；默认自动选择当前 env 最新目录")
    parser.add_argument("--decided-at", default="", help="人工决策时间（ISO8601）；默认使用当前 UTC 时间")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else _latest_evidence_dir(args.env)
    output_dir = create_signoff_record(
        decision=args.decision,
        env=args.env,
        operator=args.operator,
        evidence_dir=evidence_dir,
        reason=args.reason,
        notes=args.notes,
        decided_at=args.decided_at or None,
    )
    print(f"[release-signoff] 记录已输出：{output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
