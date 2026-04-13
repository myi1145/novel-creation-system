# 05_Codex执行任务单_文本级人工修订闭环

## 1. 任务名称
**文本级人工修订闭环**

## 2. 项目
`novel-creation-system`

## 3. 当前阶段
- 前端第二轮接线收口已完成。
- 当前阶段已进入“下一阶段最小产品化闭环补齐”。
- 当前系统并非从零开始，已具备以下基础：
  - 主链基础：目标 → 蓝图 → 场景 → 草稿 → Gate → ChangeSet → Publish。
  - 第一版创作工作台。
  - Gate / ChangeSet / Published 页面。
  - 四类结构化对象页。
  - 已存在“需要人工接管”的状态语义与相关测试基础。
- 当前真正缺口不是扩新对象，也不是重做前端主体，而是：**作者仍无法真正人工接管 `ChapterDraft`，并将修改后的草稿继续送回主链。**

## 4. 本轮定位
- 不重做前两轮页面。
- 不开启第三轮对象体系扩展。
- 不改后端主链核心业务语义。
- 本轮仅补齐一个关键断点：
  - `ChapterDraft` 的人工编辑入口。
  - 人工编辑后的最小审计记录。
  - 从人工修订返回 Gate → ChangeSet → Publish 的接线路径。
  - 与上述闭环对应的最小测试与最小文档同步。

## 5. 本轮唯一目标
**让作者可以人工编辑 `ChapterDraft.content`，保存后重新执行 Gate，并继续走 ChangeSet → Publish。**

**本轮是否完成，只看一件事：作者能否在系统中手改草稿，并把修改后的草稿继续送回主链。**

## 6. 严格边界（必须遵守）
1. 不重做 WorkbenchPage。
2. 不重做 GatesPage。
3. 不重做 ChangesetsPage。
4. 不重做 PublishedPage。
5. 不新增第三轮对象体系。
6. 不新增 Location / Faction / Item / Terminology 等结构化对象类型。
7. 不做蓝图级人工修订 UI。
8. 不做场景级人工修订 UI。
9. 不做“修订后自动重算蓝图 / 场景 / 草稿”的复杂联动。
10. 不改 chapter-cycle / chapter-sequence 核心语义。
11. 不改 gate / publish / changeset 核心业务规则。
12. 不新增复杂后端聚合接口。
13. 不新增大范围数据库结构调整，除非完成本轮目标绝对必要。
14. 不允许任何前端页面或新 API 绕过 ChangeSet 直写 CanonSnapshot。
15. 不顺手做视觉大改。
16. 不顺手重构前端路由体系。
17. 不顺手清理无关代码。
18. 不顺手扩 pause / resume / manual-takeover 的其他 UI 能力。
19. 不顺手扩完整审计系统。
20. 必须先审计再修改。
21. 必须以 current main 为准，不以旧 PR 描述、旧讨论或主观印象为准。

**特别强调：除非是完成本轮唯一目标所必需，否则禁止顺手优化、顺手扩展、顺手重构。**

## 7. 你必须先审计的对象

### 7.1 后端数据与路由
- `app/db/models.py`
- `app/routers/chapters.py`
- `app/routers/changesets.py`
- `app/routers/workflows.py`

### 7.2 既有测试与状态语义
- `tests/test_workflow_revision_policy.py`
- 与 `ChapterDraft`、state-history、workflow `attention_required` / `review_revised_draft` 相关的测试文件。
- 与 mock provider 流程相关的测试辅助代码。

### 7.3 前端页面
- `frontend/src/pages/WorkbenchPage.tsx`
- `frontend/src/pages/GatesPage.tsx`
- `frontend/src/pages/ChangesetsPage.tsx`
- `frontend/src/pages/PublishedPage.tsx`

### 7.4 前端路由与 API
- `frontend/src/router/AppRouter.tsx`
- `frontend/src/api/client.ts`
- 任何已存在的 draft / chapter / gate / changeset 相关 hooks、service 或类型定义。

### 7.5 文档
- `frontend/README.md`
- `md/status/current_stage_handoff.md`
- `md/next_stage_decision/01_下一阶段方向确认.md`
- `md/next_stage_decision/02_下一阶段阶段目标与边界.md`
- `md/next_stage_decision/03_下一阶段MVP范围.md`
- `md/next_stage_decision/04_任务拆解与轮次规划.md`

## 8. 审计时必须先回答的问题
1. 当前是否已经存在可复用的 draft 更新接口或半成品接口。
2. `ChapterDraft` 的 metadata 是否适合承载最小审计信息。
3. 当前是否已经存在 state-history 或等价状态流转记录机制可复用。
4. 当前前端最自然的草稿编辑入口应放在 Workbench、Gate 还是其他页面。
5. 当前前端路由最适合挂 `DraftEditorPage` 的位置在哪里。
6. 哪些问题只是“缺一个人工编辑入口”，哪些会牵涉到更大范围的结构变动。
7. 本轮最小挂接点应该落在哪些已有结构上。
8. 哪些现有能力已经存在，哪些只是语义存在但产品未闭环。

## 9. 本轮最小挂接层

### 9.1 后端
- `chapters` router 下的 `ChapterDraft` 相关接口。
- `ChapterDraft` 自身 metadata。
- 既有 `chapter_state_transitions` 或等价状态流转记录。

### 9.2 前端
- `AppRouter`。
- 一个新的 `DraftEditorPage`。
- Workbench 或 Gate 中的最小跳转入口。
- `client.ts` 或等价 API client。

### 9.3 文档
- `frontend/README.md`
- 必要的下一阶段 md 文档同步。

### 9.4 允许
- 新增一个 `ChapterDraft` 人工编辑接口。
- 新增一个最小 `DraftEditorPage`。
- 在 Workbench 或 Gate 中补一个“去编辑草稿”入口。
- 保存后提供回 Gate 的引导。
- 为人工编辑写入最小审计信息。
- 复用既有 state-history 机制。
- 做最小测试补齐。
- 做最小文档同步。

### 9.5 不允许
- 重写草稿生成逻辑。
- 改写 Gate 判定策略。
- 改写 ChangeSet 生成核心逻辑。
- 重做 Published 流程。
- 擅自把人工编辑结果直写 Canon。
- 顺手扩成蓝图编辑器或场景编辑器。
- 顺手做复杂富文本编辑器。
- 顺手做多人协作、评论或批注系统。

## 10. 本轮必须完成的 4 个任务

### 任务 1：新增 `ChapterDraft` 的人工编辑接口
**目标：**为草稿提供明确、可审计、可复用的人工文本更新入口。  
**接口建议：**
- `PATCH /api/v1/chapters/drafts/:draftId`
- 或 `POST /api/v1/chapters/drafts/:draftId/manual-edit`

**必须满足：**
- 更新 `chapter_drafts.content`。
- 明确区分“人工编辑”和“自动修订”。
- 不触碰 `CanonSnapshot`。
- 不绕过 `ChangeSet`。

### 任务 2：为人工编辑写入最小审计信息
**目标：**确保人工接管行为可追踪、可复盘、可核验。  
draft metadata 至少写入：
- `edit_reason`
- `edited_at`
- `source_type = human_edited`

条件允许时建议同时写入：
- `edited_by`
- `source_ref`

state transition 至少追加：
- `trigger_type = human_edit`

**要求：**
- 必须能通过既有或新增查询路径看到“发生过一次人工编辑”。
- 不要求做复杂审计系统。
- 但必须保证来源、原因、时间可追踪。

### 任务 3：新增最小 `DraftEditorPage`
**目标：**提供作者可直接接管 `ChapterDraft` 的最小可用页面。  
**路由建议：**
- `/projects/:projectId/drafts/:draftId/edit`

**页面至少具备：**
- 拉取 `draft.content`。
- 大文本编辑。
- `edit_reason` 输入框。
- 保存按钮。
- 保存成功反馈。
- 回 Gate 的引导或跳转入口。

**要求：**
- 不做复杂 UI。
- 不做富文本。
- 不做多人协作。
- 只做最小可用文本编辑器。

### 任务 4：补齐从人工修订回到主链的最小闭环
**目标：**让人工修订结果可继续走现有主链，而非停留在孤立草稿页。  
**至少确认以下路径可走：**
1. Workbench 生成 draft。
2. 从 Workbench 或 Gate 进入 `DraftEditorPage`。
3. 编辑 draft 并填写 `edit_reason`。
4. 保存成功。
5. 回 Gate 页面重新审查同一个 draft。
6. 再去 ChangeSet 页面生成提议。
7. 再继续 Publish。

**要求：**
- 不要求自动跳完整条链。
- 重点是“用户有地方接管，并且接管后能继续走”。

## 11. 推荐实现顺序（必须按顺序走）

### 第一步：先审计 current main，不要直接修
必须先确认：
- 后端是否已经有半成品接口。
- metadata / state-history 哪些可以复用。
- 前端最适合挂编辑页的位置在哪里。
- 现有 draft_id 流转路径是否够用。

### 第二步：先补后端人工编辑接口
- 优先级最高。
- 没有后端写入口，前端编辑页无意义。

### 第三步：再补最小审计
- 确保不是直接覆盖内容。
- 避免后续返工。

### 第四步：再补前端 `DraftEditorPage`
- 让用户真正有地方修改草稿。

### 第五步：最后补最小跳转与验证
- 确认不是“代码有了，但链没接回主路径”。

## 12. 最小测试要求

### 12.1 后端接口测试
至少新增一个针对人工编辑接口的测试，覆盖：
- 创建项目与最小章节上下文。
- 生成或准备一个 draft。
- 调用人工编辑接口修改 `draft.content`。
- 断言 `draft.content` 已更新。
- 断言 metadata 中包含 `edit_reason`。
- 断言 metadata 中包含 `source_type = human_edited`。
- 断言 state-history 中新增 `human_edit` 触发记录。

### 12.2 测试依赖要求
- 不允许依赖真实 provider。
- 必须默认走 mock provider 或现有可离线测试路径。
- 不能把本轮实现做成只能联真实模型才能验收。

### 12.3 前端最小构建验证
至少执行：
- `cd frontend`
- `npm install`
- `npm run build`

### 12.4 主链闭环验收
至少确认：
- draft 可以被人工编辑。
- 保存后可以继续去 Gate。
- Gate 后仍可去 ChangeSet。
- 不会因为本轮改动导致第一轮主链回退。

### 12.5 不回归抽查
至少抽查：
- Workbench 主链不回退。
- Gate 页面不回退。
- Changesets 页面不回退。
- Published 页面不回退。

## 13. 输出要求
完成实现后，必须按以下顺序输出：
1. 你对本轮目标的理解。
2. 你审计后的结论。
   - 当前哪些能力已经存在。
   - 哪些只是语义存在但产品层未闭环。
   - 哪些数据结构与机制可以直接复用。
3. 你的最小改动方案。
4. 实际修改内容。
5. 你补了哪些验证。
6. 风险与未完成项。
   - 哪些是本轮故意不做的。
   - 哪些后续应进入下一阶段。
7. 最后总结。
   - 改了哪些文件。
   - 为什么这是“文本级人工修订闭环”而不是扩功能。
   - 当前这一轮是否可以正式签收。

**输出要求补充：**
- 必须诚实说明是否真正闭环。
- 如果只做成半闭环，必须明确指出卡点。
- 不允许把“未来建议”混成“本轮已完成”。

## 14. 提交与 PR 约束（必须遵守）

### 14.1 Commit message（简体中文）
`feat: 补齐文本级人工修订闭环`

如需拆分提交，可按下面拆：
- 提交 1：`feat: 为 ChapterDraft 新增人工编辑接口`
- 提交 2：`feat: 新增草稿编辑页并接回 Gate 主链`
- 提交 3：`test: 补齐人工修订闭环的最小测试`
- 提交 4：`docs: 同步人工修订闭环的最小操作说明`

### 14.2 PR 标题（简体中文）
`feat: 补齐文本级人工修订闭环`

### 14.3 PR 描述摘要（简体中文）

#### Motivation
- 说明为什么当前系统虽然已有 draft / gate / changeset / publish，但仍不能算作者可控。
- 说明为什么关键断点在“人工接管草稿”而不是继续扩对象层。
- 说明为什么本轮属于最小产品化闭环补齐，而不是第三轮扩展。

#### Description
- 改了哪些后端接口。
- 如何写入人工编辑审计信息。
- 如何新增 `DraftEditorPage`。
- 如何把人工编辑后的 draft 接回 Gate → ChangeSet → Publish。
- 为什么没有扩蓝图 / 场景 / Canon 直写能力。

#### Testing
- 跑了哪些后端测试。
- 是否使用 mock provider。
- 前端是否完成构建验证。
- 人工编辑后的 draft 是否能继续过 Gate。
- 第一轮主链是否未回归。

## 15. 特别强调
这次不是重做工作台。  
这次不是开第三轮对象体系。  
这次不是扩世界设定卡。  
这次不是做蓝图编辑器。  
这次不是做场景编辑器。  
这次不是做富文本系统。  
这次不是做多人协作系统。  

这次只是：

**把当前已经存在的草稿工作态，补成“作者可人工接管、可审计、可继续回主链”的最小闭环。**

## 16. 最终交付口径
请按“文本级人工修订闭环任务”执行，不要发散路线图，不要顺手扩功能。

你的任务只有一个：

**补齐 `ChapterDraft` 的人工编辑能力、最小审计记录与返回 Gate → ChangeSet → Publish 的接线路径，并判断这一轮是否可以签收。**

## 17. 文档验收自检清单
1. 文档全文使用中文。
2. 文档明确体现“最终 Codex 执行工单”定位。
3. 文档完整承接 `01 / 02 / 03 / 04` 的口径。
4. 文档未写成研究归档、方向确认、阶段边界、MVP 或轮次规划文档。
5. 文档明确写出唯一目标、严格边界、审计对象、最小挂接层、四个任务、实现顺序、测试要求、输出要求与 PR 约束。
6. 文档可直接交给 Codex 执行，无需再补关键结构。
7. 文档未越界写入具体代码实现。
8. 文档可直接纳入 `/md/next_stage_decision/` 决策链条。

---

请按“Codex执行任务单生成任务”执行，不要发散研究，不要顺手改写成别的文档类型。

**最终执行指令：生成并执行“文本级人工修订闭环”任务，严格受本任务单约束。**
