# 小说多 Agent 后端（V1 / P0 增量实现）

本项目是一个面向长篇小说创作的多 Agent 后端系统，当前代码以 **V1 架构约束** 为准，重点实现章节级主链路的可执行闭环，并补齐 provider 治理与可观测能力。

> 当前定位：工程联调与能力收口版本（非最终生产形态）。

---

## 1. 项目简介

项目目标不是“自由续写”，而是把小说创作过程收敛为可追踪、可校验、可回滚的后端流程：

- 用 Workflow 驱动章节生产与状态流转。
- 用 Gate 控制质量准入。
- 用 ChangeSet 作为 Canon 唯一写入口。
- 用 Publish 串联章节发布与派生更新。

当前已实现单章主链路与连续章节执行器，并支持人工接管、恢复、续跑等控制动作。

---

## 2. 核心设计原则（与 V1 一致）

- **Canon / Story State 是系统中枢**，不是 Agent。
- **Canon 只能通过 ChangeSet 写入**，禁止旁路直写。
- **主链固定为**：目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish。
- **Agent 是受控执行者**，由 Workflow 编排，不可跳步入史。
- **多题材扩展走分层**：通用底座 + 题材配置层 + 规则包。
- **增量演进优先**：以最小闭环持续扩展，不重写系统。

---

## 3. 目录结构说明

```text
app/
  core/        # 配置、异常与应用级基础能力
  db/          # SQLAlchemy 模型、会话、建表初始化
  domain/      # 领域枚举
  routers/     # API 路由入口（/api/v1）
  schemas/     # Pydantic 请求/响应与结构化对象协议
  services/    # 领域服务（workflow、chapter、gate、changeset、publish...）
  utils/       # 通用响应壳层
md/            # V1 架构与协议文档（系统约束来源）
data/          # 本地 SQLite 数据与题材样例
README.md
requirements.txt
```

---

## 4. 主要模块说明

- `workflow_service`：章节主链编排、连续章节执行、诊断与人工控制。
- `chapter_service`：章目标、蓝图、场景、草稿、摘要、连续性上下文处理。
- `gate_service`：多闸门审查与结果聚合。
- `changeset_service`：提议、审批、应用、回滚，收口 Canon 写入。
- `publish_service`：发布章节与发布记录。
- `agent_gateway`：Agent 调用路由、结构化输出解析、provider 治理联动。
- `prompt_template_service`：Prompt 模板管理、激活、解析预览。
- `provider_governance_service`：重试、限流、熔断、半开探测状态治理。

---

## 5. 环境准备

- Python 3.11+（建议）
- pip
- 可选：虚拟环境（venv/conda）

本项目默认使用 SQLite（`data/app.db`），适合本地联调。

---

## 6. 安装方式

```bash
pip install -r requirements.txt
```

---

## 7. 启动方式

```bash
uvicorn app.main:app --reload
```

默认监听配置见 `app/core/config.py`：
- host: `0.0.0.0`
- port: `8000`
- API 前缀: `/api/v1`

---

## 8. 关键配置说明

项目通过 `.env` 读取配置（`pydantic-settings`），当前仓库未提供 `.env.example`，可按下列关键项自行创建：

### 应用与数据库
- `APP_NAME`（可选，默认已有）
- `APP_VERSION`（可选）
- `DEBUG`
- `DATABASE_URL`（默认 SQLite）
- `AUTO_CREATE_TABLES`

### Agent / Provider
- `AGENT_PROVIDER`：默认 `mock`，可切到 `openai_compatible`
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

## 9. 建议联调顺序

建议按“先底座、再主链、再连续章节、再诊断”的顺序联调：

1. `health/ping` 检查服务是否启动。
2. 创建项目与题材装载：`/projects`、`/genres/load`。
3. 初始化 Canon 快照：`/canon/snapshots/init`。
4. 执行单章主链：
   - chapter goal
   - blueprints generate/select
   - scenes decompose
   - drafts generate/revise
   - gates reviews
   - changeset propose/approve/apply
   - drafts publish
5. 触发发布后派生更新与章节摘要。
6. 执行连续章节：`/workflows/chapter-sequence/execute`。
7. 查看诊断与运行明细：`/workflows/diagnostics/*`、`/workflows/runs/*`。
8. 查看 provider 治理：`/workflows/agent-gateway/governance`。

---

## 10. 当前项目状态说明

当前代码已具备以下能力：

- 单章主链可跑通（目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish）。
- 连续章节执行器可用，支持批量推进与阶段性报告。
- 工作流人工控制最小闭环可用（暂停、恢复、人工接管、人工审阅后续跑）。
- ChangeSet 支持提议、审批、应用、回滚。
- 发布后派生更新与章节摘要链路已接入。
- provider 治理已落地（重试、限流、熔断、fallback、调用统计）。

---

## 11. 注意事项（P0 占位与未完全落地项）

- 当前默认 `mock` provider，便于离线联调；真实模型能力依赖外部 provider 配置。
- 项目仍以 P0/P1 工程闭环为主，部分能力是“可运行壳层 + 协议对齐”，不是最终质量实现。
- 部分 Gate/Prompt/题材规则仍以可扩展骨架为主，需按业务继续细化规则包。
- 当前未接入 Alembic 迁移流程；如本地 SQLite 结构与新版本不兼容，建议清理旧库后重建。
- 联调时请优先关注 `workflow_run_id`、`trace_id`、`changeset_id` 的链路一致性与可追踪性。

---

## 12. 参考文档

请优先阅读 `md/` 下 V1 文档，尤其是：

1. 小说多Agent系统最终架构设计文档_V1.md
2. Story_State_Canon_State_状态模型设计_V1.md
3. 章节循环工作流说明_V1.md
4. 多层质量闸门设计_V1.md
5. API_接口与服务边界说明_V1.md
6. 字段命名与对象映射总表_V1.md

