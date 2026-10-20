"""Leakage, label validity, compatibility and budget checks for published benchmark scans."""

import builtins
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from dq_framework import paths
from dq_framework.contracts import Column, Contract, load_contract
from dq_framework.datasets import load_contract_table, make_split
from dq_framework.evaluation.published import evaluate_scans, label_cells, scan_config, selection_metrics
from dq_framework.service.partitioning import grouped_partitions
from dq_framework.service.review import review_order
from dq_framework.service.scan import run_scan

from .conftest import data_available, make_toy


def test_dirty_missing_tokens_are_opt_in_and_unknown_numbers_are_rejected(monkeypatch):
    contract = Contract("d", "t", "", None, [Column("amount", "numeric", missing_tokens=["?"])], {}, [])
    raw = pd.DataFrame({"amount": ["?", "20."]})
    monkeypatch.setattr("dq_framework.datasets.load_raw_table", lambda _: raw)
    monkeypatch.setattr("dq_framework.datasets.get_spec", lambda _: None)
    typed = load_contract_table("d", contract)
    assert np.isnan(typed["amount"].iloc[0]) and typed["amount"].iloc[1] == 20
    assert raw["amount"].tolist() == ["?", "20."]
    raw.loc[0, "amount"] = "unrecognised"
    with pytest.raises(ValueError):
        load_contract_table("d", contract)


def test_group_split_reserves_legacy_holdout_and_keeps_dirty_entities_together(toy_contract):
    df = make_toy(200)
    raw = pd.DataFrame({"name": [f"name{i // 2}" for i in range(200)], "class": ["?"] * 200})
    p = grouped_partitions(raw, df, toy_contract, ["name", "class"])
    assert p.groupby("group")["partition"].nunique().max() == 1
    original_holdout = make_split(df, toy_contract, seed=1) == "test"
    assert (p.loc[original_holdout, "partition"] == "holdout").all()
    assert p["group"].nunique() == 100  # missing '?' classes never join all records
    assert set(p["partition"]) == {"history", "batch", "holdout"}
    pd.testing.assert_frame_equal(p, grouped_partitions(raw, df, toy_contract, ["name", "class"]))


def test_budget_order_does_not_review_missing_scores_or_invent_binary_scores():
    s = pd.DataFrame({"_row_id": [1, 2, 3, 4], "column": ["v"] * 4,
                      "score": [np.nan, 0.8, np.inf, 0.9], "flag": [False, True, True, False]})
    assert review_order(s, ranked=True)["_row_id"].tolist() == [4, 2]
    binary = s.assign(score=np.nan)
    ranked = review_order(binary)
    assert set(ranked["_row_id"]) == {2, 3} and ranked["score"].isna().all()
    pd.testing.assert_frame_equal(ranked, review_order(binary.sample(frac=1, random_state=4)))


def test_labels_do_not_turn_reference_ambiguity_or_formatting_into_proven_errors():
    numeric = Contract("d", "t", "", None, [Column("v", "numeric", missing_tokens=["?", ""])], {}, [])
    dirty = pd.DataFrame({"v": ["?", "3504.", "12", "?"]}, index=[10, 11, 12, 13])
    clean = pd.DataFrame({"v": ["12", "3504.0", "13", "?"]}, index=dirty.index)
    labels = label_cells("jung_cars", dirty, clean, numeric)
    assert labels["label"].tolist() == ["missing", "formatting", "value_candidate", "reference_missing"]
    assert labels["_row_id"].tolist() == [11, 12, 13, 14]
    rayyan = label_cells("raha_rayyan", dirty, clean, numeric)
    assert rayyan["label"].tolist() == ["uncertain", "formatting", "uncertain", "reference_missing"]


def test_reference_error_metrics_exclude_uncertain_labels_and_preserve_alert_cost():
    labels = pd.DataFrame({"_row_id": [1, 2, 3, 4], "column": ["v"] * 4,
                           "label": ["missing", "formatting", "uncertain", "agreement"],
                           "changed": [True, True, True, False]})
    m = selection_metrics(labels, labels)
    assert m["reviews"] == 4 and m["reference_error_recall"] == 1
    assert m["reference_error_precision"] == 1 / 3
    assert m["uncertain_reviews"] == 1 and m["reviews_formatting"] == 1 and m["reviews_agreement"] == 1


def test_changed_scan_artifacts_cannot_be_evaluated(tmp_path, monkeypatch):
    monkeypatch.setattr("dq_framework.evaluation.published.fingerprints", lambda _: {"a": "frozen"})
    (tmp_path / "completed_scans.json").write_text(json.dumps({
        "fingerprints": {"a": "different"}, "jobs": []}))
    with pytest.raises(ValueError, match="changed"):
        evaluate_scans(tmp_path / "p.yaml", tmp_path, tmp_path / "out")


@pytest.mark.data
@pytest.mark.dbt
@pytest.mark.parametrize("dataset", ["raha_rayyan", "jung_restaurant", "jung_cars"])
def test_actual_service_scan_does_not_open_clean_reference(tmp_path, monkeypatch, dataset):
    if not data_available(dataset):
        pytest.skip("published dataset not downloaded")
    protocol = yaml.safe_load((paths.CONFIG_DIR / "benchmarks/published_errors.yaml").read_text())
    cfg = scan_config(protocol, dataset, 11)
    p = tmp_path / "scan.yaml"
    p.write_text(yaml.safe_dump(cfg))
    original = builtins.open

    def deny_clean(file, *args, **kwargs):
        if isinstance(file, str | Path) and Path(file).name == "clean.csv":
            raise AssertionError("clean reference accessed by operational service")
        return original(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", deny_clean)
    monkeypatch.setattr("dq_framework.datasets.load_pair", lambda *_: pytest.fail("pair loader called by service"))
    out = run_scan(p, tmp_path / "scan")
    summary = json.loads((out / "scan_summary.json").read_text())
    assert not any(d["status"] == "failed" for d in summary["detectors"])
    findings = pd.read_csv(out / "findings.csv")
    assert len(findings) and findings["explanation"].notna().all()
    assert set(r["recommendation"] for r in summary["recommendations"]) == {"INSUFFICIENT_EVIDENCE"}
    scores = pd.read_parquet(out / "detector_scores.parquet")
    assert scores.groupby("detector")["review_selected"].sum().max() <= summary["review_slots"]
    if dataset in ("raha_rayyan", "jung_restaurant"):
        cdc = next(d for d in summary["detectors"] if d["detector"] == "cdc")
        assert cdc["status"] == "incompatible"
    assert load_contract(dataset).excluded_columns
