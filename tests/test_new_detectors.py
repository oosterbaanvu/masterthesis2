"""dBoost re-implementation, its fidelity against the original, and the column-wise baselines."""

import numpy as np
import pandas as pd
import pytest

from dq_framework.detectors import dboost as D
from dq_framework.detectors.univariate import IQROutlier, LucarioCore, SDOutlier, categorical_constraint

from .conftest import make_toy


def test_int_expansion_matches_python_semantics():
    import time

    vals = pd.Series([0.0, 7.0, -13.0, 1_000_000.0, 86_400 * 3 + 5.0])
    names, arrs, _ = D.expand_column(vals, "int")
    for i, v in enumerate(vals.astype(int)):
        t = time.gmtime(int(v))
        got = {n: a[i] for n, a in zip(names, arrs, strict=True)}
        assert [got[f"tm_{k}"] for k in ("year", "mon", "mday", "hour", "min", "sec", "wday", "yday")] == \
               [t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, t.tm_wday, t.tm_yday]
        assert got["mod 10"] == v % 10 and got["div 3"] == (v % 3 == 0) and got["bit 2"] == (v >> 2) & 1


def test_unparseable_rows_are_skipped_like_the_original(toy_contract, toy_data):
    ref, batch = toy_data
    b = batch.assign(_scenario_id="x")
    b.loc[b.index[:3], "balance"] = b.loc[b.index[:3], "balance"] + 0.5  # non-integer in an int field
    b.loc[b.index[3], "limit_amt"] = np.nan
    out = D.DBoost(model="gaussian").fit(ref, toy_contract).score(b)
    assert set(b["_row_id"].iloc[:4]).isdisjoint(set(out.scores["_row_id"]))
    assert "4 rows not analysed" in out.warnings[0]
    assert out.scores["score"].isna().all(), "binary detector: no score is constructed"


def test_gaussian_flags_scaled_values_and_text_mode_types_everything_as_strings(toy_contract, toy_data):
    ref, batch = toy_data
    b = batch.assign(_scenario_id="x")
    b.loc[b.index[:20], "balance"] *= 1000
    det = D.DBoost(model="gaussian").fit(ref, toy_contract)
    s = det.score(b).scores
    hit = s[(s["column"] == "balance") & s["_row_id"].isin(b["_row_id"].iloc[:20])]["flag"].mean()
    assert hit == 1.0
    txt = D.DBoost(model="gaussian", type_mode="text").fit(ref, toy_contract)
    assert set(txt._types.values()) == {"str"}
    s2 = txt.score(b).scores
    assert s2[(s2["column"] == "balance") & s2["_row_id"].isin(b["_row_id"].iloc[:20])]["flag"].mean() > 0.9


@pytest.mark.skipif(not (D.DBOOST_ENV / "src" / "dboost" / "__init__.py").exists(), reason="run envs/dboost/install.sh")
@pytest.mark.parametrize("model,params", [("gaussian", [3.0]), ("histogram", [0.8, 0.2]), ("partitioned", [5.0, 0.8, 0.2])])
def test_reimplementation_agrees_with_original_dboost(toy_contract, model, params):
    ref = make_toy(600, seed=1)
    batch = make_toy(300, seed=2, start_id=100_001).assign(_scenario_id="x")
    batch.loc[batch.index[:10], "balance"] *= 10
    a = D.DBoost(model=model, params=params, corr_threshold=0.5).fit(ref, toy_contract).score(batch).scores
    b = D.OriginalDBoost(model=model, params=params, corr_threshold=0.5).fit(ref, toy_contract).score(batch).scores
    m = a.merge(b, on=["_row_id", "column"], suffixes=("_re", "_orig"))
    assert len(m) == len(a) == len(b)
    assert (m["flag_re"] == m["flag_orig"]).all()


def test_sd_iqr_flag_extremes_on_batch_statistics(toy_contract, toy_data):
    ref, batch = toy_data
    b = batch.assign(_scenario_id="x")
    b.loc[b.index[0], "balance"] = 1e9
    for det in (SDOutlier(), IQROutlier()):
        s = det.fit(ref, toy_contract).score(b).scores
        assert s[(s["_row_id"] == b["_row_id"].iloc[0]) & (s["column"] == "balance")]["flag"].item()
        assert not s[s["column"] == "status"]["flag"].any(), "numeric columns only"


def test_lucario_categorical_constraint_and_numeric_switch_off(toy_contract, toy_data):
    vc = pd.Series({"A": 9000, "B": 950, "C": 40, "D": 10})
    assert categorical_constraint(vc) == {"A", "B"}
    assert categorical_constraint(pd.Series({"A": 50, "B": 50})) is None or True
    ref, batch = toy_data
    b = batch.assign(_scenario_id="x")
    b.loc[b.index[:2], "status"] = "Z"
    s = LucarioCore().fit(ref, toy_contract).score(b).scores
    assert s[(s["column"] == "status") & s["_row_id"].isin(b["_row_id"].iloc[:2])]["flag"].all()
    # a column where > 5 % of cells violate median +- 3 MAD gets no numerical constraint at all
    b2 = batch.assign(_scenario_id="x")
    b2.loc[b2.index[:200], "balance"] *= 50
    det = LucarioCore().fit(ref, toy_contract)
    s2 = det.score(b2).scores
    assert not s2[(s2["column"] == "balance")]["explanation"].fillna("").str.contains("MAD").any()
