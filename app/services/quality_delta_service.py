from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import zip_longest

from app.core.config import settings
from app.schemas.chapter import PublishQualityDeltaReport


_CRITICAL_SEVERITIES = {"S2", "S3", "S4"}


@dataclass
class QualityDeltaContext:
    draft_text: str
    candidate_published_text: str
    unresolved_critical_issues_count: int


class QualityDeltaService:
    def _normalize_text(self, value: str) -> str:
        text = value or ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_paragraphs(self, value: str) -> list[str]:
        text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []
        parts = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        return parts

    def _split_sentences(self, value: str) -> list[str]:
        text = (value or "").strip()
        if not text:
            return []
        parts = [item.strip() for item in re.split(r"(?<=[。！？!?；;])|\n+", text) if item.strip()]
        return parts

    def _count_changed_units(self, left: list[str], right: list[str]) -> int:
        changed = 0
        for item_left, item_right in zip_longest(left, right, fillvalue=""):
            if self._normalize_text(item_left) != self._normalize_text(item_right):
                changed += 1
        return changed

    def evaluate(self, context: QualityDeltaContext) -> PublishQualityDeltaReport:
        draft_normalized = self._normalize_text(context.draft_text)
        published_normalized = self._normalize_text(context.candidate_published_text)

        if not draft_normalized and not published_normalized:
            similarity_score = 1.0
        else:
            similarity_score = SequenceMatcher(None, draft_normalized, published_normalized).ratio()

        changed_char_ratio = max(0.0, min(1.0, 1.0 - similarity_score))
        changed_paragraph_count = self._count_changed_units(self._split_paragraphs(context.draft_text), self._split_paragraphs(context.candidate_published_text))
        changed_sentence_count = self._count_changed_units(self._split_sentences(context.draft_text), self._split_sentences(context.candidate_published_text))

        has_meaningful_delta = changed_paragraph_count >= settings.publish_delta_min_changed_paragraphs and changed_char_ratio > 0.0

        strict_block = (
            similarity_score >= settings.publish_delta_similarity_threshold
            and not has_meaningful_delta
            and context.unresolved_critical_issues_count > 0
        )

        if strict_block and settings.publish_require_quality_delta:
            decision = "fail"
        elif has_meaningful_delta:
            decision = "pass"
        else:
            decision = "warn"

        if decision == "pass":
            summary = (
                f"检测到可见质量增益：相似度 {similarity_score:.3f}，"
                f"段落变化 {changed_paragraph_count} 处，句子变化 {changed_sentence_count} 处。"
            )
        elif decision == "fail":
            summary = (
                f"发布被阻断：draft 与 published 相似度 {similarity_score:.3f} 过高，"
                f"且关键问题未解决（{context.unresolved_critical_issues_count} 项）。"
            )
        else:
            summary = (
                f"质量增益不足：相似度 {similarity_score:.3f}，"
                f"段落变化 {changed_paragraph_count}，关键未解决问题 {context.unresolved_critical_issues_count}。"
            )

        return PublishQualityDeltaReport(
            similarity_score=round(similarity_score, 6),
            changed_char_ratio=round(changed_char_ratio, 6),
            changed_paragraph_count=changed_paragraph_count,
            changed_sentence_count=changed_sentence_count,
            has_meaningful_delta=has_meaningful_delta,
            unresolved_critical_issues_count=max(0, int(context.unresolved_critical_issues_count)),
            fixed_issue_hints=[],
            decision=decision,
            summary=summary,
        )

    def count_unresolved_critical_issues(self, gate_reviews: list[dict]) -> int:
        unresolved = 0
        for review in gate_reviews:
            pass_status = str(review.get("pass_status") or "")
            for issue in list(review.get("issues") or []):
                severity = str(issue.get("severity") or "").upper()
                if severity in _CRITICAL_SEVERITIES and pass_status != "passed":
                    unresolved += 1
        return unresolved


quality_delta_service = QualityDeltaService()
