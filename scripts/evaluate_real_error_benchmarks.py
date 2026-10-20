#!/usr/bin/env python
"""Run dirty-only service scans, then score them against the published references (no injection)."""

import argparse
from pathlib import Path

from dq_framework import paths
from dq_framework.evaluation.published import evaluate_scans, run_scans


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol", type=Path, default=paths.CONFIG_DIR / "benchmarks/published_errors.yaml")
    ap.add_argument("--work-dir", type=Path, default=paths.RESULTS_DIR / "runs/real_error_benchmark")
    ap.add_argument("--output", type=Path, default=paths.RESULTS_DIR / "real_error_benchmark")
    ap.add_argument("--phase", choices=("scan", "evaluate", "all"), default="all")
    args = ap.parse_args()
    if args.phase in ("scan", "all"):
        run_scans(args.protocol.resolve(), args.work_dir)
    if args.phase in ("evaluate", "all"):
        evaluate_scans(args.protocol.resolve(), args.work_dir, args.output)


if __name__ == "__main__":
    main()
