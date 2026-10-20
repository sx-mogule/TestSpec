---
name: prd-analysis
license: MIT
description: TestSpec 需求分析和梳理（流程第 1 步）- 对需求做深度测试分析，运用等价类、边界值、状态迁移等方法，产出 requirements-analysis.md。当用户要「分析需求」「梳理测试点」「做需求分析」「拆解可测项」或执行 prd-analysis / prd analysis 时使用。也适用于用户说「这个 PRD 有哪些要测的」「帮我分析一下测试范围」「需求评审准备」的场景。注意：如果用户要的是简短的测试点清单而非深度分析，应使用 test-points。
---

# prd-analysis：需求分析和梳理

铁律：绝不能用重新排版的 PRD 冒充需求分析；每个问题都必须说明它为何影响测试。

```text
TestSpec 分析进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载 requirements/proposal 和可用 source 材料 ⚠️ 必需
- [ ] 步骤 3：从 references/analysis-modes.md 选择分析模式
- [ ] 步骤 4：分析风险、缺口和可测试性
- [ ] 步骤 5：歧义影响测试设计时执行需求审问闭环
- [ ] 步骤 6：反思、写入 context 元数据并报告下一步
```

## 职责

对需求进行**深度测试分析**，先基于用户目标和上下文选择合适的分析模式，再产出结构化的 `requirements-analysis.md`。核心价值是**发现隐含风险、缺失信息和逻辑漏洞**，而不是把需求文档换个格式重新罗列。

**与 test-points 的分工**：analysis 做深度拆解（"为什么要测、有哪些风险"），points 从 analysis 中提炼精简清单（"要测什么"，一句话一条）。

首次按 `../_testspec-shared/references/execution-efficiency.md` 的相关章节核对输入哈希和读取范围；同一会话已读且未变的内容可复用，不重复加载本阶段无关章节。阶段与门禁照常执行。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 分析模式单一数据源：`references/analysis-modes.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 产物模板：`references/requirements-analysis-template.md`
- 需求审问闭环：`references/interrogation-loop.md`
- 蓝湖 PRD 输入适配：`references/lanhu-prd-input.md`
- HTML 需求输入交互核对：`references/html-prd-input.md`
- 来源与 TestLib 信任：`../_testspec-shared/references/source-provenance.md`

## 执行步骤

1. **确定当前变更目录**。
2. **读取上下文**：优先读取 `requirements.md`（若存在）；否则读取 `proposal.md`；若两者都不存在，则使用用户本次提供的 PRD、用户故事或需求片段，并先创建最小 `testspec/changes/<name>/` 工作区与 canonical 需求源。若有外部需求文档，尽可能获取内容；本轮新提供的 HTML 即使已有 `requirements.md` 也必须读取，与 canonical 内容核对并更新来源记录；冲突未确认时进入阻塞澄清，不沿用旧口径掩盖新材料。若输入为可交互 HTML 文件，按 `references/html-prd-input.md` 逐项核对按钮及其可观察结果；若链接来自蓝湖，先读取 `references/lanhu-prd-input.md`，再使用 `<prd-analysis-skill-dir>/scripts/direct_extract_axure.py` 走直连读取，并按该说明逐页读取文字与图片内容、核对完整性。
3. **判定分析模式**：根据用户目标和输入材料，从 `references/analysis-modes.md` 中选择一个或多个模式。
4. **按模式执行分析**：合并模式结果，生成兼容现有结构的 `requirements-analysis.md`。
5. **告知用户**：文件路径及下一步可执行 test-points 提炼测试要点。

---

## 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

### 材料评估与上下文消费

1. 读取所有可用需求输入（优先 requirements.md，其次 proposal.md、用户提供的 PRD/需求片段、外部链接）。蓝湖链接按 `references/lanhu-prd-input.md` 对全部页面、文字、图片和可见交互状态建立阅读记录并归档到 canonical source；未逐张视觉阅读的图片不得标为已读，未读资源须明确标为缺口。可交互 HTML 文件按 `references/html-prd-input.md` 建立按钮清单并逐项点击核对；静态源码盘点不能代替点击验证。本 skill 不扫描被测系统的底层生产代码；HTML 结构只用于定位用户提供的需求页面控件，交互结果按来源证据分层，不能直接当作生产系统的业务 Oracle。
2. 检查上游产物是否包含上下文元数据（按 `../_testspec-shared/references/context-protocol.md`）
3. 评估信息密度和关键信号：
   - 若存在 requirements.md：以其「功能列表」「边界声明」「风险点」「阻塞澄清项」「执行期动态跟进」作为主需求源；blocking_open_questions 直接纳入质询清单种子输入，dynamic_followups 作为执行期关注点记录但不阻塞分析
   - 将 requirements.md（否则 proposal.md）作为 canonical source。若其 context 有 `source_revision`，本次生成必须原样复制该版本；不得自行递增
   - canonical source 有版本，而现有 requirements-analysis.md 缺少版本、版本更低，或 stale 列表命中 requirements-analysis.md：重新生成分析，不复用旧口径结论
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

**产出**：按 `references/requirements-analysis-template.md` 的假设扫描小节记录模块、待核查方向、状态、证据和整体信心。

**下游影响**：

- confirmed 假设进入 `risks_identified`，注明证据位置
- unverified 假设仅作为后续核查提示，不改变测试点优先级和用例数量
- rejected 假设保留一句结论，避免后续重复猜测

### 模式推理

根据材料的主要风险、歧义和用户目标选择 `references/analysis-modes.md` 中适用的模式。信息缺失关注completeness，状态逻辑关注logic，验收含糊关注testability，术语和冲突分别关注clarity、consistency；用户明确指定时遵从其选择。未指定时以completeness、testability、logic兜底，说明理由，不机械按关键词匹配。

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
2. **价值检查**：产出中有多少内容是直接从需求文档复述的？每个问题是否指出了"为什么这是风险"？
3. **迭代决策**：points 作者能否从这份分析中直接提炼测试点？

反思后修正产物，最多 2 轮迭代。告知用户迭代次数和修正摘要。

### 上下文播种

按 `../_testspec-shared/references/context-protocol.md` 写入唯一闭合的 context，传播 canonical 版本、来源策略、证据、问题、质量和 stale 信息。`source_skill` 为 `prd-analysis`，下一步为 `test-points`。

本阶段补充：
- `thinking_summary`、`strategy_used`：简要记录分析模式及原因。
- `risks_identified`：仅写有来源依据的风险；`intuition_flags` 保留假设的状态和证据。
- `testlib_coverage`：实际扫描状态、相关模块、已有用例数、可复用项、回归风险及信任过滤条件；未命中不虚构复用结论。

## 反模式识别（Agent 自检参照）

> 生成产物后，对照以下反模式自查。发现符合的情况时自动修正。

| 反模式       | 表现                                       | 正确做法                                                   |
| ------------ | ------------------------------------------ | ---------------------------------------------------------- |
| **需求复述** | 分析内容只是把需求文档换了个说法重写一遍   | 每个分析项必须指出"为什么这是风险"或"缺了什么"             |
| **万能模板** | 所有功能模块的分析结构完全相同，缺少针对性 | 根据模块特性选择性使用分析框架，复杂模块深入、简单模块精简 |
| **伪风险**   | 风险点全是"可能出错""需要注意"等泛泛之言   | 风险必须指向具体场景（"并发修改同一订单时状态冲突"）       |
| **实现泄漏** | 本阶段直接扫描代码，或把实现行为混入产品需求 | 本阶段只消费需求材料；用户提供的实现证据必须留在实现证据附录 |
| **过度发散** | 分析了大量与当前需求无关的"最佳实践"       | 只分析当前需求范围内的内容，标注明确的需求边界             |
| **缺失审问** | 发现需求不明确但没有列出问题清单           | 发现不明确处必须产出结构化问题，标注测试影响               |

---

## 需求审问（Agentic 能力）

当需求存在会影响用例设计或测试结果判断的不明确项时，加载 `references/interrogation-loop.md`，生成「需求审问清单」并支持后续回答合并。

---

## 分析基线与边界

分析覆盖Functional、Boundary、Exception、Integration的可观察行为，有明确口径时下传Tracking和Compatibility。各分析项聚焦单一业务意图；需求不明确进入澄清，不生成步骤、测试数据、接口字段或实现细节。通用方法、功能拆解基线及禁止项见 `references/analysis-modes.md` 的“分析基线与边界”，需要时读取，不重复加载全部模式。

## 产出结构

严格按 `references/requirements-analysis-template.md` 写入完整结构。执行前读取该模板；不要在 SKILL.md 中临时发明平行格式。至少保留：

- 需求来源、分析摘要和假设扫描
- 有证据的位置化问题、已明确内容和建议补充
- 按模块组织的输入/输出、边界、状态、业务规则和风险
- testlib 已有覆盖摘要（仅在实际命中时）
- 阻塞澄清项、执行期动态跟进
- 文件末尾 canonical revision envelope

兼容约束见 `../_testspec-shared/references/output-contracts.md`。

## 产物

- `testspec/changes/<name>/requirements-analysis.md`
