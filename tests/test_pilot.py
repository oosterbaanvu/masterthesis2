"""Pilot design: hold-out isolation, equal strategy budgets, disjoint held-out family, metric definitions."""

from collections import Counter

import numpy as np
import pytest

from dq_framework import paths
from dq_framework.contracts import load_contract
from dq_framework.pilot import metrics as M
from dq_framework.pilot.runner import load_config
from dq_framework.pilot.scenarios import build_all
from dq_framework.pilot.splits import design_pool, pilot_split

from .conftest import data_available

CONFIGS = sorted((paths.CONFIG_DIR / "pilot").glob("pilot_*.yaml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_strategies_have_equal_budgets_and_heldout_is_disjoint(path):
    cfg = load_config(path)
    contract = load_contract(cfg["dataset"])
    scs = build_all(cfg, contract, pilot_seed=11)
    by_set = Counter(s.set_name for s in scs)
    assert by_set["sel_simple"] == by_set["sel_diverse"] == by_set["test_simple"] == by_set["test_diverse"]
    # same cases x rates in both strategies, same number of scenarios per (case, rate)
    cell = lambda name: Counter((s.case_id, s.scenario.rate) for s in scs if s.set_name == name)  # noqa: E731
    assert cell("sel_simple") == cell("sel_diverse")
    assert {s.mechanism_setting for s in scs if s.set_name == "sel_simple"} == {"ecar"}
    assert len({s.mechanism_setting for s in scs if s.set_name == "sel_diverse"}) >= 4
    sel_cases = {(s.scenario.column, s.scenario.operation) for s in scs if s.set_name.startswith("sel_")}
    held = [s for s in scs if s.set_name == "test_heldout"]
    assert held and not ({(s.scenario.column, s.scenario.operation) for s in held} & sel_cases)
    sel_mechs = {s.mechanism_setting for s in scs if s.set_name.startswith("sel_")}
    assert not ({s.mechanism_setting for s in held} - {"ecar"}) & sel_mechs
    # no seed is shared between selection and test scenarios; ids are unique
    sel_seeds = {s.scenario.seed for s in scs if s.partition == "selection"}
    assert not sel_seeds & {s.scenario.seed for s in scs if s.partition == "test"}
    assert len({s.sid for s in scs}) == len(scs)
    # reproducible
    assert [s.sid for s in build_all(cfg, contract, 11)] == [s.sid for s in scs]
    assert [s.sid for s in build_all(cfg, contract, 12)] != [s.sid for s in scs]


@pytest.mark.data
@pytest.mark.skipif(not data_available("uci_credit"), reason="dataset not downloaded")
def test_pilot_split_never_uses_the_confirmatory_holdout():
    from dq_framework.datasets import load_contract_table, make_split

    c = load_contract("uci_credit")
    df = load_contract_table("uci_credit", c)
    holdout = make_split(df, c, seed=1) == "test"
    for seed in (11, 12):
        lab = pilot_split(df, c, seed)
        assert (lab[holdout] == "holdout").all()
        assert set(lab[~holdout]) == {"reference", "selection", "test"}
        assert design_pool(df, c).sum() == (~holdout).sum()
    a, b = pilot_split(df, c, 11), pilot_split(df, c, 12)
    assert (a != b).any(), "pilot seeds must give different re-splits"


def test_budget_capped_flag_recall_and_ranked_recall():
    n, m = 1000, 2
    inj = np.zeros((n, m), bool)
    inj[:10, 0] = True  # 10 injected cells
    base = np.zeros((n, m), bool)
    base[:2, 0] = True  # baseline finds 2
    flags = np.zeros((n, m), bool)
    flags[:6, 0] = True  # detector flags 6 injected (2 already in baseline) ...
    flags[100:136, 1] = True  # ... and 36 untouched cells
    r = M.cell_metrics(inj, base, flags, None, (10, 50))
    assert r["recall_L"] == 0.6 and r["incremental_recall_flags"] == 0.4
    assert r["extra_alerts_untouched_per_1k"] == 36.0
    # 40 extra flags, budget 10 -> expected 4 hits x 10/40 = 1 found -> 0.1; budget 50 -> all 4 -> 0.4
    assert r["dR_flags@10"] == pytest.approx(0.1) and r["dR_flags@50"] == pytest.approx(0.4)
    assert "dR_ranked@10" not in r
    scores = np.zeros((n, m))
    scores[:10, 0] = np.arange(10, 0, -1)  # injected cells ranked first, baseline ones on top
    r = M.cell_metrics(inj, base, flags, scores, (5,), target_col=0)
    assert r["dR_ranked@5"] == pytest.approx(0.5)  # top 5 among non-baseline cells are injected rows 2..6
    assert r["auc_target"] == 1.0


def test_found_mask_and_row_metrics():
    inj = np.zeros((10, 2), bool)
    inj[0, 0] = inj[1, 1] = True
    base = np.zeros((10, 2), bool)
    base[1, 0] = True  # baseline implicates row 1 (other column): row-level it is caught
    flags = np.zeros((10, 2), bool)
    flags[0, 0] = True
    assert M.found_mask(inj, base, flags, None, 25).sum() == 1
    rm = M.row_metrics(inj, base, flags.any(1), None, (100,))
    assert rm["row_recall_B"] == 0.5 and rm["row_incremental_recall_flags"] == 0.5


def test_utility_key_never_ranks_binary_detectors():
    assert M.utility_key(True, 25) == "dR_ranked@25"
    assert M.utility_key(False, 25) == "dR_flags@25"


def test_decide_and_selection_regret_on_synthetic_runs():
    from dq_framework.pilot.analysis import decide

    assert decide(np.array([0.2, 0.3, 0.25]), 0.05)["decision"] == "ADOPT"
    assert decide(np.array([0.0, 0.01, 0.0]), 0.05)["decision"] == "DO_NOT_ADOPT"
    assert decide(np.array([0.0, 0.3]), 0.05)["decision"] == "INSUFFICIENT_EVIDENCE"
    assert decide(np.array([]), 0.05)["decision"] == "INSUFFICIENT_EVIDENCE"
