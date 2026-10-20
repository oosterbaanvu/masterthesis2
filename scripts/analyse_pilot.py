#!/usr/bin/env python
"""Aggregate pilot replications into the small, committed summary tables and figures.

Usage:
    python scripts/analyse_pilot.py                          # all replications under results/runs/pilot/
    python scripts/analyse_pilot.py --runs DIR [DIR ...] --out results/pilot --figures docs/figures

Writes (CSV, small): baseline_by_case.csv, detector_by_family.csv, detector_by_case.csv, selection.csv,
selection_summary.csv, strategy_comparison.csv, overlap.csv, seed_sensitivity.csv, detector_evidence.csv,
evaluation_alert_rates.csv, untouched_burden.csv, runtime.csv, failures.csv, replications.csv;
figures (PNG) if matplotlib is installed (`uv sync --extra figures`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dq_framework import paths
from dq_framework.pilot import analysis as A

# reference palette (light mode) of the dataviz method: categorical slots 1-3, text and surface tokens
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def _budgets(data) -> list[float]:
    cols = [c for c in data["metrics"].columns if c.startswith("dR_flags@")]
    return sorted(float(c.split("@")[1]) for c in cols)


def figures(out_fig: Path, tables: dict[str, pd.DataFrame]) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: figures skipped (uv sync --extra figures)")
        return []
    out_fig.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "text.color": INK})
    made = []
    ev = tables["detector_evidence"]
    for ds, g in ev[(ev["scheme"] == "random")].groupby("dataset"):
        g = g[(g["test_set"] == "test_heldout")]
        dets = (g[(g["baseline"] == "full") & (g["budget"] == 25)].sort_values("utility")["detector"].tolist())
        fig, axes = plt.subplots(1, 2, figsize=(9.5, 0.32 * len(dets) + 1.6), sharey=True)
        for ax, base in zip(axes, ("deterministic", "full"), strict=True):
            for i, b in enumerate((10, 25, 50)):
                s = g[(g["baseline"] == base) & (g["budget"] == b)].set_index("detector").reindex(dets)
                y = np.arange(len(dets)) + (i - 1) * 0.22
                ax.errorbar(s["utility"], y, xerr=[s["utility"] - s["utility_lo"], s["utility_hi"] - s["utility"]],
                            fmt="o", ms=4, lw=1.2, color=SERIES[i], label=f"k = {b}/1k rows")
            ax.axvline(0.05, color=INK2, lw=0.8, ls="--")
            ax.set_title(f"baseline: {'rules only' if base == 'deterministic' else 'rules + statistical'}", fontsize=9)
            ax.set_xlabel("incremental recall at budget (held-out scenarios)")
            ax.grid(axis="x", color=GRID, lw=0.6)
            ax.set_yticks(np.arange(len(dets)), dets)
        axes[0].legend(frameon=False, loc="lower right", fontsize=8)
        fig.suptitle(f"{ds}: added detection over existing controls (mean, 95% CI over pilot splits; dashed = min_gain)",
                     fontsize=9.5)
        fig.tight_layout()
        p = out_fig / f"pilot_{ds}_heldout_increment.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        made.append(p)
    fam = tables["detector_by_family"]
    for ds, g in fam[(fam["scheme"] == "random") & (fam["baseline"] == "full") & (fam["set"].isin(["sel_simple", "sel_diverse"]))].groupby("dataset"):
        top = ["cdc", "dboost_gaussian_text", "lucario_core"]
        g = g[g["detector"].isin(top)]
        fams = sorted(g["family"].unique())
        fig, ax = plt.subplots(figsize=(8, 0.4 * len(fams) + 1.6))
        for i, d in enumerate(top):
            s = g[(g["detector"] == d) & (g["set"] == "sel_simple")].set_index("family").reindex(fams)
            col = "dR_ranked@25" if d == "cdc" else "dR_flags@25"
            ax.barh(np.arange(len(fams)) + (i - 1) * 0.26, s[col], height=0.24, color=SERIES[i], label=d)
        ax.set_yticks(np.arange(len(fams)), fams)
        ax.set_xlabel("incremental recall at 25 reviews / 1k rows (selection scenarios, simple strategy, full baseline)")
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.legend(frameon=False, fontsize=8)
        ax.set_title(f"{ds}: increment by error family", fontsize=9.5)
        fig.tight_layout()
        p = out_fig / f"pilot_{ds}_increment_by_family.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        made.append(p)
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, nargs="*")
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "pilot")
    ap.add_argument("--figures", type=Path, default=paths.ROOT / "docs" / "figures")
    args = ap.parse_args(argv)
    dirs = args.runs or sorted(p for p in (paths.RESULTS_DIR / "runs" / "pilot").glob("*") if (p / "manifest.json").exists())
    if not dirs:
        print("no replications found")
        return 1
    data = A.load_replications(dirs)
    budgets = _budgets(data)
    cfg_gain = 0.05
    t: dict[str, pd.DataFrame] = {}
    t["replications"] = data["manifest"]
    t["baseline_by_case"] = A.baseline_table(data, ["dataset", "scheme", "baseline", "set", "family", "case_id"])
    t["baseline_by_family"] = A.baseline_table(data, ["dataset", "scheme", "baseline", "set", "family"])
    t["detector_by_family"] = A.detector_table(data, budgets, ["dataset", "scheme", "baseline", "set", "family", "detector"])
    t["detector_by_case"] = A.detector_table(data, budgets, ["dataset", "scheme", "baseline", "set", "case_id", "detector"])
    t["detector_overall"] = A.detector_table(
        {**data, "metrics": data["metrics"][data["metrics"]["role"].fillna("primary") == "primary"]}, budgets,
        ["dataset", "scheme", "baseline", "set", "detector"])
    sel = A.selection_table(data, budgets, cfg_gain)
    t["selection"] = sel
    t["selection_summary"] = A.summarise_selection(sel)
    t["strategy_comparison"] = A.strategy_comparison(sel)
    t["overlap"] = A.overlap_table(data)
    t["seed_sensitivity"] = A.seed_sensitivity(data, 25.0)
    t["detector_evidence"] = A.detector_evidence(data, budgets)
    t["evaluation_alert_rates"] = A.statistical_alert_rate(data)
    t["untouched_burden"] = (data["burden"].groupby(["dataset", "scheme", "partition", "detector", "baseline"])
                             [[c for c in ("alerts_per_1k", "rows_per_1k", "flags_per_1k") if c in data["burden"]]]
                             .agg(["mean", "std"]).round(2))
    t["untouched_burden"].columns = [f"{a}_{b}" for a, b in t["untouched_burden"].columns]
    t["untouched_burden"] = t["untouched_burden"].reset_index()
    det = data["detectors"]
    keep = [c for c in ("dataset", "scheme", "pilot_seed", "detector", "name", "granularity", "provides_scores", "fit_scope",
                        "supervision", "compatibility", "status", "fit_seconds", "score_seconds", "n_score_calls") if c in det]
    t["runtime"] = det[keep]
    t["failures"] = data["failures"]
    args.out.mkdir(parents=True, exist_ok=True)
    for k, v in t.items():
        v.to_csv(args.out / f"{k}.csv", index=False, float_format="%.4g")
    made = figures(args.figures, t)
    meta = {"replications": [d.name for d in dirs], "budgets_per_1k": budgets, "min_gain": cfg_gain,
            "tables": sorted(t), "figures": [str(p.relative_to(paths.ROOT)) if p.is_relative_to(paths.ROOT) else str(p) for p in made]}
    (args.out / "index.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
