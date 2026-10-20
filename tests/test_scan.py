"""Operational scan: findings with provenance, recommendation logic, feedback summary."""

import json

import numpy as np
import pandas as pd
import pytest
import yaml

from dq_framework.service.scan import recommend, run_scan, summarise_feedback

from .conftest import data_available

EVID = pd.DataFrame([
    {"dataset": "d", "scheme": "random", "baseline": "full", "budget": 25.0, "test_set": "test_heldout", "detector": "good",
     "utility": 0.2, "utility_lo": 0.1, "utility_hi": 0.3, "n_replications": 5},
    {"dataset": "d", "scheme": "random", "baseline": "full", "budget": 25.0, "test_set": "test_heldout", "detector": "weak",
     "utility": 0.01, "utility_lo": 0.0, "utility_hi": 0.02, "n_replications": 5},
    {"dataset": "d", "scheme": "random", "baseline": "full", "budget": 25.0, "test_set": "test_heldout", "detector": "single",
     "utility": 0.2, "utility_lo": 0.2, "utility_hi": 0.2, "n_replications": 1},
])


def test_recommendation_rule():
    rule = {"min_gain": 0.05, "max_extra_alerts_per_1k": 50}
    assert recommend("good", True, EVID, "full", 25.0, "random", 25, 1.0, rule)["recommendation"] == "ADOPT"
    assert recommend("weak", True, EVID, "full", 25.0, "random", 25, 1.0, rule)["recommendation"] == "DO_NOT_ADOPT"
    # one replication: no interval over replications -> never ADOPT
    assert recommend("single", True, EVID, "full", 25.0, "random", 25, 1.0, rule)["recommendation"] == "INSUFFICIENT_EVIDENCE"
    # strong shift between this batch and the evaluation conditions blocks ADOPT
    r = recommend("good", True, EVID, "full", 25.0, "random", 25, 10.0, rule)
    assert r["recommendation"] == "INSUFFICIENT_EVIDENCE" and any("shift" in x for x in r["reasons"])
    # binary detector with too many extra alerts on this batch
    assert recommend("good", False, EVID, "full", 25.0, "random", 400, 1.0, rule)["recommendation"] == "DO_NOT_ADOPT"
    assert recommend("missing", True, EVID, "full", 25.0, "random", 0, 1.0, rule)["recommendation"] == "INSUFFICIENT_EVIDENCE"


def test_feedback_summary(tmp_path):
    pd.DataFrame({"finding_id": ["F1", "F2", "F3", "F4"], "source": ["rule:a", "rule:a", "detector:x", "detector:x"],
                  "verdict": ["confirmed_error", "not_an_error", "", "unsure"]}).to_csv(tmp_path / "feedback.csv", index=False)
    s = summarise_feedback(tmp_path).set_index("source")
    assert s.loc["rule:a", "adjudicated_precision"] == 0.5
    assert np.isnan(s.loc["detector:x", "adjudicated_precision"]) and s.loc["detector:x", "annotated"] == 1
    pd.DataFrame({"finding_id": ["F1"], "source": ["rule:a"], "verdict": ["maybe"]}).to_csv(tmp_path / "feedback.csv", index=False)
    with pytest.raises(ValueError):
        summarise_feedback(tmp_path)


@pytest.mark.data
@pytest.mark.dbt
@pytest.mark.skipif(not data_available("uci_credit"), reason="dataset not downloaded")
def test_scan_reports_findings_with_provenance(tmp_path):
    cfg = {"name": "t", "dataset": "uci_credit", "history": {"select": "row_range", "start": 1, "end": 6000},
           "batch": {"select": "row_range", "start": 29001, "end": 30000}, "budget_per_1k": 25,
           "detectors": {"lucario_core": {"name": "lucario_core", "params": {}},
                         "dboost_gaussian_text": {"name": "dboost", "params": {"model": "gaussian", "type_mode": "text"}},
                         "iforest": {"name": "iforest_row", "params": {}}}}
    p = tmp_path / "scan.yaml"
    p.write_text(yaml.safe_dump(cfg))
    out = run_scan(p, tmp_path / "out")
    f = pd.read_csv(out / "findings.csv")
    assert {"finding_id", "_row_id", "record_key", "column", "value", "source", "score", "explanation"} <= set(f.columns)
    assert f["source"].str.startswith("rule:").any() and f["source"].str.startswith("detector:").any()
    assert f["explanation"].notna().all()
    s = json.loads((out / "scan_summary.json").read_text())
    assert s["excluded_research_holdout"] and {r["recommendation"] for r in s["recommendations"]} == {"INSUFFICIENT_EVIDENCE"}
    assert (out / "feedback.csv").exists() and (out / "scan_report.md").exists()
