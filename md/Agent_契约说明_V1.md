# Agent 契约说明（V1）

## 1. 文档信息

- 文档名称：Agent 契约说明
- 版本：V1
- 文档定位：正式定版稿
- 关联文档：
  - 《小说多 Agent 系统最终架构设计文档（V1）》
  - 《Story State / Canon State 状态模型设计（V1）》
  - 《结构化创作对象 Schema 设计（V1）》
- 文档目标：明确系统内各类 Agent 的职责边界、输入输出协议、读写权限、禁止行为、执行规则与失败处理机制，防止 Agent 失控、越权、重复建设与职责重叠。

---

## 2. 文档定位

本文件不是 Prompt 集合，也不是“让 Agent 怎么写得更好”的技巧文档。

本文件的正式定位是：

**系统级 Agent 执行契约文档。**

它解决的是以下问题：

- 系统里需要哪些 Agent
- 每个 Agent 到底负责什么，不负责什么
- 每个 Agent 允许读取哪些状态与对象
- 每个 Agent 允许输出什么结构
- 哪些 Agent 可以提出变更，哪些绝不能直接改 Canon
- Agent 之间如何协作，而不是互相覆盖
- 当 Agent 输出异常、漂移、越权、冲突时如何处理

因此，本文件的核心原则不是“给 Agent 更多自由”，而是：

**让 Agent 成为流程中的受控执行者。**

---

## 3. Agent 体系总原则

### 3.1 Agent 是执行者，不是中枢

系统的中枢是：

- Workflow / Orchestrator
- Story State / Canon State
- Creative Objects
- Quality Gates
- ChangeSet 审批机制

Agent 只在需要生成、推断、评审、归纳的环节承担执行任务。

Agent 不得承担以下中枢职责：

- 直接决定正史事实
- 直接写入 Canon Snapshot
- 直接发布章节
- 绕过审批修改对象
- 同时兼任生成者与唯一审批者

### 3.2 先有协议，再有 Prompt

Agent 必须先定义：

- 输入对象
- 输出对象
- 权限边界
- 错误码与失败状态
- 上下文来源
- 与工作流节点的关系

之后才能设计 Prompt。

任何没有协议约束、只靠自然语言要求运行的 Agent，都不视为正式系统 Agent。

### 3.3 Agent 输出必须结构化

正式 Agent 的输出必须可被程序解析、校验、审查与回放。

允许的输出形式包括：

- 严格 JSON
- 结构化 Markdown
- 指定 Schema 对象
- 带状态码的结果对象

不允许仅输出大段自由文本，再由下游“猜测”其含义。

### 3.4 Agent 默认无写权限

除非有明确规定，否则 Agent 默认只有：

- 读取权限
- 候选输出权限
- 建议权限
- 评审意见权限

Agent 默认没有：

- Canon 写权限
- 已发布对象覆盖权限
- 审批权限
- 发布权限

### 3.5 Agent 输出不等于真相

Agent 的所有输出在进入 Canon 之前，都只能视为：

- 候选方案
- 工作态对象
- 变更建议
- 评审意见

只有被 Workflow 接收、被 Gate 审核、被 Human 或规则审批、并通过 ChangeSet Apply 后，内容才可以成为正史的一部分。

---

## 4. Agent 分层

V1 将 Agent 分为五类：

### 4.1 规划类 Agent

职责：负责卷级、章级、弧光级规划与候选方案生成。

代表 Agent：
- Volume Planner Agent
- Chapter Planner Agent
- Arc Mapper Agent
- Open Loop Planner Agent

### 4.2 拆解类 Agent

职责：将较大的叙事结构拆成可执行、可写作、可校验的细粒度对象。

代表 Agent：
- Scene Decomposer Agent
- Beat Planner Agent
- Scene Transition Agent

### 4.3 生成类 Agent

职责：负责正文草稿、局部重写、对白增强、文本修饰。

代表 Agent：
- Writer Agent
- Rewriter Agent
- Dialogue Enhancer Agent

### 4.4 审阅类 Agent

职责：对候选内容、草稿、对象、变更提议进行结构化评审。

代表 Agent：
- Canon Review Agent
- Narrative Review Agent
- Voice Review Agent
- Style Review Agent
- Pacing Review Agent

### 4.5 状态辅助类 Agent

职责：负责摘要、提取、变更建议、对象补全等辅助工作。

代表 Agent：
- Summarizer Agent
- Metadata Extractor Agent
- Change Proposal Agent
- Object Normalizer Agent

---

## 5. Agent 生命周期与调用时机

### 5.1 Agent 不常驻自治运行

V1 不采用“Agent 自主对话、自主拉群、自主协商”的默认机制。

所有正式 Agent 均由 Workflow 节点显式触发。

即：

- 谁触发 Agent，由工作流定义
- 给 Agent 什么上下文，由编排层决定
- Agent 的结果流向哪里，由契约定义
- Agent 失败后如何处理，由流程控制

### 5.2 标准调用生命周期

每次 Agent 调用，统一遵循以下生命周期：

1. 准备输入上下文
2. 组装 Agent 输入对象
3. 触发 Agent 执行
4. 获取结构化输出
5. 执行 Schema 校验
6. 执行权限与字段边界检查
7. 写入工作态对象或评审结果对象
8. 决定是否进入下一节点

### 5.3 禁止 Agent 链式失控调用

Agent 不允许自行无限调用其他 Agent。

V1 只允许两种协作方式：

1. **Workflow 显式串联**
   - 例如：Chapter Planner -> Scene Decomposer -> Writer -> Reviewers

2. **受限委托调用**
   - 某些 Agent 可以请求下游辅助能力，但必须通过 Orchestrator 代为执行
   - 原 Agent 不得直接持有其他 Agent 的调用权限

---

## 6. 统一输入输出协议

## 6.1 统一输入对象：AgentTask

所有正式 Agent 接收的任务对象，至少应包含以下字段：

```json
{
  "task_id": "string",
  "task_type": "string",
  "project_id": "string",
  "novel_id": "string",
  "workflow_run_id": "string",
  "node_id": "string",
  "agent_name": "string",
  "objective": "string",
  "constraints": [],
  "input_refs": [],
  "context_bundle": {},
  "output_schema": "string",
  "permission_scope": {},
  "retry_index": 0,
  "trace_id": "string"
}
```

### 6.2 统一输出对象：AgentResult

所有正式 Agent 输出至少包含：

```json
{
  "task_id": "string",
  "agent_name": "string",
  "status": "success | partial_success | fail | needs_human_review",
  "summary": "string",
  "outputs": {},
  "risks": [],
  "violations": [],
  "confidence": 0.0,
  "suggested_next_action": "string",
  "trace": {}
}
```

### 6.3 状态码说明

- `success`：成功完成既定任务，输出可进入下游节点
- `partial_success`：完成部分任务，但有字段缺失或局部风险
- `fail`：未完成任务，输出不得直接进入下游关键节点
- `needs_human_review`：结果可用，但必须人工复核后才能继续

---

## 7. 权限模型

### 7.1 权限分类

Agent 权限按四类定义：

#### 1）读权限（read）
允许读取：
- Canon Snapshot 指定子域
- Working State 指定对象
- Creative Objects 指定版本
- 审阅报告
- 最近章节摘要
- 题材模板配置

#### 2）候选输出权限（propose）
允许输出：
- 候选蓝图
- 候选场景
- 正文草稿
- 审阅意见
- 变更建议
- 元数据提取结果

#### 3）工作态写入权限（write_working）
允许由 Orchestrator 代表 Agent 写入工作态对象，例如：
- CandidateChapterBlueprint
- SceneDraftSet
- ReviewResultCard
- ChangeProposalCard

注意：这不是 Agent 直接数据库写权限。

#### 4）审批/发布权限（approve / publish）
V1 默认只授予 Human 或特定 Workflow 规则服务。

Agent 默认无此权限。

### 7.2 严格禁止的权限

以下权限 V1 禁止任何普通 Agent 持有：

- 直接写 Canon Snapshot
- 删除 Immutable Log
- 修改已发布章节正文
- 修改已发布对象的历史版本
- 自行批准自己的 ChangeSet
- 跳过 Gate 直接进入发布状态

### 7.3 最小权限原则

每个 Agent 只能获得完成当前任务所需的最小权限。

例如：
- Writer Agent 无需读取全量世界状态，只需读取与本章有关的角色卡、规则卡、章蓝图、场景卡、最近摘要
- Style Review Agent 无需获得 ChangeSet 审批权限
- Metadata Extractor Agent 无需获得卷级规划对象的写权限

---

## 8. 核心 Agent 契约

## 8.1 Chapter Planner Agent

### 定位
负责在给定卷目标、章节位次、当前 Canon 状态和节奏约束下，生成多个候选章蓝图。

### 输入
- 当前 Canon Snapshot 的相关子集
- 当前 VolumeBlueprint
- 最近 1~3 章摘要
- 未回收 OpenLoopCard 集合
- PacingConstraintCard
- 题材配置
- 作者额外指令（可选）

### 输出
- 3~7 个 CandidateChapterBlueprint
- 每个候选的推进摘要
- 风险点
- 推荐理由

### 允许读取
- CharacterCard（相关角色）
- RelationshipEdge（相关边）
- RuleCard（相关规则）
- TimelineEvent（最近相关事件）
- OpenLoopCard（相关伏笔）
- 当前卷蓝图

### 禁止行为
- 直接生成正文
- 直接改写 CharacterCard
- 直接关闭 OpenLoop
- 将某候选自动标记为已确认正稿

### 成功标准
- 候选蓝图格式正确
- 至少覆盖本章主推进目标
- 不出现明显 Canon 冲突
- 每个候选具备差异性

---

## 8.2 Scene Decomposer Agent

### 定位
将已选定章蓝图拆解为可执行的场景序列。

### 输入
- FinalChapterBlueprint
- 相关 CharacterCard
- 相关 LocationCard
- 相关 OpenLoopCard
- PacingConstraintCard

### 输出
- SceneCard 列表
- 场景顺序与转场说明
- 每个场景的目标、冲突、信息增量、情绪曲线

### 禁止行为
- 不得自行新增章级主目标
- 不得在未声明的前提下引入重大新设定
- 不得直接输出最终正文章节

### 成功标准
- 场景顺序清晰
- 每个场景有明确功能
- 章蓝图目标被完整覆盖
- 信息揭示与冲突升级符合节奏约束

---

## 8.3 Writer Agent

### 定位
基于已确认的章蓝图与场景卡生成正文章节草稿。

### 输入
- FinalChapterBlueprint
- SceneCard 列表
- 相关 CharacterCard
- 相关 RuleCard
- 相关 LocationCard
- 最近章节摘要
- 风格约束
- 题材配置

### 输出
- ChapterDraft
- 可选的 SceneDraft 分段结果
- 自检备注（可选）

### 禁止行为
- 不得跳过场景卡另起炉灶重写主线
- 不得主动创造与 Canon 冲突的核心事实
- 不得直接把文本中的新事实写入 Canon
- 不得替代 Reviewer 作出“通过”判断

### 成功标准
- 草稿完整覆盖章蓝图核心目标
- 角色声音基本稳定
- 结构不塌
- 可进入 Review 阶段

### 特殊说明
Writer Agent 产物默认为：

**工作态文本对象，不是已发布章节。**

---

## 8.4 Rewriter Agent

### 定位
在不改变既定结构目标的前提下，对正文进行局部或整体修订。

### 输入
- 原始 ChapterDraft
- 对应 ReviewResultCard
- 修订约束
- 不可改动项

### 输出
- RevisedChapterDraft
- 修订说明
- 受影响片段范围

### 禁止行为
- 借修订之名重做剧情规划
- 随意删除关键伏笔
- 修改既定主冲突走向

### 成功标准
- 明确响应审阅意见
- 保持原章蓝图目标不变
- 改动范围可追踪

---

## 8.5 Canon Review Agent

### 定位
检查候选内容与 Canon State 是否冲突。

### 输入
- ChapterDraft 或 CandidateChapterBlueprint
- Canon Snapshot 子集
- 相关 Creative Objects

### 输出
- ReviewResultCard
- 冲突项清单
- 冲突等级
- 建议修复方式

### 禁止行为
- 直接修改正文
- 直接批准 ChangeSet
- 直接变更 Canon Snapshot

### 成功标准
- 冲突判断具备引用依据
- 输出结构清晰
- 可被下游修订或人工复核使用

---

## 8.6 Narrative Review Agent

### 定位
检查本章是否完成既定叙事推进与结构目标。

### 输入
- ChapterBlueprint
- SceneCard 列表
- ChapterDraft

### 输出
- 推进完成度
- 场景有效性评估
- 节点缺失/冗余报告
- 修订建议

### 禁止行为
- 用个人偏好替代蓝图目标
- 越权要求改动 Canon 事实

---

## 8.7 Voice Review Agent

### 定位
检查人物声音、说话方式、行为逻辑与当前角色状态是否一致。

### 输入
- CharacterCard
- RelationshipEdge
- 历史声音样本
- ChapterDraft

### 输出
- 人物偏移清单
- 语气偏差说明
- 行为不合理点
- 修订建议

### 禁止行为
- 擅自重定义角色设定
- 仅凭风格偏好要求大改剧情

---

## 8.8 Style Review Agent

### 定位
检查文风稳定性、语言重复、题材语体适配度与文本可读性。

### 输入
- 题材风格配置
- 历史风格样本
- ChapterDraft

### 输出
- 风格偏差报告
- 重复表达报告
- 语体不匹配项
- 修订建议

### 禁止行为
- 因风格喜好否定正确的叙事推进
- 越权要求修改 Canon 对象

---

## 8.9 Summarizer Agent

### 定位
对章节、卷、对象集合进行结构化摘要，为后续生成与检索提供压缩上下文。

### 输入
- ChapterDraft 或 PublishedChapter
- 相关对象

### 输出
- ChapterSummary
- StateDeltaSummary
- RetrievalSummary

### 禁止行为
- 在摘要中新增原文没有的关键事实
- 用推测替代确定事实而不标注

---

## 8.10 Change Proposal Agent

### 定位
从通过审阅的章节或对象变更中提取状态变化，形成 ChangeSet 草案。

### 输入
- ApprovedDraft
- ReviewResultCard
- 当前 Canon Snapshot
- 相关对象引用

### 输出
- ChangeProposalCard
- 拟更新对象列表
- 拟关闭/新增伏笔
- 拟新增时间线事件

### 禁止行为
- 直接 Apply 变更
- 擅自跳过人工审批
- 覆盖现有 Canon 历史

### 特殊说明
Change Proposal Agent 可以“提出正史变化”，但不能“决定正史变化”。

---

## 9. Agent 与 Workflow 的协作契约

### 9.1 协作主线

V1 标准章节流程中的 Agent 协作顺序为：

1. Chapter Planner Agent
2. Human Select / Workflow Filter
3. Scene Decomposer Agent
4. Writer Agent
5. Canon Review Agent
6. Narrative Review Agent
7. Voice Review Agent
8. Style Review Agent
9. Rewriter Agent（如需要）
10. Summarizer Agent
11. Change Proposal Agent
12. Human / Rule Approval

### 9.2 谁决定进入下一步

不是 Agent 自己决定下一步。

进入下一步的决策方必须是：
- Workflow 编排层
- Human 审批人
- 规则服务

### 9.3 Agent 之间的交付物形式

Agent 之间不直接交换自由文本。

正式交付物必须是：
- CandidateChapterBlueprint
- SceneCardSet
- ChapterDraft
- ReviewResultCard
- ChangeProposalCard
- ChapterSummary

---

## 10. Prompt 与上下文治理原则

### 10.1 Prompt 不是契约本身

Prompt 可以变化，契约不能频繁漂移。

应当把：
- 权限
- 输入输出字段
- 角色职责
- 成功标准
- 禁止行为

放在系统契约层，而不是仅放在 Prompt 文本里。

### 10.2 上下文最小充分原则

每个 Agent 只拿当前任务需要的上下文。

禁止粗暴地把：
- 全书正文
- 全部人物卡
- 全部世界观
- 全部日志

一股脑塞给所有 Agent。

### 10.3 上下文必须来源可追踪

每次 Agent 调用所使用的上下文，必须在 trace 中记录来源：

- 引用了哪些对象
- 引用了哪些版本
- 引用了哪个 Canon Snapshot
- 引用了哪个风格样本

这样才能做问题复盘与结果审计。

---

## 11. 失败处理与容错策略

### 11.1 常见失败类型

#### 1）Schema 失败
表现：
- 缺字段
- 类型错误
- 枚举值非法

处理：
- 直接判定为 fail 或 partial_success
- 不进入关键下游节点
- 可触发一次结构化重试

#### 2）越权输出
表现：
- Writer 试图写 CanonPatch
- Reviewer 试图批准 ChangeSet

处理：
- 丢弃越权字段
- 记录 violation
- 必要时中断流程

#### 3）内容漂移
表现：
- 不按章蓝图写
- 忽略关键场景目标
- 人物行为明显跑偏

处理：
- 进入 Review 报告
- 触发 Rewriter 或人工修订

#### 4）高不确定性
表现：
- 输出含大量猜测
- 自信度过低
- 多处“可能/也许/不确定”

处理：
- 输出 needs_human_review
- 不自动推进关键流程

### 11.2 重试原则

V1 建议：
- 同一 Agent 同一任务最多重试 1~2 次
- 重试必须记录 retry_index
- 重试前允许缩小任务范围或补充约束
- 禁止无上限“抽卡式重试”

---

## 12. 可观测性与审计要求

每次 Agent 执行至少记录：

- task_id
- workflow_run_id
- agent_name
- 输入对象引用
- 输入对象版本
- 输出状态
- violations
- confidence
- 执行时间
- token/成本统计（可选）
- 是否进入下游节点

这样可以支持：
- 问题排查
- 质量复盘
- 成本分析
- Prompt 优化
- Agent 绩效评估

---

## 13. V1 必备 Agent 集合

MVP 阶段不需要把所有 Agent 一次做全。

V1 建议最小闭环 Agent 集合为：

1. Chapter Planner Agent
2. Scene Decomposer Agent
3. Writer Agent
4. Canon Review Agent
5. Style Review Agent
6. Summarizer Agent
7. Change Proposal Agent

### 延后实现的 Agent

以下可在 V1.1 / V2 再补：
- Volume Planner Agent
- Arc Mapper Agent
- Narrative Review Agent
- Voice Review Agent
- Rewriter Agent
- Dialogue Enhancer Agent
- Pacing Review Agent

---

## 14. V1 定版结论

本系统采用的 Agent 契约路线为：

**以 Workflow 驱动为主，以对象协议为载体，以最小权限为边界，以结构化输入输出为标准，以 ChangeSet 与审批机制阻断越权写入。**

因此，V1 中 Agent 的本质定位不是“自由创作角色”，而是：

- 规划器
- 拆解器
- 写作器
- 审阅器
- 提议器
- 摘要器

它们都必须服从以下事实：

1. Agent 输出不是正史
2. Agent 默认无 Canon 写权限
3. Agent 只能在工作流节点中被受控调用
4. Agent 必须输出结构化对象
5. Agent 的所有行为都应可追踪、可校验、可复盘

只有在这个前提下，多 Agent 系统才不会退化成“多个 Prompt 彼此干扰”的伪架构。

---

## 15. 后续配套文档

本文件定版后，建议继续补齐：

1. 《章节循环工作流说明（V1）》
2. 《多层质量闸门设计（V1）》
3. 《Prompt 设计说明（V1）》
4. 《结构化输出解析与容错规范（V1）》
5. 《日志与调试规范（V1）》
6. 《MVP 开发任务拆解（V1）》
