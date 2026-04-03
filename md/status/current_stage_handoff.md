# Current Stage Handoff

> 作用：这是当前阶段的唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“现在做到哪 / 下一步做什么”时，优先看这份文档。  
> README 提供项目入口与运行说明，并给出本文件入口；当前阶段、已完成内容、下一步唯一目标，以本文件为准。

---

## 1. 当前阶段

**当前阶段：最小生产化基础收口**

当前项目已经不再属于：

- V1 架构落图期
- 单章闭环验证期

当前项目已经进入并基本完成了：

- 连续章节闭环收口
- 真实 provider 连续章节验收基线收口

因此，当前主战场已经从“workflow 主链补洞”切换为：

**最小生产化基础收口**

这意味着后续重点不再是继续扩 chapter workflow 功能，  
而是收口：

- 数据层可升级
- 环境初始化一致性
- 验收与发布边界
- 最小工程化运行基础

---

## 2. 当前阶段判断（一句话版）

现在系统已经不是“能不能跑起来”的问题，  
而是要把已经跑通、跑稳、可验收的能力，推进到：

**可升级、可发布、可控变更**

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

**收口 CI 迁移基线：把“空数据库 `alembic upgrade head`”固化为默认 CI 强校验门槛。**

一句话解释：

当前系统虽然已经完成 Alembic baseline 与初始化主路径切换，  
但迁移链路尚未成为稳定 CI 合并门槛。  
下一步必须把“空库升级到 head”推进到默认 CI 强校验：

- CI 干净环境真实执行 `alembic upgrade head`
- 迁移失败可直接让 PR 变红
- 迁移 smoke test 与阶段验收并行固化

---

## 7. 下一步任务定义（只保留一个）

### 任务名称

**CI 迁移基线收口（Migration Smoke Gate）**

### 本次只做什么

- 在默认 CI 中增加 migration smoke gate（空库 upgrade head）
- 固化 Python 可控 Alembic entrypoint 的执行路径，避免依赖本地 CLI 安装偶然性
- 收紧迁移测试，确保 CI 中不以 skip 替代真实升级
- 更新阶段文档，明确本轮结果与下一步口径

### 本次不要做什么

- 不改 workflow 主链逻辑
- 不改 gate / publish / changeset 规则
- 不改 provider gateway
- 不做容器化
- 不做监控平台
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

可直接复制后修改：

```text
任务类型：发布任务单

项目：novel-creation-system
当前阶段：最小生产化基础收口

当前已完成：
- chapter-cycle 运行层幂等与唯一活跃运行控制已完成
- chapter-sequence 断点续跑 / 恢复执行已完成
- real-provider 连续章节验收基线已完成
- real-provider 验收工件归属防串档已完成

本次唯一目标：
- 收口 Alembic 迁移链路，弱化 AUTO_CREATE_TABLES 为开发兜底选项

不要做：
- 不改 workflow 主链逻辑
- 不改 gate / publish / changeset 规则
- 不改 provider gateway
- 不做容器化/监控/权限系统

验收标准：
- alembic upgrade head 可在空数据库执行成功
- 应用在开发模式下仍可启动
- README 写清初始化/升级命令
- /md/status/current_stage_handoff.md 更新任务结果

输出要求：
1. 说明理解
2. 给出最小改动方案
3. 实现代码
4. 补测试
5. 更新 README / 文档
6. 最后列出改动文件、测试命令、结果

---

## 12. 本次任务结果（Alembic 迁移链路收口）

本轮任务已完成以下收口项：

- 已建立正式 Alembic 迁移链路（`alembic.ini`、`alembic/env.py`、baseline migration）。
- 已明确迁移主路径为 `alembic upgrade head`（空库初始化与已有库升级统一走迁移链路）。
- 应用启动时默认不再走自动建表；`AUTO_CREATE_TABLES` 已降级为开发兜底开关（默认 `false`）。
- README 已更新“新库初始化 / 已有库升级 / 开发兜底”命令与语义。

最小验证口径：

- migration smoke test：通过（空 sqlite 可 `alembic upgrade head`）。
- config/init path test：通过（关闭 `AUTO_CREATE_TABLES` 且无 schema 时启动失败并提示迁移命令）。
- 开发兜底回归：通过（`AUTO_CREATE_TABLES=true` 时应用可自动建表并启动）。
