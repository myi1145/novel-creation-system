# 小说创作系统 V15 稳定性诊断（P0）

这一版重点补齐了 **真实模型提供方调用治理**。目标不是增加业务花样，而是把模型调用链路做稳、做可观测、做可回退。

## 新增能力

- 新增 `provider_circuit_states`（提供方熔断状态）表
- 新增模型提供方治理配置：
  - 超时控制
  - 重试次数与退避策略
  - 可重试状态码
  - 每分钟请求限流
  - 熔断失败阈值与冷却时间
  - 半开状态探测次数限制
- `openai_compatible` 提供方现支持错误分类：
  - `timeout`（超时）
  - `network`（网络）
  - `http_4xx` / `http_5xx`（HTTP 错误）
  - `parse`（解析）
- `Planner / Scene / Writer / Gate Reviewer` 已接入统一治理
- Agent 调用日志新增字段：
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

- 默认仍使用 `mock` 提供方，可离线跑通主链路
- Prompt 模板默认会在应用启动时自动初始化
- 当前仍未接入 Alembic；若你从旧版 SQLite 直接升级，建议删除旧 `data/app.db` 后重新初始化
- 若要接入真实兼容接口，请配置：
  - `AGENT_PROVIDER=openai_compatible`
  - `AGENT_API_BASE_URL`
  - `AGENT_API_KEY`
  - `AGENT_MODEL`
