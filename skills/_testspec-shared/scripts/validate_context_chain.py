#!/usr/bin/env python3
"""Validate TestSpec context propagation for one change directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


# 按固定路径复用用例校验器的别名规则，避免跨阶段维护两套名称映射。
_method_spec = spec_from_file_location("testspec_method_validator", Path(__file__).with_name("validate_testcases.py"))
_method_validator = module_from_spec(_method_spec)
_method_spec.loader.exec_module(_method_validator)
normalize_design_method = _method_validator.normalize_design_method


STAGES = {
    "analysis": ("requirements-analysis.md", "prd-analysis"),
    "points": ("specs/testpoints.md", "test-points"),
    "generate": ("artifacts/testcases.json", "testcase-generate"),
    "review": ("review-report.md", "testcase-reviewer"),
}

SELF_ARTIFACT_NAMES = {
    "analysis": {"requirements-analysis.md"},
    "points": {"testpoints.md", "specs/testpoints.md"},
    "generate": {"testcases.json", "artifacts/testcases.json"},
    "review": {"review-report.md"},
}

REQUIRED_ENVELOPE_FIELDS = {
    "source_revision",
    "blocking_open_questions",
    "dynamic_followups",
    "material_quality",
    "stale_downstream_artifacts",
}


def markdown_context(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(
        r"^[ \t]*<!--[ \t]*testspec-context\b", text, flags=re.MULTILINE,
    ))
    if not starts:
        raise ValueError(f"{path}: missing testspec-context block")
    if len(starts) != 1:
        raise ValueError(f"{path}: expected exactly one testspec-context block")
    end = text.find("-->", starts[0].end())
    if end == -1:
        raise ValueError(f"{path}: unclosed testspec-context block")
    context = json.loads(text[starts[0].end():end].strip())
    if not isinstance(context, dict):
        raise ValueError(f"{path}: testspec-context must contain a JSON object")
    return context


def json_context(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    context = data.get("_context")
    if not isinstance(context, dict):
        raise ValueError(f"{path}: missing object _context")
    return context


def load_context(path: Path) -> dict[str, Any]:
    return json_context(path) if path.suffix == ".json" else markdown_context(path)


def canonical_path(change_dir: Path) -> Path:
    requirements = change_dir / "requirements.md"
    if requirements.exists():
        return requirements
    proposal = change_dir / "proposal.md"
    if proposal.exists():
        return proposal
    raise ValueError(f"{change_dir}: missing requirements.md and proposal.md")


def bdd_artifacts(change_dir: Path) -> tuple[dict[str, str], list[str]]:
    """检查伴生文件存在、可读且非空；不代替 Gherkin 或业务语义评审。"""
    paths = sorted((change_dir / "artifacts").glob("*_features.feature"))
    if not paths:
        return {}, ["generate: missing artifacts/*_features.feature"]
    fingerprints: dict[str, str] = {}
    errors: list[str] = []
    for path in paths:
        try:
            content = path.read_bytes()
            if not content.decode("utf-8-sig").strip():
                errors.append(f"generate: empty BDD feature {path.name}")
            fingerprints[path.relative_to(change_dir).as_posix()] = hashlib.sha256(content).hexdigest()
        except (OSError, UnicodeError) as exc:
            errors.append(f"generate: unreadable BDD feature {path.name}: {exc}")
    return fingerprints, errors


def validate_bdd_review(report: Path, context: dict[str, Any], fingerprints: dict[str, str]) -> list[str]:
    """核对完成记录、可见评审摘要与全部 BDD 指纹，不判断评审结论的真假。"""
    errors: list[str] = []
    record = context.get("bdd_review")
    if not isinstance(record, dict) or record.get("status") != "complete":
        errors.append("review: BDD review is incomplete or missing; rerun testcase-reviewer")
    reviewed = context.get("reviewed_artifacts")
    hashes = reviewed.get("bdd_features_sha256") if isinstance(reviewed, dict) else None
    if (
        not isinstance(hashes, dict) or not hashes
        or any(not isinstance(name, str) or not isinstance(digest, str)
               or not re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in hashes.items())
    ):
        errors.append("review: missing or invalid reviewed_artifacts.bdd_features_sha256; rerun testcase-reviewer")
    elif hashes != fingerprints:
        errors.append("review: BDD files or hashes differ from reviewed artifacts; rerun testcase-reviewer")

    text = report.read_text(encoding="utf-8")
    headings = list(re.finditer(r"^##\s+BDD 场景评审\s*$", text, re.MULTILINE))
    if len(headings) != 1:
        errors.append("review: expected one visible BDD 场景评审 section")
        return errors
    tail = text[headings[0].end():]
    following = re.search(r"^##\s+|^<!--[ \t]*testspec-context\b", tail, re.MULTILINE)
    block = tail[:following.start()] if following else tail
    values = {}
    for label in ("BDD评审状态", "评审文件", "已检查内容", "评审结论"):
        matches = re.findall(rf"^[ \t]*\*\*{label}\*\*[ \t]*[:：][ \t]*([^\r\n]*)$", block, re.MULTILINE)
        if len(matches) != 1 or re.fullmatch(r"\s*(?:<[^>]*>|TODO|TBD|待填写|待补充|无|—|-)?\s*", matches[0], re.I):
            errors.append(f"review: BDD {label} must have one filled value")
        else:
            values[label] = matches[0].strip()
    if values.get("BDD评审状态") != "已完成":
        errors.append("review: visible BDD review is incomplete")
    if any(name not in values.get("评审文件", "") for name in fingerprints):
        errors.append("review: BDD review scope omits current feature files")
    return errors


def validate(change_dir: Path, through: str, expected_version: int | None) -> list[str]:
    errors: list[str] = []
    try:
        canonical = load_context(canonical_path(change_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    canonical_revision = canonical.get("source_revision")
    canonical_version = (
        canonical_revision.get("version")
        if isinstance(canonical_revision, dict)
        else None
    )
    if expected_version is not None and canonical_version != expected_version:
        errors.append(
            f"canonical source_revision.version={canonical_version!r}, "
            f"expected {expected_version}"
        )

    through_index = list(STAGES).index(through)
    bdd_hashes: dict[str, str] = {}
    if through_index >= list(STAGES).index("generate"):
        bdd_hashes, bdd_errors = bdd_artifacts(change_dir)
        errors.extend(bdd_errors)
    generated_methods = None
    for stage, (relative_path, expected_skill) in list(STAGES.items())[: through_index + 1]:
        path = change_dir / relative_path
        if not path.exists() and stage == "generate":
            fallback = change_dir / "testcases.json"
            if fallback.exists():
                path = fallback
        if not path.exists():
            errors.append(f"{stage}: missing {relative_path}")
            continue

        try:
            context = load_context(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue

        accepted_skills = {expected_skill, "testcase-review"} if stage == "review" else {expected_skill}
        if context.get("source_skill") not in accepted_skills:
            errors.append(
                f"{stage}: source_skill={context.get('source_skill')!r}, "
                f"expected {expected_skill!r}"
            )

        if stage == "generate" and "design_methods" in context:
            names = context["design_methods"]
            if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
                errors.append("generate: design_methods must be an array of names")
            else:
                generated_methods = {normalize_design_method(name) for name in names}
        if stage == "review" and generated_methods is not None:
            names = context.get("design_methods")
            if (
                not isinstance(names, list)
                or any(not isinstance(name, str) for name in names)
                or {normalize_design_method(name) for name in names} != generated_methods
            ):
                errors.append("review: design_methods differs from generated cases")

        if stage == "review":
            errors.extend(validate_bdd_review(path, context, bdd_hashes))
            gate = context.get("review_gate")
            if not isinstance(gate, dict) or gate.get("status") not in {"pass", "blocked"}:
                errors.append("review: missing or invalid review_gate.status")
            else:
                if gate["status"] == "pass" and (gate.get("s1_unresolved_count") != 0 or gate.get("s1_issue_ids") != []):
                    errors.append("review: pass requires zero unresolved S1 and empty s1_issue_ids")

                description_fields = {"description_unresolved_count", "description_issue_ids"}
                missing_description = sorted(description_fields - gate.keys())
                if missing_description:
                    errors.append(
                        "review: missing four-field description gate fields: "
                        + ", ".join(missing_description)
                        + "; rerun testcase-reviewer"
                    )
                count = gate.get("description_unresolved_count")
                issue_ids = gate.get("description_issue_ids")
                valid_count = type(count) is int and count >= 0
                valid_ids = (
                    isinstance(issue_ids, list)
                    and all(isinstance(issue_id, str) and issue_id.strip() for issue_id in issue_ids)
                    and len(set(issue_ids)) == len(issue_ids)
                )
                if "description_unresolved_count" in gate and not valid_count:
                    errors.append("review: description_unresolved_count must be a nonnegative integer")
                if "description_issue_ids" in gate and not valid_ids:
                    errors.append("review: description_issue_ids must be an array of unique nonblank strings")
                if valid_count and valid_ids:
                    if count != len(issue_ids):
                        errors.append("review: description_unresolved_count differs from description_issue_ids length")
                    if gate["status"] == "pass" and (count != 0 or issue_ids):
                        errors.append("review: pass requires zero unresolved description issues and empty description_issue_ids")
            if "next_skill" in context:
                errors.append("review: terminal stage must omit next_skill")

        if canonical_version is None:
            if context.get("source_revision") is not None:
                errors.append(f"{stage}: legacy canonical source must not gain a fabricated revision")
            continue

        missing = sorted(REQUIRED_ENVELOPE_FIELDS - context.keys())
        if missing:
            errors.append(f"{stage}: missing envelope fields: {', '.join(missing)}")

        if context.get("source_revision") != canonical_revision:
            errors.append(f"{stage}: source_revision differs from canonical source")

        stale = context.get("stale_downstream_artifacts")
        if not isinstance(stale, list):
            errors.append(f"{stage}: stale_downstream_artifacts must be an array")
            continue
        stale_names = {str(item) for item in stale}
        if stale_names & SELF_ARTIFACT_NAMES[stage]:
            errors.append(f"{stage}: propagated stale list still contains its own artifact")
        if stage == "generate" and any(name.endswith("_features.feature") for name in stale_names):
            errors.append("generate: propagated stale list still contains its BDD artifact")
        if not stale and ("stale_reason" in context or "next_skill" in context):
            errors.append(f"{stage}: empty stale list must omit stale_reason and next_skill")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change-dir", required=True, type=Path)
    parser.add_argument("--through", required=True, choices=tuple(STAGES))
    parser.add_argument("--expected-version", type=int)
    args = parser.parse_args()

    errors = validate(args.change_dir, args.through, args.expected_version)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: TestSpec context chain is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
