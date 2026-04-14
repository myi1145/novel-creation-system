# 前端创作工作台（第二轮接线收口）

本工程为独立前端目录，仅消费后端 `/api/v1` 公开接口，不改后端主链逻辑。

## 启动

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## 构建

```bash
npm run build
```

## 路由

- `/projects`
- `/projects/:projectId`（默认重定向到 `/projects/:projectId/overview`）
- `/projects/:projectId/overview`
- `/projects/:projectId/genres`
- `/projects/:projectId/canon`
- `/projects/:projectId/objects`
- `/projects/:projectId/character-cards`
- `/projects/:projectId/terminology-cards`
- `/projects/:projectId/faction-cards`
- `/projects/:projectId/location-cards`
- `/projects/:projectId/workbench`
- `/projects/:projectId/blueprints/:blueprintId/edit`
- `/projects/:projectId/scenes/:sceneId/edit`
- `/projects/:projectId/drafts/:draftId/edit`
- `/projects/:projectId/gates`
- `/projects/:projectId/changesets`
- `/projects/:projectId/published`
- `/projects/:projectId/chapters/:chapterNo/release-readiness`
- `/projects/:projectId/chapters/:chapterNo/publish-history`
- `/projects/:projectId/chapters/:chapterNo/version-diff`
- `/projects/:projectId/chapters/:chapterNo/published-reader`
- `/projects/:projectId/workflows`

## 说明

- 项目列表“进入项目”默认进入 `overview`，先看聚合状态再继续主链处理。
- Canon 初始化仅调用 `/canon/snapshots/init`。
- Canon 的长期写入必须通过 ChangeSet 审批/应用链路（前端未绕过）。
- 对象页已提供对象侧 `update / restore / retire` ChangeSet 提议入口，提议后在 ChangeSet 页审批。
- 工作台蓝图候选选择在 `WorkbenchPage` 内完成，不新增后端聚合接口。
- 题材页语义为“题材配置库管理（查看 + 导入）”，不伪装项目级题材切换。
- ChangeSet 页在项目路由下按 `project_id` 前端过滤展示，并对缺少项目归属字段的记录做排除提示。

## 作者端术语说明

1. **章节蓝图**：用于确定本章的剧情方向和结构。  
2. **场景安排**：用于把蓝图拆成具体场景。  
3. **章节草稿**：用于生成和人工修订正文。  
4. **人工修订**：用于作者按创作意图调整蓝图、场景和草稿，并记录修订原因。  
5. **质量检查**：用于检查草稿是否满足发布要求。  
6. **变更提案**：用于确认哪些内容要写入正式设定。  
7. **发布前检查**：用于确认是否还有未处理问题。  
8. **发布章节**：用于把当前章节发布为正式版本。  

补充术语统一：

- **发布章节历史**：查看本章每次发布时间与发布记录。  
- **版本差异与重发建议**：对比“当前工作内容 vs 最近发布版本”，给出是否建议重新发布。  
- **阅读已发布章节**：以成品阅读视图查看、复制、导出单章发布内容。  
- **下游内容可能已过期**：表示上游改动后，建议重新生成相关下游内容。  

> 以上中文术语仅影响前端展示文案，不改变后端 API 字段、枚举值和业务语义。

## 作者主路径（中文展示）

作者主路径统一为：  
**创作工作台 → 章节蓝图 → 场景安排 → 章节草稿 → 质量检查 → 变更提案 → 发布章节 → 发布前检查 / 章节发布历史 / 版本差异与重发建议 / 阅读已发布章节**。

### 创作到发布最短路径

1. 进入 `创作工作台`，创建并选用蓝图，生成场景与草稿。  
2. 如需调整，进入 `蓝图/场景/草稿人工修订` 页面保存。  
3. 进入 `质量检查` 执行审查。  
4. 进入 `变更提案`，生成提案并完成通过/写入。  
5. 进入 `发布前检查` 确认结论后，在 `发布章节` 页面发布。  

### 发布后追踪与导出最短路径

1. 在 `发布章节` 页面输入章节号，进入 `章节发布历史`。  
2. 进入 `版本差异与重发建议` 查看是否建议重发。  
3. 进入 `阅读已发布章节`，执行 `复制正文`。  
4. 在同页使用 `导出 Markdown` 与 `导出 txt` 完成单章导出。  

## 文本级人工修订最小闭环（当前阶段）

1. 在 `Workbench` 先生成 `draft_id`。
2. 从 `Workbench` 或 `Gates` 点击统一入口「进入人工修订（编辑草稿）」进入 `/projects/:projectId/drafts/:draftId/edit`。
3. 编辑 `draft.content` 并填写 `edit_reason` 后保存（建议写清“改了什么、为什么改”，后端会写入 `metadata.edit_reason / edited_at / source_type=human_edited`）。
4. 保存成功后按页面引导先回到 `Gates` 重新审查同一个 draft。
5. 审查通过后继续在 `Changesets` 页面从 draft 生成提议并审批/应用，再到 `Published` 页面发布。

> 失败提示策略：前端会优先给出可重试的产品化提示，避免直接暴露原始技术报错。

## 蓝图级人工修订最小闭环（本轮新增）

1. 在 `Workbench` 生成并选择 `blueprint_id`。
2. 点击「进入人工修订（编辑蓝图）」进入 `/projects/:projectId/blueprints/:blueprintId/edit`。
3. 编辑 `title_hint / summary / advances / risks` 并填写必填 `edit_reason` 后保存。
4. 保存后可在页面内直接继续执行「场景拆解」「草稿生成」，或返回 Workbench 继续主链。
5. 生成草稿后继续进入 `Gate -> ChangeSet -> Publish` 页面，不绕过既有审核/入史规则。

## 场景级人工修订最小闭环（本轮新增）

1. 在 `Workbench` 先完成场景拆解并拿到 `scene_id`。
2. 从 Workbench 点击「进入人工修订（编辑场景）」进入 `/projects/:projectId/scenes/:sceneId/edit`。
3. 编辑 `scene_goal / participating_entities / conflict_type / emotional_curve / information_delta` 并填写必填 `edit_reason` 后保存（后端会记录 `source_type=human_edited`、`edited_at`、`edit_reason`）。
4. 保存后点击「基于该场景继续生成草稿」，再按既有主链进入 `Gate -> ChangeSet -> Publish`。
5. 场景修订不会直接写 Canon，仍需通过 ChangeSet 入史。

## 下游依赖失效与人工确认重跑（本轮新增）

1. 当 `BlueprintEditorPage` 保存蓝图人工修订后，系统会标记本章下游 `scenes / draft / gate / changeset / publish` 可能过期。
2. 当 `SceneEditorPage` 保存场景人工修订后，系统会标记该场景下游 `draft / gate / changeset / publish` 可能过期。
3. `WorkbenchPage`、`BlueprintEditorPage`、`SceneEditorPage` 都会显示“下游可能过期”提示，并提供人工确认重跑 CTA。
4. 人工确认重跑后，系统复用现有接口执行：
   - 重跑场景拆解：复用 `/chapters/scenes/decompose`
   - 重跑草稿生成：复用 `/chapters/drafts/generate`
5. 重跑只会更新失效状态为 `recomputed`，不会自动发布，不会绕过 Gate / ChangeSet。

## 发布前一致性验收与章节发布准入（本轮新增）

1. `WorkbenchPage` 与 `PublishedPage` 已新增统一入口文案「发布前一致性验收」。
2. 验收页路由为 `/projects/:projectId/chapters/:chapterNo/release-readiness`。
3. 页面会聚合并展示四类检查项：`stale`、`gate`、`changeset`、`publish`。
4. 页面总状态只输出两类结论：
   - `ready_to_publish`
   - `needs_attention`
5. 每个检查项都提供说明与下一步 CTA，用于跳转到 Workbench / Gate / ChangeSet / Published 对应页面继续处理。
6. 该页面定位为“提示与准入建议”，不是硬阻断发布：不会自动修复问题，不会自动重跑，不会自动 apply ChangeSet，也不会自动发布。

## 章节发布历史与版本追踪（本轮新增）

1. 新增页面路由：`/projects/:projectId/chapters/:chapterNo/publish-history`。
2. 入口文案统一为「章节发布历史」，已接入 `WorkbenchPage`、`PublishedPage`、`ReleaseReadinessPage`。
3. 页面展示三块核心信息：
   - 最近一次发布记录（发布时间、来源草稿、来源变更提案、最小摘要、状态）。
   - 当前工作态与最近发布态关系提示（`never_published / up_to_date / work_in_progress_after_publish`）。
   - 本章历史发布列表（按发布时间倒序）。
4. 若本章未发布，页面会明确提示「本章还没有正式发布记录。」。
5. 该能力定位是“版本追踪与状态提示”，不是版本回滚系统：不提供回滚按钮、不做复杂 diff、不自动重新发布。

## 轻量版本差异与重发建议（本轮新增）

1. 新增页面路由：`/projects/:projectId/chapters/:chapterNo/version-diff`。
2. 入口文案统一为「版本差异与重发建议」，已接入 `WorkbenchPage`、`PublishedPage`、`PublishHistoryPage`。
3. 页面聚合展示：
   - 对比总状态：`never_published / no_current_work / comparable`
   - 重发建议：`cannot_compare / republish_not_needed / republish_recommended`
   - 最近发布版引用信息与当前工作态草稿引用信息
   - 轻量指标：`length_delta / paragraph_delta / change_level / changed_summary`
   - 检查项列表（长度、段落、来源、发布时间等）
4. 该能力只做“轻量差异提示 + 重发建议”，不是全文 diff、不是版本回滚系统、不是自动重发系统。

## 发布章节成品阅读与导出（本轮新增）

1. 新增页面路由：`/projects/:projectId/chapters/:chapterNo/published-reader`。
2. `WorkbenchPage`、`PublishedPage`、`PublishHistoryPage` 已新增统一入口文案「阅读已发布章节」。
3. 页面用于作者阅读已发布单章成品，展示：
   - `第 X 章 + 标题`
   - 发布时间
   - 字数
   - 正文阅读区域（保留段落换行）
4. 页面提供 `复制正文` 按钮：
   - 仅复制正文内容
   - 复制成功/失败均有中文反馈
5. 页面提供单章导出入口：
   - Markdown：`/api/v1/chapters/projects/{project_id}/chapters/{chapter_no}/published-reader/export.md`
   - txt：`/api/v1/chapters/projects/{project_id}/chapters/{chapter_no}/published-reader/export.txt`
6. 本能力范围严格限定为**单章已发布成品阅读与导出**，不是整本书导出、不是 PDF/Word 导出，也不是出版排版系统。

## 结构化设定卡槽（四类基础卡槽使用验收后）

- 角色卡入口：`/projects/:projectId/character-cards`
- 术语卡入口：`/projects/:projectId/terminology-cards`
- 势力卡入口：`/projects/:projectId/faction-cards`
- 地点卡入口：`/projects/:projectId/location-cards`

### 每类卡槽适合维护什么

- 角色卡：维护人物身份、性格关键词、关系备注、当前状态与首次出场章节。
- 术语卡：维护固定概念、专有名词、定义摘要、使用规则与示例。
- 势力卡：维护宗门/王朝/组织/族群的类型、立场、目标、核心成员与阶段状态。
- 地点卡：维护城镇/宗门/秘境/禁地的类型、区域、关键特征、关联势力与剧情作用。

### 当前阶段边界（必须遵守）

- 当前阶段只支持人工创建/编辑/查看，不做自动抽取。
- 当前不会自动写入 Canon。
- 当前不会自动生成 ChangeSet。
- 是否进入正式设定仅作人工标记，不触发主链自动入史。

### 暂不扩展内容

- 暂不继续扩展物品卡、伏笔卡、关系图谱。
- 下一批卡槽能力将在四类基础卡槽长期使用反馈稳定后再进入。
