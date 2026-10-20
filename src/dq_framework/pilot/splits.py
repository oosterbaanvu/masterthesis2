"""Pilot partitions inside the design pool; the confirmatory hold-out is never touched."""

from __future__ import annotations

import pandas as pd

from dq_framework.datasets import make_split

PILOT_PARTS = ("reference", "selection", "test")


def design_pool(df: pd.DataFrame, contract, holdout_seed: int = 1, holdout_partition: str = "test") -> pd.Series:
    """True for rows the pilot may use: everything except the hold-out partition of ``holdout_seed``."""
    return make_split(df, contract, seed=holdout_seed, scheme="random") != holdout_partition


def pilot_split(df: pd.DataFrame, contract, pilot_seed: int, scheme: str = "random",
                fractions: tuple[float, float, float] = (0.5, 0.25, 0.25), holdout_seed: int = 1) -> pd.Series:
    """Label every row 'reference' / 'selection' / 'test' (pilot) or 'holdout' (reserved, unused).

    random   : group-aware random split of the design pool (exact duplicates stay together)
    temporal : earliest delivery periods -> reference, then selection, latest -> test (periods never split)
    """
    pool = design_pool(df, contract, holdout_seed)
    lab = pd.Series("holdout", index=df.index, name="partition")
    inner = make_split(df[pool], contract, seed=pilot_seed, scheme=scheme, fractions=fractions)
    lab.loc[inner.index] = inner.map({"reference": "reference", "dev": "selection", "test": "test"})
    return lab
