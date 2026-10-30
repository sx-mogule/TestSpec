# TestSpec 输出契约

> 适用于 `prd-analysis → test-points → testcase-generate → testcase-reviewer`。

正式用例产物为 `artifacts/testcases.json` 与 `artifacts/<name>_cases.xmind`。两者参与本流程的输出校验与交付；Excel 不属于默认产物或验收门禁。

## 通用原则

- PRD 和用户确认内容是需求事实来源；不得用实现现状覆盖需求。
- 本流程产出功能测试点和用例，并允许有需求依据的埋点、兼容性矩阵测试点和用例；角色权限、边界、异常和跨功能交互须有可观察的业务结果。埋点须有明确事件触发/字段或统计口径，兼容性矩阵须有明确环境组合与验收结果；缺口进入澄清。独立 API、协议、安全攻防、性能负载及其他未授权类型不进入本流程。
- 下游产物必须保留上游 `source_revision`，不得自行修改版本。
- 如文档与导出脚本冲突，以脚本和单测为准。
- 需求口径变化时，旧下游产物必须标记为 stale 并按流程重新生成。

## 报告模板与输出规范的统一入口

所有报告先按本文件选择格式，再读取对应共享模板；不在各 Skill 内维护平行模板。下表路径均相对于 `_testspec-shared/`：

| 报告类型 | 模板与规范 | 生成报告的保存位置 |
|---|---|---|
| 需求分析报告 | `templates/requirements-analysis-template.md` | 当前变更目录的 `requirements-analysis.md` |
| TestSpec 统一评审报告 | `templates/review-report-template.md` | 当前变更目录的 `review-report.md` |
| 通用测试用例/套件评审 | `templates/testcase-review-report-template.md` | TestSpec 输入齐全时汇入当前变更目录的 `review-report.md`；其他材料仅在用户要求保存时按指定位置写文件，否则在对话中输出 |
| BDD 评审与正式报告 | `references/bdd-output-contracts.md`；正式报告另读 `references/bdd-report-rubric.md` 和 `templates/bdd-review-report-template.md` | TestSpec 输入齐全时汇入当前变更目录的 `review-report.md`；其他材料仅在用户要求保存时按指定位置写文件，否则在对话中输出 |

`_testspec-shared/` 仅维护模板、规范与工具，不保存每次执行生成的报告。表中的模板与规范路径以共享目录为基准；从具体 Skill、内部模块或本文件的链接读取时，按实际相对路径定位，不能把模板路径当作产物保存路径。

同一轮评审汇总为一份报告。TestSpec 输入齐全时，以统一评审模板为外层结构，把通用或 BDD 评审结果填入“两部分评审执行记录”及相应检查项，保留原始发现、等级、依据与处置，不用通用/BDD 模板替代原 14 项检查。输入不足时按适用的通用/BDD 格式报告可核实发现，同时记录两部分完成状态和 SOP 缺项；不补造 TP、context、版本或 Gate 通过结论。通用评审能力无需先具备 TestSpec 产物。

单独分发 `testcase-reviewer` 时须携带同级 `_testspec-shared/`，模板始终引用这一份共享资源，不回退到 Skill 内的旧副本。

共享存放不改变评审能力边界：通用用例和 BDD 评审沿用各自的判定依据及 Critical/High/Medium/Low 等级；TestSpec 的范围、版本、TP 与 Gate 约束只作用于 SOP 部分，不能用它们过滤或改写通用评审的发现。

## requirements.md

由 `prd-analysis` 根据用户提供的 PRD 或需求片段整理，至少包含：

- 需求来源
- 用户角色和用户故事
- 带 `REQ-001` 编号的需求及可观察验收条件
- 范围、边界和风险
- 阻塞澄清项与执行期跟进项
- 需求质量结论

可交互 HTML 作为需求输入时，保留页面与按钮清单、逐项点击的观察记录及未覆盖原因；点击现象与已确认的需求预期分别标注。

缺少验收条件的内容不得写成已确认功能，应进入风险或澄清项。

## requirements-analysis.md

由 `prd-analysis` 生成，保持可读的 Markdown，至少包含：

- 需求来源和分析摘要
- 已确认行为、边界、异常、状态和集成风险
- 阻塞问题和建议
- 可交互 HTML 来源的按钮覆盖摘要与未覆盖清单（若适用）
- `testspec-context` 元数据

分析结论必须能追溯到 PRD、REQ 或用户确认内容。

## specs/testpoints.md

由 `test-points` 生成，至少包含：

- `# 测试点：<被测对象>`
- 模块和子模块命名字典
- 按模块、子模块组织的测试点
- 每条测试点的 `TP_ID`、验证要点、优先级、Oracle 状态和关联需求
- `testspec-context` 元数据

测试点只描述“验证什么”，不得写操作步骤和具体测试数据。

## artifacts/testcases.json

由 `testcase-generate` 生成：

```json
{
  "schema_version": 2,
  "_context": {},
  "testcases": []
}
```

每条用例必须包含八项业务字段：

1. `module`：模块
2. `submodule`：子模块
3. `test_name`：测试名称
4. `preconditions`：前置条件，可为空字符串
5. `test_data`：测试数据，可为空字符串
6. `steps`：按序号输出的操作步骤
7. `expected_result`：按序号输出的预期结果
8. `priority`：仅允许 `p0`、`p1`、`p2`

内部追溯字段可包含 `id`、`tp_refs`、`type`、`regression_tier`、`origin` 和 `trust`；兼容旧数据时可保留 `title` 和 `feature`，但不得替代八项业务字段。

`test_name` 的场景部分须简短、直白、见名知意，统一遵循 `naming-contract.md`；JSON 与 XMind 表达同一测试意图，`title` 兼容别名与 `test_name` 同步。XMind 仅剥离分类前缀，不自动截断或改写场景名称。

`type=冒烟`、`regression_tier=Smoke` 和 `priority=p0` 是完整集内的场景分类元数据。它们不缩小生成或覆盖范围，也不触发独立 JSON/XMind 产物；所有场景统一交付在 `artifacts/testcases.json` 和对应的完整集 XMind 中。

埋点用例须使用 `type=埋点` 并引用 Tracking 测试点；兼容性矩阵用例须使用 `type=兼容性矩阵` 并引用 Compatibility 测试点。两类均纳入原有 TP 覆盖率、字段、步骤、Oracle、来源与 Review 门禁。

## 可选 Excel 格式约定（不参与默认验收）

Excel 不属于默认正式产物或任何阶段的生成、格式校验、覆盖率及 Review 门禁。只有用户单独明确要求，且当前工作区已有明确可用的导出流程时，才可作为附加格式处理；本约定不构成 Excel 导出实现。若处理，工作表 `测试用例` 的列头固定为：

1. 模块
2. 子模块
3. 测试名称
4. 前置条件
5. 测试数据
6. 操作步骤
7. 预期结果
8. 优先级

## XMind 输出契约

默认生成 XMind 8 格式：

- 层级：`模块 → 子模块 → 用例名称`。XMind 用例节点只显示用例名称，不重复模块或子模块；JSON 中 `test_name` 保持完整命名。导出时剥离与父节点精确匹配的 `{模块}_{子模块}_` 前缀；兼容输入若已是纯用例名称则原样显示。缺少用例名称，或输入使用三段式名称但前缀与父节点不匹配时，拒绝导出，避免空节点或错误归类。
- 详情层级：
  ```text
  用例名称
  ├── 前置条件：\n<内容>
  ├── 测试数据：\n<内容>
  └── 操作步骤：\n<编号步骤>
      └── 预期结果：\n<编号预期>
  ```
- 上述 `\n` 表示同一个节点标题中的实际换行：标签独占第一行，内容从第二行开始。前置条件、测试数据、操作步骤是测试名称的同级子节点；预期结果仅是操作步骤的子节点，不另建内容节点。
- 前置条件和测试数据为空时不创建对应节点
- 操作步骤为空而预期结果非空时拒绝导出；多条步骤和预期按编号保留在各自的单个节点中
- `p0` 不标记，`p1` 使用 1 号 marker，`p2` 使用 2 号 marker
- 不生成优先级文本节点

## review-report.md

由 `testcase-reviewer` 生成，至少包含：

- 评审模式（Import-Quarantine/Provenance-Unknown/Strict/Legacy）、深度（标准/加深）、触发原因和置信度
- R1-R6、H1-H8 共 14 项检查矩阵与总体结论
- 覆盖、命名、优先级、字段、可执行性和追溯检查
- S1/S2/S3 问题列表；每项带稳定 issue ID、`open/resolved/accepted` 状态、`case_id`/`TP_ID`/`GLOBAL:<rule>`、owner、影响和建议
- 前置条件、测试数据、操作步骤、预期结果的四行检查结果及对应问题 ID；问题给出原文、原因和可直接替换的短句
- `review_gate.status`、`s1_unresolved_count`、`s1_issue_ids`、`description_unresolved_count`、`description_issue_ids`
- `reviewed_artifacts`：实际评审完整 JSON 与测试点的 SHA-256，用于标识评审对应的产物

新执行的统一评审必须记录通用评审与SOP检查两部分的执行状态、来源依据、原等级、原始发现与逐项处置；任一部分未完成时说明原因，不提供未启用选项。协同规则由 `skills/testcase-reviewer/testcase-review/references/independent-reviewer.md` 定义，由统一入口执行，通用评审能力与原SOP检查规则均保留。发现经证据复核后关联原生 issue ID；同一问题只计一次，不机械换算严重度，也不增加或替换现有 Gate 字段/公式。历史报告保持兼容，不补造协同记录。

四项描述门禁与 S1 门禁同时生效：逐条检查完整用例集的四个字段，只有未解决 S1 和四项描述问题均为 0、两个 ID 列表均为空，`review_gate.status` 才能为 `pass`。`description_unresolved_count` 为非负整数，必须等于去重后的 `description_issue_ids` 数量；ID 必须是非空字符串并指向报告中的问题。

四项描述问题按现有 R5/H2/H3/H4/H6 分级，仍可为 S2/S3；严重度不代替门禁结论。确认的套话、重复背景、无关配置/操作/检查或含糊表达均进入描述问题列表，不能仅以“建议优化”放行；其他 S2/S3 不因此新增阻断。每项给出 `case_id`、字段、原文、原因和可直接替换的建议，只有复审确认 resolved 后才移出；`accepted` 仍计入未解决描述问题，不能豁免本门禁。用户明确按报告修复且范围包含该项时，由 Review 先以原 issue ID 重开为 `open`，保留严重度、定位、owner 和计数/ID；Generate 只消费 `open` 且 owner 为 generate 的 finding。未纳入范围的 accepted 项保持 accepted 并继续阻断。返修后 Review 对完整集复核同一 ID、按原公式重算并刷新两个 SHA-256；旧哈希不再代表已改变的用例集。

未完成四项检查时，记录 `GLOBAL:description-review-incomplete` 范围的问题并保持 `blocked`，不得填 0 假装通过。旧报告缺少描述门禁字段时必须重新 Review，不自动补通过。脚本校验能检查字段、计数和门禁的一致性，不能代替文案语义评审；合法的 `blocked` 报告通过上下文校验也不代表用例获准交付。

需求去向表用于记录原文位置→REQ→TP→用例→可观察 Oracle 的对应关系，不改变现有分级或 Gate 公式。原始需求材料未提供时，只能声明核对 canonical 需求文件；已确认且在范围内但缺少 TP、用例或可判定 Oracle 的需求应记为覆盖缺口，不得以待澄清/范围外掩盖。

### 评审完成后的对话摘要

```text
✅ 评审完成 | 模式: <Import-Quarantine/Provenance-Unknown/Strict/Legacy> | 深度: <标准/加深> | 置信度: <高/中/低>
📄 报告: testspec/changes/<name>/review-report.md
📊 总评: <S1> 个 S1 + <S2> 个 S2 + <S3> 个 S3 | 未解决四项描述问题: <count> | Gate: <pass/blocked>
```

两部分未完成时如实写明状态和缺项，不能使用“评审完成”作为通过承诺；摘要中的路径使用本次报告的实际保存位置。

## 变更控制

修改正式 JSON 八字段或 XMind 层级时，必须同步修改生成脚本、校验器、示例和单测。若用户单独要求 Excel 附加输出并修改其格式约定，也须同步检查相应导出流程和验证材料。
