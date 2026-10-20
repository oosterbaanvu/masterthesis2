"""Label-blind review ordering, shared by operational triage and offline evaluation."""

from __future__ import annotations

import hashlib

import pandas as pd


def review_order(cells: pd.DataFrame, *, ranked=False, seed=0) -> pd.DataFrame:
    """Rank finite scores, or hash-order binary flags; never invent a binary detector score."""
    out = cells.copy()
    if ranked:
        out = out[out["score"].notna() & out["score"].abs().ne(float("inf"))]
    elif "flag" in out:
        out = out[out["flag"]]
    out = out.drop_duplicates(["_row_id", "column"])
    out["_tie"] = [hashlib.sha256(f"{seed}|{rid}|{col}".encode()).hexdigest()
                   for rid, col in zip(out["_row_id"], out["column"], strict=True)]
    cols = ["score", "_tie"] if ranked else ["_tie"]
    return out.sort_values(cols, ascending=[False, True] if ranked else [True], kind="stable").drop(columns="_tie")
