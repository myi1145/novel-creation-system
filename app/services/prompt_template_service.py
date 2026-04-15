from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import ProjectORM, PromptTemplateORM
from app.schemas.prompt import CreatePromptTemplateRequest, PromptResolutionPreview, PromptTemplate


DEFAULT_PROMPT_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_key": "story_planner.generate_story_planning",
        "agent_type": "story_planner",
        "action_name": "generate_story_planning",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": (
            "你是小说全书规划 Agent。请基于项目基础信息输出“整书架构规划对象”，而不是粗大纲。"
            "必须严格返回 JSON 对象，不要输出 Markdown，不要输出正文。"
        ),
        "user_template": (
            "请生成全书规划草稿，覆盖 worldview/main_outline/volume_plan/core_seed_summary 四个字段。\n"
            "project_name: {project_name}\n"
            "premise: {premise}\n"
            "genre_id: {genre_id}\n"
            "genre_name: {genre_name}\n"
            "genre_rule_summary: {genre_rule_summary}\n"
            "target_chapter_count: {target_chapter_count}\n"
            "tone: {tone}\n"
            "要求：\n"
            "1) worldview 必须用分段标签输出，且至少包含：[世界背景] [力量体系] [社会秩序] [势力格局] [资源与代价] [隐藏真相方向] [规则边界]；\n"
            "2) main_outline 必须同时覆盖核心种子 + 角色动力学 + 主线架构，且至少包含：[阅读承诺] [主角长期成长主线] [核心冲突] [关键角色关系张力] [关键配角功能] [主要对抗力量] [感情线/情绪主线] [长期钩子] [主线架构] [关键转折点] [长程悬念问题]；\n"
            "3) volume_plan 必须按分卷职责输出，且至少包含：[分卷规划原则] [卷一职责] [卷二职责] [卷三职责] [卷末承接]；每卷需写清职责、目标、冲突、关键推进、卷末转折；\n"
            "4) core_seed_summary 必须聚焦核心种子与开局状态快照，且至少包含：[核心种子] [初始状态快照] [主角初始状态] [关键关系初始状态] [已知开放问题] [埋下的谜团/伏笔] [开局局势张力] [前期不可随意改写的状态边界]；\n"
            "5) 输出应可直接作为 StoryDirectory 上游输入，禁止空泛套话，禁止章节正文。"
        ),
        "output_contract": {
            "type": "json_object",
            "fields": ["worldview", "main_outline", "volume_plan", "core_seed_summary"],
        },
        "template_metadata": {"description": "全书规划生成默认模板"},
    },
    {
        "template_key": "story_planner.generate_story_directory",
        "agent_type": "story_planner",
        "action_name": "generate_story_directory",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": (
            "你是小说章节目录规划 Agent。请基于已保存的全书规划生成章节目录草稿。"
            "必须严格返回 JSON 对象，不要输出 Markdown，不要输出正文。"
        ),
        "user_template": (
            "请基于以下信息生成 StoryDirectory 草稿。\n"
            "project_name: {project_name}\n"
            "premise: {premise}\n"
            "genre_id: {genre_id}\n"
            "worldview: {worldview}\n"
            "main_outline: {main_outline}\n"
            "volume_plan: {volume_plan}\n"
            "core_seed_summary: {core_seed_summary}\n"
            "target_chapter_count: {target_chapter_count}\n"
            "输出要求：\n"
            "1) 目录必须基于世界观、主线、分卷/阶段规划，不得脱离全书规划；\n"
            "2) 每章必须给出 chapter_role 与 chapter_goal；\n"
            "3) 每章必须给出 required_entities、required_seed_points、foreshadow_constraints；\n"
            "4) 输出仅包含 directory_title、directory_summary、chapter_items，不要输出正文；\n"
            "5) chapter_items 至少 1 章，chapter_no 从 1 开始递增。"
        ),
        "output_contract": {
            "type": "json_object",
            "fields": ["directory_title", "directory_summary", "chapter_items"],
        },
        "template_metadata": {"description": "章节目录生成默认模板"},
    },
    {
        "template_key": "planner.generate_blueprints",
        "agent_type": "planner",
        "action_name": "generate_blueprints",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是长篇小说章节规划 Agent。你的任务是根据当前章目标生成多个候选章蓝图。严格返回 JSON。",
        "user_template": (
            "请根据以下信息生成 {candidate_count} 个候选章蓝图。\n"
            "项目题材：{genre_name}\n"
            "章目标：{goal_json}\n"
            "未解决伏笔：{open_loops_json}\n"
            "上章摘要：{previous_chapter_summary}\n"
            "连续性约束：{continuity_summary}\n"
            "下一章种子：{next_chapter_seed}\n"
            "输出要求：返回 JSON 数组，每项包含 title_hint, summary, advances, risks, selected。"
        ),
        "output_contract": {
            "type": "json_array",
            "fields": ["title_hint", "summary", "advances", "risks", "selected"],
        },
        "template_metadata": {"description": "章节蓝图生成默认模板"},
    },
    {
        "template_key": "scene_decomposer.decompose_scenes",
        "agent_type": "scene_decomposer",
        "action_name": "decompose_scenes",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是小说场景拆解 Agent。你的任务是把章蓝图拆成可执行场景卡。严格返回 JSON。",
        "user_template": (
            "请基于以下章蓝图拆解场景。\n"
            "章蓝图：{blueprint_json}\n"
            "输出要求：返回 JSON 数组，每项包含 scene_goal, participating_entities, conflict_type, emotional_curve, information_delta。"
        ),
        "output_contract": {
            "type": "json_array",
            "fields": ["scene_goal", "participating_entities", "conflict_type", "emotional_curve", "information_delta"],
        },
        "template_metadata": {"description": "场景拆解默认模板"},
    },
    {
        "template_key": "writer.generate_draft",
        "agent_type": "writer",
        "action_name": "generate_draft",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是长篇小说正文写作 Agent。请根据蓝图、场景和 Canon 摘要写出章节正文草稿。",
        "user_template": (
            "请直接输出正文，不要解释。\n"
            "章蓝图：{blueprint_json}\n"
            "场景列表：{scenes_json}\n"
            "伏笔：{open_loops_json}\n"
            "上章摘要：{previous_chapter_summary}\n"
            "连续性约束：{continuity_summary}\n"
            "下一章种子：{next_chapter_seed}\n"
            "Canon 摘要：{canon_summary_json}"
        ),
        "output_contract": {
            "type": "text",
            "fields": ["content"],
        },
        "template_metadata": {"description": "正文写作默认模板"},
    },
    {
        "template_key": "writer.revise_draft",
        "agent_type": "writer",
        "action_name": "revise_draft",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是长篇小说修订 Agent。请根据失败闸门、修订指令和原始正文，输出一版修订后的正文草稿。",
        "user_template": (
            "请直接输出修订后的正文，不要解释。\n"
            "章蓝图：{blueprint_json}\n"
            "场景列表：{scenes_json}\n"
            "原始正文：{content}\n"
            "失败闸门问题：{gate_issues_json}\n"
            "修订指令：{revision_instruction}\n"
            "连续性约束：{continuity_summary}\n"
            "Canon 摘要：{canon_summary_json}"
        ),
        "output_contract": {
            "type": "text",
            "fields": ["content"],
        },
        "template_metadata": {"description": "正文修订默认模板"},
    },
    {
        "template_key": "changeset_proposer.propose_changeset",
        "agent_type": "changeset_proposer",
        "action_name": "propose_changeset",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": (
            "你是小说 Change Proposal Agent。请从已通过闸门的章节草稿中提取可验证的状态变化，输出结构化变更提议。严格返回 JSON。"
            "注意：patch_operations 必须严格遵循系统可执行白名单，禁止输出 add_character、add_rule、create_character 等非白名单 op。"
        ),
        "user_template": (
            "项目题材：{genre_name}\n"
            "章蓝图：{blueprint_json}\n"
            "最终草稿：{content}\n"
            "Canon 摘要：{canon_summary_json}\n"
            "patch_operations 约束：\n"
            "- kind=snapshot 时，op 只允许 append/extend/replace，field 只允许 timeline_events。\n"
            "- kind=object 时，op 只允许 create_object/create_version/restore_version/retire_version，且 object_type 必须在 character_card/rule_card/open_loop_card/relationship_edge 内。\n"
            "- 出现不支持的 op（例如 add_character）会被系统直接拒绝。\n"
            "输出字段：proposal_summary, rationale, extracted_changes, uncertain_items, evidence_refs, review_recommendation, patch_operations。"
        ),
        "output_contract": {
            "type": "json_object",
            "fields": ["proposal_summary", "rationale", "extracted_changes", "uncertain_items", "evidence_refs", "review_recommendation", "patch_operations"],
        },
        "template_metadata": {"description": "ChangeSet 提议默认模板"},
    },
    {
        "template_key": "summarizer.summarize_chapter",
        "agent_type": "summarizer",
        "action_name": "summarize_chapter",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是小说章节摘要 Agent。请根据已发布章节、蓝图与 Canon 摘要输出结构化章节摘要。严格返回 JSON。",
        "user_template": (
            "项目题材：{genre_name}\n"
            "章标题：{chapter_title}\n"
            "章号：{chapter_no}\n"
            "章蓝图：{blueprint_json}\n"
            "正文内容：{content}\n"
            "Canon 摘要：{canon_summary_json}\n"
            "输出字段：summary, state_summary, key_plot_points, canon_updates, unresolved_open_loops, carry_over_constraints, next_chapter_seed。"
        ),
        "output_contract": {
            "type": "json_object",
            "fields": ["summary", "state_summary", "key_plot_points", "canon_updates", "unresolved_open_loops", "carry_over_constraints", "next_chapter_seed"],
        },
        "template_metadata": {"description": "章节摘要默认模板"},
    },
    {
        "template_key": "gate_reviewer.review_gate",
        "agent_type": "gate_reviewer",
        "action_name": "review_gate",
        "provider_scope": "all",
        "scope_type": "global",
        "scope_key": "__global__",
        "system_template": "你是小说质量闸门 Reviewer。请依据 Gate 名称和正文内容输出结构化评审结论。严格返回 JSON。",
        "user_template": (
            "当前 Gate：{gate_name}\n"
            "蓝图摘要：{blueprint_summary}\n"
            "Canon 摘要：{canon_summary_json}\n"
            "正文内容：{content}\n"
            "输出字段：pass_status, highest_severity, recommended_route, can_override, override_role, issues。"
        ),
        "output_contract": {
            "type": "json_object",
            "fields": ["pass_status", "highest_severity", "recommended_route", "can_override", "override_role", "issues"],
        },
        "template_metadata": {"description": "质量闸门默认模板"},
    },
]


class SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass
class PromptTemplateResolution:
    template: PromptTemplateORM
    system_prompt: str
    user_prompt: str

    @property
    def template_id(self) -> str:
        return self.template.id

    @property
    def template_key(self) -> str:
        return self.template.template_key

    @property
    def template_version(self) -> int:
        return self.template.template_version

    @property
    def scope_type(self) -> str:
        return self.template.scope_type

    @property
    def scope_key(self) -> str:
        return self.template.scope_key

    @property
    def provider_scope(self) -> str:
        return self.template.provider_scope

    @property
    def output_contract(self) -> dict[str, Any]:
        return dict(self.template.output_contract or {})


class PromptTemplateService:
    def ensure_default_templates(self, db: Session) -> None:
        changed = False
        for item in DEFAULT_PROMPT_TEMPLATES:
            existing = (
                db.query(PromptTemplateORM)
                .filter(
                    PromptTemplateORM.template_key == item["template_key"],
                    PromptTemplateORM.template_version == 1,
                    PromptTemplateORM.scope_type == item.get("scope_type", "global"),
                    PromptTemplateORM.scope_key == item.get("scope_key", "__global__"),
                    PromptTemplateORM.provider_scope == item.get("provider_scope", "all"),
                )
                .first()
            )
            if existing is not None:
                continue
            entity = PromptTemplateORM(
                template_key=item["template_key"],
                template_version=1,
                agent_type=item["agent_type"],
                action_name=item["action_name"],
                provider_scope=item.get("provider_scope", "all"),
                scope_type=item.get("scope_type", "global"),
                scope_key=item.get("scope_key", "__global__"),
                status="active",
                is_active=True,
                system_template=item["system_template"],
                user_template=item["user_template"],
                output_contract=item.get("output_contract") or {},
                template_metadata=item.get("template_metadata") or {},
            )
            db.add(entity)
            changed = True
        if changed:
            db.commit()

    def list_templates(
        self,
        db: Session,
        template_key: str | None = None,
        agent_type: str | None = None,
        action_name: str | None = None,
        scope_type: str | None = None,
        scope_key: str | None = None,
        status: str | None = None,
    ) -> list[PromptTemplate]:
        self.ensure_default_templates(db)
        query = db.query(PromptTemplateORM)
        if template_key:
            query = query.filter(PromptTemplateORM.template_key == template_key)
        if agent_type:
            query = query.filter(PromptTemplateORM.agent_type == agent_type)
        if action_name:
            query = query.filter(PromptTemplateORM.action_name == action_name)
        if scope_type:
            query = query.filter(PromptTemplateORM.scope_type == scope_type)
        if scope_key:
            query = query.filter(PromptTemplateORM.scope_key == scope_key)
        if status:
            query = query.filter(PromptTemplateORM.status == status)
        items = query.order_by(PromptTemplateORM.template_key.asc(), PromptTemplateORM.template_version.desc()).all()
        return [PromptTemplate.model_validate(item) for item in items]

    def create_template(self, db: Session, request: CreatePromptTemplateRequest) -> PromptTemplate:
        self.ensure_default_templates(db)
        if request.scope_type == "global":
            scope_key = "__global__"
        else:
            scope_key = request.scope_key.strip()
            if not scope_key:
                raise ValidationError("非 global 模板必须提供 scope_key")
        last_version = (
            db.query(PromptTemplateORM)
            .filter(
                PromptTemplateORM.template_key == request.template_key,
                PromptTemplateORM.provider_scope == request.provider_scope,
                PromptTemplateORM.scope_type == request.scope_type,
                PromptTemplateORM.scope_key == scope_key,
            )
            .order_by(PromptTemplateORM.template_version.desc())
            .first()
        )
        next_version = 1 if last_version is None else last_version.template_version + 1
        entity = PromptTemplateORM(
            template_key=request.template_key,
            template_version=next_version,
            agent_type=request.agent_type,
            action_name=request.action_name,
            provider_scope=request.provider_scope,
            scope_type=request.scope_type,
            scope_key=scope_key,
            status="active" if request.activate_now else "draft",
            is_active=bool(request.activate_now),
            system_template=request.system_template,
            user_template=request.user_template,
            output_contract=request.output_contract,
            template_metadata=request.template_metadata,
        )
        db.add(entity)
        db.flush()
        if request.activate_now:
            self._deactivate_siblings(db, entity)
        db.commit()
        db.refresh(entity)
        return PromptTemplate.model_validate(entity)

    def activate_template(self, db: Session, template_id: str) -> PromptTemplate:
        self.ensure_default_templates(db)
        entity = db.get(PromptTemplateORM, template_id)
        if entity is None:
            raise NotFoundError("Prompt 模板不存在")
        entity.status = "active"
        entity.is_active = True
        self._deactivate_siblings(db, entity)
        db.commit()
        db.refresh(entity)
        return PromptTemplate.model_validate(entity)

    def resolve_template(
        self,
        db: Session | None,
        *,
        project_id: str | None,
        genre_id: str | None,
        agent_type: str,
        action_name: str,
        provider_scope: str,
        render_context: dict[str, Any],
    ) -> PromptTemplateResolution:
        if db is None:
            template = self._build_fallback_default(agent_type=agent_type, action_name=action_name)
            system_prompt = self._render(template.system_template, render_context)
            user_prompt = self._render(template.user_template, render_context)
            system_prompt, user_prompt = self._apply_genre_rulepack_overlay(
                action_name=action_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                render_context=render_context,
            )
            return PromptTemplateResolution(
                template=template,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        self.ensure_default_templates(db)
        resolved_genre_id = genre_id or self._resolve_project_genre_id(db=db, project_id=project_id)
        candidates = self._load_candidates(db=db, agent_type=agent_type, action_name=action_name, provider_scope=provider_scope, genre_id=resolved_genre_id)
        if not candidates:
            template = self._build_fallback_default(agent_type=agent_type, action_name=action_name)
        else:
            template = candidates[0]
        system_prompt = self._render(template.system_template, render_context)
        user_prompt = self._render(template.user_template, render_context)
        system_prompt, user_prompt = self._apply_genre_rulepack_overlay(
            action_name=action_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            render_context=render_context,
        )
        return PromptTemplateResolution(
            template=template,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def get_resolution_preview(
        self,
        db: Session,
        *,
        project_id: str | None,
        genre_id: str | None,
        agent_type: str,
        action_name: str,
        provider_scope: str | None,
        render_context: dict[str, Any],
    ) -> PromptResolutionPreview:
        resolution = self.resolve_template(
            db=db,
            project_id=project_id,
            genre_id=genre_id,
            agent_type=agent_type,
            action_name=action_name,
            provider_scope=provider_scope or "all",
            render_context=render_context,
        )
        return PromptResolutionPreview(
            template_id=resolution.template.id,
            template_key=resolution.template.template_key,
            template_version=resolution.template.template_version,
            scope_type=resolution.template.scope_type,
            scope_key=resolution.template.scope_key,
            provider_scope=resolution.template.provider_scope,
            system_prompt=resolution.system_prompt,
            user_prompt=resolution.user_prompt,
            output_contract=resolution.output_contract,
        )

    def _resolve_project_genre_id(self, db: Session, project_id: str | None) -> str | None:
        if not project_id:
            return None
        project = db.get(ProjectORM, project_id)
        return None if project is None else project.genre_id

    def _load_candidates(self, db: Session, *, agent_type: str, action_name: str, provider_scope: str, genre_id: str | None) -> list[PromptTemplateORM]:
        query = db.query(PromptTemplateORM).filter(
            PromptTemplateORM.agent_type == agent_type,
            PromptTemplateORM.action_name == action_name,
            PromptTemplateORM.status == "active",
            PromptTemplateORM.is_active.is_(True),
        )
        provider_candidates = [provider_scope, "all"] if provider_scope != "all" else ["all"]
        scope_pairs: list[tuple[str, str]] = []
        if genre_id:
            scope_pairs.extend([("genre", genre_id)])
        scope_pairs.append(("global", "__global__"))

        items = query.order_by(PromptTemplateORM.template_version.desc()).all()
        scored: list[tuple[int, PromptTemplateORM]] = []
        for item in items:
            provider_rank = provider_candidates.index(item.provider_scope) if item.provider_scope in provider_candidates else None
            if provider_rank is None:
                continue
            try:
                scope_rank = scope_pairs.index((item.scope_type, item.scope_key))
            except ValueError:
                continue
            score = scope_rank * 10 + provider_rank
            scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], -pair[1].template_version))
        return [item for _, item in scored]

    def _deactivate_siblings(self, db: Session, entity: PromptTemplateORM) -> None:
        siblings = (
            db.query(PromptTemplateORM)
            .filter(
                PromptTemplateORM.template_key == entity.template_key,
                PromptTemplateORM.provider_scope == entity.provider_scope,
                PromptTemplateORM.scope_type == entity.scope_type,
                PromptTemplateORM.scope_key == entity.scope_key,
                PromptTemplateORM.id != entity.id,
                PromptTemplateORM.is_active.is_(True),
            )
            .all()
        )
        for item in siblings:
            item.is_active = False
            if item.status == "active":
                item.status = "retired"

    def _apply_genre_rulepack_overlay(self, *, action_name: str, system_prompt: str, user_prompt: str, render_context: dict[str, Any]) -> tuple[str, str]:
        genre_rulepack_summary = str(render_context.get("genre_rulepack_summary") or "").strip()
        if not genre_rulepack_summary:
            return system_prompt, user_prompt
        overlay_lines = [
            f"题材规则摘要：{genre_rulepack_summary}",
            f"题材世界规则：{self._stringify(render_context.get('genre_world') or render_context.get('genre_world_json') or {})}",
            f"题材叙事偏好：{self._stringify(render_context.get('genre_narrative') or render_context.get('genre_narrative_json') or {})}",
            f"题材风格约束：{self._stringify(render_context.get('genre_style') or render_context.get('genre_style_json') or {})}",
            f"禁用词：{self._stringify(render_context.get('genre_banned_terms') or render_context.get('genre_banned_terms_json') or [])}",
            f"禁忌：{self._stringify(render_context.get('genre_taboos') or render_context.get('genre_taboos_json') or [])}",
        ]
        overlay = "\n".join(overlay_lines)
        if genre_rulepack_summary in user_prompt:
            return system_prompt, user_prompt
        if action_name in {"generate_story_planning", "generate_story_directory", "generate_blueprints", "decompose_scenes", "generate_draft", "revise_draft", "review_gate", "propose_changeset", "summarize_chapter"}:
            user_prompt = f"{user_prompt}\n\n【题材配置层 / RulePack】\n{overlay}"
        return system_prompt, user_prompt

    def _render(self, template: str, render_context: dict[str, Any]) -> str:
        flat: dict[str, str] = {}
        for key, value in render_context.items():
            flat[key] = self._stringify(value)
            if key.endswith("_json"):
                continue
            if isinstance(value, (dict, list)):
                flat[f"{key}_json"] = json.dumps(value, ensure_ascii=False)
        return template.format_map(SafeFormatDict(flat))

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _build_fallback_default(self, *, agent_type: str, action_name: str) -> PromptTemplateORM:
        matched = next((item for item in DEFAULT_PROMPT_TEMPLATES if item["agent_type"] == agent_type and item["action_name"] == action_name), None)
        if matched is None:
            matched = {
                "template_key": f"{agent_type}.{action_name}",
                "agent_type": agent_type,
                "action_name": action_name,
                "provider_scope": "all",
                "scope_type": "global",
                "scope_key": "__global__",
                "system_template": "You are a structured agent.",
                "user_template": "{input_json}",
                "output_contract": {},
                "template_metadata": {"description": "fallback in-memory template"},
            }
        return PromptTemplateORM(
            id="in_memory_default",
            template_key=matched["template_key"],
            template_version=1,
            agent_type=matched["agent_type"],
            action_name=matched["action_name"],
            provider_scope=matched["provider_scope"],
            scope_type=matched["scope_type"],
            scope_key=matched["scope_key"],
            status="active",
            is_active=True,
            system_template=matched["system_template"],
            user_template=matched["user_template"],
            output_contract=matched.get("output_contract") or {},
            template_metadata=matched.get("template_metadata") or {},
        )


prompt_template_service = PromptTemplateService()
