"""Behavioral regression for the neutral bridge and reviewer/shared distribution."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILLS = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load("reviewer_input", SKILLS / "testcase-reviewer/testcase-review/scripts/prepare_reviewer_input.py")
contracts = load("reviewer_contracts", SKILLS / "_testspec-shared/scripts/validate_skill_contracts.py")


class TestReviewerInput(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.json = self.root / "testcases.json"
        self.req = self.root / "requirements.md"
        self.case = {
            "id": "CASE-01", "module": "通知", "submodule": "设置", "test_name": "通知_设置_空值被拒绝",
            "preconditions": "已登录", "test_data": "值：0；金额：0.00元；文本：空串",
            "steps": "1. 清空名称\n2. 点击保存", "expected_result": "显示“名称不能为空”，原配置不变", "priority": "p1",
            "tp_refs": ["TP_NOTICE_SAVE_001"], "origin": {"kind": "testspec-native"}, "trust": {"status": "provisional"},
        }
        self.write_cases([self.case])
        self.req.write_text('# 规则\n名称不能为空。\n<!-- testspec-context\n{"review_gate":{"status":"pass"}}\n-->\n<!-- 原始备注 -->\n', encoding="utf-8")

    def write_cases(self, cases):
        self.json.write_text(json.dumps({"_context": {"source_skill": "testcase-generate"}, "testcases": cases}, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SKILLS / "testcase-reviewer/testcase-review/scripts/prepare_reviewer_input.py"), "--testcases", str(self.json), *map(str, args)], text=True, capture_output=True)

    def test_preserves_all_business_values_and_ids_without_control_metadata(self):
        packet = bridge.prepare(self.json, [self.req])
        self.assertEqual(packet["testcases"], [{k: self.case[k] for k in bridge.CASE_FIELDS}])
        text = json.dumps(packet, ensure_ascii=False)
        for control in ("_context", "tp_refs", "review_gate", "source_skill", "testspec-context", '"origin"', '"trust"'):
            self.assertNotIn(control, text)
        self.assertIn("<!-- 原始备注 -->", packet["requirements"][0]["content"])

    def test_missing_and_empty_fields_are_not_invented(self):
        self.write_cases([{"test_name": "未编号草稿", "test_data": "", "preconditions": None, "priority": 0}])
        self.assertEqual(bridge.prepare(self.json, [])["testcases"], [{"test_name": "未编号草稿", "preconditions": None, "test_data": "", "priority": 0}])

    def test_sources_and_multiple_requirements_are_read_only_and_fingerprinted(self):
        extra = self.root / "raw-prd.md"
        extra.write_text("# 用户选定的原始需求\n", encoding="utf-8")
        before = {p: p.read_bytes() for p in (self.json, self.req, extra)}
        packet = bridge.prepare(self.json, [extra, self.req])
        self.assertEqual(packet["case_source"]["sha256"], hashlib.sha256(before[self.json]).hexdigest())
        self.assertEqual([s["sha256"] for s in packet["requirements"]], [hashlib.sha256(before[p]).hexdigest() for p in (extra, self.req)])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_stdout_cli_supports_missing_requirements_without_claiming_coverage(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["requirements"], [])
        self.assertNotIn("coverage", json.loads(result.stdout))

    def test_cli_writes_new_packet_but_refuses_existing_output_and_input_alias(self):
        output = self.root / "cache/input.json"
        first = self.run_cli("--requirements", self.req, "--output", output)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = output.read_bytes()
        self.assertNotEqual(self.run_cli("--output", output).returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        before_input = self.json.read_bytes()
        self.assertNotEqual(self.run_cli("--output", self.json).returncode, 0)
        self.assertEqual(self.json.read_bytes(), before_input)

    def test_invalid_or_empty_cases_fail_before_creating_output(self):
        output = self.root / "new/input.json"
        for value in ("{", "[]", '{"testcases":[]}', '{"testcases":[null]}'):
            with self.subTest(value=value):
                self.json.write_text(value, encoding="utf-8")
                self.assertNotEqual(self.run_cli("--output", output).returncode, 0)
                self.assertFalse(output.exists())

    def test_missing_or_non_utf8_source_fails_without_partial_packet(self):
        output = self.root / "input.json"
        self.req.write_bytes(b"\xff")
        for req in (self.req, self.root / "missing.md"):
            with self.subTest(req=req):
                result = self.run_cli("--requirements", req, "--output", output)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())


class TestStandaloneSnapshot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.vendor = self.skills / "testcase-reviewer"
        shutil.copytree(SKILLS / "testcase-reviewer", self.vendor)
        shutil.copytree(SKILLS / "_testspec-shared", self.skills / "_testspec-shared")
        self.manifest = self.skills / "_testspec-shared/references/testcase-reviewer-source.json"

    def errors(self):
        result = []
        with patch.object(contracts, "SKILLS_DIR", self.skills):
            contracts.validate_standalone_reviewer(result)
        return result

    def test_unified_package_and_shared_reports_validate_without_project_checkout(self):
        isolated = self.root / "relocated/skills/testcase-reviewer"
        shutil.copytree(self.vendor, isolated)
        shutil.copytree(self.skills / "_testspec-shared", isolated.parent / "_testspec-shared")
        result = subprocess.run([sys.executable, "-B", "scripts/validate_skill_repo.py", "."], cwd=isolated, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((isolated.parent.parent / "README.md").exists())
        self.assertEqual(self.errors(), [])

    def test_package_without_shared_reports_is_rejected(self):
        isolated = self.root / "reviewer-only/testcase-reviewer"
        shutil.copytree(self.vendor, isolated)
        result = subprocess.run([sys.executable, "-B", "scripts/validate_skill_repo.py", "."], cwd=isolated, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("缺少共享报告资源", result.stdout)

    def test_missing_each_required_shared_report_resource_is_rejected(self):
        validator = load("package_reports", self.vendor / "scripts/validate_skill_repo.py")
        for name in validator.REQUIRED_SHARED_FILES:
            with self.subTest(resource=name):
                path = self.skills / "_testspec-shared" / name
                original = path.read_bytes()
                path.unlink()
                try:
                    errors = []
                    validator.validate_required_files(self.vendor, errors)
                    self.assertEqual(len(errors), 1, errors)
                    self.assertIn(name, errors[0])
                finally:
                    path.write_bytes(original)

    def test_package_exposes_one_review_entry_with_internal_sop_module(self):
        entries = list(self.vendor.rglob("SKILL.md"))
        self.assertEqual(entries, [self.vendor / "SKILL.md"])
        self.assertIn("name: testcase-reviewer\n", entries[0].read_text())
        self.assertTrue((self.vendor / "testcase-review/review-workflow.md").is_file())
        self.assertFalse((self.skills / "testcase-review").exists())

    def test_package_validation_requires_both_entry_and_sop_workflow(self):
        for name in ("SKILL.md", "testcase-review/review-workflow.md"):
            with self.subTest(name=name):
                path = self.vendor / name
                original = path.read_bytes()
                path.unlink()
                result = subprocess.run([sys.executable, "-B", "scripts/validate_skill_repo.py", "."], cwd=self.vendor, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(name, result.stdout)
                path.write_bytes(original)

    def test_snapshot_change_missing_or_extra_file_is_rejected(self):
        target = self.vendor / "SKILL.md"
        before = target.read_bytes()
        target.write_bytes(before + b"\nchanged")
        self.assertTrue(self.errors())
        target.unlink()
        self.assertTrue(self.errors())
        target.write_bytes(before)
        extra = self.vendor / "testspec-adapter.md"
        extra.write_text("Unexpected coupling")
        self.assertTrue(self.errors())
        extra.unlink()
        self.assertEqual(self.errors(), [])

    def test_missing_or_unsafe_source_manifest_is_rejected(self):
        for value in ({"files": {}}, {"files": {"../escape": "0" * 64}}, {"files": {"SKILL.md": "not-a-hash"}}):
            with self.subTest(value=value):
                self.manifest.write_text(json.dumps(value))
                self.assertTrue(self.errors())
        self.manifest.unlink()
        self.assertTrue(self.errors())

    def test_symlink_is_rejected_in_the_pinned_snapshot(self):
        target = self.vendor / "unexpected-link"
        target.symlink_to(self.vendor / "SKILL.md")
        self.assertTrue(self.errors())
        target.unlink()
        relocated = self.root / "aliased-snapshot"
        self.vendor.rename(relocated)
        self.vendor.symlink_to(relocated, target_is_directory=True)
        self.assertTrue(self.errors())

    def test_sop_specific_name_lints_do_not_apply_to_standalone_content(self):
        old_name = "testspec" + "-analysis"
        removed_stage = "testcase" + "-merge"
        (self.root / "README.md").write_text("TestSpec")
        (self.vendor / "notes.md").write_text(old_name + " " + removed_stage)
        with patch.object(contracts, "ROOT", self.root), patch.object(contracts, "SKILLS_DIR", self.skills):
            errors = []
            contracts.validate_no_old_skill_names(errors)
            contracts.validate_no_removed_stage_references(errors)
            self.assertEqual(errors, [])
            (self.vendor / "testcase-review/notes.md").write_text(old_name + " " + removed_stage)
            contracts.validate_no_old_skill_names(errors)
            contracts.validate_no_removed_stage_references(errors)
            self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
