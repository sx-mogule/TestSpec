# SOP 14项评审模块（原 testcase-review）

[维度细则](references/review-dimensions.md) 是 M1–M5、J1–J4、D1–D5 的判定依据。按 [公共约定](../../_testspec-shared/references/common.md) 定位变更目录，按 [复用规则](../../_testspec-shared/references/execution-efficiency.md) 核对输入版本和读取范围。

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

- 两种深度使用同一套 14 项检查、分级和 Gate 标准，必测清单都要列全。
- 标准深度对 p0、p1、写操作和风险项做 J2 反事实检验，高风险 TP 给出完整 J3 证据。加深时补读可用的 `requirements-analysis.md` 和相关原文，对全部用例做反事实检验，逐项说明所有 TP 的条件、动作和结果证据。

评审开始时必须向用户说明当前深度及理由。

---

## 输入策略

### 必读文件

- `artifacts/testcases.json`（canonical path）
- `specs/testpoints.md`
- `artifacts/*_features.feature`（标准 SOP 强制伴生 BDD 核心特性文件）

### 可选文件

- `requirements-analysis.md`（`--deep` 或 auto 加深时建议读取）
- 可选阅读副本：`scripts/prepare_reviewer_input.py` 生成只保留 ID 和八项业务字段的只读 JSON（去掉 TP、context 与来源元数据），用于先按需求判断用例、减少被既有 TP 锚定；完整 JSON 仍是评审对象。用法：`python3 -B skills/testcase-reviewer/testcase-review/scripts/prepare_reviewer_input.py --testcases <用例 JSON> --requirements <需求文件> --output .testspec-cache/reviewer/<run>/input.json`

### 输入健康检查（失败即终止）

1. `artifacts/testcases.json` 存在且可解析；只有该文件不存在时才读取根目录 `testcases.json` 作为 Legacy fallback，并明确告警。两者同时存在时始终使用 artifacts 版本
2. 顶层包含 `testcases` 数组且非空
3. `specs/testpoints.md` 存在且包含 TP_ID
4. 检查全部伴生 BDD 特性文件 `artifacts/*_features.feature` 存在、可读取且非空，并在本轮按入口规则评审。缺失、为空或无法读取时，输入健康检查未完成，在评审执行记录中写明交付缺口并返回 `testcase-generate` 补齐，不形成 SOP 通过结论
5. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`），按 `../../_testspec-shared/references/context-protocol.md` 比较版本。有分析时先运行共享 `validate_context_chain.py --change-dir <变更目录> --through analysis` 核对需求指纹。历史分析无指纹时可继续给出有据可查的评审，正式放行前交回 `prd-analysis` 核对原文并重建指纹。
6. canonical 有版本时，`specs/testpoints.md` 与 `testcases.json._context.source_revision` 都必须与 canonical 完全一致：
   - testpoints 缺少版本或版本更低 → 终止并提示先运行 `test-points`，之后再运行 generate
   - testcases 缺少版本或版本更低 → 终止并提示先运行 `testcase-generate`
   - 任一版本高于 canonical → 终止并报告元数据损坏
7. testpoints/testcases 版本与 canonical 相等时，即使 inherited stale 列表仍含 `review-report.md`，也允许执行本次 review；review 成功后该 stale 项被解决
8. canonical 无版本：按 Legacy 版本兼容模式继续并告警，不得仅因缺少 `source_revision` 终止；当前正式交付仍须提供 BDD 并完成评审

若失败：停止门禁判定，评审状态记为未完成并列出具体缺项；对可判定的 J/D 项继续给出结论，无法核实的项逐项标明原因。不得补造TP、来源、context或Gate。TestSpec正式交付仍须先补齐上游产物后重评。

### 模式判定

- **Import-Quarantine**：`_context.origin.kind = legacy-import` 且 `_context.trust.status = unverified`
- **Provenance-Unknown**：`_context` 或任一 case 的 `origin` / `trust` 缺失、不是对象、关键枚举为空/未知，或来源与信任组合非法/上下不一致
- **Strict**：`schema_version: 2` 且所有用例有非空 `tp_refs`
- **Legacy**：否则

模式判定优先级固定为 `Import-Quarantine > Provenance-Unknown > Strict/Legacy`。
以 `validate_testcases.py` 输出的 `provenance.mode` 和 `provenance.issues` 为准。脚本检查用例集上下文和每条用例，问题记录包含等级、范围及受影响的用例 ID 或 `_context`。顶层 `status` 为格式和覆盖等用例自检结果。
Legacy 模式仍可评审，但 M1/J3 置信度下调，并在报告中明确升级建议。
Import-Quarantine 必须产生 M5 `GLOBAL:legacy-traceability` S1，`review_gate.status = blocked`；评审可以继续给出修复清单，但不得伪装通过。
Provenance-Unknown 必须产生 M5 `GLOBAL:provenance-unknown` S1，`review_gate.status = blocked`；`origin={}` / `trust={}` 不算有效 provenance。先隔离导入或从当前 PRD 重新生成。

---

## 严重级别与 Gate

等级定义、默认等级和阻断范围统一见 [维度细则](references/review-dimensions.md) 的「分级与 Gate」：任意层未解决的 S1、J1–J4 任意等级、D1–D4 任意等级（含 accepted）均阻断 Gate；M 层的 S2/S3、M4、D5 和附注不阻断。

---

## 执行与报告

1. **准入。** 核对输入健康和评审深度。运行共享 `validate_testcases.py --input <用例 JSON> --testpoints <测试点文件> --pretty` 和 `validate_context_chain.py --change-dir <变更目录> --through generate`，M1–M5 直接引用其结果。将 `provenance.issues` 登记为 M5，并按现有 S1 规则计入 Gate。
2. **建必测清单。** 先不看 TP，只依据需求原文、已确认澄清和项目交互规范列出“条件 → 可观察结果”；可先用阅读副本减少被既有 TP 锚定。
3. **逐项判定（J 层）。** 每个必测项对照 TP、用例和 BDD，判断已拦住 / 漏测 / 拦不住 / 待澄清 / 范围外，填入需求判定力表；按维度细则做反事实检验、方法落地与范围检查（J3 同时检查范围：有明确依据的埋点和兼容性矩阵按各自 Oracle 核对；未授权的独立 API、安全、性能等类型按 S1 阻断）。确认缺口时写明哪种错误实现可能误通过，以及该回哪个阶段。
4. **用例质量（D 层）。** 完整集的 D1–D4 逐条核对，D5 复核 M4 候选与命名；伴生 BDD 按入口规则逐个场景核对，并与 JSON 在同一条件下比较关键结果。
5. **裁定。** 按 [统一报告模板](../../_testspec-shared/templates/review-report-template.md) 和 [输出契约](../../_testspec-shared/references/output-contracts.md) 写当前变更的 `review-report.md`。每个问题只在问题清单登记一次，带编号标签、确切的 `case_id`/`TP_ID`/BDD 场景或 `GLOBAL:<rule>`、owner 和修复动作。J4 引用原 Q 编号。矩阵按标签统计，正文与上下文使用同一 Gate 结论。保存后运行 `verify_eval_artifacts.py review --report <实际报告路径>` 和 `validate_context_chain.py --change-dir <变更目录> --through review`（脚本在共享目录的 `scripts/` 下）。材料不齐时按健康检查规则交付部分评审，并如实说明结论限制。
6. 标准交付前，对实际 XMind（默认 `artifacts/<name>_cases.xmind`）运行共享 `verify_eval_artifacts.py xmind --json <实际评审的 JSON> --xmind <实际 XMind>`。文件缺失、不一致或交付路径未确定时，记录交付待补并交回生成阶段。用例评审和 Gate 仍按实际评审的 JSON、测试点与 BDD 判定。

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
- `review_gate` 写完整 S1、判定力（`judgment_unresolved_count`、`judgment_issue_ids`）与四项描述门禁字段；只有三类未解决问题均为 0、三个 ID 列表均为空才可为 `pass`。缺少任一组字段必须重审，不默认通过；`accepted` 不豁免判定力和描述问题。
- `risks_identified` 只记录本次有依据的风险。完整模板只在首次生成或需要格式修复时读取。

---

## 输出总结

按 `../../_testspec-shared/references/output-contracts.md` 的“评审完成后的对话摘要”报告本次实际结果。

## 产物

- `testspec/changes/<name>/review-report.md`

## 维护

本包文件指纹固定在 `../../_testspec-shared/references/testcase-reviewer-source.json`；修改本目录任一文件后须同步更新该清单。回归：`python3 -B -m unittest discover -s skills/testcase-reviewer/testcase-review/tests -v`。
