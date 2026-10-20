#!/usr/bin/env python
"""Validate every catalog scenario (operation x mechanism x seed) on the DEV partition.

Writes results/qualification/injection_validation_<dataset>.csv (one row per scenario)
and prints an aggregated verdict per (operation, column) and per mechanism family.
The test partition is never touched here.

Usage: python scripts/validate_injection.py uci_credit [--split-seed 1]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

import pandas as pd

from dq_framework import paths
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_contract_table, make_split
from dq_framework.injection.catalog import expand, load_catalog
from dq_framework.injection.validation import validate

warnings.filterwarnings("ignore")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--split-seed", type=int, default=1)
    args = ap.parse_args(argv)
    cat = load_catalog()
    contract = load_contract(args.dataset)
    df = load_contract_table(args.dataset, contract)
    part = make_split(df, contract, seed=args.split_seed)
    ref, dev = df[part == "reference"], df[part == "dev"].reset_index(drop=True)
    control = cat["datasets"][args.dataset].get("control_column")
    rows = []
    failures = []
    for sc in expand(args.dataset, contract, cat):
        try:
            v = validate(dev, sc, contract, ref, control_column=control)
        except Exception as exc:  # recorded, not hidden
            failures.append({"scenario_id": sc.scenario_id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        flat = {k: v[k] for k in v if k not in ("scenario", "placement", "notes", "op_params", "mech_params")}
        flat["op_params"] = json.dumps(sc.op_params)
        flat["mech_params"] = json.dumps(sc.mech_params)
        flat["notes"] = "; ".join(v["notes"])
        for lab, d in v["placement"].items():
            flat[f"dep_{lab}"] = d.get("stat")
            flat[f"dep_{lab}_p"] = d.get("p")
            flat[f"dep_{lab}_column"] = d.get("column")
        rows.append(flat)
    out = pd.DataFrame(rows)
    qdir = paths.RESULTS_DIR / "qualification"
    qdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(qdir / f"injection_validation_{args.dataset}.csv", index=False)
    (qdir / f"injection_validation_{args.dataset}_failures.json").write_text(json.dumps(failures, indent=2))
    checks = ["real_change_all", "no_side_effects", "reproducible", "seed_sensitive", "semantics_ok"]
    print(f"{len(out)} scenarios validated, {len(failures)} failed to run")
    print(out[checks].mean().round(3).to_string())
    g = out.groupby("mechanism")[[c for c in ("dep_own", "dep_cond", "dep_control") if c in out]].agg(["mean", "max"])
    print("\nmean dependence statistic by mechanism (KS or Cramér's V; 0 = none):")
    print(g.round(3).to_string())
    triv = [c for c in ("share_outside_reference_range", "share_outside_reference_envelope", "share_outside_reference_domain") if c in out]
    print("\ntriviality by case (mean over mechanisms and seeds):")
    print(out.groupby(["column", "operation"])[triv + ["realised_fraction_of_intended"]].mean().round(3).to_string())
    for f in failures[:10]:
        print("FAILED:", f)
    ok = out[checks].all(axis=None) if len(out) else False
    return 0 if ok and not failures else 1


if __name__ == "__main__":
    sys.exit(main())
