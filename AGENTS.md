# AGENTS.md

## Hard constraints
- 必须严格遵循 V1 文档，不得另起一套架构
- Canon / Story State 是系统中枢
- Canon 只能通过 ChangeSet 写入
- 主链必须是：目标 -> 蓝图 -> 场景 -> 草稿 -> Gate -> ChangeSet -> Publish
- Agent 是受控执行者，不是系统中枢
- 多题材走：通用底座 + 题材配置层 + 规则包
- 只能增量修改，不得重写整套系统

## Working rules
- 先审计，再改代码
- 先计划，再实现
- 一次只改一个高价值模块
- 修改后必须说明影响范围和验证方法

## Required docs
在进行任何代码修改之前, 请按照以下的顺序阅读位于 /md 目录下的这些文件:
1. 小说多Agent系统最终架构设计文档_V1.md
2. Story_State_Canon_State_状态模型设计_V1.md
3. 结构化创作对象 Schema 设计_V1.md
4. 章节循环工作流说明_V1.md
5. 多层质量闸门设计_V1.md
6. 题材配置层与规则包设计_V1.md
7. Prompt_设计说明_V1.md
8. 结构化输出解析与容错规范_V1.md
9. API_接口与服务边界说明_V1.md
10. 数据库与存储设计_V1.md
11. 字段命名与对象映射总表_V1.md
## Current stage docs（任务前优先阅读）
在遵循上述 V1 文档顺序的基础上，进行当前阶段任务前请优先补充阅读：
1. md/status/current_stage_handoff.md
2. md/next_stage_decision_release_readiness/00_发布前一致性验收与章节发布准入候选方向与问题定义.md
3. md/next_stage_decision_release_readiness/01_发布前一致性验收与章节发布准入方向确认.md
4. md/next_stage_decision_release_readiness/02_发布前一致性验收与章节发布准入阶段目标与边界.md
5. md/next_stage_decision_release_readiness/03_发布前一致性验收与章节发布准入MVP范围.md
6. md/next_stage_decision_release_readiness/04_发布前一致性验收与章节发布准入任务拆解与轮次规划.md

> 历史参考：文本级人工修订闭环阶段决策链保留在 `md/next_stage_decision/`，蓝图级人工修订阶段决策链保留在 `md/next_stage_decision_blueprint_revision/`，场景级人工修订阶段决策链保留在 `md/next_stage_decision_scene_revision/`，下游依赖失效与重跑治理阶段决策链保留在 `md/next_stage_decision_dependency_recompute/`，均用于追溯，不作为当前阶段主入口。
