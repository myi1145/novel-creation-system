from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.schemas.chapter import SeedConsumptionReport


_ACTION_SIGNALS = (
    "决定",
    "决意",
    "行动",
    "追查",
    "调查",
    "对峙",
    "冲突",
    "揭开",
    "发现",
    "逼问",
    "潜入",
    "阻止",
    "营救",
    "计划",
    "execute",
    "decide",
    "plan",
    "confront",
    "investigate",
)


@dataclass
class SeedConsumptionContext:
    chapter_no: int
    previous_next_chapter_seed: str | None
    previous_summary: str | None
    current_chapter_text: str
    current_summary: str | None = None


class SeedConsumptionService:
    def _normalize(self, value: str | None) -> str:
        text = (value or "").strip()
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\s+", " ", text)
        return text

    def _split_fragments(self, seed_text: str) -> list[str]:
        parts = [item.strip(" ，。；;、,.!?！？:：") for item in re.split(r"[，。；;、\n]+", seed_text) if item.strip()]
        fragments: list[str] = []
        for item in parts:
            candidates = [item]
            candidates.extend(re.split(r"[并且并在将和与及是否然后、的了]", item))
            for candidate in candidates:
                token = candidate.strip(" ，。；;、,.!?！？:：")
                if len(token) < 2:
                    continue
                if token not in fragments:
                    fragments.append(token)
        return fragments[:8]

    def _split_sentences(self, value: str) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in re.split(r"(?<=[。！？!?；;])|\n+", value) if item.strip()]

    def evaluate(self, context: SeedConsumptionContext) -> SeedConsumptionReport:
        seed_text = self._normalize(context.previous_next_chapter_seed)
        previous_summary = self._normalize(context.previous_summary)
        current_text = self._normalize(context.current_chapter_text)
        current_summary = self._normalize(context.current_summary)
        combined_text = f"{current_text}\n{current_summary}".strip()

        if not seed_text:
            return SeedConsumptionReport(
                chapter_no=context.chapter_no,
                has_previous_seed=False,
                previous_seed_excerpt=previous_summary[:120],
                matched_seed_fragments_count=0,
                matched_seed_fragments=[],
                consumed_signals_count=0,
                unresolved_seed_points_count=0,
                decision="consumed",
                summary="无可用上一章 next_chapter_seed，跳过 seed 消费判定。",
            )

        fragments = self._split_fragments(seed_text)
        matched = [item for item in fragments if item and item in combined_text]
        matched_count = len(matched)

        consumed_signals_count = 0
        for sentence in self._split_sentences(combined_text):
            if not sentence:
                continue
            if not any(fragment in sentence for fragment in matched):
                continue
            lowered = sentence.lower()
            has_signal = any(signal in sentence or signal in lowered for signal in _ACTION_SIGNALS)
            negated = any(flag in sentence for flag in ("没有", "未", "并未", "无意", "拒绝"))
            if has_signal and not negated:
                consumed_signals_count += 1

        unresolved = max(len(fragments) - matched_count, 0)
        min_matched = max(1, settings.seed_consumption_min_matched_fragments)
        if matched_count >= min_matched and consumed_signals_count > 0:
            decision = "consumed"
            summary = f"第{context.chapter_no}章明显承接上一章种子，命中 {matched_count} 个片段，并出现 {consumed_signals_count} 个推进信号。"
        elif matched_count > 0:
            decision = "weak"
            summary = f"第{context.chapter_no}章提及了上一章种子（命中 {matched_count} 个片段），但推进信号偏弱。"
        else:
            decision = "missing"
            summary = f"第{context.chapter_no}章几乎未承接上一章 next_chapter_seed（0 命中）。"

        return SeedConsumptionReport(
            chapter_no=context.chapter_no,
            has_previous_seed=True,
            previous_seed_excerpt=seed_text[:200],
            matched_seed_fragments_count=matched_count,
            matched_seed_fragments=matched,
            consumed_signals_count=consumed_signals_count,
            unresolved_seed_points_count=unresolved,
            decision=decision,
            summary=summary,
        )


seed_consumption_service = SeedConsumptionService()
