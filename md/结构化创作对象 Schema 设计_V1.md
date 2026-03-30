# 结构化创作对象 Schema 设计（V1）

## 1. 文档信息

- 文档名称：结构化创作对象 Schema 设计
- 版本：V1
- 文档定位：正式定版稿
- 关联文档：
  - 《小说多 Agent 系统最终架构设计文档（V1）》
  - 《Story State / Canon State 状态模型设计（V1）》
- 文档目标：定义小说多 Agent 创作控制系统中的结构化创作对象体系、对象分类、公共元数据、核心对象字段、对象关系、版本机制、校验机制与 MVP 范围，为后续 Agent 契约、工作流编排、状态写入、质量闸门与存储设计提供统一对象协议。

---

## 2. 文档目的

本系统的一个核心前提是：

**创作中间产物不能只以自由文本存在，而必须以可引用、可校验、可追踪、可版本化的结构化对象存在。**

如果角色、设定、章节目标、场景拆解、伏笔状态、审核结果都只是 prompt 中的一段文字，那么系统最终会退化为：

- prompt 拼装器
- 记忆片段堆积器
- 多 Agent 文本接力系统

这会直接导致：

- 无法稳定校验对象间关系
- 无法建立明确的写入权限边界
- 无法追踪创作中间状态来源
- 无法支持精细化回滚与对象级审批
- 无法把规划、写作、审阅、状态更新真正分层

因此，本系统必须采用：

**Schema-first Creative Object 机制。**

即：先定义对象，再定义流程；先定义字段，再定义生成；先定义协议，再定义 Agent。

---

## 3. 设计原则

### 3.1 对象优先于文本块

所有关键创作资产必须先成为对象，再决定是否渲染成文本给模型使用。

### 3.2 正史与工作态分离

结构化对象必须区分：
- 正史对象
- 工作态对象
- 候选对象
- 审核对象
- 派生对象

不是所有对象都天然属于 Canon 正史。

### 3.3 每个对象都必须可追踪来源

任意对象都必须能回答以下问题：
- 谁生成的
- 基于什么输入生成的
- 当前版本是多少
- 是否已审批
- 是否已被发布引用
- 是否已写入 Canon

### 3.4 每个对象都必须可引用

章节蓝图、场景卡、审核结果、变更提议不能只是孤立文本，必须能引用角色、地点、规则、伏笔、时间线事件等对象。

### 3.5 对象必须可版本化

对象被修改后，不应简单覆盖；至少在系统层面要支持：
- 当前版本号
- 上一版本引用
- 变更摘要
- 版本状态

### 3.6 公共协议统一，题材字段可扩展

对象层的公共协议必须统一；题材差异通过：
- genre_profile
- extension_fields
- plugin_fields
- domain_specific_constraints

来扩展，而不是破坏底座字段结构。

### 3.7 Schema 要服务于工作流，而不是为存档而存档

对象字段设计不是为了“信息越多越好”，而是为了支撑：
- 规划
- 写作
- 审核
- 状态更新
- 索引与检索
- 人工编辑
- 回滚与审计

---

## 4. 创作对象总分类

V1 将结构化创作对象分为五大类。

### 4.1 世界与设定对象（World Objects）

用于描述小说世界中的长期稳定元素。

包括：
- CharacterCard（角色卡）
- LocationCard（地点卡）
- FactionCard（势力卡）
- ItemCard（物品卡）
- RuleCard（规则卡）
- TerminologyCard（术语卡）
- SystemMechanicCard（体系机制卡，可选）

### 4.2 叙事推进对象（Narrative Objects）

用于描述故事推进中的结构化单元。

包括：
- TimelineEventCard（时间线事件卡）
- RelationshipEdge（关系边）
- ArcCard（人物弧光卡）
- OpenLoopCard（伏笔卡）
- HookCard（钩子卡）
- VolumeBlueprint（卷蓝图）
- ChapterBlueprint（章蓝图）
- SceneCard（场景卡）

### 4.3 控制与评审对象（Control Objects）

用于约束生成行为与记录质量结论。

包括：
- PacingConstraintCard（节奏约束卡）
- StyleConstraintCard（风格约束卡）
- ReviewResultCard（审核结果卡）
- RiskAlertCard（风险预警卡）
- ChangeProposalCard（变更提议卡）

### 4.4 运行与发布对象（Runtime Objects）

用于承载流程过程中的操作记录与发布状态。

包括：
- DraftRecord（草稿记录）
- PublishRecord（发布记录）
- CandidateSet（候选集）
- SelectionDecision（选择决策记录）
- WorkflowRunRecord（流程运行记录）

### 4.5 派生与辅助对象（Derived Objects）

用于服务检索、摘要、图谱与提示词组织。

包括：
- SummaryCard（摘要卡）
- EvidenceBundle（证据包）
- RetrievalContextPack（检索上下文包）
- VoiceSamplePack（人物声音样本包）
- StyleSamplePack（风格样本包）

说明：

派生与辅助对象不是 Canon 真相对象，但可被工作流与 Agent 引用。

---

## 5. 对象公共协议

所有结构化创作对象都必须遵循统一公共协议。

### 5.1 公共顶层字段

每个对象至少包含以下顶层字段：

- object_id：对象唯一 ID
- object_type：对象类型
- schema_version：Schema 版本
- object_version：对象版本号
- project_id：所属项目
- story_id：所属作品
- status：对象状态
- lifecycle_stage：生命周期阶段
- source_type：来源类型
- source_ref：来源引用
- created_by：创建主体
- updated_by：最后更新主体
- created_at：创建时间
- updated_at：最后更新时间
- tags：标签列表
- genre_profile：题材配置引用
- extension_fields：扩展字段

### 5.2 推荐状态枚举

status 推荐枚举：
- draft
- candidate
- selected
- approved
- active
- archived
- deprecated
- rejected

lifecycle_stage 推荐枚举：
- planning
- drafting
- reviewing
- canon_pending
- published
- retired

### 5.3 来源类型枚举

source_type 推荐枚举：
- human_created
- human_edited
- agent_generated
- workflow_generated
- extracted_from_text
- imported
- system_derived

### 5.4 公共关系字段

每个对象都应支持以下关系字段：

- refs：当前对象主动引用的对象列表
- ref_by：引用当前对象的对象列表（可在索引层维护）
- related_objects：弱关联对象列表
- parent_object_id：父对象 ID
- child_object_ids：子对象 ID 列表

### 5.5 公共审计字段

每个对象建议具备：

- change_summary：本次版本变更摘要
- review_status：审核状态
- review_refs：关联审核结果卡列表
- approval_required：是否需要审批
- canon_write_intent：是否存在写入 Canon 意图
- canon_state_binding：是否已绑定 Canon 状态域

---

## 6. 核心对象字段设计

以下对象为 V1 必须定版的核心对象。

---

## 6.1 CharacterCard（角色卡）

### 6.1.1 对象定位

CharacterCard 是角色真相与角色控制的核心对象，用于承载角色的身份、目标、能力、关系、行为边界、声音风格与阶段状态。

### 6.1.2 必要字段

- object_id
- object_type = CharacterCard
- name：角色名
- aliases：别名列表
- role_type：角色类型（主角/核心配角/反派/路人等）
- narrative_importance：叙事重要度
- identity_summary：身份摘要
- public_identity：公开身份
- hidden_identity：隐藏身份
- faction_refs：所属势力引用
- location_refs：常驻地点引用
- age_or_stage：年龄或阶段
- gender_presentation：性别呈现（可选）
- appearance_notes：外观识别要点
- personality_traits：性格标签
- core_motivation：核心动机
- short_term_goals：短期目标
- long_term_goals：长期目标
- fear_and_weakness：弱点与恐惧
- value_system：价值观
- taboo_list：禁忌点
- speaking_style：说话风格
- voice_samples_ref：声音样本引用
- capability_profile：能力档案
- knowledge_scope：认知范围
- relationship_refs：关系边引用
- current_status：当前状态摘要
- arc_refs：人物弧光引用
- first_appearance_chapter：首次登场章
- latest_major_change：最近重大变化
- canon_truth_level：正史确定级别

### 6.1.3 说明

CharacterCard 是高优先级正史对象。涉及以下内容的变更通常需要进入 ChangeSet：
- 身份变化
- 势力归属变化
- 能力等级变化
- 关系状态变化
- 生死状态变化
- 核心动机重大改变

---

## 6.2 LocationCard（地点卡）

### 6.2.1 对象定位

LocationCard 用于承载世界中的空间节点信息，支持叙事场景、路线约束、势力分布、事件定位与地理一致性校验。

### 6.2.2 必要字段

- object_id
- object_type = LocationCard
- name：地点名称
- aliases：别名列表
- location_type：地点类型
- parent_location_ref：上级地点引用
- child_location_refs：下级地点引用
- controlling_faction_refs：控制势力引用
- spatial_scope：空间级别
- environment_traits：环境特征
- access_constraints：进入条件/移动限制
- culture_notes：文化与风俗要点
- strategic_value：战略价值
- secrecy_level：公开/隐蔽等级
- first_appearance_chapter
- current_status：当前状态
- related_rule_refs：相关规则引用

---

## 6.3 FactionCard（势力卡）

### 6.3.1 对象定位

FactionCard 用于承载宗门、组织、学校、公司、家族、阵营等长期存在的集体实体。

### 6.3.2 必要字段

- object_id
- object_type = FactionCard
- name
- aliases
- faction_type
- public_positioning：外部形象
- true_agenda：真实目标
- ideology：核心理念
- hierarchy_summary：组织结构摘要
- leader_refs：核心领导引用
- member_refs：关键成员引用
- territory_refs：势力影响范围引用
- ally_faction_refs：盟友势力
- enemy_faction_refs：敌对势力
- resources_summary：资源概况
- taboo_and_rules：内部禁忌与规章
- current_status
- active_conflict_refs：正在参与的冲突引用

---

## 6.4 RuleCard（规则卡）

### 6.4.1 对象定位

RuleCard 用于承载世界中必须稳定遵守的规则，包括修炼体系、能力边界、社会规则、技术规则、悬疑推理规则等。

### 6.4.2 必要字段

- object_id
- object_type = RuleCard
- rule_name：规则名称
- rule_category：规则类别
- scope：适用范围
- statement：规则陈述
- implications：规则推论
- examples：示例
- constraints：限制条件
- violation_cost：违反代价
- exception_conditions：例外条件
- certainty_level：确定性等级
- related_terms_refs：相关术语引用
- related_object_refs：相关对象引用
- source_basis：来源依据
- canon_priority：正史优先级

### 6.4.3 说明

RuleCard 属于高约束对象，是 Canon Gate 的关键输入之一。未经审批不得随意改动。

---

## 6.5 TerminologyCard（术语卡）

### 6.5.1 对象定位

用于维护题材专属名词、境界体系、机构名称、装备命名、社会称谓等术语的一致性。

### 6.5.2 必要字段

- object_id
- object_type = TerminologyCard
- term：术语名称
- aliases：同义表达
- term_category：术语类别
- canonical_definition：标准定义
- usage_constraints：使用限制
- forbidden_usages：禁止误用
- tone_register：语体等级
- related_rule_refs
- related_object_refs
- replacement_suggestions：替代表达建议

---

## 6.6 RelationshipEdge（关系边）

### 6.6.1 对象定位

RelationshipEdge 用于明确两个角色、角色与势力、角色与地点之间的结构化关系，支持人物关系演化与关系一致性校验。

### 6.6.2 必要字段

- object_id
- object_type = RelationshipEdge
- source_entity_ref
- target_entity_ref
- relation_type：关系类型
- relation_stage：关系阶段
- public_visibility：关系公开程度
- emotional_polarity：情感极性
- trust_level：信任等级
- dependency_level：依赖等级
- conflict_level：冲突等级
- latest_trigger_event_ref：最近变化事件引用
- change_history_summary：变化摘要
- stability_level：稳定度

### 6.6.3 说明

关系边不只是展示用途，还要进入：
- 章蓝图规划
- 人物行为合理性判断
- Voice Gate / Narrative Gate 的辅助判断

---

## 6.7 TimelineEventCard（时间线事件卡）

### 6.7.1 对象定位

用于记录故事时间线中的关键事件，是时间顺序、因果关系、状态变更的桥梁对象。

### 6.7.2 必要字段

- object_id
- object_type = TimelineEventCard
- event_name
- event_type
- event_time_position：时间位置
- chronology_order：时间顺序号
- participants_refs：参与对象列表
- location_ref：发生地点
- cause_refs：原因引用
- consequence_summary：结果摘要
- affected_object_refs：受影响对象列表
- linked_chapter_ref：对应章节引用
- canonization_status：是否已正史化

---

## 6.8 OpenLoopCard（伏笔卡）

### 6.8.1 对象定位

OpenLoopCard 是长篇系统中的核心叙事控制对象，用于管理伏笔、悬念、承诺、未解释异常、待回收信息与读者期待点。

### 6.8.2 必要字段

- object_id
- object_type = OpenLoopCard
- loop_title：伏笔标题
- loop_type：伏笔类型
- setup_ref：埋设来源引用
- setup_chapter_ref：埋设章节
- setup_text_span_ref：埋设文本区间引用
- narrative_purpose：叙事目的
- importance_level：重要等级
- expected_payoff_window：预期回收区间
- current_state：当前状态
- remind_frequency_hint：提醒频率建议
- related_character_refs
- related_rule_refs
- risk_if_dropped：若遗失的风险
- payoff_candidate_refs：候选回收点引用
- resolved_by_ref：回收来源引用
- resolution_summary：回收摘要

### 6.8.3 当前状态枚举建议

- open
- planted
- reminded
- escalated
- partially_paid_off
- resolved
- abandoned
- retconned

---

## 6.9 ArcCard（弧光卡）

### 6.9.1 对象定位

ArcCard 用于维护人物成长线、关系弧、主题弧或支线弧的结构性推进状态。

### 6.9.2 必要字段

- object_id
- object_type = ArcCard
- arc_name
- arc_type
- owner_refs：弧光所属对象
- start_state：起点状态
- target_state：目标状态
- midpoint_constraints：中段约束
- key_turning_points：关键转折点列表
- current_progress_state：当前推进状态
- blocked_by_refs：阻塞因素引用
- milestone_refs：关键节点引用
- completion_criteria：完成条件

---

## 6.10 VolumeBlueprint（卷蓝图）

### 6.10.1 对象定位

VolumeBlueprint 是卷级规划对象，负责定义某一卷的目标、节奏、主要冲突、核心关系推进与结尾状态。

### 6.10.2 必要字段

- object_id
- object_type = VolumeBlueprint
- volume_no：卷序号
- volume_title：卷标题
- stage_type：卷阶段类型
- volume_goal：本卷目标
- entry_state_summary：入卷状态摘要
- exit_state_summary：出卷状态摘要
- major_conflict_summary：主要冲突
- sub_conflict_summary：次级冲突
- major_arc_refs：主要弧光引用
- required_open_loop_actions：本卷必须处理的伏笔动作
- pacing_profile：节奏模板
- target_chapter_count：目标章节数
- forbidden_directions：禁止方向
- success_criteria：完成判据

---

## 6.11 ChapterBlueprint（章蓝图）

### 6.11.1 对象定位

ChapterBlueprint 是章节执行的核心对象，必须成为 Planner、Writer、Reviewer 的共同输入基础。

### 6.11.2 必要字段

- object_id
- object_type = ChapterBlueprint
- chapter_no：章节号
- chapter_title_candidate：章节标题候选
- belongs_to_volume_ref：所属卷引用
- blueprint_type：蓝图类型（候选/已选定）
- chapter_goal：本章目标
- chapter_function：本章功能
- required_inputs：必须承接内容
- target_outputs：本章应产出内容
- main_conflict：主要冲突
- secondary_conflicts：次要冲突
- pov_requirement：视角要求
- involved_character_refs：涉及角色
- involved_location_refs：涉及地点
- involved_rule_refs：涉及规则
- open_loop_actions：伏笔动作
- hook_design：钩子设计
- information_delta：信息增量摘要
- emotional_curve_summary：情绪曲线摘要
- pacing_constraints_ref：节奏约束引用
- risk_points：风险点列表
- selected_reason：被选中原因

### 6.11.3 说明

ChapterBlueprint 是候选方案比较的核心对象。一个章节可同时存在多个 candidate 版本，但只能有一个 selected 主版本进入下一步场景拆解。

---

## 6.12 SceneCard（场景卡）

### 6.12.1 对象定位

SceneCard 是 Writer 生成时的最小结构化执行单元，负责限制场景目标、冲突、人物参与与信息变化。

### 6.12.2 必要字段

- object_id
- object_type = SceneCard
- scene_no：场景序号
- belongs_to_chapter_ref：所属章节蓝图引用
- scene_goal：场景目标
- scene_function：场景功能
- entry_condition：进入条件
- exit_condition：退出条件
- participating_entity_refs：参与实体
- location_ref：地点引用
- conflict_type：冲突类型
- emotional_shift：情绪变化
- information_delta：信息变化
- open_loop_action：伏笔动作
- expected_word_range：预期字数区间
- transition_hint：转场提示
- forbidden_content：禁止内容

---

## 6.13 PacingConstraintCard（节奏约束卡）

### 6.13.1 对象定位

用于明确某一卷、某一章或某一场景的节奏边界，是 Pacing Engine 输出的重要对象。

### 6.13.2 必要字段

- object_id
- object_type = PacingConstraintCard
- scope_type：作用域类型
- scope_ref：作用域引用
- conflict_escalation_level：冲突升级等级
- info_reveal_level：信息揭示等级
- hook_requirement：钩子要求
- action_ratio_hint：行动比例提示
- exposition_ratio_hint：说明比例提示
- emotional_intensity_band：情绪强度带
- relationship_progress_cap：关系推进上限
- deviation_tolerance：偏离容忍度

---

## 6.14 ReviewResultCard（审核结果卡）

### 6.14.1 对象定位

ReviewResultCard 用于承载各类质量闸门输出，必须结构化保存，不能只留一段自然语言评价。

### 6.14.2 必要字段

- object_id
- object_type = ReviewResultCard
- review_type：审核类型
- target_object_ref：被审核对象引用
- target_version：被审核版本
- reviewer_type：审核主体类型
- reviewer_ref：审核主体引用
- pass_status：是否通过
- severity_level：问题严重等级
- issue_list：问题列表
- evidence_refs：证据引用
- fix_suggestions：修订建议
- score_breakdown：评分拆解
- reviewed_at：审核时间
- followup_required：是否需要后续复审

---

## 6.15 ChangeProposalCard（变更提议卡）

### 6.15.1 对象定位

用于承接“从文本/蓝图/人工修改中抽取出来的状态变化提议”，是 ChangeSet 前的上游对象。

### 6.15.2 必要字段

- object_id
- object_type = ChangeProposalCard
- proposal_scope：变更范围
- source_object_ref：来源对象引用
- affected_state_domains：影响状态域
- proposed_operations：拟执行操作列表
- rationale：变更理由
- risk_assessment：风险评估
- approval_required：是否需人工审批
- proposal_status：提议状态
- linked_changeset_ref：关联变更集引用

---

## 7. 对象关系规则

### 7.1 关系类型

对象间关系至少应支持以下类型：

- references：引用
- depends_on：依赖
- derived_from：派生于
- constrains：约束
- reviews：审核
- affects：影响
- resolves：回收/解决
- belongs_to：隶属
- expands_into：拆解为
- canonizes：正史化

### 7.2 关键关系示例

- ChapterBlueprint references CharacterCard / RuleCard / OpenLoopCard
- SceneCard belongs_to ChapterBlueprint
- ReviewResultCard reviews DraftRecord / ChapterBlueprint / SceneCard
- ChangeProposalCard affects CharacterCard / RelationshipEdge / TimelineEventCard
- OpenLoopCard resolves by TimelineEventCard 或 ChapterBlueprint / PublishRecord

### 7.3 强引用与弱引用

建议分两类引用：

#### 强引用
必须存在，否则对象不合法。
例如：
- SceneCard.belongs_to_chapter_ref
- ReviewResultCard.target_object_ref

#### 弱引用
可为空，仅作语义辅助。
例如：
- ChapterBlueprint.selected_reason 中引用的某些候选分析对象

---

## 8. 对象生命周期

### 8.1 通用生命周期

大多数对象应遵循以下生命周期：

1. created
2. draft
3. candidate
4. selected / approved
5. active
6. archived / deprecated / rejected

### 8.2 不同对象的生命周期差异

#### 正史对象
如 CharacterCard / RuleCard / RelationshipEdge：
- draft
- approved
- active
- deprecated

#### 候选规划对象
如 ChapterBlueprint：
- candidate
- selected
- rejected
- archived

#### 审核对象
如 ReviewResultCard：
- created
- issued
- acknowledged
- closed

#### 变更提议对象
如 ChangeProposalCard：
- created
- reviewing
- approved
- rejected
- merged
- abandoned

---

## 9. 对象版本机制

### 9.1 基本要求

所有核心对象必须支持版本化，不允许无痕覆盖。

### 9.2 推荐版本字段

- object_version
- previous_version_ref
- supersedes_ref
- change_summary
- changed_fields
- version_reason

### 9.3 版本策略

建议采用：

- 小修订：object_version + 1
- 重大改写：新版本对象 + supersedes_ref
- 废弃对象：status = deprecated，并记录替代对象引用

### 9.4 发布锁定原则

被发布章节引用过的对象，不得直接静默覆盖其关键字段。若必须修改，应：
- 新建版本
- 形成 ChangeProposal
- 触发受影响对象复核

---

## 10. 校验机制

### 10.1 校验分层

对象必须通过三层校验：

#### 第一层：Schema 校验
检查：
- 必填字段
- 字段类型
- 枚举合法性
- 引用格式

#### 第二层：关系校验
检查：
- 引用对象是否存在
- 父子关系是否成立
- 是否存在循环依赖
- 强引用是否缺失

#### 第三层：语义校验
检查：
- 角色卡是否缺少关键动机字段
- 章蓝图是否缺少章节目标/冲突/钩子设计
- 伏笔卡是否缺少回收窗口或状态
- 审核结果卡是否缺少证据与建议

### 10.2 与质量闸门的关系

对象校验不等于质量闸门。

- 对象校验：检查“对象是否合法、完整、可进入流程”
- 质量闸门：检查“内容是否合格、是否满足目标、是否可发布”

---

## 11. 权限与读写边界

### 11.1 Agent 权限

Agent 可以：
- 生成 candidate 对象
- 更新 draft 对象
- 生成 review 对象
- 生成 proposal 对象

Agent 不可以：
- 直接把对象标记为 canon_active
- 直接改写高优先级正史对象的关键字段
- 绕过审核与审批流程

### 11.2 Workflow 权限

Workflow 服务可以：
- 建立对象间关系
- 推动对象生命周期流转
- 在审批通过后写入 Canon 对象状态
- 触发对象级再校验与派生更新

### 11.3 Human 权限

人类作者/编辑可以：
- 创建对象
- 修改关键字段
- 选择候选对象
- 审批 proposal / changeset
- 废弃对象
- 强制回滚特定对象版本

---

## 12. 存储建议

### 12.1 主存储

结构化创作对象建议存储于关系型数据库或文档数据库中，但必须保证：
- 对象主键唯一
- 版本记录完整
- 引用关系可追踪
- 审批历史可回放

### 12.2 派生索引

以下内容应作为派生索引维护：
- ref_by 反向引用
- 角色关系图视图
- 伏笔待回收列表
- 当前活跃规则集合
- 当前卷/章对象视图

### 12.3 向量化素材

对象的摘要文本、声音样本、风格样本可进入向量索引，但向量索引不能反向作为正史来源。

---

## 13. MVP 范围

V1 MVP 阶段，不追求一次把所有对象全部做完，先定最小闭环对象集。

### 13.1 P0 必做对象

- CharacterCard
- RuleCard
- RelationshipEdge
- OpenLoopCard
- ChapterBlueprint
- SceneCard
- PacingConstraintCard
- ReviewResultCard
- ChangeProposalCard
- TimelineEventCard

### 13.2 P1 可延后对象

- LocationCard
- FactionCard
- TerminologyCard
- ArcCard
- VolumeBlueprint
- HookCard
- DraftRecord
- PublishRecord
- CandidateSet
- SummaryCard

### 13.3 MVP 原则

先确保以下闭环成立：

- 候选章蓝图可生成
- 已选章蓝图可拆场景
- 场景可生成正文
- 正文可产出审核结果
- 审核通过后可形成 ChangeProposal
- ChangeProposal 可映射到 Canon 状态域

只要这个闭环成立，对象层就算真正落地。

---

## 14. 与其他文档的接口关系

### 14.1 对《状态模型设计（V1）》的接口

- CharacterCard / RuleCard / RelationshipEdge / TimelineEventCard / OpenLoopCard 是 Canon State 的关键映射对象
- ChangeProposalCard 是状态写入前的对象级中间层

### 14.2 对《Agent 契约说明（V1）》的接口

- 每个 Agent 的输入输出必须绑定到对象类型，而不是自由文本
- Planner 输出 ChapterBlueprint candidate
- Scene Decomposer 输出 SceneCard 列表
- Reviewer 输出 ReviewResultCard
- Change Extractor 输出 ChangeProposalCard

### 14.3 对《工作流说明（V1）》的接口

- 工作流节点流转基于对象生命周期推进
- 审批节点处理对象状态变更与版本切换

---

## 15. V1 结论

结构化创作对象层不是系统的附属组件，而是多 Agent 创作控制系统的核心基础设施。

V1 正式定版结论如下：

1. 系统必须采用 Schema-first Creative Object 机制。
2. 关键创作资产必须对象化，而不是只保留自由文本。
3. 对象必须支持统一公共协议、引用关系、生命周期、版本机制与校验机制。
4. CharacterCard、RuleCard、RelationshipEdge、OpenLoopCard、ChapterBlueprint、SceneCard、ReviewResultCard、ChangeProposalCard 构成 V1 的最小闭环对象体系。
5. Agent 只能生成或修改候选对象、草稿对象、审核对象与提议对象，不能直接改写 Canon 正史对象。
6. 后续 Agent 契约、工作流、质量闸门、数据库设计都必须以本对象层定义为准，而不能另起一套自由格式。

至此，结构化创作对象层在 V1 中正式定版。
