# 前端第一版创作工作台（最小闭环）

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
- `/projects/:projectId/genres`
- `/projects/:projectId/canon`
- `/projects/:projectId/objects`
- `/projects/:projectId/workbench`
- `/projects/:projectId/gates`
- `/projects/:projectId/changesets`
- `/projects/:projectId/published`

## 说明

- Canon 初始化仅调用 `/canon/snapshots/init`。
- Canon 的长期写入必须通过 ChangeSet 审批/应用链路（前端未绕过）。
- Gate 与 ChangeSet 与 Publish 均通过后端现有接口执行。
