"""Integrity of downloaded raw data (skipped when datasets are not present, e.g. in CI)."""

import pytest

from dq_framework.acquisition import load_registry, verify
from dq_framework.datasets import check_table_shape

from .conftest import data_available

REG = load_registry()


@pytest.mark.data
@pytest.mark.parametrize("key", [k for k, s in REG.items() if not s.manual])
def test_raw_files_match_pinned_hashes_and_shape(key):
    if not data_available(key):
        pytest.skip(f"{key} not downloaded (run scripts/download_datasets.py)")
    res = verify(REG[key])
    assert res["status"] == "VERIFIED", res["problems"]
    shape = check_table_shape(REG[key])
    assert shape["ok"], shape["problems"]
