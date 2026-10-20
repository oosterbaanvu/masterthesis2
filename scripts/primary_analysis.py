#!/usr/bin/env python
"""Primary analysis (D-28): increment of scored label-free cell detectors over both baselines, baseline vs
detector effect, go/no-go and confirmatory sample size. Financial tables only.

Usage: python scripts/primary_analysis.py [--runs DIR ...] [--out results/pilot]
Writes primary_increments.csv, primary_effects.csv, primary_effects_by_replication.csv,
primary_paired_differences.csv, go_no_go.json (and docs/figures/primary_*.png if matplotlib is installed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

from dq_framework import paths
from dq_framework.pilot import analysis as A
from dq_framework.pilot import primary as P

FINANCIAL = {"uci_credit", "uci_bank_marketing", "gmsc"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def figure(inc, eff, out: Path) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "text.color": INK})
    out.mkdir(parents=True, exist_ok=True)
    h = inc[(inc["set"] == "test_heldout") & (inc["budget"] == 25)]
    units = sorted(h["unit"].unique())
    dets = sorted(h["detector"].unique())
    fig, axes = plt.subplots(1, len(units), figsize=(3.4 * len(units), 3.2), sharey=True, squeeze=False)
    for ax, u in zip(axes[0], units, strict=True):
        g = h[h["unit"] == u]
        for i, d in enumerate(dets):
            s = g[g["detector"] == d].set_index("baseline").reindex(["deterministic", "full"])
            x = np.arange(2) + (i - 1) * 0.18
            ax.errorbar(x, s["T"], yerr=[s["T"] - s["T_lo"], s["T_hi"] - s["T"]], fmt="o", ms=4, lw=1.2,
                        color=SERIES[i % 3], label=d)
        bl = g.drop_duplicates("baseline").set_index("baseline").reindex(["deterministic", "full"])["R_B"]
        ax.plot(np.arange(2), bl, ls="none", marker="_", ms=18, color=INK2, label="baseline alone")
        ax.set_xticks([0, 1], ["rules", "rules+stat"])
        ax.set_title(u, fontsize=8.5)
        ax.grid(axis="y", color=GRID, lw=0.6)
    axes[0][0].set_ylabel("recall on held-out errors (baseline + 25 reviews / 1k rows)")
    axes[0][-1].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Total detection: the baseline moves the result more than the choice of detector (mean, 95% CI over replications)",
                 fontsize=9)
    fig.tight_layout()
    p = out / "primary_total_detection.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return [p]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, nargs="*")
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "pilot")
    ap.add_argument("--figures", type=Path, default=paths.ROOT / "docs" / "figures")
    args = ap.parse_args(argv)
    dirs = args.runs or sorted(p for p in (paths.RESULTS_DIR / "runs" / "pilot").glob("*") if (p / "manifest.json").exists())
    data = A.load_replications(dirs)
    keep = data["manifest"]["dataset"].isin(FINANCIAL)
    reps = set(data["manifest"].loc[keep, "replication"])
    data = {k: (v[v["replication"].isin(reps)] if "replication" in v else v) for k, v in data.items()}
    primary = sorted({d for ds in data["manifest"]["dataset"].unique()
                      for d in yaml.safe_load((paths.CONFIG_DIR / "pilot" / f"pilot_{ds}.yaml").read_text())["primary_detectors"]})
    sets = ["sel_simple", "sel_diverse", "test_simple", "test_diverse", "test_heldout"]
    reps_tables = [P.unit_replication_table(data, primary, b, sets) for b in (10.0, 25.0, 50.0)]
    import pandas as pd

    rep = pd.concat(reps_tables, ignore_index=True)
    inc = P.increments(rep)
    eff = P.effects(rep)
    eff_s = P.summarise_effects(eff)
    diffs = P.paired_differences(rep, "cdc", [d for d in primary if d != "cdc"])
    gng = {str(b): P.go_no_go(inc, diffs, primary, budget=b) for b in (10.0, 25.0, 50.0)}
    args.out.mkdir(parents=True, exist_ok=True)
    rep.to_csv(args.out / "primary_by_replication.csv", index=False, float_format="%.4g")
    inc.to_csv(args.out / "primary_increments.csv", index=False, float_format="%.4g")
    eff.to_csv(args.out / "primary_effects_by_replication.csv", index=False, float_format="%.4g")
    eff_s.to_csv(args.out / "primary_effects.csv", index=False, float_format="%.4g")
    diffs.to_csv(args.out / "primary_paired_differences.csv", index=False, float_format="%.4g")
    (args.out / "go_no_go.json").write_text(json.dumps({"primary_detectors": primary, "replications": sorted(reps), **gng},
                                                       indent=2, default=str) + "\n")
    figs = figure(inc, eff, args.figures)
    print(json.dumps({"primary": primary, "units": sorted(inc["unit"].unique()), "figures": [str(f) for f in figs],
                      "go_no_go_k25": {k: v for k, v in gng["25.0"].items() if k != "G3_sample_size"}}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
