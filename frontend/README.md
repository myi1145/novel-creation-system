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
- `/projects/:projectId/workbench`
- `/projects/:projectId/gates`
- `/projects/:projectId/changesets`
- `/projects/:projectId/published`
- `/projects/:projectId/workflows`

## 说明

- 项目列表“进入项目”默认进入 `overview`，先看聚合状态再继续主链处理。
- Canon 初始化仅调用 `/canon/snapshots/init`。
- Canon 的长期写入必须通过 ChangeSet 审批/应用链路（前端未绕过）。
- 对象页已提供对象侧 `update / restore / retire` ChangeSet 提议入口，提议后在 ChangeSet 页审批。
- 工作台蓝图候选选择在 `WorkbenchPage` 内完成，不新增后端聚合接口。
- 题材页语义为“题材配置库管理（查看 + 导入）”，不伪装项目级题材切换。
- ChangeSet 页在项目路由下按 `project_id` 前端过滤展示，并对缺少项目归属字段的记录做排除提示。
