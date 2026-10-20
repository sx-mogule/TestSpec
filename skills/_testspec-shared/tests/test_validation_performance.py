import hashlib
import itertools
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

from test_case_quality import make_case, validator


def signature(issue):
    return (tuple(sorted(issue["case_ids"])), issue["type"], issue["severity"],
            tuple(issue.get("different_fields", [])), issue.get("title_similarity"), issue.get("steps_similarity"))


def reference_pairs(cases):
    """独立的全对比较基线，用于证明分组和缓存没有改变判定。"""
    issues = []
    for i, j in itertools.combinations(range(len(cases)), 2):
        left, right = map(validator._comparison_fields, (cases[i], cases[j]))
        if not all((left["steps"], left["expected_result"], right["steps"], right["expected_result"])):
            continue
        if (left["module"], left["submodule"]) != (right["module"], right["submodule"]):
            continue
        if left == right:
            issues.append({"case_ids": [cases[i]["id"], cases[j]["id"]], "type": "DUPLICATE", "severity": "warning"})
            continue
        title = validator._simple_similarity(cases[i]["test_name"], cases[j]["test_name"])
        steps = validator._simple_similarity(cases[i]["steps"], cases[j]["steps"])
        if title > 0.8 and steps > validator.SIMILARITY_THRESHOLD:
            issues.append({"case_ids": [cases[i]["id"], cases[j]["id"]], "type": "SIMILAR_CASES", "severity": "info",
                           "different_fields": [key for key in left if left[key] != right[key]],
                           "title_similarity": round(title, 2), "steps_similarity": round(steps, 2)})
    return sorted(map(signature, issues))


class TestDuplicatePerformance(unittest.TestCase):
    def test_empty_required_field_still_returns_fail_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "testcases.json"
            for value in (None, ""):
                source.write_text(json.dumps({"schema_version": 2, "testcases": [make_case(steps=value)]}))
                self.assertEqual(validator.validate(str(source))["status"], "FAIL")

    def test_grouped_results_match_all_pairs_reference(self):
        rng = random.Random(20)
        cases = []
        for i in range(60):
            module = rng.choice(["公告", "通知", "订单"])
            case = make_case(f"CASE-{i}", module=module,
                             test_name=module + "_标题_" + rng.choice(["最短标题允许保存", "最长标题允许保存", "空标题拒绝保存"]),
                             test_data="值：" + rng.choice(["1", "10", "1.5元", "15元", "空字符串", "0"]))
            if i % 9 == 0:
                case["expected_result"] = "1、标题仍为OLD"
            if i % 17 == 0:
                case["steps"] = ""
            cases.append(case)
        self.assertEqual(sorted(map(signature, validator.check_duplicates(cases))), reference_pairs(cases))

    def test_text_processing_grows_with_inputs_not_pairs(self):
        cases = [make_case(f"CASE-{i}", test_data=f"值：{i}") for i in range(100)]
        with patch.object(validator, "_normalize", wraps=validator._normalize) as normalize:
            validator.check_duplicates(cases)
        self.assertLessEqual(normalize.call_count, 2 * len(cases))

    def test_compact_report_keeps_every_pair_and_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cases = [make_case(f"CASE-{i}", test_data=f"值：{i}") for i in range(50)]
            source = path / "testcases.json"
            source.write_text(json.dumps({"schema_version": 2, "testcases": cases}, ensure_ascii=False))
            result = validator.validate(str(source), details_path=str(path / "pairs.jsonl"))
            pairs = [json.loads(line) for line in (path / "pairs.jsonl").read_text().splitlines()]
            self.assertEqual(len(pairs), 1225)
            self.assertEqual(result["summary"]["review_candidate_count"], 1225)
            self.assertEqual(result["summary"]["review_candidate_group_count"], 1)
            self.assertEqual(set(result["review_candidates"][0]["case_ids"]), {case["id"] for case in cases})
            self.assertEqual(sorted(map(signature, pairs)), reference_pairs(cases))
            self.assertEqual(result["duplicate_details"]["sha256"], hashlib.sha256((path / "pairs.jsonl").read_bytes()).hexdigest())
            self.assertLess(len(json.dumps(result)), len(json.dumps(pairs)) // 10)

    def test_connected_group_does_not_invent_missing_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cases = [make_case(f"CASE-{i}", test_name="公告_标题_" + title, test_data=f"值：{i}")
                     for i, title in enumerate(["ij", "ijk", "jk"])]
            groups, details = validator._duplicate_summary(cases, path / "pairs.jsonl")
            edges = {tuple(issue["case_ids"]) for issue in map(json.loads, (path / "pairs.jsonl").read_text().splitlines())}
            self.assertEqual(edges, {("CASE-0", "CASE-1"), ("CASE-1", "CASE-2")})
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["pair_count"], 2)
            self.assertEqual(details["pair_count"], 2)

    def test_exact_duplicate_group_keeps_warning_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cases = [make_case(f"CASE-{i}") for i in range(4)]
            source = path / "testcases.json"
            source.write_text(json.dumps({"schema_version": 2, "testcases": cases}))
            result = validator.validate(str(source), details_path=str(path / "pairs.jsonl"))
            self.assertEqual(result["status"], "WARN")
            self.assertEqual(result["summary"]["warning_count"], 6)
            self.assertEqual(len(result["warnings"]), 1)
            self.assertEqual(result["duplicate_details"]["duplicate_pair_count"], 6)


class TestValidationCache(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.script = self.root / "skills/_testspec-shared/scripts/validate_testcases.py"
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(Path(validator.__file__), self.script)
        self.rule = self.root / "skills/_testspec-shared/references/rules.md"
        self.rule.parent.mkdir(parents=True)
        self.rule.write_text("# 当前规则\n")
        spec = spec_from_file_location("isolated_cache_validator", self.script)
        self.v = module_from_spec(spec)
        spec.loader.exec_module(self.v)
        self.change = self.root / "change"
        self.source = self.change / "artifacts/testcases.json"
        self.source.parent.mkdir(parents=True)
        self.cases = [make_case()]
        self.write_cases()
        self.points = self.change / "specs/testpoints.md"
        self.points.parent.mkdir()
        self.points.write_text("- TP_NOTE_TITLE_001: 标题保存\n")
        self.canonical = self.change / "requirements.md"
        self.canonical.write_text("# 需求\nversion: 1\n标题保存后保留新值。\n")

    def write_cases(self):
        self.source.write_text(json.dumps({"schema_version": 2, "testcases": self.cases}, ensure_ascii=False))

    def report(self, **kwargs):
        return self.v.validate_report(str(self.source), str(self.points), **kwargs)

    def test_second_run_reuses_verified_result(self):
        first = self.report()
        with patch.object(self.v, "validate", side_effect=AssertionError("cache should avoid recomputation")):
            second = self.report()
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual({k: v for k, v in first.items() if k != "cache"}, {k: v for k, v in second.items() if k != "cache"})

    def test_input_content_change_invalidates_cache(self):
        first = self.report()
        self.cases[0]["expected_result"] = "1、操作成功"
        self.write_cases()
        second = self.report()
        self.assertFalse(second["cache"]["hit"])
        self.assertNotEqual(first["cache"]["key"], second["cache"]["key"])
        self.assertEqual(second["status"], "WARN")

    def test_points_change_invalidates_coverage(self):
        self.report()
        self.points.write_text(self.points.read_text() + "- TP_NOTE_TITLE_002: 另一条未覆盖测试点\n")
        result = self.report()
        self.assertFalse(result["cache"]["hit"])
        self.assertEqual(result["status"], "FAIL")

    def test_canonical_change_without_revision_change_invalidates_cache(self):
        first = self.report()
        self.canonical.write_text("# 需求\nversion: 1\n标题保存后显示新标题。\n")
        second = self.report()
        self.assertFalse(second["cache"]["hit"])
        self.assertNotEqual(first["cache"]["key"], second["cache"]["key"])

    def test_analysis_creation_and_change_invalidate_cache(self):
        first = self.report()
        analysis = self.change / "requirements-analysis.md"
        analysis.write_text("# 新分析\n")
        second = self.report()
        analysis.write_text("# 分析已变化\n")
        third = self.report()
        self.assertFalse(second["cache"]["hit"])
        self.assertFalse(third["cache"]["hit"])
        self.assertEqual(len({first["cache"]["key"], second["cache"]["key"], third["cache"]["key"]}), 3)

    def test_rule_and_validator_changes_invalidate_cache(self):
        first = self.report()
        self.rule.write_text("# 规则已更新\n")
        second = self.report()
        self.script.write_text(self.script.read_text() + "\n# 新校验规则版本\n")
        third = self.report()
        self.assertEqual(len({first["cache"]["key"], second["cache"]["key"], third["cache"]["key"]}), 3)

    def test_modified_time_alone_does_not_invalidate_cache(self):
        self.report()
        os.utime(self.source, (1000, 1000))
        self.assertTrue(self.report()["cache"]["hit"])

    def test_missing_or_changed_details_are_rebuilt(self):
        for operation in ("remove", "corrupt"):
            with self.subTest(operation=operation):
                result = self.report()
                details = Path(result["duplicate_details"]["path"])
                if operation == "remove":
                    details.unlink()
                else:
                    details.write_text("incorrect details\n")
                rebuilt = self.report()
                self.assertFalse(rebuilt["cache"]["hit"])
                self.assertEqual(rebuilt["duplicate_details"]["sha256"], hashlib.sha256(details.read_bytes()).hexdigest())

    def test_corrupt_cached_result_is_not_reused(self):
        result = self.report()
        cached = Path(result["duplicate_details"]["path"]).with_name("result.json")
        body = json.loads(cached.read_text())
        body["result"]["status"] = "FAIL"
        cached.write_text(json.dumps(body))
        rebuilt = self.report()
        self.assertFalse(rebuilt["cache"]["hit"])
        self.assertEqual(rebuilt["status"], "PASS")

    def test_force_recheck_does_not_use_cached_result(self):
        self.report()
        with patch.object(self.v, "validate", wraps=self.v.validate) as validate:
            result = self.report(use_cache=False)
        self.assertFalse(result["cache"]["hit"])
        self.assertEqual(validate.call_count, 1)

    def test_check_does_not_change_inputs_or_formal_artifact_set(self):
        before = {p: p.read_bytes() for p in (self.source, self.points, self.canonical)}
        self.report()
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual({p.name for p in self.source.parent.iterdir()}, {"testcases.json"})

    def test_concurrent_checks_leave_complete_cache_and_details(self):
        self.cases = [make_case(f"CASE-{i}", test_data=f"值：{i}") for i in range(20)]
        self.write_cases()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.report(), range(3)))
        self.assertTrue(all(result["status"] == "PASS" for result in results))
        final = self.report()
        self.assertTrue(final["cache"]["hit"])
        self.assertEqual(len(Path(final["duplicate_details"]["path"]).read_text().splitlines()), 190)

    def run_cli(self, *flags):
        result = subprocess.run(
            [sys.executable, "-B", str(self.script), "--input", str(self.source), "--testpoints", str(self.points), *flags],
            capture_output=True, text=True, timeout=20, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        return result.returncode, json.loads(result.stdout)

    def test_cli_keeps_warn_exit_on_cached_result(self):
        self.cases.append(dict(self.cases[0], id="CASE-002"))
        self.write_cases()
        first, _ = self.run_cli()
        second, result = self.run_cli()
        self.assertEqual((first, second), (1, 1))
        self.assertTrue(result["cache"]["hit"])

    def test_full_cli_mode_is_read_only(self):
        code, result = self.run_cli("--full")
        self.assertEqual(code, 0)
        self.assertNotIn("duplicate_details", result)
        self.assertFalse((self.change / ".testspec-cache").exists())

    def test_no_cache_cli_writes_details_but_no_result_cache(self):
        code, result = self.run_cli("--no-cache")
        self.assertEqual(code, 0)
        self.assertFalse(result["cache"]["hit"])
        details = Path(result["duplicate_details"]["path"])
        self.assertTrue(details.exists())
        self.assertFalse(details.with_name("result.json").exists())

    def test_missing_input_does_not_return_stale_cache(self):
        self.report()
        self.source.unlink()
        self.assertEqual(self.report()["status"], "ERROR")

    def test_input_change_during_validation_is_not_cached(self):
        original = self.v.validate
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.canonical.write_text("# 需求在校验时变化\n")
            return result
        with patch.object(self.v, "validate", side_effect=changed):
            result = self.report()
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("发生变化", result["message"])


class TestInputFingerprints(unittest.TestCase):
    def test_changed_and_unchanged_inputs_are_read_only(self):
        script = Path(validator.__file__).with_name("fingerprint_inputs.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            first, second = root / "requirements.md", root / "rules.md"
            first.write_text("version: 1\n旧内容")
            second.write_text("规则")
            def run(*args):
                result = subprocess.run([sys.executable, "-B", str(script), *map(str, args)], capture_output=True, text=True,
                                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            initial = run(first, second)
            previous = root / "previous.json"
            previous.write_text(json.dumps(initial))
            identical = run(first, second, "--previous", previous)
            self.assertEqual(identical["changed"], [])
            self.assertEqual(set(identical["unchanged"]), {str(first), str(second)})
            first.write_text("version: 1\n新内容")
            changed = run(first, "--previous", previous)
            self.assertEqual(changed["changed"], [str(first)])
            self.assertEqual(changed["removed"], [str(second)])
            self.assertEqual(first.read_text(), "version: 1\n新内容")
            self.assertEqual(second.read_text(), "规则")


if __name__ == "__main__":
    unittest.main()
