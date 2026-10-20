import numpy as np
from sklearn.metrics import roc_auc_score

from dq_framework.detectors.cdc import ConformalDataCleaningHGB, _p_values, _q_hat
from dq_framework.injection import Scenario, inject


def test_q_hat_matches_reference_definition():
    s = np.arange(1, 101, dtype=float)
    assert _q_hat(s, 0.9) == 91.0  # quantile 0.9 * (1 + 1/100) = 0.909, 'higher'
    assert _q_hat(np.array([]), 0.9) is None


def test_p_values_are_valid():
    cal = np.sort(np.arange(10, dtype=float))
    p = _p_values(cal, np.array([-1.0, 4.5, 100.0]))
    assert np.allclose(p, [11 / 11, 6 / 11, 1 / 11])


def test_cdc_ranks_injected_scaling_errors_and_rarely_alerts_on_clean(toy_contract, toy_data):
    ref, batch = toy_data
    det = ConformalDataCleaningHGB(confidence=0.99, max_iter=50, calibration_rows=500).fit(ref, toy_contract)
    clean = det.score(batch.assign(_scenario_id="u")).scores
    assert clean["flag"].mean() < 0.03
    r = inject(batch, Scenario("toy", "balance", "scale", "soft_ecar", 0.05, 1, {"factor": 10}), toy_contract, ref)
    s = det.score(r.corrupted.assign(_scenario_id="x")).scores
    s = s[s["column"] == "balance"]
    y = s["_row_id"].isin(set(r.log["_row_id"]))
    assert roc_auc_score(y, s["score"]) > 0.95
    assert s.loc[y, "flag"].mean() > 0.8


def test_strict_set_rule_over_alerts_with_tied_probabilities(toy_contract, toy_data):
    """Inclusive sets (s <= q_hat) keep coverage under ties; the original strict rule (s < q_hat) does not."""
    ref, batch = toy_data
    b = batch.assign(_scenario_id="u")
    inc = ConformalDataCleaningHGB(confidence=0.99, max_iter=30, calibration_rows=500, target_columns=["status"]).fit(ref, toy_contract)
    strict = ConformalDataCleaningHGB(confidence=0.99, max_iter=30, calibration_rows=500, target_columns=["status"],
                                      set_rule="strict_original").fit(ref, toy_contract)
    assert inc.score(b).scores["flag"].mean() <= strict.score(b).scores["flag"].mean()
