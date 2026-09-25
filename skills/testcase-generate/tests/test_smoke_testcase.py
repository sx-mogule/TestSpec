import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


def _venv_python() -> str:
    return sys.executable


def _xmind_script() -> str:
    pkg_root = Path(__file__).resolve().parents[1]
    return str(pkg_root / "scripts" / "generate_xmind.py")


class TestSmokeTestCase(unittest.TestCase):
    def test_priority_markers_and_detail_order(self):
        """p0 无优先级标记，p2 使用 2 号标记，详情按步骤后紧跟预期结果。"""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_path = td_path / "testcases.json"
            output_path = td_path / "out.xmind"

            testcases = [
                {
                    "id": "需求A_202602280001",
                    "module": "登录",
                    "submodule": "凭据验证",
                    "test_name": "登录_凭据验证_正确凭据登录成功",
                    "type": "冒烟",
                    "priority": "p0",
                    "preconditions": "",
                    "test_data": "账号：正确账号",
                    "steps": "1、输入正确的账号密码\\n2、点击登录",
                    "expected_result": "1、登录成功",
                },
                {
                    "id": "需求A_202602280002",
                    "module": "登录",
                    "submodule": "凭据验证",
                    "test_name": "登录_凭据验证_错误凭据登录失败",
                    "type": "负向",
                    "priority": "p2",
                    "steps": "1、输入错误的账号密码\\n2、点击登录",
                    "expected_result": "1、提示登录失败",
                },
            ]
            input_path.write_text(json.dumps(testcases, ensure_ascii=False), encoding="utf-8")

            subprocess.check_call(
                [
                    _venv_python(),
                    _xmind_script(),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--title",
                    "测试用例",
                ],
                timeout=30,
            )

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("content.xml").decode("utf-8")

            self.assertIn("登录", content)
            self.assertIn("凭据验证", content)
            self.assertIn('marker-id="priority-2"', content)
            self.assertNotIn('marker-id="priority-1"', content)
            self.assertLess(content.find("操作步骤："), content.find("预期结果："))


if __name__ == "__main__":
    unittest.main()
