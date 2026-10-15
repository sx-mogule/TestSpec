# TestSpec 输出契约

> 适用于 `prd-analysis → test-points → testcase-generate → testcase-review`。

正式用例产物为 `artifacts/testcases.json` 与 `artifacts/<name>_cases.xmind`。两者参与本流程的输出校验与交付；Excel 不属于默认产物或验收门禁。

## 通用原则

- PRD 和用户确认内容是需求事实来源；不得用实现现状覆盖需求。
- 本流程产出功能测试点和用例，并允许有需求依据的埋点、兼容性矩阵测试点和用例；角色权限、边界、异常和跨功能交互须有可观察的业务结果。埋点须有明确事件触发/字段或统计口径，兼容性矩阵须有明确环境组合与验收结果；缺口进入澄清。独立 API、协议、安全攻防、性能负载及其他未授权类型不进入本流程。
- 下游产物必须保留上游 `source_revision`，不得自行修改版本。
- 如文档与导出脚本冲突，以脚本和单测为准。
- 需求口径变化时，旧下游产物必须标记为 stale 并按流程重新生成。

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

埋点用例须使用 `type=埋点` 并引用 Tracking 测试点；兼容性矩阵用例须使用 `type=兼容性矩阵` 并引用 Compatibility 测试点。两类均纳入原有 TP 覆盖率、字段、步骤、Oracle、来源与 Review 门禁。

## Smoke 执行集

- 完整集固定为 `artifacts/testcases.json`，覆盖率分母为当前 `specs/testpoints.md` 的全部 TP，沿用现有 ≥95% 门槛。
- 完整集校验为 PASS，且当前版本 Review Gate 为 `pass`、`s1_unresolved_count=0`、`s1_issue_ids=[]` 后，才调用 `testcase-generate/scripts/select_smoke.py --change-dir <变更目录>`。
- Review 的 `reviewed_artifacts` 必须记录实际评审的完整 JSON 与测试点的 SHA-256；缺少或不匹配时先重新 Review，不沿用过期结论。
- 选取条件为 `regression_tier=Smoke` 且全部为 p0，不自动把所有 p0 纳入。不存在候选或候选优先级不合法时停止，不补造或改写源用例。
- 固定输出 `artifacts/smoke-testcases.json`，顶层保持 `schema_version=2`、`_context` 和 `testcases`；`_context.artifact_kind=smoke-execution-set`，记录源文件、已评审哈希、选取规则、case/TP 范围、完整集校验及 Review 结论。完整集覆盖率仅放在 `full_set_validation.coverage` 下，不表述为 Smoke 对全部 TP 的覆盖率。
- 每条选中用例完整保留源对象与顺序，包括 ID、八项业务字段、步骤、预期、优先级和 TP 追溯；不覆盖源 JSON、测试点、Review 报告或完整 XMind。
- 按需使用现有 XMind 导出脚本生成 `artifacts/smoke-cases.xmind`，沿用同一八字段与层级契约。执行集不作为新的完整集再次送入全量覆盖校验，也不增加公开 Skill 阶段。

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

由 `testcase-review` 生成，至少包含：

- 评审模式、深度和置信度
- 覆盖、命名、优先级、字段、可执行性和追溯检查
- S1/S2/S3 问题及对应 case/TP/global 定位
- `review_gate.status`、`s1_unresolved_count`、`s1_issue_ids`

## 变更控制

修改正式 JSON 八字段或 XMind 层级时，必须同步修改生成脚本、校验器、示例和单测。若用户单独要求 Excel 附加输出并修改其格式约定，也须同步检查相应导出流程和验证材料。
