---
name: prd-analysis
license: MIT
description: TestSpec 需求分析和梳理（流程第 1 步）- 对需求做深度测试分析，运用等价类、边界值、状态迁移等方法，产出 requirements-analysis.md。当用户要「分析需求」「梳理测试点」「做需求分析」「拆解可测项」或执行 prd-analysis / prd analysis 时使用。也适用于用户说「这个 PRD 有哪些要测的」「帮我分析一下测试范围」「需求评审准备」的场景。注意：如果用户要的是简短的测试点清单而非深度分析，应使用 test-points。
---

# prd-analysis：需求分析和梳理

铁律：绝不能用重新排版的 PRD 冒充需求分析；每个问题都必须说明它为何影响测试。

## 职责

对需求进行**深度测试分析**，先基于用户目标和上下文选择合适的分析模式，再产出结构化的 `requirements-analysis.md`。核心价值是**发现隐含风险、缺失信息和逻辑漏洞**，而不是把需求文档换个格式重新罗列。

**与 test-points 的分工**：analysis 做深度拆解（"为什么要测、有哪些风险"），points 从 analysis 中提炼精简清单（"要测什么"，一句话一条）。

首次按 `../_testspec-shared/references/execution-efficiency.md` 的相关章节核对输入哈希和读取范围；同一会话已读且未变的内容可复用，不重复加载本阶段无关章节。阶段与门禁照常执行。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 分析模式单一数据源：`references/analysis-modes.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 产物模板：`../_testspec-shared/templates/requirements-analysis-template.md`
- 需求审问闭环：`references/interrogation-loop.md`
- 蓝湖 PRD 输入适配：`references/lanhu-prd-input.md`
- HTML 需求输入交互核对：`references/html-prd-input.md`
- 来源与 TestLib 信任：`../_testspec-shared/references/source-provenance.md`

## 执行步骤

1. **确定当前变更目录**。
2. **读取并交接需求**：按下文核对原始材料、canonical 文件和版本，处理冲突后再生成分析。
3. **判定分析模式**：根据用户目标、已知风险及其对范围和验收判断的影响，从 `references/analysis-modes.md` 中选择相关模式；信号数量仅辅助定位，不限制高影响问题的分析深度。
4. **按模式执行分析**：合并模式结果，生成兼容现有结构的 `requirements-analysis.md`。
5. **告知用户**：文件路径及下一步可执行 test-points 提炼测试要点。

---

## 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

### 材料评估与需求交接

1. 选 `requirements.md` 为 canonical，缺省用 `proposal.md`。两者都缺失时，从用户提供的需求材料建立最小需求源。读取本轮新增材料并与当前口径核对。蓝湖按 `references/lanhu-prd-input.md` 用 `scripts/direct_extract_axure.py` 提取后逐页核对文字、逐张阅读图片，记录未读缺口。可交互 HTML 按 `references/html-prd-input.md` 逐项点击并保留观察证据。原型现象不直接作为验收结果。本阶段只消费用户提供的实现证据。
2. 用共享 `fingerprint_inputs.py <canonical 文件>` 计算实际字节的 SHA-256，与已有分析的 `canonical_source_sha256` 比较，并按 `../_testspec-shared/references/context-protocol.md` 完成版本交接。即使版本号相同，内容变化也须回到原文核实。确认业务规则或验收口径变更后，由本阶段更新 canonical 版本并标记分析、TP、JSON、XMind、相关 BDD 和报告过期；已有对应新版本时直接继承。未确认的冲突进入需求审问，保留旧分析的指纹和受影响范围。首次记录指纹时先核对内容与分析，勿用新指纹替旧分析背书。
3. 评估需求质量、主要风险及其对验收结论的影响；信息密度和关键信号只辅助定位与分流，不单独决定分析深度：
   - 若存在 requirements.md：以其「功能列表」「边界声明」「风险点」「阻塞澄清项」「执行期动态跟进」作为主需求源；blocking_open_questions 直接纳入质询清单种子输入，dynamic_followups 作为执行期关注点记录但不阻塞分析
   - 已确认的 canonical 正文变化、分析版本落后或分析被标记过期时，按本轮口径重新生成分析
   - canonical source 无版本：按 Legacy 模式继续并告警，不得伪造 `source_revision`
   - 重新生成成功后，从向下传播的 stale 列表移除 requirements-analysis.md，保留仍需重跑的 testpoints/cases/review，并把 `next_skill` 指向 test-points
   - 若 requirements.md context 中 `requirement_quality.readiness` 为 `blocked` 或 `needs_revision`：先提示用户需求质量不足；若用户仍要求继续，则加深质询并在 requirements-analysis.md 中标注低置信度
   - 检查 proposal.md 中「协作确认」勾选状态：全部未勾选 → `material_quality` 预判为 `low`，自动加深质询力度；已填写的「关键问题」项直接纳入质询清单种子输入
   - 保持 `canonical_source_policy = prd-first`；只消费用户提供且可追溯的实现证据，按 intended / observed / inferred / unverified 分层；代码不可访问不得成为阻塞项
   - `conflict/code-only/unknown` 仍未产品确认时，只进入阻塞澄清，不得进入已明确需求、风险事实、测试点优先级或 oracle
4. **扫描 testlib 已有覆盖**（若 `testspec/testlib/index.json` 存在）：
   - 从 proposal.md 提取被测模块关键词
   - 读取 `index.json`，匹配相关模块和功能
   - 统计已有用例数、优先级分布、已覆盖功能点和关联功能
   - 仅当需要参考具体用例内容时，再按 `index.json` 中的 `file` 路径定点读取对应 `<feature>.json`
   - TestLib 只用于回归、命名和覆盖提示，不覆盖 PRD；`legacy-import + unverified` 不得成为风险证据或 oracle
   - 结论纳入分析：哪些已验证功能可复用、哪些是新增、哪些历史用例需要审计

### 假设扫描

> 在正式分析前快速记录可能遗漏的方向。这里产生的是待验证假设，不是风险结论。

在完成材料评估后、进入正式模式推理前，快速浏览需求材料并记录待验证假设：

1. **待核查模块**：哪个模块可能存在未显式说明的状态、权限或边界？
2. **过于顺畅的描述**：哪些描述可能省略了异常或依赖？
3. **质量直觉**：对整体需求质量的信心评估（几成把握认为信息足够设计测试？）

**规则**：

- 每条假设标记 `unverified`，并在正式分析中寻找需求、接口、设计或历史用例证据
- 找到证据后才能进入 `risks_identified`，并记录证据位置
- 未找到证据的假设保留在 `intuition_flags`，不得自动提高 points 优先级或增加 generate 用例
- 扫描控制在 30 秒到 1 分钟

**产出**：按 `../_testspec-shared/templates/requirements-analysis-template.md` 的假设扫描小节记录模块、待核查方向、状态、证据和整体信心。

**下游影响**：

- confirmed 假设进入 `risks_identified`，注明证据位置
- unverified 假设仅作为后续核查提示，不改变测试点优先级和用例数量
- rejected 假设保留一句结论，避免后续重复猜测

### 模式推理

根据材料的主要风险、歧义和用户目标选择 `references/analysis-modes.md` 中适用的模式。信息缺失关注completeness，状态逻辑关注logic，验收含糊关注testability，术语和冲突分别关注clarity、consistency；用户明确指定时遵从其选择。无法判断相关模式时，以completeness、testability、logic做基础检查，再按风险追加；信号数量少不作为跳过理由。

### 工具使用决策

- 信息不足时，主动获取外部信息（按 `../_testspec-shared/references/thinking-protocol.md` 的优先级）
- 信息足够时，直接进入分析

### 执行原则

- 先做推理判断，再分析，不要一上来套统一大模板
- 只读取本次任务需要的模式定义，避免把所有模式全文复述给用户
- 分析结论聚焦"为什么这是风险/缺口"，不输出测试步骤和具体数据
- 发现需求不明确时，标记"需与产品确认"，不要替需求方编造规则
- 不要把 requirements.md 再格式化一遍；analysis 必须指出需求对测试设计、验收判断或覆盖策略的影响

---

## 反思与迭代

> 按 `../_testspec-shared/references/reflection-protocol.md` 执行产物反思。

产物首次生成后，执行反思循环：

1. **完整性检查**：是否有功能模块被跳过？风险点是否仅停留表面？
2. **证据与影响**：每个风险能否回到有依据的业务场景，说明哪个条件、状态或结果会影响验收？只记录适用范围内的风险，将未决规则留给澄清。
3. **迭代决策**：points 作者能否从这份分析中直接提炼测试点？

反思后修正产物，最多 2 轮迭代。告知用户迭代次数和修正摘要。

### 上下文播种

按 `../_testspec-shared/references/context-protocol.md` 写入唯一闭合的 context，传播 canonical 版本、来源、证据、问题、质量和 stale 信息。规范需求文件写入完成后，记录本轮实际分析的 `canonical_source_sha256` 并运行共享 `validate_context_chain.py --change-dir <变更目录> --through analysis`。`source_skill` 为 `prd-analysis`，下一步为 `test-points`。

本阶段补充：
- `thinking_summary`、`strategy_used`：简要记录分析模式及原因。
- `risks_identified`：仅写有来源依据的风险；`intuition_flags` 保留假设的状态和证据。
- `testlib_coverage`：实际扫描状态、相关模块、已有用例数、可复用项、回归风险及信任过滤条件；未命中不虚构复用结论。

## 需求审问（Agentic 能力）

当需求存在会影响用例设计或测试结果判断的不明确项时，加载 `references/interrogation-loop.md`，生成「需求审问清单」并支持后续回答合并。

---

## 分析基线与边界

分析覆盖Functional、Boundary、Exception、Integration的可观察行为，有明确口径时下传Tracking和Compatibility。各分析项聚焦单一业务意图；需求不明确进入澄清，不生成步骤、测试数据、接口字段或实现细节。通用方法、功能拆解基线及禁止项见 `references/analysis-modes.md` 的“分析基线与边界”，需要时读取，不重复加载全部模式。

## 产出结构

严格按 `../_testspec-shared/templates/requirements-analysis-template.md` 写入完整结构。执行前读取该模板；不要在 SKILL.md 中临时发明平行格式。至少保留：

- 需求来源、分析摘要和假设扫描
- 有证据的位置化问题、已明确内容和建议补充
- 按模块组织的输入/输出、边界、状态、业务规则和风险
- testlib 已有覆盖摘要（仅在实际命中时）
- 阻塞澄清项、执行期动态跟进
- 文件末尾 canonical revision envelope

兼容约束见 `../_testspec-shared/references/output-contracts.md`。

## 产物

- `testspec/changes/<name>/requirements-analysis.md`
