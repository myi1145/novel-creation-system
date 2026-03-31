# 日志排障说明（最小可用版）

## 1) 当前日志类别

- **请求日志**：`RequestLoggingMiddleware` 记录请求开始/完成/失败（method、path、status_code、duration）。
- **业务过程日志**：章节工作流主链关键步骤的开始/成功/失败日志，覆盖：
  - `execute_chapter_cycle`
  - `execute_chapter_sequence`
  - `create_goal / generate_blueprints / select_blueprint / decompose_scenes / generate_draft`
  - `changeset proposal generate`
  - `agent_gateway invoke`
  - `summary.generate / derived_updates.run`
  - `manual_continue`
- **异常日志**：统一异常处理器输出中文错误摘要（含唯一约束冲突、非法恢复执行等高频场景）。

## 2) 排查主索引字段

按以下顺序定位最稳妥：

1. `request_id`：先锁定一次 API 请求。
2. `trace_id`：跨服务串联一次工作流链路。
3. `workflow_run_id`：查看单次 workflow 的全部关键步骤。
4. `project_id + chapter_no`：按章节定位问题。

建议组合查询：
- `workflow_run_id=xxx and event=execute_chapter_cycle`
- `project_id=xxx and chapter_no=1 and status=failed`

## 3) 章节过程日志主要函数

- `app/services/workflow_service.py`
  - `execute_chapter_cycle`
  - `execute_chapter_sequence`
  - `manual_continue_workflow_run`
- `app/services/chapter_service.py`
  - `create_goal`
  - `generate_blueprints`
  - `select_blueprint`
  - `decompose_scenes`
  - `generate_draft`
  - `generate_published_chapter_summary`
  - `run_post_publish_updates`
- `app/services/changeset_service.py`
  - `generate_proposal`
- `app/services/agent_gateway.py`
  - `_invoke`

## 4) 摘要记录与脱敏策略

只记录业务摘要，不记录敏感全文：

- 记录：`chapter_no / workflow_run_id / trace_id / candidate_count / scene_count / draft_length / provider / model / fallback_used / latency_ms / next_action / stop_reason`。
- 不记录：API Key、完整 prompt、完整 agent 输入输出、正文全文。
- ID 列表（如 candidate 蓝图）会截断记录，避免过长日志与敏感泄露。

## 5) 本地查看日志

默认日志文件：`logs/app.log`

常用命令：

```bash
# 查看最近日志
tail -n 200 logs/app.log

# 追踪单个 workflow
grep '"workflow_run_id":"<your_run_id>"' logs/app.log

# 查看失败日志
grep '"status":"failed"' logs/app.log
```
