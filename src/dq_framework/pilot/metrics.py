"""Matrix-based evaluation of one scenario: cells are (row position, column index) of an (n_rows x n_cols) grid.

Ground truth: ``inj`` marks cells whose value actually changed (injection log). Every other cell is
*untouched* - not "correct": alerts there are alert burden, never counted as verified false positives.

Metrics valid for every cell-level detector (binary or scored):

* recall / precision of the detector's own flags w.r.t. injected cells (precision is a lower bound: untouched
  alerts are unverified), incremental recall over the baseline, extra alerts per 1,000 rows (cells flagged by
  the detector, not by the baseline, not injected);
* budget-capped flag recall ``dR@k (flags)``: the reviewer has k extra review slots per 1,000 rows and reviews
  the detector's extra flags (those the baseline did not raise) in random order; the expected number of
  injected cells found is hits x min(1, k / n_extra_flags). No ranking is constructed for binary detectors.

Additional metric for detectors that publish a ranking score:

* ranked budget recall ``dR@k (ranked)``: the k highest-scored cells not alerted by the baseline are reviewed.

The operational utility used for selection is the ranked variant when the detector provides scores and the
flag variant otherwise (``utility_at_k``).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _k(budget_per_1k: float, n_rows: int) -> int:
    return int(round(budget_per_1k * n_rows / 1000))


def ranked_order(scores: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Flat indices of allowed cells with a finite score, highest score first (ties by position)."""
    s = np.where(allowed & np.isfinite(scores), scores, np.nan).ravel()
    idx = np.flatnonzero(~np.isnan(s))
    return idx[np.argsort(-s[idx], kind="stable")]


def topk_mask(scores: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask of the k highest finite scores among ``allowed`` cells (stable: ties by position)."""
    s = np.where(allowed & np.isfinite(scores), scores, -np.inf).ravel()
    out = np.zeros(s.shape, dtype=bool)
    k = min(k, int(np.isfinite(s).sum()))
    if k > 0:
        idx = np.argsort(-s, kind="stable")[:k]
        out[idx] = True
    return out.reshape(scores.shape)


def baseline_metrics(inj: np.ndarray, base: np.ndarray, n_rows: int) -> dict[str, Any]:
    n_inj = int(inj.sum())
    return {"n_injected": n_inj,
            "recall_B": float((inj & base).sum() / n_inj) if n_inj else np.nan,
            "B_alerts_untouched_per_1k": 1000 * float((base & ~inj).sum()) / n_rows,
            "row_recall_B": float((inj.any(1) & base.any(1)).sum() / inj.any(1).sum()) if n_inj else np.nan}


def cell_metrics(inj: np.ndarray, base: np.ndarray, flags: np.ndarray, scores: np.ndarray | None,
                 budgets_per_1k: tuple[float, ...], target_col: int | None = None) -> dict[str, Any]:
    n_rows = inj.shape[0]
    n_inj = int(inj.sum())
    m: dict[str, Any] = {}
    hits = inj & flags
    extra = flags & ~base
    inc = hits & ~base
    m["n_flags"] = int(flags.sum())
    m["recall_L"] = float(hits.sum() / n_inj) if n_inj else np.nan
    m["precision_L_lb"] = float(hits.sum() / flags.sum()) if flags.any() else np.nan
    m["incremental_recall_flags"] = float(inc.sum() / n_inj) if n_inj else np.nan
    m["extra_alerts_untouched_per_1k"] = 1000 * float((extra & ~inj).sum()) / n_rows
    n_extra = int(extra.sum())
    for b in budgets_per_1k:
        k = _k(b, n_rows)
        share = 1.0 if n_extra <= k else k / n_extra
        m[f"dR_flags@{b:g}"] = float(inc.sum() * share / n_inj) if n_inj else np.nan
        m[f"reviews_flags@{b:g}"] = min(k, n_extra)
    if scores is not None:
        order = ranked_order(scores, ~base)
        inj_flat = inj.ravel()
        for b in budgets_per_1k:
            top = order[:_k(b, n_rows)]
            found = int(inj_flat[top].sum())
            m[f"dR_ranked@{b:g}"] = float(found / n_inj) if n_inj else np.nan
            m[f"precision_ranked@{b:g}"] = float(found / len(top)) if len(top) else np.nan
        if target_col is not None:
            s = scores[:, target_col]
            y = inj[:, target_col]
            ok = np.isfinite(s)
            if y[ok].any() and (~y[ok]).any():
                from sklearn.metrics import average_precision_score, roc_auc_score

                m["auc_target"] = float(roc_auc_score(y[ok], s[ok]))
                m["ap_target"] = float(average_precision_score(y[ok], s[ok]))
    return m


def found_mask(inj: np.ndarray, base: np.ndarray, flags: np.ndarray, scores: np.ndarray | None,
               budget_per_1k: float) -> np.ndarray:
    """Injected cells the detector adds over the baseline at a budget: top-k for scored detectors, extra flags
    otherwise (all of them; the budget cap enters the expected recall, not the identity of detected cells)."""
    if scores is not None:
        return topk_mask(scores, ~base, _k(budget_per_1k, inj.shape[0])) & inj
    return flags & inj & ~base


def row_metrics(inj: np.ndarray, base: np.ndarray, row_flags: np.ndarray, row_scores: np.ndarray | None,
                budgets_per_1k: tuple[float, ...]) -> dict[str, Any]:
    """Record level: a row is erroneous if it has an injected cell, alerted if the baseline implicates any cell."""
    n_rows = inj.shape[0]
    ir = inj.any(1)
    br = base.any(1) if base.ndim == 2 else base.astype(bool)
    n = int(ir.sum())
    m = {"row_n_injected": n, "row_recall_B": float((ir & br).sum() / n) if n else np.nan,
         "row_recall_L": float((ir & row_flags).sum() / n) if n else np.nan,
         "row_incremental_recall_flags": float((ir & row_flags & ~br).sum() / n) if n else np.nan,
         "row_extra_alerts_untouched_per_1k": 1000 * float((row_flags & ~br & ~ir).sum()) / n_rows}
    if row_scores is not None:
        for b in budgets_per_1k:
            top = topk_mask(row_scores[:, None], ~br[:, None], _k(b, n_rows))[:, 0]
            m[f"row_dR_ranked@{b:g}"] = float((top & ir).sum() / n) if n else np.nan
    return m


def utility_key(provides_scores: bool, budget: float) -> str:
    return f"dR_ranked@{budget:g}" if provides_scores else f"dR_flags@{budget:g}"
