import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "skills/_testspec-shared/scripts/validate_testcases.py"
spec = spec_from_file_location("validate_testcases_new_methods", VALIDATOR)
validator = module_from_spec(spec)
spec.loader.exec_module(validator)

METHODS = ("基于属性的测试", "变形测试", "语法规则分析")
POINTS = (
    ("TP_ORDER_TOTAL_001", "购物车商品数量变化后，总价等于商品小计之和", "REQ-001"),
    ("TP_LIST_SORT_001", "相同记录的录入顺序不改变编号升序结果", "REQ-002"),
    ("TP_SEARCH_SYNTAX_001", "搜索表达式按已确认语法解析或拒绝", "REQ-003"),
)
CASES = (
    (
        "订单", "总价", "数量变化后总价等于小计之和",
        "商品甲单价10元且数量2，商品乙单价5元且数量1", "修改购物车数量并查看结算页",
        "结算页总价为25元，等于20元与5元两个商品小计之和", "TP_ORDER_TOTAL_001",
    ),
    (
        "列表", "排序", "录入顺序变化后排序结果一致", "记录编号3、1、2与2、3、1两种录入顺序",
        "分别录入、保存两次列表结果并选择编号升序", "两次列表的记录编号顺序均为1、2、3",
        "TP_LIST_SORT_001",
    ),
    (
        "搜索", "表达式", "合法括号表达式返回匹配记录",
        "记录A含甲乙、B含丙、C仅含甲；表达式：(甲 AND 乙) OR 丙", "输入表达式并执行搜索",
        "结果列表仅包含记录A与记录B", "TP_SEARCH_SYNTAX_001",
    ),
    (
        "搜索", "表达式", "缺少右括号的表达式被拒绝", "表达式：(甲 AND 乙",
        "输入表达式并执行搜索", "搜索条件未更新，页面明确提示表达式结构不合法",
        "TP_SEARCH_SYNTAX_001",
    ),
)


class TestNewDesignMethods(unittest.TestCase):
    def validate(self, context_methods, *, point_methods=METHODS, point_context_methods=METHODS,
                 export=False, full_chain=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = root / "specs/testpoints.md"
            cases = root / "artifacts/testcases.json"
            points.parent.mkdir()
            cases.parent.mkdir()
            revision = {"version": 1, "summary": "合成业务规则", "updated_by_skill": "prd-analysis"}

            def stage_context(skill, stale, **extra):
                return {"source_skill": skill, "source_revision": revision,
                        "blocking_open_questions": [], "dynamic_followups": [],
                        "material_quality": "high", "stale_downstream_artifacts": stale, **extra}

            def write_markdown(path, body, context):
                path.write_text(body + "\n\n<!-- testspec-context\n" +
                                json.dumps(context, ensure_ascii=False) + "\n-->\n", encoding="utf-8")

            point_body = "\n".join(
                f"- {tp}: {objective}\n  - 验证要点: {objective}\n  - 设计方法: {method}"
                f"\n  - 优先级: p1\n  - Oracle 状态: confirmed\n  - Oracle 范围: direct"
                f"\n  - 回归层级: Full\n  - 关联需求: {requirement}"
                for (tp, objective, requirement), method in zip(POINTS, point_methods)
            )
            write_markdown(
                points, point_body,
                stage_context("test-points", ["artifacts/testcases.json", "review-report.md"],
                              design_methods=point_context_methods, next_skill="testcase-generate"),
            )
            payload = {
                "schema_version": 2,
                "_context": stage_context("testcase-generate", ["review-report.md"],
                                          design_methods=context_methods, next_skill="testcase-review",
                                          origin={"kind": "testspec-native", "source_change": "synthetic-method-chain"},
                                          trust={"status": "provisional", "basis": "prd-first"}),
                "testcases": [
                    {
                        "id": f"CASE-{index:03d}", "module": module, "submodule": submodule,
                        "test_name": f"{module}_{submodule}_{scene}", "preconditions": "已准备可操作的业务数据",
                        "test_data": data, "steps": f"1、{action}",
                        "expected_result": f"1、{oracle}",
                        "priority": "p1", "type": "正向",
                        "tp_refs": [tp],
                        "origin": {"kind": "testspec-native", "source_change": "synthetic-method-chain"},
                        "trust": {"status": "provisional", "basis": "prd-first"},
                    }
                    for index, (module, submodule, scene, data, action, oracle, tp) in enumerate(CASES, 1)
                ],
            }
            cases.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = validator.validate(str(cases), str(points))
            if export:
                output = root / "cases.xmind"
                subprocess.run([sys.executable, str(ROOT / "skills/testcase-generate/scripts/generate_xmind.py"),
                                "--input", str(cases), "--output", str(output)], check=True, capture_output=True)
                with zipfile.ZipFile(output) as package:
                    xml = package.read("content.xml").decode("utf-8")
                self.assertTrue(all(scene in xml for _, _, scene, *_ in CASES))
            if full_chain:
                requirements = ("# 合成需求\n\n"
                    "- REQ-001：无优惠、无运费时，购物车总价等于各商品单价乘数量的小计之和。\n"
                    "- REQ-002：记录列表按编号升序排序，结果与记录录入顺序无关。\n"
                    "- REQ-003：搜索表达式支持括号、AND、OR；合法表达式按条件筛选记录；"
                    "缺少右括号时拒绝搜索、提示结构不合法且保留原搜索条件。")
                write_markdown(root / "requirements.md", requirements, stage_context("prd-analysis", [
                    "requirements-analysis.md", "specs/testpoints.md", "artifacts/testcases.json", "review-report.md"]))
                write_markdown(
                    root / "requirements-analysis.md",
                    "# 合成需求分析\n\n三条已确认业务规则分别适用属性、变形和语法规则分析。",
                    stage_context("prd-analysis", ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"],
                                  next_skill="test-points"),
                )
                write_markdown(
                    root / "review-report.md", "# 合成 Review 门禁上下文\n\n独立语义评审尚未执行。",
                    stage_context("testcase-review", [], design_methods=list(METHODS),
                                  review_gate={"status": "blocked", "s1_unresolved_count": 1,
                                               "s1_issue_ids": ["SYN-REVIEW-PENDING"]}),
                )
                subprocess.run([sys.executable, str(ROOT / "skills/_testspec-shared/scripts/validate_context_chain.py"),
                                "--change-dir", str(root), "--through", "review", "--expected-version", "1"],
                               check=True, capture_output=True)
            return result

    def test_three_methods_reach_case_context(self):
        result = self.validate(list(METHODS), export=True, full_chain=True)
        self.assertFalse(result["errors"], result)
        self.assertEqual(result["coverage"]["covered_tp"], 3)
        self.assertEqual(result["summary"]["total_cases"], 4)

    def test_missing_method_is_blocked(self):
        result = self.validate(list(METHODS[:2]))
        self.assertIn("DESIGN_METHOD_MISMATCH", {issue["type"] for issue in result["errors"]})

    def test_auxiliary_strategy_is_rejected_as_method(self):
        result = self.validate([*METHODS, "探索式测试"])
        self.assertIn("DESIGN_METHOD_MISMATCH", {issue["type"] for issue in result["errors"]})

    def test_missing_method_context_is_blocked(self):
        result = self.validate(None)
        self.assertIn("MISSING_DESIGN_METHODS", {issue["type"] for issue in result["errors"]})

    def test_testpoint_method_context_mismatch_is_blocked(self):
        result = self.validate(list(METHODS), point_context_methods=METHODS[:2])
        self.assertIn("TESTPOINT_METHOD_CONTEXT_MISMATCH", {issue["type"] for issue in result["errors"]})

    def test_unknown_testpoint_method_is_blocked(self):
        result = self.validate(list(METHODS), point_methods=("基于属性的测试", "探索式测试", "语法规则分析"))
        self.assertIn("UNKNOWN_DESIGN_METHOD", {issue["type"] for issue in result["errors"]})

    def test_one_testpoint_without_method_is_blocked(self):
        result = self.validate(list(METHODS), point_methods=("基于属性的测试", "", "语法规则分析"))
        self.assertIn("MISSING_TP_DESIGN_METHOD", {issue["type"] for issue in result["errors"]})


if __name__ == "__main__":
    unittest.main()
