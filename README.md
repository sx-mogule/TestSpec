# TestSpec SOP

TestSpec SOP 将已确认的需求转成可执行、可追溯的测试用例。标准流程由四个 Skill 完成，交付 **完整 JSON、XMind、核心 BDD 和评审报告**。业务覆盖和结果判定由评审核实，本地脚本负责检查结构、版本、指纹及导出一致性。

## 快速开始

在仓库目录向 Agent 提供 PRD、蓝湖链接、可交互 HTML 或需求片段，并写清变更名和验收范围。

> 根据提供的材料，按 TestSpec SOP 完成需求分析、测试点、用例和统一评审。变更名为 `example`。对影响验收判定的未确认规则，保留原始依据、待确认问题和受影响范围。

如果 Agent 已识别这些 Skill，按下表顺序调用，也可以让 Agent 读取对应的 `SKILL.md`。开始分析、提炼测试点和生成用例前，读取适用的项目交互规范。根目录当前是 Jellycat 的规范，包含文本和列表边界、拦截行为与默认测试商品。文本长度和列表数量有 PRD 明确口径时，使用该口径。[项目执行规则](AGENTS.md) · [Jellycat 交互与断言规范](project-interaction-spec.md)

## 四个阶段

| 阶段 | 决定什么 | 主要产物 |
|---|---|---|
| 1. 需求分析 | 从原始材料确认范围、业务规则和可观察结果，定位风险及待澄清事项。[prd-analysis](skills/prd-analysis/SKILL.md) | `requirements.md`、`requirements-analysis.md` |
| 2. 测试点 | 按已确认的业务条件、状态和结果差异划分验证目标，记录需求引用、方法、优先级和 Oracle。[test-points](skills/test-points/SKILL.md) | `specs/testpoints.md` |
| 3. 用例生成 | 按 TP 展开前置条件、数据、操作和可观察预期，校验完整集，从当前 JSON 导出并核对 XMind，生成核心 BDD。[testcase-generate](skills/testcase-generate/SKILL.md) | `artifacts/testcases.json`、`<name>_cases.xmind`、`<name>_features.feature` |
| 4. 统一评审 | 依据原始需求评审完整用例和全部伴生 BDD，复用证据完成 SOP 检查，裁定 Gate，在正式交付前再核对 XMind。[testcase-reviewer](skills/testcase-reviewer/SKILL.md) | `review-report.md` |

每项变更使用一个目录。优先读取 `requirements.md`，缺省使用 `proposal.md`。两者都缺失时，由需求分析根据提供的材料建立规范需求源。只有用户明确要求跳过分析时，测试点阶段才从规范需求源降级提炼，并注明低置信度。

```text
testspec/changes/<name>/
├── requirements.md                # 缺省使用 proposal.md
├── requirements-analysis.md
├── specs/
│   └── testpoints.md
├── artifacts/
│   ├── testcases.json              # schema v2 完整用例集
│   ├── <name>_cases.xmind           # 默认 XMind 8 格式
│   └── <name>_features.feature      # 核心主路径与关键异常
└── review-report.md
```

变更目录、产物和校验缓存默认被 Git 忽略，按团队约定归档交付件。[忽略规则](.gitignore)

### 分析和设计要点

- **原始证据。** 蓝湖须核对已取得的页面文字、图片及可读交互，记录缺失项。可交互 HTML 按可访问控件逐项观察并记录结果。已确认业务规则用来确定预期，原型表现和历史用例用来定位差异和回归线索。[蓝湖输入](skills/prd-analysis/references/lanhu-prd-input.md) · [HTML 输入](skills/prd-analysis/references/html-prd-input.md) · [来源规则](skills/_testspec-shared/references/source-provenance.md)
- **测试点的粒度。** 一条 TP 表达一个可独立验证的意图。单一且可判定的规则可以只对应一个 TP。按需求选择方法和类型，执行步骤和具体数据在生成阶段展开。埋点或兼容性用例须有明确口径，已声明的必测环境组合逐项保留。[测试点规则](skills/test-points/references/testpoint-design-rules.md) · [方法选择](skills/test-points/references/test-design-methods.md) · [方法完成标准](skills/testcase-generate/references/test-design-methods.md)
- **完整集与伴生产物。** 用例通过 `tp_refs` 回溯到当前 TP。冒烟是完整集内的分类。JSON 的八项业务字段、XMind 结构和 Gherkin 规则统一见输出契约。BDD 核心场景描述业务事件及可观察结果。[输出契约](skills/_testspec-shared/references/output-contracts.md) · [用例写法](skills/testcase-generate/references/case-design-rules.md)

## 评审与交付

同一模型先形成通用评审反馈，再用已核实的证据执行 R1–R6、H1–H8。伴生 BDD 单列场景评审，对照需求与 JSON 核对核心业务结果。报告保留原始 GR 发现及逐项处置、SOP 分级和 Gate，以及实际评审的 JSON、TP 和全部 BDD 的 SHA-256。标准和加深模式采用相同的分级标准，加深模式会追查更多原文和用例证据。[评审流程](skills/testcase-reviewer/testcase-review/review-workflow.md) · [报告模板](skills/_testspec-shared/templates/review-report-template.md)

| 判断 | 依据 |
|---|---|
| 引用覆盖 | 按 `tp_refs` 计算，95% 是生成校验和 Strict 模式下 R1 的通过线。 |
| 实际覆盖 | H3/H5 核对业务条件、动作和结果。即使 TP 引用率为 100%，已确认的必测边界漏测或关键结果无法判定，仍可能触发 S1。 |
| 未决口径 | 保留原 `Q-xxx` 和受影响的验收。已确认部分继续生成和评审。当前范围内仍影响关键验收的问题按 H5 记 S1；执行数据准备等事项记录为 `dynamic_followups`。 |
| 交付产物 | XMind 缺失或与当前 JSON 不一致时，标准交付待补并退回生成阶段。用例评审的 Gate 根据其实际评审输入判定。 |

**标准交付同时满足以下三项。**

- 通用评审、BDD 场景评审、SOP 检查和逐项处置已完成。输入不齐时，记录缺项和可核实的评审结论。
- `review_gate.status = pass`，`s1_unresolved_count` 和 `description_unresolved_count` 均为 0，`s1_issue_ids` 和 `description_issue_ids` 均为空。
- 实际 XMind 和当前 JSON 比对通过。

前置条件、测试数据、操作步骤和预期结果属于四项描述。已确认的描述问题即使分为 S2/S3 或标记为 `accepted`，仍须复审为 `resolved` 才能通过描述门禁。[评审维度与分级](skills/testcase-reviewer/testcase-review/references/review-dimensions.md) · [报告与 Gate 契约](skills/_testspec-shared/references/output-contracts.md#review-reportmd)

## 变更、返修与重评

- **规范需求变化。** 分析产物记录实际分析文件的 `canonical_source_sha256`。已有指纹时，即使 `source_revision` 未变，内容变化也会要求重新分析。业务口径确认变化后，由 `prd-analysis` 更新版本并标记下游过期。历史分析可按版本读取，经重新核对原文后建立指纹基线。[上下文协议](skills/_testspec-shared/references/context-protocol.md)
- **按责任阶段返修。** 需求口径交 `prd-analysis`，TP 缺口交 `test-points`，用例或 BDD 问题交 `testcase-generate`。授权返修时依据原 issue ID 和范围处理。被选中的已 `accepted` 描述问题先由 Review 重开，最终仍由 Review 判断是否解决。[生成返修规则](skills/testcase-generate/SKILL.md) · [评审处置规则](skills/testcase-reviewer/testcase-review/references/independent-reviewer.md)
- **有变化就复核实际产物。** JSON 变更后重新导出并比对 XMind。JSON、TP 或 BDD 内容变化，以及 BDD 文件集合变化，均须重评并更新实际评审的指纹。缺少所需评审记录或指纹的旧报告须重评后才能作为当前交付依据。[输出契约](skills/_testspec-shared/references/output-contracts.md#review-reportmd)

## 本地命令

命令在仓库根目录运行，使用 Python 3。先替换变更名。交付使用自定义 XMind 文件名时，将 `XMIND_PATH` 设为实际交付文件。

```bash
CHANGE_NAME="example"
CHANGE_DIR="testspec/changes/$CHANGE_NAME"
XMIND_PATH="$CHANGE_DIR/artifacts/${CHANGE_NAME}_cases.xmind"
```

### 需求分析完成后

```bash
CANONICAL="$CHANGE_DIR/requirements.md"
if [ ! -f "$CANONICAL" ]; then
  CANONICAL="$CHANGE_DIR/proposal.md"
fi

python3 -B skills/_testspec-shared/scripts/fingerprint_inputs.py "$CANONICAL"
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through analysis
```

指纹命令读取文件并输出摘要。分析阶段把实际分析的规范需求文件指纹记录到分析上下文。

### 生成及导出

```bash
python3 -B skills/_testspec-shared/scripts/validate_testcases.py \
  --input "$CHANGE_DIR/artifacts/testcases.json" \
  --testpoints "$CHANGE_DIR/specs/testpoints.md" \
  --full --pretty

python3 -B skills/testcase-generate/scripts/generate_xmind.py \
  --input "$CHANGE_DIR/artifacts/testcases.json" \
  --output "$XMIND_PATH" --title "测试用例"

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py xmind \
  --json "$CHANGE_DIR/artifacts/testcases.json" --xmind "$XMIND_PATH"

python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through generate
```

用例校验返回 `WARN` 或 `FAIL` 时逐项核查，退出码为非零。`--full` 在标准输出给出完整明细。XMind 导出会覆盖同名目标文件。

### 评审报告保存后

```bash
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through review

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py review \
  --report "$CHANGE_DIR/review-report.md"

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py feedback \
  --report "$CHANGE_DIR/review-report.md"
```

正式交付前，对实际交付件再执行一次上面的 `xmind` 比对。上下文校验可用 `--expected-version` 核对指定版本。结构合法的 `blocked` 报告也可以通过脚本校验，交付结论看 Gate 和实际产物。业务语义、Gherkin 场景质量和产品执行各有对应的评审或测试。

## 仓库维护

```bash
python3 -B -m unittest discover -s skills/prd-analysis/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/testcase-generate/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/_testspec-shared/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/testcase-reviewer/testcase-review/tests -p 'test_*.py'

python3 -B skills/_testspec-shared/scripts/validate_skill_contracts.py
python3 -B skills/_testspec-shared/scripts/validate_evals.py
python3 -B skills/testcase-reviewer/scripts/validate_skill_repo.py skills/testcase-reviewer
```

`validate_evals.py` 检查评测定义。模型实际评测、真实需求试跑及产品执行分别记录结果。
