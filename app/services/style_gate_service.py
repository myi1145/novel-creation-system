from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.schemas.gate import StyleIssue, StyleReport


_SLANG_TOKENS = ("yyds", "666", "绝绝子", "笑死", "离谱", "我靠", "卧槽", "哈哈哈")
_FORMAL_TOKENS = ("因此", "然而", "由此可见", "综上", "据此")
_LIGHT_TONE_TOKENS = ("段子", "吐槽", "搞笑", "轻松地", "笑着说", "哈哈")
_FANTASY_TERMS = ("灵力", "法阵", "宗门", "道基", "符箓")
_TECH_TERMS = ("芯片", "服务器", "算法", "数据库", "协议栈")


@dataclass
class StyleGateContext:
    chapter_no: int
    target_genre: str
    draft_text: str
    previous_summary: str
    genre_style: dict


class StyleGateService:
    def _split_sentences(self, text: str) -> list[str]:
        return [item.strip() for item in re.split(r"(?<=[。！？!?；;])|\n+", (text or "").strip()) if item.strip()]

    def _highest(self, issues: list[StyleIssue]) -> str:
        order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}
        highest = "S0"
        for issue in issues:
            if order.get(issue.severity, 0) > order.get(highest, 0):
                highest = issue.severity
        return highest

    def evaluate(self, context: StyleGateContext) -> StyleReport:
        text = context.draft_text or ""
        sentences = self._split_sentences(text)
        issues: list[StyleIssue] = []
        tone = str((context.genre_style or {}).get("tone") or "").lower()
        target_genre = context.target_genre or "default"

        for idx, sentence in enumerate(sentences, start=1):
            location = f"句子{idx}"
            lowered = sentence.lower()
            if any(token in lowered for token in _SLANG_TOKENS) and any(flag in tone for flag in ("冷峻", "克制", "严肃", "dark")):
                issues.append(StyleIssue(issue_type="style_drift", severity="S2", location_hint=location, evidence_excerpt=sentence[:90], explanation="既定风格偏克制/冷峻，但文本出现明显网文化或口水化表达。", suggested_action="替换网络热词，改为题材稳定语体。"))
            if (any(token in sentence for token in _FORMAL_TOKENS) and any(token in lowered for token in _SLANG_TOKENS)) or ("emmm" in lowered):
                issues.append(StyleIssue(issue_type="register_shift", severity="S1", location_hint=location, evidence_excerpt=sentence[:90], explanation="同一语句内语体层级突变（正式叙述与口语化混杂）。", suggested_action="统一语体层级，避免同句突然切口。"))
            if any(flag in target_genre.lower() for flag in ("suspense", "mystery", "悬疑")) and any(token in sentence for token in _LIGHT_TONE_TOKENS):
                issues.append(StyleIssue(issue_type="genre_tone_mismatch", severity="S2", location_hint=location, evidence_excerpt=sentence[:90], explanation="当前题材语感应偏紧张克制，但文本出现明显轻喜剧/吐槽腔调。", suggested_action="保留信息点，改为压迫感更强的叙述与对白。"))
            if any(token in sentence for token in _FANTASY_TERMS) and any(token in sentence for token in _TECH_TERMS):
                issues.append(StyleIssue(issue_type="terminology_tone_inconsistency", severity="S2", location_hint=location, evidence_excerpt=sentence[:90], explanation="同句混用不同语汇体系术语，叙述腔调不统一。", suggested_action="统一该段术语体系，必要时拆分并补桥接设定。"))

        highest = self._highest(issues)
        if settings.style_gate_strict and any(item.issue_type in {"genre_tone_mismatch", "terminology_tone_inconsistency"} for item in issues):
            for issue in issues:
                if issue.issue_type in {"genre_tone_mismatch", "terminology_tone_inconsistency"} and issue.severity in {"S1", "S2"}:
                    issue.severity = "S3"
            highest = self._highest(issues)

        summary = (
            f"第{context.chapter_no}章检测到 {len(issues)} 条风格稳定性问题。"
            if issues
            else f"第{context.chapter_no}章风格闸门未发现明显漂移。"
        )
        return StyleReport(
            chapter_no=context.chapter_no,
            target_genre=target_genre,
            issue_count=len(issues),
            highest_severity=highest,
            issues=issues[:8],
            summary=summary,
        )


style_gate_service = StyleGateService()
