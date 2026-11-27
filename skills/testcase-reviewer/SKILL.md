---
name: testcase-reviewer
description: 评审测试用例、套件和 BDD/Gherkin，也用于 TestSpec 第四阶段。对照需求找覆盖和判定缺口，单次执行 SOP 的 14 项检查（M 机器层取脚本结果，判断力集中在 J 判定力层与 D 描述层）并给出 Review Gate。也支持按需评分、改写和 BDD 起草。
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

一次评审、一套编号：同一模型按下列五步走完一轮，判断这套用例和伴生 BDD 能否在需求范围内拦住错误实现，发现直接登记为 issue。

0. **准入。** 检查输入完整性，确定来源模式和深度，运行共享 `validate_testcases.py` 与 `validate_context_chain.py`。M 机器层（M1 覆盖与追溯、M2 字段与格式、M3 优先级分布、M4 相似候选、M5 来源与版本）直接引用脚本结果，不人工重算。
1. **建必测清单。** 先不看 TP，只依据当前 PRD、验收条款、已确认澄清和适用项目规范，列出每条规则或分支的“条件 → 可观察结果”。原件缺失时用 canonical 需求，说明依据和限制；验收规则冲突或含糊时列待确认项。仅有测试稿时，检查结构、可执行性和内部一致性。
2. **逐项判定（J 判定力层，主要工作量）。** 每个必测项对照 TP、用例和 BDD，回答“实现错成 X，会变红吗”：J1 漏测、J2 拦不住（含对生成阶段判定力自检的反事实抽查）、J3 偏题（意图、方法落地、类型范围）、J4 口径未定。结果写入需求判定力表。
3. **用例质量（D 描述层）。** 完整集逐条检查四项描述门禁 D1 前置条件、D2 测试数据、D3 操作步骤、D4 预期表述，D5 复核命名、相似候选与粒度；伴生 BDD 按下方规则逐个场景核对，BDD 问题同样按编号登记，定位到 feature 路径和场景，归生成阶段。
4. **裁定。** 写评审执行记录、需求判定力表、问题清单和 14 项矩阵，计算 Gate。任意层未解决的 S1、J1–J4 任意等级、D1–D4 任意等级（含 accepted）都阻断。材料不足时完成有据可查的检查，说明缺项和结论限制；SOP 输入健康检查失败时评审状态为未完成，Gate 未计算。

各编号的判定标准、默认等级和两条边界规则见 [维度细则](testcase-review/references/review-dimensions.md)，执行细节见 [SOP 模块](testcase-review/review-workflow.md)。每个问题只登记一次，issue ID 不含等级（如 `RV-007`），写明编号标签、定位、依据、会逃逸的行为或原因、建议和 owner。

按 [输出契约](../_testspec-shared/references/output-contracts.md) 选模板。完整 TestSpec 输入写入当前变更的 `review-report.md`，记录 Gate 和实际评审的 JSON、TP、全部 BDD 指纹。评审以只读方式使用正式产物，定向返修交给责任阶段。普通材料仅在用户要求保存时写文件。新报告的 `source_skill` 为 `testcase-reviewer`，旧报告可兼容读取 `testcase-review`。此目录只有一个 Skill 入口，单独分发须同时携带同级 `_testspec-shared/`。

### 单独评审的发现分级

以下等级只用于未进入 TestSpec SOP 的普通用例、套件或 BDD 评审（编号 `GR-001` 起）；SOP 评审统一使用 S1/S2/S3，两套等级不在同一份报告中互相映射。

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
