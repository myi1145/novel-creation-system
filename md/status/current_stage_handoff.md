# Current Stage Handoff

> 作用：这是当前阶段唯一交接入口。  
> 每次开新窗口、给 Codex 发任务、判断“当前阶段 / 已完成内容 / 下一步唯一目标”时，优先查看本文件。  
> README 仅提供项目入口与运行说明；阶段判断与任务边界以本文件为准。

---

## 1. 当前阶段结论

**当前阶段：发布章节成品阅读与导出方向确认与边界立项阶段（docs-only）。**

> 阶段签收补充（2026-04-14）：轻量版本差异对比与重发决策阶段已完成最小实现并正式签收，仓库主战场切换为“发布章节成品阅读与导出”立项。
> 阶段进展补充（2026-04-14）：已完成“单章已发布成品阅读 + 复制正文 + Markdown/txt 导出 + 入口接线 + 最小测试与 README 同步”最小实现。

阶段切换说明：
- 上一阶段“轻量版本差异对比与重发决策”已完成并签收；
- 当前阶段不进入成品阅读页实现，不进入导出接口实现；
- 当前只做方向确认、边界收口、MVP 范围与轮次规划（00~04）。

---

## 2. 上一阶段签收结论（轻量版本差异对比与重发决策）

以下结论已作为签收依据成立：
- 已新增 `version-diff` 只读聚合能力；
- 已新增 `VersionDiffPage` 最小展示能力；
- 已接入 Workbench / PublishedPage / PublishHistoryPage 入口；
- 已支持轻量差异摘要与重发建议；
- 已完成测试与 README 同步。

签收口径：
**轻量版本差异对比与重发决策阶段已完成并签收，不再作为当前唯一主战场。**

---

## 3. 当前阶段判断

当前核心问题已从“是否能看懂工作态与发布态差异并获得重发建议”转移为“作者如何阅读、复制并导出已发布成品章节”。

当前判断如下：
- **已完成并签收**：文本级 / 蓝图级 / 场景级人工修订闭环；下游依赖失效与重跑治理；发布前一致性验收 / 章节发布准入；章节发布历史与版本追踪；轻量版本差异对比与重发决策。
- **当前属于**：发布章节成品阅读与导出立项阶段。
- **仍未进入**：成品阅读页实现、复制按钮实现、Markdown/txt 导出实现、整本书导出实现。

---

## 4. 当前不要再动的区域

除非修复明确缺陷或回归，当前阶段不应将主精力投入以下区域：
- 不继续扩展“轻量版本差异对比与重发建议”已签收能力作为主线；
- 不改 Gate / ChangeSet / Publish 核心业务语义；
- 不改 `chapter-cycle` / `chapter-sequence` 主链核心语义；
- 不直接落地“整本书导出、复杂排版导出、云分享链接”。

---

## 5. 当前唯一主任务

**完成“发布章节成品阅读与导出”方向确认与边界立项。**

即：在不进入实现工单的前提下，形成可供后续任务引用的新阶段决策链，明确“为什么做、做什么、不做什么、MVP 最小范围与轮次规划”。

---

## 6. 下一步唯一目标（当前阶段执行口径）

**建立并固化“发布章节成品阅读与导出”决策文档链（00~04），作为后续是否进入实现任务的上游依据。**

当前固定阅读入口为：`md/next_stage_decision_published_export/00~04`。

当前阶段约束文档位于：
- `md/next_stage_decision_published_export/00_发布章节成品阅读与导出候选方向与问题定义.md`
- `md/next_stage_decision_published_export/01_发布章节成品阅读与导出方向确认.md`
- `md/next_stage_decision_published_export/02_发布章节成品阅读与导出阶段目标与边界.md`
- `md/next_stage_decision_published_export/03_发布章节成品阅读与导出MVP范围.md`
- `md/next_stage_decision_published_export/04_发布章节成品阅读与导出任务拆解与轮次规划.md`

---

## 7. 给 Codex / 新协作者的固定入口

新窗口任务开始前，建议最小阅读顺序：
1. 本文件（`md/status/current_stage_handoff.md`）
2. `md/next_stage_decision_published_export/00_发布章节成品阅读与导出候选方向与问题定义.md`
3. `md/next_stage_decision_published_export/01_发布章节成品阅读与导出方向确认.md`
4. `md/next_stage_decision_published_export/02_发布章节成品阅读与导出阶段目标与边界.md`
5. `md/next_stage_decision_published_export/03_发布章节成品阅读与导出MVP范围.md`
6. `md/next_stage_decision_published_export/04_发布章节成品阅读与导出任务拆解与轮次规划.md`

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
- 当前阶段新增独立目录 `md/next_stage_decision_published_export/`，用于避免与已签收阶段决策链混写。
- 当前阶段口径为“立项收口”，不是“发布章节成品阅读与导出功能开发启动”。
