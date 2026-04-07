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
- `/projects/:projectId/genres`（题材档案导入 / 可用题材查看，不做项目级绑定）
- `/projects/:projectId/canon`
- `/projects/:projectId/objects`
- `/projects/:projectId/workbench`
- `/projects/:projectId/gates`
- `/projects/:projectId/changesets`
- `/projects/:projectId/published`

## 说明

- Canon 初始化仅调用 `/canon/snapshots/init`。
- Canon 的长期写入必须通过 ChangeSet 审批/应用链路（前端未绕过）。
- 对象库页面支持四类对象的 ChangeSet 提议入口（update / restore / retire）。
- 工作台页面内提供蓝图候选列表与最小选择子视图。
