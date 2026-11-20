---
name: test-points
license: MIT
description: TestSpec 测试点（流程第 2 步）- 从需求分析中提炼「要测什么」的简短要点清单，产出 specs/testpoints.md。当用户要「写测试点」「提取测试要点」「列出要验证的内容」或执行 test-points / test points 时使用。也适用于用户说「这个功能要测哪些点」「帮我列测试清单」的场景。与测试用例区分：测试点只列验证目标（What），不写操作步骤（How）。产出供 testcase-generate 展开为完整测试用例。
---

# test-points：测试点

从已确认需求提炼可独立验证的业务差异，交给 `testcase-generate` 展开。正式测试点描述验证目标和结果关系，执行步骤、具体测试数据和断言表达式留给用例。

## 读什么

- 按 `../_testspec-shared/references/common.md` 定位变更；读适用的 `project-interaction-spec.md`、canonical 需求（先 `requirements.md`，缺省用 `proposal.md`）和直接上游 `requirements-analysis.md`。
- 按 `../_testspec-shared/references/context-protocol.md` 核对版本和待更新产物。有分析时先运行共享 `validate_context_chain.py --change-dir <变更目录> --through analysis`，发现规范需求与分析指纹不一致时回到需求分析。缺少分析，或已有分析过期、缺版本、版本异常时，回到 `prd-analysis`。仅用户明确跳过分析时用 canonical 降级提炼并注明低置信度。canonical 无版本按 Legacy 处理；本阶段产物过期时重新生成。
- 按 `../_testspec-shared/references/execution-efficiency.md` 复用已读材料。复用分析已有的 TestLib 检索结果；上游未扫描且索引存在时，只匹配当前模块和功能。按 `../_testspec-shared/references/source-provenance.md` 核对来源，记录可复用项和回归提示。

## 怎么提炼

1. 逐项对照已确认需求、分析中的证据和适用项目规范，覆盖会改变结果或具有独立验证价值的条件、状态和业务规则。每条 TP 表达一个可独立验证的意图。分类、序号和回归层级见 `references/testpoint-design-rules.md`，命名字典见 `../_testspec-shared/references/naming-contract.md`。分类由需求决定，单一且可判定的规则可以只对应一个 TP。
2. 按 `references/test-design-methods.md` 选择方法，写清它要区分的业务条件、边界或关系。已确认风险影响优先级和覆盖重点。未核实假设用于后续核查；TestLib 用于命名、回归和复用，业务规则及 Oracle 以当前需求为准。冒烟层级标记完整集内的核心闭环。
3. 为正式 TP 写清需求引用、方法、优先级与 Oracle 状态和范围。间接验证只断言当前系统的可观察结果。原型 HTML 逐项消费分析中的 `BTN_ID`，已确认行为关联到 TP，禁用、不可达、未执行或含糊的项保留状态及依据。
4. 会改变通过或失败判定的未决规则，保留上游 Q 编号及影响，标记 `oracle_status: needs-confirmation`；尚无编号时用稳定的 `Q-001` 等编号。明确关联需求和潜在影响优先级。已确认部分继续提炼，待澄清和已确认排除范围的部分不生成正式 TP；已确认却遗漏的需求记覆盖缺口。口径确认后重新生成受影响产物。

## 交付

按 `references/testpoints-template.md` 写入 `specs/testpoints.md`。使用模板的命名字典、需求去向和唯一上下文；实际命中 TestLib 时记录可复用资产。保持 canonical 版本和上游来源、问题、质量及待更新信息。从 stale 列表移除本阶段产物，保留下游项。按模板记录 `coverage_estimate`、`risks_identified`、`regression_tiers`、`testlib_reuse` 与 `"design_methods"`，方法集合与各 TP 标注一致。

交付前按 `../_testspec-shared/references/reflection-protocol.md` 核对需求覆盖、独立意图和方法落地，读回文件头和上下文。报告修正摘要及产物路径，下一步为 `testcase-generate`。
