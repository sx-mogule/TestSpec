# SOP 14项评审模块（原 testcase-review）

[维度细则](references/review-dimensions.md) 是 R1–R6、H1–H8 的判定依据。按 [公共约定](../../_testspec-shared/references/common.md) 定位变更目录，按 [复用规则](../../_testspec-shared/references/execution-efficiency.md) 核对输入版本和读取范围。

## 深度策略（统一语义）

默认执行 `auto` 模式：先判断风险及其对需求范围、Oracle、通过/失败判断和关键流程的影响，再决定标准深度或加深深度；用例量、模块数、类型数和上游信号只作辅助提示。

- `auto`（默认）：按风险及验收影响选择深度，信号辅助判断
- `--deep`（显式）：强制加深深度，不再降级

### auto 信号

**辅助加深信号：**
- 用例总数 > 50
- 涉及模块数 > 5
- 同时满足用例类型 ≥ 3 且用例总数 ≥ 20
- 上游 `material_quality = low`
- 上游 `risks_identified` 非空
- 上游 `blocking_open_questions` 非空

**深度优先规则：**
- 可能改变验收范围、通过/失败 Oracle、关键状态或恢复判断的风险和阻塞问题，触发加深，即使用例少或预先信号少；缺少证据时按既有流程记录澄清，不猜测。
- 无上述高影响问题且材料足以判定时可保持标准深度；数量指标本身不强制加深，也不能据此跳过任何固定检查。

Strict/Legacy 只决定追溯检查的置信度，不单独决定深度。报告中说明主要风险/验收影响，并将命中信号作为辅助依据。

### 深度行为差异

- 两种深度使用同一套 14 项检查、分级和 Gate 标准。
- 标准深度对高风险 TP 给出完整的 H3 证据。加深时补读可用的 `requirements-analysis.md` 和相关原文，逐项说明所有 TP 的条件、动作和结果证据，回查关键缺口。

评审开始时必须向用户说明当前深度及理由。

---

## 输入策略

### 必读文件

- `artifacts/testcases.json`（canonical path）
- `specs/testpoints.md`
- `artifacts/*_features.feature`（标准 SOP 强制伴生 BDD 核心特性文件）

### 可选文件

- `requirements-analysis.md`（`--deep` 或 auto 加深时建议读取）

### 输入健康检查（失败即终止）

1. `artifacts/testcases.json` 存在且可解析；只有该文件不存在时才读取根目录 `testcases.json` 作为 Legacy fallback，并明确告警。两者同时存在时始终使用 artifacts 版本
2. 顶层包含 `testcases` 数组且非空
3. `specs/testpoints.md` 存在且包含 TP_ID
4. 检查全部伴生 BDD 特性文件 `artifacts/*_features.feature` 存在、可读取且非空；复用入口已完成的 BDD 场景评审。缺失、为空或无法读取时，输入健康检查未完成，在通用反馈中记录交付缺口并返回 `testcase-generate` 补齐，不形成 SOP 通过结论
5. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`），按 `../../_testspec-shared/references/context-protocol.md` 比较版本。有分析时先运行共享 `validate_context_chain.py --change-dir <变更目录> --through analysis`，确认分析使用的规范需求指纹仍有效；历史分析无指纹时说明验证限制
6. canonical 有版本时，`specs/testpoints.md` 与 `testcases.json._context.source_revision` 都必须与 canonical 完全一致：
   - testpoints 缺少版本或版本更低 → 终止并提示先运行 `test-points`，之后再运行 generate
   - testcases 缺少版本或版本更低 → 终止并提示先运行 `testcase-generate`
   - 任一版本高于 canonical → 终止并报告元数据损坏
7. testpoints/testcases 版本与 canonical 相等时，即使 inherited stale 列表仍含 `review-report.md`，也允许执行本次 review；review 成功后该 stale 项被解决
8. canonical 无版本：按 Legacy 版本兼容模式继续并告警，不得仅因缺少 `source_revision` 终止；当前正式交付仍须提供 BDD 并完成评审

若失败：停止SOP门禁判定，标记SOP检查未完成并列出具体缺项；保留入口已完成的通用评审，对可判定的R/H质量项继续给出结论，无法核实的项逐项标明原因。不得补造TP、来源、context或Gate。TestSpec正式交付仍须先补齐上游产物后重评。

### 模式判定

- **Import-Quarantine**：`_context.origin.kind = legacy-import` 且 `_context.trust.status = unverified`
- **Provenance-Unknown**：`_context` 或任一 case 的 `origin` / `trust` 缺失、不是对象、关键枚举为空/未知，或来源与信任组合非法/上下不一致
- **Strict**：`schema_version: 2` 且所有用例有非空 `tp_refs`
- **Legacy**：否则

模式判定优先级固定为 `Import-Quarantine > Provenance-Unknown > Strict/Legacy`。
Legacy 模式仍可评审，但 R6/H3 置信度下调，并在报告中明确升级建议。
Import-Quarantine 必须产生 `GLOBAL:legacy-traceability` S1，`review_gate.status = blocked`；评审可以继续给出修复清单，但不得伪装通过。
Provenance-Unknown 必须产生 `GLOBAL:provenance-unknown` S1，`review_gate.status = blocked`；`origin={}` / `trust={}` 不算有效 provenance。先隔离导入或从当前 PRD 重新生成。

---

## 严重级别体系

- **S1 阻断级**：必须修复（影响可执行性或严重偏离测试意图）
- **S2 重要级**：应当修复（影响覆盖质量、追溯、维护）
- **S3 建议级**：可选优化（提升可读性和效率）

关键分支或预期缺口按维度细则的 H3/H5 记 S1。四项描述问题仍按原维度分级；确认的 S2/S3 描述问题也须修复后才能通过描述门禁。其他 S3 仍为可选优化。

---

## 执行与报告

1. 核对输入健康、来源模式和深度。读取入口已经形成的通用反馈，按 [发现处置规则](references/independent-reviewer.md) 复用证据并裁定。
2. 按 R1–R6、H1–H8 完成 [维度细则](references/review-dimensions.md) 的检查。先匹配原文和已有证据，再补查缺口。完整集的四项描述逐条核对。按 H5 复核上游待澄清项是否影响本次关键验收，再决定是否进入 S1。确认关键缺口时，说明哪种错误可能误通过，以及该回哪个阶段。H3 同时检查范围：有明确依据的埋点和兼容性矩阵按各自 Oracle 核对；未授权的独立 API、安全、性能等类型按 S1 阻断。
3. 按 [统一报告模板](../../_testspec-shared/templates/review-report-template.md) 和 [输出契约](../../_testspec-shared/references/output-contracts.md) 写当前变更的 `review-report.md`，保留原始 GR、逐项处置、BDD 评审摘要和 SOP 结论。每个问题引用确切的 `case_id`、`TP_ID`、BDD 场景或 `GLOBAL:<rule>`，给出范围和修复动作。BDD 专属发现定位 feature 路径和场景，分配给生成阶段。
4. 保存后运行 `verify_eval_artifacts.py feedback --report <实际报告路径>` 和 `validate_context_chain.py --change-dir <变更目录> --through review`（脚本在共享目录的 `scripts/` 下）。材料不齐时按健康检查规则交付部分评审，并如实说明结论限制。
5. 标准交付前，对实际 XMind（默认 `artifacts/<name>_cases.xmind`）运行共享 `verify_eval_artifacts.py xmind --json <实际评审的 JSON> --xmind <实际 XMind>`。文件缺失、不一致或交付路径未确定时，记录交付待补并交回生成阶段。用例评审和 Gate 仍按实际评审的 JSON、测试点与 BDD 判定。

用户授权返修时，按输出契约重开其指定的已 accepted 描述问题，保留原 ID、等级、定位及 owner。返修后按同一 ID 重评，并以实际评审产物刷新完整 JSON、TP 和全部 BDD 指纹。

## 总体置信度

- **高**：Strict + 输入完整 + 14 项均可执行
- **中**：Legacy，或部分检查依赖推断
- **低**：输入缺失，导致关键检查无法执行

---

### 上下文播种

按 `../../_testspec-shared/references/context-protocol.md` 和 `../../_testspec-shared/templates/review-report-template.md` 写入唯一闭合的 context：

- 原样传播 canonical 版本、来源、问题、质量及 `design_methods`，`source_skill` 为 `testcase-reviewer`。
- 终点清空 `stale_downstream_artifacts`，省略 `next_skill` 和 `stale_reason`。
- `bdd_review` 与可见 BDD 场景评审摘要一致；`reviewed_artifacts` 记录完整 JSON、测试点和全部 BDD 文件的 SHA-256。
- `review_gate` 写完整 S1 与四项描述门禁字段；只有两类未解决问题均为 0、两个 ID 列表均为空才可为 `pass`。缺少描述检查结果必须重审，不默认通过；`accepted` 不豁免描述问题。
- `risks_identified` 只记录本次有依据的风险。完整模板只在首次生成或需要格式修复时读取。

---

## 输出总结

按 `../../_testspec-shared/references/output-contracts.md` 的“评审完成后的对话摘要”报告本次实际结果。

## 产物

- `testspec/changes/<name>/review-report.md`
