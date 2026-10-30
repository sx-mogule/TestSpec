# BDD 输出契约

报告类型选择、统一汇总与保存位置遵循同目录的 `output-contracts.md`。本文件只定义 BDD 各模式的内容格式，不另设产物目录。

当默认 Skill 流程不能提供足够明确的结构时，使用以下回复格式。

## 评审契约

```text
Mode: review
Oracle used: <来源>
Oracle sufficiency: <strong|partial|weak>
Confidence: <high|medium|low>

Findings:
1. <严重度>（Critical|High|Medium|Low）: <问题>
   Evidence: <场景、步骤或需求>
   Why it matters: <影响>
   Fix: <建议修正>

Traceability and coverage:
- <摘要>

Top recommendations:
- <行动>
```

若事实来源较弱或缺失，使用 `Confidence: low`。

若未发现实质性缺陷，将发现列表替换为：

```text
Findings:
- No material defects identified.
  （中文释义：未发现实质性缺陷。）
```

之后列出尚待确认的问题或可选改进项。

## 改写契约

```text
Mode: rewrite
Rewrite strategy:
- <改了什么以及原因>

Rewritten artifact:
<Gherkin 内容>

Open assumptions:
- <缺口、未解决的规则或缺失的元数据>
```

## 生成契约

```text
Mode: generate
Source inputs:
- <材料类型>

Generated artifact:
<Gherkin 内容>

Assumptions and gaps:
- <来源不支持的行为或缺失的决策>
```

## 混合契约

```text
Mode: hybrid
Oracle used: <来源>
Oracle sufficiency: <strong|partial|weak>
Confidence: <high|medium|low>

Key findings:
1. <严重度>（Critical|High|Medium|Low）: <问题>

Rewritten artifact:
<Gherkin 内容>

Open assumptions:
- <事项>
```

## 判定依据不足时的回退格式

当用户要求判断正确性，但材料过于薄弱，无法支持结论时，使用以下格式：

```text
Mode: <review|hybrid>
Oracle used: <来源>
Oracle sufficiency: weak
Confidence: low

Limitations:
- <无法确认的内容>

BDD quality findings:
1. <严重度>（Critical|High|Medium|Low）: <问题>

Blocked decisions:
- <缺失规则或歧义>
```

## 正式报告契约

用户明确要求以下内容时，使用 [BDD 正式评审模板](../templates/bdd-review-report-template.md)：

- 正式评审报告
- 执行摘要
- 评分卡
- 报告形式的辅导建议
