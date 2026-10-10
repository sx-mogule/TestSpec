# TestSpec 公共约定

## 当前变更目录定位规则

所有 TestSpec skill 共享以下规则来确定「当前变更目录」：

1. 若用户指定了变更名 → `testspec/changes/<name>/`
2. 若未指定，检查 `testspec/changes/` 下有几个**非 archive** 子目录：
   - 仅 1 个 → 自动使用该目录
   - 多个 → 列出选项，询问用户
   - 0 个 → 由 `prd-analysis` 根据用户提供的需求名称创建变更目录，并写入最小 canonical 需求源

## 流程概览

```
prd-analysis → test-points → testcase-generate → testcase-review
  需求分析       测试点设计       测试用例生成       测试用例 Review
```

需求分析阶段接收 PRD、用户故事或需求片段；如果工作区尚无变更目录，先创建 `testspec/changes/<name>/` 并保存 `requirements.md` 或 `proposal.md` 作为 canonical 需求源。生成阶段直接输出统一用例 JSON 与 XMind，Review 是最终门禁。

## 阶段门禁

默认必须按完整链路执行；只有用户明确要求跳步时才允许降级，并在产物中标记缺失来源或低置信度。

| 阶段 | 进入条件 | 最低出口条件 | 不满足时回退 |
|---|---|---|---|
| `prd-analysis` | 有 PRD、蓝湖事实或用户需求 | canonical `requirements.md` 与 `requirements-analysis.md` 可追溯，风险/边界/待确认项已分开 | 补充需求来源 |
| `test-points` | analysis 与 canonical revision 一致 | 每个 TP 有 ID、验证目标、优先级、Oracle 状态和需求引用 | 回到 `prd-analysis` |
| `testcase-generate` | testpoints 与 canonical revision 一致 | JSON 8 字段完整，TP 引用有效，XMind/Excel 通过格式校验 | 回到 `test-points` 或本阶段修复 |
| `testcase-review` | 用例和测试点版本一致 | 14 项检查完成，`review_gate` 明确，未解决 S1 为 0 才能通过 | 回到 `testcase-generate` |

## 智能编排指引

### 步骤跳转决策

默认按完整四阶段链路执行，不得仅因已有材料充足而自动跳过阶段。只有用户明确要求跳步时才允许跳步，并在产物中标记缺失来源或低置信度。

### 回溯建议

当下游 skill 发现上游产物质量不足时，不要默默降级。应提供选项让用户决定：

- 回到上游补充（推荐，质量最高）
- 在当前步骤尽力弥补，标注风险
- 继续执行，在 review 阶段集中处理

### 上下文传播

所有 TestSpec skill 遵循 `context-protocol.md` 进行跨 skill 上下文传播。上游 skill 在产物中播种元数据，下游 skill 在执行前读取并纳入推理。

### 推理式决策

所有 TestSpec skill 使用 `thinking-protocol.md` 进行策略决策，使用 `reflection-protocol.md` 进行产物质量反思。详见各协议文件。

## 命名契约

test-points 和 testcase-generate 共享命名规则，详见 `naming-contract.md`。

## 目录结构

### 变更工作区（临时，按需求/版本）

```
testspec/changes/<name>/
├── proposal.md                # 测试提案（可选）
├── requirements.md            # 可验收需求源（由需求分析阶段建立）
├── requirements-analysis.md   # 需求分析（prd-analysis）
├── review-report.md           # 评审报告（testcase-review）
├── specs/
│   └── testpoints.md          # 测试点（test-points）
└── artifacts/
    ├── source-prd.md          # 需求源归档（可选）
    ├── api-doc.md             # 接口口径归档（可选）
    ├── update-log.md          # 口径更新记录（可选）
    ├── testcases.json         # 统一功能用例 JSON（testcase-generate）
    ├── <name>_cases.xlsx      # 测试用例 Excel（按需）
    └── <name>_cases.xmind     # 统一 XMind 8（testcase-generate）
```
