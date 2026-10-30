from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "LICENSE",
    "agents/openai.yaml",
    "testcase-review/review-workflow.md",
    "testcase-review/references/review-dimensions.md",
    "testcase-review/references/independent-reviewer.md",
    "testcase-review/scripts/prepare_reviewer_input.py",
    "evals/evals.json",
    "assets/bdd-feature-template.feature",
    "references/bdd/quality-rules.md",
    "references/bdd/feature-and-scenario-protocol.md",
    "references/bdd/intake-and-decision-flow.md",
    "references/bdd/review-workflow.md",
    "references/test-cases/review-workflow.md",
    "references/test-cases/test-case-protocol.md",
    "references/test-cases/test-suite-protocol.md",
    "references/test-cases/examples-test-case-quality.md",
    "references/test-cases/examples-review-comments.md",
    "references/test-cases/examples-mini-review-reports.md",
    "references/test-cases/examples-bad-input-artifacts.md",
    "eval/behavior-checklist.md",
    "eval/forward-evals.json",
    "eval/forward-test-matrix.md",
    "eval/trigger-evals.json",
    "examples/bdd/formal-report-request.md",
    "examples/bdd/generation-source.md",
    "examples/bdd/review-input.feature",
    "examples/bdd/review-oracle.md",
    "examples/bdd/review-request.md",
    "examples/bdd/rewrite-request.md",
    "examples/bdd/rewrite-source.feature",
    "examples/bdd/hybrid-source.feature",
]

REQUIRED_SHARED_FILES = [
    "references/output-contracts.md",
    "references/bdd-output-contracts.md",
    "references/bdd-report-rubric.md",
    "templates/review-report-template.md",
    "templates/testcase-review-report-template.md",
    "templates/bdd-review-report-template.md",
]

SKILL_ALLOWED_FIELDS = {"name", "description", "license", "metadata", "allowed-tools"}
SKILL_REQUIRED_FIELDS = {"name", "description"}
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message: str) -> None:
    print(f"FAIL: {message}")


def ok(message: str) -> None:
    print(f"PASS: {message}")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md 必须以 YAML frontmatter 开头")

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter 未正确闭合")

    raw = parts[1]
    result: dict[str, str] = {}

    for line in raw.splitlines():
        if not line or line.startswith(" ") or line.startswith("\t"):
            continue
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"frontmatter 行无效：{line}")
        key, value = stripped.split(":", 1)
        result[key.strip()] = value.strip().strip('"')

    return result


def validate_skill_md(root: Path, errors: list[str]) -> None:
    path = root / "SKILL.md"
    data = parse_frontmatter(path)

    missing = sorted(SKILL_REQUIRED_FIELDS - data.keys())
    if missing:
        errors.append(f"SKILL.md 缺少必需的 frontmatter 字段：{', '.join(missing)}")

    unknown = sorted(set(data) - SKILL_ALLOWED_FIELDS)
    if unknown:
        errors.append(f"SKILL.md 的 frontmatter 含有不受支持的字段：{', '.join(unknown)}")

    name = data.get("name", "")
    if name and not SKILL_NAME_PATTERN.match(name):
        errors.append("SKILL.md 的 name 只能包含小写字母、数字和连字符")
    if len(name) > 64:
        errors.append("SKILL.md 的 name 超过 64 个字符")

    description = data.get("description", "")
    if not description:
        errors.append("SKILL.md 的 description 不能为空")
    if len(description) > 1024:
        errors.append("SKILL.md 的 description 超过 1024 个字符")


def validate_openai_yaml(root: Path, errors: list[str]) -> None:
    text = (root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    required_snippets = [
        "interface:",
        "display_name:",
        "short_description:",
        "default_prompt:",
        "policy:",
        "allow_implicit_invocation:",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f"agents/openai.yaml 缺少 `{snippet}`")


def validate_trigger_evals(root: Path, errors: list[str]) -> None:
    path = root / "eval" / "trigger-evals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"eval/trigger-evals.json 不是有效的 JSON：{exc}")
        return

    if not isinstance(data, list) or not data:
        errors.append("eval/trigger-evals.json 必须包含非空数组")
        return

    seen_queries: set[str] = set()
    has_positive = False
    has_negative = False

    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append(f"第 {idx} 条触发评测不是对象")
            continue
        if not isinstance(item.get("query"), str) or not item["query"].strip():
            errors.append(f"第 {idx} 条触发评测必须包含非空字符串 `query`")
        elif item["query"] in seen_queries:
            errors.append(f"第 {idx} 条触发评测与之前的 query 重复")
        else:
            seen_queries.add(item["query"])
        if not isinstance(item.get("should_trigger"), bool):
            errors.append(f"第 {idx} 条触发评测的 `should_trigger` 必须是布尔值")
        elif item["should_trigger"]:
            has_positive = True
        else:
            has_negative = True

    if not has_positive:
        errors.append("eval/trigger-evals.json 必须至少包含一条正向触发用例")
    if not has_negative:
        errors.append("eval/trigger-evals.json 必须至少包含一条负向触发用例")


def validate_forward_evals(root: Path, errors: list[str]) -> None:
    path = root / "eval" / "forward-evals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"eval/forward-evals.json 不是有效的 JSON：{exc}")
        return

    if not isinstance(data, dict):
        errors.append("eval/forward-evals.json 必须包含 JSON 对象")
        return

    skill_name = data.get("skill_name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        errors.append("eval/forward-evals.json 必须包含非空字符串 `skill_name`")

    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append("eval/forward-evals.json 必须包含非空的 `evals` 数组")
        return

    seen_ids: set[int] = set()
    for idx, item in enumerate(evals, start=1):
        if not isinstance(item, dict):
            errors.append(f"第 {idx} 条前向评测不是对象")
            continue

        eval_id = item.get("id")
        if not isinstance(eval_id, int):
            errors.append(f"第 {idx} 条前向评测必须包含整数 `id`")
        elif eval_id in seen_ids:
            errors.append(f"第 {idx} 条前向评测的 id {eval_id} 与其他评测重复")
        else:
            seen_ids.add(eval_id)

        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            errors.append(f"第 {idx} 条前向评测必须包含非空字符串 `prompt`")

        if not isinstance(item.get("expected_output"), str) or not item["expected_output"].strip():
            errors.append(f"第 {idx} 条前向评测必须包含非空字符串 `expected_output`")

        files = item.get("files")
        if not isinstance(files, list):
            errors.append(f"第 {idx} 条前向评测必须包含 `files` 数组")
        else:
            for file_idx, file_path in enumerate(files, start=1):
                if not isinstance(file_path, str) or not file_path.strip():
                    errors.append(
                        f"第 {idx} 条前向评测的第 {file_idx} 个文件条目必须为非空字符串"
                    )
                    continue
                if not (root / file_path).exists():
                    errors.append(f"第 {idx} 条前向评测引用了不存在的文件：{file_path}")

        expectations = item.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"第 {idx} 条前向评测必须包含非空的 `expectations` 数组")
        else:
            for exp_idx, expectation in enumerate(expectations, start=1):
                if not isinstance(expectation, str) or not expectation.strip():
                    errors.append(
                        f"第 {idx} 条前向评测的第 {exp_idx} 项 expectation 必须为非空字符串"
                    )


def validate_template(root: Path, errors: list[str]) -> None:
    text = (root / "assets" / "bdd-feature-template.feature").read_text(encoding="utf-8")
    forbidden_defaults = [
        "\n@requirement-",
        "\n@persona-",
        "\n@test-level-",
        "\n@manual",
        "\n@automated",
    ]
    for snippet in forbidden_defaults:
        if snippet in text:
            errors.append(
                "assets/bdd-feature-template.feature 不得强制要求默认元数据标签；请将其注释掉或移除"
            )
            break


def validate_required_files(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            errors.append(f"缺少必需文件：{relative}")
    shared = root.parent / "_testspec-shared"
    for relative in REQUIRED_SHARED_FILES:
        if not (shared / relative).is_file():
            errors.append(f"缺少共享报告资源：../_testspec-shared/{relative}；分发 reviewer 时须同时携带同级共享目录")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    errors: list[str] = []

    validate_required_files(root, errors)
    if errors:
        for error in errors:
            fail(error)
        return 1

    try:
        validate_skill_md(root, errors)
    except Exception as exc:
        errors.append(f"无法校验 SKILL.md frontmatter：{exc}")

    validate_openai_yaml(root, errors)
    validate_trigger_evals(root, errors)
    validate_forward_evals(root, errors)
    validate_template(root, errors)

    if errors:
        for error in errors:
            fail(error)
        return 1

    ok("必需文件均已存在")
    ok("SKILL.md frontmatter 格式有效")
    ok("agents/openai.yaml 包含必需的 interface 字段")
    ok("触发评测为有效 JSON，且结构符合预期")
    ok("前向评测清单有效，且引用文件均存在")
    ok("特性模板未强制要求臆造标签")
    print("仓库校验成功。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
