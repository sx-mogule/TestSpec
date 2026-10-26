import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_context_chain.py"
spec = spec_from_file_location("validate_context_chain", SCRIPT)
chain = module_from_spec(spec)
spec.loader.exec_module(chain)


def write_markdown(path, context):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Fixture\n\n<!-- testspec-context\n" + json.dumps(context, ensure_ascii=False) + "\n-->\n", encoding="utf-8")


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
        reviewed = context("testcase-review", [], review_gate={
            "status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": [],
            "description_unresolved_count": 0, "description_issue_ids": [],
        })
        write_markdown(root / "review-report.md", reviewed)
        return reviewed

    def test_review_is_terminal_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_change(root)
            self.assertEqual(chain.validate(root, "review", 1), [])
            self.assertEqual(tuple(chain.STAGES), ("analysis", "points", "generate", "review"))

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

    def test_review_preserves_design_methods_when_present(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = self.make_change(root)
            generated_path = root / "artifacts/testcases.json"
            generated = json.loads(generated_path.read_text(encoding="utf-8"))
            generated["_context"]["design_methods"] = ["基于属性的测试"]
            generated_path.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")
            reviewed["design_methods"] = ["变形测试"]
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
            write_markdown(root / "review-report.md", reviewed)
            self.assertEqual(chain.validate(root, "review", 1), [])

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
