"""A genuinely shared total cell-review budget, separate from legacy additive metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score


def queues(base, flags, scores, k, seed=0):
    """Baseline-only vs 50/50 baseline/novel-detector triage; duplicates cost one slot.

    Uniform seeded cell priorities break all ties without labels. Binary outputs have only flags.
    Unused novel capacity returns to the baseline. A detector can displace useful baseline alerts.
    """
    n = base.size
    tie = np.random.default_rng(seed).permutation(n)
    b = tie[base.ravel()[tie]]
    eligible = flags.ravel() if scores is None else np.isfinite(scores.ravel())
    d = tie[eligible[tie]]
    if scores is not None:
        d = d[np.argsort(-scores.ravel()[d], kind="stable")]
    novel = d[~base.ravel()[d]]
    first = b[:min(len(b), (k + 1) // 2)]
    added = novel[:max(0, k - len(first))]
    mix = np.concatenate([first, added, b[len(first):len(first) + max(0, k - len(first) - len(added))]])

    def mask(idx):
        out = np.zeros(n, bool)
        out[idx[:k]] = True
        return out.reshape(base.shape)

    return mask(b), mask(mix), mask(d)


def metrics(inj, base, flags, scores, budgets):
    n = int(inj.sum())
    out = {}
    for budget in budgets:
        k = int(round(budget * inj.shape[0] / 1000))
        b, mix, solo = queues(base, flags, scores, k)
        bh, mh = int((b & inj).sum()), int((mix & inj).sum())
        out.update({f"total_base_recall@{budget:g}": bh / n if n else np.nan,
                    f"total_recall@{budget:g}": mh / n if n else np.nan,
                    f"total_delta@{budget:g}": (mh - bh) / n if n else np.nan,
                    f"total_precision_lb@{budget:g}": mh / mix.sum() if mix.any() else np.nan,
                    f"total_reviews@{budget:g}": int(mix.sum()),
                    f"total_unique_added_hits@{budget:g}": int((mix & inj & ~b).sum()),
                    f"total_displaced_hits@{budget:g}": int((b & inj & ~mix).sum()),
                    f"solo_recall@{budget:g}": float((solo & inj).sum() / n) if n else np.nan})
    if scores is not None:
        finite = np.isfinite(scores)
        out["scored_positive_coverage"] = float((inj & finite).sum() / n) if n else np.nan
        out["ap_all_scored"] = float(average_precision_score(inj[finite], scores[finite])) if inj[finite].any() else np.nan
    return out
