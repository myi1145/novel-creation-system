# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：全书级规划与卡槽种子生成方向确认与边界立项阶段（docs-only）。**

> 阶段签收补充（2026-04-14）：基础卡槽导入导出阶段已完成并签收，四类基础卡槽（角色卡、术语卡、势力卡、地点卡）已完成 JSON/CSV 导入导出、CSV 模板与导入校验报告最小闭环。  
> 阶段切换补充（2026-04-14）：当前主战场切换为“全书级规划与卡槽种子生成”立项，当前唯一主任务为生成 story_planning 00~04 决策文档链。  
> 阶段边界补充（2026-04-14）：当前不进入全书规划实现、不进入卡槽种子生成功能实现，不触发 Canon 写入与 ChangeSet 生成链路。

阶段切换说明：
- 上一阶段“基础卡槽导入导出”能力已完成并签收；
- 当前阶段进入“全书级规划与卡槽种子生成”立项；
- 当前唯一主任务是完成 `md/next_stage_decision_story_planning/00~04`；
- 当前不进入实现开发。

---

## 2. 上一阶段签收结论（基础卡槽导入导出）

以下结论已作为签收依据成立：
- 四类基础卡槽已完成 JSON / CSV 导入导出最小闭环；
- CSV 模板下载能力已形成统一口径；
- 导入校验报告（文件级 / 行级 / 字段级）已形成最小可用能力；
- 导入导出能力保持边界：不自动写 Canon，不自动生成 ChangeSet，不绕过章节主链。

签收口径：
**基础卡槽导入导出阶段已正式签收，后续保留为基础设定资产维护工具，不再作为当前阶段主战场。**

---

## 3. 当前阶段判断

当前核心问题已从“卡槽如何批量维护”转移为“章节生成前缺少全书级规划与设定资产种子主线”。

当前判断如下：
- **已完成并签收**：基础卡槽导入导出（四类卡槽 JSON/CSV、模板、校验报告）；
- **当前属于**：全书级规划与卡槽种子生成立项阶段（docs-only）；
- **当前唯一主任务**：生成 `md/next_stage_decision_story_planning/00~04`；
- **当前仍未进入**：全书级规划对象实现、卡槽种子生成实现、章节主链重构。

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不继续扩展基础卡槽导入导出作为主线；
- 不继续扩新卡型（如物品卡/伏笔卡/关系图谱）作为当前主线；
- 不改 Gate / ChangeSet / Publish 核心业务语义；
- 不改 `chapter-cycle` / `chapter-sequence` 主链核心语义；
- 不进入“自动抽取建卡 / LLM 自动入 Canon / 复杂知识图谱”开发。

---

## 5. 当前唯一主任务

**完成“全书级规划与卡槽种子生成”方向确认与边界立项。**

即：在不进入实现工单的前提下，形成可供后续任务引用的新阶段决策链，明确“为什么做、做什么、不做什么、MVP 最小范围与轮次规划”。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**建立并固化“全书级规划与卡槽种子生成”决策文档链（00~04），作为后续是否进入实现任务的上游依据。**

当前固定阅读入口为：`md/next_stage_decision_story_planning/00~04`。

当前阶段约束文档位于：
- `md/next_stage_decision_story_planning/00_全书级规划与卡槽种子生成候选方向与问题定义.md`
- `md/next_stage_decision_story_planning/01_全书级规划与卡槽种子生成方向确认.md`
- `md/next_stage_decision_story_planning/02_全书级规划与卡槽种子生成阶段目标与边界.md`
- `md/next_stage_decision_story_planning/03_全书级规划与卡槽种子生成MVP范围.md`
- `md/next_stage_decision_story_planning/04_全书级规划与卡槽种子生成任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision_story_planning/00_全书级规划与卡槽种子生成候选方向与问题定义.md`
3. `md/next_stage_decision_story_planning/01_全书级规划与卡槽种子生成方向确认.md`
4. `md/next_stage_decision_story_planning/02_全书级规划与卡槽种子生成阶段目标与边界.md`
5. `md/next_stage_decision_story_planning/03_全书级规划与卡槽种子生成MVP范围.md`
6. `md/next_stage_decision_story_planning/04_全书级规划与卡槽种子生成任务拆解与轮次规划.md`

---

## 8. 本文件维护约束

- 本文件仅维护“当前阶段结论、边界、唯一主任务、下一步唯一目标”。
- 不在本文件展开实现细节与工单级步骤。
- 若阶段再次切换，必须先同步本文件，再同步 README 入口口径。

---

## 9. 阶段切换备注

- `md/next_stage_decision_dependency_recompute/00~04` 作为“下游依赖失效与重跑治理阶段”已签收决策链，继续保留并用于追溯。
- `md/next_stage_decision_release_readiness/00~04` 作为“发布前一致性验收 / 章节发布准入与术语收口阶段”已签收决策链，继续保留并用于追溯。
- `md/next_stage_decision_publish_history/00~04` 作为“章节发布历史与版本追踪阶段”已签收决策链，继续保留并用于追溯。
- `md/next_stage_decision_version_diff/00~04` 作为“轻量版本差异对比与重发决策阶段”已签收决策链，继续保留并用于追溯。
- `md/next_stage_decision_published_export/` 作为历史阶段立项决策链继续保留追溯。
- `md/next_stage_decision_structured_cards/` 作为历史阶段立项决策链继续保留追溯。
- `md/next_stage_decision_card_import_export/` 作为已签收阶段决策链继续保留追溯。
- 当前阶段新增独立目录 `md/next_stage_decision_story_planning/`。
- 当前阶段口径为“全书级规划与卡槽种子生成立项收口”，不是“功能开发启动”。
