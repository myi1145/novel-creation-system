# Release Signoff 模板（最小闭环）

> 用途：记录“谁基于哪份运行期证据做了什么放行决策”，不引入审批系统。  
> 输出建议：通过 `scripts/release_signoff.py` 自动生成 `release_signoff.json` + `release_signoff.md`。

---

## 1. 决策元信息

- generated_at:
- decided_at:
- env: `real-provider | prod`
- decision: `approve | reject | rollback`
- operator:

## 2. 决策说明

- reason:
- notes:

## 3. 证据关联

- linked_evidence_dir:
- linked_runbook_summary_json:
- linked_stage_acceptance_summary:

## 4. 必要检查状态（required_checks_status）

- preflight:
- migration:
- health:
- stage-acceptance:

## 5. 推荐来源（recommendation_source）

- source_file: `runbook_summary.json`
- overall_result: `passed | startup_blocked | prod_release_blocked`
- recommended_action:

## 6. 人工签署口径（最小规则）

1. `overall_result=startup_blocked`：只允许 `reject`，不允许 `approve`。
2. `overall_result=prod_release_blocked`：不允许 `approve prod`。
3. 仅当 `overall_result=passed` 时允许 `approve`。
4. `rollback` 仅用于“已执行上线动作后”的回退记录，不与 `reject` 混用。
