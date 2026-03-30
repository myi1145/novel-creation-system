# Prompt 设计说明（V1）

## 1. 文档信息

- 文档名称：Prompt 设计说明
- 版本：V1
- 文档定位：实现层设计文档
- 适用范围：小说多 Agent 系统 V1
- 关联文档：
  - 《小说多 Agent 系统最终架构设计文档（V1）》
  - 《Story State / Canon State 状态模型设计（V1）》
  - 《结构化创作对象 Schema 设计（V1）》
  - 《Agent 契约说明（V1）》
  - 《章节循环工作流说明（V1）》
  - 《多层质量闸门设计（V1）》
  - 《题材配置层与规则包设计（V1）》
  - 《字段命名与对象映射总表（V1）》
  - 《API 接口与服务边界说明（V1）》

---

## 2. 文档目标

本文件用于正式定义系统内 Prompt 的设计原则、分层结构、上下文装配方式、约束注入规则、Agent Prompt 骨架、输出格式要求与版本治理方式。

本文件要解决的核心问题不是“怎么把提示词写长”，而是：

- 如何让 Prompt 服务于系统控制，而不是替代系统控制
- 如何让不同 Agent 使用统一的上下文协议与输出协议
- 如何降低长篇创作中的设定漂移、角色漂移、节奏漂移与风格漂移
- 如何让 Prompt 与 Story State、结构化对象层、工作流、质量闸门形成稳定协作
- 如何使 Prompt 可版本化、可审计、可灰度、可替换

---

## 3. Prompt 在系统中的正式定位

### 3.1 Prompt 不是系统中枢

在本系统中，Prompt 的正式定位是：

**受控生成接口层。**

Prompt 负责把：
- 工作流当前节点的任务目标
- Story State 的可读部分
- 结构化创作对象
- 题材配置与规则约束
- 输出协议与失败策略

转译成对大模型友好的输入形式。

Prompt 不负责：
- 替代 Canon State
- 替代对象层 Schema
- 替代 Workflow 决策
- 替代 ChangeSet 审批
- 直接决定系统真相

### 3.2 Prompt 的核心职责

Prompt 在系统中的核心职责只有四类：

1. **任务边界表达**
   - 告诉模型当前在做什么，不在做什么

2. **约束注入**
   - 将来自 Canon、Genre、Rule Pack、Workflow 的限制转为可执行文本约束

3. **输出格式约束**
   - 要求模型生成结构化结果、显式字段、显式风险说明

4. **失败可恢复性增强**
   - 通过显式步骤、显式自检、显式空值策略，降低输出失控概率

---

## 4. Prompt 总体设计原则

### 4.1 状态先于措辞

Prompt 必须依赖 Story State、Canon Snapshot、Creative Objects 与 Workflow 输入。

不能采用“先写一段很强的系统提示，再用自然语言补背景”的做法作为主方案。

### 4.2 结构先于文学修辞

系统 Prompt 的首要目标是：
- 正确
- 可控
- 可解析
- 可比较
- 可复用

而不是首先追求“文案写得很高级”。

### 4.3 分层优于单块巨 Prompt

V1 明确禁止单个超长 Prompt 承担以下全部职责：
- 角色设定说明
- 世界观说明
- 工作流任务
- 风格要求
- 输出格式要求
- 失败容错说明
- 题材规则

正确做法是采用分层拼装。

### 4.4 最小必要上下文原则

不是上下文越长越稳。

每个 Agent 的 Prompt 上下文必须遵循：
- 只给当前任务所需信息
- 只给与当前对象直接相关的信息
- 只给当前章节/场景必要的 Canon 片段
- 只给必要的题材配置与风格片段

### 4.5 Prompt 必须与对象层绑定

Prompt 中出现的“角色”“地点”“规则”“伏笔”“章目标”等内容，原则上都必须来自结构化对象或状态快照，而不是临时手写。

### 4.6 输出优先结构化

除正文生成类 Agent 外，其他 Agent 一律优先输出结构化结果。

正文生成类 Agent 也应采用：
- 元数据字段 + 正文文本
- 或分区块输出

而不能只返回一整坨不可分析文本。

### 4.7 Prompt 必须可版本化

所有正式进入系统的 Prompt 模板必须具备：
- prompt_id
- version
- owner
- target_agent_type
- target_workflow_node
- change_note
- compatible_schema_version

---

## 5. Prompt 分层架构

V1 采用六层 Prompt 结构。

### 5.1 层 1：Meta Instruction 层

用于定义最稳定的基础行为边界。

内容包括：
- 角色定位
- 禁止行为
- 输出真实性约束
- 不得越权写入 Canon
- 不得忽略结构化字段
- 不得擅自发明未授权设定

特点：
- 最稳定
- 复用范围最大
- 变更频率最低

### 5.2 层 2：Agent Role 层

定义该 Agent 的专业职责。

例如：
- Chapter Planner 负责候选章蓝图设计
- Scene Decomposer 负责章蓝图拆成 SceneCard
- Writer 负责按 SceneCard 写出正文
- Canon Reviewer 负责检查与正史冲突项

这一层只回答：
**你是谁、你负责什么、不负责什么。**

### 5.3 层 3：Workflow Task 层

定义当前工作流节点的具体任务。

例如：
- 为第 17 章生成 3 个候选章蓝图
- 为已选章蓝图生成场景拆解
- 对第 17 章草稿做 Canon Gate 审查

这一层只回答：
**这一次具体要做什么。**

### 5.4 层 4：Constraint Injection 层

用于注入来自系统的约束。

包括：
- Canon 事实约束
- 题材配置约束
- Rule Pack 约束
- 章节节奏目标
- 不可触碰事项
- 必须承接事项

这一层是防漂移核心层。

### 5.5 层 5：Context Payload 层

提供当前任务最小必要上下文。

包括：
- 当前 Canon 相关摘要
- 相关对象片段
- 上章摘要
- 当前卷目标
- 当前 open loops
- 人物声音样本
- 当前场景输入

这一层必须严格控长。

### 5.6 层 6：Output Contract 层

定义输出格式、字段、空值策略、自检要求与失败回传方式。

这是保证解析稳定性的关键层。

---

## 6. Prompt 装配模型

### 6.1 标准装配公式

V1 统一采用以下装配模型：

```text
Prompt =
Meta Instruction
+ Agent Role
+ Workflow Task
+ Constraint Injection
+ Context Payload
+ Output Contract
```

### 6.2 装配原则

1. 由系统自动装配，不允许手工自由拼接成为主方案
2. 不同层来自不同配置源
3. 每层必须可单独版本管理
4. 每次调用必须记录实际装配结果摘要
5. 必须能追踪某次输出使用了哪一版 Prompt 组件

### 6.3 Prompt 组件来源

| 层级 | 来源 |
|---|---|
| Meta Instruction | 平台全局模板 |
| Agent Role | Agent 类型模板 |
| Workflow Task | 工作流节点模板 |
| Constraint Injection | Canon / Genre / Rule Pack / Pacing / Gate |
| Context Payload | 上下文装配服务 |
| Output Contract | Schema / Parser / Node Contract |

---

## 7. 上下文装配设计

### 7.1 上下文来源分类

Prompt 的上下文来源分为五类：

1. **State Context**
   - Canon Snapshot
   - 当前章节元数据
   - 当前卷状态
   - open loops 状态

2. **Object Context**
   - 角色卡
   - 规则卡
   - 章蓝图
   - 场景卡
   - 关系边

3. **Genre Context**
   - Genre Profile
   - 风格配置
   - 节奏模板
   - 禁忌项

4. **Memory Context**
   - 最近章节摘要
   - 相关历史片段摘要
   - 人物声音样本

5. **Execution Context**
   - 当前 workflow node
   - 当前任务 ID
   - 输出 schema
   - 重试策略

### 7.2 上下文选择原则

#### Planner Agent
重点读取：
- 当前卷目标
- 当前章位次
- 未关闭 open loops
- 关键角色状态
- 节奏目标

不应读取：
- 大量原文全文
- 无关人物的全部细节

#### Scene Decomposer Agent
重点读取：
- 已选 ChapterBlueprint
- 关键角色卡
- 关键地点卡
- 相关规则卡

#### Writer Agent
重点读取：
- 已选 SceneCard 序列
- 角色卡摘要
- 最近章节摘要
- 当前卷目标摘要
- 必要风格片段

不应直接读取：
- 整个项目所有人物卡全文
- 全部世界观文档全文

#### Review Agents
重点读取：
- 待审文本
- 对应对象版本
- 审核目标对应的 Canon 片段
- 审核规则与 gate contract

### 7.3 上下文摘要策略

V1 推荐采用以下策略：

- Canon 不直接全量注入，而是按对象关系裁切
- 历史章节不直接全文注入，而是使用章节摘要 + 片段引用
- 角色卡注入时优先提供“当前相关字段摘要”而不是完整卡
- 风格样本只给少量高代表性样本
- Prompt 中引用的对象应带 object_id / version 便于追踪

---

## 8. 约束注入设计

约束注入是 Prompt 设计中最重要的一层。

### 8.1 约束来源

约束可来自：
- Canon Snapshot
- Creative Objects
- Genre Profile
- Rule Pack
- Pacing Engine
- Workflow Node Contract
- Quality Gate Contract

### 8.2 约束类型

V1 将约束分为六类。

#### 1）事实约束
示例：
- 角色当前境界为“筑基中期”，不得写成金丹
- A 与 B 尚未公开结盟
- 某地点当前不可进入

#### 2）叙事约束
示例：
- 本章必须推进支线 X
- 本章不可提前揭示谜底 Y
- 本章必须回收提醒型伏笔 Z

#### 3）人物约束
示例：
- 某角色不应主动说出过于外露的情感表达
- 某角色当前与主角仍在试探阶段

#### 4）风格约束
示例：
- 修仙题材不得大量使用现代职场术语
- 校园题材对白应贴近日常语感

#### 5）输出约束
示例：
- 必须返回 3 个候选方案
- 每个方案必须包含 risk_points
- 为空时必须返回空数组而不是省略字段

#### 6）安全与越权约束
示例：
- 不得擅自引入新的核心设定
- 不得将候选内容写成既定 Canon

### 8.3 约束优先级

V1 统一采用以下优先级：

1. 系统硬约束
2. Canon 事实约束
3. Workflow 任务约束
4. Genre / Rule Pack 约束
5. 风格增强约束
6. 表达优化建议

若存在冲突，必须按优先级降级处理，不得为了语言华丽而违背正史与任务边界。

---

## 9. Prompt 模板体系

### 9.1 模板分类

V1 将 Prompt 模板分为以下五类。

#### A. 基础模板
- global_meta_instruction
- global_output_contract
- global_failure_policy

#### B. Agent 角色模板
- planner_role
- scene_decomposer_role
- writer_role
- canon_reviewer_role
- narrative_reviewer_role
- style_reviewer_role
- summarizer_role
- change_proposal_role

#### C. Workflow 节点模板
- generate_chapter_candidates_task
- decompose_scenes_task
- write_scene_draft_task
- canon_gate_task
- style_gate_task
- summarize_chapter_task
- propose_changeset_task

#### D. 题材模板
- xiuxian_style_pack
- urban_style_pack
- campus_style_pack
- entertainment_style_pack
- suspense_style_pack

#### E. Gate / Parser 配套模板
- schema_output_contract
- reviewer_output_contract
- error_recovery_prompt
- reask_prompt

### 9.2 模板命名规范

统一命名建议：

```text
{layer}.{agent_or_domain}.{purpose}.{version}
```

示例：
- role.writer.base.v1
- task.chapter_planner.generate_candidates.v1
- genre.xiuxian.style_pack.v1
- contract.review.canon_output.v1

---

## 10. 各类 Agent Prompt 设计要点

### 10.1 Chapter Planner Agent

目标：
- 生成 3~5 个 ChapterBlueprint 候选

重点：
- 明确章级推进目标
- 显式说明每个候选使用了哪些 Canon 事实
- 显式说明风险点
- 明确不可提前揭示内容

禁止：
- 直接生成正文
- 擅自引入重大设定

### 10.2 Scene Decomposer Agent

目标：
- 将 ChapterBlueprint 拆解为 SceneCard 列表

重点：
- 每个场景必须有功能定位
- 每个场景必须说明情绪曲线和信息增量
- 场景之间必须可形成过渡

禁止：
- 把场景拆成只有“聊天”而无叙事功能的流水片段

### 10.3 Writer Agent

目标：
- 根据 SceneCard 生成正文草稿

重点：
- 以场景为单位推进
- 保持人物语气与视角稳定
- 保持题材语体一致
- 不自动升格候选内容为 Canon 事实

输出建议：
- draft_metadata
- scene_texts
- chapter_full_text
- self_risks

### 10.4 Canon Review Agent

目标：
- 找出与 Canon 冲突的地方

重点：
- 只报告基于证据的冲突
- 明确 object_ref / state_ref
- 输出严重度等级与修订建议

禁止：
- 以个人审美否定文本

### 10.5 Narrative Review Agent

目标：
- 评估章级推进质量

重点：
- 是否完成蓝图目标
- 是否有结构断裂
- 是否节奏失衡
- 是否信息堆砌

### 10.6 Style Review Agent

目标：
- 检查语言风格与题材语体是否稳定

重点：
- 重复表达
- 语体偏差
- 出戏词汇
- 不合题材用语

### 10.7 Summarizer Agent

目标：
- 生成章节摘要、状态摘要、上下文摘要

重点：
- 摘要必须忠实于文本与对象
- 不得加入未发生事实
- 要适合进入后续 Prompt Context

### 10.8 Change Proposal Agent

目标：
- 从已通过审核的章节中抽取可能进入 Canon 的状态变化

重点：
- 区分“明确发生”与“可能暗示”
- 仅输出变更提议，不做直接写入

---

## 11. 输出协议设计

### 11.1 总体原则

Prompt 必须和输出协议绑定设计。

输出协议优先级高于文案自然度。

### 11.2 标准输出区块

V1 推荐大多数 Prompt 输出使用以下区块：

- meta
- result
- risks
- self_check
- errors

### 11.3 正文类输出建议

Writer Agent 推荐输出结构：

```json
{
  "meta": {
    "agent_type": "writer",
    "task_id": "...",
    "chapter_id": "..."
  },
  "result": {
    "scene_texts": [],
    "chapter_full_text": "..."
  },
  "risks": [],
  "self_check": {
    "canon_risk": "low",
    "voice_risk": "medium",
    "style_risk": "low"
  },
  "errors": []
}
```

### 11.4 审核类输出建议

Review Agent 推荐输出结构：

```json
{
  "meta": {...},
  "result": {
    "gate_pass": false,
    "issues": [
      {
        "issue_code": "CANON_CONFLICT",
        "severity": "S2",
        "evidence": "...",
        "related_refs": [],
        "repair_suggestion": "..."
      }
    ]
  },
  "risks": [],
  "self_check": {...},
  "errors": []
}
```

### 11.5 空值与失败策略

必须统一：
- 无结果时返回空数组或 null，不得漏字段
- 解析失败时返回 errors，不得伪造成功结果
- 不确定项要显式标 uncertain

---

## 12. 防漂移策略

### 12.1 角色漂移防控

方法：
- 只注入当前相关角色摘要
- 注入关系阶段
- 注入典型语气样本
- 在 Prompt 中显式列出“不可违背的人物约束”

### 12.2 世界观漂移防控

方法：
- 注入相关 RuleCard 摘要
- 注入关键 TerminologyCard
- 显式声明禁止新造核心规则

### 12.3 节奏漂移防控

方法：
- 注入 chapter_goal
- 注入 pacing targets
- 注入“本章必须推进 / 不得提前”列表

### 12.4 风格漂移防控

方法：
- 题材 Style Pack 分离管理
- 风格样本少量高质量注入
- 用词禁忌清单显式注入

---

## 13. Re-ask 与修订 Prompt 策略

### 13.1 不直接在原 Prompt 上无限追加

当输出不合格时，禁止简单采用：
- 再来一次
- 再认真一点
- 再检查一下

这类低信息量重复追加。

### 13.2 标准修订方式

应采用：
- 保留原任务目标
- 明确失败点
- 明确需要修复的 issue list
- 尽量缩小重生成范围

### 13.3 修订 Prompt 输入内容

修订 Prompt 至少应包含：
- 原输出摘要
- issue 列表
- 不需要重写的内容范围
- 需要重点修复的对象约束

---

## 14. Prompt 版本治理

### 14.1 版本对象

每个正式 Prompt 组件必须登记：
- prompt_component_id
- component_type
- target_agent_type
- target_node
- version
- status
- owner
- content_hash
- created_at
- updated_at
- change_note

### 14.2 版本策略

建议采用：
- 大版本：结构协议变化
- 小版本：约束增强、表达优化、容错增强
- 热修订：明显错误修复

### 14.3 兼容性要求

Prompt 版本必须声明兼容：
- schema_version
- parser_version
- agent_contract_version
- workflow_version

---

## 15. Prompt 质量评估指标

V1 阶段建议重点观察以下指标：

1. 结构化解析成功率
2. 字段缺失率
3. 重试率
4. 审核失败率
5. 修订后通过率
6. Canon 冲突率
7. 风格偏移率
8. 平均上下文长度
9. 平均响应成本
10. 人工二次修改率

---

## 16. Prompt 存储与运行建议

### 16.1 存储建议

正式 Prompt 组件建议存储为：
- 数据库元数据 + 文件内容
- 或数据库 + Git 双登记

### 16.2 运行建议

运行时应记录：
- 调用所用 Prompt 组件版本
- 实际装配片段 hash
- 上下文对象引用清单
- 输出 schema 版本
- 解析结果
- 是否进入 re-ask

### 16.3 安全建议

- 不允许运行时任意拼接未审核模板作为正式生产模板
- Prompt 改动应能灰度发布
- 高风险 Agent 的 Prompt 变更需人工审核

---

## 17. MVP 范围

### 17.1 MVP 必做 Prompt 组件

至少包括：
- 全局 Meta Instruction
- Planner Role Prompt
- Scene Decomposer Role Prompt
- Writer Role Prompt
- Canon Review Role Prompt
- Style Review Role Prompt
- Summarizer Role Prompt
- Change Proposal Role Prompt
- Chapter Candidate Task Prompt
- Scene Decompose Task Prompt
- Chapter Draft Task Prompt
- Canon Gate Task Prompt
- Style Gate Task Prompt
- 统一输出 Contract
- 统一 Re-ask Prompt
- 修仙题材 Style Pack

### 17.2 可延后内容

- 多语言 Prompt
- Prompt 自动优化系统
- Prompt A/B 自动实验平台
- 更复杂的少样本示例库
- 多模型差异化 Prompt 编译

---

## 18. 关键风险与控制

### 风险一：Prompt 继续变成系统主体
控制：
- 保持状态中枢、对象层、工作流优先

### 风险二：上下文失控导致成本和漂移上升
控制：
- 最小必要上下文
- 摘要化注入
- 对象裁切

### 风险三：输出看似自然但不可解析
控制：
- 输出 Contract 前置
- Parser 驱动 Prompt 设计

### 风险四：不同 Agent 各写各的 Prompt，失去统一性
控制：
- Prompt 组件化
- 统一命名与版本治理

### 风险五：修订机制退化成反复重跑
控制：
- issue 驱动 re-ask
- 局部修订优先

---

## 19. V1 结论

V1 阶段，Prompt 的正式设计路线确定为：

**组件化、分层化、对象绑定化、约束注入化、输出协议化、版本治理化。**

系统不再采用“大一统巨 Prompt”作为主方案，而是采用：
- Meta Instruction
- Agent Role
- Workflow Task
- Constraint Injection
- Context Payload
- Output Contract

构成的分层 Prompt 架构。

该路线的核心目标不是“让模型自由发挥”，而是：
- 在可控边界内生成
- 在最小必要上下文内生成
- 在结构化协议下生成
- 在失败可恢复机制下生成
- 在 Story State 与 Workflow 主导下生成

