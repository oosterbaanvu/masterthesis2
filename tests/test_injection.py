import numpy as np
import pandas as pd
import pytest
from scipy import stats

from dq_framework.injection import Scenario, inject
from dq_framework.injection.mechanisms import make_mechanism
from dq_framework.injection.validation import validate

CASES = [
    ("balance", "scale", {"factor": 10}),
    ("balance", "sign_flip", {}),
    ("balance", "digit_transposition", {}),
    ("balance", "rounding", {"unit": 1000}),
    ("balance", "plausible_substitution", {}),
    ("balance", "missing", {}),
    ("balance", "outlier", {}),
    ("status", "category_swap", {}),
    ("status", "category_swap", {"weighing": "uniform"}),
    ("status", "code_remap", {}),
    ("status", "invalid_code", {"code": "Z"}),
    ("status", "plausible_substitution", {}),
    ("limit_amt", "period_shift", {"source_column": "balance"}),
]
MECHS = [("soft_ecar", {}), ("tab_err_ecar", {}), ("soft_ear", {"condition_column": "limit_amt", "strength": 4.0}),
         ("tab_err_ear", {"condition_column": "limit_amt"}), ("soft_enar", {"strength": 4.0}), ("tab_err_enar", {})]


@pytest.mark.parametrize("col,op,params", CASES)
@pytest.mark.parametrize("mech,mp", MECHS)
def test_every_operation_mechanism_pair_validates(toy_contract, toy_data, col, op, params, mech, mp):
    ref, batch = toy_data
    if mech == "soft_enar" and toy_contract.column(col).type == "categorical":
        mp = {"strength": 4.0, "segment_values": ["A"]}
    sc = Scenario("toy", col, op, mech, 0.05, 7, params, mp)
    v = validate(batch, sc, toy_contract, ref)
    assert v["real_change_all"], v["notes"]
    assert v["realised_errors"] == v["intended_errors"] == 50
    assert v["no_side_effects"] and v["reproducible"] and v["semantics_ok"]


def test_reference_overlap_is_rejected(toy_contract, toy_data):
    ref, _ = toy_data
    with pytest.raises(ValueError, match="leakage"):
        inject(ref.head(100), Scenario("toy", "balance", "scale", "soft_ecar", 0.1, 1), toy_contract, ref)


def test_scale_never_selects_zero(toy_contract, toy_data):
    ref, batch = toy_data
    b = batch.copy()
    b.loc[b.index[:500], "balance"] = 0.0
    r = inject(b, Scenario("toy", "balance", "scale", "soft_ecar", 0.2, 3, {"factor": 10}), toy_contract, ref)
    assert (pd.to_numeric(r.log["original"]) != 0).all()


def _selection(batch, mech, mp, n=100, seed=5, target="balance"):
    m = make_mechanism(mech, **mp)
    elig = pd.Series(True, index=batch.index)
    return batch.index.isin(m.select(batch, target, elig, n, seed))


def test_ecar_is_independent_and_enar_depends_on_own_value(toy_data):
    _, batch = toy_data
    ks = lambda sel, c: stats.ks_2samp(batch.loc[sel, c], batch.loc[~sel, c]).statistic  # noqa: E731
    sel_ecar = _selection(batch, "soft_ecar", {})
    sel_enar = _selection(batch, "soft_enar", {"strength": 6.0, "direction": "high"})
    assert ks(sel_ecar, "balance") < 0.15
    assert ks(sel_enar, "balance") > 0.3
    assert batch.loc[sel_enar, "balance"].mean() > batch["balance"].mean()


def test_soft_strength_zero_equals_ecar(toy_data):
    _, batch = toy_data
    a = _selection(batch, "soft_ear", {"condition_column": "limit_amt", "strength": 0.0})
    b = _selection(batch, "soft_ecar", {})
    assert (a == b).all()


def test_tab_err_enar_selects_a_contiguous_value_window(toy_data):
    """Documents tab_err 0.2.1 behaviour: ENAR corrupts one contiguous block of the sorted values."""
    _, batch = toy_data
    sel = _selection(batch, "tab_err_enar", {}, n=100)
    order = batch["balance"].sort_values(kind="mergesort").index
    pos = np.flatnonzero(np.isin(order, batch.index[sel]))
    assert pos.max() - pos.min() + 1 <= 100 + int((batch["balance"].duplicated()).sum())


def test_tab_err_ear_on_low_cardinality_condition_follows_row_order():
    """Documents a tie-order artefact: with a binary condition column, tab_err EAR's window falls inside the
    tie block of one category, and pandas' (unstable) sort keeps rows of a tie block close to file order.
    The selection is therefore concentrated in a narrow region of the file, not spread over the category."""
    n = 1000
    df = pd.DataFrame({"_row_id": range(n), "v": np.arange(n, dtype=float),
                       "c": ["x"] * 700 + ["y"] * 300})
    m = make_mechanism("tab_err_ear", condition_column="c")
    sel = m.select(df, "v", pd.Series(True, index=df.index), 50, seed=1)
    rows = np.sort(np.asarray(sel))
    assert df.loc[rows, "c"].nunique() == 1          # one category only
    assert rows.max() - rows.min() + 1 <= 4 * 50     # narrow file-order region (a random subset would span ~700)


def test_category_swap_is_independent_per_cell(toy_contract, toy_data):
    ref, batch = toy_data
    r = inject(batch, Scenario("toy", "status", "category_swap", "soft_ecar", 0.3, 4, {"weighing": "uniform"}),
               toy_contract, ref)
    per_orig = r.log.assign(o=r.log["original"].astype(str), n=r.log["injected"].astype(str)).groupby("o")["n"].nunique()
    assert (per_orig > 1).any()


def test_frequency_weighted_swap_prefers_common_codes(toy_contract, toy_data):
    ref, batch = toy_data
    r = inject(batch, Scenario("toy", "status", "category_swap", "soft_ecar", 0.3, 4, {"weighing": "frequency"}),
               toy_contract, ref)
    rare = ref["status"].value_counts().idxmin()
    share_rare = (r.log["injected"].astype(str) == rare).mean()
    r_u = inject(batch, Scenario("toy", "status", "category_swap", "soft_ecar", 0.3, 4, {"weighing": "uniform"}),
                 toy_contract, ref)
    assert share_rare < (r_u.log["injected"].astype(str) == rare).mean()


def test_ordinal_shift_changes_to_an_observed_neighbour():
    from dq_framework.injection.operations import OpContext, make_operation

    s = pd.Series(["mar", "may", "jun", "dec", "may"], index=range(5), dtype=object)
    ctx = OpContext("categorical", pd.Series(["mar", "apr", "may", "jun", "dec"]), pd.DataFrame({"m": s}),
                    domain=["apr", "dec", "jun", "mar", "may"])
    op = make_operation("ordinal_shift", order=["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                                "oct", "nov", "dec"], step=-1)
    elig = op.eligible(s, ctx)
    # mar -> feb (never observed) and dec -> nov (never observed) are not eligible
    assert elig.tolist() == [False, True, True, False, True]
    out = op.apply(s, s.index[elig], ctx, seed=0)
    assert out.tolist() == ["apr", "may", "apr"]


@pytest.mark.parametrize("mech,mp", [("tab_err_ear", {"condition_column": "id"}),
                                     ("soft_ear", {"condition_column": "segment", "segment_values": [2], "strength": 4.0})])
def test_pilot_block_and_segment_mechanisms_log_only_changed_cells(toy_contract, toy_data, mech, mp):
    """Realistic pilot mechanisms: a contiguous record block (one upstream file segment) and a segment."""
    ref, batch = toy_data
    sc = Scenario("toy", "balance", "scale", mech, 0.05, 3, {"factor": 10}, mp)
    v = validate(batch, sc, toy_contract, ref)
    assert v["real_change_all"] and v["no_side_effects"] and v["realised_errors"] == 50
    r = inject(batch, sc, toy_contract, ref)
    ids = np.sort(r.log["_row_id"].to_numpy())
    if mech == "tab_err_ear":
        # one contiguous window of the sorted id (eligible rows only; here every row is eligible)
        assert ids[-1] - ids[0] == len(ids) - 1
    else:
        seg = batch.set_index("_row_id").loc[ids, "segment"]
        assert (seg == 2).mean() > 0.8


def test_injection_log_counts_only_changed_cells_when_operation_is_a_no_op(toy_contract, toy_data):
    """plausible_substitution can fail to find a material change; such cells must not be logged."""
    ref, batch = toy_data
    b = batch.copy()
    b["balance"] = 5000.0  # constant column: reference draws within 20 % of 5000 do not count
    sc = Scenario("toy", "balance", "plausible_substitution", "soft_ecar", 0.05, 1, {"min_rel_diff": 50.0}, {})
    r = inject(b, sc, toy_contract, ref)
    assert r.realised == len(r.log) <= r.intended
    assert (pd.to_numeric(r.log["original"]) != pd.to_numeric(r.log["injected"])).all()
