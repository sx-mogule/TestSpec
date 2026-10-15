import copy
import json
import subprocess
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
spec = spec_from_file_location("validate_evals", ROOT / "skills/_testspec-shared/scripts/validate_evals.py")
validator = module_from_spec(spec)
spec.loader.exec_module(validator)


class TestEvalExitStatus(unittest.TestCase):
    def test_validator_rejects_printing_fail_with_success_exit(self):
        source = ROOT / "skills/prd-analysis/evals/evals.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evals.json"
            for script, rejected in [
                ("test -f missing.md || echo FAIL", True),
                ("test -f missing.md || { echo FAIL; exit 1; }", False),
            ]:
                with self.subTest(script=script):
                    edited = copy.deepcopy(data)
                    edited["evals"][0]["assertions"][0]["script"] = script
                    path.write_text(json.dumps(edited), encoding="utf-8")
                    errors = validator.validate_eval_file(path)
                    self.assertEqual(any("masks failure" in error for error in errors), rejected, errors)

    def test_fixed_assertions_return_nonzero_for_failed_conditions(self):
        checked = 0
        for path in validator.EVAL_PATHS:
            data = json.loads(path.read_text(encoding="utf-8"))
            for case in data["evals"]:
                for assertion in case["assertions"]:
                    script = assertion.get("script", "")
                    if "|| { echo FAIL; exit 1; }" not in script:
                        continue
                    with self.subTest(skill=data["skill_name"], case=case["id"], text=assertion["text"]):
                        with tempfile.TemporaryDirectory() as directory:
                            root = Path(directory)
                            # 这两项断言检查不应产生文件，负例需显式创建禁止产物。
                            if "test ! -e testspec/changes/synthetic-notification-rules" in script:
                                forbidden = root / "testspec/changes/synthetic-notification-rules/artifacts/testcases.json"
                                forbidden.parent.mkdir(parents=True)
                                forbidden.write_text("{}", encoding="utf-8")
                            if "test ! -e network-contact.marker" in script:
                                (root / "network-contact.marker").touch()
                            result = subprocess.run(["sh", "-c", script], cwd=root, capture_output=True, text=True, timeout=10)
                            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    checked += 1
        self.assertGreater(checked, 0)

    def test_successful_condition_still_returns_zero(self):
        result = subprocess.run(["sh", "-c", "test -d . && echo PASS || { echo FAIL; exit 1; }"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "PASS")


if __name__ == "__main__":
    unittest.main()
