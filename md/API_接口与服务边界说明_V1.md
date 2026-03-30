# API 接口与服务边界说明（V1）

## 1. 文档信息

- 文档名称：API 接口与服务边界说明
- 版本：V1
- 文档定位：实现层定版文档
- 适用范围：小说多 Agent 创作控制系统 MVP 与 V1 阶段后端接口、服务拆分、工作流调用边界设计
- 关联上位文档：
  - 《小说多 Agent 系统最终架构设计文档（V1）》
  - 《Story State / Canon State 状态模型设计（V1）》
  - 《结构化创作对象 Schema 设计（V1）》
  - 《Agent 契约说明（V1）》
  - 《章节循环工作流说明（V1）》
  - 《多层质量闸门设计（V1）》
  - 《数据库与存储设计（V1）》
  - 《字段命名与对象映射总表（V1）》

---

## 2. 文档目标

本文件用于将前述架构文档中的“对象、状态、工作流、Agent、质量闸门、ChangeSet、题材配置”等抽象设计，统一翻译为：

1. **服务边界**
2. **领域职责**
3. **对外 API 资源模型**
4. **内部工作流调用关系**
5. **跨模块禁区**
6. **MVP 接口范围**

本文件要解决的核心问题不是“接口怎么命名”这么简单，而是明确：

- 哪些能力应该是独立服务
- 哪些数据应该通过服务访问而不是直接跨表读取
- 哪些动作必须经过 Workflow 编排
- 哪些写操作必须走 ChangeSet
- Agent 调用后端时到底能读什么、写什么、不能做什么

---

## 3. 总体原则

## 3.1 服务优先于表直连

系统对外暴露的是**业务服务能力**，而不是数据库表的直接映射。  
控制台、Workflow、Agent 适配层均不允许以“直接拼 SQL / 直接跨仓储修改表”为默认模式。

## 3.2 Canon 写入必须收口

任何会改变 Canon Snapshot 的写操作，都必须通过：

**ChangeSet Service → Review / Approval → Canon Apply Service**

不得通过对象服务、章节服务、Agent 服务绕过。

## 3.3 Workflow 是动作编排中心

章节循环、发布、修订、回滚、题材初始化等流程性动作，不应由前端串多个接口临时拼装，而应由 Workflow Service 负责有状态编排。

## 3.4 对象服务不负责“解释故事”

对象服务负责 CRUD、版本、引用、状态标签、校验，不负责叙事推理。  
故事推进逻辑归 Workflow、Planner、Pacing、Review 等领域能力。

## 3.5 API 分为三层

V1 将接口划分为三类：

1. **控制台公开接口（External API）**
2. **工作流内部服务接口（Internal Service API）**
3. **Agent 适配接口（Agent Gateway API）**

三者职责不同，不能混用。

## 3.6 先稳定，再扩展

V1 先保证：
- 项目初始化
- 题材装载
- 对象层访问
- 状态读取
- 章节八步循环
- ChangeSet 审批与发布
- 基础审计与回滚

不优先追求：
- 平台级开放 API
- 批量外部集成
- 多租户复杂权限
- 第三方插件开放网关

---

## 4. 服务域划分

V1 推荐按“领域服务”而不是“技术层服务”拆分。

### 4.1 Project Service（项目服务）

负责：
- 项目创建
- 项目配置读取与更新
- 当前题材绑定
- 项目生命周期状态
- 当前卷、当前章进度摘要
- 项目级初始化任务入口

不负责：
- 直接管理章节正文
- 直接修改 Canon
- 直接执行写作流程

### 4.2 Genre Service（题材配置服务）

负责：
- Genre Profile 读取
- Rule Pack 装载
- Resolved Genre Config 生成
- 题材模板版本管理
- 项目与题材绑定关系

不负责：
- 章节生成
- 对象 CRUD
- Canon 写入

### 4.3 Canon Service（正史状态服务）

负责：
- Canon Snapshot 读取
- Canon 域级查询
- Canon 快照版本读取
- Canon 派生摘要生成入口
- Canon 只读视图聚合

不负责：
- 直接写入 Canon
- 跳过 ChangeSet 修改正史

### 4.4 ChangeSet Service（变更集服务）

负责：
- 创建 ChangeSet
- 校验 ChangeSet 基本合法性
- 读取变更集详情
- 审批、驳回、撤销、应用、回滚入口
- 记录 before/after 引用
- 驱动 Canon Apply

这是 V1 的**唯一正史写入入口服务**。

### 4.5 Creative Object Service（创作对象服务）

负责：
- CharacterCard / RuleCard / OpenLoopCard / ChapterBlueprint / SceneCard 等对象的创建、读取、更新、归档
- 对象版本管理
- 对象引用校验
- 标签、状态、来源记录
- 草稿对象与正式对象管理

不负责：
- 正史写入
- 发布章节
- 章节流程编排

### 4.6 Chapter Service（章节服务）

负责：
- 章节基础元数据
- 章目标输入记录
- 草稿版本管理
- 发布记录
- 章节摘要
- 当前章节状态读取

不负责：
- 替代 Workflow 完成章节循环
- 直接 Apply ChangeSet

### 4.7 Workflow Service（工作流服务）

负责：
- 项目初始化工作流
- 卷规划工作流
- 章节八步循环
- 修订回路
- 发布流程
- 回滚流程
- 长任务状态机与任务恢复

这是系统中的**动作编排中心**。

### 4.8 Agent Gateway Service（Agent 网关服务）

负责：
- 向 Agent 组装标准上下文包
- 接收 Agent 结构化输出
- 输出解析、校验、容错
- 调用对象服务 / 章节服务 / Review 服务落中间结果
- 屏蔽底层存储细节

不负责：
- 直接改 Canon
- 直接发布章节
- 绕过工作流

### 4.9 Review / Gate Service（评审与闸门服务）

负责：
- Schema Gate
- Canon Gate
- Narrative Gate
- Character Voice Gate
- Style Gate
- Publish Gate
- 统一严重度分级与报告格式
- 失败分流建议

### 4.10 Pacing Service（节奏控制服务）

负责：
- 章目标节奏参数生成
- 候选蓝图打分
- 节奏约束输入
- 冲突升级、信息揭示、钩子位置等指标建议

### 4.11 Search & Derived Index Service（检索与派生索引服务）

负责：
- 向量召回
- 图谱查询
- 历史语料召回
- 风格样本检索
- 派生视图刷新

不负责：
- 真相写入
- 正史判断

### 4.12 Audit & Ops Service（审计与运维服务）

负责：
- 操作日志
- 工作流审计
- 幂等键记录
- 任务诊断
- 重放与追踪
- 指标采集

---

## 5. API 分层模型

## 5.1 控制台公开接口

面向：
- 作者
- 编辑
- 项目管理员
- 调试界面

特点：
- 语义化资源
- 稳定版本前缀
- 权限明确
- 返回适合 UI 消费的数据结构

统一前缀建议：

`/api/v1`

## 5.2 工作流内部服务接口

面向：
- Workflow Service
- 内部异步任务
- 编排节点

特点：
- 更偏动作型
- 可接受内部上下文对象
- 不直接暴露给控制台

统一前缀建议：

`/internal/v1`

## 5.3 Agent 网关接口

面向：
- Planner Agent
- Writer Agent
- Reviewer Agent
- Summarizer Agent
- Change Proposal Agent

特点：
- 强结构化输入输出
- 强 schema 校验
- 带调用上下文与 trace 信息
- 不暴露底层表结构

统一前缀建议：

`/agent-gateway/v1`

---

## 6. 统一接口规范

## 6.1 命名规范

- 资源名使用复数英文小写：`projects`, `chapters`, `changesets`
- 动作型接口使用子路径动词：`/approve`, `/apply`, `/rollback`, `/launch`
- 避免使用表意模糊的路径：
  - 不建议：`/doTask`
  - 建议：`/workflows/chapter-cycles/{run_id}/resume`

## 6.2 响应信封建议

V1 统一返回结构建议：

```json
{
  "success": true,
  "code": "OK",
  "message": "ok",
  "data": {},
  "request_id": "req_xxx",
  "trace_id": "trace_xxx"
}
```

错误响应建议：

```json
{
  "success": false,
  "code": "CHANGESET_CONFLICT",
  "message": "changeset conflict detected",
  "details": {},
  "request_id": "req_xxx",
  "trace_id": "trace_xxx"
}
```

## 6.3 分页规范

列表接口建议统一：

- `page`
- `page_size`
- `total`
- `items`

## 6.4 幂等规范

以下写操作建议必须支持 `idempotency_key`：

- 创建项目
- 启动章节循环
- 创建 ChangeSet
- Apply ChangeSet
- 发布章节
- 回滚章节

## 6.5 时间与版本

统一字段建议：
- `created_at`
- `updated_at`
- `version_no`
- `snapshot_version`
- `changeset_id`

---

## 7. 公开 API 资源设计

## 7.1 Project API

### 创建项目
`POST /api/v1/projects`

请求示例：

```json
{
  "project_name": "青石镇修仙长篇",
  "genre_profile_id": "genre_xiuxian_v1",
  "project_description": "东方修仙，宗门群像，单女主双强",
  "init_mode": "from_template"
}
```

### 查询项目列表
`GET /api/v1/projects`

### 查询项目详情
`GET /api/v1/projects/{project_id}`

### 更新项目基础信息
`PATCH /api/v1/projects/{project_id}`

### 获取项目总览
`GET /api/v1/projects/{project_id}/overview`

总览建议返回：
- 当前卷
- 当前章
- 当前状态
- 已发布章数
- open loops 数量
- 最近 ChangeSet 状态
- 最近 workflow run 状态

---

## 7.2 Genre API

### 获取题材模板列表
`GET /api/v1/genres`

### 获取单个题材模板详情
`GET /api/v1/genres/{genre_profile_id}`

### 将题材绑定到项目
`POST /api/v1/projects/{project_id}/genre-binding`

### 获取项目解析后的题材配置
`GET /api/v1/projects/{project_id}/resolved-genre-config`

---

## 7.3 Canon API

### 获取项目当前 Canon Snapshot 摘要
`GET /api/v1/projects/{project_id}/canon/summary`

### 获取项目 Canon 全量视图
`GET /api/v1/projects/{project_id}/canon`

### 获取指定快照版本
`GET /api/v1/projects/{project_id}/canon/snapshots/{snapshot_version}`

### 按域读取 Canon
`GET /api/v1/projects/{project_id}/canon/domains/{domain_name}`

建议域包括：
- `characters`
- `relationships`
- `rules`
- `timeline`
- `open_loops`
- `published_chapters`

注意：
- Canon API 默认只读
- 不提供 `PATCH /canon`

---

## 7.4 Creative Object API

### 获取对象列表
`GET /api/v1/projects/{project_id}/objects`

支持过滤：
- `object_type`
- `status`
- `tag`
- `source_type`
- `linked_chapter_id`

### 创建对象
`POST /api/v1/projects/{project_id}/objects`

### 获取对象详情
`GET /api/v1/projects/{project_id}/objects/{object_id}`

### 更新对象
`PATCH /api/v1/projects/{project_id}/objects/{object_id}`

### 获取对象版本列表
`GET /api/v1/projects/{project_id}/objects/{object_id}/versions`

### 获取对象引用关系
`GET /api/v1/projects/{project_id}/objects/{object_id}/references`

### 归档对象
`POST /api/v1/projects/{project_id}/objects/{object_id}/archive`

说明：
- 这里的更新对象，是更新对象层工作态或配置态
- 如果对象属于 Canon 管辖的正史投影，更新后仍需通过 ChangeSet 落正史

---

## 7.5 Chapter API

### 获取章节列表
`GET /api/v1/projects/{project_id}/chapters`

### 创建章节壳记录
`POST /api/v1/projects/{project_id}/chapters`

### 获取章节详情
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}`

### 获取章节草稿列表
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/drafts`

### 获取单个草稿详情
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/drafts/{draft_id}`

### 更新草稿元信息
`PATCH /api/v1/projects/{project_id}/chapters/{chapter_id}/drafts/{draft_id}`

### 获取章节摘要
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/summary`

### 获取章节状态
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/status`

---

## 7.6 Workflow API

### 启动项目初始化流程
`POST /api/v1/projects/{project_id}/workflows/project-init/launch`

### 启动章节循环
`POST /api/v1/projects/{project_id}/workflows/chapter-cycle/launch`

请求示例：

```json
{
  "chapter_id": "chapter_0008",
  "launch_mode": "full",
  "operator_id": "user_xxx"
}
```

### 获取工作流运行详情
`GET /api/v1/workflow-runs/{run_id}`

### 获取工作流节点状态
`GET /api/v1/workflow-runs/{run_id}/nodes`

### 暂停工作流
`POST /api/v1/workflow-runs/{run_id}/pause`

### 恢复工作流
`POST /api/v1/workflow-runs/{run_id}/resume`

### 取消工作流
`POST /api/v1/workflow-runs/{run_id}/cancel`

原则：
- 控制台不直接手搓“候选蓝图 → 场景拆解 → 写稿 → 闸门”
- 必须通过 `chapter-cycle` 这样的流程入口发起

---

## 7.7 Review / Gate API

### 获取章节闸门报告列表
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/gate-reports`

### 触发某一闸门重跑
`POST /api/v1/projects/{project_id}/chapters/{chapter_id}/gates/{gate_name}/rerun`

### 获取单个闸门报告详情
`GET /api/v1/gate-reports/{gate_report_id}`

### 获取发布准入结论
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/publish-readiness`

---

## 7.8 ChangeSet API

### 创建 ChangeSet
`POST /api/v1/projects/{project_id}/changesets`

### 获取 ChangeSet 列表
`GET /api/v1/projects/{project_id}/changesets`

### 获取 ChangeSet 详情
`GET /api/v1/projects/{project_id}/changesets/{changeset_id}`

### 审批 ChangeSet
`POST /api/v1/projects/{project_id}/changesets/{changeset_id}/approve`

### 驳回 ChangeSet
`POST /api/v1/projects/{project_id}/changesets/{changeset_id}/reject`

### 应用 ChangeSet
`POST /api/v1/projects/{project_id}/changesets/{changeset_id}/apply`

### 回滚 ChangeSet
`POST /api/v1/projects/{project_id}/changesets/{changeset_id}/rollback`

注意：
- `approve` 与 `apply` 可以分开
- MVP 中可允许“审批即应用”的简化模式，但接口概念上仍建议分离

---

## 7.9 Publish API

### 检查章节发布条件
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/publish-check`

### 发布章节
`POST /api/v1/projects/{project_id}/chapters/{chapter_id}/publish`

### 获取发布记录
`GET /api/v1/projects/{project_id}/chapters/{chapter_id}/publish-records`

原则：
- 发布接口内部必须依赖 Publish Gate + ChangeSet Apply 状态
- 不能只因为“有草稿”就允许发布

---

## 8. 内部服务接口设计

## 8.1 内部接口使用场景

内部接口主要用于：
- Workflow 节点之间通信
- 异步任务处理
- 定时派生刷新
- 审计与运维诊断

不面向前端直接公开。

## 8.2 推荐内部动作接口

### 生成章目标输入
`POST /internal/v1/projects/{project_id}/chapter-goal-input:generate`

### 生成候选章蓝图
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/candidate-blueprints:generate`

### 选定章蓝图
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/blueprint-selection:commit`

### 生成场景拆解
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/scene-cards:generate`

### 生成章节草稿
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/drafts:generate`

### 运行章节闸门
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/gates:run`

### 生成 ChangeSet 提议
`POST /internal/v1/projects/{project_id}/chapters/{chapter_id}/changeset-proposals:generate`

### 应用 Canon 更新
`POST /internal/v1/projects/{project_id}/changesets/{changeset_id}:apply-to-canon`

---

## 9. Agent Gateway 设计

## 9.1 设计目标

Agent 不直接理解数据库和业务表。  
Agent 只能看见**标准上下文包**和**标准输出契约**。

Agent Gateway 负责：
- 取数
- 裁剪上下文
- 构造 prompt 输入对象
- 校验 Agent 输出
- 记录 trace
- 写入中间结果

## 9.2 标准读取接口

### 获取 Planner 输入包
`GET /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/planner-input`

### 获取 Scene Decomposer 输入包
`GET /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/scene-decomposer-input`

### 获取 Writer 输入包
`GET /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/writer-input`

### 获取 Reviewer 输入包
`GET /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/reviewer-input?gate_name=canon`

## 9.3 标准提交接口

### 提交候选章蓝图
`POST /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/candidate-blueprints`

### 提交场景拆解结果
`POST /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/scene-cards`

### 提交草稿文本
`POST /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/drafts`

### 提交闸门报告
`POST /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/gate-reports`

### 提交 ChangeSet 提议
`POST /agent-gateway/v1/projects/{project_id}/chapters/{chapter_id}/changeset-proposals`

## 9.4 网关约束

- Agent Gateway 不提供 Canon 写接口
- Agent Gateway 不提供 publish 接口
- Agent Gateway 不提供 approve/apply 接口
- Agent 输出不符合 schema 时必须返回结构化错误

---

## 10. 服务边界禁区

以下行为在 V1 中明令禁止：

### 10.1 前端跨服务硬拼工作流

不允许控制台通过连续调多个零散接口模拟章节主流程。  
必须由 Workflow Service 承担状态编排。

### 10.2 对象服务直改 Canon

Creative Object Service 可以维护对象，但不能直接修改 Canon Snapshot。  
正史变更必须走 ChangeSet。

### 10.3 Agent 直连数据库

Agent 不允许：
- 直接查表
- 直接更表
- 自己决定正史落库

### 10.4 派生索引反写主真相

图谱、向量索引、摘要索引均属于派生层。  
不得把派生层推断结果直接写回 Canon，除非形成 ChangeSet 并经过审批。

### 10.5 Review 服务代替 Workflow 发布

Review / Gate Service 只负责给出准入结论，不负责直接发布。

---

## 11. 权限边界

## 11.1 Human User

可执行：
- 创建项目
- 绑定题材
- 查看对象
- 编辑工作态对象
- 选择候选蓝图
- 审批 ChangeSet
- 发布章节
- 触发回滚

默认不可执行：
- 绕过 Workflow 直接改 Canon 底层记录

## 11.2 Workflow Service

可执行：
- 调用内部动作接口
- 推进章节状态机
- 调度 Agent Gateway
- 触发 Gate
- 触发 ChangeSet 生命周期动作

不可执行：
- 无审批直接强改 Canon（除系统级特定策略外）

## 11.3 Agent

可执行：
- 读取网关输入包
- 提交结构化结果

不可执行：
- 审批
- 应用 ChangeSet
- 发布
- 回滚
- 直接读取敏感内部表

## 11.4 Ops / Admin

可执行：
- 查看审计日志
- 重跑派生任务
- 查看失败任务
- 手动恢复任务

需严格受限：
- 手动修复 Canon 数据

---

## 12. 状态转换与接口协作主链

章节八步循环在接口层面建议收敛为以下主链：

1. `launch chapter-cycle workflow`
2. Workflow 调用 Pacing / Planner 输入生成
3. Workflow 调用 Agent Gateway 生成候选蓝图
4. 人工通过公开接口选定蓝图
5. Workflow 调用 Scene Decomposer
6. Workflow 调用 Writer
7. Workflow 调用 Gate Service
8. 若失败，进入修订回路
9. 若通过，Workflow 调用 ChangeSet Proposal
10. 人工审批 ChangeSet
11. Workflow 调用 Apply
12. Publish API 完成发布
13. 派生索引刷新

---

## 13. 错误码建议

V1 建议至少统一以下错误码：

- `PROJECT_NOT_FOUND`
- `GENRE_PROFILE_NOT_FOUND`
- `OBJECT_NOT_FOUND`
- `CHAPTER_NOT_FOUND`
- `WORKFLOW_RUN_NOT_FOUND`
- `INVALID_WORKFLOW_STATE`
- `INVALID_OBJECT_SCHEMA`
- `GATE_FAILED_BLOCKING`
- `CHANGESET_NOT_FOUND`
- `CHANGESET_CONFLICT`
- `CHANGESET_NOT_APPROVED`
- `CANON_APPLY_FAILED`
- `PUBLISH_NOT_ALLOWED`
- `IDEMPOTENCY_CONFLICT`
- `PERMISSION_DENIED`

---

## 14. MVP 必做接口范围

V1 MVP 阶段，优先必须落地以下接口组：

### P0 必做
- Project API
- Genre Binding API
- Canon Read API
- Creative Object API（最小对象集）
- Chapter API（最小字段）
- Workflow Launch / Status API
- Gate Report API
- ChangeSet API
- Publish API

### P1 可延后
- 批量对象操作
- 高级检索筛选
- Rule Pack 独立管理界面 API
- 多版本比较 API
- 复杂图谱查询 API
- 高级运维 API

---

## 15. 推荐实现顺序

1. 公共响应模型、错误码、鉴权骨架
2. Project / Genre / Canon Read API
3. Creative Object API
4. Chapter API
5. ChangeSet API
6. Workflow Run API
7. Gate Report API
8. Publish API
9. Agent Gateway API
10. 内部动作接口

推荐原因：
- 先把“读接口 + 基础对象 + ChangeSet”立住
- 再补“动作链”
- 最后接 Agent 网关与内部编排

---

## 16. V1 结论

V1 的 API 与服务边界必须服务于系统核心路线：

**Story State / Canon State 中枢 + 结构化对象层 + Workflow 编排 + ChangeSet 收口写入 + 多层质量闸门。**

因此，接口设计不能退化为：
- 数据表导出接口集合
- 前端临时拼动作
- Agent 直接改库
- 派生索引反向写真相

V1 正确的服务边界应当是：

- **Project / Genre / Canon / Object / Chapter** 提供稳定资源视图
- **Workflow** 负责有状态动作编排
- **ChangeSet** 负责唯一正史写入入口
- **Agent Gateway** 负责 Agent 适配与结构化读写
- **Gate Service** 负责质量准入
- **Publish** 负责最终发布动作

该边界既能支撑 MVP 快速落地，又能保证后续扩展多题材、多 Agent、多流程时不失控。
