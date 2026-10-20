"""Pilot partitions inside the design pool; the confirmatory hold-out is never touched."""

from __future__ import annotations

import pandas as pd

from dq_framework.datasets import make_split

PILOT_PARTS = ("reference", "selection", "test")


def design_pool(df: pd.DataFrame, contract, holdout_seed: int = 1, holdout_partition: str = "test") -> pd.Series:
    """True for rows the pilot may use: everything except the hold-out partition of ``holdout_seed``."""
    return make_split(df, contract, seed=holdout_seed, scheme="random") != holdout_partition


def pilot_split(df: pd.DataFrame, contract, pilot_seed: int, scheme: str = "random",
                fractions: tuple[float, float, float] = (0.5, 0.25, 0.25), holdout_seed: int = 1,
                pool_max_rows: int | None = None) -> pd.Series:
    """Label every row 'reference' / 'selection' / 'test' (pilot), 'holdout' (reserved) or 'unused'.

    random   : group-aware random split of the design pool (exact duplicates stay together)
    temporal : earliest delivery periods -> reference, then selection, latest -> test (periods never split)
    """
    pool = design_pool(df, contract, holdout_seed)
    lab = pd.Series("holdout", index=df.index, name="partition")
    if pool_max_rows and pool.sum() > pool_max_rows:
        # large tables: one fixed random subset of the design pool (same for every pilot seed) bounds the cost
        keep = df.index[pool].to_series().sample(pool_max_rows, random_state=holdout_seed).index
        lab[pool & ~df.index.isin(keep)] = "unused"
        pool = pool & df.index.isin(keep)
    inner = make_split(df[pool], contract, seed=pilot_seed, scheme=scheme, fractions=fractions)
    lab.loc[inner.index] = inner.map({"reference": "reference", "dev": "selection", "test": "test"})
    return lab


def delivery_split(df: pd.DataFrame, contract, delivery: dict, holdout_seed: int = 1,
                   period_column: str = "_period") -> pd.Series:
    """Consecutive deliveries: explicit period lists for reference (history), selection and test.

    ``delivery = {"reference": [1, 2], "selection": [3], "test": [4]}``; the periods must be strictly ordered
    (history before selection before test). Rows of the confirmatory hold-out stay excluded.
    """
    ref, sel, tst = (list(delivery[k]) for k in ("reference", "selection", "test"))
    if not (max(ref) < min(sel) and max(sel) < min(tst)):
        raise ValueError(f"delivery periods must be consecutive and ordered: {delivery}")
    pool = design_pool(df, contract, holdout_seed)
    lab = pd.Series("unused", index=df.index, name="partition")
    per = df[period_column]
    for name, ps in (("reference", ref), ("selection", sel), ("test", tst)):
        lab[pool & per.isin(ps)] = name
    lab[~pool] = "holdout"
    return lab
