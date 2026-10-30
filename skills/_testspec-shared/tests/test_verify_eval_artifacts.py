import hashlib
import json
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
    def valid_report(self):
        rows = []
        for key in verify.MATRIX_IDS:
            if key == "H8":
                rows.append("| H8 测试价值与亮点 | — | 标杆用例数 0；可复用模式数 0 | 0 |")
            else:
                rows.append(f"| {key} 检查 | pass | 已检查 4 项 | 0 |")
        return "\n".join([
            "### 结论总览矩阵",
            "| 检查项 | 结果 | 关键指标 | 问题数 |",
            "|---|---|---|---|",
            *rows,
            "### H8: 测试价值与亮点识别",
            "**标杆用例数**: 0",
            "**可复用模式数**: 0",
            "**测试策略健康度**: 覆盖完整，风险已记录。",
            "## 整改建议清单",
        ])

    def test_complete_matrix_and_h8_without_pass_fail_is_valid(self):
        report = self.root_report(self.valid_report())
        result = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_eval_artifacts.py"), "review", "--report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_observed_h8_counts_with_parenthetical_evidence_and_health_label_are_valid(self):
        text = self.valid_report()
        text = text.replace(
            "| H8 测试价值与亮点 | — | 标杆用例数 0；可复用模式数 0 | 0 |",
            "| H8 测试价值与亮点 | — | 标杆用例 1；可复用变形测试模式 1 | 0 |",
        )
        text = text.replace("**标杆用例数**: 0", "**标杆用例数**: 1（notice-edit_202610280008）")
        text = text.replace("**可复用模式数**: 0", "**可复用模式数**: 1（固定同一数据集、改变创建顺序、比较结果序列）")
        text = text.replace(
            "**测试策略健康度**: 覆盖完整，风险已记录。",
            "- 策略健康度：用例集覆盖全部测试点，排序用例有清楚的变形断言。",
        )
        self.assertEqual(verify.validate_review_report(text), [])

    def test_h8_count_without_number_is_rejected(self):
        text = self.valid_report().replace("**可复用模式数**: 0", "**可复用模式数**:")
        self.assertTrue(any("可复用模式数" in error for error in verify.validate_review_report(text)))

    def test_h8_missing_health_comment_is_rejected(self):
        text = self.valid_report().replace("**测试策略健康度**: 覆盖完整，风险已记录。\n", "")
        self.assertTrue(any("测试策略健康度" in error for error in verify.validate_review_report(text)))

    def root_report(self, content):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        report = Path(directory.name) / "review-report.md"
        report.write_text(content, encoding="utf-8")
        return report

    def test_missing_h2_is_rejected(self):
        text = self.valid_report().replace("| H2 检查 | pass | 已检查 4 项 | 0 |\n", "")
        self.assertTrue(any("H2: row missing" in error for error in verify.validate_review_report(text)))

    def test_placeholder_count_is_rejected(self):
        text = self.valid_report().replace("| H2 检查 | pass | 已检查 4 项 | 0 |", "| H2 检查 | pass | 已检查 4 项 | <count> |")
        self.assertTrue(any("H2: problem count" in error for error in verify.validate_review_report(text)))

    def test_keyword_only_sections_without_matrix_are_rejected(self):
        text = "R1 R2 R3 R4 R5 R6 H1 H2 H3 H4 H5 H6 H7 H8"
        self.assertTrue(any("matrix" in error for error in verify.validate_review_report(text)))

    def test_finding_checks_dimension_case_severity_and_missing_oracle(self):
        report = "### H3: 意图一致性\n- [S1] [open] RV-S1-002 SYN_CANCEL_002：预期遗漏已取消状态。\n### H4: 前置条件充分性\n"
        self.assertEqual(verify.validate_review_finding(report, "H3", "SYN_CANCEL_002", "S1", "已取消"), [])
        self.assertTrue(verify.validate_review_finding(report, "H3", "SYN_CANCEL_001", "S1", "已取消"))

    def test_review_evidence_requires_case_test_point_and_boundary_values(self):
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


if __name__ == "__main__":
    unittest.main()
