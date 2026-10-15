import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/select_smoke.py"
spec = spec_from_file_location("select_smoke", SCRIPT)
selector = module_from_spec(spec)
spec.loader.exec_module(selector)


def write_markdown(path, body, context):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body + "\n\n<!-- testspec-context\n" +
                    json.dumps(context, ensure_ascii=False, indent=2) + "\n-->\n", encoding="utf-8")


def make_change(root):
    revision = {"version": 1, "summary": "合成订单闭环", "updated_by_skill": "prd-analysis"}

    def context(skill, stale, **extra):
        return dict(source_skill=skill, source_revision=revision, blocking_open_questions=[],
                    dynamic_followups=[], material_quality="high", stale_downstream_artifacts=stale, **extra)

    write_markdown(root / "requirements.md", "# 合成需求\nREQ-001：提交后显示待支付订单。\n"
                   "REQ-002：查询展示订单明细。\nREQ-003：取消后订单关闭。", context("prd-analysis", [
                       "requirements-analysis.md", "specs/testpoints.md", "artifacts/testcases.json", "review-report.md"]))
    write_markdown(root / "requirements-analysis.md", "# 合成分析\n提交为最短核心闭环，查询和取消仍需完整覆盖。",
                   context("prd-analysis", ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"],
                           next_skill="test-points"))
    points = "# 测试点：合成订单\n## 命名字典\n### 模块字典\n| 模块名称 | MODULE |\n|---|---|\n| 订单 | ORDER |\n"
    points += "### 功能点字典\n| 模块名称 | 功能点名称 | FEATURE |\n|---|---|---|\n| 订单 | 提交 | SUBMIT |\n| 订单 | 查询 | QUERY |\n| 订单 | 取消 | CANCEL |\n### 订单模块\n"
    for feature, name, tier in (("SUBMIT", "提交", "Smoke"), ("QUERY", "查询", "Full"), ("CANCEL", "取消", "Full")):
        points += (f"#### {name}功能\n##### 功能验证点 (Functional)\n"
                   f"- TP_ORDER_{feature}_001: 订单_{name}_确认业务结果\n"
                   f"  - 验证要点: {name}后展示已确认的订单状态\n  - 设计方法: 流程分析\n"
                   f"  - 优先级: p0\n  - Oracle 状态: confirmed\n  - Oracle 范围: direct\n"
                   f"  - 回归层级: {tier}\n  - 关联需求: REQ-001/REQ-002/REQ-003\n")
    write_markdown(root / "specs/testpoints.md", points, context("test-points", [
        "artifacts/testcases.json", "review-report.md"], design_methods=["流程分析"], next_skill="testcase-generate"))
    origin = {"kind": "testspec-native", "source_change": "synthetic-smoke"}
    trust = {"status": "provisional", "basis": "prd-first"}
    scenarios = [
        ("QUERY", "查询", "订单详情展示明细", "1、打开已有订单详情并查看商品明细", "1、订单详情列出原商品名称、购买数量与应付金额", "p0", "Full", "正向"),
        ("SUBMIT", "提交", "创建后显示待支付订单", "1、选择可购买商品并提交创建订单", "1、创建的订单详情显示独立订单编号与待支付状态", "p0", "Smoke", "冒烟"),
        ("CANCEL", "取消", "取消后关闭待支付订单", "1、对待支付订单点击取消并确认关闭", "1、目标订单更新为已关闭状态且不可继续支付", "p1", "Full", "正向"),
    ]
    cases = []
    for index, (feature, name, scene, steps, expected, priority, tier, kind) in enumerate(scenarios, 1):
        cases.append(dict(id=f"SYN-SMOKE-{index:03d}", module="订单", submodule=name,
                          test_name=f"订单_{name}_{scene}", preconditions="已准备可操作的独立订单与商品数据",
                          test_data="使用当前用例独立准备的业务数据", steps=steps, expected_result=expected,
                          priority=priority, regression_tier=tier, type=kind,
                          tp_refs=[f"TP_ORDER_{feature}_001"], origin=origin, trust=trust))
    payload = {"schema_version": 2, "_context": context("testcase-generate", ["review-report.md"],
               design_methods=["流程分析"], next_skill="testcase-review", origin=origin, trust=trust), "testcases": cases}
    (root / "artifacts").mkdir()
    (root / "artifacts/testcases.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reviewed = context("testcase-review", [], design_methods=["流程分析"],
                       reviewed_artifacts=selector.artifact_hashes(root),
                       review_gate={"status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": []})
    write_markdown(root / "review-report.md", "# 合成评审上下文夹具\n仅用于脚本契约回归，不代表实际模型 Review。", reviewed)
    return payload


class TestSelectSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = make_change(self.root)
        self.output = self.root / "artifacts/smoke-testcases.json"

    def write_cases(self, payload):
        (self.root / "artifacts/testcases.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_review(self, **updates):
        path = self.root / "review-report.md"
        context = selector.context_chain.markdown_context(path)
        context.update(updates)
        write_markdown(path, "# 合成评审上下文夹具", context)

    def refresh_review(self):
        self.write_review(reviewed_artifacts=selector.artifact_hashes(self.root))

    def assert_blocked(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            selector.select_smoke(self.root)
        self.assertFalse(self.output.exists())

    def test_selects_existing_tier_preserving_case_and_all_sources(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = selector.select_smoke(self.root)
        selected = json.loads(self.output.read_text())
        self.assertEqual(result["smoke_case_count"], 1)
        self.assertEqual(result["full_case_count"], 3)
        self.assertEqual(selected["testcases"], [self.payload["testcases"][1]])
        self.assertEqual(selected["_context"]["full_set_validation"]["coverage"]["coverage_rate"], 1.0)
        self.assertEqual(selected["_context"]["selected_tp_ids"], ["TP_ORDER_SUBMIT_001"])
        self.assertEqual(selected["_context"]["artifact_kind"], "smoke-execution-set")
        for relative, content in before.items():
            self.assertEqual((self.root / relative).read_bytes(), content)

    def test_full_set_coverage_cannot_be_replaced_with_smoke_coverage(self):
        self.payload["testcases"] = [self.payload["testcases"][1]]
        self.write_cases(self.payload)
        self.refresh_review()
        self.assert_blocked("TP_COVERAGE_BELOW_THRESHOLD")

    def test_existing_warning_status_does_not_count_as_pass(self):
        self.payload["testcases"][0]["expected_result"] = "1、操作成功"
        self.write_cases(self.payload)
        self.refresh_review()
        self.assert_blocked("完整用例集尚未通过")

    def test_blocked_review_stops_selection(self):
        self.write_review(review_gate={"status": "blocked", "s1_unresolved_count": 0, "s1_issue_ids": []})
        self.assert_blocked("Review 门禁未通过")

    def test_passing_review_with_unresolved_s1_is_blocked(self):
        self.write_review(review_gate={"status": "pass", "s1_unresolved_count": 1, "s1_issue_ids": ["SYN-S1-001"]})
        self.assert_blocked("zero unresolved S1")

    def test_missing_review_stops_selection(self):
        (self.root / "review-report.md").unlink()
        self.assert_blocked("missing review-report")

    def test_changed_cases_require_new_review(self):
        self.payload["testcases"][0]["test_data"] = "更新后的独立订单数据"
        self.write_cases(self.payload)
        self.assert_blocked("文件已变化")

    def test_changed_points_require_new_review(self):
        path = self.root / "specs/testpoints.md"
        path.write_text(path.read_text() + "\n范围补充说明。\n", encoding="utf-8")
        self.assert_blocked("文件已变化")

    def test_missing_review_binding_stops_selection(self):
        self.write_review(reviewed_artifacts={})
        self.assert_blocked("Review 缺少")

    def test_review_with_stale_artifacts_stops_selection(self):
        self.write_review(stale_downstream_artifacts=["artifacts/testcases.json"])
        self.assert_blocked("Review 仍有过期产物")

    def test_p0_without_smoke_tier_is_not_automatically_selected(self):
        self.payload["testcases"][1]["regression_tier"] = "Full"
        self.write_cases(self.payload)
        self.refresh_review()
        self.assert_blocked("没有 regression_tier=Smoke")

    def test_smoke_tier_with_non_p0_priority_is_blocked(self):
        self.payload["testcases"][1].update(priority="p1", type="正向")
        self.write_cases(self.payload)
        self.refresh_review()
        self.assert_blocked("Smoke 用例必须全部为 p0")

    def test_old_review_revision_stops_selection(self):
        revision = copy.deepcopy(self.payload["_context"]["source_revision"])
        revision["version"] = 2
        self.write_review(source_revision=revision)
        self.assert_blocked("source_revision differs")

    def test_selection_keeps_source_order(self):
        self.payload["testcases"][0]["regression_tier"] = "Smoke"
        self.write_cases(self.payload)
        self.refresh_review()
        selector.select_smoke(self.root)
        self.assertEqual(json.loads(self.output.read_text())["testcases"], self.payload["testcases"][:2])

    def test_failed_selection_keeps_existing_output_unchanged(self):
        self.output.write_text("EXISTING_SMOKE_OUTPUT", encoding="utf-8")
        self.write_review(review_gate={"status": "blocked", "s1_unresolved_count": 0, "s1_issue_ids": []})
        with self.assertRaisesRegex(ValueError, "Review 门禁未通过"):
            selector.select_smoke(self.root)
        self.assertEqual(self.output.read_text(), "EXISTING_SMOKE_OUTPUT")

    def test_output_hardlink_does_not_modify_complete_cases(self):
        source = self.root / "artifacts/testcases.json"
        before = source.read_bytes()
        os.link(source, self.output)
        selector.select_smoke(self.root)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(len(json.loads(self.output.read_text())["testcases"]), 1)

    def test_cli_failure_returns_nonzero_without_output(self):
        self.write_review(review_gate={"status": "blocked", "s1_unresolved_count": 0, "s1_issue_ids": []})
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--change-dir", str(self.root)],
                                capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")
        self.assertFalse(self.output.exists())

    def test_selected_json_exports_with_existing_xmind_generator(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--change-dir", str(self.root)],
                                capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        output = self.root / "artifacts/smoke-cases.xmind"
        exported = subprocess.run([sys.executable, "-B", str(SCRIPT.with_name("generate_xmind.py")),
                                   "--input", str(self.output), "--output", str(output)],
                                  capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(exported.returncode, 0, exported.stderr)
        with zipfile.ZipFile(output) as package:
            self.assertIsNone(package.testzip())
            content = package.read("content.xml").decode("utf-8")
        self.assertIn("创建后显示待支付订单", content)
        self.assertNotIn("订单详情展示明细", content)


if __name__ == "__main__":
    unittest.main()
