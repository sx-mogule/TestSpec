import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_xmind.py"
NS = "{urn:xmind:xmap:xmlns:content:2.0}"


def children(topic):
    container = topic.find(f"{NS}children/{NS}topics")
    return list(container) if container is not None else []


def title(topic):
    return topic.findtext(f"{NS}title")


class TestScreenshotStructure(unittest.TestCase):
    def generate(self, case):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        source = root / "testcases.json"
        output = root / "cases.xmind"
        source.write_text(json.dumps({"schema_version": 2, "testcases": [case]}, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
        return result, output

    def case(self, **overrides):
        case = {
            "id": "INTERNAL-001", "module": "订单", "submodule": "提交",
            "test_name": "订单_提交_显示待支付状态", "priority": "p1",
            "preconditions": "用户已登录", "test_data": "一件普通商品",
            "steps": "1、选择商品\n2、提交订单",
            "expected_result": "1、商品进入订单\n2、订单显示待支付状态",
        }
        case.update(overrides)
        return case

    def read_case(self, output):
        with zipfile.ZipFile(output) as archive:
            document = ET.fromstring(archive.read("content.xml"))
        root = document.find(f"{NS}sheet/{NS}topic")
        module = children(root)[0]
        submodule = children(module)[0]
        return module, submodule, children(submodule)[0]

    def test_case_details_match_screenshot_parent_child_layout(self):
        result, output = self.generate(self.case())
        self.assertEqual(result.returncode, 0, result.stderr)
        module, submodule, case = self.read_case(output)
        self.assertEqual((title(module), title(submodule), title(case)), ("订单", "提交", "显示待支付状态"))
        detail = children(case)
        self.assertEqual([title(item) for item in detail], [
            "前置条件：用户已登录",
            "测试数据：一件普通商品",
            "操作步骤：1、选择商品\n2、提交订单",
        ])
        self.assertEqual(children(detail[0]), [])
        self.assertEqual(children(detail[1]), [])
        self.assertEqual([title(item) for item in children(detail[2])], ["预期结果：1、商品进入订单\n2、订单显示待支付状态"])
        self.assertEqual(children(children(detail[2])[0]), [])
        self.assertEqual([item.get("marker-id") for item in case.findall(f"{NS}marker-refs/{NS}marker-ref")], ["priority-1"])
        with zipfile.ZipFile(output) as archive:
            self.assertNotIn("INTERNAL-001", archive.read("content.xml").decode("utf-8"))

    def test_legacy_title_uses_only_matching_scene_name(self):
        result, output = self.generate(self.case(test_name="", title="订单_提交_商品为空_提交被拦截"))
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, case = self.read_case(output)
        self.assertEqual(title(case), "商品为空_提交被拦截")

    def test_unmatched_three_part_name_is_rejected(self):
        result, output = self.generate(self.case(test_name="订单_支付_显示待支付状态"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不符合当前模块/子模块", result.stderr)
        self.assertFalse(output.exists())

    def test_scene_only_name_is_preserved(self):
        result, output = self.generate(self.case(test_name="显示待支付状态"))
        self.assertEqual(result.returncode, 0, result.stderr)
        module, submodule, case = self.read_case(output)
        self.assertEqual((title(module), title(submodule), title(case)), ("订单", "提交", "显示待支付状态"))

    def test_module_submodule_without_scene_is_rejected(self):
        result, output = self.generate(self.case(test_name="订单_提交"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少测试场景", result.stderr)
        self.assertFalse(output.exists())

    def test_blank_case_name_is_rejected(self):
        result, output = self.generate(self.case(test_name="   ", title="", name=""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("用例名称不能为空", result.stderr)
        self.assertFalse(output.exists())

    def test_empty_optional_fields_are_omitted(self):
        result, output = self.generate(self.case(preconditions="", test_data="", priority="p0"))
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, case = self.read_case(output)
        detail = children(case)
        self.assertEqual(len(detail), 1)
        self.assertTrue(title(detail[0]).startswith("操作步骤："))
        self.assertEqual(len(children(detail[0])), 1)
        self.assertEqual(case.findall(f"{NS}marker-refs/{NS}marker-ref"), [])

    def test_expected_result_without_steps_is_rejected(self):
        result, output = self.generate(self.case(steps=""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("预期结果缺少对应的操作步骤", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
