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

    def _extract_relation_pairs(self, relationship_edges: list[dict]) -> dict[tuple[str, str], str]:
        pairs: dict[tuple[str, str], str] = {}
        for item in list(relationship_edges or []):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source_character_name") or item.get("source_name") or item.get("source_character_id") or "").strip()
            target = str(item.get("target_character_name") or item.get("target_name") or item.get("target_character_id") or "").strip()
            stage = str(item.get("relation_stage") or "").strip().lower()
            if not source or not target:
                continue
            pairs[(source, target)] = stage
            pairs[(target, source)] = stage
        return pairs

    def _has_transition_bridge(self, line: str, previous_summary: str) -> bool:
        bridge_tokens = ("因为", "所以", "因此", "终于", "随后", "经过", "解释", "转而", "但")
        bridge_text = f"{line} {previous_summary}"
        return any(token in bridge_text for token in bridge_tokens)

    def _apply_strict_semantic_escalation(self, issues: list[CharacterVoiceIssue], *, strict_enabled: bool) -> None:
        if not strict_enabled:
            return
        for issue in issues:
            if issue.issue_type == "voice_drift" and issue.character_name and issue.severity in {"S1", "S2"}:
                if "主角" in issue.explanation or "核心" in issue.explanation:
                    issue.severity = "S3"
            if issue.issue_type == "relationship_stage_mismatch" and issue.severity in {"S1", "S2"}:
                issue.severity = "S3"
            if issue.issue_type == "motivation_gap" and issue.severity in {"S1", "S2"}:
                if "完全相反" in issue.explanation and "无解释" in issue.explanation:
                    issue.severity = "S3"

    def evaluate(self, context: CharacterVoiceContext) -> CharacterVoiceReport:
        draft_text = context.draft_text or ""
        previous_summary = context.previous_summary or ""
        sentences = self._split_sentences(draft_text)
        issues: list[CharacterVoiceIssue] = []
        evaluated_characters: list[str] = []
        relation_pairs = self._extract_relation_pairs(context.relationship_edges)

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
                    explanation = f"{name} 当前设定偏冷静克制，但该句语气突兀偏说教/压迫。"
                    if "lead" in str(card.get("role_tags") or []):
                        explanation = f"主角{name}核心人设（冷静克制）被明显破坏。"
                    issues.append(CharacterVoiceIssue(issue_type="voice_drift", character_name=name, severity="S2", location_hint=location, evidence_excerpt=line[:90], explanation=explanation, suggested_action="保留立场，改为符合角色基调的短句与动作反馈。"))
                if any(token in state_text for token in ("谨慎", "低调", "avoid", "risk")) and any(token in line for token in ("公开身份", "主动暴露", "正面挑衅", "当众承认")):
                    bridge_missing = not self._has_transition_bridge(line, previous_summary)
                    explanation = f"{name} 当前动机倾向规避风险，但该行为直接反向，缺少动机转折。"
                    if bridge_missing:
                        explanation = f"{name} 做出与已知动机完全相反的重大行为且无解释。"
                    issues.append(CharacterVoiceIssue(issue_type="motivation_gap", character_name=name, severity="S2", location_hint=location, evidence_excerpt=line[:90], explanation=explanation, suggested_action="补充触发动机变化的桥接事件或代价说明。"))
                if any(token in previous_summary for token in ("死亡", "牺牲", "重伤", "崩溃", "背叛")) and any(token in line for token in ("哈哈", "轻松地", "像没事一样", "无所谓")):
                    issues.append(CharacterVoiceIssue(issue_type="emotion_mismatch", character_name=name, severity="S1", location_hint=location, evidence_excerpt=line[:90], explanation=f"上章高冲击事件后，{name} 的情绪反应过平或方向失真。", suggested_action="补一层情绪余波（停顿/回避/躯体反应）再进入行动。"))
                if any(token in line for token in ("也就是说", "这说明", "真相是", "设定", "机制")) and len(line) >= 20:
                    issues.append(CharacterVoiceIssue(issue_type="authorial_override", character_name=name, severity="S1", location_hint=location, evidence_excerpt=line[:90], explanation=f"{name} 的表达承担了过多作者解释功能，角色自然性下降。", suggested_action="拆分为场景行动与对话反应，减少直给设定阐述。"))
                for (left, right), stage in relation_pairs.items():
                    if left != name or right not in line:
                        continue
                    if stage in {"hostile", "opposed", "wary", "conflict", "警惕", "对立"} and any(token in line for token in ("我完全信你", "全部交给你", "把底牌都告诉你", "我们永远一体")):
                        if not self._has_transition_bridge(line, previous_summary):
                            issues.append(
                                CharacterVoiceIssue(
                                    issue_type="relationship_stage_mismatch",
                                    character_name=name,
                                    related_character_name=right,
                                    severity="S2",
                                    location_hint=location,
                                    evidence_excerpt=line[:90],
                                    explanation=f"{name}-{right} 当前关系阶段仍偏{stage}，但正文出现无依据的高度信任跳变。",
                                    suggested_action="补充关系阶段变化触发事件，或将交底拆为试探式互动。",
                                )
                            )
                    if stage in {"trust", "allied", "intimate", "合作", "信任", "亲密"} and any(token in line for token in ("立刻背刺", "我一直在利用你", "现在就杀了你", "你从来不是同伴")):
                        if not self._has_transition_bridge(line, previous_summary):
                            issues.append(
                                CharacterVoiceIssue(
                                    issue_type="relationship_stage_mismatch",
                                    character_name=name,
                                    related_character_name=right,
                                    severity="S2",
                                    location_hint=location,
                                    evidence_excerpt=line[:90],
                                    explanation=f"{name}-{right} 原关系阶段为{stage}，但正文突然极端敌对，缺少关系破裂桥接。",
                                    suggested_action="先补关系破裂触发点，再升级冲突烈度。",
                                )
                            )

        self._apply_strict_semantic_escalation(issues, strict_enabled=settings.character_voice_gate_strict)
        highest = self._highest(issues)
        if settings.character_voice_gate_strict and highest != "S3" and len(issues) >= 4:
            highest = "S3"

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
