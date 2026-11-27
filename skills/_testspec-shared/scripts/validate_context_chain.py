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


def _load_sibling(name: str):
    spec = spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_case_validator = _load_sibling("validate_testcases")
_report_validator = _load_sibling("verify_eval_artifacts")
normalize_design_method = _case_validator.normalize_design_method


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


def json_context(path: Path, data: Any) -> dict[str, Any]:
    context = data.get("_context") if isinstance(data, dict) else None
    if not isinstance(context, dict):
        raise ValueError(f"{path}: missing object _context")
    return context


def load_context(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json_context(path, json.loads(path.read_text(encoding="utf-8")))
    return markdown_context(path)


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


def validate_bdd_review(text: str, context: dict[str, Any], fingerprints: dict[str, str]) -> list[str]:
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


def validate_reviewed_files(context: dict[str, Any], paths: dict[str, Path], change_dir: Path) -> list[str]:
    reviewed = context.get("reviewed_artifacts")
    errors: list[str] = []
    for key, path in paths.items():
        relative_path = path.relative_to(change_dir).as_posix()
        digest = reviewed.get(key) if isinstance(reviewed, dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"review: missing or invalid reviewed_artifacts.{key} for {relative_path}; rerun testcase-reviewer")
            continue
        try:
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"review: cannot read {relative_path}: {exc}")
            continue
        if digest != actual_digest:
            errors.append(f"review: {relative_path} hash differs from reviewed_artifacts.{key}; rerun testcase-reviewer")
    return errors


def validate_issue_gate(gate: dict[str, Any], prefix: str, label: str) -> list[str]:
    """Check one issue gate (judgment J1-J4 or description D1-D4): fields present, count matches IDs, pass needs zero."""
    errors: list[str] = []
    count_field, ids_field = f"{prefix}_unresolved_count", f"{prefix}_issue_ids"
    missing = sorted({count_field, ids_field} - gate.keys())
    if missing:
        errors.append(f"review: missing {label} fields: " + ", ".join(missing) + "; rerun testcase-reviewer")
    count = gate.get(count_field)
    issue_ids = gate.get(ids_field)
    valid_count = type(count) is int and count >= 0
    valid_ids = (
        isinstance(issue_ids, list)
        and all(isinstance(issue_id, str) and issue_id.strip() for issue_id in issue_ids)
        and len(set(issue_ids)) == len(issue_ids)
    )
    if count_field in gate and not valid_count:
        errors.append(f"review: {count_field} must be a nonnegative integer")
    if ids_field in gate and not valid_ids:
        errors.append(f"review: {ids_field} must be an array of unique nonblank strings")
    if valid_count and valid_ids:
        if count != len(issue_ids):
            errors.append(f"review: {count_field} differs from {ids_field} length")
        if gate["status"] == "pass" and (count != 0 or issue_ids):
            errors.append(f"review: pass requires zero unresolved {prefix} issues and empty {ids_field}")
    return errors


def validate_review_provenance(text: str, gate: dict[str, Any], case_data: dict) -> list[str]:
    provenance = _case_validator.check_provenance(case_data)
    if provenance["status"] == "pass":
        return []

    finding = provenance["issues"][0]
    scope = finding["scope"]
    mode = provenance["mode"]
    locations = ", ".join(finding["locations"])
    if gate["status"] == "pass":
        return [f"review: M5 {mode} requires blocked Gate ({scope}; {locations})"]

    s1_ids = gate.get("s1_issue_ids")
    s1_count = gate.get("s1_unresolved_count")
    if isinstance(s1_ids, list) and type(s1_count) is int and s1_count == len(s1_ids) and any(
        issue["dimension"] == "M5" and issue["severity"] == "S1" and issue["status"] != "resolved"
        and issue["id"] in s1_ids and re.search(rf"\b{re.escape(scope)}(?![\w-])", issue["body"].splitlines()[0])
        for issue in _report_validator.parse_issues(text)
    ):
        return []
    return [f"review: M5 {mode} requires an unresolved S1 issue for {scope} ({locations})"]


def validate(change_dir: Path, through: str, expected_version: int | None) -> list[str]:
    errors: list[str] = []
    try:
        source_path = canonical_path(change_dir)
        canonical = load_context(source_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    canonical_revision = canonical.get("source_revision")
    open_questions = _report_validator.blocking_question_ids(canonical, "canonical", errors)
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
    case_data = None
    analysis_has_fingerprint = False
    reviewed_paths: dict[str, Path] = {}
    review_fields = {"points": "testpoints_sha256", "generate": "testcases_sha256"}
    for stage, (relative_path, expected_skill) in list(STAGES.items())[: through_index + 1]:
        path = change_dir / relative_path
        if not path.exists() and stage == "generate":
            fallback = change_dir / "testcases.json"
            if fallback.exists():
                path = fallback
        if not path.exists():
            errors.append(f"{stage}: missing {relative_path}")
            continue
        if stage in review_fields:
            reviewed_paths[review_fields[stage]] = path

        try:
            if stage == "generate":
                case_data = json.loads(path.read_text(encoding="utf-8"))
                context = json_context(path, case_data)
            else:
                context = load_context(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue

        question_errors: list[str] = []
        questions = _report_validator.blocking_question_ids(context, stage, question_errors)
        if stage != "review":  # Review report validation checks its own question metadata below.
            errors.extend(question_errors)
        dropped_questions = open_questions - questions
        if dropped_questions:
            errors.append(f"{stage}: missing upstream blocking questions: " + ", ".join(sorted(dropped_questions)))
        open_questions.update(questions)

        if stage == "analysis" and "canonical_source_sha256" in context:
            analysis_has_fingerprint = True
            recorded = context["canonical_source_sha256"]
            if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded):
                errors.append("analysis: invalid canonical_source_sha256; rerun prd-analysis")
            else:
                try:
                    current = _case_validator._file_digest(source_path)
                except OSError as exc:
                    errors.append(f"analysis: cannot read {source_path.name}: {exc}")
                else:
                    if current != recorded:
                        errors.append(
                            f"analysis: {source_path.name} content differs from the analyzed canonical source; "
                            "rerun prd-analysis to confirm the current requirements and update the revision if needed"
                        )

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
            errors.extend(validate_reviewed_files(context, reviewed_paths, change_dir))
            text = path.read_text(encoding="utf-8")
            errors.extend(validate_bdd_review(text, context, bdd_hashes))
            gate = context.get("review_gate")
            if not isinstance(gate, dict) or gate.get("status") not in ("pass", "blocked"):
                errors.append("review: missing or invalid review_gate.status")
            else:
                if gate["status"] == "pass" and (gate.get("s1_unresolved_count") != 0 or gate.get("s1_issue_ids") != []):
                    errors.append("review: pass requires zero unresolved S1 and empty s1_issue_ids")

                for prefix, label in (("judgment", "judgment gate"), ("description", "four-field description gate")):
                    errors.extend(validate_issue_gate(gate, prefix, label))

                if gate["status"] == "pass" and not analysis_has_fingerprint:
                    errors.append("review: pass requires canonical_source_sha256; rerun prd-analysis on the current requirements")
                cases = case_data.get("testcases") if isinstance(case_data, dict) else None
                case_count = len(cases) if isinstance(cases, list) else 0
                errors.extend(_report_validator.validate_review_report(text, case_count=case_count, allow_legacy=False))
                if isinstance(cases, list) and cases:
                    errors.extend(validate_review_provenance(text, gate, case_data))
                elif gate["status"] == "pass":
                    errors.append("review: pass requires a nonempty testcase array")
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
