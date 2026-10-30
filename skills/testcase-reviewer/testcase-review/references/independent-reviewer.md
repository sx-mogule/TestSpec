# 通用评审与SOP检查的统一执行

唯一入口是 `../../SKILL.md`。本目录是原 `testcase-review` 的内部模块，没有第二个Skill入口，也没有仅运行其中一部分的开关。

## 同一轮的两部分

1. 按入口保留的通用用例/套件/BDD规则，先基于原始需求与完整测试稿形成发现，使用 `Critical/High/Medium/Low`，保持来源强弱、可信度与假设边界。
2. 读取 `../review-workflow.md`，执行健康检查和R1-R6、H1-H8。完整TestSpec输入继续沿用来源隔离、版本、设计方法、四项描述门禁、S1分级、owner及同ID返修机制。
3. 汇总同一份报告，保留两部分执行状态与逐项处置。不得再次调用根SKILL造成递归；同一模型连续执行不能称为独立评审者或多模型复核。

通用评审不以已有TP、Gate或旧评审结论替代需求事实；SOP检查也不能用通用报告绕过必需输入。原始PRD未提供时明确canonical来源限制，不能声称完成原文追溯。

## 输入不完整

缺少需求时仍能评审结构和可执行性，降低结论可信度；缺少TP、来源或版本时，列出不能完成的R/H项，完成有依据的质量检查。两部分都需报告，SOP状态为未完成，Gate为未计算，不补造TestSpec产物或pass。原有来源未知或隔离导入判定仍在输入齐全后按原规则阻断。

如果通用评审没有完成或发现未逐项处置，即使原生Gate能按原公式计算为pass，也不能宣称整轮评审完成。历史报告保持可读，不补造两部分执行记录。

## 发现的处置

| 通用发现 | SOP复核 |
|---|---|
| 需求、边界、状态或错误路径缺口 | 对照原文与TP在R1/H3/H5核实，按原有定义评S1/S2/S3 |
| Oracle、前置条件、步骤或数据问题 | 在R4/R5/H2/H4核实，确认的四项描述问题进入原描述门禁 |
| 冗余、维护或回归价值 | 在H1/H6/H7核实，保留必要边界，不自动合并或删减 |
| 通用命名、路径标签或优先级建议 | 与当前项目契约核对；不适用时说明理由，不强行改写项目规范 |
| 结论冲突或证据不足 | 保留双方证据，记录无法确认项并按原澄清规则处理 |

每项记“采纳 / 重复关联 / 不适用 / 待确认”，采纳/重复项关联原生issue ID、维度和级别。同一实体问题只登记一次，不机械换算等级或改变Gate公式。TestSpec的正式输出类型保持原范围；通用API/BDD评审能力不将API、安全、性能等类型自动加入SOP输出。

## 可选阅读副本

`../scripts/prepare_reviewer_input.py` 仅准备通用评审用的中性JSON副本，保留ID和8业务字段，不改源用例、不调用模型。完整JSON仍是SOP检查对象。

从SOP根目录执行，替换为实际路径并使用新的输出文件：

```bash
python3 -B skills/testcase-reviewer/testcase-review/scripts/prepare_reviewer_input.py --testcases "testspec/changes/<name>/artifacts/testcases.json" --requirements "testspec/changes/<name>/requirements.md" --output ".testspec-cache/reviewer/<run>/input.json"
```

`--requirements` 可重复且仅支持UTF-8文本。记录实际原始材料、JSON与TP的指纹；输入改变后重新评审，不复用旧结论。

## 维护

共享来源清单位于 `../../../_testspec-shared/references/testcase-reviewer-source.json`，在整个统一目录外，避免自包含哈希。它同时固定通用资源和嵌套SOP模块；旧顶层 `skills/testcase-review` 已移除。

回归：`python3 -B -m unittest discover -s skills/testcase-reviewer/testcase-review/tests -v`。打包校验与结构检查不能代替模型语义和产品行为验证。
