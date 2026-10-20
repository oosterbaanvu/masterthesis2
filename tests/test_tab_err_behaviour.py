"""Pinned behaviour of tab_err 0.2.1 that the framework works around (see docs/error_injection_validation.md).

If an upgrade changes any of these, the corresponding workaround must be re-evaluated.
"""

import warnings

import numpy as np
import pandas as pd
import pytest
from tab_err.api import low_level
from tab_err.error_mechanism import ECAR
from tab_err.error_type import AddDelta, CategorySwap, WrongUnit

warnings.filterwarnings("ignore")


@pytest.fixture
def frame():
    rng = np.random.default_rng(0)
    return pd.DataFrame({"c": pd.Categorical(rng.choice(list("abcde"), 2000)),
                         "x": rng.normal(50_000, 20_000, 2000).round()})


def _swap(frame, weighing, global_seed):
    np.random.seed(global_seed)
    d, m = low_level.create_errors(frame, "c", 0.1, ECAR(seed=1), CategorySwap(config={"mislabel_weighing": weighing}, seed=1))
    return d["c"][m["c"]].astype(str).tolist()


def test_category_swap_frequency_depends_on_global_numpy_state(frame):
    # pandas .sample() without random_state is used internally -> not reproducible from tab_err seeds
    assert _swap(frame, "frequency", 0) != _swap(frame, "frequency", 1)


def test_category_swap_uniform_is_reproducible(frame):
    assert _swap(frame, "uniform", 0) == _swap(frame, "uniform", 1)


def test_add_delta_default_is_immaterial_for_amounts(frame):
    d, m = low_level.create_errors(frame, "x", 0.1, ECAR(seed=1), AddDelta(seed=1))
    delta = np.abs((d["x"] - frame["x"])[m["x"]]).max()
    assert delta < 5  # a z-scale delta added to amounts of ~50,000: not a material error


def test_wrong_unit_mask_includes_unchanged_zero_cells():
    z = pd.DataFrame({"x": [0.0] * 50 + [100.0] * 50})
    d, m = low_level.create_errors(z, "x", 0.5, ECAR(seed=1), WrongUnit(seed=1))
    assert int(m["x"].sum()) == 50
    assert int((d["x"] != z["x"]).sum()) < 50  # mask overstates the realised errors


def test_category_swap_maps_each_true_code_to_one_wrong_code(frame):
    """tab_err 0.2.1 + pandas 2.3: Series.apply on a categorical runs once per category, so within one
    call every cell with the same true code receives the same new code (systematic remap)."""
    d, m = low_level.create_errors(frame, "c", 0.2, ECAR(seed=1), CategorySwap(seed=1))
    pairs = pd.DataFrame({"orig": frame["c"][m["c"]].astype(str), "new": d["c"][m["c"]].astype(str)})
    assert (pairs.groupby("orig")["new"].nunique() == 1).all()
