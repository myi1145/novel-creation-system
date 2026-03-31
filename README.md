# 小说多 Agent 后端（V1 / P0-P1 增量实现）

本仓库是一个面向长篇小说创作的多 Agent 后端服务实现，严格对齐 `/md` 下 V1 文档体系，围绕“可控创作 + 可追踪状态 + 可审计变更”构建最小可运行闭环。

> 当前阶段定位：**工程联调版本**（已可跑通主链路，仍在持续补齐规则深度与生产化能力）。

---

## 1. 系统定位（V1 对齐）

本项目不是“自由续写工具”，也不是“单一写作 Agent + 长 Prompt”的拼装系统，而是：

- 以 **Story State / Canon State** 为中枢的创作控制后端；
- 以 **Workflow** 驱动章节循环的有状态流程系统；
- 以 **ChangeSet** 作为 Canon 唯一合法写入口；
- 以 **Gate + Publish + Derived Update** 保障发布质量和后续可用性。

### 核心硬约束

- Canon / Story State 是系统中枢，Agent 不是中枢。
- Canon 只能通过 ChangeSet 写入，禁止旁路更新。
- 章节主链固定为：**目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish**。
- Agent 是受控执行者，必须受 Workflow 编排。
- 多题材扩展遵循：**通用底座 + 题材配置层 + 规则包**。
- 项目采用增量演进策略，不重写整套架构。

---

## 2. 当前能力边界（你可以期待什么）

### 已落地（可联调）

- 单章八步主链路可执行，并可生成完整流程数据。
- 连续章节执行器可批量推进，支持阶段报告输出。
- Workflow 人工控制最小闭环可用（暂停 / 恢复 / 人工接管 / 人工续跑）。
- ChangeSet 支持提议、审批、应用、回滚。
- 发布后派生更新与章节摘要链路已接入。
- Agent Provider 治理可用（重试、限流、熔断、fallback、调用统计）。

### 当前仍在增强（请知悉）

- 默认以 `mock` provider 为主，真实模型能力依赖外部配置。
- 部分题材规则与质量闸门仍是“可扩展骨架 + 基础实现”。
- 数据库迁移暂未接入 Alembic，联调期建议按需清库重建。

---

## 3. 仓库结构

```text
app/
  core/        # 配置、异常、错误处理
  db/          # SQLAlchemy 模型、会话、建表初始化
  domain/      # 领域枚举与常量
  routers/     # API 路由入口（/api/v1）
  schemas/     # Pydantic 请求/响应与结构化对象协议
  services/    # 领域服务（workflow/chapter/gate/changeset/publish 等）
  utils/       # 通用响应壳层与工具
md/            # V1 架构与协议文档（规范来源）
data/          # 本地 SQLite 数据与题材样例
tests/         # 回归与接口测试
```

---

## 4. 快速开始

### 4.1 环境要求

- Python 3.11+
- pip
- 推荐使用虚拟环境（venv/conda）

### 4.2 安装依赖

```bash
pip install -r requirements.txt
```

### 4.3 启动服务

```bash
uvicorn app.main:app --reload
```

默认配置（见 `app/core/config.py`）：

- Host：`0.0.0.0`
- Port：`8000`
- API 前缀：`/api/v1`

### 4.4 健康检查

- 全局健康：`GET /health`
- API 连通性：`GET /api/v1/ping`

---

## 5. 配置说明（`.env`）

项目通过 `.env`（`pydantic-settings`）读取配置，建议至少配置以下关键项。

### 应用与数据库

- `APP_NAME`
- `APP_VERSION`
- `DEBUG`
- `DATABASE_URL`（默认 SQLite）
- `AUTO_CREATE_TABLES`

### Agent / Provider

- `AGENT_PROVIDER`（默认 `mock`，支持 `openai_compatible`）
- `AGENT_MODEL`
- `AGENT_API_BASE_URL`
- `AGENT_API_KEY`
- `AGENT_TIMEOUT_SECONDS`
- `AGENT_TEMPERATURE`
- `AGENT_FALLBACK_TO_MOCK`

### 治理参数（重试 / 限流 / 熔断）

- `AGENT_MAX_RETRIES`
- `AGENT_RETRY_BACKOFF_MS`
- `AGENT_RETRY_BACKOFF_MULTIPLIER`
- `AGENT_RETRY_ON_STATUSES`
- `AGENT_ENABLE_RATE_LIMIT`
- `AGENT_RATE_LIMIT_PER_MINUTE`
- `AGENT_ENABLE_CIRCUIT_BREAKER`
- `AGENT_CIRCUIT_FAILURE_THRESHOLD`
- `AGENT_CIRCUIT_COOLDOWN_SECONDS`
- `AGENT_CIRCUIT_HALF_OPEN_MAX_CALLS`

---

## 6. API 总览（按领域分组）

> 基础前缀：`/api/v1`

### 6.1 项目 / 题材 / Canon

- `projects`：项目创建、读取、更新、进度摘要。
- `genres`：题材配置加载、读取、规则包解析。
- `canon`：Canon 快照初始化、读取与状态视图。

### 6.2 创作对象 / 章节链路

- `objects`：结构化创作对象查询与管理。
- `chapters/goals`：章目标创建。
- `chapters/blueprints/*`：蓝图生成、查询、选择。
- `chapters/scenes/decompose`：场景拆解。
- `chapters/drafts/*`：草稿生成、修订、发布。
- `chapters/published/*`：已发布章节、摘要、派生更新。

### 6.3 质量与入史

- `gates/*`：多闸门审查结果。
- `changesets/*`：提议、审批、应用、回滚（Canon 写入主入口）。

### 6.4 工作流与观测

- `workflows/chapter-cycle/*`：单章主链执行与状态。
- `workflows/chapter-sequence/*`：连续章节执行与报告。
- `workflows/runs/*`：运行明细与人工控制动作。
- `workflows/diagnostics/*`：诊断总览与运行诊断。
- `workflows/agent-gateway/*`、`workflows/agent-calls*`：Agent 调用与治理观测。

---

## 7. 推荐联调顺序（主链优先）

1. 健康检查：`/health`、`/api/v1/ping`。
2. 项目初始化：`/projects`。
3. 题材加载：`/genres/load`。
4. Canon 初始化：`/canon/snapshots/init`。
5. 执行单章链路：
   - goal -> blueprints -> scenes -> drafts -> gates -> changesets -> publish
6. 触发发布后派生更新与摘要。
7. 执行连续章节：`/workflows/chapter-sequence/execute`。
8. 查看运行诊断与治理状态：`/workflows/diagnostics/*`、`/workflows/agent-gateway/governance`。

---

## 8. 开发与验证

### 8.1 运行测试

```bash
python -m unittest tests/test_chapter_goal_api.py
```

### 8.2 联调关注指标

建议重点跟踪以下链路标识，确保流程可追踪：

- `workflow_run_id`
- `trace_id`
- `changeset_id`

### 8.3 日志排障

- 请求级与业务步骤级日志说明见：`docs/logging.md`
- 默认日志文件：`logs/app.log`

---

## 9. 文档阅读顺序（修改代码前必读）

请按以下顺序阅读 `/md`：

1. `小说多Agent系统最终架构设计文档_V1.md`
2. `Story_State_Canon_State_状态模型设计_V1.md`
3. `结构化创作对象 Schema 设计_V1.md`
4. `章节循环工作流说明_V1.md`
5. `多层质量闸门设计_V1.md`
6. `题材配置层与规则包设计_V1.md`
7. `Prompt_设计说明_V1.md`
8. `结构化输出解析与容错规范_V1.md`
9. `API_接口与服务边界说明_V1.md`
10. `数据库与存储设计_V1.md`
11. `字段命名与对象映射总表_V1.md`

---

## 10. 版本说明

- 当前 README 对齐时间：`2026-03-31`
- 目标：让仓库说明与现有实现保持一致，便于研发联调与增量迭代。
