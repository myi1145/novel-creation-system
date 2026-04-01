from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.schemas.gate import CharacterVoiceIssue, CharacterVoiceReport


@dataclass
class CharacterVoiceContext:
    chapter_no: int
    draft_text: str
    previous_summary: str
    character_cards: list[dict]
    relationship_edges: list[dict]


class CharacterVoiceService:
    def _split_sentences(self, text: str) -> list[str]:
        return [item.strip() for item in re.split(r"(?<=[。！？!?；;])|\n+", (text or "").strip()) if item.strip()]

    def _highest(self, issues: list[CharacterVoiceIssue]) -> str:
        order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}
        highest = "S0"
        for item in issues:
            if order.get(item.severity, 0) > order.get(highest, 0):
                highest = item.severity
        return highest

    def evaluate(self, context: CharacterVoiceContext) -> CharacterVoiceReport:
        draft_text = context.draft_text or ""
        previous_summary = context.previous_summary or ""
        sentences = self._split_sentences(draft_text)
        issues: list[CharacterVoiceIssue] = []
        evaluated_characters: list[str] = []

        for card in list(context.character_cards or [])[:6]:
            name = str(card.get("character_name") or "").strip()
            if not name:
                continue
            evaluated_characters.append(name)
            state_text = f"{card.get('role_tags') or []} {card.get('current_state') or {}}".lower()
            name_sentences = [line for line in sentences if name in line]
            for idx, line in enumerate(name_sentences, start=1):
                location = f"{name}:句子{idx}"
                if ("冷静" in state_text or "克制" in state_text or "calm" in state_text) and any(token in line for token in ("必须听我", "闭嘴", "给我记住", "教你们")):
                    issues.append(CharacterVoiceIssue(issue_type="voice_drift", character_name=name, severity="S2", location_hint=location, evidence_excerpt=line[:90], explanation=f"{name} 当前设定偏冷静克制，但该句语气突兀偏说教/压迫。", suggested_action="保留立场，改为符合角色基调的短句与动作反馈。"))
                if any(token in state_text for token in ("谨慎", "低调", "avoid", "risk")) and any(token in line for token in ("公开身份", "主动暴露", "正面挑衅", "当众承认")):
                    issues.append(CharacterVoiceIssue(issue_type="motivation_gap", character_name=name, severity="S2", location_hint=location, evidence_excerpt=line[:90], explanation=f"{name} 当前动机倾向规避风险，但该行为直接反向，缺少动机转折。", suggested_action="补充触发动机变化的桥接事件或代价说明。"))
                if any(token in previous_summary for token in ("死亡", "牺牲", "重伤", "崩溃", "背叛")) and any(token in line for token in ("哈哈", "轻松地", "像没事一样", "无所谓")):
                    issues.append(CharacterVoiceIssue(issue_type="emotion_mismatch", character_name=name, severity="S1", location_hint=location, evidence_excerpt=line[:90], explanation=f"上章高冲击事件后，{name} 的情绪反应过平或方向失真。", suggested_action="补一层情绪余波（停顿/回避/躯体反应）再进入行动。"))
                if any(token in line for token in ("也就是说", "这说明", "真相是", "设定", "机制")) and len(line) >= 20:
                    issues.append(CharacterVoiceIssue(issue_type="authorial_override", character_name=name, severity="S1", location_hint=location, evidence_excerpt=line[:90], explanation=f"{name} 的表达承担了过多作者解释功能，角色自然性下降。", suggested_action="拆分为场景行动与对话反应，减少直给设定阐述。"))

        highest = self._highest(issues)
        if settings.character_voice_gate_strict and len(issues) >= 2 and highest in {"S1", "S2"}:
            highest = "S3"
            for issue in issues:
                if issue.severity in {"S1", "S2"}:
                    issue.severity = "S3"

        summary = (
            f"第{context.chapter_no}章评估角色 {len(evaluated_characters)} 个，发现 {len(issues)} 条人物声音风险。"
            if issues
            else f"第{context.chapter_no}章人物声音检查未发现明显失真。"
        )
        return CharacterVoiceReport(
            chapter_no=context.chapter_no,
            evaluated_characters=evaluated_characters,
            issue_count=len(issues),
            highest_severity=highest,
            issues=issues[:8],
            summary=summary,
        )


character_voice_service = CharacterVoiceService()
