# Current Stage Handoff

> 作用：这是当前阶段的唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“现在做到哪 / 下一步做什么”时，优先看这份文档。  
> README 提供项目入口与运行说明，并给出本文件入口；当前阶段、已完成内容、下一步唯一目标，以本文件为准。

---

## 1. 当前阶段

**当前阶段：最小生产化基础收口（后段）**

### 当前阶段状态结论（一句话版）

项目已从“工程可运行”推进到“运行可追溯、可签署”的阶段，当前处于“最小生产化基础收口”的后段。

### 当前阶段状态结论（展开版）

当前项目已完成单章主链闭环、连续章节闭环第一轮、真实 provider 连续章节验收基线，以及 Alembic、CI 迁移基线、环境分层、preflight、runbook、运行期证据包与 signoff 记录等关键收口动作。

系统已经具备最小生产化基础：

- 可迁移
- 可预检
- 可验收
- 可留证
- 可签署

阶段边界判断如下：

- **已不属于**：V1 架构落图期、单章闭环验证期、连续章节刚起步期。
- **当前属于**：最小生产化基础收口后段（以收口治理口径与可追溯发布边界为主）。
- **仍未到达**：完整生产发布治理系统、平台化/运维化 fully mature 状态。

因此，当前主战场不是扩 workflow 主链，而是把已存在的验收、证据、签署结果组织成稳定可复用的发布台账视图与最新状态指针。

---

## 2. 当前阶段判断（一句话版）

现在系统的核心问题已不是“能不能跑起来”，而是确保“已经跑通并可验收”的能力能够被稳定追踪与复用。

当前判断：

**最小生产化基础已具备，阶段任务进入后段收口。**
---

## 3. 当前已经明确完成的内容

以下内容视为当前阶段前已完成的基线项，后续不要轻易回头重做。

### 3.1 单章主链闭环已完成（稳定基线）

已具备单章主链能力，包括：

- chapter goal
- blueprint
- draft
- gates
- changeset
- publish
- chapter summary
- derived updates

这部分已经不是当前主战场。

---

### 3.2 chapter-cycle 运行层第一刀已完成

已完成 chapter-cycle 运行层收口，包括：

- 同意图复用
- 冲突拒绝
- 唯一活跃运行控制
- linked run 过滤
- sequence child run 复用边界

结论：

**单章运行入口的幂等 / 冲突控制已完成第一轮收口。**

---

### 3.3 连续章节闭环收口已完成第一轮

已完成 chapter-sequence 的关键闭环能力，包括：

- sequence 可连续派发章节
- sequence 可在中断后恢复
- 已完成章节跳过
- 停止章节优先继续
- `chapter_results` 去重覆盖
- batch report 基本收口
- 恢复响应与累计结果口径已对齐
- continuity 输入恢复已补齐（summary + unresolved_open_loops）

结论：

**连续章节已经从“能跑”推进到“能停、能恢复、能继续、结果不污染”。**

---

### 3.4 真实 provider 连续章节验收基线已完成（含工件归属防串档）

已完成真实 provider 验收基线建设，包括：

- 固定连续章节验收场景
- 验收工件导出
- batch report 导出
- acceptance summary 导出
- CI 上传 real provider 验收工件
- 工件归属防串档（manifest 绑定）

结论：

**真实 provider 连续章节验收已经从“能跑一次”推进到“可重复执行、可留工件、可人工复核”。**

---

### 3.5 Alembic 迁移链路 CI 基线收口已完成（空库升级强校验）

已完成迁移基线接入默认 CI，包括：

- 在默认 `core-stage-acceptance` workflow 增加 migration smoke gate
- CI 干净 SQLite 路径真实执行 `alembic upgrade head`（Python entrypoint 方式）
- 迁移测试从“CLI 缺失可 skip”收紧为 Python 可控 entrypoint 的真实执行路径
- 迁移失败将直接导致 CI 失败并阻断合并

结论：

**Alembic 迁移已从“本地可跑”推进到“CI 强校验门槛”。**

---

### 3.6 环境分层与启动模式语义已完成第一轮收口

已完成环境模式边界统一，包括：

- `APP_ENV=dev|ci|real-provider|prod` 的默认语义与边界校验
- `real-provider` / `prod` 禁止 mock / fallback / auto-create
- `ci` 禁止 `AUTO_CREATE_TABLES=true`
- README / 配置校验 / 阶段交接口径对齐

结论：

**环境分层已从“文档约定”推进到“配置校验可执行”。**

---

### 3.7 示例配置与运行前检查（preflight）收口已完成

已完成最小生产化运行入口收口，包括：

- 新增 `dev / ci / real-provider / prod` 示例 `.env` 文件
- 新增统一 preflight 入口（启动前关键危险配置检查）
- README 增加“示例配置 -> preflight -> Alembic -> 启动/验收”的推荐顺序

结论：

**新协作者已可按仓库示例配置快速起步，并在启动前明确识别高风险配置。**

---

### 3.8 放行记录与人工签署口径已完成（release_signoff）

已完成放行记录与人工签署最小闭环，包括：

- `scripts/release_signoff.py` 可生成结构化签署记录
- 产出 `release_signoff.json` + `release_signoff.md`
- 与 runbook 证据包可建立关联，支持人工复核与留档
- 已提供签署模板与 runbook 文档入口，形成可执行操作路径

结论：

**放行记录与人工签署不再是“下一步目标”，已正式纳入“当前已完成基线”。**

---

## 4. 当前不要再动的区域

除非出现明确 bug 或回归，否则当前不要再把主要精力投到下面这些区域：

### 4.1 不要继续扩 chapter workflow 主链

包括但不限于：

- chapter-cycle 主流程增强
- chapter-sequence 新能力扩展
- gate 规则继续加功能
- publish / changeset 主逻辑继续扩展

这些已经不是当前阶段的优先级。

---

### 4.2 不要再围着真实 provider 验收工件反复打磨

真实 provider 连续章节验收基线已经具备：

- 固定入口
- 固定输出
- 工件归属绑定
- CI 上传

后续除非有明确缺陷，否则不要继续把主精力投入到工件层细节。

---

### 4.3 不要提前扩散到大规模平台化建设

当前还不是做这些的时候：

- 容器化平台
- 监控告警平台
- 权限系统
- 多租户
- 大规模运维治理
- 复杂发布平台

这些都属于后续更高阶段，不是当前主战场。

---

## 5. 当前主战场

### 当前唯一主战场

**最小生产化基础收口**

当前这一阶段最应该优先解决的问题，不再是功能缺口，  
而是：

**运行层 / 生产化边界缺口**

当前最优先的一刀已经明确为：

---

## 6. 下一步唯一目标

### 下一步唯一目标

**收口“放行台账索引与最新状态指针”最小版。**

一句话解释：

在 runbook 证据包与 release signoff 都已具备的前提下，下一刀只做“索引与指针收口”，把既有 `runbook_evidence / release_signoff / stage_acceptance_summary` 串成统一入口，让新窗口可以一眼定位最新放行结论与对应证据。

---

## 7. 下一步任务定义（只保留一个）

### 任务名称

**放行台账索引与最新状态指针收口（最小版）**

### 本次只做什么

- 建立最小台账索引（仅索引，不新增业务逻辑），串联：
  - `runbook_evidence`
  - `release_signoff`
  - `stage_acceptance_summary`
- 提供“最新状态指针”最小入口，明确：
  - 最新一次 prod signoff 是哪份记录
  - 最新一次 real-provider 验收对应哪份证据
  - 新窗口应优先查看哪个状态目录/文件
- 保持口径一致：当前阶段判断、证据位置、签署状态可在 handoff 一处读懂。

### 本次不要做什么

- 不改 workflow 主链逻辑
- 不改 gate / publish / changeset 规则
- 不改 provider gateway 核心业务逻辑
- 不改 Alembic / preflight / runbook / signoff 业务逻辑
- 不做容器化/监控/权限系统
- 不扩业务功能

---

## 8. 当前验收基线

当前默认以以下验收链路判断系统是否稳定：

### 8.1 Core 验收

- `tests/run_stage_acceptance.py --suite core`

作用：

- 验证 mock / core 逻辑层是否稳定
- 验证 chapter workflow 主链与 sequence 基本闭环是否无回归

---

### 8.2 Real provider smoke

- `tests/run_stage_acceptance.py --suite real-smoke`

作用：

- 验证真实 provider 基本可用
- 验证最小真实调用链没有明显退化

---

### 8.3 Real provider acceptance

- `tests/run_stage_acceptance.py --suite real-acceptance`

作用：

- 验证真实 provider 的连续章节验收基线
- 验证工件导出、summary、batch report、归属绑定链路

---

## 9. 当前文档策略

### README 的职责

README 只负责：

- 项目入口说明
- 运行方式
- 初始化方式
- 关键命令
- 当前阶段入口文档链接

### `/md/status/current_stage_handoff.md` 的职责

本文件负责：

- 当前阶段判断
- 当前已完成内容
- 当前不要再动的区域
- 下一步唯一目标
- 给 Codex / 新窗口的交接依据

---

## 10. 给 Codex 的固定交接方式

以后每次开新窗口，不要假设 Codex 知道上下文。  
统一按“发布任务单”形式下发。

建议固定包含以下字段：

1. 当前阶段
2. 当前已完成
3. 本次唯一目标
4. 不要做的事
5. 重点改动对象
6. 验收标准
7. 最小测试
8. 输出格式

---

## 11. 当前推荐的任务下发模板

可直接复制后修改（已翻到当前目标：放行台账索引与最新状态指针收口）：

```text
任务类型：发布任务单

项目：novel-creation-system
当前阶段：最小生产化基础收口（后段）

当前事实（以 current main / 当前文档为准）：
- 单章主链闭环已完成
- 连续章节闭环已完成第一轮
- 真实 provider 连续章节验收基线已完成
- Alembic 迁移链路 + 默认 CI migration smoke gate 已完成
- 环境分层与启动模式语义已完成
- 示例配置 + preflight 已完成
- real-provider / prod runbook 与回滚演练入口已完成
- 运行期验收证据包已完成
- 放行记录与人工签署入口（release_signoff）已完成

本次唯一目标：
- 收口“放行台账索引与最新状态指针（最小版）”

不要做：
- 不改 workflow 主链逻辑
- 不改 gate / publish / changeset 规则
- 不改 provider gateway
- 不改 Alembic / preflight / runbook / signoff 业务逻辑
- 不新增功能
- 不做大范围 README 重写

重点改动对象：
- md/status/current_stage_handoff.md
- README.md（仅当需要最小同步一句入口/阶段口径时再改）
- 如确有必要，可最小调整：
  - md/status/runbook_real_provider_prod.md
  - md/status/release_signoff_template.md

验收标准：
1. handoff 内存在明确“当前阶段状态结论”
2. signoff 已从“下一步”翻入“已完成”
3. 下一步唯一目标已翻到“台账索引 + 最新状态指针”
4. 新窗口仅看 handoff 即可定位当前状态、阶段边界与下一步
5. 不触碰业务逻辑

输出要求：
1. 说明理解
2. 给出最小文档改动方案
3. 更新 handoff（必要时最小同步 README）
4. 最后列出改动文件、改动原因、阶段判断、下一步目标
```

---

## 12. 本次任务结果（阶段基线状态）

本轮任务基线登记：

已完成项（延续既有结论）：

- runbook 执行后自动沉淀证据包目录：`output/runbook_evidence/<timestamp>_<env>/`。
- 证据包最小内容：`runbook_summary.json` + `runbook_summary.md`。
- 结果语义统一：`passed / startup_blocked / prod_release_blocked`。
- 证据包关联：runbook 文档入口 + 最近 stage acceptance summary 路径（若存在）。
- 放行记录与人工签署入口（`release_signoff`）已完成并可留档。

下一刀（当前唯一目标）：

- 收口“放行台账索引与最新状态指针”最小版（仅做索引与指针，不新增主功能）。
