# Novel Multi-Agent Backend V15 Diagnostics P0

这一版新增了 **真实 Provider 调用治理**，重点不是扩业务功能，而是把模型调用真正做稳。

## 新增能力

- 新增 `provider_circuit_states` 表
- 新增 Provider 治理配置：
  - 超时控制
  - 重试次数与退避策略
  - 可重试状态码
  - 每分钟请求限流
  - 熔断器失败阈值与冷却时间
  - 半开状态探测次数限制
- `openai_compatible` provider 现在支持：
  - timeout 分类
  - network 分类
  - http_4xx / http_5xx 分类
  - parse 分类
- `Planner / Scene / Writer / Gate Reviewer` 都接入统一治理
- Agent 调用日志新增：
  - `attempt_count`
  - `error_type`
  - `circuit_state_at_call`
  - `rate_limited`
- 新增接口：
  - `GET /api/v1/workflows/agent-gateway/governance`

## 运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 说明

- 默认仍使用 `mock` provider，可离线跑通主链路
- Prompt 模板默认会在应用启动时自动 seed
- 当前仍未接入 Alembic，如果你是从旧版 SQLite 直接升级，建议删除旧 `data/app.db` 后重新初始化
- 如果要接真实兼容接口，请配置：
  - `AGENT_PROVIDER=openai_compatible`
  - `AGENT_API_BASE_URL`
  - `AGENT_API_KEY`
  - `AGENT_MODEL`
