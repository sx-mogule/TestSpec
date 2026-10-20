#!/usr/bin/env python3
"""比较阶段输入的内容哈希；只读文件，不复制原文或自动跳过评审。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_testcases import _file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="本阶段实际使用的输入或规则文件")
    parser.add_argument("--previous", type=Path, help="上次输出的 JSON；没有时全部视为未读")
    args = parser.parse_args()
    try:
        current = {str(path): _file_digest(path) for path in sorted({p.resolve() for p in args.paths})}
        previous = {}
        if args.previous:
            previous = json.loads(args.previous.read_text(encoding="utf-8"))["fingerprints"]
            if not isinstance(previous, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in previous.items()):
                raise ValueError("旧摘要中的 fingerprints 必须是路径与哈希的映射")
        print(json.dumps({
            "fingerprints": current,
            "changed": [p for p, digest in current.items() if previous.get(p) != digest],
            "removed": [p for p in previous if p not in current],
            "unchanged": [p for p, digest in current.items() if previous.get(p) == digest],
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "message": f"无法核对输入：{exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
