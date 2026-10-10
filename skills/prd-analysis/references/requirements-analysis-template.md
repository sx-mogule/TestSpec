# requirements-analysis.md 模板

```markdown
# 需求分析：<被测对象>

## 需求来源
- PRD：<文档名或链接>
- 设计稿：<链接>
- 来源策略：prd-first；代码证据：<none/reference/verification-baseline/change-evidence>

## 蓝湖素材阅读核对（仅蓝湖来源时填写）
- 素材清单：<manifest.json 的本地路径；仅作阅读证据，不作为需求事实>
- 文档版本与页面清单来源：<版本、Axure JSON/站点图位置>
- 页面：发现 <N> 页；已逐页读取 <N> 页；未读 <页面及原因>
- 文字：已读取 <页面文字/图片文字来源>；无法辨认 <页面、位置及原因>
- 图片：发现 <N> 张；已下载 <N> 张；已逐张视觉阅读 <N> 张；未读 <页面、图片及原因>
- 交互状态：已查看 <状态及页面>；未覆盖 <状态及原因>
- 完整性结论：<已核对完成/未完成，缺口影响范围>

## HTML 按钮交互核对（仅可交互 HTML 来源时填写）
- 来源文件及页面/版本：<文件、页面和版本>
- 按钮：发现 <N> 项；已逐项点击 <N> 项；禁用/不可达/未执行 <N> 项
- 对照表：<BTN_ID、页面与状态、按钮名称/定位、点击动作、实际可观察结果、需求依据或待澄清项、覆盖状态>
- 未覆盖清单：<BTN_ID、原因和受影响功能>
- 完整性结论：<已核对完成/未完成；未完成的范围不作为已验证交互>

## 分析摘要
- 分析模式：<本次采用的模式>
- 总结：<一句话总结>

## 假设扫描
- 待验证：<模块/功能名> — <可能遗漏的方向> — 状态：unverified/confirmed/rejected
- 证据：<REQ/API/设计稿/testlib 位置；unverified 时写“暂无”>
- 整体信心：<X/10>

## 主要问题

### 高优先级问题
- [类别] <问题描述>
  - 位置：<REQ/API/设计稿/testlib 位置>
  - 影响：<为什么影响测试或验收>
  - 建议：<整改或澄清动作>

### 中低优先级问题
- <问题>

## 已明确内容
- <当前材料定义清楚的内容>

## 建议补充
- <建议补充的信息>

## 已有测试覆盖

> 仅在 testlib 实际命中时输出。

| 模块 | 功能点 | 已有用例数 | 覆盖优先级 | 状态 |
|------|--------|------------|------------|------|
| <模块> | <功能> | N | p0×a, p1×b | active |

## 功能模块拆解

### 模块 N：<模块名>

**功能描述**：<一句话说明>

**输入/输出**：
- 输入：<触发条件、用户操作、数据>
- 输出：<预期系统响应、UI 变化>

**等价类分析**：
| 条件 | 有效等价类 | 无效等价类 |
|------|-----------|-----------|
| <条件> | <有效值范围> | <无效值范围> |

**边界值**：
- <边界 1>：<临界值及预期行为>

**状态迁移**（若涉及状态切换）：
- <状态A> → <触发条件> → <状态B>

**业务规则**：
- <规则 1>
- <规则 2>

**风险点**：
- <风险及证据位置>

**推荐设计技术**：
- <技术>：<推荐理由>

## 阻塞澄清项
- [ ] <问题 1>
- [ ] <问题 2>

## 执行期动态跟进
- [ ] <测试执行中持续补充、不阻塞当前分析的问题>

<!-- testspec-context
{
  "source_skill": "prd-analysis",
  "canonical_source_policy": "prd-first",
  "evidence_sources": [],
  "questions": [],
  "source_revision": {"version": "<canonical 版本>", "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "blocking_open_questions": [],
  "dynamic_followups": [],
  "material_quality": "<从上游继承或复核>",
  "stale_downstream_artifacts": [],
  "risks_identified": ["<仅含有证据的风险>"],
  "intuition_flags": [{"signal": "<假设>", "status": "unverified/confirmed/rejected", "evidence": "<证据或空>"}],
  "strategy_used": "<分析模式组合>",
  "testlib_coverage": {
    "scanned": false,
    "related_modules": [],
    "existing_case_count": 0,
    "reusable_features": [],
    "regression_risk_features": [],
    "trust_filter": "exclude legacy-import+unverified from facts/oracles"
  }
}
-->
```
