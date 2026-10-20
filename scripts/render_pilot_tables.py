#!/usr/bin/env python
"""Render the Markdown tables of docs/comprehensive_pilot_report.md from results/pilot/*.csv.

Usage: python scripts/render_pilot_tables.py [--pilot results/pilot] > /tmp/tables.md
Every number in the report's result tables comes from this script (no hand-edited values).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from dq_framework import paths

DS = {"uci_credit": "Credit", "uci_bank_marketing": "Bank"}
BASE = {"deterministic": "rules", "full": "rules+stat"}


def ci(m, lo, hi, d=3):
    if pd.isna(m):
        return "–"
    return f"{m:.{d}f} [{lo:.{d}f}, {hi:.{d}f}]"


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, default=paths.RESULTS_DIR / "pilot")
    a = ap.parse_args(argv)
    P = a.pilot
    rep = pd.read_csv(P / "replications.csv")
    print("## T0 replications\n")
    print(md(rep[["replication", "n_scenarios", "n_failed", "elapsed_s", "dbt_s", "n_reference", "n_selection", "n_test",
                  "n_holdout_excluded"]]))

    bf = pd.read_csv(P / "baseline_by_family.csv")
    print("\n## T1 baseline recall by error family (selection, simple strategy; mean [95% CI over pilot splits])\n")
    x = bf[(bf["set"] == "sel_simple") | (bf["set"] == "sanity")]
    rows = []
    for (ds, sch, fam), g in x.groupby(["dataset", "scheme", "family"]):
        r = {"dataset": DS[ds], "split": sch, "family": fam}
        for b in ("deterministic", "full"):
            gg = g[g["baseline"] == b]
            r[BASE[b]] = ci(gg["recall_B"].iloc[0], gg["recall_B_lo"].iloc[0], gg["recall_B_hi"].iloc[0]) if len(gg) else "–"
        rows.append(r)
    print(md(pd.DataFrame(rows)))

    bc = pd.read_csv(P / "baseline_by_case.csv")
    print("\n## T1b baseline recall by error case (random splits, selection, simple)\n")
    x = bc[(bc["scheme"] == "random") & bc["set"].isin(["sel_simple", "sanity", "test_heldout"])]
    p = x.pivot_table(index=["dataset", "set", "family", "case_id"], columns="baseline", values="recall_B").reset_index()
    p["dataset"] = p["dataset"].map(DS)
    print(md(p.round(3).rename(columns=BASE)))

    det = pd.read_csv(P / "detector_overall.csv")
    print("\n## T2 detector performance on primary scenarios (random splits; mean over pilot splits)\n")
    for ds in DS:
        for base in ("deterministic", "full"):
            x = det[(det["dataset"] == ds) & (det["scheme"] == "random") & (det["baseline"] == base) & (det["set"] == "sel_simple")]
            if not len(x):
                continue
            t = x[["detector", "recall_L", "precision_L_lb", "incremental_recall_flags", "extra_alerts_untouched_per_1k",
                   "dR_flags@10", "dR_flags@25", "dR_flags@50"] + [c for c in ("dR_ranked@10", "dR_ranked@25", "dR_ranked@50", "auc_target") if c in x]]
            print(f"\n**{DS[ds]}, baseline {BASE[base]}, selection scenarios (simple)**\n")
            print(md(t.sort_values("dR_flags@25", ascending=False).round(3)))

    ev = pd.read_csv(P / "detector_evidence.csv")
    print("\n## T3 utility on held-out scenarios (mean [95% CI over pilot splits])\n")
    for (ds, sch), g in ev[ev["test_set"] == "test_heldout"].groupby(["dataset", "scheme"]):
        rows = []
        for d, gd in g.groupby("detector"):
            r = {"detector": d}
            for base in ("deterministic", "full"):
                for b in (10, 25, 50):
                    q = gd[(gd["baseline"] == base) & (gd["budget"] == b)]
                    r[f"{BASE[base]} k={b}"] = ci(q["utility"].iloc[0], q["utility_lo"].iloc[0], q["utility_hi"].iloc[0]) if len(q) else "–"
            rows.append(r)
        print(f"\n**{DS[ds]} ({sch} split)**\n")
        print(md(pd.DataFrame(rows)))

    ss = pd.read_csv(P / "selection_summary.csv")
    print("\n## T4 selection, decisions and regret\n")
    keep = ["dataset", "scheme", "baseline", "budget", "strategy", "test_set", "n_replications", "selected", "decisions",
            "test_decisions", "decision_agreement", "selected_is_best", "regret_mean", "regret_lo", "regret_hi", "regret_max"]
    x = ss[keep].copy()
    x["dataset"] = x["dataset"].map(DS)
    x["baseline"] = x["baseline"].map(BASE)
    print(md(x.round(3)))

    sc = pd.read_csv(P / "strategy_comparison.csv")
    print("\n## T5 does the injection strategy change the selection? (paired by split, held-out evaluation)\n")
    g = sc.groupby(["dataset", "scheme", "baseline", "budget"]).agg(
        n=("same_selection", "size"), same_selection=("same_selection", "mean"), same_decision=("same_decision", "mean"),
        regret_simple=("regret_simple", "mean"), regret_diverse=("regret_diverse", "mean")).reset_index()
    g["dataset"] = g["dataset"].map(DS)
    g["baseline"] = g["baseline"].map(BASE)
    print(md(g.round(3)))

    ov = pd.read_csv(P / "overlap.csv")
    print("\n## T6 overlap of added detections (k = 25; summed over primary scenarios and splits)\n")
    x = ov[(ov["scheme"] == "random") & (ov["a"] != "<all>")].copy()
    x = x[(x["a_found"] + x["b_found"]) > 0]
    x["dataset"] = x["dataset"].map(DS)
    x["baseline"] = x["baseline"].map(BASE)
    top = x.sort_values("either", ascending=False).groupby(["dataset", "baseline"]).head(8)
    print(md(top[["dataset", "baseline", "a", "b", "a_found", "b_found", "both", "jaccard", "a_only_share", "b_only_share"]].round(3)))
    allr = ov[(ov["a"] == "<all>")].copy()
    allr["union_share"] = allr["either"] / allr["n_injected"]
    allr["dataset"] = allr["dataset"].map(DS)
    print("\n**union of all cell candidates (share of injected cells added over the baseline)**\n")
    print(md(allr[["dataset", "scheme", "baseline", "either", "n_injected", "union_share"]].round(3)))

    sd = pd.read_csv(P / "seed_sensitivity.csv")
    print("\n## T7 seed sensitivity at k = 25 (mean SD of utility per error case)\n")
    x = sd[sd["set"] == "sel_simple"].copy()
    x["dataset"] = x["dataset"].map(DS)
    print(md(x.round(4)))

    rt = pd.read_csv(P / "runtime.csv")
    print("\n## T8 runtime per replication (seconds; mean over splits)\n")
    g = rt.groupby(["dataset", "detector", "granularity", "fit_scope", "provides_scores"])[["fit_seconds", "score_seconds", "n_score_calls"]].mean().reset_index()
    g["dataset"] = g["dataset"].map(DS)
    print(md(g.round(1)))

    ub = pd.read_csv(P / "untouched_burden.csv")
    print("\n## T9 alert burden on untouched test partitions (per 1,000 rows)\n")
    x = ub[(ub["partition"] == "test")].copy()
    x["dataset"] = x["dataset"].map(DS)
    print(md(x.round(1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
