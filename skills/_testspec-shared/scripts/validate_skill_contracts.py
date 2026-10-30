#!/usr/bin/env python3
"""校验当前四步 TestSpec SOP 的目录、依赖和关键输出契约。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = ROOT / "skills"
SHARED_DIR = SKILLS_DIR / "_testspec-shared"

PIPELINE = (
    ("prd-analysis", "test-points"),
    ("test-points", "testcase-generate"),
    ("testcase-generate", "testcase-reviewer"),
    ("testcase-reviewer", None),
)

SHARED_FILES = (
    "common.md",
    "thinking-protocol.md",
    "reflection-protocol.md",
    "context-protocol.md",
    "output-contracts.md",
    "naming-contract.md",
    "source-provenance.md",
    "bdd-output-contracts.md",
    "bdd-report-rubric.md",
)

REPORT_TEMPLATES = (
    "requirements-analysis-template.md",
    "review-report-template.md",
    "testcase-review-report-template.md",
    "bdd-review-report-template.md",
)

BUSINESS_FIELDS = (
    "module",
    "submodule",
    "test_name",
    "preconditions",
    "test_data",
    "steps",
    "expected_result",
    "priority",
)

DESIGN_METHODS = (
    "等价类",
    "边界值",
    "判定表",
    "流程分析",
    "状态迁移",
    "错误推断",
    "正交实验",
    "因果图",
    "配对组合",
    "基于属性的测试",
    "变形测试",
    "语法规则分析",
)

OLD_SKILL_SUFFIXES = (
    "new",
    "update",
    "analysis",
    "points",
    "generate",
    "review",
    "publish",
    "import",
    "audit",
    "code-calibrate",
)

TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def listed_design_methods(markdown: str) -> tuple[str, ...]:
    return tuple(
        title.split("（", 1)[0].strip()
        for title in re.findall(r"^## \d+\.\s+(.+)$", markdown, re.MULTILINE)
    )


def referenced_paths(skill_dir: Path, markdown: str) -> set[Path]:
    refs = set(re.findall(r"`((?:references/|testcase-review/|\.\./_testspec-shared/)[^`]+)`", markdown))
    return {(skill_dir / ref).resolve() for ref in refs}


def validate_skill(name: str, next_skill: str | None, errors: list[str]) -> None:
    skill_dir = SKILLS_DIR / name
    entry = skill_dir / "SKILL.md"
    agent = skill_dir / "agents" / "openai.yaml"
    eval_file = skill_dir / "evals" / "evals.json"

    for path in (entry, agent, eval_file):
        add_error(errors, path.is_file(), f"缺少文件：{path}")
    if not all(path.is_file() for path in (entry, agent, eval_file)):
        return

    skill_text = read_text(entry)
    agent_text = read_text(agent)
    add_error(errors, f"name: {name}" in skill_text, f"{entry}: name 与目录不一致")
    add_error(errors, len(skill_text.splitlines()) <= 500, f"{entry}: 超过 500 行")
    add_error(errors, f"${name}" in agent_text, f"{agent}: default_prompt 未使用新名称 ${name}")
    add_error(errors, "allow_implicit_invocation: true" in agent_text, f"{agent}: 隐式调用策略缺失")

    try:
        json.loads(read_text(eval_file))
    except json.JSONDecodeError as exc:
        errors.append(f"{eval_file}: JSON 无效：{exc}")

    for target in referenced_paths(skill_dir, skill_text):
        add_error(errors, target.exists(), f"{entry}: 引用了不存在的文件 {target}")

    references_dir = skill_dir / "references"
    if references_dir.is_dir():
        for reference in references_dir.glob("*.md"):
            add_error(errors, reference.name in skill_text, f"{reference}: 未从 SKILL.md 路由")

    if next_skill:
        add_error(errors, next_skill in skill_text, f"{entry}: 未指向下一步 {next_skill}")


def validate_generate_contract(errors: list[str]) -> None:
    skill_dir = SKILLS_DIR / "testcase-generate"
    skill_text = read_text(skill_dir / "SKILL.md")
    methods_text = read_text(skill_dir / "references" / "test-design-methods.md")
    points_methods_text = read_text(SKILLS_DIR / "test-points" / "references" / "test-design-methods.md")
    xmind_text = read_text(skill_dir / "scripts" / "generate_xmind.py")
    validator_text = read_text(SHARED_DIR / "scripts" / "validate_testcases.py")

    for field in BUSINESS_FIELDS:
        add_error(errors, field in skill_text, f"testcase-generate 缺少字段 {field}")
        add_error(errors, field in validator_text, f"validate_testcases.py 缺少字段 {field}")
    for method in DESIGN_METHODS:
        add_error(errors, method in methods_text, f"test-design-methods.md 缺少方法：{method}")
        add_error(errors, method in points_methods_text, f"test-points 测试方法说明缺少方法：{method}")
    add_error(errors, listed_design_methods(methods_text) == DESIGN_METHODS,
              "testcase-generate 的正式方法集合或顺序与十二种方法契约不一致")
    add_error(errors, listed_design_methods(points_methods_text) == DESIGN_METHODS,
              "test-points 的正式方法集合或顺序与十二种方法契约不一致")
    add_error(errors, '"design_methods"' in read_text(SKILLS_DIR / "test-points" / "SKILL.md"), "test-points 未声明 design_methods 上下文输出")
    add_error(errors, "_context.design_methods" in skill_text, "testcase-generate 未声明 design_methods 上下文输出")

    add_error(errors, "XMind（默认）" in skill_text, "testcase-generate 未声明默认输出 XMind")
    add_error(errors, "独立 API、安全、性能等类型不进入本流程" in skill_text, "testcase-generate 未限制为功能用例")
    add_error(errors, '"p1": "priority-1"' in xmind_text, "XMind p1 marker 映射不正确")
    add_error(errors, '"p2": "priority-2"' in xmind_text, "XMind p2 marker 映射不正确")
    marker_match = re.search(r"PRIORITY_MARKERS\s*=\s*\{[^}]*\}", xmind_text)
    add_error(errors, marker_match is not None, "XMind 缺少优先级 marker 配置")
    if marker_match:
        add_error(errors, '"p0"' not in marker_match.group(0), "XMind p0 不应设置 marker")

    points_rules = read_text(SKILLS_DIR / "test-points" / "references" / "testpoint-design-rules.md")
    type_rules = read_text(skill_dir / "references" / "test-type-strategies.md")
    add_error(errors, "Non-Functional" not in points_rules, "test-points 仍含非功能分类")
    add_error(errors, "## security" not in type_rules and "## performance" not in type_rules,
              "testcase-generate 仍含非功能策略")
    points_template = read_text(SKILLS_DIR / "test-points" / "references" / "testpoints-template.md")
    review_root = SKILLS_DIR / "testcase-reviewer" / "testcase-review"
    workflow = review_root / "review-workflow.md"
    template = SHARED_DIR / "templates/review-report-template.md"
    for required in (workflow, review_root / "references/review-dimensions.md", template):
        add_error(errors, required.is_file(), f"统一评审缺少SOP模块：{required}")
    if not all(p.is_file() for p in (workflow, review_root / "references/review-dimensions.md", template)):
        return
    add_error(errors, not (SKILLS_DIR / "testcase-review").exists(), "旧独立 testcase-review 入口仍存在")
    add_error(errors, not list(review_root.rglob("SKILL.md")), "SOP内部模块不应另设Skill入口")
    review_text = read_text(workflow)
    review_dimensions = read_text(review_root / "references" / "review-dimensions.md")
    review_template = read_text(template)
    add_error(errors, "Non-Functional" not in points_template, "测试点模板仍含非功能分支")
    for category, case_type in (("Tracking", "埋点"), ("Compatibility", "兼容性矩阵")):
        add_error(errors, category in points_rules and category in points_template,
                  f"测试点缺少允许分类：{category}")
        add_error(errors, case_type in validator_text and case_type in type_rules and case_type in review_text,
                  f"用例生成或 Review 缺少允许类型：{case_type}")
    add_error(errors, "H3 同时检查范围" in review_text and "S1 阻断" in review_text,
              "Review 未保持范围阻断")
    for method in DESIGN_METHODS[-3:]:
        add_error(errors, method in review_dimensions, f"Review 未覆盖新增方法：{method}")
    add_error(errors, '"design_methods"' in review_template and "| 设计方法 |" in review_template,
              "Review 模板未保留方法追溯")
    add_error(errors, "反馈合成闭环" not in review_text and "feedback_for_" not in review_text + review_template,
              "Review 仍含反馈合成流程")


def validate_lanhu_adapter(errors: list[str]) -> None:
    skill_dir = SKILLS_DIR / "prd-analysis"
    skill_text = read_text(skill_dir / "SKILL.md")
    reference = skill_dir / "references" / "lanhu-prd-input.md"
    script = skill_dir / "scripts" / "direct_extract_axure.py"
    add_error(errors, reference.is_file(), f"prd-analysis 缺少蓝湖输入说明：{reference}")
    add_error(errors, script.is_file(), f"prd-analysis 缺少蓝湖直连脚本：{script}")
    add_error(errors, "lanhu-prd-input.md" in skill_text, "prd-analysis 未路由蓝湖输入说明")
    add_error(errors, "direct_extract_axure.py" in skill_text, "prd-analysis 未声明蓝湖直连脚本")
    if script.is_file():
        script_text = read_text(script)
        for marker in ("api/share/url/resolve", "api/project/image", "axure-file.lanhuapp.com"):
            add_error(errors, marker in script_text, f"蓝湖直连脚本缺少接口标识：{marker}")


def validate_no_old_skill_names(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if standalone_path(path) or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        for suffix in OLD_SKILL_SUFFIXES:
            old_name = f"testspec-{suffix}"
            add_error(errors, old_name not in text, f"{path}: 仍包含旧 Skill 名称 {old_name}")


def validate_no_removed_stage_references(errors: list[str]) -> None:
    removed_name = "testcase" + "-merge"
    paths = [ROOT / "README.md", *SKILLS_DIR.rglob("*.md"), *SKILLS_DIR.rglob("*.json"), *SKILLS_DIR.rglob("*.yaml")]
    for path in paths:
        if standalone_path(path):
            continue
        add_error(errors, removed_name not in read_text(path), f"{path}: 仍引用已删除的合并阶段")


def standalone_path(path: Path) -> bool:
    root = SKILLS_DIR / "testcase-reviewer"
    if not path.is_relative_to(root):
        return False
    relative = path.relative_to(root)
    return bool(relative.parts) and relative.parts[0] not in {"testcase-review", "evals", "SKILL.md"}


def validate_standalone_reviewer(errors: list[str]) -> None:
    """Pin the unified reviewer package, including the nested SOP module."""
    root = SKILLS_DIR / "testcase-reviewer"
    manifest = SKILLS_DIR / "_testspec-shared" / "references" / "testcase-reviewer-source.json"
    try:
        if root.is_symlink():
            raise ValueError("standalone snapshot must be a real directory, not a symbolic link")
        files = json.loads(read_text(manifest))["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("files must be a non-empty object")
        for name, digest in files.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or str(relative) != name:
                raise ValueError(f"unsafe snapshot path: {name}")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"invalid SHA-256: {name}")
        actual = {}
        for path in root.rglob("*"):
            if path.is_symlink():
                errors.append(f"独立 reviewer 快照不得包含符号链接：{path}")
                continue
            if not path.is_file() or any(part in {"__pycache__", ".DS_Store"} for part in path.relative_to(root).parts):
                continue
            actual[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in sorted(set(files) | set(actual)):
            add_error(errors, files.get(name) == actual.get(name), f"独立 reviewer 快照缺失、增加或被修改：{name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"独立 reviewer 来源清单无效：{exc}")


def main() -> int:
    errors: list[str] = []

    actual_public = sorted(
        path.name
        for path in SKILLS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )
    expected_public = sorted(name for name, _ in PIPELINE)
    add_error(errors, actual_public == expected_public, f"公开 Skill 目录不匹配：{actual_public}")

    for shared_name in SHARED_FILES:
        add_error(errors, (SHARED_DIR / "references" / shared_name).is_file(), f"缺少共享契约：{shared_name}")

    for template_name in REPORT_TEMPLATES:
        add_error(errors, (SHARED_DIR / "templates" / template_name).is_file(), f"缺少共享报告模板：{template_name}")

    for name, next_skill in PIPELINE:
        validate_skill(name, next_skill, errors)

    validate_generate_contract(errors)
    validate_lanhu_adapter(errors)
    validate_no_old_skill_names(errors)
    validate_no_removed_stage_references(errors)
    validate_standalone_reviewer(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("PASS: validated 4 TestSpec SOP skills, unified review entry, dependencies, output contracts, and reviewer snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
