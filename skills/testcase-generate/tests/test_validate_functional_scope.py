import json
import tempfile
import unittest
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location


VALIDATOR = Path(__file__).resolve().parents[2] / "_testspec-shared" / "scripts" / "validate_testcases.py"
spec = spec_from_file_location("validate_testcases", VALIDATOR)
validator = module_from_spec(spec)
spec.loader.exec_module(validator)


class TestFunctionalScope(unittest.TestCase):
    def validate(self, point_text, refs, *, case_type="正向", priority="p0", include_testpoints=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = root / "testpoints.md"
            cases = root / "testcases.json"
            if include_testpoints:
                points.write_text(point_text, encoding="utf-8")
            cases.write_text(json.dumps({"schema_version": 2, "testcases": [{
                "id": "CASE-001", "module": "订单", "submodule": "提交",
                "test_name": "订单_提交_成功后显示订单号", "preconditions": "已登录",
                "test_data": "商品一件", "steps": "1、选择商品并提交订单",
                "expected_result": "1、订单详情显示新订单号和待支付状态",
                "priority": priority, "type": case_type, "tp_refs": refs,
            }]} , ensure_ascii=False), encoding="utf-8")
            return validator.validate(str(cases), str(points) if include_testpoints else None)

    def test_confirmed_functional_point_passes(self):
        result = self.validate("##### 功能验证点 (Functional)\n- TP_ORDER_SUBMIT_001: 提交后显示订单号", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "PASS", result)

    def test_prose_labels_and_references_do_not_reduce_coverage(self):
        result = self.validate(
            "说明中的 TP_ID 与 TP_OTHER_PROSE_999 不是测试点定义。\n"
            "| 需求 | TP_ID |\n| REQ-001 | TP_ORDER_SUBMIT_001 |\n"
            "- TP_ID: 模板字段说明\n- TP_<MODULE>_<FEATURE>_001: 模板占位\n"
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号",
            ["TP_ORDER_SUBMIT_001"],
        )
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["coverage"]["total_tp"], 1)
        self.assertEqual(result["coverage"]["coverage_rate"], 1)

    def test_reference_in_prose_cannot_create_a_valid_testpoint(self):
        result = self.validate(
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号\n"
            "待确认的引用 TP_ORDER_SUBMIT_002 尚未定义。",
            ["TP_ORDER_SUBMIT_001", "TP_ORDER_SUBMIT_002"],
        )
        self.assertIn("INVALID_TP_REFS", {issue["type"] for issue in result["errors"]})

    def test_uncovered_star_bullet_with_chinese_colon_is_counted(self):
        result = self.validate(
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号\n"
            "* TP_ORDER_SUBMIT_002：拒绝非法提交",
            ["TP_ORDER_SUBMIT_001"],
        )
        self.assertEqual(result["coverage"]["total_tp"], 2)
        self.assertIn("TP_COVERAGE_BELOW_THRESHOLD", {issue["type"] for issue in result["errors"]})

    def test_non_functional_point_is_blocked(self):
        result = self.validate("##### 非功能性验证点 (Non-Functional)\n- TP_ORDER_SUBMIT_001: 性能", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("NON_FUNCTIONAL_TESTPOINT", {issue["type"] for issue in result["errors"]})

    def test_negated_scope_note_and_ordinary_text_do_not_block(self):
        result = self.validate(
            "##### 功能验证点 (Functional)\n"
            "本次不生成非功能性验证点。\n"
            "#### 范围说明：非功能性验证点不在本次范围\n"
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号",
            ["TP_ORDER_SUBMIT_001"],
        )
        self.assertEqual(result["status"], "PASS", result)
        self.assertNotIn("NON_FUNCTIONAL_TESTPOINT", {issue["type"] for issue in result["errors"]})

    def test_non_functional_parent_also_blocks_nested_tracking_point(self):
        result = self.validate(
            "##### 非功能性验证点 (Non-Functional)\n"
            "###### 埋点验证点 (Tracking)\n- TP_TRACK_EVENT_400: 结算页曝光事件上报",
            ["TP_TRACK_EVENT_400"], case_type="埋点",
        )
        issue = next(issue for issue in result["errors"] if issue["type"] == "NON_FUNCTIONAL_TESTPOINT")
        self.assertEqual(issue["tp_ids"], ["TP_TRACK_EVENT_400"])

    def test_returning_to_top_level_functional_section_clears_non_functional_scope(self):
        text = (
            "##### 非功能性验证点 (Non-Functional)\n"
            "- TP_ORDER_PERF_200: 性能检查\n"
            "##### 功能验证点 (Functional)\n"
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号\n"
            "##### 埋点验证点 (Tracking)\n"
            "- TP_TRACK_EVENT_400: 结算页曝光事件上报"
        )
        categories, non_functional_ids = validator._extract_tp_section_metadata(text)
        self.assertEqual(non_functional_ids, {"TP_ORDER_PERF_200"})
        self.assertNotIn("TP_ORDER_SUBMIT_001", non_functional_ids)
        self.assertEqual(categories["TP_TRACK_EVENT_400"], {"埋点"})

    def test_non_functional_heading_and_tp_inside_fenced_example_are_ignored(self):
        text = (
            "##### 功能验证点 (Functional)\n"
            "- TP_ORDER_SUBMIT_001: 提交后显示订单号\n"
            "~~~markdown\n"
            "##### 非功能性验证点 (Non-Functional)\n"
            "- TP_ORDER_PERF_200: 性能检查\n"
            "~~~\n"
        )
        result = self.validate(text, ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["coverage"]["total_tp"], 1)

    def test_fenced_tp_is_not_counted_as_a_formal_testpoint(self):
        result = self.validate(
            "##### 功能验证点 (Functional)\n"
            "~~~markdown\n"
            "- TP_ORDER_SUBMIT_001: 示例用例\n"
            "~~~",
            ["TP_ORDER_SUBMIT_001"],
        )
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("未定义 TP_ID", result["message"])

    def test_tracking_case_passes_with_tracking_point(self):
        result = self.validate(
            "##### 埋点验证点 (Tracking)\n- TP_TRACK_EVENT_400: 结算页曝光事件上报",
            ["TP_TRACK_EVENT_400"], case_type="埋点",
        )
        self.assertEqual(result["status"], "PASS", result)

    def test_compatibility_matrix_case_passes_with_compatibility_point(self):
        result = self.validate(
            "##### 兼容性矩阵验证点 (Compatibility)\n- TP_COMP_CLIENT_500: 已声明客户端组合的页面展示",
            ["TP_COMP_CLIENT_500"], case_type="兼容性矩阵",
        )
        self.assertEqual(result["status"], "PASS", result)

    def test_other_type_cannot_bypass_tracking_scope(self):
        result = self.validate(
            "##### 埋点验证点 (Tracking)\n- TP_TRACK_EVENT_400: 结算页曝光事件上报",
            ["TP_TRACK_EVENT_400"], case_type="其他",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("CASE_TYPE_TP_CATEGORY_MISMATCH", {issue["type"] for issue in result["errors"]})

    def test_special_case_type_cannot_reference_functional_point(self):
        result = self.validate(
            "##### 功能验证点 (Functional)\n- TP_ORDER_SUBMIT_001: 提交后显示订单号",
            ["TP_ORDER_SUBMIT_001"], case_type="埋点",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("CASE_TYPE_TP_CATEGORY_MISMATCH", {issue["type"] for issue in result["errors"]})

    def test_general_non_functional_heading_remains_blocked(self):
        result = self.validate(
            "##### 非功能性验证点 (Non-Functional)\n"
            "###### 埋点验证点 (Tracking)\n- TP_TRACK_EVENT_400: 结算页曝光事件上报",
            ["TP_TRACK_EVENT_400"], case_type="埋点",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("NON_FUNCTIONAL_TESTPOINT", {issue["type"] for issue in result["errors"]})

    def test_unlisted_scope_type_is_still_rejected(self):
        result = self.validate(
            "##### 功能验证点 (Functional)\n- TP_ORDER_SUBMIT_001: 提交后显示订单号",
            ["TP_ORDER_SUBMIT_001"], case_type="API",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("INVALID_TYPE", {issue["type"] for issue in result["errors"]})

    def test_special_case_type_requires_testpoints_file(self):
        result = self.validate("", ["TP_TRACK_EVENT_400"], case_type="埋点", include_testpoints=False)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("SPECIAL_CASE_TYPE_REQUIRES_TESTPOINTS", {issue["type"] for issue in result["errors"]})

    def test_functional_coverage_below_95_percent_is_blocked(self):
        result = self.validate("- TP_ORDER_SUBMIT_001: 成功\n- TP_ORDER_SUBMIT_002: 拒绝", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("TP_COVERAGE_BELOW_THRESHOLD", {issue["type"] for issue in result["errors"]})

    def test_missing_traceability_and_non_p0_smoke_are_blocked(self):
        result = self.validate("- TP_ORDER_SUBMIT_001: 成功", [], case_type="冒烟", priority="p1")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue({"INVALID_TP_REFS", "SMOKE_NOT_P0"}.issubset({issue["type"] for issue in result["errors"]}))


if __name__ == "__main__":
    unittest.main()
