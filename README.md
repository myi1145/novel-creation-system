# Novel Creation System

一个基于 **FastAPI + SQLAlchemy + 多 Agent 工作流** 的小说协作后端。  
它覆盖了从立项、设定维护、章节生成、关卡审核到发布与连续性更新的完整链路，适合做「人机协同写作」或「写作工作流编排」服务端。

## 功能概览

- **项目与题材管理**：创建小说项目，加载/查询题材配置。  
- **世界观对象版本化**：角色、规则、伏笔、关系支持变更、恢复、退役与历史追踪。  
- **章节生产流水线**：章节目标 → 蓝图 → 场景分解 → 初稿/改稿 → 发布。  
- **质量关卡（Gate）与变更集（ChangeSet）**：支持提案、审批、拒绝、应用。  
- **工作流编排**：支持 chapter-cycle 与 chapter-sequence 批处理，含暂停、恢复、人工接管。  
- **Prompt 模板管理**：支持模板创建、激活、分层解析预览。  
- **Agent 诊断治理**：调用日志、状态统计、限流、熔断、重试策略。

## 技术栈

- Python 3.10+
- FastAPI
- SQLAlchemy ORM
- Pydantic / pydantic-settings
- SQLite（默认，可通过环境变量切换）
- HTTPX（Agent Gateway 调用）

## 目录结构

```text
.
├── main.py                 # FastAPI 应用入口
├── core/                   # 配置、异常、全局异常处理
├── db/                     # 数据库连接、模型、初始化
├── domain/                 # 领域枚举
├── routers/                # API 路由
├── schemas/                # 请求/响应模型
├── services/               # 业务服务层
└── utils/                  # 通用响应等工具
```

## 快速开始

> 当前代码导入路径使用 `app.xxx`（如 `from app.core.config import settings`）。
> 请确保你的运行环境里该项目作为 `app` 包可被导入（例如放在上级目录以 `app/` 命名，或通过 `PYTHONPATH` 映射）。

### 1) 安装依赖

```bash
pip install fastapi uvicorn sqlalchemy pydantic pydantic-settings httpx
```

### 2) 启动服务

如果你的包路径是 `app.main:app`：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3) 健康检查

```bash
curl http://127.0.0.1:8000/health
```

返回结构示例：

```json
{
  "success": true,
  "message": "success",
  "data": {
    "status": "ok"
  }
}
```

## 配置说明（`.env`）

应用通过 `pydantic-settings` 从 `.env` 读取配置，常用项如下：

```env
APP_NAME="Novel Multi-Agent Backend"
APP_VERSION="0.15.0"
DEBUG=true
HOST="0.0.0.0"
PORT=8000
API_PREFIX="/api/v1"
DATABASE_URL="sqlite:///./data/app.db"
AUTO_CREATE_TABLES=true

# Agent 基础
AGENT_PROVIDER="mock"
AGENT_MODEL="mock-creative-writer-v1"
AGENT_API_BASE_URL=
AGENT_API_KEY=
AGENT_TIMEOUT_SECONDS=45
AGENT_TEMPERATURE=0.3
AGENT_FALLBACK_TO_MOCK=true

# 重试
AGENT_MAX_RETRIES=2
AGENT_RETRY_BACKOFF_MS=800
AGENT_RETRY_BACKOFF_MULTIPLIER=2
AGENT_RETRY_ON_STATUSES="408,409,429,500,502,503,504"

# 限流
AGENT_ENABLE_RATE_LIMIT=true
AGENT_RATE_LIMIT_PER_MINUTE=30

# 熔断
AGENT_ENABLE_CIRCUIT_BREAKER=true
AGENT_CIRCUIT_FAILURE_THRESHOLD=3
AGENT_CIRCUIT_COOLDOWN_SECONDS=60
AGENT_CIRCUIT_HALF_OPEN_MAX_CALLS=1
```

## API 概览

基础路径：`/api/v1`

### 基础
- `GET /health`
- `GET /api/v1/ping`

### 项目 / 题材
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `POST /api/v1/genres/load`
- `GET /api/v1/genres`

### 设定快照（Canon）
- `POST /api/v1/canon/snapshots/init`
- `GET /api/v1/canon/snapshots`

### 世界观对象（Objects）
- 角色：创建、查询、历史、更新/恢复/退役变更集
- 规则：创建、查询、历史、更新/恢复/退役变更集
- 伏笔：创建、查询、历史、更新/恢复/退役变更集
- 关系：创建、查询、历史、更新/恢复/退役变更集

> 统一前缀：`/api/v1/objects`

### 章节与发布（Chapters）
- 章节目标：`POST /chapters/goals`
- 蓝图：生成/查询/选择
- 场景卡：分解
- 草稿：生成/修订/发布
- 发布结果与记录：查询
- 章节摘要与连续性包：生成/查询
- 发布后派生更新：执行/查询

### Gate 与 ChangeSet
- Gate 审核：`POST /api/v1/gates/reviews`
- ChangeSet：提案、审批、拒绝、应用、列表

### 工作流（Workflows）
- chapter-cycle：状态/执行
- chapter-sequence：批量执行、报告
- 运行态控制：暂停、恢复、人工接管、人工确认后继续
- Agent 观测：调用列表、详情、统计
- 诊断：整体概览、运行级诊断

### Prompt 模板（Prompts）
- 默认模板灌入
- 模板列表/创建/激活
- 解析预览（resolve preview）

## 响应格式约定

成功：

```json
{
  "success": true,
  "message": "success",
  "data": {}
}
```

失败：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误信息"
  }
}
```

## 开发建议

- 业务扩展优先在 `services/` 实现，再在 `routers/` 暴露接口。
- 新增请求/响应模型放在 `schemas/`，避免在路由层直接拼装复杂结构。
- 需要持久化审计时，可复用 `immutable_logs` 与 `agent_call_logs` 相关模型。
- 默认 `AUTO_CREATE_TABLES=true` 会在启动时自动建表；生产环境可改为迁移方案（如 Alembic）。
