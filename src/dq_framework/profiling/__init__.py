"""Column profiling and dirty/clean pair characterisation.

Profiles are descriptive only: they never decide that a value is an error.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

MISSING_TOKENS = {"", "n/a", "na", "nan", "null", "none", "-", "?", "empty", "unknown"}


def profile_column(s: pd.Series, max_values: int = 25) -> dict[str, Any]:
    n = len(s)
    out: dict[str, Any] = {
        "dtype": str(s.dtype),
        "n": n,
        "n_null": int(s.isna().sum()),
        "n_distinct": int(s.nunique(dropna=True)),
    }
    out["distinct_ratio"] = out["n_distinct"] / n if n else 0.0
    if pd.api.types.is_numeric_dtype(s):
        x = s.dropna().astype(float)
        if len(x):
            q = x.quantile([0.0, 0.001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.999, 1.0])
            out.update(
                {
                    "min": float(q.iloc[0]),
                    "p001": float(q.iloc[1]),
                    "p01": float(q.iloc[2]),
                    "q1": float(q.iloc[3]),
                    "median": float(q.iloc[4]),
                    "q3": float(q.iloc[5]),
                    "p99": float(q.iloc[6]),
                    "p999": float(q.iloc[7]),
                    "max": float(q.iloc[8]),
                    "mean": float(x.mean()),
                    "std": float(x.std()),
                    "share_zero": float((x == 0).mean()),
                    "share_negative": float((x < 0).mean()),
                    "is_integer_valued": bool(np.all(np.isclose(x, np.round(x)))),
                }
            )
    if out["n_distinct"] <= max_values:
        vc = s.value_counts(dropna=False)
        out["value_counts"] = {str(k): int(v) for k, v in vc.items()}
    else:
        vc = s.value_counts(dropna=False).head(5)
        out["top_values"] = {str(k): int(v) for k, v in vc.items()}
    return out


def profile_table(df: pd.DataFrame, exclude: list[str] | None = None) -> dict[str, Any]:
    exclude = exclude or []
    cols = [c for c in df.columns if c not in exclude]
    dup_rows = int(df[cols].duplicated(keep=False).sum())
    return {
        "n_rows": len(df),
        "n_columns": len(cols),
        "rows_in_exact_duplicate_groups": dup_rows,
        "columns": {c: profile_column(df[c]) for c in cols},
    }


_num = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _norm(v: str) -> str:
    return re.sub(r"\s+", " ", v.strip().lower())


def classify_difference(dirty: str, clean: str) -> str:
    """Coarse, rule-based taxonomy of a dirty->clean cell change (for benchmark characterisation)."""
    d, c = _norm(dirty), _norm(clean)
    if d in MISSING_TOKENS and c not in MISSING_TOKENS:
        return "missing_in_dirty"
    if c in MISSING_TOKENS and d not in MISSING_TOKENS:
        return "value_where_clean_missing"
    if d == c:
        return "whitespace_or_case_only"
    if _num.match(d) and _num.match(c):
        try:
            if float(d) == float(c):
                return "numeric_formatting_only"  # e.g. 01907 vs 1907, 12.0 vs 12
        except ValueError:
            pass
        return "numeric_value_change"
    dn = re.sub(r"[^0-9a-z]", "", d)
    cn = re.sub(r"[^0-9a-z]", "", c)
    if dn == cn:
        return "punctuation_or_format_only"
    if cn and cn in dn or dn and dn in cn:
        return "extraneous_or_truncated_text"
    if len(d) == len(c) and sum(a != b for a, b in zip(d, c, strict=True)) == 1:
        return "single_character_substitution"
    return "other_value_change"


def characterise_pair(dirty: pd.DataFrame, clean: pd.DataFrame, id_columns: list[str] | None = None) -> dict[str, Any]:
    """Cell-level comparison of an aligned dirty/clean pair read as strings."""
    if dirty.shape != clean.shape:
        raise ValueError("pair is not aligned")
    id_columns = id_columns or []
    diff = dirty.values != clean.values
    n_cells = diff.size
    per_col = {}
    cats_total: dict[str, int] = {}
    examples: dict[str, list[tuple[str, str]]] = {}
    for j, col in enumerate(dirty.columns):
        idx = np.flatnonzero(diff[:, j])
        cats: dict[str, int] = {}
        for i in idx:
            cat = classify_difference(dirty.iat[i, j], clean.iat[i, j])
            cats[cat] = cats.get(cat, 0) + 1
            cats_total[cat] = cats_total.get(cat, 0) + 1
            ex = examples.setdefault(cat, [])
            if len(ex) < 6:
                ex.append((f"{col}: {dirty.iat[i, j]!r}", f"{clean.iat[i, j]!r}"))
        per_col[col] = {"n_errors": int(len(idx)), "error_rate": float(len(idx) / len(dirty)), "categories": cats}
    rows_with_error = int(diff.any(axis=1).sum())
    return {
        "n_rows": int(dirty.shape[0]),
        "n_columns": int(dirty.shape[1]),
        "n_cells": int(n_cells),
        "n_error_cells": int(diff.sum()),
        "cell_error_rate": float(diff.sum() / n_cells),
        "rows_with_error": rows_with_error,
        "id_columns_with_differences": [c for c in id_columns if per_col.get(c, {}).get("n_errors", 0) > 0],
        "categories": dict(sorted(cats_total.items(), key=lambda kv: -kv[1])),
        "examples": examples,
        "per_column": per_col,
    }
