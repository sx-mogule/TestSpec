# TestSpec 上下文传播协议

> 适用于 `prd-analysis → test-points → testcase-generate → testcase-reviewer`。

## 传播介质

Markdown 产物在文件末尾保存：

每份产物只保留一个完整闭合的 `testspec-context` HTML 注释，内部为 JSON 对象。更新时替换原块，不追加第二个块；写入后校验注释边界和 JSON，重复或未闭合时停止下游流程。

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
    "next_skill": "testcase-reviewer"
  },
  "testcases": []
}
```

## 核心字段

| 字段 | 说明 |
|---|---|
| `source_skill` | 生成当前产物的 Skill 新名称 |
| `source_revision` | 当前需求口径的版本、摘要和更新者 |
| `canonical_source_sha256` | 仅在 `requirements-analysis.md` 记录实际分析的 canonical 文件字节指纹，由共享 `fingerprint_inputs.py` 计算 |
| `blocking_open_questions` | 影响验收的未决问题。保留上游 Q 编号及受影响需求，已确认的问题由 `prd-analysis` 更新需求和分析后移出。Review 将尚未解决的 Q 关联到未解决的 J4 并阻断放行 |
| `dynamic_followups` | 执行期继续关注但不阻塞当前流程的问题 |
| `material_quality` | 输入质量：high / medium / low |
| `risks_identified` | 已识别风险 |
| `coverage_estimate` | 覆盖情况摘要 |
| `design_methods` | test-points 记录各 TP 使用的正式方法集合；testcase-generate 记录已生成正式用例所引用 TP 的方法集合，不进入八个业务字段 |
| `stale_downstream_artifacts` | 需要重新生成或复核的下游产物 |
| `stale_reason` | 产物过期原因 |
| `next_skill` | 下一步 Skill 新名称 |
| `iteration_count` | 生成或修正轮次 |
| `iteration_summary` | 修正摘要 |
| `origin` / `trust` | 用例来源与信任状态 |
| `reviewed_artifacts` | Review 记录 `testcases_sha256`、`testpoints_sha256`，以及 `bdd_features_sha256`（全部 `artifacts/*_features.feature` 的相对路径到 SHA-256 映射）；只记录实际评审的版本，不改变 Review Gate 计算 |
| `bdd_review` | BDD 评审完成记录：`status` 为 `complete` 或 `incomplete`；须与报告中单列的 BDD 场景评审状态一致，不以存在文件或写入指纹代替评审 |

## 版本规则

- `prd-analysis` 创建或更新 `source_revision`。确认业务规则或验收口径变化后，在 canonical 中更新版本、变更摘要及待更新产物，再生成与其一致的分析。版本已经更新时直接继承。仅格式或元数据变化时，复核内容后可以保留版本并刷新分析指纹。
- `test-points`、`testcase-generate`、`testcase-reviewer` 必须原样传播版本，不得自行递增。
- canonical source 没有版本时，按 Legacy 模式继续并告警，不得伪造版本。
- 直接上游版本低于 canonical source 时停止，并提示重新运行直接上游 Skill。
- 直接上游版本高于 canonical source 时停止，报告元数据异常。
- `validate_context_chain.py` 核对分析指纹。同版本正文改变时回到 `prd-analysis` 复核。历史分析无指纹时仍可按版本读取，正式评审放行前须核对当前原文，重跑分析并记录指纹。

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
| `testcase-generate` | `artifacts/testcases.json`、`artifacts/<name>_cases.xmind`、`artifacts/<name>_features.feature` | `testcase-reviewer` |
| `testcase-reviewer` | `review-report.md` | 无 |

Review 通过后保留完整集 JSON、XMind 和伴生 BDD，`review-report.md` 记录最终门禁；冒烟分类仍作为完整集内元数据，不派生独立文件。`review_gate` 必须包含 S1 和四项描述问题的计数与 ID 列表，通过条件及旧报告处理见 `output-contracts.md` 的 `review-report.md` 契约。发现问题时按回溯规则返修并重新 Review。

需求或测试点变化影响 BDD 时，将对应 `artifacts/<name>_features.feature` 与其他受影响产物一起列为 stale；生成完成后从 stale 列表移除该 BDD。BDD 内容修改、新增、删除或改名后，旧评审记录失效，须重新评审当前全部 BDD 并更新指纹映射。

`validate_context_chain.py --through generate` 检查 BDD 存在、可读取且非空；`--through review` 还检查 BDD 完成记录和可见评审摘要，并逐一比对实际评审的 JSON、测试点和全部 BDD 指纹。旧报告仍可读取，缺少记录或指纹不一致时须重评，不补造历史完成状态或指纹。合法的 Gate `blocked` 报告在 BDD 评审已完成且指纹一致时仍可通过结构校验；结构通过不代表交付通过，也不证明 Gherkin 语法或评审语义正确。

## 消费规则

- 优先读取 `requirements.md`，不存在时读取 `proposal.md`。
- 每一步必须读取直接上游产物并比较 `source_revision`。
- 同一会话已读且原文仍在上下文、内容哈希也未变时，可按 `execution-efficiency.md` 复用已读内容；每阶段仍核对版本。哈希变化、新材料或上下文缺失时重读，不能只凭版本号复用。
- 风险影响覆盖策略；阻塞问题不能被假设补全。
- 低质量输入需要提高检查深度，但不得虚构需求。
- 来源与信任未知的旧用例只能作为参考，不能成为需求事实或预期结果依据。

## 回溯规则

发现上游内容不足时，明确指出缺失内容和受影响范围，并回到对应上游：

- 需求或验收条件不清楚 → `prd-analysis`
- 测试点缺失或粒度不合适 → `test-points`
- 用例字段、步骤或预期有问题 → `testcase-generate`

## 历史评审标识兼容

唯一评审入口和新产物的source_skill均为 `testcase-reviewer`。历史 `source_skill: testcase-review` 仅在读取旧评审报告时兼容；旧next_skill提示应指向现有统一入口继续处理，不恢复独立Skill。
