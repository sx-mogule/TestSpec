#!/usr/bin/env python3
"""
testcases.json 自检工具 —— Agent 生成用例后自主调用，返回结构化 JSON 结果。

用途：
- 格式合规检查（必填字段、枚举值、编号格式）
- 明确含糊的步骤和预期检查；关键结果覆盖由 Review 复核
- 内容重复检查和相似用例复核候选
- 覆盖度报告（对照当前变更的 testpoints.md 中的 TP_ID）
- 优先级/类型分布统计

约定：
- `id` 视为用例的源编号（source id），由生成阶段写入，用于当前变更追溯
- `tp_refs` 只校验当前变更工作区中的测试点追溯关系，不承担跨变更唯一性语义

返回 JSON 格式结果，Agent 据此决定是否自动修复。

用法:
    python validate_testcases.py --input testcases.json [--testpoints specs/testpoints.md]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "module", "submodule", "test_name", "preconditions", "test_data",
    "steps", "expected_result", "priority",
}
OPTIONAL_VALUE_FIELDS = {"preconditions", "test_data"}
VALID_PRIORITIES = {"p0", "p1", "p2"}
VALID_TYPES = {"冒烟", "正向", "负向", "边界", "异常", "其他", "埋点", "兼容性矩阵"}
SPECIAL_TP_SECTION_TYPES = {
    "埋点验证点 (Tracking)": "埋点",
    "兼容性矩阵验证点 (Compatibility)": "兼容性矩阵",
}
ACTION_VERBS = [
    "点击", "输入", "选择", "等待", "查看", "校验",
    "打开", "提交", "确认", "删除", "修改", "搜索",
    "上传", "下载", "切换", "拖拽", "长按", "滑动",
]
SIMILARITY_THRESHOLD = 0.75
TP_ENTRY_PATTERN = re.compile(
    r"^[ \t]*[-*][ \t]+(TP_[A-Z0-9]+_[A-Z0-9_]+_[0-9]+)[ \t]*[:：]",
    re.MULTILINE,
)


# ── 工具函数 ──────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """去除空白和标点，用于相似度比较。"""
    return re.sub(r"[\s\d、.。，,；;：:！!？?（）()\[\]【】{}\"'""'']+", "", text)


def _simple_similarity(a: str, b: str) -> float:
    """基于字符级 Jaccard 的简单相似度。"""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    sa, sb = set(na), set(nb)
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / union if union else 0.0


def _content_lines(text: str, *, numbered: bool = True) -> list[str]:
    """去掉行首编号和空白，保留正文中的数值、单位和顺序。"""
    if text is None:
        return []
    if not isinstance(text, str):
        return [json.dumps(text, ensure_ascii=False, sort_keys=True)]
    lines = []
    for line in text.splitlines():
        if numbered:
            line = re.sub(r"^[ \t]*\d+(?:、|\.(?!\d))[ \t]*", "", line)
        if line.strip():
            lines.append(line.strip())
    return lines


def _comparison_fields(case: dict) -> dict[str, str]:
    """比较实际内容，不用标题、优先级或 TP 编号代替业务差异。"""
    return {
        "module": case.get("module") or case.get("feature", ""),
        "submodule": case.get("submodule", ""),
        **{
            field: "\n".join(_content_lines(value, numbered=field != "test_data"))
            for field, value in {
                "preconditions": case.get("preconditions", ""),
                "test_data": case.get("test_data", ""),
                "steps": case.get("steps", ""),
                "expected_result": case.get("expected_result") or case.get("expected", ""),
            }.items()
        },
    }


def _extract_tp_ids_from_md(md_text: str) -> set[str]:
    """只统计正式测试点条目，不把说明、引用或模板字段计入覆盖率。"""
    return set(TP_ENTRY_PATTERN.findall(md_text))


def check_design_methods(data: dict, cases: list[dict], tp_text: str) -> list[dict]:
    """核对已覆盖 TP 的方法名是否进入生成阶段上下文。"""
    methods_by_tp: dict[str, set[str]] = {}
    listed_tps: set[str] = set()
    current_tp = None
    for line in tp_text.splitlines():
        tp_match = TP_ENTRY_PATTERN.match(line)
        if tp_match:
            current_tp = tp_match.group(1)
            listed_tps.add(current_tp)
            continue
        method_match = re.match(r"^\s*-\s*设计方法\s*[:：]\s*(.+)$", line)
        if current_tp and method_match:
            names = {
                name.strip() for name in re.split(r"[、,，]", method_match.group(1)) if name.strip()
            }
            if names:
                methods_by_tp[current_tp] = names
    if not methods_by_tp:
        return []  # 兼容未标方法的旧测试点

    methods_doc = Path(__file__).resolve().parents[2] / "test-points/references/test-design-methods.md"
    allowed = {
        title.split("（", 1)[0].strip()
        for title in re.findall(r"^## \d+\.\s+(.+)$", methods_doc.read_text(encoding="utf-8"), re.MULTILINE)
    }
    declared = set().union(*methods_by_tp.values())
    errors = []
    missing_tp_methods = sorted(listed_tps - methods_by_tp.keys())
    if missing_tp_methods:
        errors.append({"type": "MISSING_TP_DESIGN_METHOD", "severity": "error",
                       "tp_ids": missing_tp_methods, "fix_hint": "每个 TP 均须标注一种或多种正式设计方法"})
    unknown = sorted(declared - allowed)
    if unknown:
        errors.append({"type": "UNKNOWN_DESIGN_METHOD", "severity": "error",
                       "methods": unknown, "fix_hint": "测试点设计方法须来自十二种正式方法，辅助策略不写入设计方法"})

    point_context = re.findall(r"<!--\s*testspec-context\s*(\{.*?\})\s*-->", tp_text, re.DOTALL)
    if point_context:
        try:
            point_methods = json.loads(point_context[-1]).get("design_methods")
        except json.JSONDecodeError:
            point_methods = None
        if (
            not isinstance(point_methods, list)
            or any(not isinstance(name, str) for name in point_methods)
            or set(point_methods) != declared
        ):
            errors.append({"type": "TESTPOINT_METHOD_CONTEXT_MISMATCH", "severity": "error",
                           "fix_hint": "testpoints.md 上下文方法名须与各 TP 的设计方法一致"})

    covered = {
        ref for case in cases
        for ref in (case.get("tp_refs") if isinstance(case.get("tp_refs"), list) else [])
        if isinstance(ref, str)
    }
    expected = set().union(*(names for tp, names in methods_by_tp.items() if tp in covered))
    context = data.get("_context")
    actual = context.get("design_methods") if isinstance(context, dict) else None
    if not isinstance(actual, list) or any(not isinstance(name, str) for name in actual):
        errors.append({"type": "MISSING_DESIGN_METHODS", "severity": "error",
                       "fix_hint": "在 testcases.json._context.design_methods 记录已覆盖 TP 的方法名"})
    else:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        if missing or extra:
            errors.append({"type": "DESIGN_METHOD_MISMATCH", "severity": "error",
                           "missing": missing, "extra": extra,
                           "fix_hint": "生成阶段方法名须与已生成用例所引用 TP 的设计方法一致，且只使用十二种正式方法"})
    return errors


# ── 校验函数 ──────────────────────────────────────────────────────

def check_required_fields(cases: list[dict]) -> list[dict]:
    """检查必填字段是否存在且非空。"""
    issues = []
    for tc in cases:
        missing = []
        for field in REQUIRED_FIELDS:
            if field not in tc:
                missing.append(field)
                continue
            val = tc.get(field, "")
            if field not in OPTIONAL_VALUE_FIELDS and (not val or (isinstance(val, str) and not val.strip())):
                missing.append(field)
        if missing:
            issues.append({
                "type": "MISSING_FIELD",
                "severity": "error",
                "case_id": tc.get("id", "UNKNOWN"),
                "title": tc.get("title", ""),
                "fields": missing,
                "fix_hint": f"补充以下字段: {', '.join(missing)}",
            })
    return issues


def check_field_quality(cases: list[dict]) -> list[dict]:
    """检查动作和明确含糊的表达，不按字数判断质量。"""
    issues = []
    vague_step = re.compile(r"(?:(?:进行|执行|完成)(?:相关|上述|必要)?操作|操作|点击|输入|选择)")
    vague_expected = re.compile(
        r"(?:(?:系统|页面|功能|操作|结果|显示|提示|保存|提交|执行|处理)\s*)*"
        r"(?:正常|成功|正确|符合预期|无异常)(?:显示|展示|完成)?"
    )

    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("test_name") or tc.get("title", "")

        steps = tc.get("steps", "")
        # 步骤中是否有动作动词
        if steps and not any(v in steps for v in ACTION_VERBS):
            issues.append({
                "type": "NO_ACTION_VERB",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "fix_hint": "写清要做什么，如「点击保存」或「输入测试数据中的手机号」。",
            })

        for index, line in enumerate(_content_lines(steps), 1):
            if vague_step.fullmatch(line.rstrip("。.!！；;")) and any(v in steps for v in ACTION_VERBS):
                issues.append({
                    "type": "VAGUE_STEP", "severity": "warning",
                    "case_id": case_id, "title": title, "line_number": index,
                    "fix_hint": "写清这一行的动作和对象，不用「进行操作」等泛称。",
                })

        expected = tc.get("expected_result", "") or tc.get("expected", "")
        for index, line in enumerate(_content_lines(expected), 1):
            if vague_expected.fullmatch(line.rstrip("。.!！；;")):
                issues.append({
                    "type": "VAGUE_EXPECTED",
                    "severity": "warning",
                    "case_id": case_id,
                    "title": title,
                    "line_number": index,
                    "fix_hint": "写清可观察的状态、值或文案，不只写「正常」「成功」「符合预期」。",
                })

    return issues


def check_enum_values(cases: list[dict]) -> list[dict]:
    """检查枚举字段值是否合法。"""
    issues = []
    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("test_name") or tc.get("title", "")

        priority = tc.get("priority", "")
        if priority and priority not in VALID_PRIORITIES:
            issues.append({
                "type": "INVALID_PRIORITY",
                "severity": "error",
                "case_id": case_id,
                "title": title,
                "value": priority,
                "valid_values": sorted(VALID_PRIORITIES),
                "fix_hint": f"优先级 '{priority}' 不合法，应为 p0/p1/p2",
            })

        tc_type = tc.get("type", "")
        if tc_type and tc_type not in VALID_TYPES:
            issues.append({
                "type": "INVALID_TYPE",
                "severity": "error",
                "case_id": case_id,
                "title": title,
                "value": tc_type,
                "valid_values": sorted(VALID_TYPES),
                "fix_hint": f"用例类型 '{tc_type}' 不在标准列表中",
            })

    return issues


def check_special_scope_type_matches(cases: list[dict], tp_text: str) -> list[dict]:
    """Require tracking/compatibility cases to reference only their explicit TP section."""
    tp_categories: dict[str, set[str]] = {}
    current_category = None
    current_heading_level = None

    for line in tp_text.splitlines():
        heading_match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            if current_heading_level is not None and level <= current_heading_level:
                current_category = None
                current_heading_level = None
            category = SPECIAL_TP_SECTION_TYPES.get(title)
            if category:
                current_category = category
                current_heading_level = level
            continue

        if current_category:
            tp_match = TP_ENTRY_PATTERN.match(line)
            if tp_match:
                tp_categories.setdefault(tp_match.group(1), set()).add(current_category)

    issues = []
    for case in cases:
        case_type = case.get("type", "")
        refs = case.get("tp_refs") if isinstance(case.get("tp_refs"), list) else []
        if case_type in {"埋点", "兼容性矩阵"}:
            mismatched = sorted(
                (
                    ref for ref in refs
                    if not isinstance(ref, str) or tp_categories.get(ref) != {case_type}
                ),
                key=lambda ref: str(ref),
            )
            if mismatched:
                issues.append({
                    "type": "CASE_TYPE_TP_CATEGORY_MISMATCH",
                    "severity": "error",
                    "case_id": case.get("id", "UNKNOWN"),
                    "case_type": case_type,
                    "tp_ids": mismatched,
                    "fix_hint": f"type={case_type} 的用例只能引用对应的专属测试点分类",
                })
            continue

        special_refs = sorted(ref for ref in refs if isinstance(ref, str) and ref in tp_categories)
        if special_refs:
            issues.append({
                "type": "CASE_TYPE_TP_CATEGORY_MISMATCH",
                "severity": "error",
                "case_id": case.get("id", "UNKNOWN"),
                "case_type": case_type,
                "tp_ids": special_refs,
                "fix_hint": "埋点与兼容性矩阵测试点必须分别使用 type=埋点 或 type=兼容性矩阵，不可用 type=其他 绕过",
            })

    return issues


def check_naming_contract(cases: list[dict]) -> list[dict]:
    """检查新字段是否存在，并兼容检查旧 title/feature 的三段式命名。"""
    issues = []
    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("test_name") or tc.get("title", "")
        feature = tc.get("module") or tc.get("feature", "")

        if not title:
            continue

        parts = title.split("_")
        if len(parts) < 3:
            issues.append({
                "type": "NAMING_FORMAT",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "fix_hint": "测试名称建议为 {模块}_{功能点}_{场景} 三段式",
            })
        elif feature and parts[0] != feature:
            issues.append({
                "type": "NAMING_FEATURE_MISMATCH",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "feature": feature,
                "title_module": parts[0],
                "fix_hint": f"测试名称前缀 '{parts[0]}' 与模块 '{feature}' 不一致",
            })

    return issues


def check_duplicates(cases: list[dict]) -> list[dict]:
    """兼容返回完整逐对结果；命令行按组摘要并将明细写入本地。"""
    return list(iter_duplicate_issues(cases))


def iter_duplicate_issues(cases: list[dict]):
    """只比较同组用例，复用文本集合和内容分组，不改变判定条件。"""
    fields = [_comparison_fields(case) for case in cases]
    groups = defaultdict(list)
    content_groups = {}
    content_ids = []
    text_sets = {}

    def tokens(text):
        text = text if isinstance(text, str) else ""
        if text not in text_sets:
            text_sets[text] = frozenset(_normalize(text))
        return text_sets[text]

    titles = [tokens(case.get("test_name") or case.get("title", "")) for case in cases]
    steps = [tokens(case.get("steps", "")) for case in cases]
    for index, field in enumerate(fields):
        key = tuple(field.items())
        content_ids.append(content_groups.setdefault(key, len(content_groups)))
        if field["steps"] and field["expected_result"]:
            groups[(field["module"], field["submodule"])].append(index)

    def similarity(left, right):
        if not left or not right:
            return 0.0
        common = len(left & right)
        return common / (len(left) + len(right) - common)

    for indices in groups.values():
        for i, j in combinations(indices, 2):
            left, right = fields[i], fields[j]
            exact = content_ids[i] == content_ids[j]
            if not exact:
                title_sim = similarity(titles[i], titles[j])
                if title_sim <= 0.8:
                    continue
                steps_sim = similarity(steps[i], steps[j])
                if steps_sim <= SIMILARITY_THRESHOLD:
                    continue
            common = {
                "case_ids": [cases[i].get("id", f"index-{i}"), cases[j].get("id", f"index-{j}")],
                "titles": [cases[i].get("test_name") or cases[i].get("title", ""),
                           cases[j].get("test_name") or cases[j].get("title", "")],
            }
            if exact:
                yield {
                    **common, "type": "DUPLICATE", "severity": "warning",
                    "fix_hint": "前置条件、数据、步骤和预期相同。请确认是否重复，再决定合并。",
                }
            else:
                yield {
                    **common, "type": "SIMILAR_CASES", "severity": "info",
                    "different_fields": [field for field in left if left[field] != right[field]],
                    "title_similarity": round(title_sim, 2),
                    "steps_similarity": round(steps_sim, 2),
                    "fix_hint": "比较条件、数据、边界位置和预期。有必要差异就保留，不用改写标题避开相似度。",
                }


class _DuplicateGroups:
    """按实际候选边归组；组内未相连的成员不被当成相似对。"""

    def __init__(self):
        self.parent = {}
        self.count = {}
        self.differences = {}

    def find(self, node):
        self.parent.setdefault(node, node)
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while node != root:
            parent = self.parent[node]
            self.parent[node] = root
            node = parent
        return root

    def add(self, issue):
        nodes = [(issue["type"], case_id) for case_id in issue["case_ids"]]
        left, right = map(self.find, nodes)
        if left != right:
            self.parent[right] = left
            self.count[left] = self.count.get(left, 0) + self.count.pop(right, 0)
            self.differences.setdefault(left, set()).update(self.differences.pop(right, set()))
        self.count[left] = self.count.get(left, 0) + 1
        self.differences.setdefault(left, set()).update(issue.get("different_fields", []))

    def results(self):
        members = defaultdict(list)
        for node in self.parent:
            members[self.find(node)].append(node[1])
        results = []
        for root, ids in members.items():
            exact = root[0] == "DUPLICATE"
            results.append({
                "type": root[0], "severity": "warning" if exact else "info",
                "case_ids": ids,
                "pair_count": self.count[root],
                "different_fields": sorted(self.differences[root]),
                "fix_hint": "读取逐对明细，核对所有成员；同组不表示任意两条都重复或相似。",
            })
        return results


def _duplicate_summary(cases, details_path):
    """逐行保存完整明细，内存中只保留候选组。"""
    path = Path(details_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    groups = _DuplicateGroups()
    counts = Counter()
    digest = hashlib.sha256()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            for issue in iter_duplicate_issues(cases):
                line = (json.dumps(issue, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                stream.write(line)
                digest.update(line)
                groups.add(issue)
                counts[issue["type"]] += 1
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return groups.results(), {
        "path": str(path.resolve()), "format": "jsonl", "sha256": digest.hexdigest(),
        "pair_count": sum(counts.values()),
        "duplicate_pair_count": counts["DUPLICATE"],
        "similar_pair_count": counts["SIMILAR_CASES"],
    }


def check_tp_coverage(cases: list[dict], tp_ids: set[str]) -> dict:
    """检查当前变更内 testcases 对 testpoints 的覆盖度。"""
    if not tp_ids:
        return {
            "available": False,
            "reason": "未提供 testpoints.md 或未找到 TP_ID",
        }

    covered = set()
    for tc in cases:
        refs = tc.get("tp_refs", [])
        if isinstance(refs, list):
            covered.update(refs)

    uncovered = sorted(tp_ids - covered)
    coverage_rate = len(tp_ids - set(uncovered)) / len(tp_ids) if tp_ids else 0

    return {
        "available": True,
        "total_tp": len(tp_ids),
        "covered_tp": len(tp_ids) - len(uncovered),
        "coverage_rate": round(coverage_rate, 4),
        "uncovered": uncovered,
        "pass": coverage_rate >= 0.95,
    }


def compute_distribution(cases: list[dict]) -> dict:
    """计算优先级和类型分布。"""
    total = len(cases)
    priority_counter = Counter(str(tc.get("priority", "UNKNOWN")).lower() for tc in cases)
    type_counter = Counter(tc.get("type", "UNKNOWN") for tc in cases)
    smoke_count = sum(1 for tc in cases if tc.get("type") == "冒烟")

    distribution = {
        "total": total,
        "priority": {k: {"count": v, "ratio": round(v / total, 2) if total else 0}
                     for k, v in sorted(priority_counter.items())},
        "type": {k: {"count": v, "ratio": round(v / total, 2) if total else 0}
                 for k, v in sorted(type_counter.items())},
        "smoke": {
            "count": smoke_count,
            "ratio": round(smoke_count / total, 2) if total else 0,
            "all_p0": all(
                str(tc.get("priority", "")).lower() == "p0"
                for tc in cases
                if tc.get("type") == "冒烟"
            ),
        },
    }

    # 分布异常检测（只检测极端异常信号，不设固定比例目标）
    warnings = []
    p0_ratio = priority_counter.get("p0", 0) / total if total else 0
    p2_ratio = priority_counter.get("p2", 0) / total if total else 0
    distinct_priorities = len([k for k in priority_counter if k in VALID_PRIORITIES])
    if total > 5:  # 用例太少时不检查比例
        if distinct_priorities < 2:
            warnings.append(f"只有单一优先级 {list(priority_counter.keys())}，缺乏优先级区分")
        if p0_ratio > 0.80:
            warnings.append(f"p0 占比 {p0_ratio:.0%} 过高（>80%），可能缺乏优先级区分")
        if p2_ratio > 0.50:
            warnings.append(f"p2 占比 {p2_ratio:.0%} 过高（>50%），可能低估了核心功能的重要性")

    distribution["warnings"] = warnings
    return distribution


# ── 主流程 ──────────────────────────────────────────────────────

def validate(testcases_path: str, testpoints_path: str | None = None, *, details_path: str | None = None) -> dict:
    """执行全量校验，返回结构化 JSON 结果。"""

    # 加载 testcases.json
    tc_path = Path(testcases_path)
    if not tc_path.exists():
        return {"status": "ERROR", "message": f"文件不存在: {testcases_path}"}

    try:
        data = json.loads(tc_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"status": "ERROR", "message": f"JSON 解析失败: {e}"}

    if not isinstance(data, dict) or data.get("schema_version") != 2 or not isinstance(data.get("testcases"), list):
        return {"status": "ERROR", "message": "用例必须是包含 schema_version=2 和 testcases 数组的对象"}
    cases = data["testcases"]
    if not cases or not all(isinstance(case, dict) for case in cases):
        return {"status": "ERROR", "message": "testcases 为空或包含非对象用例"}

    # 加载 testpoints（可选）
    tp_ids: set[str] = set()
    if testpoints_path:
        tp_path = Path(testpoints_path)
        if not tp_path.is_file():
            return {"status": "ERROR", "message": f"测试点文件不存在: {testpoints_path}"}
        tp_text = tp_path.read_text(encoding="utf-8")
        tp_ids = _extract_tp_ids_from_md(tp_text)
        if not tp_ids:
            return {"status": "ERROR", "message": "测试点文件未定义 TP_ID"}

    # 执行所有检查
    errors = []
    warnings = []
    review_candidates = []

    ids = [case.get("id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id.strip() for case_id in ids) or len(ids) != len(set(ids)):
        errors.append({"type": "INVALID_CASE_ID", "severity": "error",
                       "fix_hint": "每条用例须有非空且在当前变更内唯一的 id"})
    if testpoints_path:
        for case in cases:
            refs = case.get("tp_refs")
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in tp_ids for ref in refs):
                errors.append({"type": "INVALID_TP_REFS", "severity": "error",
                               "case_id": case.get("id", "UNKNOWN"),
                               "fix_hint": "tp_refs 必须非空且只引用当前测试点"})
        errors.extend(check_special_scope_type_matches(cases, tp_text))
    else:
        for case in cases:
            if case.get("type") in {"埋点", "兼容性矩阵"}:
                errors.append({
                    "type": "SPECIAL_CASE_TYPE_REQUIRES_TESTPOINTS",
                    "severity": "error",
                    "case_id": case.get("id", "UNKNOWN"),
                    "case_type": case.get("type"),
                    "fix_hint": "埋点与兼容性矩阵用例必须提供 testpoints.md 以校验对应分类和 TP 引用",
                })
    for case in cases:
        if case.get("type") == "冒烟" and case.get("priority") != "p0":
            errors.append({"type": "SMOKE_NOT_P0", "severity": "error",
                           "case_id": case.get("id", "UNKNOWN"),
                           "fix_hint": "冒烟用例必须为 p0"})

    if testpoints_path and tp_path.exists() and re.search(r"(?:Non-Functional|非功能性验证点)", tp_text, re.IGNORECASE):
        errors.append({"type": "NON_FUNCTIONAL_TESTPOINT", "severity": "error",
                       "fix_hint": "本流程仅接收允许范围内的测试点；移除泛非功能分支，保留功能、埋点或兼容性矩阵专属分类"})

    if testpoints_path:
        errors.extend(check_design_methods(data, cases, tp_text))

    for issue in check_required_fields(cases):
        (errors if issue["severity"] == "error" else warnings).append(issue)

    for issue in check_enum_values(cases):
        (errors if issue["severity"] == "error" else warnings).append(issue)

    for issue in check_naming_contract(cases):
        warnings.append(issue)

    for issue in check_field_quality(cases):
        warnings.append(issue)

    details = None
    if details_path is None:
        duplicate_issues = check_duplicates(cases)
    else:
        duplicate_issues, details = _duplicate_summary(cases, details_path)
    for issue in duplicate_issues:
        (review_candidates if issue["severity"] == "info" else warnings).append(issue)

    # 覆盖度
    coverage = check_tp_coverage(cases, tp_ids)
    if coverage.get("available") and not coverage["pass"]:
        errors.append({"type": "TP_COVERAGE_BELOW_THRESHOLD", "severity": "error",
                       "uncovered": coverage["uncovered"], "coverage_rate": coverage["coverage_rate"],
                       "fix_hint": "允许范围内的测试点覆盖率必须达到 95%"})

    # 分布
    distribution = compute_distribution(cases)

    # 汇总
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")

    result = {
        "status": status,
        "summary": {
            "total_cases": len(cases),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "review_candidate_count": len(review_candidates),
        },
        "errors": errors,
        "warnings": warnings,
        "review_candidates": review_candidates,
        "coverage": coverage,
        "distribution": distribution,
    }
    if details is not None:
        result["duplicate_details"] = details
        exact_groups = sum(issue["type"] == "DUPLICATE" for issue in duplicate_issues)
        result["summary"].update(
            warning_count=len(warnings) - exact_groups + details["duplicate_pair_count"],
            review_candidate_count=details["similar_pair_count"],
            review_candidate_group_count=len(review_candidates),
        )
    return result


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validation_manifest(testcases_path, testpoints_path):
    """使用内容哈希识别输入和规则变化，不仅依赖版本号或修改时间。"""
    source = Path(testcases_path).resolve()
    change = source.parent.parent if source.parent.name == "artifacts" else source.parent
    rules = Path(__file__).resolve().parents[2]
    paths = {source, Path(__file__).resolve(), *rules.rglob("*.md")}
    if testpoints_path:
        paths.add(Path(testpoints_path).resolve())
    # canonical 或分析内容变化后，即使版本号未更新也不复用旧检查结果。
    for name in ("requirements.md", "proposal.md", "requirements-analysis.md"):
        path = change / name
        if path.exists():
            paths.add(path)
    return {
        str(path): _file_digest(path)
        for path in sorted(paths)
    }


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _result_digest(result):
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def validate_report(testcases_path, testpoints_path=None, *, report_dir=None, use_cache=True):
    """命令行使用按组摘要；保留完整逐对明细，缓存只复用确定性检查。"""
    source = Path(testcases_path).resolve()
    change = source.parent.parent if source.parent.name == "artifacts" else source.parent
    try:
        manifest = _validation_manifest(testcases_path, testpoints_path)
    except OSError:
        return validate(testcases_path, testpoints_path)
    key = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()
    directory = Path(report_dir) if report_dir else change / ".testspec-cache" / "validation"
    report_path = directory / key / "result.json"
    details_path = directory / key / "pairs.jsonl"
    if use_cache:
        try:
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            result = saved["result"]
            details = result["duplicate_details"]
            if (saved["key"] == key and saved["result_sha256"] == _result_digest(result)
                    and details["path"] == str(details_path.resolve())
                    and _file_digest(details_path) == details["sha256"]):
                return {**result, "cache": {"hit": True, "key": key}}
        except (OSError, ValueError, KeyError, TypeError):
            pass  # 缓存损坏、缺失或明细不完整时重新校验。
    try:
        result = validate(testcases_path, testpoints_path, details_path=str(details_path))
        if manifest != _validation_manifest(testcases_path, testpoints_path):
            return {"status": "ERROR", "message": "校验期间输入或规则发生变化，请重跑。"}
        if use_cache and result.get("status") in {"PASS", "WARN", "FAIL"}:
            _atomic_json(report_path, {"key": key, "result_sha256": _result_digest(result), "result": result})
        return {**result, "cache": {"hit": False, "key": key}}
    except OSError as exc:
        return {"status": "ERROR", "message": f"输入读取或检查结果写入失败：{exc}。请检查输入及 --report-dir；只读检查可用 --full。"}


def main() -> int:
    parser = argparse.ArgumentParser(description="TestSpec 用例自检工具")
    parser.add_argument("--input", required=True, help="testcases.json 路径")
    parser.add_argument("--testpoints", default=None, help="testpoints.md 路径（可选）")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    parser.add_argument("--full", action="store_true", help="输出完整逐对结果，不创建缓存或明细文件")
    parser.add_argument("--no-cache", action="store_true", help="重新校验，不复用或保存结果缓存；仍保存逐对明细")
    parser.add_argument("--report-dir", help="内部明细和缓存目录；默认位于变更目录的 .testspec-cache/validation")
    args = parser.parse_args()

    result = validate(args.input, args.testpoints) if args.full else validate_report(
        args.input, args.testpoints, report_dir=args.report_dir, use_cache=not args.no_cache,
    )

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
