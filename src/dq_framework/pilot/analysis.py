"""Aggregate pilot replications: detector performance, selection, decisions, regret, overlap, runtime.

Units of replication: a *pilot seed* is an independent reference/selection/test re-split of the design pool;
injection seeds within one pilot seed share rows and are therefore averaged first (never treated as
independent datasets). Confidence intervals across replications are percentile bootstraps over pilot seeds
(5 seeds: coarse, reported as such).

Selection (per replication, dataset, baseline, budget k, strategy S):
  candidates = cell-level detectors that ran; utility U(d) = mean over error cases of the mean utility of d
  (``metrics.utility_key``: ranked dR@k for scored detectors, budget-capped flag dR@k otherwise) on the
  selection scenarios of S. The selected detector is argmax U. Decision for it (ADOPT / DO_NOT_ADOPT /
  INSUFFICIENT_EVIDENCE) from a cluster bootstrap over error cases against ``min_gain``.
Evaluation on each test set T (fresh scenarios on other rows): regret = max_d U_T(d) - U_T(selected); the
  decision is also recomputed on T ("target decision") to measure decision agreement.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SEL_SETS = {"simple": "sel_simple", "diverse": "sel_diverse"}
TEST_SETS = ("test_simple", "test_diverse", "test_heldout")


def load_replications(dirs: list[Path]) -> dict[str, pd.DataFrame]:
    parts: dict[str, list[pd.DataFrame]] = {k: [] for k in ("metrics", "baseline", "scenarios", "overlap", "burden",
                                                            "failures", "detectors", "manifest")}
    for d in dirs:
        man = json.loads((d / "manifest.json").read_text())
        rid = {"replication": man["replication"], "dataset": man["dataset"], "pilot_seed": man["pilot_seed"],
               "scheme": man["scheme"]}
        sc = pd.read_csv(d / "scenarios.csv").assign(**rid)
        parts["scenarios"].append(sc)
        for key, f in (("metrics", "detector_metrics.csv"), ("baseline", "baseline_metrics.csv"),
                       ("overlap", "overlap.csv"), ("burden", "untouched_burden.csv"), ("failures", "failures.csv")):
            p = d / f
            if p.exists() and p.stat().st_size > 1:
                with contextlib.suppress(pd.errors.EmptyDataError):
                    parts[key].append(pd.read_csv(p).assign(**rid))
        for k, v in man["detectors"].items():
            parts["detectors"].append(pd.DataFrame([{**rid, "detector": k, **{kk: (json.dumps(vv) if isinstance(vv, (list, dict)) else vv)
                                                                               for kk, vv in v.items() if kk != "detector"}}]))
        parts["manifest"].append(pd.DataFrame([{**rid, "elapsed_s": man["elapsed_s"], "n_scenarios": man["n_scenarios"],
                                                "n_failed": man["n_failed_scenarios"], "dbt_s": man["dbt"]["elapsed_s"],
                                                **{f"n_{p}": n for p, n in man["partitions"].items()}}]))
    out = {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in parts.items()}
    scen_cols = ["replication", "sid", "set", "case_id", "family", "mechanism_setting", "mechanism_class", "column",
                 "operation", "rate", "role"]
    for k in ("metrics", "baseline", "overlap"):
        if len(out[k]):
            out[k] = out[k].merge(out["scenarios"][scen_cols], on=["replication", "sid"], how="left")
    return out


def cell_detectors(det: pd.DataFrame) -> pd.DataFrame:
    d = det[(det["granularity"] == "cell") & (det["status"] == "ok")]
    return d[["dataset", "detector", "provides_scores", "fit_scope"]].drop_duplicates()


def _utility_frame(metrics: pd.DataFrame, det: pd.DataFrame, budget: float) -> pd.DataFrame:
    """One utility per (scenario, candidate). A scored detector yields two operating modes: reviewing its top-k
    ranked cells (``<det>``) and reviewing its own flags within the budget (``<det>[flags]``) - both are things an
    engineer can do with its output (decision D-26). Binary detectors have the flag mode only."""
    cd = cell_detectors(det)
    m = metrics.merge(cd, on=["dataset", "detector"], how="inner")
    scored = m["provides_scores"].astype(str).str.lower().isin(["true", "1"])
    flag_col, rank_col = f"dR_flags@{budget:g}", f"dR_ranked@{budget:g}"
    m["utility"] = np.where(scored, m.get(rank_col, np.nan), m[flag_col])
    fm = m[scored].assign(detector=lambda x: x["detector"] + "[flags]", utility=lambda x: x[flag_col])
    return pd.concat([m, fm], ignore_index=True)


def case_means(u: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Mean utility per error case first (equal weight per case), then the list of case means per group."""
    return u.groupby([*by, "case_id"], dropna=False)["utility"].mean().reset_index()


def decide(case_vals: np.ndarray, min_gain: float, n_boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    v = np.asarray(case_vals, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return {"decision": "INSUFFICIENT_EVIDENCE", "mean": np.nan, "lo": np.nan, "hi": np.nan, "n_cases": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    lo, hi = float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))
    d = "ADOPT" if lo >= min_gain else ("DO_NOT_ADOPT" if hi < min_gain else "INSUFFICIENT_EVIDENCE")
    return {"decision": d, "mean": float(v.mean()), "lo": lo, "hi": hi, "n_cases": int(len(v))}


def selection_table(data: dict[str, pd.DataFrame], budgets: list[float], min_gain: float, n_boot: int = 2000) -> pd.DataFrame:
    rows = []
    met, det = data["metrics"], data["detectors"]
    met = met[met["role"].fillna("primary") == "primary"]
    for budget in budgets:
        u = _utility_frame(met, det, budget)
        cm = case_means(u, ["replication", "dataset", "scheme", "baseline", "set", "detector"])
        for (rep, ds, scheme, base), g in cm.groupby(["replication", "dataset", "scheme", "baseline"]):
            per_set = {s: gg.groupby("detector")["utility"].mean() for s, gg in g.groupby("set")}
            for strat, sset in SEL_SETS.items():
                if sset not in per_set:
                    continue
                us = per_set[sset].sort_index()
                chosen = us.idxmax()
                dec = decide(g[(g["set"] == sset) & (g["detector"] == chosen)]["utility"].to_numpy(), min_gain, n_boot)
                for tset in TEST_SETS:
                    if tset not in per_set:
                        continue
                    ut = per_set[tset].reindex(us.index)
                    best = ut.idxmax()
                    tdec = decide(g[(g["set"] == tset) & (g["detector"] == chosen)]["utility"].to_numpy(), min_gain, n_boot)
                    rows.append({"replication": rep, "dataset": ds, "scheme": scheme, "baseline": base, "budget": budget,
                                 "strategy": strat, "test_set": tset, "selected": chosen,
                                 "selection_utility": float(us[chosen]), "runner_up": us.drop(chosen).idxmax() if len(us) > 1 else None,
                                 "selection_margin": float(us[chosen] - us.drop(chosen).max()) if len(us) > 1 else np.nan,
                                 "decision": dec["decision"], "decision_lo": dec["lo"], "decision_hi": dec["hi"],
                                 "test_best": best, "test_utility_selected": float(ut[chosen]),
                                 "test_utility_best": float(ut[best]), "regret": float(ut[best] - ut[chosen]),
                                 "test_decision": tdec["decision"], "decision_agrees": dec["decision"] == tdec["decision"],
                                 "selected_is_best": chosen == best})
    return pd.DataFrame(rows)


def boot_ci(v: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    b = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    return float(v.mean()), float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))


def summarise_selection(sel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, g in sel.groupby(["dataset", "scheme", "baseline", "budget", "strategy", "test_set"]):
        m, lo, hi = boot_ci(g["regret"].to_numpy())
        rows.append({**dict(zip(["dataset", "scheme", "baseline", "budget", "strategy", "test_set"], key, strict=True)),
                     "n_replications": len(g), "selected": "; ".join(f"{k}×{v}" for k, v in g["selected"].value_counts().items()),
                     "decisions": "; ".join(f"{k}×{v}" for k, v in g["decision"].value_counts().items()),
                     "test_decisions": "; ".join(f"{k}×{v}" for k, v in g["test_decision"].value_counts().items()),
                     "decision_agreement": float(g["decision_agrees"].mean()), "selected_is_best": float(g["selected_is_best"].mean()),
                     "regret_mean": m, "regret_lo": lo, "regret_hi": hi, "regret_max": float(g["regret"].max()),
                     "test_utility_selected": float(g["test_utility_selected"].mean()),
                     "test_utility_best": float(g["test_utility_best"].mean())})
    return pd.DataFrame(rows)


def strategy_comparison(sel: pd.DataFrame) -> pd.DataFrame:
    """Does the injection strategy change the selected detector / the decision? Paired by replication."""
    k = ["replication", "dataset", "scheme", "baseline", "budget"]
    a = sel[sel["test_set"] == "test_heldout"]
    p = a.pivot_table(index=k, columns="strategy", values=["selected", "decision", "regret"], aggfunc="first")
    p.columns = [f"{x}_{y}" for x, y in p.columns]
    p = p.reset_index()
    p["same_selection"] = p["selected_simple"] == p["selected_diverse"]
    p["same_decision"] = p["decision_simple"] == p["decision_diverse"]
    p["regret_diff_simple_minus_diverse"] = p["regret_simple"].astype(float) - p["regret_diverse"].astype(float)
    return p


def detector_table(data: dict[str, pd.DataFrame], budgets: list[float], by: list[str]) -> pd.DataFrame:
    """Mean per replication first, then mean and bootstrap CI over replications."""
    met = data["metrics"]
    met = met[~met["detector"].str.contains("@row") & met["detector"].isin(cell_detectors(data["detectors"])["detector"])]
    cols = ["recall_L", "precision_L_lb", "incremental_recall_flags", "extra_alerts_untouched_per_1k", "auc_target",
            *[f"dR_flags@{b:g}" for b in budgets], *[f"dR_ranked@{b:g}" for b in budgets]]
    cols = [c for c in cols if c in met]
    rep = met.groupby(["replication", *by])[cols].mean().reset_index()
    out = []
    for key, g in rep.groupby(by):
        r = dict(zip(by, key if isinstance(key, tuple) else (key,), strict=True))
        r["n_replications"] = len(g)
        for c in cols:
            m, lo, hi = boot_ci(g[c].to_numpy())
            r[c] = m
            r[f"{c}_lo"], r[f"{c}_hi"] = lo, hi
        out.append(r)
    return pd.DataFrame(out)


def baseline_table(data: dict[str, pd.DataFrame], by: list[str]) -> pd.DataFrame:
    b = data["baseline"]
    rep = b.groupby(["replication", *by])[["recall_B", "row_recall_B"]].mean().reset_index()
    out = []
    for key, g in rep.groupby(by):
        r = dict(zip(by, key if isinstance(key, tuple) else (key,), strict=True))
        for c in ("recall_B", "row_recall_B"):
            m, lo, hi = boot_ci(g[c].to_numpy())
            r[c], r[f"{c}_lo"], r[f"{c}_hi"] = m, lo, hi
        r["n_replications"] = len(g)
        out.append(r)
    return pd.DataFrame(out)


def overlap_table(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    o = data["overlap"]
    o = o[o["role"].fillna("primary") == "primary"]
    g = o.groupby(["dataset", "scheme", "baseline", "a", "b"])[["a_found", "b_found", "both", "either", "n_injected"]].sum().reset_index()
    g["jaccard"] = g["both"] / g["either"].replace(0, np.nan)
    g["a_only_share"] = (g["a_found"] - g["both"]) / g["n_injected"]
    g["b_only_share"] = (g["b_found"] - g["both"]) / g["n_injected"]
    return g


def seed_sensitivity(data: dict[str, pd.DataFrame], budget: float) -> pd.DataFrame:
    """Spread of utility across injection seeds (same rows) vs across pilot seeds (different rows)."""
    met = data["metrics"]
    met = met[(met["role"].fillna("primary") == "primary") & met["set"].isin(list(SEL_SETS.values()))]
    u = _utility_frame(met, data["detectors"], budget)
    within = (u.groupby(["dataset", "baseline", "detector", "set", "replication", "case_id", "rate"])["utility"].std()
              .groupby(["dataset", "baseline", "detector", "set"]).mean().rename("sd_within_replication"))
    rep_means = u.groupby(["dataset", "baseline", "detector", "set", "replication", "case_id"])["utility"].mean()
    between = (rep_means.groupby(["dataset", "baseline", "detector", "set", "case_id"]).std()
               .groupby(["dataset", "baseline", "detector", "set"]).mean().rename("sd_between_replications"))
    return pd.concat([within, between], axis=1).reset_index()


def detector_evidence(data: dict[str, pd.DataFrame], budgets: list[float]) -> pd.DataFrame:
    """Utility of every cell detector on every set, per replication (case-mean), then mean/CI over replications.

    This is the offline evidence the operational scan uses for its recommendation (test sets only)."""
    met = data["metrics"]
    met = met[met["role"].fillna("primary") == "primary"]
    rows = []
    for budget in budgets:
        u = _utility_frame(met, data["detectors"], budget)
        cm = case_means(u, ["replication", "dataset", "scheme", "baseline", "set", "detector"])
        rep = cm.groupby(["replication", "dataset", "scheme", "baseline", "set", "detector"])["utility"].mean().reset_index()
        for key, g in rep.groupby(["dataset", "scheme", "baseline", "set", "detector"]):
            m, lo, hi = boot_ci(g["utility"].to_numpy())
            rows.append({**dict(zip(["dataset", "scheme", "baseline", "test_set", "detector"], key, strict=True)),
                         "budget": budget, "utility": m, "utility_lo": lo, "utility_hi": hi, "n_replications": len(g)})
    return pd.DataFrame(rows)


def statistical_alert_rate(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Baseline alert rate on the untouched evaluation partitions (reference value for the scan's shift check)."""
    b = data["burden"]
    b = b[b["detector"] == "<baseline>"]
    return b.groupby(["dataset", "scheme", "partition", "baseline"])["alerts_per_1k"].mean().reset_index()
