# 小说多 Agent 后端（V1 / P0-P1 增量实现）

本仓库是面向长篇小说创作的多 Agent 后端服务实现，按 `/md` 下 V1 文档体系推进，目标是把“可控创作 + 状态中枢 + 可审计入史”先落成可联调、可回归的工程闭环。

---

## 1. 项目简介

项目聚焦后端控制面，不做“自由续写工具”定位。当前代码以 Story State / Canon State 为中枢，围绕章节主链、质量闸门、ChangeSet 入史、发布后派生更新建立可执行流程。

---

## 2. 当前阶段定位

当前阶段与任务交接请见：**`/md/status/current_stage_handoff.md`**。

README 负责项目入口与运行说明；`/md/status/current_stage_handoff.md` 负责维护“当前阶段、已完成内容、下一步唯一目标、任务交接口径”。新窗口/新任务请先按该文档对齐上下文。

为避免口径漂移：README 不定义当前阶段结论，只提供执行入口与推荐顺序；阶段判断与任务边界一律以 `current_stage_handoff.md` 为准。

当前仓库阶段口径以 handoff 为准：基础卡槽导入导出阶段已完成并签收（四类基础卡槽 JSON/CSV 导入导出、CSV 模板与导入校验报告最小闭环已具备）；当前已切换至“章节目录对象（StoryDirectory / ChapterDirectory）方向确认与边界立项阶段（docs-only）”；相关决策链位于 `md/next_stage_decision_story_directory/`（00~04），并由 handoff 统一收口。卡槽候选生成已后置到章节目录对象之后，不作为当前主线执行项。

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
- 当前阶段（以 `md/status/current_stage_handoff.md` 为准）为“章节目录对象方向确认与边界立项（docs-only）”；
- 已收口 Alembic 迁移链路，`AUTO_CREATE_TABLES` 仅保留开发兜底语义；
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
- 推荐通过统一入口执行：`python tests/run_real_provider_acceptance.py --suite smoke|acceptance|all`（环境缺失时相关用例会 skip 并提示缺失项）。

### 6.3 阶段验收统一入口（基线固化）

为避免“默认 mock 回归”和“真实 provider 验收”混用，新增统一阶段入口：

```bash
python tests/run_stage_acceptance.py --suite core
python tests/run_stage_acceptance.py --suite real-smoke
python tests/run_stage_acceptance.py --suite real-acceptance
python tests/run_stage_acceptance.py --suite all
```

分层语义约定（仅用于阶段验收，不代表生产 SLA）：

- `core`：默认 mock 核心回归基线（主链与关键闸门回归）。
- `real-smoke`：真实 provider 最小联调通过（单章 smoke）。
- `real-acceptance`：真实 provider 阶段性验收（重复单章 + 多章连续 + 多章 revision 协同）。
- `all`：按 `core -> real-smoke -> real-acceptance` 顺序串行执行。

入口会在控制台打印阶段摘要（suite、模块数、退出码、是否包含 skip），并默认输出一份最小 JSON 摘要到 `output/stage_acceptance_summary_*.json`。

说明：`real-smoke` / `real-acceptance` 继续复用现有 skip 语义；环境前置缺失时会 skip，不会误报 fail。

补充：
- 默认 GitHub Actions（push / pull_request）已接入 `core` 阶段验收，并已作为主分支合并门槛完成实际验证；默认自动 CI 不会执行 `real-smoke` / `real-acceptance`。
- real provider 的 GitHub 验收入口为手动触发 workflow_dispatch（workflow: `Real Provider Stage Acceptance (Manual)`，输入 `suite=real-smoke|real-acceptance|all`）；该入口已可用，`real-smoke` 与 `real-acceptance` 已完成真实手动验收通过，但仍依赖外部环境配置，不属于默认自动 CI。

---

## 7. 已知边界 / 尚未完成项

请避免将当前状态误判为“V1 全量完成”。当前主要边界包括：

1. **质量层仍偏基础版**
   - 多数规则为启发式与阈值策略，覆盖深度和泛化能力仍在迭代。
2. **自动修订闭环尚未全面收口**
   - 闸门已能检测与分级，但并非所有失败项都自动完成高质量修订并二次通过。
3. **生产化能力仍在继续增强**
   - 已具备正式迁移链路，但运维稳定性基线与平台化治理仍需持续补齐。
4. **题材规则包仍在扩展**
   - 已有通用底座 + 配置层机制，但不同题材的规则深度与一致性仍有差异。
5. **真实 provider 效果依赖外部条件**
   - 模型、网络、配额与参数会影响结果，当前更强调“可观测联调”而非“结果质量绝对稳定”。

---

## 8. 仓库结构

```text
app/
  core/        # 配置、异常、日志与观测上下文
  db/          # SQLAlchemy 模型、会话、数据库初始化兜底逻辑
alembic/       # Alembic 迁移链路与版本脚本
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

### 9.3 初始化数据库（推荐主路径）

新库初始化（空数据库）：

```bash
alembic upgrade head
```

已有库升级（增量迁移）：

```bash
alembic upgrade head
```

仅在本地开发临时兜底场景下，可启用自动建表：

```bash
AUTO_CREATE_TABLES=true uvicorn app.main:app --reload
```

### 9.4 启动服务

```bash
uvicorn app.main:app --reload
```

默认配置（见 `app/core/config.py`）：

- Host：`0.0.0.0`
- Port：`8000`
- API 前缀：`/api/v1`
- `APP_ENV`：`dev`（默认开发模式）

### 9.5 环境分层、示例配置与 preflight（最小生产化收口）

当前统一约定四类模式：`dev` / `ci` / `real-provider` / `prod`。

仓库已提供示例配置文件（无真实 secret）：

- `.env.dev.example`
- `.env.ci.example`
- `.env.real-provider.example`
- `.env.prod.example`

推荐统一顺序（先检查再启动）：

1. 复制示例配置

```bash
# dev
cp .env.dev.example .env

# real-provider
cp .env.real-provider.example .env

# prod
cp .env.prod.example .env
```

2. 执行 preflight（启动前检查）

```bash
python scripts/preflight_env.py --env dev
python scripts/preflight_env.py --env real-provider
python scripts/preflight_env.py --env prod
```

3. 非 dev 模式先执行 Alembic 迁移（统一推荐命令）

```bash
alembic upgrade head
```

4. 启动服务或执行验收

```bash
# dev
uvicorn app.main:app --reload

# ci
python tests/run_stage_acceptance.py --suite core

# real-provider / prod
uvicorn app.main:app
```

preflight 重点检查项：

- `APP_ENV` 与 `--env` 是否一致；
- `real-provider` / `prod` 是否错误使用 `AGENT_PROVIDER=mock`；
- `real-provider` / `prod` 是否错误开启 `AGENT_FALLBACK_TO_MOCK=true`；
- 非开发安全模式是否错误开启 `AUTO_CREATE_TABLES=true`；
- `real-provider` / `prod` 是否缺少关键 provider 参数（`AGENT_API_BASE_URL` / `AGENT_API_KEY` / `AGENT_MODEL`）。

### 9.6 健康检查

- 全局健康：`GET /health`
- API 连通性：`GET /api/v1/ping`

### 9.7 real-provider / prod 运行期验收与回滚入口（最小闭环）

运行手册见：`md/status/runbook_real_provider_prod.md`。

推荐统一入口（可执行+可演练）：

```bash
# real-provider 联调验收
python scripts/runbook_checks.py --env real-provider --env-file .env --stage-suite real-smoke

# prod 放行前验收（服务已启动时加 health 检查）
python scripts/runbook_checks.py --env prod --env-file .env --health-url http://127.0.0.1:8000/health --stage-suite real-acceptance
```

统一发布入口顺序（文档/脚本同口径）：

1. `preflight`（`python scripts/preflight_env.py ...`）
2. `alembic`（`alembic upgrade head`）
3. `runbook_checks`（生成 `output/runbook_evidence/`）
4. `release_signoff`（生成 `output/release_signoff/`）
5. `release_registry`（由 `release_signoff` 自动刷新 `output/release_registry/`）

运行完成后会自动输出运行期验收证据包到 `output/runbook_evidence/<timestamp>_<env>/`，至少包含 `runbook_summary.json` 与 `runbook_summary.md`，用于人工复核、放行记录与失败审计。

完成证据包后，可用最小签署入口沉淀人工决策记录（approve / reject / rollback）：

```bash
python scripts/release_signoff.py \
  --decision approve \
  --env prod \
  --operator alice \
  --reason "runbook passed, approve release" \
  --evidence-dir output/runbook_evidence/<timestamp>_prod
```

记录会输出到 `output/release_signoff/<timestamp>_<env>/`，包含 `release_signoff.json` 与 `release_signoff.md`；并会自动刷新 `output/release_registry/` 下的 release index 与 latest pointers。

入口阻断语义：

- preflight / migration / health 失败：禁止启动或禁止继续放行；
- real-provider 验收失败：禁止放行 prod，回到 real-provider 联调态排查；
- prod 安全默认值不满足：直接拒绝启动。

---

## 10. 配置说明（`.env`）

### 10.1 应用与数据库

- `APP_NAME`
- `APP_VERSION`
- `APP_ENV`（`dev|ci|real-provider|prod`，默认 `dev`）
- `DEBUG`
- `DATABASE_URL`（默认 SQLite）
- `AUTO_CREATE_TABLES`（默认 `false`，仅开发兜底）

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
