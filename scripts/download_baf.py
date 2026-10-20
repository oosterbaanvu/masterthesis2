#!/usr/bin/env python
"""Download and validate the optional Feedzai BAF dataset (Base variant) from Kaggle.

BAF is optional: nothing else in the framework requires it. Licence is unresolved (Kaggle: CC BY-NC-SA
4.0; publisher datasheet: CC BY-NC-ND 4.0), so confirm it before using the data in the thesis.

Setup (once, also on a local computer):
    uv sync --extra dev --extra kaggle        # or: pip install kaggle
    export KAGGLE_API_TOKEN=...               # kaggle.com > Settings > API; or ~/.kaggle/kaggle.json

Usage:
    python scripts/download_baf.py                    # download Base.csv (if absent) and validate
    python scripts/download_baf.py --force            # re-download
    python scripts/download_baf.py --validate-only    # no network; validate the local copy
    python scripts/download_baf.py --report data/manifests/baf.validation.json

Files land read-only in data/raw/baf/ (git-ignored). The SHA-256 of each file is checked against
config/datasets.yaml; while unpinned, the observed hash is printed for a human to pin. Validation
reports columns, row count, missing values (NaN and the datasheet's negative sentinels) and the target
distribution. The target ``fraud_bool`` is a prediction label, not a data-quality label.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dq_framework.acquisition import AcquisitionError, load_registry, verify
from dq_framework.acquisition.kaggle import acquire_kaggle, authenticate, credential_source
from dq_framework.datasets import check_table_shape, load_raw_table

KEY = "baf"


def validate(spec) -> dict[str, Any]:
    """Shape against the registry, then a descriptive profile. Descriptive only: flags nothing as an error."""
    t = spec.raw.get("table", {})
    df = load_raw_table(spec)
    shape = check_table_shape(spec)
    nan = df.isna().sum()
    sentinels = {}
    for col, rule in t.get("missing_sentinels", {}).items():
        s = df[col]
        hit = s < 0 if rule == "negative" else s == rule
        sentinels[col] = {"rule": rule, "n": int(hit.sum()), "rate": float(hit.mean())}
    num = df.select_dtypes("number")
    neg = (num < 0).sum()
    target = t.get("target")
    out: dict[str, Any] = {
        "dataset": spec.key,
        "file": t.get("file"),
        "rows": len(df),
        "n_columns": df.shape[1],
        "columns": {c: str(d) for c, d in df.dtypes.items()},
        "shape_check": shape,
        "missing_nan": {c: int(n) for c, n in nan.items() if n},
        "missing_nan_total": int(nan.sum()),
        "missing_sentinels": sentinels,
        "missing_sentinels_status": t.get("missing_sentinels_status"),
        "negative_values": {c: int(n) for c, n in neg.items() if n},
        "duplicate_rows": int(df.duplicated().sum()),
    }
    if target:
        vc = df[target].value_counts(dropna=False).sort_index()
        out["target"] = {
            "column": target,
            "counts": {str(k): int(v) for k, v in vc.items()},
            "rates": {str(k): float(v / len(df)) for k, v in vc.items()},
        }
    return out


def _print_report(r: dict[str, Any]) -> None:
    print(f"\nValidation of {r['dataset']}/{r['file']}: {r['rows']:,} rows x {r['n_columns']} columns")
    print(f"  shape vs registry: {'OK' if r['shape_check']['ok'] else 'FAIL'} {r['shape_check']['problems'] or ''}")
    print("  columns:", ", ".join(f"{c} ({d})" for c, d in r["columns"].items()))
    print(f"  NaN cells: {r['missing_nan_total']:,}" + (f" {r['missing_nan']}" if r["missing_nan"] else ""))
    if r["missing_sentinels"]:
        print(f"  negative-sentinel missing values ({r['missing_sentinels_status']}):")
        for c, s in r["missing_sentinels"].items():
            print(f"    {c:<34} {s['n']:>9,} ({s['rate']:.2%})")
    other = {c: n for c, n in r["negative_values"].items() if c not in r["missing_sentinels"]}
    if other:
        print(f"  other columns with negative values (not documented as missing; descriptive only): {other}")
    print(f"  fully duplicated rows: {r['duplicate_rows']:,}")
    if "target" in r:
        t = r["target"]
        dist = ", ".join(f"{k}: {t['counts'][k]:,} ({t['rates'][k]:.3%})" for k in t["counts"])
        print(f"  target {t['column']}: {dist}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download even if the file exists")
    ap.add_argument("--validate-only", action="store_true", help="skip download; validate the local copy")
    ap.add_argument("--report", type=Path, help="write the validation report as JSON to this path")
    args = ap.parse_args(argv)

    spec = load_registry()[KEY]
    if not args.validate_only:
        print(f"Kaggle credentials: {credential_source() or 'none found'}")  # names the source, never the value
        try:
            api = authenticate()
            print("Kaggle authentication: OK")
            manifest = acquire_kaggle(spec, force=args.force, api=api)
        except AcquisitionError as exc:
            print(f"[FAIL] {KEY}: {exc}", file=sys.stderr)
            return 1
    else:
        manifest = verify(spec)
    print(f"[{manifest['status']}] {KEY}: {[f['path'] for f in manifest['files']]}")
    for p in manifest["problems"] + manifest["unpinned"]:
        print(f"    - {p}")
    if manifest["status"] == "FAIL":
        return 1

    report = validate(spec)
    _print_report(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nreport written to {args.report}")
    return 0 if report["shape_check"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
