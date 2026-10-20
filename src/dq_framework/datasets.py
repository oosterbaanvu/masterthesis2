"""Load registered raw tables exactly as published, then apply the source contract.

Two loading levels are kept separate on purpose:

* :func:`load_raw_table` reads the raw file with the declared reader and **no**
  type coercion beyond what the reader does, so qualification can inspect the
  data as published.
* :func:`load_contract_table` applies the source contract: selects analysed
  columns, assigns a stable ``_row_id`` and the declared logical types.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from dq_framework import paths
from dq_framework.acquisition import DatasetSpec, load_registry

ROW_ID = "_row_id"


def get_spec(key: str) -> DatasetSpec:
    return load_registry()[key]


def load_raw_table(spec: DatasetSpec) -> pd.DataFrame:
    t = spec.raw["table"]
    path = spec.raw_dir / t["file"]
    opts: dict[str, Any] = dict(t.get("read_options", {}))
    fmt = t["format"]
    if fmt == "xls":
        return pd.read_excel(path, engine="xlrd", **opts)
    if fmt == "csv":
        return pd.read_csv(path, **opts)
    raise ValueError(f"unsupported format {fmt}")


def load_pair(spec: DatasetSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a dirty/clean benchmark pair as strings (no type inference, no NA conversion)."""
    p = spec.raw["pair"]
    kw: dict[str, Any] = {"dtype": str, "keep_default_na": False} if p.get("read_as_string", True) else {}
    dirty = pd.read_csv(spec.raw_dir / p["dirty"], **kw)
    clean = pd.read_csv(spec.raw_dir / p["clean"], **kw)
    if p.get("align_columns") == "positional":
        # Published pairs whose headers differ (e.g. 'beer_name' vs 'beer-name') are aligned
        # by position, as the Raha loader does; the dirty header is kept.
        if dirty.shape[1] != clean.shape[1]:
            raise ValueError("positional alignment requires equal column counts")
        clean.columns = dirty.columns
    return dirty, clean


def check_table_shape(spec: DatasetSpec) -> dict[str, Any]:
    """Verify every declared table and pair, including source-specific row anchors."""
    problems = []
    summaries = []
    if "table" in spec.raw:
        df = load_raw_table(spec)
        t = spec.raw["table"]
        if t.get("expected_rows") is not None and len(df) != t["expected_rows"]:
            problems.append(f"rows {len(df)} != expected {t['expected_rows']}")
        exp_cols = t.get("expected_columns")
        if exp_cols is not None and list(df.columns) != exp_cols:
            missing = sorted(set(exp_cols) - set(df.columns))
            extra = sorted(set(df.columns) - set(exp_cols))
            problems.append(f"column mismatch: missing={missing} extra={extra}")
        summaries.append(f"{len(df)} rows x {df.shape[1]} cols")
    if "pair" in spec.raw:
        dirty, clean = load_pair(spec)
        if dirty.shape != clean.shape:
            problems.append(f"dirty {dirty.shape} != clean {clean.shape}")
        if list(dirty.columns) != list(clean.columns):
            problems.append("dirty/clean column names differ (declare align_columns: positional if intended)")
        for col in spec.raw["pair"].get("alignment_columns", []):
            if col not in dirty or col not in clean:
                problems.append(f"alignment column missing: {col}")
            elif not dirty[col].equals(clean[col]):
                problems.append(f"dirty/clean row alignment differs in {col}")
        summaries.append(f"dirty {dirty.shape}, clean {clean.shape}")
    return {"ok": not problems, "problems": problems, "summary": "; ".join(summaries) or "no table declared"}


def raw_path(key: str, rel: str) -> str:
    return str(paths.RAW_DIR / key / rel)


# ---------------------------------------------------------------------------
# Contract-level loading and partitioning
# ---------------------------------------------------------------------------


def _derive(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    if spec["method"] == "contiguous_runs":
        s = df[spec["source_column"]]
        return (s != s.shift()).cumsum().astype("int64")
    raise ValueError(f"unknown derivation {spec['method']}")


def load_contract_table(dataset: str, contract=None) -> pd.DataFrame:
    """Raw table -> analysed table: ``_row_id``, natural key, derived and contract columns.

    Numeric columns become float64 (so injected missing values are representable);
    categorical columns keep their published values as pandas nullable/string types.
    Excluded columns (e.g. prediction targets) are dropped.
    """
    from dq_framework.contracts import load_contract

    contract = contract or load_contract(dataset)
    raw = load_raw_table(get_spec(dataset))
    out = pd.DataFrame(index=raw.index)
    if contract.row_id:
        out["_row_id"] = raw[contract.row_id].astype("int64").to_numpy()
        out[contract.row_id] = raw[contract.row_id].astype("int64").to_numpy()
    else:
        out["_row_id"] = range(1, len(raw) + 1)
    for name, d in contract.derived_columns.items():
        out[name] = _derive(raw, d).to_numpy()
    for col in contract.columns:
        s = raw[col.name]
        if col.missing_tokens:
            s = s.mask(s.isin(col.missing_tokens))
        if col.type == "numeric":
            out[col.name] = pd.to_numeric(s, errors="raise").astype("float64")
        elif pd.api.types.is_integer_dtype(s):
            out[col.name] = s.astype("Int64")
        else:
            out[col.name] = s.astype("string")
    return out.reset_index(drop=True)


def make_split(
    df: pd.DataFrame,
    contract,
    seed: int,
    scheme: str = "random",
    fractions: tuple[float, float, float] = (0.6, 0.2, 0.2),
    period_column: str = "_period",
) -> pd.Series:
    """Assign each row to 'reference', 'dev' or 'test'.

    random   : group-aware random split; rows that are exact duplicates on all analysed
               columns form one group and stay in one partition (prevents leakage).
    temporal : by delivery period; earliest periods -> reference, then dev, latest -> test,
               with cut points at the requested row fractions (periods are never split).
    """
    import numpy as np

    if scheme == "random":
        groups = df[contract.column_names].astype("string").fillna("<NA>").agg("\x1f".join, axis=1)
        codes, uniq = pd.factorize(groups)
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(uniq))
        rank = np.empty(len(uniq), dtype=np.int64)
        rank[order] = np.arange(len(uniq))
        u = (rank[codes] + 0.5) / len(uniq)
        cut1, cut2 = fractions[0], fractions[0] + fractions[1]
        lab = np.where(u < cut1, "reference", np.where(u < cut2, "dev", "test"))
        return pd.Series(lab, index=df.index, name="partition")
    if scheme == "temporal":
        per = df[period_column]
        counts = per.value_counts().sort_index()
        cum = counts.cumsum() / counts.sum()
        cut1, cut2 = fractions[0], fractions[0] + fractions[1]
        part_of = {p: ("reference" if c <= cut1 else "dev" if c <= cut2 else "test") for p, c in cum.items()}
        return per.map(part_of).rename("partition")
    raise ValueError(scheme)
