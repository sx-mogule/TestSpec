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

    def test_non_functional_point_is_blocked(self):
        result = self.validate("##### 非功能性验证点 (Non-Functional)\n- TP_ORDER_SUBMIT_001: 性能", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("NON_FUNCTIONAL_TESTPOINT", {issue["type"] for issue in result["errors"]})

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
