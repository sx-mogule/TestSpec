import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_testcases.py"
SPEC = spec_from_file_location("quality_validator", SCRIPT)
validator = module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def make_case(case_id="CASE-001", **changes):
    case = {
        "id": case_id, "module": "公告", "submodule": "标题",
        "test_name": "公告_标题_保存后保留新标题",
        "preconditions": "已打开公告编辑页，有编辑权限。",
        "test_data": "标题：ABC", "steps": "1、点击保存",
        "expected_result": "1、标题已保存", "priority": "p1",
        "type": "正向", "tp_refs": ["TP_NOTE_TITLE_001"],
    }
    case.update(changes)
    return case


class TestCaseQuality(unittest.TestCase):
    def validate_cases(self, cases):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "testcases.json"
            path.write_text(json.dumps({"schema_version": 2, "testcases": cases}, ensure_ascii=False))
            return validator.validate(str(path))

    def run_cli(self, cases):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "testcases.json"
            path.write_text(json.dumps({"schema_version": 2, "testcases": cases}, ensure_ascii=False))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--input", str(path)],
                capture_output=True, text=True, timeout=20, env=env,
            )
            return result.returncode, json.loads(result.stdout)

    def boundary_cases(self):
        lower = make_case(
            test_name="公告_标题_最短标题允许保存", test_data="标题：A；长度：1个字符。",
            type="边界", expected_result="1、重新打开编辑页后，标题为输入值。",
        )
        upper = dict(
            lower, id="CASE-002", test_name="公告_标题_最长标题允许保存",
            test_data="标题：ABCDEFGHIJ；长度：10个字符。",
        )
        return [lower, upper]

    def test_clear_short_step_and_result_pass(self):
        result = self.validate_cases([make_case()])
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["warnings"], [])

    def test_clear_short_step_returns_zero(self):
        code, result = self.run_cli([make_case()])
        self.assertEqual(code, 0, result)

    def test_concrete_display_and_prompt_are_not_vague_by_word_or_length(self):
        for expected in ("1、显示3条订单", "1、提示「请输入标题」", "1、订单状态为已取消"):
            with self.subTest(expected=expected):
                result = self.validate_cases([make_case(expected_result=expected)])
                self.assertEqual(result["status"], "PASS", result)

    def test_vague_step_is_still_reported(self):
        result = self.validate_cases([make_case(steps="1、进行操作")])
        self.assertEqual(result["status"], "WARN")
        self.assertIn("NO_ACTION_VERB", {item["type"] for item in result["warnings"]})

    def test_scroll_step_is_recognized_by_the_action_hint(self):
        result = self.validate_cases([make_case(steps="1、向下滚动进入夏日模块")])
        self.assertEqual(result["status"], "PASS", result)
        self.assertNotIn("NO_ACTION_VERB", {item["type"] for item in result["warnings"]})

    def test_generic_related_action_still_receives_the_action_hint(self):
        result = self.validate_cases([make_case(steps="1、进行相关操作")])
        self.assertEqual(result["status"], "WARN", result)
        self.assertIn("NO_ACTION_VERB", {item["type"] for item in result["warnings"]})

    def test_vague_step_beside_clear_step_is_reported(self):
        result = self.validate_cases([make_case(steps="1、打开编辑页\n2、进行相关操作")])
        self.assertIn("VAGUE_STEP", {item["type"] for item in result["warnings"]})

    def test_action_without_object_is_reported(self):
        result = self.validate_cases([make_case(steps="1、点击")])
        self.assertIn("VAGUE_STEP", {item["type"] for item in result["warnings"]})

    def test_vague_result_is_reported_without_length_limit(self):
        for expected in ("1、操作成功", "1、页面正常显示", "1、符合预期", "1、系统页面功能操作结果执行处理保存提交正常"):
            with self.subTest(expected=expected):
                result = self.validate_cases([make_case(expected_result=expected)])
                self.assertIn("VAGUE_EXPECTED", {item["type"] for item in result["warnings"]})

    def test_vague_result_beside_specific_result_is_reported(self):
        result = self.validate_cases([make_case(expected_result="1、标题已保存\n2、操作成功")])
        self.assertIn("VAGUE_EXPECTED", {item["type"] for item in result["warnings"]})

    def test_six_steps_can_have_one_key_result(self):
        steps = "1、打开公告列表\n2、选择公告\n3、点击编辑\n4、输入标题\n5、点击保存\n6、打开公告详情"
        result = self.validate_cases([make_case(steps=steps, expected_result="1、公告详情显示新标题ABC")])
        self.assertEqual(result["status"], "PASS", result)

    def test_missing_steps_or_result_remains_an_error(self):
        for field in ("steps", "expected_result"):
            with self.subTest(field=field):
                result = self.validate_cases([make_case(**{field: ""})])
                self.assertEqual(result["status"], "FAIL", result)
                self.assertIn("MISSING_FIELD", {item["type"] for item in result["errors"]})

    def test_boundary_pair_is_a_review_candidate_not_a_warning(self):
        result = self.validate_cases(self.boundary_cases())
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["summary"]["review_candidate_count"], 1)
        candidate = result["review_candidates"][0]
        self.assertEqual(candidate["type"], "SIMILAR_CASES")
        self.assertEqual(candidate["different_fields"], ["test_data"])

    def test_review_candidate_does_not_change_cli_exit(self):
        code, result = self.run_cli(self.boundary_cases())
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result["review_candidates"]), 1)

    def test_same_content_with_different_title_is_reported(self):
        first = make_case()
        second = dict(first, id="CASE-002", test_name="公告_标题_另一个名称", priority="p2")
        result = self.validate_cases([first, second])
        self.assertEqual(result["status"], "WARN", result)
        self.assertEqual(result["warnings"][0]["type"], "DUPLICATE")
        self.assertEqual(result["review_candidates"], [])

    def test_same_content_still_returns_nonzero(self):
        first = make_case()
        code, result = self.run_cli([first, dict(first, id="CASE-002")])
        self.assertEqual(code, 1, result)

    def test_different_tp_refs_do_not_hide_same_content(self):
        first = make_case()
        second = dict(first, id="CASE-002", tp_refs=["TP_NOTE_TITLE_002"])
        result = self.validate_cases([first, second])
        self.assertIn("DUPLICATE", {item["type"] for item in result["warnings"]})

    def test_list_number_format_does_not_hide_same_content(self):
        first = make_case()
        second = dict(first, id="CASE-002", steps=" 1. 点击保存 ", expected_result=" 1. 标题已保存 ")
        result = self.validate_cases([first, second])
        self.assertIn("DUPLICATE", {item["type"] for item in result["warnings"]})

    def test_business_differences_are_not_automatically_merged(self):
        first = make_case()
        differences = [
            {"preconditions": "已打开公告编辑页，无编辑权限。"},
            {"preconditions": "已打开已停用公告的编辑页。"},
            {"test_data": "标题：空字符串"},
            {"expected_result": "1、标题仍为OLD"},
        ]
        for changes in differences:
            with self.subTest(changes=changes):
                second = dict(first, id="CASE-002", **changes)
                result = self.validate_cases([first, second])
                self.assertNotIn("DUPLICATE", {item["type"] for item in result["warnings"]})
                self.assertEqual(len(result["review_candidates"]), 1)

    def test_numbers_units_and_empty_values_are_preserved(self):
        for left, right in (("值：1", "值：10"), ("金额：1.5元", "金额：15元"),
                            ("容量：1MB", "容量：1GB"), ("值：空字符串", "值：0"),
                            ("1.5元", "15元"), ("1、A", "2、A")):
            with self.subTest(left=left, right=right):
                cases = [make_case(test_data=left), make_case("CASE-002", test_data=right)]
                result = self.validate_cases(cases)
                self.assertNotIn("DUPLICATE", {item["type"] for item in result["warnings"]})

    def test_decimal_values_in_expected_result_are_preserved(self):
        cases = [make_case(expected_result="1.5元"), make_case("CASE-002", expected_result="15元")]
        result = self.validate_cases(cases)
        self.assertNotIn("DUPLICATE", {item["type"] for item in result["warnings"]})

    def test_optional_null_fields_do_not_break_validation(self):
        result = self.validate_cases([make_case(preconditions=None, test_data=None)])
        self.assertEqual(result["status"], "PASS", result)

    def test_numeric_zero_data_is_not_treated_as_empty(self):
        result = self.validate_cases([make_case(test_data=0), make_case("CASE-002", test_data="")])
        self.assertNotIn("DUPLICATE", {item["type"] for item in result["warnings"]})

    def test_data_only_difference_does_not_prove_necessary_coverage(self):
        first = make_case(test_data="标题：ABC")
        second = dict(first, id="CASE-002", test_data="标题：DEF")
        result = self.validate_cases([first, second])
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["review_candidates"][0]["different_fields"], ["test_data"])

    def test_different_modules_are_not_flagged_as_same_case(self):
        first = make_case()
        second = dict(first, id="CASE-002", module="通知", test_name="通知_标题_保存后保留新标题")
        result = self.validate_cases([first, second])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["review_candidates"], [])

    def test_other_warning_still_returns_nonzero(self):
        code, result = self.run_cli([make_case(steps="1、进行操作")])
        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "WARN")

    def test_validation_does_not_edit_input_cases(self):
        cases = self.boundary_cases()
        original = copy.deepcopy(cases)
        self.validate_cases(cases)
        self.assertEqual(cases, original)


if __name__ == "__main__":
    unittest.main()
