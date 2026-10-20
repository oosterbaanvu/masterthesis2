from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dq_framework import paths
from dq_framework.contracts import load_contract

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def toy_contract():
    return load_contract(FIXTURES / "toy_contract.yaml")


def make_toy(n: int, seed: int = 0, start_id: int = 1) -> pd.DataFrame:
    """Synthetic accounts: balance depends on limit and segment, so a learned model can predict it."""
    rng = np.random.default_rng(seed)
    segment = rng.integers(1, 3, n)
    limit_amt = rng.choice([10_000, 20_000, 50_000, 100_000], n).astype(float)
    balance = np.round(limit_amt * (0.2 + 0.3 * (segment == 2)) + rng.normal(0, 500, n))
    status = np.where(balance > 0.4 * limit_amt, "B", np.where(rng.random(n) < 0.05, "C", "A"))
    df = pd.DataFrame(
        {
            "_row_id": np.arange(start_id, start_id + n),
            "id": np.arange(start_id, start_id + n),
            "limit_amt": limit_amt,
            "balance": balance.astype(float),
            "status": pd.array(status, dtype="string"),
            "segment": pd.array(segment, dtype="Int64"),
        }
    )
    return df


@pytest.fixture
def toy_data():
    ref = make_toy(4000, seed=1, start_id=1)
    batch = make_toy(1000, seed=2, start_id=100_001)
    return ref, batch


def data_available(key: str) -> bool:
    return (paths.RAW_DIR / key).exists() and any((paths.RAW_DIR / key).iterdir())
