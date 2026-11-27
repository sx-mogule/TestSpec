# 测试用例评审报告

**评审时间**: <timestamp>
**评审模式**: <mode> (Import-Quarantine/Provenance-Unknown/Strict/Legacy)
**评审深度**: <depth> (标准/加深)
**深度依据**: <主要风险/验收影响；辅助信号>
**变更目录**: <change_dir>
**Review Gate**: <pass/blocked/未计算；输入健康检查失败时不补造context>
**Unresolved S1**: <count>
**未解决判定力问题（J1–J4）**: <count>
**未解决四项描述问题（D1–D4）**: <count>
**Provenance Gate**: <pass/blocked>

### 已评审完整集

- 完整用例：`artifacts/testcases.json`
- 测试点：`specs/testpoints.md`
- BDD 核心特性：`artifacts/<name>_features.feature`
- 实际 SHA-256 写入末尾 `reviewed_artifacts`，用于追溯本次 Review 对应的版本；完整集变化后须重新评审。不改变现有 Review Gate 计算。

### 深度决策记录

- **执行模式**: <auto/--deep>
- **决策依据**: <主要风险/验收影响；辅助信号（如用例量、模块数或上游标记）/无>
- **额外读取材料**: <例如：requirements-analysis.md / 无>

---

## 评审执行记录

**评审状态**: <已完成/未完成；输入健康检查、14 项检查和 BDD 场景评审均完成才可写已完成>
**执行方式**: 同一模型单次评审；发现直接登记为 issue，不另设第二轮复核或映射表
**判定依据及限制**: <实际读取的原始 PRD/验收标准/canonical 需求；缺失材料及其对结论的限制>
**机器检查**: <validate_testcases.py 与 validate_context_chain.py 结果 PASS/WARN/FAIL 及要点>
**未完成原因**: <仅未完成时填写具体原因；已完成时删除此行>

## 一、机器检查

直接引用脚本输出，不写评语；问题仍在「问题清单」登记。

| 编号 | 结果 | 数值 | 问题 ID |
|---|---|---|---|
| M1 覆盖与追溯 | <pass/fail> | <TP 覆盖率 %；追溯完整率 %> | <IDs / 无> |
| M2 字段与格式 | <pass/fail> | <缺失字段数；命名格式违规数> | <IDs / 无> |
| M3 优先级分布 | <pass/fail> | <冒烟 %、p0 %、p1 %、p2 %> | <IDs / 无> |
| M4 相似候选 | — | <候选组数，交 D5 复核> | — |
| M5 来源与版本 | <pass/blocked> | <模式；未验证导入数；版本与指纹是否一致> | <IDs / 无> |

## 二、需求判定力表

先依据需求原文与项目规范列必测项，再对照 TP、用例和 BDD。结论只用：已拦住 / 漏测 / 拦不住 / 待澄清 / 范围外。未提供原始材料时，说明只核对 canonical `requirements.md`/`proposal.md`，不声称完成原文追溯。

| # | 必测项（REQ / 规则 / 分支） | 来源位置 | 覆盖用例 / BDD 场景 | 若实现错成… | 能拦住？ | 结论 | issue |
|---|---|---|---|---|---|---|---|
| 1 | <条件 → 可观察结果> | <原文位置 / REQ-001> | <case ID / feature:场景 / 无> | <具体错误实现> | <是/否> | <已拦住/漏测/拦不住/待澄清 Q-001/范围外（依据）> | <ID / 无> |

### 方法落地（J3）

| TP_ID | 设计方法 | 用例数 | Action | Oracle | Scope | Component | 结论 | 证据 |
|---|---|---|---|---|---|---|---|---|
| <tp_id> | <method> | <count> | <✓/✗> | <✓/✗> | <✓/✗> | <✓/✗> | <conclusion> | <case ID + 数据/操作/Oracle 中体现方法的证据> |

### 判定力自检对照

**生成阶段记录**: <_context.oracle_strength 摘要：checked / strengthened / weak_remaining；缺失时说明>
**本次反事实抽查**: <抽查范围与条数>
**不一致项**: <case ID 与差异；无则写“无”>

## 三、用例与 BDD 质量

### 四项描述门禁

逐条检查完整用例集，不以抽样代替；D1–D4 未解决问题为 0 才可通过，S2/S3 与 accepted 同样阻断。

| 编号 | 字段 | 已检查用例数/总数 | 结果（pass/blocked/未完成） | 问题 ID |
|---|---|---|---|---|
| D1 | 前置条件 | <checked/total> | <result> | <IDs / 无> |
| D2 | 测试数据 | <checked/total> | <result> | <IDs / 无> |
| D3 | 操作步骤 | <checked/total> | <result> | <IDs / 无> |
| D4 | 预期表述 | <checked/total> | <result> | <IDs / 无> |

### 相似候选与命名（D5）

| 候选组 / 用例 | 差异 | 结论（保留/合并/改名） | 问题 ID |
|---|---|---|---|
| <M4 候选组或 case ID> | <条件、数据、边界位置或预期差异> | <结论与理由> | <ID / 无> |

## BDD 场景评审

**BDD评审状态**: <已完成/未完成>
**评审文件**: <全部实际评审的 artifacts/<name>_features.feature 相对路径>
**已检查内容**: <核心主路径与关键异常覆盖、Given/When/Then、单一职责、业务语言、可观察 Oracle>
**评审结论**: <具体结论及对应 issue ID；无发现时说明已检查范围，未完成时说明缺失材料及原因>

| 场景 | 对应用例 | 同条件下结果一致？ | 问题 ID |
|---|---|---|---|
| <feature 路径:场景名> | <case ID> | <是/否及差异> | <ID / 无> |

缺少或未完成 BDD 评审时评审状态为未完成；不得只填完成状态或重算指纹代替评审。输入不足时沿用原规则不补造 Gate。

## 四、问题清单

每个问题只在此登记一次；上方各表只引用 ID。issue ID 不含等级，状态为 `open/resolved/accepted`。

- [<S1/S2/S3>] [<open/resolved/accepted>] <RV-001> [<M1–M5/J1–J4/D1–D5>] 范围：<case_id / TP_ID / feature:场景 / GLOBAL:rule>
  - **定位**: <需求或用例位置及原文>
  - **依据**: <需求原文、项目规范或脚本结果>
  - **会逃逸的行为 / 原因**: <J 层写可能误通过的错误实现；D 层写原文与原因>
  - **建议**: <可执行的修改；D 层给可直接替换的短句>
  - **owner**: <prd-analysis / test-points / testcase-generate>

没有问题时写“未发现问题”，并说明已检查范围。

## 五、14 项矩阵

问题数等于问题清单中该编号的登记条数；结果按问题与检查完成情况填写，不另写评语。

| 检查项 | 结果 | 关键数值 | 问题数 |
|--------|------|----------|--------|
| M1 覆盖与追溯 | <pass/fail/blocked> | <metric> | <count> |
| M2 字段与格式 | <pass/fail/blocked> | <metric> | <count> |
| M3 优先级分布 | <pass/fail/blocked> | <metric> | <count> |
| M4 相似候选 | — | <候选组数> | 0 |
| M5 来源与版本 | <pass/fail/blocked> | <metric> | <count> |
| J1 漏测 | <pass/fail/blocked> | <必测项数；漏测数> | <count> |
| J2 拦不住 | <pass/fail/blocked> | <反事实抽查数；拦不住数> | <count> |
| J3 偏题 | <pass/fail/blocked> | <已核对 TP 数> | <count> |
| J4 口径未定 | <pass/fail/blocked> | <待澄清数> | <count> |
| D1 前置条件 | <pass/fail/blocked> | <checked/total> | <count> |
| D2 测试数据 | <pass/fail/blocked> | <checked/total> | <count> |
| D3 操作步骤 | <pass/fail/blocked> | <checked/total> | <count> |
| D4 预期表述 | <pass/fail/blocked> | <checked/total> | <count> |
| D5 命名与粒度 | <pass/fail/blocked> | <已复核候选组数> | <count> |

**附注（可选）**: <可沉淀的标杆用例或可复用模式；没有时删除此行>

---

通过条件：未解决 S1、J1–J4 和 D1–D4 问题均为 0，三个 ID 列表均为空；“未解决”指状态不是 `resolved`。计数必须对应问题清单，不因模板默认值为 0 就宣称通过。

**评审完成时间**: <timestamp>

<!-- testspec-context
{
  "source_skill": "testcase-reviewer",
  "source_revision": {"version": "<canonical 版本>", "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "blocking_open_questions": [],
  "dynamic_followups": [],
  "material_quality": "<从上游继承>",
  "design_methods": ["<从 testcase-generate 继承的正式方法名>"],
  "stale_downstream_artifacts": [],
  "bdd_review": {"status": "<complete/incomplete>"},
  "reviewed_artifacts": {
    "testcases_sha256": "<实际完整 JSON 的 SHA-256>",
    "testpoints_sha256": "<实际测试点的 SHA-256>",
    "bdd_features_sha256": {"artifacts/<name>_features.feature": "<实际 BDD 文件的 SHA-256>"}
  },
  "canonical_source_policy": "prd-first",
  "origin": {"kind": "<testspec-native/legacy-import/mixed>"},
  "trust": {"status": "<verified/provisional/unverified/mixed>"},
  "review_gate": {
    "status": "pass/blocked",
    "s1_unresolved_count": 0,
    "s1_issue_ids": [],
    "judgment_unresolved_count": 0,
    "judgment_issue_ids": [],
    "description_unresolved_count": 0,
    "description_issue_ids": []
  },
  "risks_identified": []
}
-->
