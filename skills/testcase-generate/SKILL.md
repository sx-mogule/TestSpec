---
name: testcase-generate
license: MIT
description: TestSpec 生成测试用例（流程第 3 步）- 根据测试点（specs/*.md）生成完整测试用例并默认导出 XMind (.xmind)。当用户要「生成用例」「写测试用例」「导出 XMind」或执行 testcase-generate / testcase generate 时使用。也适用于用户说「把测试点展开成用例」或「帮我出一份测试用例表」的场景。使用内置 Python 脚本生成 XMind 文件，不依赖外部技能。
---

# testcase-generate：用例生成

铁律：每条生成用例都必须可执行、可验证，并可追溯到至少一个当前 TP_ID；生成阶段不得主动请求真实接口来反推正确结果。

```text
TestSpec 用例生成进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载 specs/*.md 和上游 context ⚠️ 必需
- [ ] 步骤 3：选择策略并设计用例
- [ ] 步骤 4：写入 schema v2 testcases.json
- [ ] 步骤 5：运行 validate_testcases.py ⛔ 阻塞
- [ ] 步骤 6：导出 XMind 并报告产物
```

## 职责

读取当前变更的 `specs/*.md`（测试点），先根据用户目标选择测试类型策略，再将测试点展开为完整测试用例；统一写入 `artifacts/testcases.json` 并默认导出 XMind。模块/子模块保留在每条用例的字段中，无需分片或后续合并。若存在 `strategy.md` 可参考其允许范围内的测试类型、层级与通过标准；否则从共享规则源读取默认策略。所有导出均遵循本文件定义的八项业务字段契约。

本阶段只消费已确认的 PRD、分析、允许范围内的测试点和经允许的参考证据。不得发送探索请求、访问真实 API、用当前实现响应生成 oracle，或把实现缺陷固化成预期结果。需求或接口事实不足时，回到需求分析阶段补充 canonical 输入。允许 Tracking 与 Compatibility 测试点按专属类型生成；其他非功能测试点停止生成并返回 test-points 清理范围，不以 `type=其他` 绕过。

首次按 `../_testspec-shared/references/execution-efficiency.md` 的相关章节核对输入哈希和读取范围；同一会话已读且未变的内容可复用，不重复加载本阶段无关章节。阶段与门禁照常执行。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 测试类型策略单一数据源：`references/test-type-strategies.md`
- 用例设计规则：`references/case-design-rules.md`
- 十二种测试方法及示例：`references/test-design-methods.md`（按上游已选方法读取对应章节）
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 命名契约：`../_testspec-shared/references/naming-contract.md`
- 来源与信任：`../_testspec-shared/references/source-provenance.md`

---


## 测试点到用例的转换规则

### 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

#### 上游上下文消费

1. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`）和直接上游 `specs/testpoints.md`（必须）
2. 按 `../_testspec-shared/references/context-protocol.md` 比对 canonical revision：
   - canonical 有版本，而 testpoints 缺少版本或版本更低：停止并提示先运行 `test-points`
   - testpoints 版本高于 canonical：停止并报告版本元数据损坏
   - canonical 无版本：按 Legacy 模式继续并告警，不伪造版本
   - 现有 testcases 过期表示本 skill 应重新生成，不得提示用户再次运行当前 skill
3. 消费 testpoints 上下文：
   - 提取 `risks_identified` → 对风险区域增加异常/边界用例
   - 提取 `coverage_estimate` → 作为覆盖基线
   - 提取 `blocking_open_questions` → 相关用例标注风险
   - 提取 `testlib_reuse`（若有）→ 识别哪些 TP 已在 testlib 中有用例
   - 提取 `regression_tiers`（若有）→ 用例继承对应 TP 的回归层级
   - 提取各 TP 的“设计方法”和 `design_methods` → 按所选方法展开场景；方法名不在十二种方法内时先退回 `test-points` 澄清，不自行替换
   - 提取 `canonical_source_policy`、`evidence_sources`、`questions` → 原样传播；代码不可访问不影响生成
4. 成功生成后原样传播 canonical envelope，从 stale 列表移除自身产物，并将 `next_skill` 指向 `testcase-review`

#### testlib 参考用例检索

每次检查当前工作区 `testspec/testlib/index.json`。实际匹配模块/功能后，只读取2–3条可信参考，排除 `legacy-import + unverified`；缺新版来源元数据的历史用例只参考命名和格式。参考步骤、预期和前置条件的表达风格，不据此决定场景、覆盖策略或需求结果。无匹配时使用默认表达规则，仍以当前TP驱动生成。

#### 测试策略推理

根据用户目标、容易遗漏的场景和主业务闭环，从 `references/test-type-strategies.md` 选当前策略；只读取适用章节。完整功能与回归覆盖由TP和证据驱动，冒烟仅作完整集内分类，不缩小范围。用户显式指定类型时按需求依据执行，未指定默认functional。独立 API、安全、性能等类型不进入本流程；埋点与兼容性矩阵须有明确口径。选择理由来自推理，不机械按关键词匹配。

#### 推理结论记录

在 testcases.json 的 `_context` 字段记录推理结论（按 `../_testspec-shared/references/context-protocol.md`），包括：

- canonical revision envelope：source_revision, blocking_open_questions, dynamic_followups, material_quality, stale_downstream_artifacts, stale_reason, next_skill
- 常规字段：coverage_estimate, design_methods, iteration_count, iteration_summary
- testlib 参考信息：`testlib_reference.referenced_features`（参考了哪些 testlib 功能的已有用例）

### 转换原则

- **一对多映射**：一个测试点可能对应多个测试用例场景
- **场景细化**：根据测试点的验证要点，细化为具体的测试场景；涉及多种输入条件或状态时，须设计多个独立用例
- **HTML 按钮来源**：核对各 `BTN_ID` 对应的已确认 TP；相关用例写明可复现的点击动作和可观察业务结果。同一场景可覆盖多个按钮，但须能逐项追溯；仅有原型点击现象、缺少需求 Oracle 的按钮不编造正式用例
- **数据驱动**：针对边界验证点，设计多组边界数据的测试用例
- **异常覆盖**：针对异常验证点，设计各种异常情况的测试用例
- **优先级独立判断**：测试点中的优先级仅供参考，每个用例根据具体场景独立判断；同一测试点可衍生 p0 到 p2 不同级别的用例

### 验证点类型对应

- 功能验证点 → 正向测试用例（验证功能正常工作）
- 边界验证点 → 边界测试用例（验证临界值处理）
- 异常验证点 → 异常测试用例（验证错误处理）
- 集成验证点 → 集成测试用例（验证模块间交互）
- 角色权限验证点 → 功能测试用例（仅验证已确认的角色与业务可见结果）
- 埋点验证点 (Tracking) → `type=埋点`（按已确认事件触发、字段与统计口径断言）
- 兼容性矩阵验证点 (Compatibility) → `type=兼容性矩阵`（逐项覆盖已确认的环境组合与验收结果）

---

## 用例设计方法

生成前读取 `references/case-design-rules.md`；从 `references/test-design-methods.md` 按上游已选方法读取对应章节，不把十二种方法全文重复加载。继承每个 TP 已选的方法，按十二种方法的规则展开可执行场景；若需补选方法，先返回 `test-points` 更新对应 TP 与测试点上下文。`_context.design_methods` 与所有被正式用例引用的 TP 方法集合一致；中等及以上复杂度的 TP 额外做创意测试探索，并在 `_context` 记录新增场景数量。

---

## 用例类型与冒烟分类

测试类型和策略定义见 `references/test-type-strategies.md`。无论用户是否提出冒烟或快速验证，均按当前需求的全部 TP 生成完整用例集，并对完整集执行现有校验（TP 覆盖率 ≥95%）及 Review Gate。冒烟场景作为完整集中的用例分类，仍写入统一 schema v2 JSON，并包含在对应的完整集 XMind 中；不得按 `regression_tier` 或 `type` 单独选取、导出或交付文件。

### 回归套件层级继承

用例从测试点继承 `regression_tier`（Smoke / Full / Targeted），作为完整集内的回归层级分类元数据：

- **继承规则**：用例的 `regression_tier` 默认等于其 `tp_refs` 中最高层级的测试点（Smoke > Full > Targeted）
- **允许降级**：Agent 可将复杂测试点的部分衍生用例降级（如 Smoke 测试点的边界用例降为 Full）
- **不允许升级**：不得将 Full/Targeted 测试点的用例升级为 Smoke，除非用户显式要求
- **未标注兜底**：若上游 testpoints.md 未包含 `regression_tier`，所有用例默认 `Full`
- **分类一致性**：`regression_tier=Smoke` 的用例必须为 p0；`type=冒烟` 同时标记 `regression_tier=Smoke`。仅按有依据的分类标记场景，不按 p0 自动推断 Smoke；层级元数据不触发独立输出

---

## 优先级规则

按风险和业务影响判定优先级，不套固定比例。p0 覆盖核心业务流程、关键入口、阻塞性功能和所有冒烟用例；p1 覆盖常规重要场景；p2 覆盖低频、边缘的功能场景。

---

## 用例字段、粒度与反模式

执行前读取：

- `references/case-design-rules.md`：字段规范、设计方法、JSON 转义和反模式
- `references/case-granularity.md`：复杂度自适应、拆分与合并
- `../_testspec-shared/references/naming-contract.md`：标题与模块命名
- `references/testcases-json-example.md`：schema v2 示例

不可省略的主契约：

- 业务字段必须包含 `module`、`submodule`、`test_name`、`preconditions`、`test_data`、`steps`、`expected_result`、`priority`；其中 `preconditions` 和 `test_data` 可为空
- `steps`、`expected_result` 使用按序号编号的可执行、可验证文本
- 前置条件、测试数据、操作步骤、预期结果能简单就别复杂，只写执行和判定必需的内容；按 `references/case-design-rules.md` 输出直白、通顺、去套话的短句，不增加无关准备、绕行操作或附带检查。四项描述均纳入 Review 门禁。
- 测试数据只列本例操作和判定必需的字段和值；不抄整套配置，不逐项展开无关素材。保留关键取值、单位、边界和必要组合，不按字符数截断。
- 用例场景名称必须简短、直白、见名知意，按共享命名契约保留关键条件和主要意图、删除套话；写完步骤和预期后再复核名称，不把完整流程塞进标题。
- `priority` 只允许 `p0` / `p1` / `p2`
- `id` 在当前变更内唯一；`test_name` 建议使用 `{模块}_{功能点}_{场景}`；`title`、`feature` 作为旧格式兼容字段保留
- `tp_refs` 非空且只引用当前变更 TP；多 TP 用例的步骤和预期覆盖每个引用
- TP 的 `oracle_scope = indirect` 时只断言当前系统可观察产物；`out-of-scope` 不生成正式用例
- `preconditions` 可为空；`test_data` 可为空；`steps` 与 `expected_result` 必须按序号输出
- 角色、权限或对象状态影响结果时必须写入前置条件；边界、取消等场景需排除权限干扰，具体写法见 `references/case-design-rules.md`。
- 每条原生用例写 `origin.kind = testspec-native` 和 `trust.status = provisional`
- JSON 合法转义；生成后必须通过结构校验

---

## 校验与迭代

写入用例后，加载 `references/generation-quality-loop.md` 并运行：

```bash
python "<_testspec-shared-skill-dir>/scripts/validate_testcases.py" \
  --input <变更目录>/artifacts/testcases.json \
  --testpoints <变更目录>/specs/testpoints.md \
  --pretty
```

导出前解决全部错误和未通过的 TP 覆盖，直到门禁通过；缺少产品 Oracle 时返回上游澄清，不虚构预期。warning 必须逐项检查，不得自动忽略。

脚本 PASS 只表示确定性校验通过。`review_candidates` 是待复核的相似用例，不单独阻断导出，须交由 Review H1 比较业务差异；主要目标是否有完整预期，仍须在生成自检和 Review H2/H3 中逐条核对。

## Review 定向返修

用户要求根据 `review-report.md` 修复时进入 repair 模式：

1. 校验 review 与 canonical revision 一致。
2. 只消费 `status = open` 且明确分配给 generate 的 finding；points/analysis finding 必须回到对应上游。
3. 只修改 finding 指定的 case IDs 和字段，默认保留 ID；未命中范围的用例保持字节级语义不变。四项描述返修只删套话、重复和无关内容，保留必要路径、边界与 Oracle；不截断关键值，不把冗余搬到其他字段。
4. 在 `_context.review_repairs` 记录 `issue_id`、`changed_case_ids` 和动作摘要。
5. generate 不得自行把 finding 标记 resolved；修复后必须重跑 testcase-review。

## 输出格式（八项业务字段，默认 XMind）

- 每条用例按以下顺序生成：模块、子模块、测试名称、前置条件（可为空）、测试数据（可为空）、操作步骤（按序号）、预期结果（按序号）、优先级（仅允许 `p0`、`p1`、`p2`）。`id`、`tp_refs`、`type`、`origin`、`trust` 等字段仅用于内部追溯和评审。
- 面向用户的用例只保留必要信息：字段值用短句表达，不输出方法论解释、推理过程或重复背景。
- **XMind（默认）**：XMind 8格式，层级为 `模块 → 子模块 → 用例名称`。场景节点剥离精确匹配的分类前缀，JSON保留完整名称；前缀不符拒绝导出。前置条件、测试数据、操作步骤并列，预期结果在操作步骤下；标签独占首行，内容从下一行开始，空的前置条件和数据省略，多条内容保留在单个节点。`p0`无标记，`p1`/`p2`用对应marker，不增加优先级文本节点。详细约定见共享输出契约。

导出契约统一以 `../_testspec-shared/references/output-contracts.md` 和当前 skill 目录下的 `scripts/generate_xmind.py` 及单测为准。如文档表述与实现冲突，必须以脚本与单测为准，不得擅自改动历史格式。

## 执行步骤

1. 按共享约定定位当前变更，读取 canonical 和直接上游，检查版本及 stale。
2. 消费 TP 的方法、风险、Oracle 范围和回归层级，按相关规则展开完整集；参考资料按需读取。
3. 用标准文件编辑机制写入 schema v2 `artifacts/testcases.json`，不另建根目录副本。字段结构见 `references/testcases-json-example.md`；使用结构化序列化或合法JSON转义。
4. 按本文件“校验与迭代”执行完整校验，修正具体问题；候选交Review复核，不删减用例绕过检查。
5. **XMind（默认）**：从当前已加载SKILL目录解析脚本绝对路径，执行：
   ```bash
   python "<testcase-generate-skill-dir>/scripts/generate_xmind.py" --input <变更目录>/artifacts/testcases.json --output <变更目录>/artifacts/<name>_cases.xmind --title "测试用例"
   ```
6. 保留完整源JSON供Review使用，报告产物路径、数量、覆盖和检查状态，下一步为 `testcase-review`。

---

## 生成后反思

确定性校验后使用 `references/generation-quality-loop.md`。报告迭代次数、具体修正、最终 TP 覆盖率、优先级分布和用例数量。

---

## 依赖

- **XMind**：无额外依赖，使用 XMind 8版本 格式生成，兼容 XMind 桌面版打开
- 当前 skill 的依赖清单位于 `requirements.txt`

## 产物

- 正式产物：`testspec/changes/<name>/artifacts/testcases.json`（schema v2）与 `testspec/changes/<name>/artifacts/<name>_cases.xmind`（默认 XMind 格式）。Excel 不属于默认生成或验收范围。

文件名可根据变更名或用户指定调整。
