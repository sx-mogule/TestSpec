# TestSpec SOP

TestSpec SOP 是一套将产品需求转化为**可执行、可追溯、可评审**测试用例的标准化工作流。流程由四个公开 Skill 串联驱动，并依托共享契约、模板与校验脚本保证上下文版本、设计方法、产物格式和评审门禁的一致性。

默认交付四类产物：**完整用例 JSON**（`artifacts/testcases.json`）、**XMind 8 思维导图**（`artifacts/<name>_cases.xmind`）、**核心伴生 BDD 特性文件**（`artifacts/<name>_features.feature`）及**统一评审报告**（`review-report.md`）。

---

## 1. 仓库与 Skills 总览

| 目录 / 文件 | 角色 | 核心职责 |
|---|---|---|
| [prd-analysis](skills/prd-analysis/SKILL.md) | 阶段 1：需求分析 | 建立规范需求源，核对蓝湖/HTML/历史覆盖，识别风险、边界与阻塞澄清项 |
| [test-points](skills/test-points/SKILL.md) | 阶段 2：测试点设计 | 按业务差异、6 大分类与 12 种设计方法提炼独立验证目标，建立命名字典与需求去向 |
| [testcase-generate](skills/testcase-generate/SKILL.md) | 阶段 3：用例生成 | 按 TP 展开八字段 schema v2 用例，自检并导出 XMind，提炼核心 BDD，支持按 issue 定向返修 |
| [testcase-reviewer](skills/testcase-reviewer/SKILL.md) | 阶段 4：统一评审 | 同一模型先做通用评审与伴生 BDD 场景评审，再执行 SOP 14 项检查与四项描述门禁，裁定 Gate |
| [_testspec-shared](skills/_testspec-shared/) | 共享底座 | 统一维护上下文协议、输出/命名/来源契约、反思与思考协议、报告模板及确定性校验脚本 |
| [AGENTS.md](AGENTS.md) | 仓库执行规则 | 定义工作原则、伴生 BDD 强制模式，以及优先读取项目交互规范的路由要求 |
| [project-interaction-spec.md](project-interaction-spec.md) | 项目交互与断言规范 | 定义当前项目的默认文本/列表上限、硬拦截/置灰行为与基准测试商品（当前为 Jellycat 规范） |

> 注：`testcase-reviewer` 为唯一评审入口（原独立 `testcase-review` 已内聚为其子模块 [testcase-review/review-workflow.md](skills/testcase-reviewer/testcase-review/review-workflow.md)）。除四阶段 SOP 外，它也支持对普通测试用例、测试套件或 BDD/Gherkin 单独执行 `review`、`rewrite`、`hybrid` 及 BDD `generate`。

---

## 2. 快速开始

1. **确认项目规范**：阶段 1–3 执行前优先读取根目录或变更目录下的 [project-interaction-spec.md](project-interaction-spec.md)。文本长度、列表数量在 PRD 有明确口径时以 PRD 为准；未特殊注明时遵循项目规范，严禁臆造错误弹窗或 Toast。
2. **准备需求材料**：在工作区提供 PRD 文档、蓝湖链接、可交互 HTML 或需求片段，并写明**变更名（`<name>`）**和**验收范围**。
3. **按四阶段顺序调用**：

```text
请根据提供的需求材料，按 TestSpec SOP 依次执行 prd-analysis、test-points、testcase-generate 与 testcase-reviewer。
变更名为 `<name>`；影响验收判定的未确认规则请保留原始依据、Q 编号与受影响范围。
```

### 变更目录结构

每项变更独占 `testspec/changes/<name>/`（已默认配置在 [.gitignore](.gitignore) 中）：

```text
testspec/changes/<name>/
├── requirements.md                  # 规范需求源（缺省时使用 proposal.md）
├── requirements-analysis.md         # 阶段 1 产物：深度需求分析
├── specs/
│   └── testpoints.md                # 阶段 2 产物：测试点清单与命名字典
├── artifacts/
│   ├── testcases.json               # 阶段 3 产物：schema v2 完整用例集
│   ├── <name>_cases.xmind           # 阶段 3 产物：XMind 8 导图（默认导出）
│   └── <name>_features.feature      # 阶段 3 产物：核心主路径与关键异常 BDD
└── review-report.md                 # 阶段 4 产物：通用评审 + BDD 评审 + SOP 门禁报告
```

> 内部校验缓存（`.testspec-cache/`）与可选 Excel 均不属于标准交付物或验收门禁。

---

## 3. 四阶段工作流详解

```text
原始材料（PRD / 蓝湖 / HTML）
   │
   ▼
[1. prd-analysis] ──▶ requirements.md + requirements-analysis.md（含 canonical_source_sha256）
   │
   ▼
[2. test-points]  ──▶ specs/testpoints.md（6 大分类 + 12 种方法 + 命名字典）
   │
   ▼
[3. testcase-generate] ──▶ testcases.json + <name>_cases.xmind + <name>_features.feature
   │                          ▲                                        │
   ▼                          └────────── 定向返修（open issue） ────────┘
[4. testcase-reviewer] ──▶ review-report.md（GR 通用反馈 + BDD 评审 + R1–R6/H1–H8 + 四项描述门禁）
```

默认按完整四阶段链路执行；仅在用户明确要求跳步时，下游才允许基于规范需求源降级执行并标注低置信度。

### 阶段 1：`prd-analysis`（需求分析）

- **输入适配**：
  - **文本/PRD**：优先读取 `requirements.md`，缺省 `proposal.md`；均缺失时根据材料建立最小规范需求源。用 [fingerprint_inputs.py](skills/_testspec-shared/scripts/fingerprint_inputs.py) 记录实际分析文件的 `canonical_source_sha256`。
  - **蓝湖 / Axure**：按 [lanhu-prd-input.md](skills/prd-analysis/references/lanhu-prd-input.md) 调用 [direct_extract_axure.py](skills/prd-analysis/scripts/direct_extract_axure.py) 全量提取页面与图片，逐页核对文字并逐张视觉阅读图片，记录未读缺口。
  - **可交互 HTML**：按 [html-prd-input.md](skills/prd-analysis/references/html-prd-input.md) 盘点页面与状态，为控件分配稳定 `BTN-001`… ID 并逐项安全点击，严格区分观察行为（`observed`）与需求预期（`intended`）。
  - **TestLib 扫描**：若 `testspec/testlib/index.json` 存在，匹配相关模块用于复用与回归提示；`legacy-import + unverified` 不得作为需求事实或 Oracle。
- **分析方法**：自适应选用 [analysis-modes.md](skills/prd-analysis/references/analysis-modes.md) 中的 5 种模式（`completeness`、`testability`、`clarity`、`consistency`、`logic`），先做 30–60 秒**假设扫描**（未证实假设仅留在 `intuition_flags`），生成后最多进行 2 轮反思迭代。
- **问题分流**：影响范围或判定的缺口进入 [interrogation-loop.md](skills/prd-analysis/references/interrogation-loop.md) 与 `blocking_open_questions`；执行期数据准备等不影响口径的事项记为 `dynamic_followups`。

### 阶段 2：`test-points`（测试点设计）

- **准入与粒度**：校验上游分析版本与指纹一致后，按 [testpoint-design-rules.md](skills/test-points/references/testpoint-design-rules.md) 提炼测试点。只描述**验证什么（What）**，不写操作步骤与具体测试数据。
- **分类与编号**：格式为 `TP_<MODULE>_<FEATURE>_<SEQ>`，模块/功能点缩写定义在顶部「命名字典」中，标题强制三段式 `{模块}_{功能点}_{验证意图}`：

| 分类 | 序号范围 | 适用范围 |
|---|---|---|
| `Functional` | `001–099` | 常规功能、规则组合、主分支及业务不变量 |
| `Boundary` | `100–199` | 上下界端点、邻近值、空值/超限拦截 |
| `Exception` | `200–299` | 异常输入、错误推断、非法状态流转、异常防御 |
| `Integration` | `300–399` | 跨模块状态或数据传递（仅断言本系统可观察结果） |
| `Tracking` | `400–499` | 需求明确规定触发时机、字段或统计口径的埋点 |
| `Compatibility` | `500–599` | 需求明确声明平台/系统/浏览器组合及结果的兼容性矩阵 |

> 独立 API、协议、安全攻防、性能负载等未授权类型不进入本流程。

- **设计方法**：每个 TP 须从 12 种正式方法中选择并标注（`等价类`、`边界值`、`判定表`、`流程分析`、`状态迁移`、`错误推断`、`正交实验`、`因果图`、`配对组合`、`基于属性的测试`、`变形测试`、`语法规则分析`），方法集合同步写入 `_context.design_methods`。`基于风险的测试设计` 与 `探索式测试` 仅作辅助策略，不写入 `design_methods`。[方法选用规则](skills/test-points/references/test-design-methods.md) · [方法完成标准](skills/testcase-generate/references/test-design-methods.md)
- **去向与待澄清**：未决规则保留 `Q-xxx` 编号并标 `oracle_status: needs-confirmation`，与已确认排除范围均不分配正式 `TP_ID`。

### 阶段 3：`testcase-generate`（用例生成与导出）

- **结构与命名**：依据 [test-type-strategies.md](skills/testcase-generate/references/test-type-strategies.md)、[case-design-rules.md](skills/testcase-generate/references/case-design-rules.md) 与 [naming-contract.md](skills/_testspec-shared/references/naming-contract.md) 展开为 `schema_version: 2` 的 `artifacts/testcases.json`：
  - **8 项核心业务字段**：`module`、`submodule`、`test_name`（`{模块}_{功能点}_{简短场景}`）、`preconditions`、`test_data`、`steps`、`expected_result`、`priority`（`p0`/`p1`/`p2`）。
  - **追溯与分类字段**：`id`、`tp_refs`（100% 关联当前 TP）、`type`（`冒烟`/`正向`/`负向`/`边界`/`异常`/`埋点`/`兼容性矩阵`/`其他`）、`regression_tier`（`Smoke`/`Full`/`Targeted`）、`origin`（`testspec-native`）、`trust`（`provisional`）。
  - **冒烟不拆集**：`type=冒烟` 与 `regression_tier=Smoke` 必须为 `p0`，保留在完整用例集和完整 XMind 中，不派生独立 Smoke 文件。
- **四项描述原则**：采用直白短句，删去套话、重复背景、无关配置与多余步骤；连续动作可合写，关键条件、准确边界取值和可观察 Oracle 必须保留；步骤与预期按阶段和检查点组织，不强制一一配对。
- **校验与导出**：
  1. 运行 [validate_testcases.py](skills/_testspec-shared/scripts/validate_testcases.py) 自检格式、方法对齐、特殊分类匹配与 TP 覆盖率（**≥95%**）。
  2. 运行 [generate_xmind.py](skills/testcase-generate/scripts/generate_xmind.py) 导出 XMind 8（剥离 `{模块}_{功能点}_` 前缀仅展示场景名；`p0` 无 marker，`p1`/`p2` 分别使用 `priority-1`/`priority-2`；空前置/数据省略节点；操作步骤为空而预期非空时拒绝导出）。
  3. 运行 [verify_eval_artifacts.py](skills/_testspec-shared/scripts/verify_eval_artifacts.py) `xmind` 子命令逐例核对 XML 与 JSON 一致性。
- **伴生 BDD**：从完整集中提取核心主成功路径（MSS）与关键异常路径（ERR），以业务领域语言编写 `artifacts/<name>_features.feature`（避免 UI 点击脚本流水账，`When` 聚焦单一事件，`Then` 给出可观察业务结果），并运行 `validate_context_chain.py --through generate`。

### 阶段 4：`testcase-reviewer`（统一评审与交付门禁）

- **执行模式与深度**：按 [review-workflow.md](skills/testcase-reviewer/testcase-review/review-workflow.md) 与 [independent-reviewer.md](skills/testcase-reviewer/testcase-review/references/independent-reviewer.md) 由同一模型依次执行：
  1. **通用评审 + BDD 场景评审**：基于原始需求与完整测试稿形成原始反馈（保留稳定 `GR-xxx` 编号与 `Critical/High/Medium/Low` 等级），并独立评审全部伴生 BDD 场景，填入 `## BDD 场景评审`。
  2. **SOP 健康检查与 14 项检查**：核对输入完整性、来源模式（优先级：`Import-Quarantine > Provenance-Unknown > Strict / Legacy`）和深度（`auto` 风险优先 / `--deep`），复用已有证据完成 **R1–R6**（覆盖度、命名、优先级、字段、可执行性、追溯）与 **H1–H8**（冗余、预期质量、意图一致性、前置充分性、风险边界、可维护性、回归价值、亮点识别）[维度细则](skills/testcase-reviewer/testcase-review/references/review-dimensions.md)，同时在 `### 通用发现处置` 表逐项关联或说明处置依据。
  3. **四项描述门禁**：对完整用例集的 `preconditions`、`test_data`、`steps`、`expected_result` 逐条检查。确认问题按原 R/H 维度分级并计入 `description_issue_ids`；**即使为 S2/S3 或标为 `accepted`，未复审为 `resolved` 前仍阻断 Gate**。
- **标准交付通过条件**（须同时满足）：
  1. 通用评审、伴生 BDD 场景评审、SOP 14 项检查及 GR 逐项处置均已完成；
  2. `review_gate.status = pass`，且 `s1_unresolved_count = 0`、`s1_issue_ids = []`、`description_unresolved_count = 0`、`description_issue_ids = []`、`bdd_review.status = complete`；
  3. `reviewed_artifacts` 中 `testcases_sha256`、`testpoints_sha256` 及 `bdd_features_sha256` 与当前文件一致，且实际 XMind 与当前 JSON 比对通过。

---

## 4. 上下文传播、版本与定向返修

跨阶段元数据通过 Markdown 末尾唯一的 `<!-- testspec-context {...} -->` 块和 JSON 顶层 `_context` 传递，完整规则见 [context-protocol.md](skills/_testspec-shared/references/context-protocol.md)：

- **版本单一更新点**：仅 `prd-analysis` 在业务口径或验收规则确认变化时递增 `source_revision` 并刷新 `canonical_source_sha256`；下游三阶段只原样继承版本。
- **内容漂移检测**：即使 `source_revision` 未变，只要规范需求正文指纹与分析记录不一致，`validate_context_chain.py` 即要求回到 `prd-analysis` 重新核对。
- **stale 收敛规则**：当前阶段完成后，从 `stale_downstream_artifacts` 移除自身产物并指向 `next_skill`；终点 `testcase-reviewer` 清空 `stale_downstream_artifacts` 并省略 `next_skill` 与 `stale_reason`。（注意：脚本规定当 `stale_downstream_artifacts` 为空时，必须省略 `next_skill` 和 `stale_reason`。）
- **按责返修闭环**：
  - 需求口径问题 → `prd-analysis`；TP 缺口或粒度问题 → `test-points`；用例字段或 BDD 问题 → `testcase-generate`。
  - 生成阶段返修仅消费 `open` 且 `owner=generate` 的问题，只修改指定字段/场景，写入 `_context.review_repairs` 并同步更新 XMind 与受影响 BDD，**不自行将 issue 标为 `resolved`**。
  - 若返修涉及用户选中的已 `accepted` 描述问题，先由 `testcase-reviewer` 以原 ID 重开为 `open`（保留原严重度与 owner），待生成阶段修复后再由 `testcase-reviewer` 复审确认 `resolved` 并刷新全部 SHA-256。

---

## 5. 常用本地命令

命令在仓库根目录使用 Python 3 运行，先设置变更目录变量：

```bash
CHANGE_NAME="example"
CHANGE_DIR="testspec/changes/$CHANGE_NAME"
XMIND_PATH="$CHANGE_DIR/artifacts/${CHANGE_NAME}_cases.xmind"
```

### 阶段 1：蓝湖提取与需求分析校验

```bash
# 可选：蓝湖/Axure 链接直连提取（需登录态时读取本机 LANHU_COOKIE 配置）
python3 -B skills/prd-analysis/scripts/direct_extract_axure.py --url "<蓝湖链接>"

# 计算规范需求文件 SHA-256 并校验分析上下文链
CANONICAL="$CHANGE_DIR/requirements.md"
[ -f "$CANONICAL" ] || CANONICAL="$CHANGE_DIR/proposal.md"

python3 -B skills/_testspec-shared/scripts/fingerprint_inputs.py "$CANONICAL"
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through analysis
```

### 阶段 2 & 3：测试点校验、用例自检、XMind 导出与比对

```bash
# 阶段 2 完成后校验上下文链
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through points

# 阶段 3：用例结构、方法、重复候选与覆盖率自检（默认按组摘要写 .testspec-cache/，--full 输出全量明细）
python3 -B skills/_testspec-shared/scripts/validate_testcases.py \
  --input "$CHANGE_DIR/artifacts/testcases.json" \
  --testpoints "$CHANGE_DIR/specs/testpoints.md" \
  --full --pretty

# 导出 XMind 8（会覆盖同名文件）并反向比对 XML 与 JSON
python3 -B skills/testcase-generate/scripts/generate_xmind.py \
  --input "$CHANGE_DIR/artifacts/testcases.json" \
  --output "$XMIND_PATH" --title "测试用例"

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py xmind \
  --json "$CHANGE_DIR/artifacts/testcases.json" --xmind "$XMIND_PATH"

# 校验生成阶段上下文与伴生 BDD 存在性
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through generate
```

### 阶段 4：评审准备、报告校验与交付复核

```bash
# 可选：为通用评审生成去上下文的中性只读 JSON 副本
python3 -B skills/testcase-reviewer/testcase-review/scripts/prepare_reviewer_input.py \
  --testcases "$CHANGE_DIR/artifacts/testcases.json" \
  --requirements "$CANONICAL" \
  --output ".testspec-cache/reviewer/input.json"

# 评审报告保存后：校验上下文/指纹、14 项矩阵及通用反馈结构
python3 -B skills/_testspec-shared/scripts/validate_context_chain.py \
  --change-dir "$CHANGE_DIR" --through review

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py review \
  --report "$CHANGE_DIR/review-report.md"

python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py feedback \
  --report "$CHANGE_DIR/review-report.md"

# 正式交付前对实际交付 XMind 复核一次
python3 -B skills/_testspec-shared/scripts/verify_eval_artifacts.py xmind \
  --json "$CHANGE_DIR/artifacts/testcases.json" --xmind "$XMIND_PATH"
```

> 提示：填写 `review-report.md` 的总览矩阵 `H8 测试价值与亮点` 行时，关键指标单元格须同时包含 `标杆用例数 <N>` 与 `可复用模式数 <N>`（例如 `标杆用例数 0；可复用模式数 0`），以满足 `verify_eval_artifacts.py review` 校验。

---

## 6. 仓库维护与回归测试

修改 Skill 规则、模板或校验脚本后，运行全部单元测试与契约校验：

```bash
python3 -B -m unittest discover -s skills/prd-analysis/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/testcase-generate/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/_testspec-shared/tests -p 'test_*.py'
python3 -B -m unittest discover -s skills/testcase-reviewer/testcase-review/tests -p 'test_*.py'

python3 -B skills/_testspec-shared/scripts/validate_skill_contracts.py
python3 -B skills/_testspec-shared/scripts/validate_evals.py
python3 -B skills/testcase-reviewer/scripts/validate_skill_repo.py skills/testcase-reviewer
```
