# 日志系统说明（最小可用版）

## 目标
- 优先支撑 workflow / sequence / agent / changeset / publish 排障。
- 保持最小改动，不重写现有响应与服务架构。

## 结构
- `app/core/logging.py`：JSON 日志格式、控制台 + 滚动文件输出、脱敏与摘要。
- `app/core/logging_context.py`：`contextvars` 上下文注入。
- `app/middleware/request_logging.py`：请求日志中间件，注入 `request_id` 并写入响应头。

## 日志分类
- `app`：应用与请求入口。
- `workflow`：章节主链、Gate、ChangeSet、Publish、Summary、Derived updates。
- `agent`：Agent Gateway 调用。
- `error`：异常处理器。

## 关键字段
- `request_id`
- `trace_id`
- `workflow_run_id`
- `project_id`
- `chapter_no`
- `module`
- `event`
- `status`

## 脱敏策略
- 自动屏蔽 `api_key/token/password/secret/authorization` 等键。
- 超长字符串截断（默认 300 字符）。
- 列表/数组仅保留前若干项并追加 `...` 摘要。

## 查看方式
- 控制台实时日志。
- 本地文件：`logs/app.log`（5MB * 5 滚动）。

## 请求日志
- 中间件读取 `X-Request-ID`，若无则自动生成。
- 响应头回写 `X-Request-ID`。
- 记录字段：`method/path/status_code/duration_ms/client_ip/request_id`。
