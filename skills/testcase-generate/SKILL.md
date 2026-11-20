---
name: testcase-generate
license: MIT
description: TestSpec 生成测试用例（流程第 3 步）- 根据测试点（specs/*.md）生成完整测试用例并默认导出 XMind (.xmind)。当用户要「生成用例」「写测试用例」「导出 XMind」或执行 testcase-generate / testcase generate 时使用。也适用于用户说「把测试点展开成用例」或「帮我出一份测试用例表」的场景。使用内置 Python 脚本生成 XMind 文件，不依赖外部技能。
---

# testcase-generate：用例生成

将当前测试点展开为可独立执行、可判定、可回溯的完整用例集，交付 JSON、XMind 与核心 BDD。

## 读什么

- 按 `../_testspec-shared/references/common.md` 定位变更；读适用的 `project-interaction-spec.md`、canonical 需求和 `specs/testpoints.md`。按 `../_testspec-shared/references/context-protocol.md` 核对版本。已有需求分析时先运行共享 `validate_context_chain.py --change-dir <变更目录> --through analysis` 核对规范需求指纹。TP 缺失或过期时回到 `test-points`，版本高于 canonical 时报告元数据异常。canonical 无版本按 Legacy 处理；本阶段产物过期时重新生成。
- 按 `../_testspec-shared/references/execution-efficiency.md` 复用已读材料。如当前 TestLib 索引命中模块或功能，按 `../_testspec-shared/references/source-provenance.md` 选少量可信参考用例，仅借鉴表达。来源缺少信任元数据的历史用例只参考命名和格式。

## 怎么展开

1. 依据 TP、已确认风险、用户目标及允许范围内的 `strategy.md`，按 `references/test-type-strategies.md` 选择适用策略，默认 functional。独立 API、安全、性能等类型不进入本流程；有明确口径的埋点和兼容性矩阵按对应 TP 生成，其他非功能 TP 返回 `test-points` 核定。
2. 从 `references/test-design-methods.md` 读取所选方法的完成标准，按 `references/case-granularity.md` 展开数据、动作和可观察结果。新增独立意图或更换未知方法前先更新上游。每个 `tp_refs` 引用都要有实际条件、步骤和预期。HTML 已确认按钮行为须按 `BTN_ID` 可追溯；间接 Oracle 只断言当前系统可观察产物。已确认部分继续生成，未确认预期保留上游问题及影响，回到 `prd-analysis` 澄清。以确认的业务规则为依据，不访问真实接口来推导 Oracle。
3. 名称按 `../_testspec-shared/references/naming-contract.md`，前置条件、数据、步骤和预期按 `references/case-design-rules.md`。优先级按每条用例的业务影响。回归层级取引用 TP 的最高层级（Smoke > Full > Targeted），未标注默认 Full；衍生场景可按实际风险降级，升级为 Smoke 须有用户明确要求。冒烟是完整集内分类，冒烟用例为 p0，`type=冒烟` 同时标记 `regression_tier=Smoke`。覆盖按完整范围计算。
4. 八字段、schema v2 和产物格式见 `../_testspec-shared/references/output-contracts.md`，样例见 `references/testcases-json-example.md`。用例 ID 在变更内唯一，`origin.kind=testspec-native`、`trust.status=provisional`。写入 `artifacts/testcases.json`；`_context.design_methods` 与实际引用 TP 的方法集合一致。按样例写入上下文，保留 canonical 版本、来源、风险、问题和下游待更新项，记录覆盖、迭代和实际参考的 TestLib 信息。

## 校验与交付

- 执行共享 `validate_testcases.py --input <用例 JSON> --testpoints <测试点文件> --pretty`。修复确定性错误，逐项核对 warning，TP 引用覆盖率至少 95%。相似候选交 Review H1。按 `references/generation-quality-loop.md` 核实已确认的关键条件、执行数据和断言；未决口径交还上游。
- **XMind（默认）**：运行当前 Skill 的 `scripts/generate_xmind.py --input <用例 JSON> --output <变更目录>/artifacts/<name>_cases.xmind --title "测试用例"`。随后对实际导出的路径运行共享 `verify_eval_artifacts.py xmind --json <当前用例 JSON> --xmind <实际 XMind>`。缺失或不一致时按当前 JSON 重导并复检，通过后才可交付。
- 从完整集提取核心主路径和关键异常，按共享输出契约生成 `artifacts/<name>_features.feature`。同步受返修影响的 BDD。正式三件产物齐备后，从 stale 列表移除本阶段产物，运行共享 `validate_context_chain.py --change-dir <变更目录> --through generate`。报告产物、覆盖率、优先级分布和修正摘要，下一步为 `testcase-reviewer`。

## 定向返修

收到用户明确返修请求时，先核对报告版本。只处理 `open` 且归生成阶段的 issue。用户选中的 `accepted` 描述问题由 Review 以原 ID 重开，其他上游问题交对应阶段。

只改指定字段或场景，默认保留用例 ID；四项描述精简应保留必要条件和 Oracle。H5 指定缺失分支且已有 TP 时只补该分支。仅涉及 BDD 时按文件和场景修订。JSON 返修写入 `_context.review_repairs`，记录 issue、受影响用例和摘要；BDD 专属返修在反馈中记录 issue 和场景。JSON 变化时重新导出并比对 XMind。校验受影响的产物，由 Review 对同一 issue 裁定状态并刷新实际评审指纹。
