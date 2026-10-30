#!/usr/bin/env python3
"""Prepare a read-only, neutral case/requirements copy for the standalone reviewer."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


CASE_FIELDS = (
    "id", "module", "submodule", "test_name", "preconditions", "test_data",
    "steps", "expected_result", "priority",
)
CONTEXT = re.compile(r"<!--\s*testspec-context\s*\{.*?\}\s*-->", re.DOTALL)


def fingerprint(path: Path, content: bytes) -> dict[str, str]:
    return {"name": path.name, "sha256": hashlib.sha256(content).hexdigest()}


def prepare(testcases: Path, requirements: list[Path]) -> dict:
    raw = testcases.read_bytes()
    data = json.loads(raw)
    cases = data.get("testcases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases or not all(isinstance(c, dict) for c in cases):
        raise ValueError("testcases must be a non-empty array of objects")
    sources = []
    for path in requirements:
        content = path.read_bytes()
        sources.append({**fingerprint(path, content), "content": CONTEXT.sub("", content.decode("utf-8"))})
    return {
        "case_source": fingerprint(testcases, raw),
        "requirements": sources,
        "testcases": [{key: case[key] for key in CASE_FIELDS if key in case} for case in cases],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testcases", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, action="append", default=[], help="UTF-8 text; repeat for multiple sources")
    parser.add_argument("--output", type=Path, help="New JSON file; refuses overwriting. Default: stdout")
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() in {p.resolve() for p in [args.testcases, *args.requirements]}:
            raise ValueError("output must not replace an input file")
        result = json.dumps(prepare(args.testcases, args.requirements), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(result)
        else:
            sys.stdout.write(result)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
