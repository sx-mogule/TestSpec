---
name: testcase-reviewer
description: 评审测试用例、套件和 BDD/Gherkin，也用于 TestSpec 第四阶段。对照需求找覆盖和判定缺口，保留通用反馈，执行 SOP 的 14 项检查并给出 Review Gate。也支持按需评分、改写和 BDD 起草。
metadata:
  version: 2.0.0
  dispatcher-category: testing
  dispatcher-layer: feedback
  dispatcher-lifecycle: active
  dispatcher-risk: low
  dispatcher-writes-files: true
  dispatcher-capabilities: test-case-review, test-suite-review, test-case-scoring, test-design-mentoring, bdd-review, bdd-rewrite, bdd-generation
  dispatcher-accepted-intents: review_test_cases, score_test_cases, mentor_test_case_quality, review_bdd_test_cases, rewrite_bdd_test_cases, generate_bdd_test_cases
  dispatcher-input-artifacts: test_cases, test_suite, traceability_matrix, bdd_feature, requirements, acceptance_criteria, business_rules, example_map
  dispatcher-output-artifacts: review_findings, scored_review, mentoring_feedback, rewritten_artifact, bdd_feature
  dispatcher-stack-tags: testing, test-design, review, bdd, gherkin
---

# 测试用例评审器

## 统一评审

1. **先核对需求依据。** 有当前 PRD、验收条款或已确认的澄清原文时，先从原文定位关键业务路径、明确必测的条件与可观察结果，再对照测试稿。原件缺失时用现有的 canonical 需求、验收标准或获批资料，说明依据和限制。按适用项目规范核实交互和默认边界；已提供的原型记录、实现证据和历史用例可帮助发现差异。验收规则冲突或含糊时列待确认项。仅有测试稿时，检查结构、可执行性和内部一致性。
2. **先完成通用评审。** 按下方材料路径核对完整测试稿。标准 SOP 同时审完整 JSON 和全部伴生 BDD，BDD 单独核查场景质量和关键规则。每项发现保留稳定 GR 编号、原等级、定位、依据、影响和建议。通用反馈先形成，再进入 SOP，依据来自本轮实际材料。
3. **再做 SOP 检查。** 同一模型执行 [内部 SOP 模块](testcase-review/review-workflow.md)，核对输入并完成 R1–R6、H1–H8。按 [发现处置规则](testcase-review/references/independent-reviewer.md) 复用首轮已核实的原文和用例证据，补查未覆盖的维度，独立判断 SOP 分级及 Gate。关键分支和结果判定按 [H3/H5 细则](testcase-review/references/review-dimensions.md) 处理。
4. **汇总报告。** 完整展示通用反馈，再列 SOP 结论、BDD 场景评审和逐项处置。整轮完成要求两部分和必需的 BDD 评审完成、每项发现有处置。材料不足时，完成有据可查的检查，说明缺项和结论限制。若 SOP 输入健康检查失败，状态为未完成，Gate 未计算。

按 [输出契约](../_testspec-shared/references/output-contracts.md) 选模板。完整 TestSpec 输入写入当前变更的 `review-report.md`，记录 Gate 和实际评审的 JSON、TP、全部 BDD 指纹。评审以只读方式使用正式产物，定向返修交给责任阶段。普通材料仅在用户要求保存时写文件。新报告的 `source_skill` 为 `testcase-reviewer`，旧报告可兼容读取 `testcase-review`。此目录只有一个 Skill 入口，单独分发须同时携带同级 `_testspec-shared/`。

### 通用发现分级

| 等级 | 判定 |
|---|---|
| Critical | 核心行为错误或矛盾、整项需求无覆盖，或判定依据缺失到无法信任结论 |
| High | 容易误导执行或签核，例如必要错误路径缺失、关键结果不可观察、分支混在一个场景中 |
| Medium | 影响局部质量，例如条件表达不清或场景承担了过多细节 |
| Low | 措辞、命名或元数据等低影响问题 |

Critical 和 High 引用具体原文及受影响的需求、用例或场景。没有实质性缺陷时，如实记录已审范围和证据。

## 选择材料路径和模式

默认 `review`。用户要求时可评分、辅导或进入 `rewrite` / `hybrid`，先评审，再提供与发现逐项对应的修订。仅 BDD 支持 `generate`，依据业务规则、验收标准或示例映射起草。本项目从零设计传统用例按需求分析、测试点、用例生成进入 SOP。改写或起草产物形成后，按可用输入完成评审。执行范围以用户指定的材料为准。

### 测试用例与套件

- 按 `references/test-cases/review-workflow.md` 检查需求追溯、适用的成功/扩展/错误路径、技术正确性和套件结构。
- 涉及字段或分组的具体判断时，分别读取该目录的 `test-case-protocol.md` 或 `test-suite-protocol.md`。校准反馈可查同目录的质量、评论、报告和薄弱输入示例。
- 单独出具普通用例评审时使用 `../_testspec-shared/templates/testcase-review-report-template.md`。标准 SOP 直接汇入统一模板。

### BDD / Gherkin

- 按 `references/bdd/review-workflow.md` 评审。用业务语言表达规则，每个场景一条行为路径，`When` 一个主要事件，`Then` 给出外部可观察的结果。完整 SOP 中按相同业务条件对照 JSON 与 BDD 的关键结果，出现分歧时回到需求原文判定。
- 任务或依据不清时读 `references/bdd/intake-and-decision-flow.md`。核对语义、结构或改写时，按需读 `references/bdd/quality-rules.md`、`references/bdd/feature-and-scenario-protocol.md`。
- 起草或改写完整特性文件可用 `assets/bdd-feature-template.feature`。各模式输出见 `../_testspec-shared/references/bdd-output-contracts.md`，评分或单独正式报告按共享输出契约加载评分规则和模板。示例见 `examples/bdd/`。
