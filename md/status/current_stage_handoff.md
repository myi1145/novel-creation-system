# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：文本级人工修订闭环阶段（下一阶段最小产品化闭环补齐）**

阶段切换说明：
- 旧阶段“最小生产化基础收口（后段）”已完成并收口。
- 当前阶段已正式切换至 `md/next_stage_decision/01~05` 定义的决策链口径。
- 本阶段唯一主战场为：**文本级人工修订闭环**。

---

## 2. 当前阶段判断

当前核心问题已不是“主链是否可跑”，而是“作者能否在主链内人工接管草稿并继续推进”。

当前判断如下：
- **已不属于**：最小生产化基础收口阶段。
- **当前属于**：文本级人工修订闭环补齐阶段。
- **仍未到达**：蓝图级 / 场景级人工修订、结构化设定卡扩充与平台化扩展阶段。

---

## 3. 已完成基线（延续结论）

以下能力已作为既有基线成立，不再作为当前阶段主目标：
- 单章主链（目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish）可执行。
- 连续章节（chapter-sequence）第一轮闭环已完成。
- Gate / ChangeSet / Publish 主链与真实 provider 验收基线已建立。
- Alembic 迁移链路、环境分层、preflight、runbook、signoff、release registry 已形成最小生产化收口。

结论：
**当前阶段不再围绕“最小生产化基础收口”继续扩展。**

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不扩 `chapter-cycle` / `chapter-sequence` 主链能力。
- 不改 gate / changeset / publish 核心业务语义。
- 不做结构化设定卡扩充（如 Location / Faction / Item / Terminology）。
- 不做蓝图级、场景级人工修订能力。
- 不做平台化与大范围前后端重构。

---

## 5. 当前唯一主战场

**文本级人工修订闭环。**

即：围绕 `ChapterDraft` 完成“人工可编辑、可追踪、可回 Gate、可继续 ChangeSet -> Publish”的最小闭环。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**补齐 `ChapterDraft` 的人工编辑、最小审计与返回 Gate -> ChangeSet -> Publish 的接线路径。**

该目标对应 `md/next_stage_decision/05_Codex执行任务单_文本级人工修订闭环.md`，并受以下文档约束：
- `md/next_stage_decision/01_下一阶段方向确认.md`
- `md/next_stage_decision/02_下一阶段阶段目标与边界.md`
- `md/next_stage_decision/03_下一阶段MVP范围.md`
- `md/next_stage_decision/04_任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision/01_下一阶段方向确认.md`
3. `md/next_stage_decision/02_下一阶段阶段目标与边界.md`
4. `md/next_stage_decision/03_下一阶段MVP范围.md`
5. `md/next_stage_decision/04_任务拆解与轮次规划.md`
6. `md/next_stage_decision/05_Codex执行任务单_文本级人工修订闭环.md`

---

## 8. 本文件维护约束

- 本文件仅维护“当前阶段结论、边界、唯一主战场、下一步唯一目标”。
- 不在本文件展开实现细节与工单级步骤。
- 若阶段再次切换，必须先同步本文件，再同步 README 入口口径。
