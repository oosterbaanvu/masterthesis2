#!/usr/bin/env python
"""Run pilot replications (one per pilot seed and split scheme) for a pilot configuration.

Usage:
    python scripts/run_pilot.py config/pilot/pilot_uci_credit.yaml                  # all seeds and schemes
    python scripts/run_pilot.py config/pilot/pilot_uci_credit.yaml --seeds 11 --max-scenarios 20   # smoke run
    python scripts/run_pilot.py CONFIG --schemes temporal --seeds 11

Outputs go to results/runs/pilot/<dataset>-<scheme>-s<seed>/ (git-ignored); summarise with
scripts/analyse_pilot.py. Set OMP_NUM_THREADS when running several replications in parallel.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dq_framework.pilot.runner import load_config, run_replication


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--schemes", nargs="*")
    ap.add_argument("--detectors", nargs="*", help="subset of detector keys from the config")
    ap.add_argument("--max-scenarios", type=int)
    ap.add_argument("--out-root", type=Path)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    for scheme in args.schemes or cfg.get("schemes", ["random"]):
        for seed in args.seeds or cfg.get(f"{scheme}_seeds", cfg["pilot_seeds"]):
            t = time.perf_counter()
            out = run_replication(cfg, seed, scheme=scheme, out_root=args.out_root, detectors=args.detectors,
                                  max_scenarios=args.max_scenarios)
            print(f"[done] {out} in {time.perf_counter() - t:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
