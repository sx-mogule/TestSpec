# TestSpec 上下文传播协议

> 适用于 `prd-analysis → test-points → testcase-generate → testcase-review`。

## 传播介质

Markdown 产物在文件末尾保存：

```markdown
<!-- testspec-context
{
  "source_skill": "prd-analysis",
  "source_revision": {
    "version": 1,
    "summary": "初始需求",
    "updated_by_skill": "prd-analysis"
  },
  "blocking_open_questions": [],
  "dynamic_followups": [],
  "material_quality": "high",
  "stale_downstream_artifacts": ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"],
  "stale_reason": "需求分析已更新",
  "next_skill": "test-points"
}
-->
```

`testcases.json` 在顶层使用 `_context`：

```json
{
  "schema_version": 2,
  "_context": {
    "source_skill": "testcase-generate",
    "source_revision": {
      "version": 1,
      "summary": "初始需求",
      "updated_by_skill": "prd-analysis"
    },
    "blocking_open_questions": [],
    "dynamic_followups": [],
    "material_quality": "high",
    "stale_downstream_artifacts": ["review-report.md"],
    "next_skill": "testcase-review"
  },
  "testcases": []
}
```

## 核心字段

| 字段 | 说明 |
|---|---|
| `source_skill` | 生成当前产物的 Skill 新名称 |
| `source_revision` | 当前需求口径的版本、摘要和更新者 |
| `blocking_open_questions` | 未确认就无法继续或无法判断预期的问题 |
| `dynamic_followups` | 执行期继续关注但不阻塞当前流程的问题 |
| `material_quality` | 输入质量：high / medium / low |
| `risks_identified` | 已识别风险 |
| `coverage_estimate` | 覆盖情况摘要 |
| `stale_downstream_artifacts` | 需要重新生成或复核的下游产物 |
| `stale_reason` | 产物过期原因 |
| `next_skill` | 下一步 Skill 新名称 |
| `iteration_count` | 生成或修正轮次 |
| `iteration_summary` | 修正摘要 |
| `origin` / `trust` | 用例来源与信任状态 |

## 版本规则

- `prd-analysis` 创建或更新 `source_revision`。
- `test-points`、`testcase-generate`、`testcase-review` 必须原样传播版本，不得自行递增。
- canonical source 没有版本时，按 Legacy 模式继续并告警，不得伪造版本。
- 直接上游版本低于 canonical source 时停止，并提示重新运行直接上游 Skill。
- 直接上游版本高于 canonical source 时停止，报告元数据异常。

## stale 收敛

当前阶段成功后：

1. 从 `stale_downstream_artifacts` 移除当前阶段产物。
2. 保留尚未重新生成的后续产物。
3. 将 `next_skill` 指向下一步；Review 是终点，通过后清空 stale 列表并省略 `next_skill`。

阶段对应关系：

| Skill | 产物 | 下一步 |
|---|---|---|
| `prd-analysis` | `requirements.md`、`requirements-analysis.md` | `test-points` |
| `test-points` | `specs/testpoints.md` | `testcase-generate` |
| `testcase-generate` | `artifacts/testcases.json`、XMind/Excel | `testcase-review` |
| `testcase-review` | `review-report.md` | 无 |

Review 通过后保留 `testcase-generate` 输出的统一 JSON 和 XMind，`review-report.md` 记录最终门禁；发现问题时按回溯规则返修并重新 Review。

## 消费规则

- 优先读取 `requirements.md`，不存在时读取 `proposal.md`。
- 每一步必须读取直接上游产物并比较 `source_revision`。
- 风险影响覆盖策略；阻塞问题不能被假设补全。
- 低质量输入需要提高检查深度，但不得虚构需求。
- 来源与信任未知的旧用例只能作为参考，不能成为需求事实或预期结果依据。

## 回溯规则

发现上游内容不足时，明确指出缺失内容和受影响范围，并回到对应上游：

- 需求或验收条件不清楚 → `prd-analysis`
- 测试点缺失或粒度不合适 → `test-points`
- 用例字段、步骤或预期有问题 → `testcase-generate`
