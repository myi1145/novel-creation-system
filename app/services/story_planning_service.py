from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import GenreProfileORM, ProjectORM, StoryPlanningORM
from app.schemas.story_planning import (
    StoryPlanningGenerateData,
    StoryPlanningGenerateRequest,
    StoryPlanningGenerateResponse,
    StoryPlanningResponse,
    StoryPlanningUpsert,
)
from app.services.agent_gateway import AgentGatewayError, agent_gateway


class StoryPlanningService:
    _GENERATION_CONTRACT_REQUIRED_HEADINGS: dict[str, tuple[str, ...]] = {
        "worldview": ("[世界背景]", "[力量体系]", "[社会秩序]", "[势力格局]", "[资源与代价]", "[隐藏真相方向]", "[规则边界]"),
        "main_outline": (
            "[阅读承诺]",
            "[主角长期成长主线]",
            "[核心冲突]",
            "[关键角色关系张力]",
            "[关键配角功能]",
            "[主要对抗力量]",
            "[感情线/情绪主线]",
            "[长期钩子]",
            "[主线架构]",
            "[关键转折点]",
            "[长程悬念问题]",
        ),
        "volume_plan": ("[分卷规划原则]", "[卷一职责]", "[卷二职责]", "[卷三职责]", "[卷末承接]"),
        "core_seed_summary": (
            "[核心种子]",
            "[初始状态快照]",
            "[主角初始状态]",
            "[关键关系初始状态]",
            "[已知开放问题]",
            "[埋下的谜团/伏笔]",
            "[开局局势张力]",
            "[前期不可随意改写的状态边界]",
        ),
    }

    @staticmethod
    def _ensure_project_exists(db: Session, project_id: str) -> None:
        exists = db.query(ProjectORM.id).filter(ProjectORM.id == project_id).first()
        if not exists:
            raise NotFoundError("项目不存在")

    def get_story_planning(self, db: Session, project_id: str) -> StoryPlanningResponse | None:
        self._ensure_project_exists(db=db, project_id=project_id)
        item = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        if item is None:
            return None
        return StoryPlanningResponse.model_validate(item)

    def upsert_story_planning(self, db: Session, project_id: str, request: StoryPlanningUpsert) -> StoryPlanningResponse:
        self._ensure_project_exists(db=db, project_id=project_id)
        item = db.query(StoryPlanningORM).filter(StoryPlanningORM.project_id == project_id).first()
        if item is None:
            item = StoryPlanningORM(
                project_id=project_id,
                worldview=request.worldview,
                main_outline=request.main_outline,
                volume_plan=request.volume_plan,
                core_seed_summary=request.core_seed_summary,
                planning_status=request.planning_status,
                last_update_source="manual",
            )
            db.add(item)
        else:
            item.worldview = request.worldview
            item.main_outline = request.main_outline
            item.volume_plan = request.volume_plan
            item.core_seed_summary = request.core_seed_summary
            item.planning_status = request.planning_status
            item.last_update_source = "manual"
            item.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(item)
        return StoryPlanningResponse.model_validate(item)

    def generate_story_planning(
        self,
        db: Session,
        project_id: str,
        request: StoryPlanningGenerateRequest | None = None,
    ) -> StoryPlanningGenerateResponse:
        project = db.get(ProjectORM, project_id)
        if project is None:
            raise NotFoundError("项目不存在")

        context = self._build_generation_context(db=db, project=project, request=request or StoryPlanningGenerateRequest())
        try:
            raw_payload = self._invoke_generation_gateway(db=db, context=context, project=project)
            generated = self._normalize_generated_payload(raw_payload)
            generated = self._upgrade_generated_payload_contract(generated=generated, context=context)
        except ValidationError:
            raise
        except AgentGatewayError as exc:
            raise ValidationError("生成失败，请稍后重试。") from exc
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("生成失败，请稍后重试。") from exc

        return StoryPlanningGenerateResponse(
            project_id=project_id,
            generated=True,
            data=generated,
            message="全书规划草稿已生成。",
        )

    def _build_generation_context(
        self,
        db: Session,
        project: ProjectORM,
        request: StoryPlanningGenerateRequest,
    ) -> dict[str, Any]:
        genre_profile = None
        if project.genre_id:
            genre_profile = db.get(GenreProfileORM, project.genre_id)
        return {
            "project_id": project.id,
            "project_name": project.project_name,
            "premise": project.premise,
            "genre_id": project.genre_id or "unknown",
            "genre_name": (genre_profile.genre_name if genre_profile else project.genre_id) or "未指定题材",
            "genre_rule_summary": self._build_genre_rule_summary(genre_profile),
            "target_chapter_count": request.target_chapter_count,
            "tone": request.tone or "",
        }

    def _invoke_generation_gateway(self, db: Session, context: dict[str, Any], project: ProjectORM) -> Any:
        result = agent_gateway.generate_story_planning(
            db=db,
            context=context,
            audit_context={
                "project_id": project.id,
                "genre_id": project.genre_id,
                "workflow_name": "story_planning_generate",
            },
        )
        return result.payload

    def _normalize_generated_payload(self, payload: Any) -> StoryPlanningGenerateData:
        if not isinstance(payload, dict):
            raise ValidationError("生成失败，请稍后重试。")
        fields = ("worldview", "main_outline", "volume_plan", "core_seed_summary")
        values: dict[str, str] = {}
        for field in fields:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError("生成失败，请稍后重试。")
            values[field] = value.strip()
        return StoryPlanningGenerateData(**values)

    def _upgrade_generated_payload_contract(self, *, generated: StoryPlanningGenerateData, context: dict[str, Any]) -> StoryPlanningGenerateData:
        values = generated.model_dump()
        values["worldview"] = self._ensure_contract_sections(
            text=values["worldview"],
            required_headings=self._GENERATION_CONTRACT_REQUIRED_HEADINGS["worldview"],
            fallback_map=self._worldview_fallback_sections(context=context),
        )
        values["main_outline"] = self._ensure_contract_sections(
            text=values["main_outline"],
            required_headings=self._GENERATION_CONTRACT_REQUIRED_HEADINGS["main_outline"],
            fallback_map=self._main_outline_fallback_sections(context=context),
        )
        values["volume_plan"] = self._ensure_contract_sections(
            text=values["volume_plan"],
            required_headings=self._GENERATION_CONTRACT_REQUIRED_HEADINGS["volume_plan"],
            fallback_map=self._volume_plan_fallback_sections(context=context),
        )
        values["core_seed_summary"] = self._ensure_contract_sections(
            text=values["core_seed_summary"],
            required_headings=self._GENERATION_CONTRACT_REQUIRED_HEADINGS["core_seed_summary"],
            fallback_map=self._core_seed_fallback_sections(context=context),
        )
        return StoryPlanningGenerateData(**values)

    @staticmethod
    def _ensure_contract_sections(*, text: str, required_headings: tuple[str, ...], fallback_map: dict[str, str]) -> str:
        normalized = text.strip()
        for heading in required_headings:
            if heading in normalized:
                continue
            fallback = fallback_map.get(heading, "待作者确认并补充。")
            normalized += f"\n{heading} {fallback}".rstrip()
        return normalized.strip()

    @staticmethod
    def _worldview_fallback_sections(context: dict[str, Any]) -> dict[str, str]:
        genre_name = str(context.get("genre_name") or "当前题材")
        premise = str(context.get("premise") or "项目前提").strip()
        return {
            "[世界背景]": f"围绕《{genre_name}》题材建立长期可连载背景，主轴承接：{premise or '待补充'}。",
            "[力量体系]": "定义力量来源、成长路径、上限与反制关系，避免后期战力失衡。",
            "[社会秩序]": "明确秩序维护者、灰色地带与底层生存逻辑，保证冲突可持续。",
            "[势力格局]": "至少给出守成势力、扩张势力、隐性势力三方博弈坐标。",
            "[资源与代价]": "强调任何跃迁都需成本与后果，禁止无代价突破。",
            "[隐藏真相方向]": "设置贯穿全书的世界真相线，分阶段揭示，不可一次性揭底。",
            "[规则边界]": "列出不可越线规则与禁区，后续章节默认必须遵守。",
        }

    @staticmethod
    def _main_outline_fallback_sections(context: dict[str, Any]) -> dict[str, str]:
        premise = str(context.get("premise") or "项目前提").strip()
        tone = str(context.get("tone") or "稳健推进").strip()
        return {
            "[阅读承诺]": f"以“{premise or '主线冲突'}”为读者承诺，持续提供阶段性兑现与升级。",
            "[主角长期成长主线]": "主角从被动求生到主动破局，能力、认知与责任同步升级。",
            "[核心冲突]": "个人目标与既有秩序发生结构性冲突，并逐卷放大。",
            "[关键角色关系张力]": "主角与盟友/对手关系在利益与情感上持续拉扯。",
            "[关键配角功能]": "配角承担镜像、催化、制衡、背叛或救赎等叙事功能。",
            "[主要对抗力量]": "明确显性敌人与隐性操盘手，并保留中期反转空间。",
            "[感情线/情绪主线]": "情绪节奏遵循由低到高、由外冲突到内抉择的推进。",
            "[长期钩子]": "设置可贯穿中后期的核心谜题或未竟约定。",
            "[主线架构]": "按前期入局→中期扩张→中后期升级→终局收束组织主线。",
            "[关键转折点]": "每阶段至少设置一次高代价选择，推动角色关系重排。",
            "[长程悬念问题]": f"保留一个需到终局回答的问题，叙事气质保持{tone or '稳定'}。",
        }

    @staticmethod
    def _volume_plan_fallback_sections(context: dict[str, Any]) -> dict[str, str]:
        target = context.get("target_chapter_count")
        chapter_hint = f"目标章节数约 {target}" if target else "目标章节数待定"
        return {
            "[分卷规划原则]": f"每卷需承担独立职责并形成阶段性胜负，{chapter_hint}。",
            "[卷一职责]": "完成主角入局、关系网初建、世界规则首轮兑现。",
            "[卷二职责]": "扩大战场并提高代价，推动主角从局部胜利走向系统性对抗。",
            "[卷三职责]": "揭示核心真相与终局矛盾，完成主角能力与价值观终极考验。",
            "[卷末承接]": "每卷结尾必须留下下一卷核心驱动，不允许无后续牵引。",
        }

    @staticmethod
    def _core_seed_fallback_sections(context: dict[str, Any]) -> dict[str, str]:
        premise = str(context.get("premise") or "项目前提").strip()
        return {
            "[核心种子]": "给出角色、势力、地点、术语最小锚点，且可被后续目录拆解引用。",
            "[初始状态快照]": "记录开局时人物、关系、局势、伏笔的起始面板。",
            "[主角初始状态]": f"主角在开局对“{premise or '核心问题'}”仅具备局部认知与有限手段。",
            "[关键关系初始状态]": "明确主角与关键角色的信任/敌意/交易基线。",
            "[已知开放问题]": "列出当前已知但未解的问题，作为前中期推进抓手。",
            "[埋下的谜团/伏笔]": "给出可回收的谜团编号与预计回收区间。",
            "[开局局势张力]": "说明外部威胁、内部矛盾与时间压力三者如何同时作用。",
            "[前期不可随意改写的状态边界]": "冻结关键起点事实，避免前期反复改写导致失真。",
        }

    @staticmethod
    def _build_genre_rule_summary(genre_profile: GenreProfileORM | None) -> str:
        if genre_profile is None:
            return "未加载题材规则包，按项目题材与前提进行通用规划。"
        world_rules = genre_profile.world if isinstance(genre_profile.world, dict) else {}
        narrative_rules = genre_profile.narrative if isinstance(genre_profile.narrative, dict) else {}
        style_rules = genre_profile.style if isinstance(genre_profile.style, dict) else {}
        world_keywords = ", ".join(str(key) for key in list(world_rules.keys())[:5]) or "无"
        narrative_keywords = ", ".join(str(key) for key in list(narrative_rules.keys())[:5]) or "无"
        style_keywords = ", ".join(str(key) for key in list(style_rules.keys())[:5]) or "无"
        return (
            f"题材：{genre_profile.genre_name}。"
            f"世界规则关键词：{world_keywords}。"
            f"叙事规则关键词：{narrative_keywords}。"
            f"风格规则关键词：{style_keywords}。"
        )


story_planning_service = StoryPlanningService()
