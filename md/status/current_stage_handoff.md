# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：基础卡槽导入导出立项阶段（docs-only）。**

> 阶段签收补充（2026-04-14）：四类基础卡槽（角色卡、术语卡、势力卡、地点卡）最小人工维护闭环已完成，并完成字段体验收口。  
> 阶段切换补充（2026-04-14）：当前主战场切换为“基础卡槽导入导出”立项，当前唯一主任务为生成 card_import_export 00~04 决策文档链。  
> 阶段边界补充（2026-04-14）：当前不进入导入导出功能实现，不进入接口/数据库/UI开发，不触发 Canon 写入与 ChangeSet 生成链路。

阶段切换说明：
- 上一阶段“结构化设定卡槽体系”立项链路（00~04）已完成并保留追溯；
- 当前阶段进入“基础卡槽导入导出”立项；
- 当前唯一主任务是完成 `md/next_stage_decision_card_import_export/00~04`；
- 当前不进入导入导出实现。

---

## 2. 上一阶段签收结论（四类基础卡槽能力收口）

以下结论已作为签收依据成立：
- 四类基础卡槽已具备人工新建、编辑、查看最小闭环；
- 四类基础卡槽字段说明与作者使用体验已完成收口；
- 卡槽边界已明确：仅人工维护，不自动入 Canon，不生成 ChangeSet；
- 当前不建议立即扩展新卡型，应优先补齐批量维护能力。

签收口径：
**四类基础卡槽最小闭环已完成并签收，当前应进入基础卡槽导入导出立项主线。**

---

## 3. 当前阶段判断

当前核心问题已从“卡槽有没有”转移为“卡槽能否批量维护、备份与迁移”。

当前判断如下：
- **已完成并签收**：四类基础卡槽最小人工维护闭环与字段体验收口；
- **当前属于**：基础卡槽导入导出立项阶段；
- **当前唯一主任务**：生成 `md/next_stage_decision_card_import_export/00~04`；
- **当前仍未进入**：导入导出接口实现、模板下载实现、解析实现、数据库改造。

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不继续扩展新卡型作为当前主线；
- 不改 Gate / ChangeSet / Publish 核心业务语义；
- 不改 `chapter-cycle` / `chapter-sequence` 主链核心语义；
- 不直接进入导入导出实现，不启动 Excel / Markdown / 自动抽取方向开发。

---

## 5. 当前唯一主任务

**完成“基础卡槽导入导出”方向确认与边界立项。**

即：在不进入实现工单的前提下，形成可供后续任务引用的新阶段决策链，明确“为什么做、做什么、不做什么、MVP 最小范围与轮次规划”。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**建立并固化“基础卡槽导入导出”决策文档链（00~04），作为后续是否进入实现任务的上游依据。**

当前固定阅读入口为：`md/next_stage_decision_card_import_export/00~04`。

当前阶段约束文档位于：
- `md/next_stage_decision_card_import_export/00_基础卡槽导入导出候选方向与问题定义.md`
- `md/next_stage_decision_card_import_export/01_基础卡槽导入导出方向确认.md`
- `md/next_stage_decision_card_import_export/02_基础卡槽导入导出阶段目标与边界.md`
- `md/next_stage_decision_card_import_export/03_基础卡槽导入导出MVP范围.md`
- `md/next_stage_decision_card_import_export/04_基础卡槽导入导出任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision_card_import_export/00_基础卡槽导入导出候选方向与问题定义.md`
3. `md/next_stage_decision_card_import_export/01_基础卡槽导入导出方向确认.md`
4. `md/next_stage_decision_card_import_export/02_基础卡槽导入导出阶段目标与边界.md`
5. `md/next_stage_decision_card_import_export/03_基础卡槽导入导出MVP范围.md`
6. `md/next_stage_decision_card_import_export/04_基础卡槽导入导出任务拆解与轮次规划.md`

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
- `md/next_stage_decision_structured_cards/` 作为上一阶段立项决策链继续保留追溯。
- 当前阶段新增独立目录 `md/next_stage_decision_card_import_export/`。
- 当前阶段口径为“基础卡槽导入导出立项收口”，不是“导入导出功能开发启动”。
