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
    def validate(self, point_text, refs, *, case_type="正向", priority="p0"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = root / "testpoints.md"
            cases = root / "testcases.json"
            points.write_text(point_text, encoding="utf-8")
            cases.write_text(json.dumps({"schema_version": 2, "testcases": [{
                "id": "CASE-001", "module": "订单", "submodule": "提交",
                "test_name": "订单_提交_成功后显示订单号", "preconditions": "已登录",
                "test_data": "商品一件", "steps": "1、选择商品并提交订单",
                "expected_result": "1、订单详情显示新订单号和待支付状态",
                "priority": priority, "type": case_type, "tp_refs": refs,
            }]} , ensure_ascii=False), encoding="utf-8")
            return validator.validate(str(cases), str(points))

    def test_confirmed_functional_point_passes(self):
        result = self.validate("##### 功能验证点 (Functional)\n- TP_ORDER_SUBMIT_001: 提交后显示订单号", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "PASS", result)

    def test_non_functional_point_is_blocked(self):
        result = self.validate("##### 非功能性验证点 (Non-Functional)\n- TP_ORDER_SUBMIT_001: 性能", ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("NON_FUNCTIONAL_TESTPOINT", {issue["type"] for issue in result["errors"]})

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
