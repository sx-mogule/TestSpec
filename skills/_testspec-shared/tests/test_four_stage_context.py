import hashlib
import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_context_chain.py"
spec = spec_from_file_location("validate_context_chain", SCRIPT)
chain = module_from_spec(spec)
spec.loader.exec_module(chain)


BDD_TEXT = "Feature: 订单提交\n  Scenario: 创建待支付订单\n    Given 商品可购买\n    When 用户提交订单\n    Then 新订单状态为待支付\n"
BDD_REPORT = """# Fixture

## BDD 场景评审

**BDD评审状态**: 已完成
**评审文件**: artifacts/synthetic_features.feature
**已检查内容**: 核对创建订单场景的 Given/When/Then、单一触发事件、业务语言及待支付状态 Oracle。
**评审结论**: 场景与合成需求一致，未发现实质性缺陷。
"""


def write_markdown(path, context, body=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        body = BDD_REPORT if path.name == "review-report.md" else "# Fixture"
    path.write_text(body + "\n\n<!-- testspec-context\n" + json.dumps(context, ensure_ascii=False) + "\n-->\n", encoding="utf-8")


class TestFourStageContext(unittest.TestCase):
    def make_change(self, root):
        revision = {"version": 1, "summary": "订单提交", "updated_by_skill": "prd-analysis"}

        def context(skill, stale, **extra):
            return {
                "source_skill": skill,
                "source_revision": revision,
                "blocking_open_questions": [],
                "dynamic_followups": [],
                "material_quality": "high",
                "stale_downstream_artifacts": stale,
                **extra,
            }

        write_markdown(root / "requirements.md", context("prd-analysis", ["requirements-analysis.md", "specs/testpoints.md", "artifacts/testcases.json", "review-report.md"]))
        write_markdown(root / "requirements-analysis.md", context("prd-analysis", ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"], next_skill="test-points"))
        write_markdown(root / "specs/testpoints.md", context("test-points", ["artifacts/testcases.json", "review-report.md"], next_skill="testcase-generate"))
        generated = context("testcase-generate", ["review-report.md"], next_skill="testcase-review")
        (root / "artifacts").mkdir()
        (root / "artifacts/testcases.json").write_text(json.dumps({"schema_version": 2, "_context": generated, "testcases": []}), encoding="utf-8")
        (root / "artifacts/synthetic_features.feature").write_text(BDD_TEXT, encoding="utf-8")
        reviewed = context(
            "testcase-review", [], bdd_review={"status": "complete"},
            reviewed_artifacts={
                "testcases_sha256": hashlib.sha256((root / "artifacts/testcases.json").read_bytes()).hexdigest(),
                "testpoints_sha256": hashlib.sha256((root / "specs/testpoints.md").read_bytes()).hexdigest(),
                "bdd_features_sha256": {
                    "artifacts/synthetic_features.feature": hashlib.sha256(BDD_TEXT.encode()).hexdigest(),
                },
            }, review_gate={
                "status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": [],
                "description_unresolved_count": 0, "description_issue_ids": [],
            },
        )
        write_markdown(root / "review-report.md", reviewed)
        return reviewed

    def test_canonical_content_drift_invalidates_analysis_at_same_revision(self):
        for filename in ("requirements.md", "proposal.md"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_change(root)
                canonical = root / filename
                (root / "requirements.md").rename(canonical)
                analysis = root / "requirements-analysis.md"
                context = chain.load_context(analysis)
                context["canonical_source_sha256"] = hashlib.sha256(canonical.read_bytes()).hexdigest()
                write_markdown(analysis, context)
                self.assertEqual(chain.validate(root, "review", 1), [])

                old_text = canonical.read_text(encoding="utf-8")
                canonical.write_text(old_text.replace("# Fixture", "# 修改订单状态验收规则"), encoding="utf-8")
                for stage in ("analysis", "review"):
                    errors = chain.validate(root, stage, 1)
                    self.assertTrue(
                        any(f"{filename} content differs from the analyzed canonical source" in error for error in errors),
                        errors,
                    )

    def test_invalid_canonical_source_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            analysis = root / "requirements-analysis.md"
            context = chain.load_context(analysis)
            context["canonical_source_sha256"] = "placeholder"
            write_markdown(analysis, context)
            self.assertIn("analysis: invalid canonical_source_sha256; rerun prd-analysis",
                          chain.validate(root, "analysis", 1))

    def test_review_is_terminal_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            self.assertEqual(chain.validate(root, "review", 1), [])
            self.assertEqual(tuple(chain.STAGES), ("analysis", "points", "generate", "review"))

    def test_new_review_source_and_legacy_reports_are_both_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            self.assertEqual(chain.validate(root, "review", 1), [])
            reviewed["source_skill"] = "testcase-reviewer"
            write_markdown(root / "review-report.md", reviewed)
            self.assertEqual(chain.validate(root, "review", 1), [])
            reviewed["source_skill"] = "unrelated-skill"
            write_markdown(root / "review-report.md", reviewed)
            self.assertTrue(any("source_skill" in error for error in chain.validate(root, "review", 1)))

    def test_review_cannot_point_to_removed_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            reviewed["next_skill"] = "testcase" + "-merge"
            write_markdown(root / "review-report.md", reviewed)
            self.assertIn("review: terminal stage must omit next_skill", chain.validate(root, "review", 1))

    def test_passing_gate_requires_no_s1(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            reviewed["review_gate"]["s1_unresolved_count"] = 1
            write_markdown(root / "review-report.md", reviewed)
            self.assertIn("review: pass requires zero unresolved S1 and empty s1_issue_ids", chain.validate(root, "review", 1))

    def validate_gate(self, **changes):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            reviewed["review_gate"].update(changes)
            write_markdown(root / "review-report.md", reviewed)
            return chain.validate(root, "review", 1)

    def test_description_s3_issue_blocks_pass_without_becoming_s1(self):
        errors = self.validate_gate(
            description_unresolved_count=1, description_issue_ids=["RV-S3-001"],
        )
        self.assertIn(
            "review: pass requires zero unresolved description issues and empty description_issue_ids", errors,
        )
        self.assertNotIn("review: pass requires zero unresolved S1 and empty s1_issue_ids", errors)

    def test_blocked_description_report_is_a_consistent_chain(self):
        errors = self.validate_gate(
            status="blocked", description_unresolved_count=1, description_issue_ids=["RV-S3-001"],
        )
        self.assertEqual(errors, [])

    def test_old_or_partial_description_gate_requires_rereview(self):
        for fields in (
            ("description_unresolved_count",),
            ("description_issue_ids",),
            ("description_unresolved_count", "description_issue_ids"),
        ):
            for status in ("pass", "blocked"):
                with self.subTest(fields=fields, status=status), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    reviewed = self.make_change(root)
                    reviewed["review_gate"]["status"] = status
                    for field in fields:
                        del reviewed["review_gate"][field]
                    write_markdown(root / "review-report.md", reviewed)
                    errors = chain.validate(root, "review", 1)
                    self.assertTrue(any("missing four-field description gate fields" in error and "rerun testcase-review" in error for error in errors), errors)

    def test_description_count_rejects_invalid_values(self):
        for count in (True, False, -1, 0.0, 1.0, "0", None, []):
            with self.subTest(count=count):
                self.assertIn(
                    "review: description_unresolved_count must be a nonnegative integer",
                    self.validate_gate(status="blocked", description_unresolved_count=count),
                )

    def test_description_ids_reject_invalid_values(self):
        for issue_ids in ("RV-S3-001", None, {}, [1], [""], [" \t"], [[]], ["RV-S3-001", "RV-S3-001"]):
            with self.subTest(issue_ids=issue_ids):
                self.assertIn(
                    "review: description_issue_ids must be an array of unique nonblank strings",
                    self.validate_gate(status="blocked", description_issue_ids=issue_ids),
                )

    def test_description_count_must_match_ids_even_when_blocked(self):
        for count, issue_ids in ((1, []), (0, ["RV-S3-001"]), (2, ["RV-S3-001"])):
            with self.subTest(count=count, issue_ids=issue_ids):
                self.assertIn(
                    "review: description_unresolved_count differs from description_issue_ids length",
                    self.validate_gate(status="blocked", description_unresolved_count=count, description_issue_ids=issue_ids),
                )

    def test_pre_review_stage_does_not_require_description_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            (root / "review-report.md").unlink()
            for through in ("analysis", "points", "generate"):
                with self.subTest(through=through):
                    self.assertEqual(chain.validate(root, through, 1), [])

    def test_generation_requires_bdd_but_upstream_stages_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            (root / "artifacts/synthetic_features.feature").unlink()
            for through in ("analysis", "points"):
                self.assertEqual(chain.validate(root, through, 1), [])
            for through in ("generate", "review"):
                self.assertIn("generate: missing artifacts/*_features.feature", chain.validate(root, through, 1))

    def test_generation_rejects_empty_or_non_utf8_bdd(self):
        for content in (b"", b" \n\t", b"\xff"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_change(root)
                (root / "artifacts/synthetic_features.feature").write_bytes(content)
                self.assertTrue(any("BDD feature" in error for error in chain.validate(root, "generate", 1)))

    def test_unreviewed_bdd_cannot_pass_with_zero_gate_counts(self):
        for record in (None, {}, {"status": "incomplete"}):
            with self.subTest(record=record), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reviewed = self.make_change(root)
                reviewed["bdd_review"] = record
                write_markdown(root / "review-report.md", reviewed)
                self.assertTrue(any("BDD review is incomplete" in error for error in chain.validate(root, "review", 1)))

    def test_bdd_review_requires_visible_scope_checks_and_conclusion(self):
        bad_bodies = ["# No BDD review", BDD_REPORT + BDD_REPORT]
        for label in ("评审文件", "已检查内容", "评审结论"):
            bad_bodies.append("\n".join(line for line in BDD_REPORT.splitlines() if not line.startswith(f"**{label}**")))
        bad_bodies += [BDD_REPORT.replace("已完成", "未完成"),
                       BDD_REPORT.replace("artifacts/synthetic_features.feature", "artifacts/other_features.feature")]
        for body in bad_bodies:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reviewed = self.make_change(root)
                write_markdown(root / "review-report.md", reviewed, body)
                self.assertTrue(any("BDD" in error for error in chain.validate(root, "review", 1)))

    def test_legacy_report_without_bdd_fingerprint_requires_rereview(self):
        for hashes in (None, {}, [], {"artifacts/synthetic_features.feature": "placeholder"}):
            with self.subTest(hashes=hashes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reviewed = self.make_change(root)
                reviewed["reviewed_artifacts"]["bdd_features_sha256"] = hashes
                write_markdown(root / "review-report.md", reviewed)
                self.assertTrue(any("bdd_features_sha256" in error for error in chain.validate(root, "review", 1)))

    def test_json_and_testpoint_content_changes_invalidate_review(self):
        for relative_path, changed in (
            ("artifacts/testcases.json", lambda text: text.replace('"testcases": []', '"testcases": [{"expected_result": "状态仍为待支付"}]')),
            ("specs/testpoints.md", lambda text: text.replace("# Fixture", "# 新增一条验收规则")),
        ):
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_change(root)
                path = root / relative_path
                before = path.read_text(encoding="utf-8")
                after = changed(before)
                self.assertNotEqual(before, after)
                path.write_text(after, encoding="utf-8")
                self.assertEqual(chain.validate(root, "generate", 1), [])
                errors = chain.validate(root, "review", 1)
                self.assertTrue(any(f"{relative_path} hash differs" in error for error in errors), errors)

    def test_missing_or_invalid_json_and_testpoint_review_hashes_require_rereview(self):
        for field in ("testcases_sha256", "testpoints_sha256"):
            for digest in (None, "placeholder"):
                with self.subTest(field=field, digest=digest), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    reviewed = self.make_change(root)
                    if digest is None:
                        del reviewed["reviewed_artifacts"][field]
                    else:
                        reviewed["reviewed_artifacts"][field] = digest
                    write_markdown(root / "review-report.md", reviewed)
                    errors = chain.validate(root, "review", 1)
                    self.assertTrue(any(f"missing or invalid reviewed_artifacts.{field}" in error for error in errors), errors)

    def test_review_hash_follows_the_selected_json_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            current = root / "artifacts/testcases.json"
            fallback = root / "testcases.json"
            current.rename(fallback)
            self.assertEqual(chain.validate(root, "review", 1), [])

            current.write_bytes(fallback.read_bytes())
            fallback.write_text("invalid fallback content", encoding="utf-8")
            self.assertEqual(chain.validate(root, "review", 1), [])

    def test_bdd_edits_additions_deletions_and_renames_invalidate_review(self):
        for action in ("edit", "add", "delete", "rename"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_change(root)
                feature = root / "artifacts/synthetic_features.feature"
                if action == "edit":
                    feature.write_text(BDD_TEXT.replace("待支付", "已支付"), encoding="utf-8")
                elif action == "add":
                    feature.with_name("extra_features.feature").write_text(BDD_TEXT, encoding="utf-8")
                elif action == "delete":
                    feature.unlink()
                else:
                    feature.rename(feature.with_name("renamed_features.feature"))
                before = (root / "review-report.md").read_bytes()
                self.assertTrue(any("BDD files or hashes differ" in error for error in chain.validate(root, "review", 1)))
                self.assertEqual((root / "review-report.md").read_bytes(), before)

    def test_rereview_can_record_all_current_bdd_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            (root / "artifacts/extra_features.feature").write_text(BDD_TEXT, encoding="utf-8")
            hashes, errors = chain.bdd_artifacts(root)
            self.assertEqual(errors, [])
            reviewed["reviewed_artifacts"]["bdd_features_sha256"] = hashes
            body = BDD_REPORT.replace("artifacts/synthetic_features.feature",
                                      "artifacts/synthetic_features.feature、artifacts/extra_features.feature")
            write_markdown(root / "review-report.md", reviewed, body)
            self.assertEqual(chain.validate(root, "review", 1), [])

    def test_generated_bdd_must_not_remain_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            generated_path = root / "artifacts/testcases.json"
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            generated["_context"]["stale_downstream_artifacts"].append("artifacts/synthetic_features.feature")
            generated_path.write_text(json.dumps(generated), encoding="utf-8")
            self.assertIn("generate: propagated stale list still contains its BDD artifact", chain.validate(root, "generate", 1))

    def test_review_preserves_design_methods_when_present(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            generated_path = root / "artifacts/testcases.json"
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            generated["_context"]["design_methods"] = ["基于属性的测试"]
            generated_path.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")
            reviewed["design_methods"] = ["变形测试"]
            reviewed["reviewed_artifacts"]["testcases_sha256"] = hashlib.sha256(generated_path.read_bytes()).hexdigest()
            write_markdown(root / "review-report.md", reviewed)
            self.assertIn("review: design_methods differs from generated cases", chain.validate(root, "review", 1))

    def test_review_method_order_does_not_change_method_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            generated_path = root / "artifacts/testcases.json"
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            generated["_context"]["design_methods"] = ["基于属性的测试", "变形测试"]
            generated_path.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")
            reviewed["design_methods"] = ["变形测试", "基于属性的测试"]
            reviewed["reviewed_artifacts"]["testcases_sha256"] = hashlib.sha256(generated_path.read_bytes()).hexdigest()
            write_markdown(root / "review-report.md", reviewed)
            self.assertEqual(chain.validate(root, "review", 1), [])

    def test_review_method_aliases_match_in_both_directions_without_rewriting(self):
        canonical = ["等价类", "边界值", "判定表", "流程分析", "状态迁移", "错误推断",
                     "正交实验", "因果图", "配对组合", "基于属性的测试", "变形测试", "语法规则分析"]
        aliases = ["等价类划分", "边界值分析", "决策表", "业务流程分析", "状态转换", "错误推测",
                   "正交试验设计", "因果图法", "两两组合", "属性测试", "蜕变测试", "语法分析"]
        for generated_names, reviewed_names in ((aliases, canonical), (canonical, aliases)):
            with self.subTest(generated_names=generated_names), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reviewed = self.make_change(root)
                generated_path = root / "artifacts/testcases.json"
                generated = json.loads(generated_path.read_text(encoding="utf-8"))
                generated["_context"]["design_methods"] = generated_names
                generated_path.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")
                reviewed["design_methods"] = reviewed_names
                reviewed["reviewed_artifacts"]["testcases_sha256"] = hashlib.sha256(generated_path.read_bytes()).hexdigest()
                reviewed_path = root / "review-report.md"
                write_markdown(reviewed_path, reviewed)
                before = [path.read_bytes() for path in (generated_path, reviewed_path)]
                self.assertEqual(chain.validate(root, "review", 1), [])
                self.assertEqual([path.read_bytes() for path in (generated_path, reviewed_path)], before)

    def test_alias_normalization_does_not_hide_a_different_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            generated_path = root / "artifacts/testcases.json"
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            generated["_context"]["design_methods"] = ["等价类划分"]
            generated_path.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")
            reviewed["design_methods"] = ["边界值分析"]
            reviewed["reviewed_artifacts"]["testcases_sha256"] = hashlib.sha256(generated_path.read_bytes()).hexdigest()
            write_markdown(root / "review-report.md", reviewed)
            self.assertIn("review: design_methods differs from generated cases", chain.validate(root, "review", 1))

    def test_unclosed_marker_before_valid_context_blocks_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            path = root / "requirements-analysis.md"
            path.write_text("<!-- testspec-context\n" + path.read_text(), encoding="utf-8")
            self.assertTrue(any("exactly one" in error for error in chain.validate(root, "review", 1)))

    def test_two_complete_contexts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.md"
            write_markdown(path, {"source_skill": "test-points"})
            path.write_text(path.read_text() * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                chain.markdown_context(path)

    def test_unclosed_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.md"
            path.write_text('<!-- testspec-context\n{"source_skill":"test-points"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unclosed"):
                chain.markdown_context(path)

    def test_context_must_be_an_object(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.md"
            path.write_text('<!-- testspec-context\n[]\n-->\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                chain.markdown_context(path)

    def test_inline_documentation_does_not_create_a_second_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.md"
            expected = {"source_skill": "test-points"}
            write_markdown(path, expected)
            path.write_text("正文提及 `<!-- testspec-context` 标记。\n" + path.read_text(), encoding="utf-8")
            self.assertEqual(chain.markdown_context(path), expected)


if __name__ == "__main__":
    unittest.main()
