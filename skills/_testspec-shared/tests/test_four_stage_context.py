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
        reviewed = context("testcase-review", [], review_gate={"status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": []})
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


if __name__ == "__main__":
    unittest.main()
