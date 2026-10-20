"""Primary analysis of the pilot (decision D-28): financial tables only, label-free scored cell detectors only.

Analysis units ("tables or delivery sets"): dataset x split scheme (UCI Credit random, Bank Marketing random,
Bank Marketing consecutive deliveries; Give Me Some Credit when available). Replications within a unit are
pilot splits (random) or delivery sets (delivery).

Main question: how much does a detector add over each of the two baselines, and is the difference *between
baselines* larger than the difference *between detectors*?

* increment U(d, b) = ranked dR@k of detector d over baseline b (mean over error cases, then replications);
* baseline effect on the increment  E_b(d) = U(d, rules) - U(d, rules+stat);
* detector spread                   S_d(b) = max_d U(d, b) - min_d U(d, b) over the primary detectors;
* the same two quantities for *total* detection T(b, d) = recall of baseline b + U(d, b): baseline effect
  T(rules+stat, d) - T(rules, d) and detector spread at fixed b.
All are computed per replication and summarised with a bootstrap CI over replications.

Go / no-go (pre-stated in docs/comprehensive_pilot_report.md §9):
  G1 two usable detectors on >= 3 units: a detector is usable on a unit if it ran on every replication and its
     held-out increment over the rules+stat baseline at k = 25 has a CI lower bound > 0;
  G2 measurable difference between detectors: the paired CDC - dBoost difference in held-out increment has a CI
     that excludes 0 on >= 2 units;
  G3 required size of the confirmatory study: number of independent replications per unit for 80 % power at
     alpha = 0.05 (two-sided, paired normal approximation) to detect a detector difference of delta.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from dq_framework.pilot.analysis import boot_ci, case_means

UNIT_NAMES = {("uci_credit", "random"): "UCI Credit (random splits)",
              ("uci_bank_marketing", "random"): "Bank Marketing (random splits)",
              ("uci_bank_marketing", "delivery"): "Bank Marketing (consecutive deliveries)",
              ("gmsc", "random"): "Give Me Some Credit (random splits)"}
BASE = {"deterministic": "rules", "full": "rules+stat"}


def _primary_metrics(data: dict[str, pd.DataFrame], primary: list[str], budget: float) -> pd.DataFrame:
    m = data["metrics"]
    m = m[(m["role"].fillna("primary") == "primary") & m["detector"].isin(primary)].copy()
    m["utility"] = m[f"dR_ranked@{budget:g}"]
    return m


def unit_replication_table(data: dict[str, pd.DataFrame], primary: list[str], budget: float, sets: list[str]) -> pd.DataFrame:
    """Per replication x set x baseline x detector: case-mean increment U and baseline recall R_B."""
    u = _primary_metrics(data, primary, budget)
    u = u[u["set"].isin(sets)]
    cm = case_means(u, ["replication", "dataset", "scheme", "set", "baseline", "detector"])
    U = cm.groupby(["replication", "dataset", "scheme", "set", "baseline", "detector"])["utility"].mean().rename("U")
    b = data["baseline"]
    b = b[b["set"].isin(sets) & (b["role"].fillna("primary") == "primary")]
    rb = (b.groupby(["replication", "dataset", "scheme", "set", "baseline", "case_id"])["recall_B"].mean()
          .groupby(["replication", "dataset", "scheme", "set", "baseline"]).mean().rename("R_B"))
    out = U.reset_index().merge(rb.reset_index(), on=["replication", "dataset", "scheme", "set", "baseline"], how="left")
    out["T"] = out["R_B"] + out["U"]
    out["budget"] = budget
    return out


def effects(rep: pd.DataFrame) -> pd.DataFrame:
    """Per replication x set: baseline effects (per detector) and detector spreads (per baseline)."""
    rows = []
    for key, g in rep.groupby(["replication", "dataset", "scheme", "set", "budget"]):
        piv_u = g.pivot_table(index="detector", columns="baseline", values="U")
        piv_t = g.pivot_table(index="detector", columns="baseline", values="T")
        if not {"deterministic", "full"} <= set(piv_u.columns):
            continue
        base = dict(zip(["replication", "dataset", "scheme", "set", "budget"], key, strict=True))
        rows.append({**base,
                     "baseline_effect_increment": float((piv_u["deterministic"] - piv_u["full"]).abs().mean()),
                     "detector_spread_increment_rules": float(piv_u["deterministic"].max() - piv_u["deterministic"].min()),
                     "detector_spread_increment_full": float(piv_u["full"].max() - piv_u["full"].min()),
                     "baseline_effect_total": float((piv_t["full"] - piv_t["deterministic"]).abs().mean()),
                     "detector_spread_total_rules": float(piv_t["deterministic"].max() - piv_t["deterministic"].min()),
                     "detector_spread_total_full": float(piv_t["full"].max() - piv_t["full"].min()),
                     "best_rules": piv_u["deterministic"].idxmax(), "best_full": piv_u["full"].idxmax()})
    return pd.DataFrame(rows)


def summarise_effects(eff: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in eff.columns if c.startswith(("baseline_effect", "detector_spread"))]
    out = []
    for key, g in eff.groupby(["dataset", "scheme", "set", "budget"]):
        r: dict[str, Any] = dict(zip(["dataset", "scheme", "set", "budget"], key, strict=True))
        r["unit"] = UNIT_NAMES.get((key[0], key[1]), f"{key[0]} ({key[1]})")
        r["n_replications"] = len(g)
        for c in cols:
            m, lo, hi = boot_ci(g[c].to_numpy())
            r[c], r[f"{c}_lo"], r[f"{c}_hi"] = m, lo, hi
        for a, b in (("baseline_effect_increment", "detector_spread_increment_full"),
                     ("baseline_effect_total", "detector_spread_total_full")):
            d = g[a] - g[b]
            m, lo, hi = boot_ci(d.to_numpy())
            r[f"{a}_minus_{b}"], r[f"{a}_minus_{b}_lo"], r[f"{a}_minus_{b}_hi"] = m, lo, hi
        r["best_rules"] = "; ".join(f"{k}×{v}" for k, v in g["best_rules"].value_counts().items())
        r["best_full"] = "; ".join(f"{k}×{v}" for k, v in g["best_full"].value_counts().items())
        out.append(r)
    return pd.DataFrame(out)


def increments(rep: pd.DataFrame) -> pd.DataFrame:
    out = []
    for key, g in rep.groupby(["dataset", "scheme", "set", "budget", "baseline", "detector"]):
        r = dict(zip(["dataset", "scheme", "set", "budget", "baseline", "detector"], key, strict=True))
        r["unit"] = UNIT_NAMES.get((key[0], key[1]), f"{key[0]} ({key[1]})")
        for c in ("U", "R_B", "T"):
            m, lo, hi = boot_ci(g[c].to_numpy())
            r[c], r[f"{c}_lo"], r[f"{c}_hi"] = m, lo, hi
        r["n_replications"] = len(g)
        out.append(r)
    return pd.DataFrame(out)


def paired_differences(rep: pd.DataFrame, a: str, others: list[str]) -> pd.DataFrame:
    """Per unit x set x baseline: CDC minus the best other primary detector (per replication), with CI."""
    out = []
    for key, g in rep.groupby(["dataset", "scheme", "set", "budget", "baseline"]):
        p = g.pivot_table(index="replication", columns="detector", values="U")
        if a not in p or not set(others) & set(p.columns):
            continue
        best_other = p[[o for o in others if o in p]].max(axis=1)
        d = (p[a] - best_other).dropna().to_numpy()
        m, lo, hi = boot_ci(d)
        out.append({**dict(zip(["dataset", "scheme", "set", "budget", "baseline"], key, strict=True)),
                    "unit": UNIT_NAMES.get((key[0], key[1]), f"{key[0]} ({key[1]})"), "n_replications": len(d),
                    "diff_mean": m, "diff_lo": lo, "diff_hi": hi, "diff_sd": float(np.std(d, ddof=1)) if len(d) > 1 else np.nan,
                    "excludes_zero": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(out)


def required_replications(sd: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Paired normal approximation: n = ((z_{1-alpha/2} + z_power) * sd / delta)^2 (rounded up, >= 3)."""
    if not np.isfinite(sd) or sd <= 0:
        return np.nan
    return float(max(3, np.ceil(((norm.ppf(1 - alpha / 2) + norm.ppf(power)) * sd / delta) ** 2)))


def go_no_go(inc: pd.DataFrame, diffs: pd.DataFrame, primary: list[str], deltas: tuple[float, ...] = (0.01, 0.02, 0.05),
             budget: float = 25.0) -> dict[str, Any]:
    h = inc[(inc["set"] == "test_heldout") & (inc["budget"] == budget) & (inc["baseline"] == "full")]
    usable = h.assign(usable=h["U_lo"] > 0)
    per_unit = usable.groupby("unit").apply(lambda g: sorted(g.loc[g["usable"], "detector"]), include_groups=False).to_dict()
    n_units_two = sum(1 for v in per_unit.values() if len(v) >= 2)
    if diffs.empty:
        diffs = pd.DataFrame(columns=["set", "budget", "unit", "baseline", "diff_mean", "diff_lo", "diff_hi", "diff_sd",
                                      "excludes_zero"])
    dd = diffs[(diffs["set"] == "test_heldout") & (diffs["budget"] == budget)]
    measurable = dd[dd["excludes_zero"].astype(bool)]
    sizes = []
    for _, r in dd.iterrows():
        for delta in deltas:
            sizes.append({"unit": r["unit"], "baseline": r["baseline"], "delta": delta, "observed_sd": r["diff_sd"],
                          "observed_diff": r["diff_mean"], "n_replications_needed": required_replications(r["diff_sd"], delta)})
    return {
        "budget": budget,
        "G1_usable_detectors_per_unit": per_unit,
        "G1_units_with_two_usable": n_units_two,
        "G1_pass": n_units_two >= 3,
        "G2_units_baselines_with_measurable_difference": measurable[["unit", "baseline", "diff_mean", "diff_lo", "diff_hi"]].to_dict("records"),
        "G2_pass": measurable["unit"].nunique() >= 2,
        "G3_sample_size": sizes,
    }
