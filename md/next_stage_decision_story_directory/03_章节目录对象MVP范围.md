# 03_章节目录对象MVP范围

## 1. 文档目的

定义“章节目录对象”后续实现阶段的最小可交付范围，确保该阶段聚焦章节职责约束，不偏移为正文生成或主链重构。

## 2. MVP 结论先行

本阶段 MVP 聚焦“StoryPlanning 与章节执行链之间的目录桥梁层”，目标是让每章在进入 ChapterBlueprint 前具备稳定职责约束。

## 3. MVP 必须覆盖

MVP 必须覆盖以下内容：

1. StoryDirectory / ChapterDirectory 对象；
2. 分卷 / 阶段结构；
3. 章节序号；
4. 章节标题；
5. 章节职责；
6. 章节推进目标；
7. 关键出场实体；
8. 必须落地的设定点；
9. 伏笔开闭约束；
10. 与 StoryPlanning 的引用关系；
11. 与后续卡槽候选的引用关系；
12. 与 ChapterGoal / ChapterBlueprint 的最小引用关系。

## 4. MVP 不包含

- 自动写 Canon；
- 自动生成 ChangeSet；
- 自动生成章节正文；
- 重写 chapter-cycle；
- 复杂知识图谱；
- LLM 自动抽取。

## 5. 最小对象建议

后续若进入实现，建议最小对象族包括：

1. `StoryDirectory`：承载全书目录元信息、分卷/阶段结构与版本信息；
2. `ChapterDirectory`：承载单章职责、推进目标、实体覆盖与设定落地点；
3. `ChapterDirectoryConstraint`：承载伏笔开闭、信息揭示与禁止偏移约束；
4. `DirectoryReferencePack`：承载与 StoryPlanning、卡槽候选、ChapterGoal/Blueprint 的引用锚点。

## 6. 最小后端要求

后续若进入实现，最小后端要求为：

1. StoryDirectory / ChapterDirectory 的最小创建、读取、更新接口；
2. 目录对象与 StoryPlanning 的引用一致性校验；
3. 目录对象对下游 ChapterGoal / ChapterBlueprint 的只读摘要输出能力；
4. 明确禁止绕过 ChangeSet 的 Canon 直写路径。

## 7. 最小前端要求

后续若进入实现，最小前端要求为：

1. 目录结构浏览与最小编辑入口；
2. 分卷/阶段与章节职责可视化；
3. 关键实体与设定落地点的章节级展示；
4. 目录对象引用来源提示（StoryPlanning / 卡槽候选 / 章节输入）。

## 8. 最小测试要求

后续若进入实现，最小测试要求为：

1. StoryDirectory / ChapterDirectory schema 与字段约束测试；
2. 分卷/阶段与章节序列一致性测试；
3. 目录引用关系测试（StoryPlanning -> Directory -> ChapterGoal/Blueprint）；
4. Canon / ChangeSet 边界守卫测试。

## 9. 验收口径

满足以下条件可判定该阶段 MVP 验收通过：

1. 全书规划可稳定下沉为可引用的章节目录对象；
2. 每章具备明确职责、推进目标、关键实体与设定落地点；
3. 目录摘要可被 ChapterGoal / ChapterBlueprint 引用；
4. 卡槽候选可读取目录约束范围；
5. Canon 仍仅通过 ChangeSet 写入。

一句话口径：

**这一阶段的 MVP，不是生成正文，而是让每一章在进入章节蓝图前先有明确的章节职责和目录约束。**
