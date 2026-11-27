import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import verify_eval_artifacts as verify  # noqa: E402


class TestReviewMatrix(unittest.TestCase):
    EXECUTION = "\n".join([
        "## 评审执行记录",
        "**评审状态**: 已完成",
        "**执行方式**: 同一模型单次评审",
        "**判定依据及限制**: requirements.md REQ-1～REQ-3；无原始 PRD",
        "**机器检查**: validate_testcases.py PASS",
        "## BDD 场景评审",
        "**BDD评审状态**: 已完成",
    ])

    def valid_report(self, issues="未发现问题。", counts=None, gate=None):
        counts = counts or {}
        unresolved = {issue["dimension"] for issue in verify.parse_issues(issues) if issue["status"] != "resolved"}
        rows = []
        for key in verify.MATRIX_IDS:
            if key == "M4":
                rows.append("| M4 相似候选 | — | 0 组 | 0 |")
            else:
                result = "blocked" if key in unresolved else "pass"
                rows.append(f"| {key} 检查 | {result} | 已检查 4 项 | {counts.get(key, 0)} |")
        gate = gate or {"status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": [],
                        "judgment_unresolved_count": 0, "judgment_issue_ids": [],
                        "description_unresolved_count": 0, "description_issue_ids": []}
        return "\n".join([
            f"**Review Gate**: {gate['status']}",
            self.EXECUTION,
            "## 二、需求判定力表",
            "| 1 | REQ-1 上限 8 件 | REQ-1 | CASE-1 | 允许第 9 件 | 是 | 已拦住 | 无 |",
            "### 方法落地（J3）",
            "| TP_CART_QTY_101 | 边界值 | 1 | ✓ | ✓ | ✓ | ✓ | 通过 | CASE-1 有 8/9 边界 |",
            "## 三、用例与 BDD 质量",
            "### 四项描述门禁",
            "| D1 | 前置条件 | 1/1 | pass | 无 |",
            "| D2 | 测试数据 | 1/1 | pass | 无 |",
            "| D3 | 操作步骤 | 1/1 | pass | 无 |",
            "| D4 | 预期表述 | 1/1 | pass | 无 |",
            "## 四、问题清单",
            issues,
            "## 五、14 项矩阵",
            "| 检查项 | 结果 | 关键数值 | 问题数 |",
            "|---|---|---|---|",
            *rows,
            "<!-- testspec-context",
            json.dumps({"review_gate": gate}),
            "-->",
        ])

    J1_ISSUE = "\n".join([
        "- [S1] [open] RV-001 [J1] 范围：REQ-3 / TP_CART_QTY_101",
        "  - **定位**: requirements.md#REQ-3「单 SKU 最多加购 8 件」",
        "  - **会逃逸的行为**: 允许加购第 9 件时现有用例仍通过",
        "  - **建议**: 补上限置灰用例",
        "  - **owner**: testcase-generate",
    ])

    def blocked_gate(self, s1=(), judgment=(), description=()):
        return {"status": "blocked", "s1_unresolved_count": len(s1), "s1_issue_ids": list(s1),
                "judgment_unresolved_count": len(judgment), "judgment_issue_ids": list(judgment),
                "description_unresolved_count": len(description), "description_issue_ids": list(description)}

    def root_report(self, content):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        report = Path(directory.name) / "review-report.md"
        report.write_text(content, encoding="utf-8")
        return report

    def test_complete_layered_matrix_is_valid(self):
        report = self.root_report(self.valid_report())
        result = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "review", "--report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_review_command_also_requires_execution_record(self):
        report = self.root_report(self.valid_report().replace(self.EXECUTION, ""))
        result = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "review", "--report", str(report)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("评审状态", result.stdout)

    def test_pass_rejects_incomplete_execution_or_missing_evidence(self):
        baseline = self.valid_report()
        for old, new, expected in (
            ("**评审状态**: 已完成", "**评审状态**: 未完成\n**未完成原因**: D4 尚未完成", "评审状态 已完成"),
            ("## 二、需求判定力表", "## 其他", "nonempty 需求判定力表"),
            ("| 1 | REQ-1 上限 8 件 | REQ-1 | CASE-1 | 允许第 9 件 | 是 | 已拦住 | 无 |", "", "nonempty 需求判定力表"),
            ("| 是 | 已拦住 |", "| 否 | 拦不住 |", "covered and observable check"),
            ("### 四项描述门禁", "### 其他", "one 四项描述门禁 table"),
            ("| D4 | 预期表述 | 1/1 |", "| D4 | 预期表述 | 0/1 |", "D4 must cover the full testcase set"),
        ):
            with self.subTest(expected=expected):
                errors = verify.validate_review_report(baseline.replace(old, new))
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_partial_review_can_record_a_blocked_gate(self):
        text = self.valid_report(gate=self.blocked_gate()).replace(
            "**评审状态**: 已完成", "**评审状态**: 未完成\n**未完成原因**: 尚未核对四项描述",
        ).replace("### 四项描述门禁", "### 待补项")
        self.assertEqual(verify.validate_review_report(text) + verify.validate_review_execution(text), [])

    def test_gate_rejects_conflicting_visible_status_and_blocking_matrix_rows(self):
        baseline = self.valid_report()
        for old, new, expected in (
            ("**Review Gate**: pass", "**Review Gate**: blocked", "visible Review Gate must match"),
            ("**Review Gate**: pass", "", "visible Review Gate must match"),
            ("| J1 检查 | pass |", "| J1 检查 | blocked |", "J1: a passing Review Gate requires a pass result"),
            ("| D4 检查 | pass |", "| D4 检查 | fail |", "D4: a passing Review Gate requires a pass result"),
        ):
            with self.subTest(expected=expected):
                errors = verify.validate_review_report(baseline.replace(old, new))
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_unresolved_issue_cannot_claim_matrix_pass_under_a_blocked_gate(self):
        text = self.valid_report(self.J1_ISSUE, {"J1": 1}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        errors = verify.validate_review_report(text.replace("| J1 检查 | blocked |", "| J1 检查 | pass |"))
        self.assertIn("review matrix J1: unresolved issues cannot have a pass result", errors)
        errors = verify.validate_review_report(text.replace("| D4 检查 | pass |", "| D4 检查 | fail |"))
        self.assertIn("review matrix D4: a fail result requires an unresolved issue", errors)

    def test_missing_row_and_placeholder_count_are_rejected(self):
        text = self.valid_report().replace("| J2 检查 | pass | 已检查 4 项 | 0 |\n", "")
        self.assertTrue(any("J2: row missing" in error for error in verify.validate_review_report(text)))
        text = self.valid_report().replace("| D4 检查 | pass | 已检查 4 项 | 0 |", "| D4 检查 | pass | 已检查 4 项 | <count> |")
        self.assertTrue(any("D4: problem count" in error for error in verify.validate_review_report(text)))

    def test_m4_takes_no_result_and_no_issues(self):
        text = self.valid_report().replace("| M4 相似候选 | — | 0 组 | 0 |", "| M4 相似候选 | pass | 0 组 | 0 |")
        self.assertTrue(any("M4" in error for error in verify.validate_review_report(text)))
        issue = self.J1_ISSUE.replace("[J1]", "[M4]")
        text = self.valid_report(issue, {"M4": 1}, self.blocked_gate(s1=["RV-001"]))
        self.assertTrue(any("uses M4" in error for error in verify.validate_review_report(text)))

    def test_tagged_issue_is_counted_and_gated(self):
        text = self.valid_report(self.J1_ISSUE, {"J1": 1}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        self.assertEqual(verify.validate_review_report(text), [])

    def test_matrix_count_must_match_tagged_issues(self):
        text = self.valid_report(self.J1_ISSUE, {}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        self.assertTrue(any("J1: problem count 0 differs" in error for error in verify.validate_review_report(text)))

    def test_gate_lists_must_match_unresolved_issues(self):
        text = self.valid_report(self.J1_ISSUE, {"J1": 1}, self.blocked_gate(s1=["RV-001"]))
        self.assertTrue(any("judgment_issue_ids differs" in error for error in verify.validate_review_report(text)))
        d4 = self.J1_ISSUE.replace("[S1] [open] RV-001 [J1]", "[S3] [accepted] RV-002 [D4]")
        text = self.valid_report(d4, {"D4": 1}, self.blocked_gate())
        self.assertTrue(any("description_issue_ids differs" in error for error in verify.validate_review_report(text)))
        self.assertEqual(verify.validate_review_report(self.valid_report(d4, {"D4": 1}, self.blocked_gate(description=["RV-002"]))), [])

    def test_resolved_issue_leaves_gate_lists(self):
        resolved = self.J1_ISSUE.replace("[open]", "[resolved]")
        self.assertEqual(verify.validate_review_report(self.valid_report(resolved, {"J1": 1})), [])

    def test_issue_requires_owner_and_unique_id(self):
        no_owner = self.J1_ISSUE.replace("  - **owner**: testcase-generate", "")
        text = self.valid_report(no_owner, {"J1": 1}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        self.assertTrue(any("owner" in error for error in verify.validate_review_report(text)))
        twice = self.J1_ISSUE + "\n" + self.J1_ISSUE
        text = self.valid_report(twice, {"J1": 2}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        self.assertTrue(any("duplicate issue ID RV-001" in error for error in verify.validate_review_report(text)))

    def test_keyword_only_sections_without_matrix_are_rejected(self):
        text = "M1 M2 M3 M4 M5 J1 J2 J3 J4 D1 D2 D3 D4 D5"
        self.assertTrue(any("matrix" in error for error in verify.validate_review_report(text)))

    def legacy_report(self, h8="| H8 测试价值与亮点 | — | 标杆用例数 0；可复用模式数 0 | 0 |"):
        rows = [h8 if key == "H8" else f"| {key} 检查 | pass | 已检查 4 项 | 0 |" for key in verify.LEGACY_MATRIX_IDS]
        return "\n".join(["### 结论总览矩阵", "| 检查项 | 结果 | 关键指标 | 问题数 |", "|---|---|---|---|", *rows, "## 整改建议清单"])

    def test_legacy_r_h_matrix_remains_readable(self):
        self.assertEqual(verify.validate_review_report(self.legacy_report()), [])
        self.assertTrue(any("H8" in error for error in verify.validate_review_report(self.legacy_report("| H8 亮点 | pass | 无 | 0 |"))))
        self.assertTrue(any("H8" in error for error in verify.validate_review_report(self.legacy_report("| H8 亮点 | — | <x> | 0 |"))))

    def test_finding_matches_tagged_issue_severity_and_text(self):
        text = self.valid_report(self.J1_ISSUE, {"J1": 1}, self.blocked_gate(s1=["RV-001"], judgment=["RV-001"]))
        self.assertEqual(verify.validate_review_finding(text, "J1", "TP_CART_QTY_101", "S1", "第 9 件"), [])
        self.assertTrue(verify.validate_review_finding(text, "J2", "TP_CART_QTY_101", "S1", "第 9 件"))
        self.assertTrue(verify.validate_review_finding(text, "J1", "TP_CART_QTY_101", "S2", "第 9 件"))

    def test_evidence_reads_layer_section_and_tagged_issues(self):
        text = self.valid_report()
        self.assertEqual(verify.validate_review_evidence(text, "J1", ["REQ-1", "CASE-1"], ["上限 8 件"]), [])
        self.assertTrue(verify.validate_review_evidence(text, "J1", ["CASE-9"], []))

    def test_legacy_finding_checks_dimension_case_severity_and_missing_oracle(self):
        report = "### H3: 意图一致性\n- [S1] [open] RV-S1-002 SYN_CANCEL_002：预期遗漏已取消状态。\n### H4: 前置条件充分性\n"
        self.assertEqual(verify.validate_review_finding(report, "H3", "SYN_CANCEL_002", "S1", "已取消"), [])
        self.assertTrue(verify.validate_review_finding(report, "H3", "SYN_CANCEL_001", "S1", "已取消"))

    def test_legacy_review_evidence_requires_case_test_point_and_boundary_values(self):
        report = "### H5: 风险与边界覆盖\nTP_NOTE_TITLE_100: SYN_MIN_001 最短 A；SYN_MAX_001 最长 ABCDEFGHIJ。\n### H6: 可维护性建议\n"
        self.assertEqual(verify.validate_review_evidence(report, "H5", ["TP_NOTE_TITLE_100", "SYN_MIN_001", "SYN_MAX_001"], ["最短", "A", "最长", "ABCDEFGHIJ"]), [])
        self.assertTrue(verify.validate_review_evidence(report, "H5", ["SYN_MISSING_001"], ["上限"]))


class TestIndependentXMindComparison(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = Path(__file__).resolve().parents[2] / "testcase-generate" / "scripts" / "generate_xmind.py"
        self.cases = [
            self.case("CASE-0", "p0", "", "", "显示待支付", "1、提交订单", "1、订单显示待支付"),
            self.case("CASE-1", "p1", "用户已登录", "订单号：D-1", "显示待支付", "1、提交订单", "1、订单显示待支付；编号为D-1"),
            self.case("CASE-2", "p2", "用户已登录", "订单号：D-2", "订单_取消_关闭待支付订单", "1、取消订单", "1、订单状态显示已关闭"),
        ]
        self.json_path = self.root / "cases.json"
        self.xmind_path = self.root / "cases.xmind"
        self.write_json()
        result = __import__("subprocess").run(
            [sys.executable, str(self.script), "--input", str(self.json_path), "--output", str(self.xmind_path)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @staticmethod
    def case(case_id, priority, preconditions, test_data, name, steps, expected):
        return {
            "id": case_id, "module": "订单", "submodule": "提交" if case_id != "CASE-2" else "取消",
            "test_name": name if "_" not in name or name.startswith("订单_") else f"订单_提交_{name}",
            "preconditions": preconditions, "test_data": test_data, "steps": steps,
            "expected_result": expected, "priority": priority,
        }

    def write_json(self):
        self.json_path.write_text(json.dumps({"schema_version": 2, "testcases": self.cases}, ensure_ascii=False), encoding="utf-8")

    def xml_root(self):
        with zipfile.ZipFile(self.xmind_path) as archive:
            return ET.fromstring(archive.read("content.xml"))

    def save_xml_root(self, root):
        with zipfile.ZipFile(self.xmind_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("content.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))

    def case_nodes(self, root):
        sheet = root.find(f"{verify.NS}sheet")
        top = sheet.find(f"{verify.NS}topic")
        result = []
        for module in verify._topic_children(top):
            for submodule in verify._topic_children(module):
                result.extend(verify._topic_children(submodule))
        return result

    def group_case_nodes(self, root, group_name):
        top = root.find(f"{verify.NS}sheet/{verify.NS}topic")
        module = verify._topic_children(top)[0]
        submodule = next(node for node in verify._topic_children(module) if verify._topic_title(node) == group_name)
        return verify._topic_children(submodule), submodule

    def test_complete_json_matches_fields_hierarchy_order_and_priorities(self):
        result = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "xmind",
            "--json", str(self.json_path), "--xmind", str(self.xmind_path),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_business_field_returns_nonzero(self):
        data = json.loads(self.json_path.read_text(encoding="utf-8"))
        del data["testcases"][0]["test_data"]
        self.json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "xmind",
            "--json", str(self.json_path), "--xmind", str(self.xmind_path),
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_data", result.stdout)

    def test_invalid_content_xml_returns_nonzero(self):
        with zipfile.ZipFile(self.xmind_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("content.xml", "<xmap-content><topic>")
        result = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "xmind",
            "--json", str(self.json_path), "--xmind", str(self.xmind_path),
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no element found", result.stdout)

    def test_data_mismatch_reports_case_and_field(self):
        root = self.xml_root()
        group_cases, _ = self.group_case_nodes(root, "提交")
        case = group_cases[1]
        test_data = next(n for n in verify._topic_children(case) if verify._topic_title(n).startswith("测试数据：\n"))
        test_data.find(f"{verify.NS}title").text = "测试数据：\n订单号：D-9"
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("case_id=CASE-1" in error and ".test_data" in error for error in errors), errors)

    def test_expected_result_mismatch_reports_case_and_field(self):
        root = self.xml_root()
        group_cases, _ = self.group_case_nodes(root, "提交")
        case = group_cases[0]
        steps = next(n for n in verify._topic_children(case) if verify._topic_title(n).startswith("操作步骤：\n"))
        expected = verify._topic_children(steps)[0]
        expected.find(f"{verify.NS}title").text = "预期结果：\n订单丢失"
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("case_id=CASE-0" in error and ".expected_result" in error for error in errors), errors)

    def test_deleted_case_node_is_rejected(self):
        root = self.xml_root()
        sheet = root.find(f"{verify.NS}sheet")
        top = sheet.find(f"{verify.NS}topic")
        module = verify._topic_children(top)[0]
        submodule = verify._topic_children(module)[0]
        submodule.find(f"{verify.NS}children/{verify.NS}topics").remove(verify._topic_children(submodule)[0])
        self.save_xml_root(root)
        self.assertTrue(any("case count" in error for error in verify.compare_xmind(self.json_path, self.xmind_path)))

    def test_blank_optional_node_is_rejected(self):
        root = self.xml_root()
        group_cases, _ = self.group_case_nodes(root, "提交")
        case = group_cases[0]
        container = ET.Element(f"{verify.NS}topic")
        title = ET.SubElement(container, f"{verify.NS}title")
        title.text = "前置条件：\n"
        case_container = case.find(f"{verify.NS}children/{verify.NS}topics")
        case_container.insert(0, container)
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("case_id=CASE-0" in error and "preconditions" in error for error in errors), errors)

    def test_priority_marker_mismatch_is_rejected(self):
        root = self.xml_root()
        group_cases, _ = self.group_case_nodes(root, "提交")
        case = group_cases[1]
        case.find(f"{verify.NS}marker-refs/{verify.NS}marker-ref").set("marker-id", "priority-2")
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("case_id=CASE-1" in error and ".priority" in error for error in errors), errors)

    def test_case_in_wrong_submodule_is_rejected(self):
        root = self.xml_root()
        top = root.find(f"{verify.NS}sheet/{verify.NS}topic")
        module = verify._topic_children(top)[0]
        submodules = verify._topic_children(module)
        submit = next(node for node in submodules if verify._topic_title(node) == "提交")
        cancel = next(node for node in submodules if verify._topic_title(node) == "取消")
        case = verify._topic_children(submit)[0]
        submit.find(f"{verify.NS}children/{verify.NS}topics").remove(case)
        cancel.find(f"{verify.NS}children/{verify.NS}topics").append(case)
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("submodule['取消']/case count" in error for error in errors), errors)

    def test_duplicate_title_reordering_is_not_hidden(self):
        root = self.xml_root()
        top = root.find(f"{verify.NS}sheet/{verify.NS}topic")
        module = verify._topic_children(top)[0]
        submit = next(node for node in verify._topic_children(module) if verify._topic_title(node) == "提交")
        nodes = verify._topic_children(submit)
        container = submit.find(f"{verify.NS}children/{verify.NS}topics")
        container.remove(nodes[0])
        container.remove(nodes[1])
        container.insert(0, nodes[1])
        container.insert(1, nodes[0])
        self.save_xml_root(root)
        errors = verify.compare_xmind(self.json_path, self.xmind_path)
        self.assertTrue(any("case_id=CASE-0" in error and ".test_data" in error for error in errors), errors)


class TestRepairCycle(unittest.TestCase):
    def test_issue_details_skips_summary_and_reads_owner_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "review.md"
            report.write_text(
                "本次接受项 RV-S3-001 需按要求重开。\n\n"
                "- [S3] [accepted] RV-S3-001 CASE-1：测试数据包含无关配置。\n"
                "  - **owner**: generate\n\n"
                "- [S2] [open] RV-S2-002 CASE-2：另一个问题。\n"
                "  - **owner**: review\n",
                encoding="utf-8",
            )
            self.assertEqual(verify._issue_details(report, "RV-S3-001"), ("accepted", "S3", "generate"))

    def test_issue_details_rejects_summary_without_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "review.md"
            report.write_text("本次接受项 RV-S3-001 需按要求重开。\n", encoding="utf-8")
            self.assertEqual(verify._issue_details(report, "RV-S3-001"), (None, None, None))

    def test_issue_details_does_not_read_owner_from_next_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "review.md"
            report.write_text(
                "- [S3] [open] RV-S3-001 CASE-1：示例问题。\n"
                "- [S2] [open] RV-S2-002 CASE-2：另一个问题。\n"
                "  - **owner**: review\n",
                encoding="utf-8",
            )
            self.assertEqual(verify._issue_details(report, "RV-S3-001"), ("open", "S3", None))

    def test_reopen_repair_resolve_and_hash_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue_id = "RV-S3-001"
            before_path = root / "before.json"
            after_path = root / "after.json"
            testpoints_path = root / "testpoints.md"
            accepted_path = root / "accepted.md"
            reopened_path = root / "reopened.md"
            post_generate_path = root / "post-generate.md"
            final_path = root / "review.md"
            base = {
                "schema_version": 2,
                "_context": {"review_repairs": []},
                "testcases": [
                    {"id": "CASE-1", "test_data": "格式：文本；颜色：蓝", "expected_result": "显示文件名与记录数"},
                    {"id": "CASE-2", "test_data": "格式：文本", "expected_result": "对话框关闭"},
                ],
            }
            before_path.write_text(json.dumps(base), encoding="utf-8")
            testpoints_path.write_text("# synthetic TP\n", encoding="utf-8")
            final = json.loads(json.dumps(base))
            final["testcases"][0]["test_data"] = "格式：文本"
            final["_context"]["review_repairs"] = [{"issue_id": issue_id, "changed_case_ids": ["CASE-1"], "summary": "删去无关颜色配置"}]
            after_path.write_text(json.dumps(final), encoding="utf-8")
            old_hash = hashlib.sha256(before_path.read_bytes()).hexdigest()
            new_hash = hashlib.sha256(after_path.read_bytes()).hexdigest()
            testpoints_hash = hashlib.sha256(testpoints_path.read_bytes()).hexdigest()

            def report(status, digest, gate_status):
                gate = {
                    "status": gate_status,
                    "s1_unresolved_count": 0,
                    "s1_issue_ids": [],
                    "judgment_unresolved_count": 0,
                    "judgment_issue_ids": [],
                    "description_unresolved_count": 0 if gate_status == "pass" else 1,
                    "description_issue_ids": [] if gate_status == "pass" else [issue_id],
                }
                context = {"review_gate": gate, "reviewed_artifacts": {"testcases_sha256": digest, "testpoints_sha256": testpoints_hash}}
                return f"- [S3] [{status}] {issue_id} CASE-1：示例问题。owner=generate\n\n<!-- testspec-context\n{json.dumps(context)}\n-->"

            stage = report("open", old_hash, "blocked")
            accepted_path.write_text(report("accepted", old_hash, "blocked"), encoding="utf-8")
            reopened_path.write_text(stage, encoding="utf-8")
            post_generate_path.write_text(stage, encoding="utf-8")
            final_path.write_text(report("resolved", new_hash, "pass"), encoding="utf-8")
            errors = verify.validate_repair_cycle(
                accepted_path, before_path, after_path, testpoints_path, reopened_path, post_generate_path, final_path,
                issue_id, "CASE-1", "test_data", "格式：文本",
            )
            self.assertEqual(errors, [])
            result = subprocess.run([
                sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "repair-cycle",
                "--accepted-report", str(accepted_path), "--before", str(before_path), "--after", str(after_path),
                "--testpoints", str(testpoints_path),
                "--reopened-report", str(reopened_path), "--post-generate-report", str(post_generate_path),
                "--final-report", str(final_path), "--issue-id", issue_id, "--case-id", "CASE-1",
                "--field", "test_data", "--contains", "格式：文本",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invalid_pass = report("resolved", new_hash, "pass").replace(
                '"s1_unresolved_count": 0, "s1_issue_ids": []',
                '"s1_unresolved_count": 1, "s1_issue_ids": ["RV-S1-009"]',
            )
            final_path.write_text(invalid_pass, encoding="utf-8")
            errors = verify.validate_repair_cycle(
                accepted_path, before_path, after_path, testpoints_path, reopened_path, post_generate_path, final_path,
                issue_id, "CASE-1", "test_data", "格式：文本",
            )
            self.assertTrue(any("Gate pass requires zero unresolved S1" in error for error in errors), errors)
            missing_judgment = report("resolved", new_hash, "pass").replace('"judgment_unresolved_count": 0, "judgment_issue_ids": [], ', "")
            final_path.write_text(missing_judgment, encoding="utf-8")
            errors = verify.validate_repair_cycle(
                accepted_path, before_path, after_path, testpoints_path, reopened_path, post_generate_path, final_path,
                issue_id, "CASE-1", "test_data", "格式：文本",
            )
            self.assertTrue(any("Gate issue counts must match" in error for error in errors), errors)
            final_path.write_text(report("resolved", new_hash, "pass").replace("owner=generate", "owner=review"), encoding="utf-8")
            errors = verify.validate_repair_cycle(
                accepted_path, before_path, after_path, testpoints_path, reopened_path, post_generate_path, final_path,
                issue_id, "CASE-1", "test_data", "格式：文本",
            )
            self.assertTrue(any("severity and owner" in error for error in errors), errors)
            final_path.write_text(report("resolved", new_hash, "pass"), encoding="utf-8")
            testpoints_path.write_text("# changed synthetic TP\n", encoding="utf-8")
            errors = verify.validate_repair_cycle(
                accepted_path, before_path, after_path, testpoints_path, reopened_path, post_generate_path, final_path,
                issue_id, "CASE-1", "test_data", "格式：文本",
            )
            self.assertTrue(any("testpoints hash does not match" in error for error in errors), errors)

    def test_generate_gate_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = root / "before.json"
            after = root / "after.json"
            accepted = root / "accepted.md"
            testpoints = root / "points.md"
            reopened = root / "reopened.md"
            post = root / "post.md"
            final = root / "final.md"
            data = {"_context": {"review_repairs": []}, "testcases": [{"id": "CASE-1", "test_data": "no", "x": 1}]}
            before.write_text(json.dumps(data), encoding="utf-8")
            testpoints.write_text("# TP\n", encoding="utf-8")
            changed = json.loads(json.dumps(data))
            changed["testcases"][0]["test_data"] = "yes"
            changed["_context"]["review_repairs"] = [{"issue_id": "RV-S3-001", "changed_case_ids": ["CASE-1"]}]
            after.write_text(json.dumps(changed), encoding="utf-8")
            old_hash = hashlib.sha256(before.read_bytes()).hexdigest()
            new_hash = hashlib.sha256(after.read_bytes()).hexdigest()
            points_hash = hashlib.sha256(testpoints.read_bytes()).hexdigest()
            accepted.write_text(f'- [S3] [accepted] RV-S3-001 CASE-1 owner=generate\n<!-- testspec-context\n{{"review_gate":{{"status":"blocked","description_unresolved_count":1,"description_issue_ids":["RV-S3-001"]}},"reviewed_artifacts":{{"testcases_sha256":"{old_hash}","testpoints_sha256":"{points_hash}"}}}}\n-->')
            opener = f'- [S3] [open] RV-S3-001 CASE-1 owner=generate\n<!-- testspec-context\n{{"review_gate":{{"status":"blocked","description_unresolved_count":1,"description_issue_ids":["RV-S3-001"]}},"reviewed_artifacts":{{"testcases_sha256":"{old_hash}","testpoints_sha256":"{points_hash}"}}}}\n-->'
            reopened.write_text(opener, encoding="utf-8")
            post.write_text(opener.replace('"blocked"', '"pass"'), encoding="utf-8")
            final.write_text(f'- [S3] [resolved] RV-S3-001 CASE-1 owner=generate\n<!-- testspec-context\n{{"review_gate":{{"status":"pass","s1_unresolved_count":0,"s1_issue_ids":[],"description_unresolved_count":0,"description_issue_ids":[]}},"reviewed_artifacts":{{"testcases_sha256":"{new_hash}","testpoints_sha256":"{points_hash}"}}}}\n-->')
            errors = verify.validate_repair_cycle(accepted, before, after, testpoints, reopened, post, final, "RV-S3-001", "CASE-1", "test_data", "yes")
            self.assertTrue(any("changed the reopened Review report or Gate" in error for error in errors), errors)



class TestReviewExecution(unittest.TestCase):
    SOP = """## 评审执行记录
**评审状态**: 已完成
**执行方式**: 同一模型单次评审
**判定依据及限制**: requirements.md REQ-1；无原始 PRD，未做原文追溯
**机器检查**: validate_testcases.py PASS
## BDD 场景评审
**BDD评审状态**: 已完成
**评审结论**: 2 个场景，RV-S2-001 指出 ERR 场景缺少库存不变断言
"""

    STANDALONE = """## 评审发现
**评审状态**: 已完成
**执行方式**: 同一模型单次评审
**判定依据及限制**: PRD REQ-1；完整 2 条用例
**已检查内容**: 覆盖、拒绝路径和可观察预期
**发现数**: 1
**评审结论**: CASE-1 缺少可观察预期
### GR-001: High
**定位**: CASE-1.expected_result
**依据**: REQ-1 要求拒绝后原名称保持
**问题**: 原文只写成功
**影响**: 无法判断原名称是否保持
**建议**: 明确列表仍显示原名称
### 执行摘要
- 材料范围：2 条用例
"""

    def test_single_pass_sop_record_is_accepted(self):
        self.assertEqual(verify.validate_review_execution(self.SOP), [])

    def test_missing_or_invalid_state_is_rejected(self):
        self.assertTrue(verify.validate_review_execution(self.SOP.replace("**评审状态**: 已完成\n", "")))
        self.assertTrue(verify.validate_review_execution(self.SOP.replace("**评审状态**: 已完成", "**评审状态**: 进行中")))

    def test_placeholder_basis_is_rejected(self):
        text = self.SOP.replace("requirements.md REQ-1；无原始 PRD，未做原文追溯", "<实际读取的需求>")
        self.assertTrue(verify.validate_review_execution(text))

    def test_incomplete_requires_reason(self):
        text = self.SOP.replace("**评审状态**: 已完成", "**评审状态**: 未完成")
        self.assertTrue(verify.validate_review_execution(text))
        self.assertEqual(verify.validate_review_execution(text + "**未完成原因**: 缺少伴生 BDD，已退回 testcase-generate\n"), [])

    def test_incomplete_bdd_cannot_claim_complete_review(self):
        text = self.SOP.replace("**BDD评审状态**: 已完成", "**BDD评审状态**: 未完成")
        self.assertTrue(any("BDD" in error for error in verify.validate_review_execution(text)))

    def test_completion_states_allow_factual_explanations(self):
        text = self.SOP.replace("**评审状态**: 已完成", "**评审状态**: 已完成（依据 requirements.md 逐条核对）")
        self.assertEqual(verify.validate_review_execution(text), [])

    def test_empty_value_cannot_consume_following_label(self):
        text = re.sub(r"^\*\*判定依据及限制\*\*:.*$", "**判定依据及限制**:", self.SOP, flags=re.M)
        self.assertTrue(verify.validate_review_execution(text))

    def test_standalone_finding_is_accepted(self):
        self.assertEqual(verify.validate_review_execution(self.STANDALONE), [])

    def test_standalone_missing_detail_is_rejected(self):
        for label in ("定位", "依据", "问题", "影响", "建议"):
            with self.subTest(label=label):
                text = re.sub(rf"^\*\*{label}\*\*:.*\n", "", self.STANDALONE, flags=re.M)
                self.assertTrue(verify.validate_review_execution(text))

    def test_standalone_count_severity_and_duplicates_are_checked(self):
        self.assertTrue(verify.validate_review_execution(self.STANDALONE.replace("**发现数**: 1", "**发现数**: 2")))
        self.assertTrue(verify.validate_review_execution(self.STANDALONE.replace("### GR-001: High", "### GR-001: S1")))
        duplicate = self.STANDALONE.replace("### 执行摘要", "### GR-001: Low\n**定位**: CASE-2\n**依据**: REQ-1\n**问题**: 措辞\n**影响**: 低\n**建议**: 改写\n### 执行摘要")
        self.assertTrue(verify.validate_review_execution(duplicate.replace("**发现数**: 1", "**发现数**: 2")))

    def test_zero_findings_require_explicit_conclusion(self):
        start = self.STANDALONE.index("### GR-001:")
        end = self.STANDALONE.index("### 执行摘要")
        zero = (self.STANDALONE[:start] + self.STANDALONE[end:]).replace("**发现数**: 1", "**发现数**: 0")
        self.assertTrue(verify.validate_review_execution(zero))
        self.assertEqual(verify.validate_review_execution(zero.replace("CASE-1 缺少可观察预期", "在已核对范围内未发现实质性缺陷")), [])

    def test_feedback_alias_matches_execution_check(self):
        self.assertEqual(verify.validate_general_feedback(self.SOP), verify.validate_review_execution(self.SOP))
        self.assertTrue(verify.validate_general_feedback("### 结论总览矩阵\nR1-R6 H1-H8"))


if __name__ == "__main__":
    unittest.main()
