"""Evaluation of conventional controls (B) and their combination with a learned detector (C = B + L).

Ground truth is the injection log: a cell is an *injected error* if it is in the log.
Every other cell is *untouched*. Untouched does NOT mean correct: alerts on untouched
cells are reported as "alerts on untouched cells" (alert burden), never as verified
false positives, because the published data may contain genuine errors.

Unit of analysis: cell (_row_id, column). Rule alerts implicate every column a rule
references (see controls.alerts_to_cells); row-level aggregates are reported too.

Core quantities per scenario
----------------------------
recall_B             share of injected cells implicated by any baseline control
recall_L             share of injected cells flagged by the learned detector (own threshold)
incremental_recall   share of injected cells flagged by L and missed by B   (= recall_C - recall_B)
extra_alerts_per_1k  untouched cells flagged by L but not by B, per 1,000 rows
recall_at_budget     recall of B plus the top-k L-ranked cells not already alerted by B,
                     k = budget_per_1k * n_rows / 1000 (a fixed review capacity)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def _key(df: pd.DataFrame) -> pd.Series:
    return df["_row_id"].astype("int64").astype(str) + "\x1f" + df["column"].astype(str)


@dataclass
class ScenarioEval:
    metrics: dict[str, Any]
    per_cell: pd.DataFrame | None = None


def evaluate_scenario(
    log: pd.DataFrame,
    baseline_cells: pd.DataFrame,
    detector_scores: pd.DataFrame | None,
    n_rows: int,
    n_cols: int,
    target_column: str | None = None,
    budgets_per_1k: tuple[float, ...] = (5.0, 10.0, 25.0),
) -> ScenarioEval:
    """Score one scenario.

    log             injection log (one row per injected cell: _row_id, column)
    baseline_cells  implicated cells of baseline alerts (_row_id, column, tier) for this scenario
    detector_scores learned detector output for this scenario (_row_id, column, score, flag) or None
    """
    inj = set(_key(log))
    n_inj = len(inj)
    b_keys = set(_key(baseline_cells)) if len(baseline_cells) else set()
    det_b = set(_key(baseline_cells[baseline_cells["tier"] == "deterministic"])) if len(baseline_cells) else set()
    m: dict[str, Any] = {"n_injected": n_inj, "n_rows": n_rows}
    m["recall_det"] = len(inj & det_b) / n_inj if n_inj else np.nan
    m["recall_B"] = len(inj & b_keys) / n_inj if n_inj else np.nan
    n_cells = n_rows * n_cols
    m["baseline_alert_cells_untouched_per_1k"] = 1000 * len(b_keys - inj) / n_rows
    # row-level view
    inj_rows = set(log["_row_id"].astype("int64"))
    b_rows = set(baseline_cells["_row_id"].astype("int64")) if len(baseline_cells) else set()
    m["row_recall_B"] = len(inj_rows & b_rows) / len(inj_rows) if inj_rows else np.nan
    if detector_scores is None or detector_scores.empty:
        return ScenarioEval(m)
    ds = detector_scores.copy()
    ds["key"] = _key(ds)
    ds["injected"] = ds["key"].isin(inj)
    ds["in_B"] = ds["key"].isin(b_keys)
    l_flag = set(ds.loc[ds["flag"], "key"])
    m["recall_L"] = len(inj & l_flag) / n_inj if n_inj else np.nan
    m["recall_C"] = len(inj & (l_flag | b_keys)) / n_inj if n_inj else np.nan
    m["incremental_recall"] = len((inj & l_flag) - b_keys) / n_inj if n_inj else np.nan
    m["unique_L_detections"] = len((inj & l_flag) - b_keys)
    m["extra_alerts_untouched_per_1k"] = 1000 * len(l_flag - b_keys - inj) / n_rows
    m["L_alerts_untouched_per_1k"] = 1000 * len(l_flag - inj) / n_rows
    m["precision_L_vs_injected"] = len(inj & l_flag) / len(l_flag) if l_flag else np.nan
    # ranking quality of L on the target column (threshold-free)
    if target_column is not None:
        sub = ds[(ds["column"] == target_column) & ds["score"].notna()]
        if sub["injected"].any() and (~sub["injected"]).any():
            from sklearn.metrics import average_precision_score, roc_auc_score

            m["auc_L_target"] = float(roc_auc_score(sub["injected"], sub["score"]))
            m["ap_L_target"] = float(average_precision_score(sub["injected"], sub["score"]))
        tgt = ds[ds["column"] == target_column]
        m["L_alerts_untouched_target_per_1k"] = 1000 * int((tgt["flag"] & ~tgt["injected"]).sum()) / n_rows
    # fixed review budget: B alerts are reviewed first (they exist anyway); L fills the remaining
    # capacity with its highest-scored cells that B did not alert. Budget counts L-added cells only.
    cand = ds[~ds["in_B"] & ds["score"].notna()].sort_values("score", ascending=False, kind="mergesort")
    for b in budgets_per_1k:
        k = int(round(b * n_rows / 1000))
        top = cand.head(k)
        add = int(top["injected"].sum())
        m[f"incremental_recall_at_{b:g}_per_1k"] = add / n_inj if n_inj else np.nan
        m[f"precision_added_at_{b:g}_per_1k"] = add / k if k else np.nan
    m["n_cells"] = n_cells
    return ScenarioEval(m, ds)


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0,
                 stat=np.mean) -> tuple[float, float, float]:
    """Percentile bootstrap CI of ``stat`` over independent replicates (e.g. scenario seeds)."""
    v = np.asarray([x for x in values if not np.isnan(x)], dtype=float)
    if len(v) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boots = np.array([stat(rng.choice(v, size=len(v), replace=True)) for _ in range(n_boot)])
    return float(stat(v)), float(np.quantile(boots, alpha / 2)), float(np.quantile(boots, 1 - alpha / 2))


@dataclass
class DecisionRule:
    """Pre-registered adoption rule for a learned detector on top of the baseline.

    ADOPT                if the lower CI bound of incremental recall at the budget >= min_gain
                         and the extra alert burden <= max_extra_alerts_per_1k;
    DO_NOT_ADOPT         if the upper CI bound < min_gain or the burden is exceeded;
    INSUFFICIENT_EVIDENCE otherwise.
    """

    metric: str = "incremental_recall_at_10_per_1k"
    min_gain: float = 0.05
    max_extra_alerts_per_1k: float = 10.0

    def decide(self, gains: np.ndarray, burdens: np.ndarray) -> dict[str, Any]:
        mean, lo, hi = bootstrap_ci(np.asarray(gains, dtype=float))
        burden = float(np.nanmean(burdens)) if len(burdens) else np.nan
        if np.isnan(mean):
            d = "INSUFFICIENT_EVIDENCE"
        elif burden > self.max_extra_alerts_per_1k:
            d = "DO_NOT_ADOPT"
        elif lo >= self.min_gain:
            d = "ADOPT"
        elif hi < self.min_gain:
            d = "DO_NOT_ADOPT"
        else:
            d = "INSUFFICIENT_EVIDENCE"
        return {"decision": d, "gain_mean": mean, "gain_ci": [lo, hi], "extra_alert_burden_per_1k": burden,
                "n": int(np.sum(~np.isnan(np.asarray(gains, dtype=float))))}


def evaluate_rows(
    log: pd.DataFrame,
    baseline_cells: pd.DataFrame,
    detector_scores: pd.DataFrame | None,
    n_rows: int,
    budgets_per_1k: tuple[float, ...] = (5.0, 10.0, 25.0),
) -> dict[str, Any]:
    """Record-level view: a row is 'erroneous' if it contains an injected cell and 'alerted' if any control
    implicates any of its cells. Cell-level detector output is aggregated to rows (max score, any flag);
    row-level detectors are used as-is. Nothing is mapped from rows down to cells."""
    inj_rows = set(log["_row_id"].astype("int64"))
    n_inj = len(inj_rows)
    b_rows = set(baseline_cells["_row_id"].astype("int64")) if len(baseline_cells) else set()
    m: dict[str, Any] = {"row_n_injected": n_inj,
                         "row_recall_B": len(inj_rows & b_rows) / n_inj if n_inj else np.nan,
                         "row_B_alerts_untouched_per_1k": 1000 * len(b_rows - inj_rows) / n_rows}
    if detector_scores is None or detector_scores.empty:
        return m
    r = (detector_scores.groupby("_row_id").agg(score=("score", "max"), flag=("flag", "any")).reset_index())
    r["_row_id"] = r["_row_id"].astype("int64")
    r["injected"] = r["_row_id"].isin(inj_rows)
    r["in_B"] = r["_row_id"].isin(b_rows)
    l_rows = set(r.loc[r["flag"], "_row_id"])
    m["row_recall_L"] = len(inj_rows & l_rows) / n_inj if n_inj else np.nan
    m["row_incremental_recall"] = len((inj_rows & l_rows) - b_rows) / n_inj if n_inj else np.nan
    m["row_extra_alerts_untouched_per_1k"] = 1000 * len(l_rows - b_rows - inj_rows) / n_rows
    cand = r[~r["in_B"] & r["score"].notna()].sort_values("score", ascending=False, kind="mergesort")
    for b in budgets_per_1k:
        k = int(round(b * n_rows / 1000))
        add = int(cand.head(k)["injected"].sum())
        m[f"row_incremental_recall_at_{b:g}_per_1k"] = add / n_inj if n_inj else np.nan
    return m
