#!/usr/bin/env python3
"""Independent structural checks used by the synthetic TestSpec evals."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any


NS = "{urn:xmind:xmap:xmlns:content:2.0}"
MATRIX_IDS = tuple([f"M{i}" for i in range(1, 6)] + [f"J{i}" for i in range(1, 5)] + [f"D{i}" for i in range(1, 6)])
LEGACY_MATRIX_IDS = tuple([f"R{i}" for i in range(1, 7)] + [f"H{i}" for i in range(1, 9)])
JUDGMENT_IDS = frozenset(f"J{i}" for i in range(1, 5))
DESCRIPTION_IDS = frozenset(f"D{i}" for i in range(1, 5))
QUESTION_ID = re.compile(r"(?<![A-Za-z0-9_-])Q-[0-9]+(?![A-Za-z0-9_-])")
DIMENSION_PATTERN = re.compile(r"(?:M[1-5]|J[1-4]|D[1-5])")
ISSUE_LINE = re.compile(
    r"^[ \t]*[-*+][ \t]+\[(S[1-3])\][ \t]+\[(open|resolved|accepted)\][ \t]+(\S+)[ \t]+\[(M[1-5]|J[1-4]|D[1-5])\]",
    re.M,
)
LAYER_SECTIONS = {"M": "一、机器检查", "J": "二、需求判定力表", "D": "三、用例与 BDD 质量"}
MATRIX_STATUSES = {"pass", "fail", "blocked"}
PLACEHOLDER = re.compile(r"<[^>]*>|\b(?:TODO|TBD|N/?A)\b|待填写|待补充|占位|未填写", re.I)
FIELD_LABELS = {
    "preconditions": "前置条件：\n",
    "test_data": "测试数据：\n",
    "steps": "操作步骤：\n",
    "expected_result": "预期结果：\n",
}
PRIORITY_MARKERS = {"p0": [], "p1": ["priority-1"], "p2": ["priority-2"]}


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return data


def _topic_children(topic: ET.Element) -> list[ET.Element]:
    container = topic.find(f"{NS}children/{NS}topics")
    return list(container) if container is not None else []


def _topic_title(topic: ET.Element) -> str:
    title = topic.find(f"{NS}title")
    return title.text if title is not None and title.text is not None else ""


def _label_value(title: str, field: str) -> str | None:
    prefix = FIELD_LABELS[field]
    return title[len(prefix):] if title.startswith(prefix) else None


def _parse_xmind_case(topic: ET.Element, module: str, submodule: str, path: str) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    values: dict[str, str] = {"module": module, "submodule": submodule, "test_name": _topic_title(topic)}
    details = _topic_children(topic)
    steps_nodes: list[ET.Element] = []
    direct_order: list[str] = []
    for node in details:
        title = _topic_title(node)
        matched = False
        for field in ("preconditions", "test_data", "steps"):
            value = _label_value(title, field)
            if value is not None:
                if field in values:
                    errors.append(f"{path}.{field}: duplicate XMind node")
                values[field] = value
                direct_order.append(field)
                matched = True
                if field == "steps":
                    steps_nodes.append(node)
                elif _topic_children(node):
                    errors.append(f"{path}.{field}: optional field node must be a leaf")
                break
        if matched:
            continue
        if title.startswith(FIELD_LABELS["expected_result"]):
            errors.append(f"{path}.expected_result: expected-result node must be nested under steps")
        else:
            errors.append(f"{path}.details: unrecognized detail node {title!r}")

    if len(steps_nodes) > 1:
        errors.append(f"{path}.steps: duplicate XMind node")
    values.setdefault("preconditions", "")
    values.setdefault("test_data", "")
    if steps_nodes:
        expected_nodes = _topic_children(steps_nodes[0])
        if len(expected_nodes) > 1:
            errors.append(f"{path}.expected_result: multiple nested nodes")
        if expected_nodes:
            expected_title = _topic_title(expected_nodes[0])
            expected = _label_value(expected_title, "expected_result")
            if expected is None:
                errors.append(f"{path}.expected_result: missing label or malformed node")
            else:
                values["expected_result"] = expected
            if _topic_children(expected_nodes[0]):
                errors.append(f"{path}.expected_result: node must be a leaf")
        else:
            values["expected_result"] = ""
    else:
        values.setdefault("steps", "")
        values["expected_result"] = ""

    marker_parent = topic.find(f"{NS}marker-refs")
    markers = [node.get("marker-id", "") for node in marker_parent.findall(f"{NS}marker-ref")] if marker_parent is not None else []
    values["_markers"] = "\0".join(markers)
    values["_direct_order"] = "\0".join(direct_order)
    values["_expected_present"] = "1" if steps_nodes and _topic_children(steps_nodes[0]) else "0"
    return values, errors


def compare_xmind(json_path: Path, xmind_path: Path) -> list[str]:
    """Compare all exported case fields without using the exporter implementation."""
    try:
        data = _read_json(json_path)
        testcases = data.get("testcases")
        if not isinstance(testcases, list) or not testcases:
            return [f"{json_path}: testcases must be a non-empty array"]
        with zipfile.ZipFile(xmind_path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                return [f"{xmind_path}: ZIP CRC failed at {bad_member}"]
            document = ET.fromstring(archive.read("content.xml"))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError, json.JSONDecodeError) as exc:
        return [f"{json_path} / {xmind_path}: {exc}"]

    expected_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for index, case in enumerate(testcases):
        case_id = case.get("id", f"<index:{index}>") if isinstance(case, dict) else f"<index:{index}>"
        if not isinstance(case, dict):
            return [f"case_id={case_id} path=testcases[{index}]: expected an object"]
        missing = [name for name in ("module", "submodule", "test_name", "preconditions", "test_data", "steps", "expected_result", "priority") if name not in case]
        if missing:
            return [f"case_id={case_id} path={','.join(missing)}: JSON business field missing"]
        if any(not isinstance(case[name], str) for name in ("module", "submodule", "test_name", "preconditions", "test_data", "steps", "expected_result", "priority")):
            return [f"case_id={case_id} path=testcases[{index}]: all eight business fields must be strings"]
        expected_groups[(case["module"], case["submodule"])].append(case)

    sheet = document.find(f"{NS}sheet")
    root_topic = sheet.find(f"{NS}topic") if sheet is not None else None
    if root_topic is None:
        return [f"{xmind_path}: content.xml is missing the sheet root topic"]

    actual_groups: dict[tuple[str, str], list[tuple[dict[str, str], list[str], str]]] = defaultdict(list)
    for module_node in _topic_children(root_topic):
        module = _topic_title(module_node)
        for submodule_node in _topic_children(module_node):
            submodule = _topic_title(submodule_node)
            group = (module, submodule)
            for case_index, case_node in enumerate(_topic_children(submodule_node)):
                xml_path = f"module[{module!r}]/submodule[{submodule!r}]/case[{case_index}]"
                values, errors = _parse_xmind_case(case_node, module, submodule, xml_path)
                actual_groups[group].append((values, errors, xml_path))

    errors: list[str] = []
    expected_group_order = sorted(expected_groups)
    actual_group_order: list[tuple[str, str]] = []
    for module_node in _topic_children(root_topic):
        module = _topic_title(module_node)
        for submodule_node in _topic_children(module_node):
            actual_group_order.append((module, _topic_title(submodule_node)))
    if actual_group_order != expected_group_order:
        errors.append(f"path=module/submodule order: expected {expected_group_order!r}, got {actual_group_order!r}")

    actual_count = sum(len(cases) for cases in actual_groups.values())
    if actual_count != len(testcases):
        errors.append(f"path=case count: JSON has {len(testcases)}, XMind has {actual_count}")

    for group in expected_group_order:
        expected_cases = expected_groups[group]
        actual_cases = actual_groups.get(group, [])
        if len(actual_cases) != len(expected_cases):
            errors.append(f"path=module[{group[0]!r}]/submodule[{group[1]!r}]/case count: JSON has {len(expected_cases)}, XMind has {len(actual_cases)}")
        for index, case in enumerate(expected_cases):
            case_id = case["id"]
            if index >= len(actual_cases):
                errors.append(f"case_id={case_id} path=xmind/{group[0]}/{group[1]}/case[{index}]: missing node")
                continue
            values, parse_errors, xml_path = actual_cases[index]
            errors.extend(f"case_id={case_id} {item}" for item in parse_errors)
            prefix = f"{case['module']}_{case['submodule']}_"
            scene = case["test_name"][len(prefix):] if case["test_name"].startswith(prefix) else case["test_name"]
            expected_values = {
                "module": case["module"],
                "submodule": case["submodule"],
                "test_name": scene,
                "preconditions": case["preconditions"],
                "test_data": case["test_data"],
                "steps": case["steps"],
                "expected_result": case["expected_result"],
            }
            for field, expected_value in expected_values.items():
                if values.get(field) != expected_value:
                    errors.append(f"case_id={case_id} path={xml_path}.{field}: expected {expected_value!r}, got {values.get(field)!r}")
            expected_order = [field for field in ("preconditions", "test_data", "steps") if case[field]]
            actual_order = list(filter(None, values.get("_direct_order", "").split("\0")))
            if actual_order != expected_order:
                errors.append(f"case_id={case_id} path={xml_path}.details.order: expected {expected_order!r}, got {actual_order!r}")
            if not case["preconditions"] and "preconditions" in actual_order:
                errors.append(f"case_id={case_id} path={xml_path}.preconditions: blank optional node must be omitted")
            if not case["test_data"] and "test_data" in actual_order:
                errors.append(f"case_id={case_id} path={xml_path}.test_data: blank optional node must be omitted")
            expected_present = bool(case["expected_result"])
            if values.get("_expected_present") != ("1" if expected_present else "0"):
                errors.append(f"case_id={case_id} path={xml_path}.expected_result: empty results must be omitted and non-empty results must be nested under steps")
            priority = case["priority"].lower()
            if priority not in PRIORITY_MARKERS:
                errors.append(f"case_id={case_id} path=priority: unsupported value {case['priority']!r}")
            else:
                actual_markers = sorted(filter(None, values.get("_markers", "").split("\0")))
                expected_markers = PRIORITY_MARKERS[priority]
                if actual_markers != expected_markers:
                    errors.append(f"case_id={case_id} path={xml_path}.priority: {priority} expects markers {expected_markers!r}, got {actual_markers!r}")

    extra_groups = set(actual_groups) - set(expected_groups)
    for module, submodule in sorted(extra_groups):
        errors.append(f"path=module[{module!r}]/submodule[{submodule!r}]: unexpected XMind group")
    return errors


def _is_placeholder(value: str) -> bool:
    return not value.strip() or PLACEHOLDER.search(value) is not None or value.strip() in {"-", "—", "待确认", "无"}


def parse_issues(text: str) -> list[dict[str, str]]:
    """Parse tagged entries of the single issue list: - [S1] [open] RV-001 [J1] ..."""
    matches = list(ISSUE_LINE.finditer(text))
    issues: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        end = len(text)
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        heading = re.search(r"^#{1,6}\s+|^<!--", text[match.end():end], re.M)
        if heading:
            end = match.end() + heading.start()
        issues.append({
            "severity": match.group(1), "status": match.group(2), "id": match.group(3),
            "dimension": match.group(4), "body": text[match.start():end],
        })
    return issues


def blocking_question_ids(context: dict[str, Any], stage: str, errors: list[str]) -> set[str]:
    entries = context.get("blocking_open_questions", [])
    if not isinstance(entries, list):
        errors.append(f"{stage}: blocking_open_questions must be an array")
        return set()
    ids = set()
    for index, entry in enumerate(entries):
        if isinstance(entry, dict):
            value = entry.get("id") or entry.get("question_id")
            match = QUESTION_ID.fullmatch(value.strip()) if isinstance(value, str) else None
        else:
            match = QUESTION_ID.search(entry) if isinstance(entry, str) else None
        if match is None:
            errors.append(f"{stage}: blocking_open_questions[{index}] requires a Q ID")
        else:
            ids.add(match[0])
    return ids


def validate_review_questions(context: dict[str, Any], gate: dict[str, Any],
                              unresolved: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    questions = blocking_question_ids(context, "review", errors)
    if not questions:
        return errors
    if gate["status"] == "pass":
        return errors + ["review: pass is blocked by open questions: " + ", ".join(sorted(questions))]

    judgment_ids = gate.get("judgment_issue_ids")
    covered = {
        question_id
        for issue in unresolved
        if issue["dimension"] == "J4" and isinstance(judgment_ids, list) and issue["id"] in judgment_ids
        for question_id in QUESTION_ID.findall(issue["body"])
    }
    missing = questions - covered
    if missing:
        errors.append("review: blocking questions require unresolved J4 issues: " + ", ".join(sorted(missing)))
    return errors


def _context_from_text(text: str) -> dict[str, Any] | None:
    matches = re.findall(r"<!--[ \t]*testspec-context\b(.*?)-->", text, flags=re.S)
    if len(matches) != 1:
        return None
    try:
        data = json.loads(matches[0].strip())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _table_rows(block: str) -> Iterator[list[str]]:
    for line in block.splitlines():
        if line.lstrip().startswith("|"):
            yield [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _matrix_rows(block: str, id_pattern: str, errors: list[str]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for cells in _table_rows(block):
        if len(cells) != 4:
            continue
        match = re.match(rf"({id_pattern})\b", cells[0])
        if match:
            key = match.group(1)
            if key in rows:
                errors.append(f"review matrix {key}: duplicate row")
            rows[key] = cells[1:]
    return rows


def _section_after(text: str, heading: re.Match[str], level: str = "##") -> str:
    following = re.search(rf"^{level}\s+", text[heading.end():], re.M)
    return text[heading.end():heading.end() + following.start()] if following else text[heading.end():]


def _review_state(raw: str) -> str:
    return re.split(r"[（(；;：:]", raw, maxsplit=1)[0].strip()


def validate_pass_evidence(text: str, case_count: int | None = None) -> list[str]:
    """Check the visible review evidence required for a passing SOP Gate."""
    errors: list[str] = []
    execution = list(re.finditer(r"^##[ \t]+评审执行记录[ \t]*$", text, re.M))
    statuses = re.findall(r"^[ \t]*\*\*评审状态\*\*[ \t]*[:：][ \t]*([^\r\n]*)$",
                          _section_after(text, execution[0]), re.M) if len(execution) == 1 else []
    if len(statuses) != 1 or _review_state(statuses[0]) != "已完成":
        errors.append("review: pass requires 评审执行记录 with 评审状态 已完成")

    judgment = list(re.finditer(r"^##[ \t]+(?:二、)?需求判定力表[ \t]*$", text, re.M))
    rows = [] if len(judgment) != 1 else [
        cells for cells in _table_rows(_section_after(text, judgment[0], "#{2,3}"))
        if any(cell and not re.fullmatch(r":?-+:?", cell) for cell in cells)
        and not any(re.match(r"^必测项(?:[（(]|$)", cell) for cell in cells[:2])
    ]
    if not rows:
        errors.append("review: pass requires nonempty 需求判定力表")
    for cells in rows:
        if len(cells) == 8 and re.fullmatch(r"\d+", cells[0]):
            cells = cells[1:]
        if len(cells) != 7 or any(_is_placeholder(cell) for cell in cells[:2]):
            errors.append("review: 需求判定力表 requires a requirement and source on each row")
            continue
        requirement, _, coverage, counterfactual, caught, conclusion, _ = cells
        if _review_state(conclusion) == "范围外":
            continue
        if (_review_state(conclusion) != "已拦住" or _review_state(caught) != "是"
                or _is_placeholder(coverage) or _is_placeholder(counterfactual)):
            errors.append(f"review: pass requires a covered and observable check in 需求判定力表 for {requirement}")

    quality = list(re.finditer(r"^##[ \t]+(?:三、)?用例与 BDD 质量[ \t]*$", text, re.M))
    block = _section_after(text, quality[0]) if len(quality) == 1 else ""
    sections = list(re.finditer(r"^###[ \t]+四项描述门禁[ \t]*$", block, re.M))
    if len(sections) != 1:
        return errors + ["review: pass requires one 四项描述门禁 table"]

    totals: dict[str, int] = {}
    for cells in _table_rows(_section_after(block, sections[0], "###")):
        dimension = cells[0] if cells else ""
        if dimension not in DESCRIPTION_IDS:
            continue
        count = re.fullmatch(r"([0-9]+)\s*[/／]\s*([0-9]+)", cells[2]) if len(cells) == 5 else None
        if dimension in totals or count is None or cells[3].lower() != "pass":
            errors.append(f"review: 四项描述门禁 {dimension} requires one passing checked/total row")
            continue
        checked, total = map(int, count.groups())
        totals[dimension] = total
        if total == 0 or checked != total or (case_count is not None and total != case_count):
            expected = f" ({case_count} current cases)" if case_count is not None else ""
            errors.append(f"review: 四项描述门禁 {dimension} must cover the full testcase set{expected}; got {checked}/{total}")
    if totals.keys() != DESCRIPTION_IDS or len(set(totals.values())) != 1:
        errors.append("review: 四项描述门禁 must record D1–D4 with one consistent testcase total")
    return errors


def validate_review_report(
    text: str, *, case_count: int | None = None, allow_legacy: bool = True,
) -> list[str]:
    """Validate the 14-item matrix, the single issue list and Gate consistency; not semantic truth."""
    heading = re.search(r"^##\s+.*14\s*项矩阵\s*$", text, re.M)
    if heading:
        return _validate_layered_report(text, _section_after(text, heading), case_count)
    legacy = re.search(r"^###\s+结论总览矩阵\s*$", text, re.M)
    if legacy and allow_legacy:
        return _validate_legacy_matrix(_section_after(text, legacy))
    return ["review report: missing 14-item matrix"]


def _validate_layered_report(text: str, matrix: str, case_count: int | None) -> list[str]:
    errors: list[str] = []
    rows = _matrix_rows(matrix, r"M[1-5]|J[1-4]|D[1-5]", errors)
    issues = parse_issues(text)
    tagged: dict[str, int] = {}
    seen: set[str] = set()
    for issue in issues:
        tagged[issue["dimension"]] = tagged.get(issue["dimension"], 0) + 1
        if issue["id"] in seen:
            errors.append(f"review issues: duplicate issue ID {issue['id']}")
        seen.add(issue["id"])
        if issue["dimension"] == "M4":
            errors.append(f"review issues: {issue['id']} uses M4; similar candidates are confirmed under D5")
        if not re.search(r"\bowner(?:\*\*)?\s*[:：=]\s*[A-Za-z0-9_-]+", issue["body"]):
            errors.append(f"review issues: {issue['id']} must declare owner")

    for key in MATRIX_IDS:
        if key not in rows:
            errors.append(f"review matrix {key}: row missing")
            continue
        result, metric, count = rows[key]
        if key == "M4":
            if result not in {"—", "-"}:
                errors.append("review matrix M4: result must be a dash; candidates are confirmed under D5")
        elif result not in MATRIX_STATUSES:
            errors.append(f"review matrix {key}: invalid result {result!r}")
        if _is_placeholder(metric) or not re.search(r"\d", metric):
            errors.append(f"review matrix {key}: metric must contain a non-placeholder quantitative value")
        if not re.fullmatch(r"\d+", count):
            errors.append(f"review matrix {key}: problem count must be a nonnegative integer, got {count!r}")
        elif int(count) != tagged.get(key, 0):
            errors.append(f"review matrix {key}: problem count {count} differs from {tagged.get(key, 0)} issue(s) tagged [{key}]")

    context = _context_from_text(text)
    gate = context.get("review_gate") if context else None
    status = gate.get("status") if isinstance(gate, dict) else None
    if status not in ("pass", "blocked"):
        return errors + ["review gate: missing or invalid review_gate.status"]

    visible = re.findall(r"^[ \t]*\*\*Review Gate\*\*[ \t]*[:：][ \t]*([^\r\n]*)$", text, re.M)
    if len(visible) != 1 or _review_state(visible[0]) != status:
        errors.append(f"review gate: visible Review Gate must match review_gate.status ({status})")

    unresolved = [issue for issue in issues if issue["status"] != "resolved"]
    errors.extend(validate_review_questions(context, gate, unresolved))
    unresolved_dimensions = {issue["dimension"] for issue in unresolved}
    for key in sorted((JUDGMENT_IDS | DESCRIPTION_IDS) & rows.keys()):
        result = rows[key][0]
        if key in unresolved_dimensions and result == "pass":
            errors.append(f"review matrix {key}: unresolved issues cannot have a pass result")
        if key not in unresolved_dimensions and result == "fail":
            errors.append(f"review matrix {key}: a fail result requires an unresolved issue")
        if status == "pass" and result != "pass":
            errors.append(f"review matrix {key}: a passing Review Gate requires a pass result")

    expected = {
        "s1_issue_ids": {issue["id"] for issue in unresolved if issue["severity"] == "S1"},
        "judgment_issue_ids": {issue["id"] for issue in unresolved if issue["dimension"] in JUDGMENT_IDS},
        "description_issue_ids": {issue["id"] for issue in unresolved if issue["dimension"] in DESCRIPTION_IDS},
    }
    for field, ids in expected.items():
        recorded = gate.get(field)
        if not isinstance(recorded, list):
            errors.append(f"review gate: {field} missing; rerun testcase-reviewer")
        elif set(map(str, recorded)) != ids:
            errors.append(f"review gate: {field} differs from unresolved issues in the issue list: expected {sorted(ids)}")
    if status == "pass":
        if any(expected.values()):
            errors.append("review gate: pass requires no unresolved S1, judgment, or description issues")
        errors.extend(validate_pass_evidence(text, case_count))
    return errors


def _validate_legacy_matrix(matrix: str) -> list[str]:
    """Pre-M/J/D reports (R1-R6, H1-H8) stay readable under their original rules."""
    errors: list[str] = []
    rows = _matrix_rows(matrix, r"R[1-6]|H[1-8]", errors)
    for key in LEGACY_MATRIX_IDS:
        if key not in rows:
            errors.append(f"review matrix {key}: row missing")
            continue
        result, metric, count = rows[key]
        if key == "H8":
            if result not in {"—", "-"}:
                errors.append("review matrix H8: result must be a dash; H8 has no pass/fail result")
            if not metric.strip() or PLACEHOLDER.search(metric):
                errors.append("review matrix H8: metric must be filled (list highlights or write 无)")
        else:
            if result not in MATRIX_STATUSES:
                errors.append(f"review matrix {key}: invalid result {result!r}")
            if _is_placeholder(metric) or not re.search(r"\d", metric):
                errors.append(f"review matrix {key}: metric must contain a non-placeholder quantitative value")
        if not re.fullmatch(r"\d+", count):
            errors.append(f"review matrix {key}: problem count must be a nonnegative integer, got {count!r}")
    return errors


def validate_review_execution(text: str) -> list[str]:
    """Check the single-pass execution record and any standalone GR entries; not review truth."""
    errors: list[str] = []

    def pending(value: str) -> bool:
        return not value.strip() or re.fullmatch(r"<[^>]*>|TODO|TBD|N/?A|待填写|待补充|占位|未填写|待确认|—|-|无", value.strip(), re.I) is not None

    def value(part: str, label: str, required: bool = True) -> str:
        matches = re.findall(rf"^[ \t]*\*\*{re.escape(label)}\*\*[ \t]*[:：][ \t]*([^\r\n]*)$", part, re.M)
        if not matches and not required:
            return ""
        if len(matches) != 1 or pending(matches[0]):
            errors.append(f"review execution: {label} must have one filled value")
            return ""
        return matches[0].strip()

    state = _review_state(value(text, "评审状态"))
    if state not in {"已完成", "未完成"}:
        errors.append("review execution: 评审状态 must be 已完成 or 未完成")
    value(text, "判定依据及限制")
    if state == "未完成":
        value(text, "未完成原因")
    bdd_raw = value(text, "BDD评审状态", required=False)
    if bdd_raw:
        bdd = _review_state(bdd_raw)
        if bdd not in {"已完成", "未完成"}:
            errors.append("review execution: invalid BDD评审状态")
        if state == "已完成" and bdd != "已完成":
            errors.append("review execution: incomplete BDD review cannot claim 评审状态 已完成")

    starts = list(re.finditer(r"^###\s+(GR-\d+)\b([^\n]*)$", text, re.M))
    seen: set[str] = set()
    for index, match in enumerate(starts):
        issue_id = match.group(1)
        if issue_id in seen:
            errors.append(f"review execution: duplicate {issue_id}")
        seen.add(issue_id)
        if not re.fullmatch(r"\s*[:：]\s*(Critical|High|Medium|Low)\s*", match.group(2)):
            errors.append(f"review execution: {issue_id} has invalid severity")
        next_heading = re.search(r"^#{1,3}\s+", text[match.end():], re.M)
        entry = text[match.end():match.end() + next_heading.start()] if next_heading else text[match.end():]
        for label in ("定位", "依据", "问题", "影响", "建议"):
            value(entry, label)
    count_text = value(text, "发现数", required=False)
    if count_text:
        if not re.fullmatch(r"\d+", count_text):
            errors.append("review execution: 发现数 must be a nonnegative integer")
        elif int(count_text) != len(starts):
            errors.append("review execution: 发现数 differs from GR entries")
        elif state == "已完成" and int(count_text) == 0 and "未发现实质性缺陷" not in text:
            errors.append("review execution: zero findings requires explicit 未发现实质性缺陷 conclusion")
    return errors


def validate_general_feedback(text: str) -> list[str]:
    """Deprecated alias kept for old eval scripts; checks the single-pass execution record."""
    return validate_review_execution(text)


def _review_section(text: str, dimension: str) -> str | None:
    """Text that may evidence one dimension: tagged issues plus its layer section, or a legacy ### section."""
    if DIMENSION_PATTERN.fullmatch(dimension):
        parts = [issue["body"] for issue in parse_issues(text) if issue["dimension"] == dimension]
        layer = re.search(rf"^##\s+{re.escape(LAYER_SECTIONS[dimension[0]])}\s*$", text, re.M)
        if layer:
            parts.append(_section_after(text, layer))
        return "\n".join(parts) if parts else None
    match = re.search(rf"^###\s+{re.escape(dimension)}\s*:", text, re.M)
    if not match:
        return None
    return _section_after(text, match, "###")


def validate_review_finding(text: str, dimension: str, identifier: str, severity: str | None, required_text: str) -> list[str]:
    """Check required report references and terms; this does not judge semantic adequacy."""
    expected = severity if severity else "an S1/S2/S3 severity"
    if DIMENSION_PATTERN.fullmatch(dimension):
        for issue in parse_issues(text):
            if issue["dimension"] != dimension or identifier not in issue["body"]:
                continue
            if (not severity or issue["severity"] == severity) and required_text in issue["body"]:
                return []
        return [f"review finding {identifier}: expected {expected} issue tagged [{dimension}] containing {required_text!r}"]
    section = _review_section(text, dimension)
    if section is None:
        return [f"review finding {identifier}: dimension {dimension} missing"]
    positions = [match.start() for match in re.finditer(re.escape(identifier), section)]
    for position in positions:
        window = section[max(0, position - 300):position + len(identifier) + 300]
        severity_matches = severity in window if severity else any(f"[{level}]" in window for level in ("S1", "S2", "S3"))
        if severity_matches and required_text in window:
            return []
    return [f"review finding {identifier}: expected {expected}, target evidence {required_text!r} in {dimension}"]


def validate_review_evidence(text: str, dimension: str, identifiers: list[str], required_text: list[str]) -> list[str]:
    """Check expected IDs and terms appear in one dimension; presence is not semantic proof."""
    section = _review_section(text, dimension)
    if section is None:
        return [f"review evidence: dimension {dimension} missing"]
    missing = [value for value in identifiers + required_text if value not in section]
    return [f"review evidence {dimension}: missing {value!r}" for value in missing]


def _context_from_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"<!--[ \t]*testspec-context\b(.*?)-->", text, flags=re.S)
    if len(matches) != 1:
        raise ValueError(f"{path}: expected exactly one testspec-context block")
    data = json.loads(matches[0].strip())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: testspec-context must be an object")
    return data


def _issue_details(report: Path, issue_id: str) -> tuple[str | None, str | None, str | None]:
    lines = report.read_text(encoding="utf-8").splitlines()
    finding_header = re.compile(r"^\s*[-*+]\s+(?:\[S[1-3]\]\s+)?\[(open|resolved|accepted)\](?:\s+\[S[1-3]\])?\s+")
    for index, line in enumerate(lines):
        header = finding_header.match(line)
        if not header or issue_id not in line:
            continue

        entry_lines = [line]
        for following in lines[index + 1:]:
            if finding_header.match(following) or re.match(r"^\s*#{1,6}\s+", following) or following.lstrip().startswith("<!-- testspec-context"):
                break
            entry_lines.append(following)

        entry = "\n".join(entry_lines)
        severities = set(re.findall(r"\[(S[1-3])\]", entry))
        severities.update(re.findall(r"(?:severity|严重度)\s*[:=：]\s*(S[1-3])\b", entry, flags=re.I))
        owners = set(re.findall(r"(?:\*\*)?\bowner(?:\*\*)?\s*[:=：]\s*([A-Za-z0-9_-]+)\b", entry, flags=re.I))
        severity = next(iter(severities)) if len(severities) == 1 else None
        owner = next(iter(owners)) if len(owners) == 1 else None
        return header.group(1), severity, owner
    return None, None, None


def validate_repair_cycle(accepted_report_path: Path, before_path: Path, after_path: Path, testpoints_path: Path,
                          reopened_path: Path, after_generate_path: Path, final_report_path: Path,
                          issue_id: str, case_id: str, field: str, required_text: str) -> list[str]:
    errors: list[str] = []
    try:
        before = _read_json(before_path)
        after = _read_json(after_path)
        before_cases = {case["id"]: case for case in before["testcases"]}
        after_cases = {case["id"]: case for case in after["testcases"]}
        reopened_text = reopened_path.read_text(encoding="utf-8")
        generated_report_text = after_generate_path.read_text(encoding="utf-8")
        accepted_context = _context_from_report(accepted_report_path)
        reopened_context = _context_from_report(reopened_path)
        generated_context = _context_from_report(after_generate_path)
        final_context = _context_from_report(final_report_path)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"repair cycle: {exc}"]

    if set(before_cases) != set(after_cases):
        errors.append("repair cycle: case IDs changed")
    if case_id not in before_cases or case_id not in after_cases:
        errors.append(f"repair cycle: target case {case_id} missing")
    else:
        for candidate_id in sorted(set(before_cases) & set(after_cases)):
            old, new = before_cases[candidate_id], after_cases[candidate_id]
            if candidate_id == case_id:
                old_other = {key: value for key, value in old.items() if key != field}
                new_other = {key: value for key, value in new.items() if key != field}
                if old_other != new_other:
                    errors.append(f"repair cycle: case_id={case_id} changed fields outside {field}")
                if old.get(field) == new.get(field) or required_text not in str(new.get(field, "")):
                    errors.append(f"repair cycle: case_id={case_id} field={field} was not repaired with expected text")
            elif old != new:
                errors.append(f"repair cycle: non-target case_id={candidate_id} changed")

    initial_hash = hashlib.sha256(before_path.read_bytes()).hexdigest()
    final_hash = hashlib.sha256(after_path.read_bytes()).hexdigest()
    testpoints_hash = hashlib.sha256(testpoints_path.read_bytes()).hexdigest()
    original_status, severity, owner = _issue_details(accepted_report_path, issue_id)
    if original_status != "accepted":
        errors.append(f"repair cycle: input issue {issue_id} must begin as accepted")
    if not severity or not owner:
        errors.append(f"repair cycle: accepted issue {issue_id} must declare severity and owner")
    if accepted_context.get("reviewed_artifacts", {}).get("testcases_sha256") != initial_hash:
        errors.append("repair cycle: accepted report does not reference the pre-repair testcase hash")
    if accepted_context.get("reviewed_artifacts", {}).get("testpoints_sha256") != testpoints_hash:
        errors.append("repair cycle: accepted report testpoints hash does not match the supplied file")
    accepted_gate = accepted_context.get("review_gate", {})
    gated_ids = list(accepted_gate.get("description_issue_ids", [])) + list(accepted_gate.get("judgment_issue_ids", []))
    if accepted_gate.get("status") != "blocked" or issue_id not in gated_ids:
        errors.append(f"repair cycle: accepted Review Gate must be blocked by {issue_id}")
    for label, path, context in (("reopen", reopened_path, reopened_context), ("post-generate", after_generate_path, generated_context)):
        status, actual_severity, actual_owner = _issue_details(path, issue_id)
        if status != "open":
            errors.append(f"repair cycle {label}: issue {issue_id} must be open under the same ID")
        if (actual_severity, actual_owner) != (severity, owner):
            errors.append(f"repair cycle {label}: issue severity and owner must remain {severity!r}/{owner!r}")
        gate = context.get("review_gate", {})
        if gate.get("status") != "blocked" or issue_id not in list(gate.get("description_issue_ids", [])) + list(gate.get("judgment_issue_ids", [])):
            errors.append(f"repair cycle {label}: Review Gate must remain blocked by {issue_id}")
        if context.get("reviewed_artifacts", {}).get("testcases_sha256") != initial_hash:
            errors.append(f"repair cycle {label}: report must still reference the pre-repair testcase hash")
        if context.get("reviewed_artifacts", {}).get("testpoints_sha256") != testpoints_hash:
            errors.append(f"repair cycle {label}: testpoints hash must match the supplied file")
    if reopened_text != generated_report_text:
        errors.append("repair cycle: Generate changed the reopened Review report or Gate")

    repairs = after.get("_context", {}).get("review_repairs", [])
    if not any(item.get("issue_id") == issue_id and item.get("changed_case_ids") == [case_id] for item in repairs if isinstance(item, dict)):
        errors.append(f"repair cycle: review_repairs must record {issue_id} and only {case_id}")
    final_status, final_severity, final_owner = _issue_details(final_report_path, issue_id)
    if final_status != "resolved":
        errors.append(f"repair cycle final Review: issue {issue_id} must be resolved under the same ID")
    if (final_severity, final_owner) != (severity, owner):
        errors.append(f"repair cycle final Review: issue severity and owner must remain {severity!r}/{owner!r}")
    reviewed_artifacts = final_context.get("reviewed_artifacts", {})
    if reviewed_artifacts.get("testcases_sha256") != final_hash:
        errors.append("repair cycle final Review: reviewed_artifacts testcase hash does not match final JSON")
    if reviewed_artifacts.get("testpoints_sha256") != testpoints_hash:
        errors.append("repair cycle final Review: reviewed_artifacts testpoints hash does not match the supplied file")
    gate = final_context.get("review_gate", {})
    s1_count = gate.get("s1_unresolved_count")
    s1_ids = gate.get("s1_issue_ids")
    description_count = gate.get("description_unresolved_count")
    description_ids = gate.get("description_issue_ids")
    judgment_count = gate.get("judgment_unresolved_count")
    judgment_ids = gate.get("judgment_issue_ids")
    valid_s1 = (
        type(s1_count) is int
        and s1_count >= 0
        and isinstance(s1_ids, list)
        and all(isinstance(item, str) and item.strip() for item in s1_ids)
        and len(set(s1_ids)) == len(s1_ids)
        and s1_count == len(s1_ids)
    )
    valid_description = (
        type(description_count) is int
        and description_count >= 0
        and isinstance(description_ids, list)
        and all(isinstance(item, str) and item.strip() for item in description_ids)
        and len(set(description_ids)) == len(description_ids)
        and description_count == len(description_ids)
    )
    valid_judgment = (
        type(judgment_count) is int
        and judgment_count >= 0
        and isinstance(judgment_ids, list)
        and all(isinstance(item, str) and item.strip() for item in judgment_ids)
        and len(set(judgment_ids)) == len(judgment_ids)
        and judgment_count == len(judgment_ids)
    )
    if not valid_s1 or not valid_judgment or not valid_description:
        errors.append("repair cycle final Review: Gate issue counts must match unique nonblank issue ID lists")
    if not (gate.get("status") == "pass" and valid_s1 and s1_count == 0 and s1_ids == []
            and valid_judgment and judgment_count == 0 and judgment_ids == []
            and valid_description and description_count == 0 and description_ids == []):
        errors.append("repair cycle final Review: Gate pass requires zero unresolved S1, judgment and description issues with empty ID lists")
    return errors


def _print_result(errors: list[str], success: str) -> int:
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {success}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    xmind_parser = subparsers.add_parser("xmind", help="compare a zipped XMind export with JSON cases")
    xmind_parser.add_argument("--json", required=True, type=Path)
    xmind_parser.add_argument("--xmind", required=True, type=Path)
    review_parser = subparsers.add_parser("review", help="check review matrix and execution record completeness, not semantic correctness")
    review_parser.add_argument("--report", required=True, type=Path)
    feedback_parser = subparsers.add_parser("feedback", help="deprecated alias: check only the review execution record")
    feedback_parser.add_argument("--report", required=True, type=Path)
    finding_parser = subparsers.add_parser("finding", help="check required Review report IDs, severity, and terms")
    finding_parser.add_argument("--report", required=True, type=Path)
    finding_parser.add_argument("--dimension", required=True)
    finding_parser.add_argument("--id", required=True)
    finding_parser.add_argument("--severity")
    finding_parser.add_argument("--contains", required=True)
    evidence_parser = subparsers.add_parser("evidence", help="check required Review report IDs and terms; not semantic correctness")
    evidence_parser.add_argument("--report", required=True, type=Path)
    evidence_parser.add_argument("--dimension", required=True)
    evidence_parser.add_argument("--id", action="append", default=[], dest="identifiers")
    evidence_parser.add_argument("--contains", action="append", default=[], dest="required_text")
    cycle_parser = subparsers.add_parser("repair-cycle", help="check a synthetic accepted-issue repair lifecycle")
    for option in ("accepted-report", "before", "after", "testpoints", "reopened-report", "post-generate-report", "final-report"):
        cycle_parser.add_argument(f"--{option}", required=True, type=Path)
    cycle_parser.add_argument("--issue-id", required=True)
    cycle_parser.add_argument("--case-id", required=True)
    cycle_parser.add_argument("--field", required=True)
    cycle_parser.add_argument("--contains", required=True)
    args = parser.parse_args()

    if args.command == "xmind":
        return _print_result(compare_xmind(args.json, args.xmind), "XMind JSON fields, order, hierarchy, and markers match")
    if args.command == "review":
        try:
            text = args.report.read_text(encoding="utf-8")
        except OSError as exc:
            return _print_result([str(exc)], "")
        return _print_result(validate_review_report(text) + validate_review_execution(text), "matrix and execution record are filled; semantic correctness is not assessed")
    if args.command == "feedback":
        try:
            text = args.report.read_text(encoding="utf-8")
        except OSError as exc:
            return _print_result([str(exc)], "")
        return _print_result(validate_review_execution(text), "review execution record is complete; semantic correctness and actual execution are not assessed")
    if args.command == "finding":
        try:
            text = args.report.read_text(encoding="utf-8")
        except OSError as exc:
            return _print_result([str(exc)], "")
        return _print_result(validate_review_finding(text, args.dimension, args.id, args.severity, args.contains), "required Review report references and terms are present; semantic adequacy is not assessed")
    if args.command == "evidence":
        try:
            text = args.report.read_text(encoding="utf-8")
        except OSError as exc:
            return _print_result([str(exc)], "")
        return _print_result(validate_review_evidence(text, args.dimension, args.identifiers, args.required_text), "required Review report references and terms are present; semantic adequacy is not assessed")
    errors = validate_repair_cycle(args.accepted_report, args.before, args.after, args.testpoints,
                                   args.reopened_report, args.post_generate_report, args.final_report,
                                   args.issue_id, args.case_id, args.field, args.contains)
    return _print_result(errors, "issue lifecycle, owner, severity, targeted repair, Gate, and both final hashes match")


if __name__ == "__main__":
    raise SystemExit(main())
