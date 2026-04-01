from __future__ import annotations

import re
from dataclasses import dataclass


_EXPLAIN_TOKENS = ("其实", "原来", "也就是说", "真相是", "意味着", "说明", "证明", "就是")
_ACTION_TOKENS = ("走", "看", "追", "推开", "冲", "停", "拿", "听", "问", "跑", "笑", "哭", "沉默", "皱眉")


@dataclass
class OverExplainedRevealIssue:
    issue_type: str
    location_hint: str
    severity: str
    explanation: str
    suggested_rewrite_strategy: str
    excerpt: str


class NarrativeRewriteService:
    def detect_over_explained_reveal(self, content: str) -> list[OverExplainedRevealIssue]:
        text = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        issues: list[OverExplainedRevealIssue] = []
        for idx, paragraph in enumerate(paragraphs, start=1):
            explain_hits = [token for token in _EXPLAIN_TOKENS if token in paragraph]
            if len(explain_hits) < 2:
                continue
            has_action = any(token in paragraph for token in _ACTION_TOKENS)
            if has_action and len(explain_hits) < 3:
                continue
            excerpt = paragraph[:80]
            issues.append(
                OverExplainedRevealIssue(
                    issue_type="over_explained_reveal",
                    location_hint=f"段落{idx}",
                    severity="S1" if len(explain_hits) == 2 else "S2",
                    explanation=f"{idx} 段出现高密度解释词（{','.join(explain_hits[:4])}），信息揭露过直。",
                    suggested_rewrite_strategy="将解释拆到行动与反应中，删减结论句，保留一处悬念留白。",
                    excerpt=excerpt,
                )
            )
        return issues[:3]


narrative_rewrite_service = NarrativeRewriteService()
