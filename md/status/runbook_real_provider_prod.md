# real-provider / prod 运行期验收与回滚演练（最小闭环）

> 范围：仅收口“上线前怎么验、失败后怎么退”的最小运行手册。  
> 非目标：不改 workflow 主链、不改 gate/publish/changeset 规则、不改 provider gateway 核心业务逻辑。

---

## 1. 统一入口

推荐统一从以下脚本入口执行（可用于演练）：

```bash
python scripts/runbook_checks.py --env real-provider --env-file .env --stage-suite real-smoke
python scripts/runbook_checks.py --env prod --env-file .env --health-url http://127.0.0.1:8000/health --stage-suite real-acceptance
```

该入口按顺序执行：
1. preflight
2. migration 检查（是否已到 head）
3. 健康检查（可选）
4. 阶段验收（默认 `real-smoke`）

执行完成后会自动导出证据包到：

`output/runbook_evidence/<timestamp>_<env>/`

至少包含：

- `runbook_summary.json`：结构化结果（环境、步骤、阻断类型、exit code、建议动作、关联文档/工件）。
- `runbook_summary.md`：人工复核摘要（一眼看结论、失败步骤、是否禁止启动、是否禁止 prod 放行、下一步动作）。

若本次执行包含 stage acceptance，证据包会尝试关联最近一次 `output/stage_acceptance_summary_*.json` 路径，保证可追溯。

执行完运行期证据包后，可继续沉淀人工放行记录（最小闭环）：

```bash
python scripts/release_signoff.py \
  --decision approve \
  --env prod \
  --operator alice \
  --reason "runbook passed, ready to release" \
  --evidence-dir output/runbook_evidence/<timestamp>_prod
```

会输出到 `output/release_signoff/<timestamp>_<env>/`，至少包含：

- `release_signoff.json`：结构化放行/拒绝/回退记录（可审计）。
- `release_signoff.md`：人工复核视图（可签署留档）。

---

## 2. 上线前最小 checklist（人工可直接照抄）

### Step 1：复制正确 env 示例

```bash
cp .env.real-provider.example .env
# 或
cp .env.prod.example .env
```

### Step 2：preflight（必须通过）

```bash
python scripts/preflight_env.py --env real-provider --env-file .env
# 或
python scripts/preflight_env.py --env prod --env-file .env
```

### Step 3：迁移到 head（必须通过）

```bash
alembic upgrade head
```

### Step 4：启动服务并做健康检查（必须通过）

```bash
uvicorn app.main:app
curl -fsS http://127.0.0.1:8000/health
```

### Step 5：阶段验收（prod 放行前必须通过）

```bash
python tests/run_stage_acceptance.py --suite core
python tests/run_stage_acceptance.py --suite real-smoke
python tests/run_stage_acceptance.py --suite real-acceptance
```

---

## 3. 失败分级与止损/回退路径

### A. preflight 失败

- 判定：**禁止启动**。
- 动作：修正 `.env`（模式、provider、fallback、必填 key/model/base_url），重新 preflight。

### B. migration 失败或未到 head

- 判定：**禁止启动**。
- 动作：停止后续操作；先修复迁移链路并执行 `alembic upgrade head`。
- 要求：不在未知迁移状态下继续应用。

### C. 健康检查失败

- 判定：**禁止放行**。
- 动作：回到 real-provider 联调态排查服务可用性、配置、依赖连通性。

### D. real-provider 验收失败（real-smoke/real-acceptance）

- 判定：**禁止放行 prod**。
- 动作：回到 real-provider 联调态；按失败摘要排查 provider 配置、网络、结构化输出与治理参数。

### E. prod 安全默认值不满足

- 判定：**直接拒绝启动**。
- 最小约束：`AGENT_PROVIDER != mock`、`AGENT_FALLBACK_TO_MOCK=false`、`AUTO_CREATE_TABLES=false`。

---

## 5. 放行记录与人工签署（最小口径）

### 5.1 决策记录字段（最小集）

放行记录最小字段统一为：

- `generated_at` / `decided_at`
- `env`（`real-provider` / `prod`）
- `decision`（`approve` / `reject` / `rollback`）
- `operator`
- `reason` / `notes`
- `linked_evidence_dir`
- `linked_runbook_summary_json`
- `linked_stage_acceptance_summary`
- `required_checks_status`
- `recommendation_source`（来自 `runbook_summary.json`）

### 5.2 人工签署规则（必须遵守）

1. `startup_blocked` 时，只能 `reject`，不允许 `approve`。
2. `prod_release_blocked` 时，不允许 `approve prod`。
3. 只有 `overall_result=passed` 时，才允许 `approve`。
4. `rollback` 仅用于“已执行上线动作后的回退记录”，不得与 `reject` 混用。

### 5.3 模板与入口

- 模板：`md/status/release_signoff_template.md`
- 命令入口：`scripts/release_signoff.py`

---

## 6. 演练建议（最小）

### 演练 1：preflight 失败路径

- 人为把 `AGENT_FALLBACK_TO_MOCK=true` 写入 `.env.prod`。
- 执行：

```bash
python scripts/runbook_checks.py --env prod --env-file .env
```

- 预期：返回启动阻断（exit code = 2）。

### 演练 2：迁移未就绪路径

- 在非 head 数据库上执行：

```bash
python scripts/runbook_checks.py --env real-provider --env-file .env --skip-stage-acceptance
```

- 预期：提示 migration 未到 head，并给出 `alembic upgrade head`。

### 演练 3：验收失败不放行路径

- 在联调态触发真实 provider 验收失败。
- 执行：

```bash
python scripts/runbook_checks.py --env real-provider --env-file .env --stage-suite real-acceptance
```

- 预期：返回“禁止放行 prod，回到 real-provider 联调态”（exit code = 3）。
