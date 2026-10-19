#!/usr/bin/env python
"""Verify raw datasets against pinned hashes and expected table shape (read-only).

Checks per dataset:
  1. every expected raw file exists and its SHA-256 equals the pinned hash;
  2. raw files are read-only (immutability guard);
  3. the primary table loads with the declared reader and has the expected
     row count and column names (or, for dirty/clean pairs, identical shapes).

Usage:
    python scripts/verify_datasets.py [dataset ...] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys

from dq_framework.acquisition import load_registry, verify
from dq_framework.datasets import check_table_shape


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--json", help="write the verification report to this path")
    args = ap.parse_args(argv)
    registry = load_registry()
    keys = args.datasets or list(registry)
    report = {}
    exit_code = 0
    for key in keys:
        spec = registry[key]
        res = verify(spec)
        if res["status"] != "FAIL":
            res["shape_check"] = check_table_shape(spec)
            if not res["shape_check"]["ok"]:
                res["status"] = "FAIL"
        if spec.manual and res["status"] == "FAIL":
            res["status"] = "BLOCKED"
        writable = [f["path"] for f in res["files"] if f.get("writable")]
        if writable:
            res.setdefault("warnings", []).append(f"raw files are writable (expected read-only): {writable}")
        report[key] = res
        print(f"[{res['status']}] {key}")
        for p in res["problems"] + res.get("warnings", []):
            print(f"    - {p}")
        if "shape_check" in res:
            print(f"    shape: {res['shape_check']['summary']}")
        if res["status"] == "FAIL":
            exit_code = 1
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
