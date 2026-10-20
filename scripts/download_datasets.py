#!/usr/bin/env python
"""Download all (or selected) datasets declared in config/datasets.yaml.

Usage:
    python scripts/download_datasets.py                # all required datasets
    python scripts/download_datasets.py uci_credit     # one dataset
    python scripts/download_datasets.py baf            # an optional dataset, by name
    python scripts/download_datasets.py --include-optional
    python scripts/download_datasets.py --force        # re-download even if present

Exit code is non-zero if any requested dataset fails verification. Optional
datasets (BAF, via the Kaggle client: scripts/download_baf.py) are skipped
unless named or --include-optional is given. Manual datasets are reported as
BLOCKED with the required user action.
"""

from __future__ import annotations

import argparse
import json
import sys

from dq_framework.acquisition import AcquisitionError, acquire, load_registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="*", help="dataset keys (default: all)")
    ap.add_argument("--force", action="store_true", help="re-download even if files exist")
    ap.add_argument("--include-optional", action="store_true", help="also download optional datasets (e.g. BAF)")
    args = ap.parse_args(argv)

    registry = load_registry()
    keys = args.datasets or [k for k, s in registry.items() if args.include_optional or not s.optional]
    for k in [k for k in registry if registry[k].optional and k not in keys]:
        print(f"[SKIPPED] {k}: optional; request it by name. {registry[k].raw['acquisition'].get('instructions', '')}")
    failed = False
    for key in keys:
        spec = registry[key]
        if spec.manual:
            res = acquire(spec)
            status = "BLOCKED" if res["status"] == "FAIL" else res["status"]
            print(f"[{status}] {key}: manual acquisition. {spec.raw['acquisition'].get('instructions', '')}")
            continue
        try:
            res = acquire(spec, force=args.force)
        except AcquisitionError as exc:
            print(f"[FAIL] {key}: {exc}")
            failed = True
            continue
        print(f"[{res['status']}] {key}: {len(res['files'])} file(s)")
        for p in res["problems"] + res["unpinned"]:
            print(f"    - {p}")
        failed |= res["status"] == "FAIL"
        if res.get("downloads"):
            print("    manifest:", json.dumps([d["url"] for d in res["downloads"]]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
