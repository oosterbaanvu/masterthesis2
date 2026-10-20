import numpy as np
import pandas as pd

from dq_framework.evaluation import DecisionRule, bootstrap_ci, evaluate_scenario


def test_incremental_metrics_on_handmade_example():
    log = pd.DataFrame({"_row_id": [1, 2, 3, 4], "column": ["a"] * 4})
    base = pd.DataFrame({"_row_id": [1, 9], "column": ["a", "a"], "tier": ["deterministic", "statistical"]})
    det = pd.DataFrame({"_row_id": [1, 2, 3, 7, 8], "column": ["a"] * 5,
                        "score": [0.9, 0.8, 0.1, 0.95, 0.2], "flag": [True, True, False, True, False]})
    m = evaluate_scenario(log, base, det, n_rows=1000, n_cols=2, target_column="a", budgets_per_1k=(2.0,)).metrics
    assert m["recall_B"] == 0.25 and m["recall_det"] == 0.25
    assert m["recall_L"] == 0.5
    assert m["incremental_recall"] == 0.25  # row 2 only (row 1 already in B)
    assert m["extra_alerts_untouched_per_1k"] == 1.0  # row 7
    # budget 2 cells: top-ranked non-B cells are row 7 (untouched) and row 2 (injected)
    assert m["incremental_recall_at_2_per_1k"] == 0.25


def test_decision_rule():
    rule = DecisionRule(min_gain=0.05, max_extra_alerts_per_1k=10)
    assert rule.decide(np.full(10, 0.2), np.full(10, 1.0))["decision"] == "ADOPT"
    assert rule.decide(np.full(10, 0.0), np.full(10, 1.0))["decision"] == "DO_NOT_ADOPT"
    assert rule.decide(np.array([0.0, 0.1, 0.0, 0.12]), np.full(4, 1.0))["decision"] == "INSUFFICIENT_EVIDENCE"
    assert rule.decide(np.full(10, 0.2), np.full(10, 50.0))["decision"] == "DO_NOT_ADOPT"


def test_bootstrap_ci_contains_mean():
    m, lo, hi = bootstrap_ci(np.array([0.1, 0.2, 0.3, 0.4]))
    assert lo <= m <= hi


def test_row_level_metrics_aggregate_cells_without_inventing_cells():
    from dq_framework.evaluation import evaluate_rows

    log = pd.DataFrame({"_row_id": [1, 2], "column": ["a", "b"]})
    base = pd.DataFrame({"_row_id": [1], "column": ["c"], "tier": ["statistical"]})  # other column, same record
    det = pd.DataFrame({"_row_id": [2, 2, 5], "column": [None, None, None], "score": [0.9, 0.1, 0.8],
                        "flag": [True, False, True]})
    m = evaluate_rows(log, base, det, n_rows=1000, budgets_per_1k=(1.0,))
    assert m["row_recall_B"] == 0.5          # record 1 alerted via another column
    assert m["row_recall_L"] == 0.5          # record 2
    assert m["row_incremental_recall"] == 0.5
    assert m["row_extra_alerts_untouched_per_1k"] == 1.0  # record 5
    assert m["row_incremental_recall_at_1_per_1k"] == 0.5  # top non-B record is record 2
