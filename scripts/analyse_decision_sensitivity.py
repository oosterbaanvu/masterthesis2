#!/usr/bin/env python
"""Feasibility analysis for SQ3: do adoption decisions change with baseline strength, budget and mechanism?

Re-evaluates a finished run directory (no new injections) under:
  * baseline = deterministic rules only  vs.  deterministic + statistical controls
  * review budget k in {10, 25, 50} learned-detector cells per 1,000 rows
and applies the decision rule per (error case, mechanism class) and per error case pooled over mechanisms.
Then it compares the decision based on ECAR scenarios only with the decision under each held-out
mechanism class (agreement), as a first look at decision reliability.

Usage: python scripts/analyse_decision_sensitivity.py results/runs/<run_dir> [--out results/qualification/x.csv]
This is feasibility evidence on the dev partition with 2 seeds per cell; it is not confirmatory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dq_framework.controls import alerts_to_cells
from dq_framework.evaluation import DecisionRule, evaluate_scenario


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    d = Path(args.run_dir)
    man = json.loads((d / "manifest.json").read_text())
    if man["detector"].get("granularity") != "cell":
        print("cell-level detector runs only")
        return 2
    m = pd.read_csv(d / "scenario_metrics.csv")
    log = pd.read_parquet(d / "injection_log.parquet")
    cells = alerts_to_cells(pd.read_parquet(d / "control_alerts.parquet"))
    scores = pd.read_parquet(d / "detector_scores.parquet")
    n_rows = man["split"]["n_evaluated_rows"]
    stored = man.get("budgets_per_1k", [5, 10, 25])
    budgets = tuple(float(b) for b in (10, 25, 50) if b <= max(stored))  # larger budgets would need unstored cells
    rows = []
    prim = m[(m["scenario_id"] != "untouched") & (m["tag"] == "primary")]
    for _, r in prim.iterrows():
        sid = r["scenario_id"]
        lg = log[log["scenario_id"] == sid]
        sc = scores[scores["_scenario_id"] == sid]
        for base in ("deterministic", "full"):
            bc = cells[cells["_scenario_id"] == sid]
            if base == "deterministic":
                bc = bc[bc["tier"] == "deterministic"]
            ev = evaluate_scenario(lg, bc, sc, n_rows, 1, target_column=r["column"], budgets_per_1k=budgets).metrics
            for b in budgets:
                rows.append({"column": r["column"], "operation": r["operation"], "mechanism": r["mechanism"],
                             "mechanism_class": r["mechanism_class"], "seed": r["seed"], "baseline": base, "budget": b,
                             "baseline_recall": ev["recall_B"], "gain": ev[f"incremental_recall_at_{b:g}_per_1k"],
                             "burden": b})  # with a fixed budget the extra review load is k by construction
    df = pd.DataFrame(rows)
    rule = DecisionRule(min_gain=0.05, max_extra_alerts_per_1k=np.inf)
    dec = []
    for (col, op, base, b), g in df.groupby(["column", "operation", "baseline", "budget"]):
        pooled = rule.decide(g["gain"].to_numpy(), g["burden"].to_numpy())["decision"]
        per = {mc: rule.decide(gm["gain"].to_numpy(), gm["burden"].to_numpy())["decision"]
               for mc, gm in g.groupby("mechanism_class")}
        ecar = per.get("ECAR")
        dec.append({"column": col, "operation": op, "baseline": base, "budget": b,
                    "baseline_recall": g["baseline_recall"].mean(), "gain_mean": g["gain"].mean(),
                    "decision_pooled": pooled, **{f"decision_{k}": v for k, v in per.items()},
                    "ecar_agrees_with_EAR": (ecar == per.get("EAR")) if "EAR" in per else None,
                    "ecar_agrees_with_ENAR": (ecar == per.get("ENAR")) if "ENAR" in per else None})
    dd = pd.DataFrame(dec)
    summary = (dd.groupby(["baseline", "budget"])
               .agg(cases=("column", "size"),
                    adopt=("decision_pooled", lambda s: int((s == "ADOPT").sum())),
                    insufficient=("decision_pooled", lambda s: int((s == "INSUFFICIENT_EVIDENCE").sum())),
                    mean_gain=("gain_mean", "mean"),
                    ecar_vs_ear_agree=("ecar_agrees_with_EAR", lambda s: float(pd.Series(s).dropna().astype(bool).mean())),
                    ecar_vs_enar_agree=("ecar_agrees_with_ENAR", lambda s: float(pd.Series(s).dropna().astype(bool).mean())))
               .reset_index())
    print(summary.round(3).to_string(index=False))
    flips = dd[(dd["ecar_agrees_with_EAR"] == False) | (dd["ecar_agrees_with_ENAR"] == False)]  # noqa: E712
    print(f"\n{len(flips)} case x baseline x budget combinations where the ECAR decision differs from a held-out mechanism:")
    show = [c for c in ["column", "operation", "baseline", "budget", "decision_ECAR", "decision_EAR", "decision_ENAR", "gain_mean"] if c in flips]
    print(flips[show].round(3).to_string(index=False))
    if args.out:
        dd.to_csv(args.out, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
