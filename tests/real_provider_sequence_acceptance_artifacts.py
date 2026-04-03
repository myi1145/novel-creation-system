"""真实 provider 连续章节验收工件导出工具。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_SEQUENCE_ARTIFACT_MANIFEST = "current_real_provider_sequence_artifact.json"


def _extract_chapter_text(chapter_item: dict[str, Any]) -> str:
    payload = chapter_item.get("chapter_result") if isinstance(chapter_item.get("chapter_result"), dict) else {}
    draft = payload.get("draft") if isinstance(payload, dict) else None
    if isinstance(draft, dict):
        for key in ("content", "chapter_content", "body", "text", "draft_content", "manuscript", "rendered_content"):
            value = draft.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _extract_continuity_fields(continuity_pack: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(continuity_pack, dict):
        return {}
    return {
        "source_published_chapter_id": continuity_pack.get("source_published_chapter_id"),
        "latest_summary": continuity_pack.get("latest_summary"),
        "latest_next_chapter_seed": continuity_pack.get("latest_next_chapter_seed"),
        "continuity_notes": continuity_pack.get("continuity_notes"),
        "state_hints": continuity_pack.get("state_hints"),
    }


def export_real_provider_sequence_artifacts(
    *,
    output_root: Path,
    acceptance_name: str,
    provider_name: str,
    model_name: str | None,
    project_id: str,
    workflow_run_id: str | None,
    chapter_count: int,
    sequence_response_data: dict[str, Any],
) -> dict[str, Any]:
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_key = workflow_run_id or run_tag
    artifact_dir = output_root / acceptance_name / f"{run_tag}_{run_key[:8]}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    chapter_results = list(sequence_response_data.get("chapter_results") or [])
    completed = 0
    failed = 0
    attention = 0
    exported_chapter_files: list[str] = []
    chapter_artifact_status: list[dict[str, Any]] = []

    for item in chapter_results:
        chapter_no = int(item.get("chapter_no") or 0)
        if chapter_no <= 0:
            continue
        stage_status = str(item.get("stage_status") or "unknown")
        if stage_status == "completed":
            completed += 1
        elif stage_status == "failed":
            failed += 1
        elif stage_status == "attention_required":
            attention += 1

        chapter_key = f"chapter_{chapter_no:02d}"
        summary_payload = {
            "chapter_no": chapter_no,
            "stage_status": stage_status,
            "next_action": item.get("next_action"),
            "published_chapter_id": item.get("published_chapter_id"),
            "latest_summary": item.get("latest_summary"),
            "latest_next_chapter_seed": item.get("latest_next_chapter_seed"),
            "derived_update_status": item.get("derived_update_status"),
            "continuity_pack": _extract_continuity_fields((item.get("chapter_result") or {}).get("continuity_pack") or {}),
            "workflow_run_id": item.get("workflow_run_id"),
            "error_message": item.get("error_message"),
        }
        summary_path = artifact_dir / f"{chapter_key}_summary.json"
        summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        exported_chapter_files.append(summary_path.as_posix())

        chapter_text = _extract_chapter_text(item)
        chapter_text_path = artifact_dir / f"{chapter_key}.txt"
        chapter_text_exists = bool(chapter_text.strip())
        if chapter_text_exists:
            chapter_text_path.write_text(chapter_text, encoding="utf-8")
            exported_chapter_files.append(chapter_text_path.as_posix())

        chapter_artifact_status.append(
            {
                "chapter_no": chapter_no,
                "stage_status": stage_status,
                "chapter_text_exported": chapter_text_exists,
                "summary_exported": True,
            }
        )

    batch_report_path = artifact_dir / "sequence_batch_report.json"
    batch_report_payload = sequence_response_data.get("sequence_batch_report")
    batch_report_path.write_text(json.dumps(batch_report_payload or {}, ensure_ascii=False, indent=2), encoding="utf-8")

    acceptance_summary = {
        "acceptance_name": acceptance_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider_name,
        "model": model_name,
        "project_id": project_id,
        "workflow_run_id": workflow_run_id,
        "chapter_count": chapter_count,
        "batch_status": sequence_response_data.get("batch_status"),
        "next_action": sequence_response_data.get("next_action"),
        "stopped_at_chapter_no": sequence_response_data.get("stopped_at_chapter_no"),
        "completed_chapter_count": completed,
        "failed_chapter_count": failed,
        "attention_chapter_count": attention,
        "chapter_artifact_status": chapter_artifact_status,
        "exported_files": exported_chapter_files + [batch_report_path.as_posix()],
        "failure_location": {
            "chapter_no": sequence_response_data.get("stopped_at_chapter_no"),
            "next_action": sequence_response_data.get("next_action"),
        },
    }
    acceptance_summary_path = artifact_dir / "acceptance_summary.json"
    acceptance_summary_path.write_text(json.dumps(acceptance_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    binding_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "acceptance_summary_path": acceptance_summary_path.as_posix(),
        "sequence_batch_report_path": batch_report_path.as_posix(),
        "workflow_run_id": workflow_run_id,
    }
    binding_manifest_path = output_root / CURRENT_SEQUENCE_ARTIFACT_MANIFEST
    binding_manifest_path.write_text(json.dumps(binding_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "artifact_dir": artifact_dir.as_posix(),
        "acceptance_summary_path": acceptance_summary_path.as_posix(),
        "sequence_batch_report_path": batch_report_path.as_posix(),
        "binding_manifest_path": binding_manifest_path.as_posix(),
        "chapter_artifact_status": chapter_artifact_status,
    }
