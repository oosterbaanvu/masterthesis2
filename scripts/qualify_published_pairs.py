#!/usr/bin/env python3
"""Audit published dirty/clean pairs without treating every difference as a true error.

Usage after registering and downloading the datasets:
  python scripts/qualify_published_pairs.py
  python scripts/qualify_published_pairs.py raha_rayyan jung_restaurant jung_cars --output data/local_pair_audit.json

Reads source files unchanged. No error injection, no model access to clean test values.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from pathlib import Path
from typing import Any

DEFAULT_KEYS = ("raha_rayyan", "jung_restaurant", "jung_cars")


def numerically_equivalent(a: str, b: str) -> bool:
    """Compare numeric data semantically; only call on explicitly declared numeric columns."""
    try:
        x, y = Decimal(a.strip()), Decimal(b.strip())
    except (InvalidOperation, ValueError):
        return False
    return x.is_finite() and y.is_finite() and x == y


def compare_pair(dirty_path: Path, clean_path: Path, *, numeric_columns: tuple[str, ...] = (),
                 alignment_columns: tuple[str, ...] = (), positional_headers: bool = False) -> dict[str, Any]:
    """Stream published row-aligned CSVs; check shape and any declared unchanged row anchors."""
    with dirty_path.open(encoding="utf-8-sig", newline="") as fd, clean_path.open(encoding="utf-8-sig", newline="") as fc:
        d, c = csv.reader(fd, strict=True), csv.reader(fc, strict=True)
        dh, ch = next(d, []), next(c, [])
        if not dh or not ch:
            raise ValueError("Both CSV files must have a header")
        if len(dh) != len(ch) or (dh != ch and not positional_headers):
            raise ValueError(f"Incompatible columns: dirty={dh!r}; clean={ch!r}")
        if len(set(dh)) != len(dh) or len(set(ch)) != len(ch):
            raise ValueError("Duplicated column names need manual mapping")
        unknown = (set(numeric_columns) | set(alignment_columns)) - set(dh)
        if unknown:
            raise ValueError(f"Unknown comparison columns: {sorted(unknown)}")
        numeric_idx = {i for i, col in enumerate(dh) if col in numeric_columns}
        alignment_idx = {i for i, col in enumerate(dh) if col in alignment_columns}
        raw, numerical_format_only, rows = Counter(), Counter(), 0
        examples: dict[str, list[dict[str, str | int]]] = {}
        changed_rows = 0
        for ri, (dr, cr) in enumerate(zip_longest(d, c), start=1):
            if dr is None or cr is None:
                raise ValueError(f"Unequal row count at row {ri}; pair cannot be aligned")
            if len(dr) != len(dh) or len(cr) != len(ch):
                raise ValueError(f"Unequal row width at row {ri}")
            if any(dr[j] != cr[j] for j in alignment_idx):
                raise ValueError(f"Row alignment differs at row {ri}")
            row_different = False
            for j, (a, b) in enumerate(zip(dr, cr, strict=True)):
                if a == b:
                    continue
                col = dh[j]
                raw[col] += 1
                row_different = True
                if j in numeric_idx and numerically_equivalent(a, b):
                    numerical_format_only[col] += 1
                elif len(examples.setdefault(col, [])) < 3:
                    examples[col].append({"row": ri, "dirty": a[:160], "clean": b[:160]})
            rows += 1
            changed_rows += row_different
    changed = sum(raw.values())
    format_only = sum(numerical_format_only.values())
    if not rows:
        raise ValueError("Both CSV files must contain data rows")
    return {
        "rows": rows, "columns": len(dh), "cells": rows * len(dh),
        "raw_differences": changed, "raw_difference_fraction": changed / max(rows * len(dh), 1),
        "rows_with_difference": changed_rows,
        "numeric_format_only": format_only,
        "remaining_candidate_differences": changed - format_only,
        "by_column_raw": dict(raw), "by_column_numeric_format_only": dict(numerical_format_only),
        "examples_remaining": examples,
        "alignment_columns": list(alignment_columns),
        "interpretation": "Differences are candidates, not automatically verified errors. No date/semantic normalisation or manual adjudication was performed."
    }


def audit(spec) -> dict[str, Any]:
    """Verify pinned bytes and the registry's shape/anchor declarations before comparing values."""
    from dq_framework.acquisition import verify
    from dq_framework.datasets import check_table_shape

    if "pair" not in spec.raw:
        return {"status": "NOT_A_PAIR"}
    v = verify(spec)
    if v["status"] != "VERIFIED":
        return {"status": v["status"], "problems": v["problems"] + v["unpinned"]}
    shape = check_table_shape(spec)
    if not shape["ok"]:
        return {"status": "SHAPE_FAIL", "problems": shape["problems"]}
    pair = spec.raw["pair"]
    details = compare_pair(spec.raw_dir / pair["dirty"], spec.raw_dir / pair["clean"],
                           numeric_columns=tuple(pair.get("numeric_compare_columns", [])),
                           alignment_columns=tuple(pair.get("alignment_columns", [])),
                           positional_headers=pair.get("align_columns") == "positional")
    return {"status": "PAIRED", "label_provenance": spec.raw.get("ground_truth_status"),
            "files": v["files"], **details}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("datasets", nargs="*", help="default: all three published pairs")
    ap.add_argument("--output", type=Path, help="Optional local JSON report (keep raw data outside Git)")
    args = ap.parse_args()
    from dq_framework.acquisition import load_registry

    registry = load_registry()
    report = {}
    failed = False
    for key in args.datasets or DEFAULT_KEYS:
        if key not in registry:
            report[key] = {"status": "UNKNOWN"}
        elif not args.datasets and registry[key].optional and not any(registry[key].raw_dir.glob("*.csv")):
            report[key] = {"status": "ABSENT (optional)"}
        else:
            try:
                report[key] = audit(registry[key])
            except (OSError, ValueError, csv.Error) as exc:
                report[key] = {"status": "PAIR_FAIL", "error": str(exc)}
        failed |= report[key]["status"] not in ("PAIRED", "ABSENT (optional)")
        print(f"{key}: {report[key]['status']} | raw differences={report[key].get('raw_differences', 'n/a')} | remaining={report[key].get('remaining_candidate_differences', 'n/a')}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
