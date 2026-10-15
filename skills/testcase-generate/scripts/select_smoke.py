#!/usr/bin/env python3
"""从通过完整校验和 Review 的用例集中选取 Smoke 执行集。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


SHARED_SCRIPTS = Path(__file__).resolve().parents[2] / "_testspec-shared/scripts"
sys.path.insert(0, str(SHARED_SCRIPTS))
import validate_context_chain as context_chain
import validate_testcases as testcase_validator


def artifact_hashes(change_dir: Path) -> dict[str, str]:
    return {
        "testcases_sha256": hashlib.sha256(
            (change_dir / "artifacts/testcases.json").read_bytes()
        ).hexdigest(),
        "testpoints_sha256": hashlib.sha256(
            (change_dir / "specs/testpoints.md").read_bytes()
        ).hexdigest(),
    }


def select_smoke(change_dir: Path) -> dict:
    change_dir = change_dir.resolve()
    cases_path = change_dir / "artifacts/testcases.json"
    points_path = change_dir / "specs/testpoints.md"
    output = change_dir / "artifacts/smoke-testcases.json"

    # 始终校验完整集，沿用现有阈值与 PASS 语义。
    validation = testcase_validator.validate(str(cases_path), str(points_path))
    if validation.get("status") != "PASS":
        raise ValueError("完整用例集尚未通过现有校验：" +
                         json.dumps(validation, ensure_ascii=False))

    errors = context_chain.validate(change_dir, "review", None)
    if errors:
        raise ValueError("完整链路上下文不一致：" + "; ".join(errors))
    review = context_chain.markdown_context(change_dir / "review-report.md")
    gate = review.get("review_gate", {})
    if (gate.get("status") != "pass" or gate.get("s1_unresolved_count") != 0
            or gate.get("s1_issue_ids") != []):
        raise ValueError("Review 门禁未通过，不能选取 Smoke 执行集")
    if review.get("stale_downstream_artifacts") != []:
        raise ValueError("Review 仍有过期产物，请先重新评审完整用例集")
    hashes = artifact_hashes(change_dir)
    if review.get("reviewed_artifacts") != hashes:
        raise ValueError("Review 缺少当前完整集与测试点的哈希，或文件已变化；请重新评审")

    data = json.loads(cases_path.read_text(encoding="utf-8"))
    if data.get("_context", {}).get("artifact_kind") == "smoke-execution-set":
        raise ValueError("artifacts/testcases.json 必须是完整集，不能使用 Smoke 执行集替代")
    selected = [case for case in data["testcases"]
                if case.get("regression_tier") == "Smoke"]
    if not selected:
        raise ValueError("完整集中没有 regression_tier=Smoke 的用例；请回到生成阶段确认并重新评审")
    if any(case.get("priority") != "p0" for case in selected):
        raise ValueError("Smoke 用例必须全部为 p0；请修正完整集并重新评审")
    if output.is_symlink():
        raise ValueError("Smoke 输出不能是符号链接，避免覆盖其他产物")

    context = {
        "artifact_kind": "smoke-execution-set",
        "source_artifact": "artifacts/testcases.json",
        "source_review": "review-report.md",
        "reviewed_artifacts": hashes,
        "selection_rule": "regression_tier=Smoke",
        "selected_case_ids": [case["id"] for case in selected],
        "selected_tp_ids": sorted({ref for case in selected for ref in case["tp_refs"]}),
        "full_set_validation": {
            "status": validation["status"],
            "coverage": validation["coverage"],
            "case_count": len(data["testcases"]),
        },
        "full_set_review_gate": gate,
    }
    source_revision = data.get("_context", {}).get("source_revision")
    if source_revision is not None:
        context["source_revision"] = source_revision
    payload = {"schema_version": 2, "_context": context, "testcases": selected}
    # 同一目录内原子替换，保留旧输出直到新内容完整写入。
    with tempfile.TemporaryDirectory(prefix=".smoke-", dir=output.parent) as directory:
        temporary = Path(directory) / "testcases.json"
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    return {
        "status": "PASS", "output": str(output),
        "full_case_count": len(data["testcases"]), "smoke_case_count": len(selected),
        "full_set_coverage": validation["coverage"],
        "selected_case_ids": context["selected_case_ids"],
        "selected_tp_ids": context["selected_tp_ids"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = select_smoke(args.change_dir)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        print(json.dumps({"status": "FAIL", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
