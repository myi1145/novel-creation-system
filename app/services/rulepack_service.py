from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import GenreProfileORM, ProjectORM
from app.schemas.rulepack import GateRulePackConstraints, GenreRulePackContext


def _dedupe_texts(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


class RulePackService:
    def _resolve_project_genre_id(self, db: Session | None, *, project_id: str | None) -> str | None:
        if db is None or not project_id:
            return None
        project = db.get(ProjectORM, project_id)
        return None if project is None else project.genre_id

    def resolve_context(self, db: Session | None, *, project_id: str | None = None, genre_id: str | None = None) -> GenreRulePackContext:
        resolved_genre_id = genre_id or self._resolve_project_genre_id(db=db, project_id=project_id)
        profile = db.get(GenreProfileORM, resolved_genre_id) if db is not None and resolved_genre_id else None

        if profile is None:
            rulepack_summary = "未加载题材规则包，当前使用通用创作底座与通用质量闸门。"
            prompt_context = {
                "genre_id": resolved_genre_id,
                "genre_name": resolved_genre_id or "default",
                "genre_tags": [],
                "genre_world": {},
                "genre_narrative": {},
                "genre_style": {},
                "genre_profile": {},
                "genre_rulepack_name": "base_rulepack_v1",
                "genre_rulepack_summary": rulepack_summary,
                "genre_banned_terms": [],
                "genre_taboos": [],
                "genre_preferred_conflict_types": [],
                "genre_hook_style": None,
                "genre_chapter_target_words": None,
            }
            return GenreRulePackContext(
                genre_id=resolved_genre_id,
                genre_name=resolved_genre_id or "default",
                rulepack_name="base_rulepack_v1",
                rulepack_summary=rulepack_summary,
                prompt_context=prompt_context,
                gate_constraints=GateRulePackConstraints(),
            )

        world = dict(profile.world or {})
        narrative = dict(profile.narrative or {})
        style = dict(profile.style or {})
        tags = _dedupe_texts(list(profile.tags or []))
        banned_terms = _dedupe_texts(list(style.get("banned_terms") or []))
        taboos = _dedupe_texts(list(world.get("taboos") or []))
        preferred_conflict_types = _dedupe_texts(list(narrative.get("preferred_conflict_types") or []))
        hook_style = str(narrative.get("hook_style") or "").strip() or None
        chapter_target_words_raw = narrative.get("chapter_target_words")
        try:
            chapter_target_words = int(chapter_target_words_raw) if chapter_target_words_raw not in (None, "") else None
        except (TypeError, ValueError):
            chapter_target_words = None

        summary_parts: list[str] = [f"题材：{profile.genre_name}"]
        if world.get("core_axis"):
            summary_parts.append(f"世界核心：{world.get('core_axis')}")
        if narrative.get("preferred_conflict_types"):
            summary_parts.append(f"偏好冲突：{'、'.join(preferred_conflict_types[:3])}")
        if style.get("tone"):
            summary_parts.append(f"风格语气：{style.get('tone')}")
        if banned_terms:
            summary_parts.append(f"禁用词：{'、'.join(banned_terms[:4])}")
        if taboos:
            summary_parts.append(f"禁忌：{'、'.join(taboos[:4])}")
        rulepack_summary = "；".join(summary_parts)

        prompt_context = {
            "genre_id": profile.genre_id,
            "genre_name": profile.genre_name,
            "base_genre": profile.base_genre,
            "genre_tags": tags,
            "genre_world": world,
            "genre_narrative": narrative,
            "genre_style": style,
            "genre_profile": {
                "genre_id": profile.genre_id,
                "genre_name": profile.genre_name,
                "base_genre": profile.base_genre,
                "tags": tags,
                "world": world,
                "narrative": narrative,
                "style": style,
            },
            "genre_rulepack_name": f"rulepack.{profile.genre_id}",
            "genre_rulepack_summary": rulepack_summary,
            "genre_banned_terms": banned_terms,
            "genre_taboos": taboos,
            "genre_preferred_conflict_types": preferred_conflict_types,
            "genre_hook_style": hook_style,
            "genre_chapter_target_words": chapter_target_words,
        }
        return GenreRulePackContext(
            genre_id=profile.genre_id,
            genre_name=profile.genre_name,
            base_genre=profile.base_genre,
            tags=tags,
            world=world,
            narrative=narrative,
            style=style,
            rulepack_name=f"rulepack.{profile.genre_id}",
            rulepack_summary=rulepack_summary,
            prompt_context=prompt_context,
            gate_constraints=GateRulePackConstraints(
                banned_terms=banned_terms,
                taboos=taboos,
                preferred_conflict_types=preferred_conflict_types,
                hook_style=hook_style,
                chapter_target_words=chapter_target_words,
            ),
        )

    def extend_agent_context(self, db: Session | None, *, project_id: str | None, genre_id: str | None, context: dict[str, Any]) -> dict[str, Any]:
        runtime = self.resolve_context(db=db, project_id=project_id, genre_id=genre_id)
        enriched = dict(context)
        for key, value in runtime.prompt_context.items():
            if value in (None, "", [], {}):
                enriched.setdefault(key, value)
                continue
            enriched[key] = value
        enriched.setdefault("genre_rulepack_summary", runtime.rulepack_summary)
        enriched.setdefault("genre_id", runtime.genre_id)
        enriched.setdefault("genre_name", runtime.genre_name)
        return enriched


rulepack_service = RulePackService()
