#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_iso(value: str) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _build_entry(payload: dict[str, Any], signoff_path: Path) -> dict[str, Any]:
    recommendation_source = payload.get("recommendation_source", {})
    return {
        "env": payload.get("env", ""),
        "decision": payload.get("decision", ""),
        "operator": payload.get("operator", ""),
        "decided_at": payload.get("decided_at", ""),
        "signoff_dir": str(signoff_path.parent),
        "linked_evidence_dir": payload.get("linked_evidence_dir", ""),
        "linked_runbook_summary_json": payload.get("linked_runbook_summary_json", ""),
        "linked_stage_acceptance_summary": payload.get("linked_stage_acceptance_summary", ""),
        "overall_result": recommendation_source.get("overall_result", ""),
        "recommended_action": recommendation_source.get("recommended_action", ""),
    }


def _build_latest_status_summary(entry: dict[str, Any]) -> str:
    decision = entry.get("decision", "unknown")
    overall_result = entry.get("overall_result", "unknown")
    env = entry.get("env", "unknown")
    return (
        f"latest {env} signoff decision={decision}, overall_result={overall_result}; "
        "请先查看 signoff_dir，再追溯 linked_evidence_dir。"
    )


def _build_pointer(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "env": entry.get("env", ""),
        "decision": entry.get("decision", ""),
        "operator": entry.get("operator", ""),
        "decided_at": entry.get("decided_at", ""),
        "signoff_dir": entry.get("signoff_dir", ""),
        "linked_evidence_dir": entry.get("linked_evidence_dir", ""),
        "overall_result": entry.get("overall_result", ""),
        "latest_status_summary": _build_latest_status_summary(entry),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_release_registry(*, output_root: Path = Path("output"), max_entries: int = 30) -> Path:
    signoff_root = output_root / "release_signoff"
    registry_dir = output_root / "release_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    for signoff_json in sorted(signoff_root.glob("*/release_signoff.json")):
        payload = _safe_read_json(signoff_json)
        if not payload:
            continue
        entries.append(_build_entry(payload, signoff_json))

    entries.sort(key=lambda item: _parse_iso(str(item.get("decided_at", ""))), reverse=True)
    trimmed_entries = entries[:max_entries]

    latest_prod = next((item for item in entries if item.get("env") == "prod"), None)
    latest_real_provider = next((item for item in entries if item.get("env") == "real-provider"), None)
    latest_runbook_evidence = next((item for item in entries if item.get("linked_evidence_dir")), None)

    index_payload = {
        "generated_at": _utc_now_iso(),
        "latest_pointers": {
            "latest_prod_signoff": _build_pointer(latest_prod) if latest_prod else None,
            "latest_real_provider_signoff": _build_pointer(latest_real_provider) if latest_real_provider else None,
            "latest_runbook_evidence": {
                "linked_evidence_dir": latest_runbook_evidence.get("linked_evidence_dir", ""),
                "signoff_dir": latest_runbook_evidence.get("signoff_dir", ""),
                "decided_at": latest_runbook_evidence.get("decided_at", ""),
            }
            if latest_runbook_evidence
            else None,
        },
        "entries": trimmed_entries,
    }
    _write_json(registry_dir / "release_index.json", index_payload)

    latest_prod_path = registry_dir / "latest_prod_signoff.json"
    if latest_prod:
        _write_json(latest_prod_path, _build_pointer(latest_prod))
    elif latest_prod_path.exists():
        latest_prod_path.unlink()

    latest_real_provider_path = registry_dir / "latest_real_provider_signoff.json"
    if latest_real_provider:
        _write_json(latest_real_provider_path, _build_pointer(latest_real_provider))
    elif latest_real_provider_path.exists():
        latest_real_provider_path.unlink()

    latest_runbook_path = registry_dir / "latest_runbook_evidence.json"
    if latest_runbook_evidence:
        _write_json(
            latest_runbook_path,
            {
                "linked_evidence_dir": latest_runbook_evidence.get("linked_evidence_dir", ""),
                "signoff_dir": latest_runbook_evidence.get("signoff_dir", ""),
                "decided_at": latest_runbook_evidence.get("decided_at", ""),
                "latest_status_summary": "最新可追溯证据入口，优先查看 linked_evidence_dir 下 runbook_summary。",
            },
        )
    elif latest_runbook_path.exists():
        latest_runbook_path.unlink()

    return registry_dir
