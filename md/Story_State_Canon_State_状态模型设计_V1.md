# Story State / Canon State 状态模型设计（V1）

## 1. 文档信息

- 文档名称：Story State / Canon State 状态模型设计
- 版本：V1
- 文档定位：正式定版稿
- 上位文档：《小说多 Agent 系统最终架构设计文档（V1）》
- 文档目标：明确系统中“Story State”与“Canon State”的边界、分层、对象范围、生命周期、写入协议、读写权限、版本与回滚机制，为后续对象 Schema、Agent 契约、工作流实现与数据库设计提供统一状态基础。

---

## 2. 文档目的

长篇小说系统失控，通常不是因为“写不出来”，而是因为“写出来之后无法稳定地纳入系统真相”。

因此，本系统必须把“状态”从普通上下文文本中剥离出来，形成可追踪、可审批、可回滚、可派生的状态体系。

本文件要解决的核心问题是：

1. 系统里到底哪些内容属于状态。
2. 哪些状态属于正史，哪些不属于正史。
3. 状态如何从“候选内容”变成“可依赖事实”。
4. 状态由谁读、由谁写、谁有审批权。
5. 状态如何做版本、快照、冲突处理与回滚。

---

## 3. 术语定义

### 3.1 Story State

**Story State** 是系统中与当前创作项目相关的全部状态集合。

它不是单一的一份“小说设定”，而是一个总状态空间，包含：

- 已确认的正史事实
- 尚未确认的候选状态
- 工作流运行状态
- 章节生成过程中产生的临时状态
- 审阅结果与修订建议
- 派生索引和辅助检索状态

换言之：

**Story State = Canon State + Working State + Workflow State + Review State + Derived State**

### 3.2 Canon State

**Canon State** 是 Story State 中的“正史真相子集”，代表系统当前正式承认、后续创作必须遵守的事实视图。

Canon State 只包含：
- 已审批
- 已落库
- 可追溯来源
- 可作为后续生成与校验依据

的内容。

Canon State 不是“所有出现过的内容”，而是“已经成为当前正史的内容”。

### 3.3 Working State

**Working State** 是尚未成为正史的工作态状态。

包括：
- 候选卷规划
- 候选章蓝图
- 候选场景拆解
- 推演分支
- 临时设定补丁
- 未审批的变更提案
- 局部重写草稿

Working State 可以并行存在多个版本，可以被放弃、替换、覆盖，但不能自动视为正史。

### 3.4 ChangeSet

**ChangeSet** 指一次针对 Canon State 的结构化变更提案。

它描述：
- 想改什么
- 改前是什么
- 改后是什么
- 变更依据是什么
- 由谁提出
- 是否通过审批
- 是否已经应用

ChangeSet 是 Canon State 唯一合法写入入口。

### 3.5 Snapshot

**Snapshot** 指某一时刻的状态快照视图。

本系统至少包含两类快照：
- Canon Snapshot：当前正史真相快照
- Working Snapshot：某一工作分支或候选分支的状态快照

### 3.6 Immutable Log

**Immutable Log** 指不可变事件日志，用于记录状态演化历史。

它只追加，不覆盖，用于：
- 审计
- 回溯
- 回滚依据
- 事件重放
- 派生状态重建

---

## 4. 设计目标

本状态模型需要满足以下目标：

### 4.1 真相唯一

系统必须有明确的正史真相中心。任何后续生成、审阅、检索、对比，都应基于统一的 Canon State，而不是各 Agent 各自理解的文本上下文。

### 4.2 候选与正史分离

所有规划、试写、推演、局部补丁都必须先进入 Working State，不能直接污染正史。

### 4.3 状态可追踪

所有进入 Canon State 的内容必须能追溯到：
- 来源章节
- 来源对象
- 来源 ChangeSet
- 审批记录
- 应用时间

### 4.4 状态可回滚

错误写入、设定修订、分支回退都必须有回滚路径，不能依赖人工“记得改回来”。

### 4.5 结构化优先

状态应优先以结构化对象表示，而不是长文本自由描述。文本描述可作为补充，但不应替代状态字段。

### 4.6 权限明确

Agent、工作流服务、人工作者、审稿服务对状态的读取与写入权限必须明确区分。

---

## 5. 总体状态分层

本系统采用五层 Story State 分层模型。

## 5.1 第一层：Canon Truth Layer（正史真相层）

这是整个系统最核心的一层，用于保存当前已确认的正史事实。

包含：
- 项目级元信息
- 世界规则状态
- 角色当前状态
- 关系当前状态
- 时间线当前视图
- 伏笔当前状态
- 已发布章节状态
- 当前卷/篇章完成情况

特点：
- 权威
- 可依赖
- 仅可通过 ChangeSet 修改
- 供所有下游生成与校验读取

## 5.2 第二层：Working State Layer（工作态层）

用于承载尚未确认的创作工作结果。

包含：
- 候选卷方案
- 候选章蓝图
- 候选场景卡
- 草稿章节
- 局部重写版本
- 未审批设定补丁
- 推演分支状态

特点：
- 可并行
- 可丢弃
- 可替换
- 不作为正史依据

## 5.3 第三层：Workflow State Layer（流程运行层）

用于记录创作流程本身的运行状态，而不是小说内容事实。

包含：
- 当前任务状态
- 当前流程节点
- 节点输入输出引用
- 重试次数
- 失败原因
- 当前负责人/当前审批人
- 发布状态

特点：
- 面向系统运行控制
- 不属于小说世界内事实
- 可用于恢复中断流程

## 5.4 第四层：Review State Layer（审阅状态层）

用于记录质量闸门与审阅结果。

包含：
- Canon Gate 报告
- Narrative Gate 报告
- Voice Gate 报告
- Style Gate 报告
- 修订建议
- 问题等级
- 是否通过
- 是否需人工介入

特点：
- 面向质量控制
- 是决策辅助，不直接等于正史
- 可关联 ChangeSet 审批

## 5.5 第五层：Derived State Layer（派生状态层）

用于存放从正史与工作态派生出来的辅助索引与检索结果。

包含：
- 向量索引
- 图谱索引
- 摘要索引
- 人物语料索引
- 风格语料索引
- 候选方案对比缓存

特点：
- 可重建
- 非权威
- 不能反向覆盖 Canon State

---

## 6. Story State 与 Canon State 的边界

### 6.1 Story State 的范围

以下内容都属于 Story State：

1. 项目当前正史
2. 正在拟定的卷与章方案
3. 章节草稿与修订稿
4. 工作流执行状态
5. 审阅结果
6. 检索与索引派生结果
7. 作者手动创建但未审批的设定补丁

### 6.2 Canon State 的范围

以下内容属于 Canon State：

1. 已确认的世界观规则
2. 已确认的角色事实与当前状态
3. 已确认的关系状态
4. 已确认的时间线事件
5. 已确认的伏笔状态
6. 已发布章节的结构化元数据
7. 已确认的卷目标与主线阶段状态
8. 已审批并应用的设定变更

### 6.3 明确不属于 Canon State 的内容

以下内容不得直接视为 Canon：

1. 草稿正文
2. 候选章蓝图
3. 候选场景拆解
4. 审阅意见
5. 自动抽取但未经审批的新事实
6. 图谱推断结果
7. 向量召回结果
8. 临时推演分支

### 6.4 Canon 判定标准

某项内容要进入 Canon State，必须同时满足：

1. 来源明确
2. 结构化可表示
3. 可与现有 Canon 进行冲突校验
4. 已形成 ChangeSet
5. 已通过审批规则或人工审批
6. 已写入 Canon Snapshot 与 Immutable Log

---

## 7. Canon State 领域模型

V1 阶段，Canon State 至少包含以下十个核心领域。

## 7.1 ProjectMetaState（项目元状态）

用于描述项目级全局信息。

建议字段：
- project_id
- title
- genre_template_id
- style_pack_id
- target_length_type
- current_volume_no
- current_chapter_no
- canon_version
- current_story_phase
- publish_status
- created_at
- updated_at

说明：
- 该对象不承载具体剧情事实，而承载项目级控制信息。

## 7.2 WorldRuleState（世界规则状态）

用于保存世界规则与硬约束。

建议字段：
- rule_id
- rule_domain（修炼体系 / 职业体系 / 社会规则 / 科技规则 / 魔法规则等）
- rule_name
- rule_description
- rule_strength（硬规则 / 软规则）
- effective_scope
- exception_clause
- status
- source_ref
- version

说明：
- 硬规则冲突应优先拦截。
- 规则状态是 Canon Gate 的核心输入之一。

## 7.3 CharacterState（角色状态）

用于保存角色当前正史状态，而不是角色全文简介。

建议字段：
- character_id
- name
- aliases
- role_type
- current_identity
- current_faction
- current_location
- current_goal
- long_term_motivation
- public_knowledge
- private_truth
- capability_state
- resource_state
- status_flags（受伤 / 失踪 / 死亡 / 潜伏 / 通缉等）
- relationship_summary_refs
- arc_stage
- last_significant_event_id
- first_appearance_chapter
- last_update_chapter
- source_refs
- version

说明：
- V1 重点保存“当前状态”，而不是无限堆积背景故事。
- 可把长背景放在对象层文本字段，但 Canon 内重点看可约束后续创作的当前事实。

## 7.4 RelationshipState（关系状态）

用于保存人物、人物与势力、人物与地点之间的当前关系事实。

建议字段：
- relation_id
- subject_id
- object_id
- relation_type
- current_stage
- trust_level
- intimacy_level
- hostility_level
- dependency_type
- public_visibility
- key_history_event_refs
- active_tension
- current_direction
- last_update_chapter
- version

说明：
- 不建议把关系只写成一句文本。
- 长篇中关系推进是核心状态，必须可追踪。

## 7.5 TimelineState（时间线状态）

用于保存已经进入正史的时间线事件。

建议字段：
- event_id
- event_name
- event_type
- absolute_time_marker
- relative_time_marker
- chapter_ref
- location_ref
- participants
- event_summary
- consequences
- causal_parent_refs
- visibility_scope
- canon_status
- version

说明：
- 时间线事件应以事件卡或事件状态保存，避免后续出现前后顺序错乱。

## 7.6 LocationState（地点状态）

用于保存地点当前状态。

建议字段：
- location_id
- location_name
- location_type
- jurisdiction
- current_owner_or_controller
- danger_level
- accessibility
- current_event_refs
- hidden_truths
- status
- version

说明：
- 对长篇而言，地点不是静态名词，经常带有“已沦陷 / 已封锁 / 正在重建”等动态状态。

## 7.7 FactionState（势力状态）

用于保存势力当前状态。

建议字段：
- faction_id
- faction_name
- faction_type
- ideology_or_core_position
- current_leader
- current_power_level
- allies
- enemies
- internal_status
- recent_events
- strategic_goal
- exposure_level
- version

## 7.8 OpenLoopState（伏笔 / 未闭环状态）

用于保存所有仍在生效的未闭环叙事要素。

建议字段：
- loop_id
- loop_title
- loop_type（悬念 / 承诺 / 隐秘身份 / 未揭示规则 / 未兑现情感 / 任务目标等）
- opened_at_chapter
- opened_by_event_ref
- current_status（open / remind / escalate / resolve_pending / resolved / abandoned）
- importance_level
- related_entities
- reminder_strategy
- expected_resolution_window
- actual_resolution_ref
- version

说明：
- 这部分是长篇系统的一等公民，不能只靠摘要记忆。

## 7.9 VolumeArcState（卷弧光 / 阶段状态）

用于保存当前卷或阶段级主线推进状态。

建议字段：
- volume_id
- volume_no
- title
- main_conflict
- sub_conflicts
- phase_goal
- entry_condition
- current_progress_stage
- locked_end_condition
- key_open_loops
- protagonist_arc_target
- relationship_arc_targets
- pacing_profile_id
- status
- version

说明：
- 该状态帮助系统判断“本章应该推进什么”，避免章节生成漂移。

## 7.10 PublishedChapterState（已发布章节状态）

用于保存章节一旦发布后，被纳入正史的章级元信息。

建议字段：
- chapter_id
- chapter_no
- volume_no
- title
- pov
- chapter_goal_summary
- key_events
- state_changes_summary
- newly_opened_loops
- resolved_loops
- participating_entities
- publish_time
- canon_version_after_publish

说明：
- 这里保存的是结构化章摘要与状态变化摘要，不一定保存整章正文。

---

## 8. Working State 模型

Working State 用于承载所有“未入正史”的中间态。

## 8.1 候选方案状态

包括：
- CandidateVolumeBlueprint
- CandidateChapterBlueprint
- CandidateScenePlan
- CandidateTwistPlan

建议字段：
- candidate_id
- parent_ref
- branch_id
- objective_summary
- expected_state_changes
- risk_points
- fit_score
- selected_flag
- status

## 8.2 草稿状态

包括：
- DraftChapter
- DraftScene
- RewriteDraft
- LocalPatchDraft

建议字段：
- draft_id
- source_candidate_ref
- draft_type
- content
- status
- review_refs
- created_by
- created_at
- superseded_by

## 8.3 未审批变更状态

包括：
- DraftChangeSet
- PendingCanonPatch
- HumanManualPatchDraft

说明：
- 未审批变更允许存在，但必须明确标记为 pending，不得被下游直接当作 Canon 使用。

---

## 9. Workflow State 模型

Workflow State 用于描述系统当前“做到哪一步了”。

建议最小字段：
- workflow_run_id
- workflow_type
- project_id
- current_node
- node_status
- input_refs
- output_refs
- retry_count
- blocked_reason
- assigned_to
- started_at
- updated_at
- finished_at

说明：
- Workflow State 不进入小说正史。
- 但它对恢复流程、问题排查、任务可观测性非常重要。

---

## 10. Review State 模型

Review State 记录质量闸门结果。

建议最小字段：
- review_id
- review_type
- target_ref
- input_refs
- result_status
- issue_list
- severity_summary
- patch_suggestions
- reviewer_type（rule / llm / human）
- reviewer_id
- created_at

说明：
- Review State 不自动修改 Canon。
- 它只为修订或审批提供依据。

---

## 11. Derived State 模型

Derived State 包括所有可重建的派生结果。

包括：
- VectorMemoryIndex
- GraphProjectionIndex
- ChapterSummaryIndex
- CharacterVoiceCorpusIndex
- StyleReferenceIndex

原则：
1. 可删除重建。
2. 不作为最终真相来源。
3. 不得绕过 ChangeSet 反写 Canon。

---

## 12. Canon Snapshot 结构

V1 阶段，Canon Snapshot 建议采用“项目总快照 + 分领域子快照”结构。

## 12.1 顶层结构

```json
{
  "project_meta": {},
  "world_rules": [],
  "characters": [],
  "relationships": [],
  "timeline_events": [],
  "locations": [],
  "factions": [],
  "open_loops": [],
  "volume_arcs": [],
  "published_chapters": [],
  "snapshot_meta": {}
}
```

## 12.2 snapshot_meta 建议字段

- snapshot_id
- project_id
- canon_version
- source_changeset_ids
- generated_at
- generated_by
- checksum
- parent_snapshot_id

说明：
- Canon Snapshot 是读取优化后的当前真相视图。
- 它可由 Immutable Log + 已应用 ChangeSet 重建，但运行时不应每次都临时重算。

---

## 13. Immutable Log 模型

Immutable Log 用于记录所有已发生的关键状态事件。

建议字段：
- log_id
- event_type
- project_id
- related_changeset_id
- target_domain
- target_id
- operation_type
- before_ref
- after_ref
- triggered_by
- approved_by
- occurred_at
- note

常见 event_type：
- chapter_published
- canon_patch_applied
- canon_patch_rolled_back
- rule_added
- character_state_changed
- relationship_state_changed
- open_loop_opened
- open_loop_resolved
- volume_phase_shifted

原则：
- 只追加
- 不覆盖
- 可分页检索
- 可按 domain 或 chapter 回放

---

## 14. ChangeSet 模型

ChangeSet 是 Canon State 的唯一合法写入入口。

## 14.1 ChangeSet 最小结构

建议字段：
- changeset_id
- project_id
- source_type
- source_ref
- changeset_type
- proposed_by_type
- proposed_by_id
- target_domains
- affected_object_refs
- before_snapshot_refs
- patch_operations
- rationale
- conflict_check_result
- review_refs
- approval_mode
- approval_status
- approved_by
- applied_flag
- applied_at
- rollback_of
- version

## 14.2 patch_operations 设计原则

每条 patch operation 至少包含：
- target_domain
- target_id
- op_type（create / update / append / close / remove / replace_status）
- field_path
- before_value
- after_value
- confidence
- evidence_refs

## 14.3 ChangeSet 分类

建议至少分为：
- chapter_publish_changeset
- human_manual_patch
- rule_fix_patch
- retcon_patch
- rollback_changeset

说明：
- retcon_patch 指事后修订正史，必须提高审批等级。

---

## 15. 状态生命周期

本系统中，一项内容进入 Canon 的标准生命周期如下：

### 第一步：生成候选内容

来源可能是：
- Planner 生成的章蓝图
- Writer 生成的章节草稿
- Human 创建的设定补丁
- Review Service 提出的修复建议

此时内容只存在于 Working State。

### 第二步：抽取状态变化

系统或 Agent 从候选内容中提取潜在状态变化，例如：
- 某角色身份变化
- 某关系推进
- 某伏笔被打开
- 某地点状态改变

### 第三步：形成 Draft ChangeSet

将提取结果结构化为 Draft ChangeSet。

### 第四步：冲突检查

对 Draft ChangeSet 做以下检查：
- 是否与现有 Canon 冲突
- 是否缺少必要引用
- 是否修改了禁止自动修改字段
- 是否存在跨域不一致

### 第五步：进入审阅与审批

根据变更类型进入：
- 自动审批
- 人工审批
- 升级审批

### 第六步：Apply 到 Canon

审批通过后：
- 写入 Immutable Log
- 更新 Canon Snapshot
- 递增 canon_version
- 触发派生索引刷新

### 第七步：发布或生效

若来源于章节发布，则章节元信息也写入 PublishedChapterState。

---

## 16. 读写权限模型

为防止状态污染，必须明确不同参与方的权限。

## 16.1 Agent 权限

Agent 可以：
- 读取 Canon Snapshot
- 读取相关对象
- 读取 Working State
- 生成候选内容
- 提出 Draft ChangeSet
- 生成审阅意见

Agent 不可以：
- 直接写 Canon Snapshot
- 直接覆盖已存在 Canon 字段
- 直接发布章节
- 直接修改 Immutable Log

## 16.2 Workflow Service 权限

Workflow Service 可以：
- 驱动节点流转
- 校验输入输出
- 创建 ChangeSet 流程记录
- 在审批通过后执行 Apply
- 刷新派生状态

Workflow Service 不可以：
- 绕过审批强制写 Canon（除非系统级管理员操作）

## 16.3 Human Author / Editor 权限

作者或编辑可以：
- 查看全部状态
- 选择候选方案
- 手工提出补丁
- 审批或驳回 ChangeSet
- 发起回滚
- 标记某些状态为锁定字段

## 16.4 Review Services 权限

审阅服务可以：
- 读取 Canon 与草稿
- 输出问题报告
- 生成修订建议

审阅服务不可以：
- 自动修改 Canon

---

## 17. 冲突处理规则

状态冲突是长篇系统中的常态，必须制度化处理。

## 17.1 冲突类型

至少识别以下冲突：

1. **硬规则冲突**
   - 违反已确认世界规则

2. **角色状态冲突**
   - 角色已死亡却再次以正常状态出现

3. **关系状态冲突**
   - 关系推进与前文阶段不一致

4. **时间线冲突**
   - 事件先后矛盾

5. **地点状态冲突**
   - 地点已封锁却被无条件进入

6. **伏笔状态冲突**
   - 已解决的伏笔又被当成未解决使用

## 17.2 处理优先级

优先级建议为：

1. 硬规则冲突
2. 时间线冲突
3. 角色状态冲突
4. 关系状态冲突
5. 伏笔状态冲突
6. 风格冲突

## 17.3 冲突处理策略

- 可自动修复：进入修订流程
- 不可自动修复：阻断发布，要求人工处理
- 属于设定重构：升级为 retcon_patch

---

## 18. 版本、快照与回滚

## 18.1 canon_version 规则

每次成功 Apply ChangeSet 后，canon_version 必须递增。

建议：
- 项目级维护单一 canon_version
- 分领域对象维护 object_version

## 18.2 快照策略

建议采用：
- 每次章节发布后生成稳定 Canon Snapshot
- 每次重大设定修订后强制生成 Snapshot
- 中间 Apply 可按批次生成轻量快照

## 18.3 回滚策略

回滚必须通过 rollback_changeset 实现，而不是直接删改原始日志。

回滚流程：
1. 指定目标 ChangeSet 或目标 Snapshot
2. 计算逆向 Patch
3. 生成 rollback_changeset
4. 审批
5. Apply rollback
6. 生成新 canon_version

说明：
- 回滚不是回到过去并擦除历史，而是在当前版本基础上追加一次“逆向修正”。

---

## 19. MVP 范围

V1 的状态模型不追求一步到位覆盖所有文学概念，MVP 只定最关键状态。

## 19.1 P0 必做状态域

1. ProjectMetaState
2. WorldRuleState
3. CharacterState
4. RelationshipState
5. TimelineState
6. OpenLoopState
7. VolumeArcState
8. PublishedChapterState
9. Canon Snapshot
10. ChangeSet
11. Immutable Log

## 19.2 P0 必做能力

1. Canon / Working 严格分离
2. ChangeSet 唯一写入入口
3. 章节发布后自动生成状态变更提案
4. 审批后更新 Canon Snapshot
5. 记录 Immutable Log
6. 支持基础回滚

## 19.3 可延后能力

1. 多分支并行推演管理
2. 复杂图谱反查
3. 自动冲突合并
4. 跨项目共享世界状态
5. 高级统计与状态分析面板

---

## 20. 与其他文档的关系

本文件是状态总线的基础文档，后续文档应基于本文件继续细化：

1. 《结构化创作对象 Schema 设计（V1）》
   - 细化对象字段与对象关系

2. 《Agent 契约说明（V1）》
   - 定义每类 Agent 的读取边界、输出格式与禁止写入行为

3. 《章节循环工作流说明（V1）》
   - 定义状态如何在八步循环中流动

4. 《多层质量闸门设计（V1）》
   - 定义 Review State 与审批链

5. 《数据库与存储映射设计（V1）》
   - 将本文件中的状态域映射到表结构与日志结构

---

## 21. V1 定版结论

本系统正式采用以下状态模型原则：

1. **Story State 是总状态空间，Canon State 是其正史真相子集。**
2. **候选内容、草稿、审阅意见、派生索引都不等于 Canon。**
3. **Canon State 只能通过 ChangeSet 进入，不能被 Agent 直接写入。**
4. **Immutable Log 是状态演化依据，Canon Snapshot 是运行时真相视图。**
5. **状态设计以“当前可约束后续创作的事实”为中心，而不是堆积无边界文本。**
6. **V1 先保证正史边界清晰、版本可追踪、回滚可执行，再逐步扩展更细粒度状态。**

本文件定版后，后续所有对象设计、流程设计、数据库设计与 Agent 设计，均必须遵守本文件中定义的状态边界与写入协议。
