import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
NS = {"x": "urn:xmind:xmap:xmlns:content:2.0"}
FIXTURE = """# 合成公告测试
## 2. 公告
### 2.1 标题
#### TC_DEMO_001 [P1] 保存后保留标题
- **前置条件**：编辑者打开可编辑原稿
- **输入数据**：月度公告
- **操作步骤**：1、输入标题并点击保存
- **预期输出**：1、重新打开仍为月度公告
"""


class TestMarkdownCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "cases.md"
        self.source.write_text(FIXTURE, encoding="utf-8")
        self.output = self.root / "exported.xmind"

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *map(str, args)], cwd=self.root, capture_output=True, text=True, timeout=10)

    def test_help_is_read_only_without_input(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        for script in ("parse_md_test.py", "export_md_to_xmind.py"):
            result = self.run_cli(script, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--input", result.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_parse_explicit_input(self):
        result = self.run_cli("parse_md_test.py", "--input", self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Parsed modules: 1", result.stdout)
        self.assertIn("Total cases: 1", result.stdout)

    def test_export_explicit_paths_preserves_details_and_markers(self):
        original = self.source.read_bytes()
        result = self.run_cli("export_md_to_xmind.py", "--input", self.source, "--output", self.output, "--root-title", "合成验证")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.source.read_bytes(), original)
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            tree = ET.fromstring(archive.read("content.xml"))
        titles = [node.text for node in tree.findall(".//x:title", NS)]
        for title in ("合成验证", "TC_DEMO_001 保存后保留标题", "前置条件：\n编辑者打开可编辑原稿", "测试数据：\n月度公告", "操作步骤：\n1、输入标题并点击保存", "预期结果：\n1、重新打开仍为月度公告"):
            self.assertIn(title, titles)
        self.assertEqual(tree.find(".//x:marker-ref", NS).get("marker-id"), "priority-1")

    def test_export_default_title_comes_from_filename(self):
        result = self.run_cli("export_md_to_xmind.py", "--input", self.source, "--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.output) as archive:
            tree = ET.fromstring(archive.read("content.xml"))
        self.assertEqual(tree.find("x:sheet/x:topic/x:title", NS).text, "cases")

    def test_missing_input_fails_without_export(self):
        for script in ("parse_md_test.py", "export_md_to_xmind.py"):
            args = ["--input", self.root / "missing.md"]
            if script == "export_md_to_xmind.py":
                args += ["--output", self.output]
            result = self.run_cli(script, *args)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.output.exists())

    def test_export_rejects_overwriting_input(self):
        original = self.source.read_bytes()
        result = self.run_cli("export_md_to_xmind.py", "--input", self.source, "--output", self.source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.source.read_bytes(), original)

    def test_invalid_markdown_fails_without_export(self):
        self.source.write_text("# 没有测试用例", encoding="utf-8")
        for script in ("parse_md_test.py", "export_md_to_xmind.py"):
            args = ["--input", self.source]
            if script == "export_md_to_xmind.py":
                args += ["--output", self.output]
            result = self.run_cli(script, *args)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
