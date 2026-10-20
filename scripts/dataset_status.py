#!/usr/bin/env python
"""Show which registered datasets are present locally and which are correctly verified (read-only).

Usage:
    python scripts/dataset_status.py                 # all datasets, with hash + shape checks
    python scripts/dataset_status.py --quick         # hashes only (skip loading tables)
    python scripts/dataset_status.py uci_credit baf  # selected datasets
    python scripts/dataset_status.py --json out.json # also write the report elsewhere

Writes data/local_manifest.json (git-ignored). Exit code 1 if any present dataset FAILs or is PARTIAL,
or if a required (non-optional) dataset is ABSENT.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dq_framework.acquisition.status import collect, format_table, write_local_manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--quick", action="store_true", help="skip table shape checks")
    ap.add_argument("--json", type=Path, help="additional path for the JSON report")
    args = ap.parse_args(argv)
    rep = collect(args.datasets or None, check_shape=not args.quick)
    print(format_table(rep))
    out = write_local_manifest(rep)
    print(f"\nlocal manifest: {out}")
    if args.json:
        args.json.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    bad = [r for r in rep["datasets"] if r["status"] in ("FAIL", "PARTIAL")
           or (r["status"] == "ABSENT" and not r["optional"])]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
