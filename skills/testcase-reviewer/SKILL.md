---
name: testcase-reviewer
description: 统一测试用例评审入口，也是TestSpec流程第4步。每次执行通用用例/套件/BDD评审与SOP原有R1-R6、H1-H8共14项检查，逐项核实发现并汇总报告及Review Gate；支持评分、辅导和按用户要求改写或起草BDD。输入不足时给出可核实的评审及缺项，不补造需求、TP或通过结论。不从零设计传统测试用例或编写自动化代码。
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

> **版本：** 2.0.0 | **许可证：** MIT

像资深测试设计人员一样评审测试稿：对照事实来源，先列发现，并提供可执行的具体建议。此 Skill 涵盖两类遵循相同评审原则的材料：传统测试用例与 BDD/Gherkin。

## 统一执行顺序（每次调用均执行）

输出报告前，先读取 `../_testspec-shared/references/output-contracts.md` 的报告路由与保存规则，再按材料类型读取共享模板。本 Skill 的报告模板与输出规范统一由同级 `_testspec-shared/` 提供；单独分发时需同时携带该共享目录。

本目录只有 `$testcase-reviewer` 一个入口。`testcase-review/review-workflow.md` 是保留原 `testcase-review` 能力的内部模块，不再独立调用；没有“仅通用”或“仅SOP”开关。

1. **通用评审**：按下面的材料类型与模式，基于需求、验收标准和完整测试稿形成发现，保持 `Critical/High/Medium/Low` 等级。优先从原始材料独立判断，不先读取旧Gate或预设结论。
2. **SOP检查**：必读 `testcase-review/review-workflow.md`，执行输入健康检查和原有R1-R6、H1-H8。模板为 `../_testspec-shared/templates/review-report-template.md`，细则为 `testcase-review/references/review-dimensions.md`；按风险决定auto或加深，不跳过任何检查维度。
3. **统一汇总**：按 `testcase-review/references/independent-reviewer.md` 逐项复核两部分发现，记录原等级、依据、处置和原生issue ID。同一问题只计一次；不机械换算等级。只有两部分均完成才可宣称整轮完成。

TestSpec输入齐全时，统一写 `review-report.md`，沿用原S1与四项描述Gate公式，并记录完整JSON/TP指纹；评审不改写正式JSON或XMind。缺少需求、TP、来源或版本等必需输入时，仍完成通用评审及可判定的R/H检查，列出14项中无法完成的项和具体缺失材料，SOP状态为“未完成”，不伪造context、TP或Gate通过结果。普通用例与BDD的原有评审能力因此保留，无需先补造SOP产物。

BDD的rewrite/generate/hybrid模式仍按原规则产出材料；随后对可评审的草稿执行上述两部分检查。输入不支持某项检查时明确记录限制。普通材料仅在用户要求保存时写文件；TestSpec完整输入按流程写统一报告。

旧报告的 `source_skill: testcase-review` 仅作为历史来源标识兼容读取，新报告使用 `source_skill: testcase-reviewer`。单个模型顺序执行两套规则不称为独立评审者或多模型复核。

## 1. 判断材料类型和模式

**材料类型**

| 类型 | 材料 | 参考目录 |
|---|---|---|
| 测试用例 | 带有前置条件、步骤和预期结果的手工、UAT 或回归测试用例；测试套件及其层级；需求到测试的追溯矩阵 | `references/test-cases/` |
| BDD | Gherkin 特性文件、场景、Scenario Outline（场景大纲）、`Rule:` 规则块、示例映射 | `references/bdd/` |

若输入同时包含两类材料，分别按各自路径评审，再合并成一份报告。

**模式**

- `review`（默认，适用两类）：评估并排列发现；用户要求时评分。
- `rewrite`（适用两类）：在保留原意的前提下改进材料。测试用例路径须先完成评审，再提出修订用例，且每项修订都要关联到明确的问题。
- `generate`（仅适用 BDD）：根据业务规则、验收标准、用户故事或示例映射起草 Gherkin。从零设计传统测试用例应使用 `test-design-orchestrator`。
- `hybrid`（适用两类）：先简要列出发现，再给出修订后的材料。

模式不明显时，在回复开头说明材料类型和模式。除非用户要求更多内容，否则保持在评审模式。

## 2. 确立判定依据

仅依据事实来源判断正确性，按可信度从高到低排列：

1. 已批准的业务规则和需求
2. 验收标准
3. 用户故事、用例、分析文档
4. 利益相关方批准的备注、用户手册
5. 材料自身的文字（最弱，只能用于检查其内部一致性）

始终遵循：

- 写明所依据的来源，并评为强、部分或弱；
- 区分已确认行为与假设；
- 缺少需求时，仍可检查结构和质量，但要标明追溯与覆盖结论受限，并列出完成全面评审还需要什么。

禁止：

- 将实现代码作为主要判定依据，除非用户明确要求检查代码与测试是否一致（照着代码编写的测试，可能在业务规则错误时仍然通过）；
- 臆造需求 ID、角色、标签、优先级、业务规则、策略限制或框架语义。缺失的元数据应作为缺口报告。

## 3. 使用统一等级评定发现

| 严重度 | 含义 |
|---|---|
| `Critical`（严重） | 被测行为错误、矛盾、缺失，或含糊到无法信任；某项需求完全没有覆盖 |
| `High`（高） | 可能误导执行、自动化、评审或签核，例如缺少反向或错误路径、预期结果不可观察、一个场景混合多条规则分支 |
| `Medium`（中） | 影响范围有限的真实质量问题，例如一个预期结果较弱、标题过于笼统而隐藏了条件、场景可读但内容过载 |
| `Low`（低） | 措辞、可读性、命名、元数据或低风险清理项 |

每条 Critical 和 High 发现都要引用依据，并指出受影响的需求、套件、用例或场景。优先写 `REQ-04 has no negative-path coverage`（REQ-04 缺少反向路径覆盖），而不要只写“增加更多测试”。材料质量良好时，应写 `No material defects identified`（未发现实质性缺陷），不要为了找问题而臆造缺陷。

## 4. 测试用例评审路径

完整流程见 `references/test-cases/review-workflow.md`。仅在任务需要时加载其他资料：

- 判断标题、前置条件、步骤、预期结果或优先级时，读取 `test-case-protocol.md`；
- 涉及套件、文件夹、层级或重复时，读取 `test-suite-protocol.md`；
- 编写最终评审时，读取 `../_testspec-shared/templates/testcase-review-report-template.md`；
- 校准优劣示例时，读取 `examples-test-case-quality.md`、`examples-review-comments.md`、`examples-mini-review-reports.md`、`examples-bad-input-artifacts.md`。

工作流程：

1. **范围与清点。** 明确范围是仅需求、仅用例、用例加套件，还是完整材料包。统计需求、用例和套件数量，并列出缺少的材料。
2. **需求与追溯。** 将每项需求标记为清晰、含糊或缺少细节。把需求映射到用例，指出未覆盖项。
3. **套件结构**（如适用）。层级宜为组件或测试级别 → 测试类型 → 判定依据或需求单元。若底层套件超过约 20 条用例，指出可拆分之处；也要指出容易造成重复用例的结构。
4. **覆盖。** 每项需求至少有一条测试。适用时应覆盖主成功路径（MSS）、扩展路径（EXT）和错误路径（ERR）。覆盖薄弱时，指出缺失的设计方法：用等价类划分输入类别，用边界值分析检查限值，用决策表分析规则组合，用状态转换分析状态驱动行为，用用例路径分析参与者流程。
5. **技术正确性。** 前置条件应建立所需状态，包括不直观的状态。步骤须可执行且确定。预期结果应具体、可观察，例如 UI 提示、API 状态码和响应体、数据库记录、事件或文件，不能只写 `Success` 或 `OK`。测试数据应描述所需状态（如“一个没有待处理订单的有效用户”），而不是硬编码易失效的 ID；还应覆盖边界和无效输入。
6. **规范符合性。** 检查命名、必填字段、追溯链接、MSS/EXT/ERR 分类，以及适用时的测试级别或优先级。
7. **辅导。** 总结优点和重复出现的问题，并按影响排序给出 3 至 5 条建议。

按 `../_testspec-shared/templates/testcase-review-report-template.md` 组织通用评审内容，并按共享输出契约汇入本轮报告。若无法验证追溯，应说明限制；建议必须具体到下一步可执行的行动。

发现及修复示例：

```text
High：REQ-07 仅由一条成功路径用例覆盖。需求还定义了无效账户状态，但没有 ERR 场景检查账户是否已停用或关闭。
修复：针对账户状态的等价类划分，增加两条 ERR 用例（一条针对停用账户，一条针对已关闭账户）。
验证拒绝提示，并确认账户余额未发生变化。
```

## 5. BDD 评审路径

将 BDD 视为面向业务的行为规格，而非 UI 操作脚本。按需读取以下资料：

- 请求、判定依据或模式不明确时，读取 `references/bdd/intake-and-decision-flow.md`；
- 进行正式评审或先列发现时，读取 `references/bdd/review-workflow.md`；
- 检查反模式和改写方法时，读取 `references/bdd/quality-rules.md`；
- 检查 `Feature:`、`Rule:`、`Background:`、`Scenario Outline`、标签和命名时，读取 `references/bdd/feature-and-scenario-protocol.md`；
- 评分或撰写正式报告时，读取 `../_testspec-shared/references/bdd-report-rubric.md` 和 `../_testspec-shared/templates/bdd-review-report-template.md`；
- 需要严格输出格式时，读取 `../_testspec-shared/references/bdd-output-contracts.md`。

约束：始终优先描述业务行为，而非 UI 操作过程；每个场景只覆盖一条行为路径；`When` 中只保留一个主要事件；`Then` 应是外部可观察的结果；`Given` 应尽量精简且足够；使用来源支持的具体业务示例；明确保留追溯关系。不要在 Gherkin 中叙述测试脚本，不要在一个场景混合多条规则分支，也不要添加行为本身不需要的实现细节。

- **`review`：** 评估意图与范围、追溯、场景结构（命名、分组、重复）、路径覆盖（主路径、替代路径、错误路径，以及适用时的角色、权限、边界或生命周期），以及 BDD 质量（业务语言、可观察结果、具体示例、不包含 UI 脚本和混合分支）。先列发现。
- **`rewrite`：** 保留原意；将场景标题改为条件加结果；拆分过载场景；除非 UI 交互本身就是规则，否则以业务行为替换 UI 步骤；将含糊结果改成可观察结果；将无依据的元数据明确记录为缺口。完整特性文件使用 `assets/bdd-feature-template.feature`。
- **`generate`：** 从规则、决策和示例开始，将规则空间映射到主路径、替代路径和错误行为；每条行为路径或规则分支对应一个场景；使用具体角色、日期、状态和金额。只生成来源支持的行为，并列出未解决的缺口；来源信息不足时停止。
- **`hybrid`：** 先列最重要的发现，再给出改进后的材料，最后列出未确认的假设。

各模式的回复结构统一读取 `../_testspec-shared/references/bdd-output-contracts.md`；正式报告按共享报告路由选择模板。示例见 `examples/bdd/`。

## 6. 处理薄弱输入

- **判定依据较弱：** 评审结构和质量，降低可信度，避免断言正确性，并请用户提供权威来源。
- **套件层级不清楚：** 根据现有分组进行分析，对照套件规范，建议更清晰的结构。
- **预期结果笼统：** 用可观察的方式重述问题，并指出缺少哪个断言目标。
- **单个特性或套件范围过大：** 建议按能力、规则集、角色或生命周期阶段拆分。
- **用户要求改写，而非仅评审：** 先完成评审，再改写；每项改动都要关联到一条发现。

## 7. 易错点

- **只关注成功路径：** 不要停留在主成功路径；检查扩展、错误、状态转换和边界覆盖。
- **自动化交接：** 除非用户明确要求，否则不编写 Cucumber、Playwright 或 Cypress 代码；这属于对应框架 Skill 的职责。
- **过度修正：** 对质量良好的材料，应写 `No material defects identified`（未发现实质性缺陷），不能臆造问题。
- **写得好不代表行为正确：** 必须依据事实来源核对行为，而不能只看结构。
- **避免范围蔓延：** 只评审用户指定的内容。用户只问两个场景时，不要生成完整特性文件。

## 8. 文件与记忆

在对话中保留工作笔记。TestSpec完整输入按统一执行顺序保存报告；其他材料只有用户要求保存报告、评分表或改写后的材料时才写入文件，并保存到用户指定的位置。

## 9. 最终检查

1. 每条重要结论都有材料依据。
2. 每个覆盖缺口都关联到明确的需求、路径、规则或状态。
3. 建议具体到无需猜测即可执行。
4. 将必须修复的问题与辅导建议分开。
