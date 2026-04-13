# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：场景级人工修订方向确认与边界立项阶段（docs-only）。**

阶段切换说明：
- 上一阶段“蓝图级人工修订最小闭环”已完成并正式签收。
- 当前阶段已从“蓝图级人工修订闭环实施”切换为“场景级人工修订立项决策”。
- 当前主任务不再是继续扩展 `ChapterBlueprint` 人工修订能力，而是完成场景级人工修订的方向确认、边界定义、MVP 收敛与轮次规划。

---

## 2. 阶段签收结论（蓝图级人工修订最小闭环）

以下结论已作为签收依据成立：
- 围绕 `ChapterBlueprint` 的人工编辑能力已落地并可用。
- 蓝图级最小审计能力与历史查询能力已落地。
- `BlueprintEditorPage` 已接入 Workbench，形成最小人工操作入口。
- 蓝图人工修订后可继续回到主链“场景拆解 -> 草稿 -> Gate -> ChangeSet -> Publish”。
- Canon 写入边界保持不变，仍严格通过 ChangeSet 入史。

签收口径：
**蓝图级人工修订最小闭环阶段已完成并签收，不再作为当前唯一主战场。**

---

## 3. 当前阶段判断

当前核心问题已从“蓝图层能否人工修订”转移为“场景层是否需要建立最小可控人工修订路径，且边界是否清晰可控”。

当前判断如下：
- **已完成并签收**：蓝图级人工修订最小闭环阶段。
- **当前属于**：场景级人工修订方向确认与边界立项阶段。
- **仍未进入**：场景级人工修订实现阶段（含场景编辑器开发与代码落地）。

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不继续以 `ChapterBlueprint` 蓝图级人工修订为主功能战场扩展新能力。
- 不改 Gate / ChangeSet / Publish 核心业务语义。
- 不改 `chapter-cycle` / `chapter-sequence` 主链核心语义。
- 不直接启动场景编辑器实现或场景级人工修订功能开发。
- 不并行开启结构化设定卡扩展工程作为当前主线。

---

## 5. 当前唯一主任务

**完成场景级人工修订的方向确认与边界立项。**

即：在不进入实现工单的前提下，形成可供后续任务引用的阶段决策链，明确“为什么先做场景级、做什么、不做什么、最小 MVP 与轮次规划”。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**建立并固化场景级人工修订决策文档链（00~04），作为后续是否进入实现任务的上游依据。**

当前阶段约束文档位于：
- `md/next_stage_decision_scene_revision/00_场景级人工修订候选方向与问题定义.md`
- `md/next_stage_decision_scene_revision/01_场景级人工修订方向确认.md`
- `md/next_stage_decision_scene_revision/02_场景级人工修订阶段目标与边界.md`
- `md/next_stage_decision_scene_revision/03_场景级人工修订MVP范围.md`
- `md/next_stage_decision_scene_revision/04_场景级人工修订任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision_scene_revision/00_场景级人工修订候选方向与问题定义.md`
3. `md/next_stage_decision_scene_revision/01_场景级人工修订方向确认.md`
4. `md/next_stage_decision_scene_revision/02_场景级人工修订阶段目标与边界.md`
5. `md/next_stage_decision_scene_revision/03_场景级人工修订MVP范围.md`
6. `md/next_stage_decision_scene_revision/04_场景级人工修订任务拆解与轮次规划.md`

---

## 8. 本文件维护约束

- 本文件仅维护“当前阶段结论、边界、唯一主任务、下一步唯一目标”。
- 不在本文件展开实现细节与工单级步骤。
- 若阶段再次切换，必须先同步本文件，再同步 README 入口口径。

---

## 9. 阶段切换备注

- `md/next_stage_decision_blueprint_revision/00~04` 作为“蓝图级人工修订阶段”的已签收决策链，继续保留并用于追溯。
- 当前阶段新增独立目录 `md/next_stage_decision_scene_revision/`，用于避免与上一阶段决策链混写。
- 本阶段输出仅限立项与边界，不等价于“场景级人工修订已进入立即开发”。
