# 小说多 Agent 后端（V1 / P0-P1 增量实现）

本仓库是面向长篇小说创作的多 Agent 后端服务实现，按 `/md` 下 V1 文档体系推进，目标是把“可控创作 + 状态中枢 + 可审计入史”先落成可联调、可回归的工程闭环。

---

## 1. 项目简介

项目聚焦后端控制面，不做“自由续写工具”定位。当前代码以 Story State / Canon State 为中枢，围绕章节主链、质量闸门、ChangeSet 入史、发布后派生更新建立可执行流程。

---

## 2. 当前阶段定位

当前分支处于：**修订执行层收口 + 修订决策层起步阶段**。

更准确地说：

- 单章主链（目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish）已经能跑通并可验收；
- 修订执行层已基本收口，revision policy 决策开始被 workflow 真实消费并驱动分流；
- Publish Delta Gate 已从伪比较切到真实 baseline 比较，sequence 报告层开始暴露单章关键决策结果；
- 真实 provider 联调与生产化验收仍是下一阶段重点，当前不应视为稳定生产自治系统。

---

## 3. 系统定位（V1 对齐）

本项目遵循 V1 核心约束：

- Canon / Story State 是系统中枢，Agent 不是中枢；
- Canon 只能通过 ChangeSet 写入；
- 章节主链固定为：**目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish**；
- Workflow 负责编排与状态推进，Agent 为受控执行者；
- 多题材扩展路径为：**通用底座 + 题材配置层 + 规则包**；
- 采用增量迭代，不重写整套架构。

---

## 4. 当前能力边界

### 4.1 已落地（可联调 / 可回归）

1. **单章主链闭环可执行**
   - 已具备 goal / blueprints / scenes / draft / gates / changeset / publish 的完整 API 与 workflow 编排。
2. **连续章节能力（同项目多章）**
   - `chapter-sequence` 可按章推进，并生成批次报告；
   - 支持 continuity pack（上一章摘要、open loops、next_chapter_seed）参与后续章节输入。
3. **Gate + ChangeSet + Publish 串联**
   - Gate 结果可驱动 revision / attention；
   - ChangeSet 支持 propose / approve / apply / rollback；
   - Publish 前校验已 applied ChangeSet，发布后落 publish record。
4. **发布后 summary 与 derived updates**
   - 支持已发布章节摘要生成、读取；
   - 支持 post-publish 派生更新任务执行与查询；
   - `next_chapter_seed` 已进入摘要与连续章节承接链路。
5. **质量闸门增强能力已接入主链**
   - Draft→Publish Delta Gate；
   - Seed Consumption Gate（叙事承接检测）；
   - Character Voice Gate；
   - Style Gate。
6. **revision policy 已进入 workflow 决策**
   - 已输出 `revision_policy_decision` / `revision_policy_reason` / `revision_text_changed` / `revision_attempt_count`；
   - 可影响 `next_action` 与 `attention_required` 分流（如 `continue` / `retry` / `stop_for_manual_review`），修订文本未变化会进入人工审阅。
7. **Publish Delta Gate 已使用真实 baseline 比较**
   - baseline 优先级：`predecessor_draft -> previous_published_chapter -> baseline_unavailable`；
   - baseline 来源与引用会写入 `publish_metadata`（`delta_baseline_source` / `delta_baseline_ref_id` / `delta_baseline_reason`）供审计与报告消费。
8. **sequence 报告已暴露单章关键决策字段**
   - 包含 `revision_policy_decision` / `revision_policy_reason` / `no_improvement_reason` / `revision_text_changed` / `revision_attempt_count`；
   - 同时暴露 `quality_delta_decision` / `delta_baseline_source`。
9. **真实 provider 联调能力**
   - 支持 `openai_compatible` provider；
   - 提供 gateway 状态检查、调用日志、治理统计（重试 / 限流 / 熔断 / fallback 观测）；
   - 已有真实 provider 单章与连续章节验收测试。
10. **验收导出工件（测试侧）**
   - 连续章节真实 provider 验收会将章节正文与摘要导出到 `output/...` 目录，便于人工复核与回归对比。

### 4.2 当前仍在增强

- 多数质量闸门当前仍是“最小可用 + 启发式规则 + 结构化报告优先”，不是完整文学评审系统；
- 已有检测能力不等于自动修复闭环：并非所有问题都会自动进入稳定重写链路；
- 默认配置仍偏联调（如 `mock` provider + 可 fallback）；真实模型效果依赖外部环境与参数；
- 默认回归仍以 mock provider 为主；真实 provider 需单独配置并按 smoke / acceptance 入口验收，不能视为开箱即跑；
- 当前阶段目标仍是“真实 provider 联调 + 生产化验收基线”持续补齐，不应高估为 fully autonomous production system；
- 存储层目前以 `AUTO_CREATE_TABLES` 为主，尚未集成 Alembic 迁移链路；
- 运维级能力（多环境发布策略、长期稳定性基线、平台化治理）仍有限。

---

## 5. 质量闸门现状

当前闸门能力重点是：**显式检测、结构化报告、可回归验证**，而非“自动保证文学质量提升”。

- **Narrative / Publish 方向**：
  - 基础结构完整性、蓝图对齐、正文长度、发布前置条件等检查；
  - 支持失败分级（S0~S4）、推荐处理路径、人工可覆盖信息。
- **Delta Gate（Publish 质量增益）**：
  - 基于 draft/published 相似度、改动段落数、未解决关键问题等给出 pass/warn/fail；
  - baseline 优先级为 `predecessor_draft -> previous_published_chapter -> baseline_unavailable`，并将来源写入 `publish_metadata` 供审计与 sequence 报告消费；
  - strict 配置下可阻断发布。
- **Seed Consumption Gate**：
  - 检查上一章 `next_chapter_seed` 在当前章的承接情况（consumed / weak / missing）；
  - strict 模式可将 missing 升级为强阻断。
- **Character Voice Gate**：
  - 检测人物声音漂移、动机断裂、情绪不匹配、关系阶段错位、作者代言等问题；
  - 输出结构化 taxonomy 供审阅与回归。
- **Style Gate**：
  - 检测风格漂移、语体失衡、题材语气不匹配、术语语气不一致等问题；
  - 结果以结构化 issue/report 返回，可用于阶段性基线验证。

---

## 6. 当前验收与测试覆盖

当前 `tests/` 已覆盖一批主链与闸门回归方向（代表性）：

- 单章主链基础验收与重复执行幂等检查；
- 单章真实 provider smoke 验收（禁止 fallback 的前置检查）；
- 同项目连续章节真实 provider 验收（1~3 章连续推进与承接）；
- Publish Delta Gate 专项测试（warn/strict fail）；
- Seed Consumption Gate 专项测试（consumed/weak/missing + strict）；
- Character Voice Gate 专项测试（问题类型与 strict 升级）；
- Style Gate 专项测试（风格与语体偏移检测）；
- workflow sequence 恢复 / manual continue / idempotency 相关测试。

这些测试的定位是：验证“链路可跑通 + 检测结果可复现 + 回归可执行”，不是证明“创作质量已全面自动达标”。

### 6.1 关键测试锚点（本阶段）

- `tests/test_workflow_revision_effectiveness.py`：验证 revision policy 已进入 workflow 决策，并在“无改进/文本未变化”等场景触发人工审阅分流。
- `tests/test_publish_quality_delta_gate.py`：验证 Publish Delta Gate 已使用真实 baseline 比较，并把 baseline 来源写入 `publish_metadata`。
- `tests/test_workflow_sequence_cycle_closure.py`：验证 sequence 报告已显式暴露单章修订决策与质量增益（delta）关键字段。

### 6.2 真实 provider 验收入口（提醒）

- 仓库内存在真实 provider 的 smoke / acceptance 测试入口；
- 这些用例依赖外部环境配置（模型、密钥、网络等）；
- 应与默认 mock 回归分开看待，不代表默认配置开箱即跑。

---

## 7. 已知边界 / 尚未完成项

请避免将当前状态误判为“V1 全量完成”。当前主要边界包括：

1. **质量层仍偏基础版**
   - 多数规则为启发式与阈值策略，覆盖深度和泛化能力仍在迭代。
2. **自动修订闭环尚未全面收口**
   - 闸门已能检测与分级，但并非所有失败项都自动完成高质量修订并二次通过。
3. **生产化能力未完全到位**
   - 迁移体系、默认策略治理、运维稳定性与平台化能力仍需补齐。
4. **题材规则包仍在扩展**
   - 已有通用底座 + 配置层机制，但不同题材的规则深度与一致性仍有差异。
5. **真实 provider 效果依赖外部条件**
   - 模型、网络、配额与参数会影响结果，当前更强调“可观测联调”而非“结果质量绝对稳定”。

---

## 8. 仓库结构

```text
app/
  core/        # 配置、异常、日志与观测上下文
  db/          # SQLAlchemy 模型、会话、建表初始化
  domain/      # 领域枚举与常量
  routers/     # API 路由入口（/api/v1）
  schemas/     # Pydantic 请求/响应与结构化对象协议
  services/    # 领域服务（workflow/chapter/gate/changeset/publish 等）
  utils/       # 通用响应壳层与工具
md/            # V1 架构与协议文档（规范来源）
tests/         # 回归与验收测试
output/        # 部分验收脚本导出的正文/摘要工件
```

---

## 9. 快速开始

### 9.1 环境要求

- Python 3.11+
- pip
- 推荐虚拟环境（venv/conda）

### 9.2 安装依赖

```bash
pip install -r requirements.txt
```

### 9.3 启动服务

```bash
uvicorn app.main:app --reload
```

默认配置（见 `app/core/config.py`）：

- Host：`0.0.0.0`
- Port：`8000`
- API 前缀：`/api/v1`

### 9.4 健康检查

- 全局健康：`GET /health`
- API 连通性：`GET /api/v1/ping`

---

## 10. 配置说明（`.env`）

### 10.1 应用与数据库

- `APP_NAME`
- `APP_VERSION`
- `DEBUG`
- `DATABASE_URL`（默认 SQLite）
- `AUTO_CREATE_TABLES`

### 10.2 Agent / Provider

- `AGENT_PROVIDER`（默认 `mock`，支持 `openai_compatible`）
- `AGENT_MODEL`
- `AGENT_API_BASE_URL`
- `AGENT_API_KEY`
- `AGENT_TIMEOUT_SECONDS`
- `AGENT_TEMPERATURE`
- `AGENT_FALLBACK_TO_MOCK`

### 10.3 治理参数（重试 / 限流 / 熔断）

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

### 10.4 质量闸门相关开关（当前已实现）

- `PUBLISH_REQUIRE_QUALITY_DELTA`
- `PUBLISH_DELTA_SIMILARITY_THRESHOLD`
- `PUBLISH_DELTA_MIN_CHANGED_PARAGRAPHS`
- `ENABLE_SEED_CONSUMPTION_GATE`
- `SEED_CONSUMPTION_REQUIRE_STRICT`
- `SEED_CONSUMPTION_MIN_MATCHED_FRAGMENTS`
- `ENABLE_CHARACTER_VOICE_GATE`
- `CHARACTER_VOICE_GATE_STRICT`
- `ENABLE_STYLE_GATE`
- `STYLE_GATE_STRICT`

---

## 11. API / 模块概览

> 基础前缀：`/api/v1`

### 11.1 项目 / 题材 / Canon

- `projects`：项目创建、读取、更新、进度摘要
- `genres`：题材配置加载、读取、规则包解析
- `canon`：Canon 快照初始化、读取与状态视图

### 11.2 章节主链与连续性

- `chapters/goals`：章目标创建
- `chapters/blueprints/*`：蓝图生成、查询、选择
- `chapters/scenes/decompose`：场景拆解
- `chapters/drafts/*`：草稿生成、修订、发布
- `chapters/published/*`：已发布章节、摘要、派生更新
- `chapters/projects/{project_id}/continuity-pack`：连续章节上下文包

### 11.3 质量闸门与入史

- `gates/*`：Gate 审查与结果读取
- `changesets/*`：提议、审批、应用、回滚（Canon 写入主入口）

### 11.4 工作流与观测

- `workflows/chapter-cycle/*`：单章主链执行与状态
- `workflows/chapter-sequence/*`：连续章节执行与批次报告
- `workflows/runs/*`：运行明细、暂停/恢复、人工接管/续跑
- `workflows/diagnostics/*`：诊断总览与运行诊断
- `workflows/agent-gateway/*`、`workflows/agent-calls*`：Agent 调用与治理观测

---

## 12. 文档阅读顺序（修改代码前必读）

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
