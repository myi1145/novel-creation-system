# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：下游依赖失效与重跑治理方向确认与边界立项阶段（docs-only）。**

阶段切换说明：
- 上一阶段“场景级人工修订最小闭环”已完成并正式签收。
- 当前阶段已从“场景级人工修订闭环实施”切换为“下游依赖失效与重跑治理立项决策”。
- 当前主任务不再是继续扩展 `SceneCard` 人工修订能力，而是完成“上游修改后下游结果失效识别、重跑引导与治理边界”的方向确认、边界定义、MVP 收敛与轮次规划。

---

## 2. 阶段签收结论（场景级人工修订最小闭环）

以下结论已作为签收依据成立：
- 围绕 `SceneCard` 的人工编辑能力已落地并可用。
- 场景级最小审计能力与历史查询能力已落地。
- `SceneEditorPage` 已接入 Workbench，形成最小人工操作入口。
- 场景人工修订后可继续回到主链“草稿 -> Gate -> ChangeSet -> Publish”。
- Canon 写入边界保持不变，仍严格通过 ChangeSet 入史。

签收口径：
**场景级人工修订最小闭环阶段已完成并签收，不再作为当前唯一主战场。**

---

## 3. 当前阶段判断

当前核心问题已从“场景层能否人工修订”转移为“上游对象被人工修订后，下游对象与结果如何识别失效、如何提示重跑、如何保持主链语义稳定”。

当前判断如下：
- **已完成并签收**：文本级、蓝图级、场景级人工修订最小闭环阶段。
- **当前属于**：下游依赖失效与重跑治理方向确认与边界立项阶段。
- **仍未进入**：下游依赖失效自动治理与自动重算实现阶段。

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不继续以 `SceneCard` 场景级人工修订为主功能战场扩展新能力。
- 不改 Gate / ChangeSet / Publish 核心业务语义。
- 不改 `chapter-cycle` / `chapter-sequence` 主链核心语义。
- 不直接启动“全链路自动重算 / 自动重跑”功能开发。
- 不并行开启结构化设定卡扩展工程作为当前主线。

---

## 5. 当前唯一主任务

**完成下游依赖失效与重跑治理的方向确认与边界立项。**

即：在不进入实现工单的前提下，形成可供后续任务引用的阶段决策链，明确“为什么先做治理、做什么、不做什么、最小 MVP 与轮次规划”。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**建立并固化下游依赖失效与重跑治理决策文档链（00~04），作为后续是否进入实现任务的上游依据。**

当前阶段约束文档位于：
- `md/next_stage_decision_dependency_recompute/00_下游依赖失效与重跑治理候选方向与问题定义.md`
- `md/next_stage_decision_dependency_recompute/01_下游依赖失效与重跑治理方向确认.md`
- `md/next_stage_decision_dependency_recompute/02_下游依赖失效与重跑治理阶段目标与边界.md`
- `md/next_stage_decision_dependency_recompute/03_下游依赖失效与重跑治理MVP范围.md`
- `md/next_stage_decision_dependency_recompute/04_下游依赖失效与重跑治理任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision_dependency_recompute/00_下游依赖失效与重跑治理候选方向与问题定义.md`
3. `md/next_stage_decision_dependency_recompute/01_下游依赖失效与重跑治理方向确认.md`
4. `md/next_stage_decision_dependency_recompute/02_下游依赖失效与重跑治理阶段目标与边界.md`
5. `md/next_stage_decision_dependency_recompute/03_下游依赖失效与重跑治理MVP范围.md`
6. `md/next_stage_decision_dependency_recompute/04_下游依赖失效与重跑治理任务拆解与轮次规划.md`

---

## 8. 本文件维护约束

- 本文件仅维护“当前阶段结论、边界、唯一主任务、下一步唯一目标”。
- 不在本文件展开实现细节与工单级步骤。
- 若阶段再次切换，必须先同步本文件，再同步 README 入口口径。

---

## 9. 阶段切换备注

- `md/next_stage_decision_scene_revision/00~05` 作为“场景级人工修订阶段”的已签收决策链与执行记录，继续保留并用于追溯。
- 当前阶段新增独立目录 `md/next_stage_decision_dependency_recompute/`，用于避免与上一阶段决策链混写。
- 本阶段输出仅限立项与边界，不等价于“下游依赖失效与重跑治理已进入立即开发”。
