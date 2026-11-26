# 测试用例评审报告

**评审时间**: <timestamp>
**评审模式**: <mode> (Import-Quarantine/Provenance-Unknown/Strict/Legacy)
**评审深度**: <depth> (标准/加深)
**深度依据**: <主要风险/验收影响；辅助信号>
**变更目录**: <change_dir>
**Review Gate**: <pass/blocked/未计算；输入健康检查失败时不补造context>
**Unresolved S1**: <count>
**未解决四项描述问题**: <count>
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

## 通用评审反馈

本节在 SOP 检查前形成并完整保留，展示同一模型按通用规则得到的原始反馈。后续复核可以补充处置，不能删除、改写或只引用 SOP 问题来代替本节。

**通用评审状态**: <已完成/未完成>
**执行方式**: 同一模型按通用评审规则单独评审
**评审依据与范围**: <实际读取的需求、用例/套件/BDD范围及来源限制>
**已检查内容**: <实际检查的覆盖、边界、错误路径、Oracle、可执行性等及证据摘要>
**通用发现数**: <count>
**通用评审结论**: <依据原始材料得出的结论；已完成且为0项时明确写“未发现实质性缺陷”>
**未完成原因**: <仅未完成时填写具体原因；已完成时删除此行>

有发现时逐项填写以下结构；使用 GR-001、GR-002 等本轮稳定编号，并删除占位说明。没有发现时删除示例发现，不为凑数编造问题。

### GR-001: <Critical/High/Medium/Low>

**定位**: <需求/用例/场景编号及原文位置>
**依据**: <原始材料与必要引文>
**问题**: <通用评审发现的原始问题>
**影响**: <影响范围和后果>
**建议**: <原始的、可执行的修改或补充建议>

## BDD 场景评审

**BDD评审状态**: <已完成/未完成>
**评审文件**: <全部实际评审的 artifacts/<name>_features.feature 相对路径>
**已检查内容**: <核心主路径与关键异常覆盖、Given/When/Then、单一职责、业务语言、可观察 Oracle，以及与正式用例在同一规则下的结果核对>
**评审结论**: <具体结论及对应 GR 编号；无发现时说明已检查范围，未完成时说明缺失材料及原因>

BDD 发现完整保留在上方通用反馈中，并使用相同 GR 编号逐项处置。缺少或未完成 BDD 评审时整轮为未完成；不得只填完成状态或重算指纹代替评审。输入不足时沿用原规则不补造 Gate。

## 总评

**结论**: <overall_conclusion>

**置信度**: <confidence_level>

### 结论总览矩阵

| 检查项 | 结果 | 关键指标 | 问题数 |
|--------|------|----------|--------|
| R1 覆盖度 | <result> | <metric> | <count> |
| R2 命名契约 | <result> | <metric> | <count> |
| R3 优先级分布 | <result> | <metric> | <count> |
| R4 字段完整性 | <result> | <metric> | <count> |
| R5 可执行性 | <result> | <metric> | <count> |
| R6 可追溯性 | <result> | <metric> | <count> |
| H1 冗余检测 | <result> | <metric> | <count> |
| H2 预期结果质量 | <result> | <metric> | <count> |
| H3 意图一致性 | <result> | <metric> | <count> |
| H4 前置条件充分性 | <result> | <metric> | <count> |
| H5 风险与边界覆盖 | <result> | <metric> | <count> |
| H6 可维护性建议 | <result> | <metric> | <count> |
| H7 回归价值评估 | <result> | <metric> | <count> |
| H8 测试价值与亮点 | — | 标杆用例数 <count>；可复用模式数 <count> | <count> |

---

## 两部分评审执行记录

**SOP检查状态**: <已完成/未完成；未完成逐项说明缺失材料>
**整轮状态**: <已完成/未完成；通用评审、BDD 场景评审与 SOP 检查均完成才可写已完成>
**执行方式**: 同一模型先执行通用评审，再执行SOP检查
**统一入口**: `testcase-reviewer`；通用评审mode=`review`，SOP模块=`review-workflow.md`
**判定依据及限制**: <原始 PRD/验收标准/canonical 需求；版本、文件 SHA-256 与缺失材料>
**原始反馈定位**: 见上方“通用评审反馈”；原始发现、等级和建议完整保留

### 通用发现处置

| 通用发现编号 | 原等级 | 原始发现定位 | 处置 | 原生 issue ID / 维度 / 级别 | 处置依据 |
|---|---|---|---|---|---|
| <GR-001> | <Critical/High/Medium/Low> | <见通用反馈 GR-001、需求或用例位置> | <采纳/重复关联/不适用/待确认> | <RV-ID / R或H / S级；无则说明> | <复核证据或不适用理由> |

没有发现时写“无通用发现，无需处置”，不保留占位行。原始反馈必须在上方单独完整展示，本表不能代替正文。每个发现均须有处置，采纳/重复问题只在原生问题列表登记一次。原等级与 S1/S2/S3 不机械对应；原有 14 项检查及 Gate 公式保持不变。

---

## 规则检查

### 四项描述门禁

逐条检查完整用例集，不以抽样代替；四项均完成且未解决描述问题为 0 才可通过。必要长值和关键路径不因长度判错；S2/S3 描述问题仍须修复，不以 accepted 豁免。

| 字段 | 已检查用例数/总数 | 结果（pass/blocked/未完成） | 问题 ID |
|---|---|---|---|
| 前置条件 | <checked/total> | <result> | <issue IDs / 无> |
| 测试数据 | <checked/total> | <result> | <issue IDs / 无> |
| 操作步骤 | <checked/total> | <result> | <issue IDs / 无> |
| 预期结果 | <checked/total> | <result> | <issue IDs / 无> |

问题在所属 R/H 维度中记录一次：用例 ID、字段、原文、原因、可直接替换的短句和状态；此表引用相同 issue ID，不重复计数。未完成时记录 `GLOBAL:description-review-incomplete` 范围的问题，Gate 保持 blocked。

### 需求去向核对

有原始 PRD/需求素材时，在来源位置与说明中串联“原文→REQ→TP→用例→可观察 Oracle”；未提供原始材料时，明确本表只核对 canonical `requirements.md`/`proposal.md`，不声称完成原文追溯。已确认且在范围内但缺少 TP、用例或可判定 Oracle 的需求，去向标为“覆盖缺口”；不得用待澄清或范围外掩盖。待澄清记录原 Q 编号及受影响的验收。仍影响本次关键验收时，按 H5 关联 S1 issue，由需求分析确认口径。范围外须有确认依据，其他关键缺口按 H3/H5 分级，本表引用对应 issue ID。

| 需求编号/来源段落 | 测试点/待澄清/范围外/覆盖缺口 | 用例 ID | 说明 |
|------------------------|----------------------------------------|---------|------|
| <原文位置（若可用）/REQ-001> | <正式测试点编号 / Q-001 / 范围外 / 覆盖缺口> | <用例 ID / 无> | <可观察结果或缺失条件、可能误通过的行为、对应 issue ID> |

### R1: 测试点覆盖度

**结果**: <pass/fail>
**覆盖率**: <percentage>%

<问题列表>
- [S1/S2/S3] [<open/resolved/accepted>] <RV-S1-001 等稳定 issue ID>：<问题描述>
  - **范围**: <case_id / TP_ID / GLOBAL:rule>
  - **owner**: <责任阶段/技能>
  - **影响**: <影响说明>
  - **建议**: <整改建议>

### R2: 命名契约

**结果**: <pass/fail>
**违规数**: <count>

<问题列表>
名称问题逐项写明：用例 ID、原名称、问题原因、建议名称；建议遵循共享命名契约，保留关键条件和原测试意图。

### R3: 优先级分布

**结果**: <pass/fail>
**分布情况**: 冒烟 <count>%, p0 <count>%, p1 <count>%, p2 <count>%

<问题列表>

### R4: 字段完整性

**结果**: <pass/fail>
**缺失字段数**: <count>

<问题列表>

### R5: 可执行性最小条件

**结果**: <pass/fail>
**不满足条件数**: <count>

<问题列表>

### R6: 可追溯性

**结果**: <pass/fail>
**追溯完整性**: <percentage>%
**模式**: <Import-Quarantine/Provenance-Unknown/Strict/Legacy>

<问题列表>

### Provenance 与导入隔离

**未验证历史导入数**: <count>
**结果**: <pass/blocked>

<问题列表；存在 legacy-import + unverified 时记录 GLOBAL:legacy-traceability S1；缺 provenance 时记录 GLOBAL:provenance-unknown S1>

---

## 启发式检查

### H1: 冗余检测

**结果**: <pass/fail>
**疑似冗余对数**: <count>

<问题列表>

### H2: 预期结果质量

**结果**: <pass/fail>
**模糊表述数**: <count>

<问题列表>

### H3: 意图一致性

**结果**: <pass/fail>

#### 意图一致性评估表

| TP_ID | 设计方法 | 用例数 | Action Match | Oracle Match | Scope Match | 结论 | 证据/说明 |
|-------|----------|--------|--------------|--------------|-------------|------|-----------|
| <tp_id> | <method> | <count> | <score> | <score> | <score> | <conclusion> | <case ID + 数据/操作/Oracle 中体现方法的证据> |

<问题列表>

### H4: 前置条件充分性

**结果**: <pass/fail>
**抽样数**: <count>
**不充分数**: <count>

<问题列表>

### H5: 风险与边界覆盖

**结果**: <pass/fail>
**覆盖类型**: <types>
**HTML 按钮覆盖（适用时）**: <发现/已点击/已关联 TP/已有用例/未覆盖数量及 BTN_ID>

<问题列表>

### H6: 可维护性建议

**结果**: <pass/fail>
**建议数**: <count>

<问题列表>

### H7: 回归价值评估

**结果**: <pass/fail>
**抽样数**: <count>
**仪式感用例数**: <count>

<问题列表>

### H8: 测试价值与亮点识别

**标杆用例数**: <count>
**可复用模式数**: <count>
**测试策略健康度**: <评语>

<亮点列表>

---

## 整改建议清单

### S1 阻断级（必须修复）

- [ ] [<open/resolved/accepted>] <RV-S1-001> <case_id / TP_ID / GLOBAL:rule>：<问题描述> - <建议>
  - **owner**: <原责任阶段/技能；返修时保留>

### S2 重要级（应当修复）

- [ ] [<open/resolved/accepted>] <RV-S2-001> <case_id / TP_ID / GLOBAL:rule>：<问题描述> - <建议>
  - **owner**: <原责任阶段/技能；返修时保留>

### S3 建议级（四项描述问题须修复，其他可选优化）

- [ ] [<open/resolved/accepted>] <RV-S3-001> <case_id / TP_ID / GLOBAL:rule>：<问题描述> - <建议>
  - **owner**: <原责任阶段/技能；返修时保留>

---

通过条件：未解决 S1 和描述问题均为 0，两个 ID 列表均为空；计数必须对应报告中的未解决问题，不因模板默认值为 0 就宣称通过。

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
    "description_unresolved_count": 0,
    "description_issue_ids": []
  },
  "risks_identified": []
}
-->
