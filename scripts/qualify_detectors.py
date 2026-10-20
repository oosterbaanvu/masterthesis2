#!/usr/bin/env python
"""Detector qualification: real executions behind every entry of the compatibility matrix.

Sections (all on the DEV partition of split seed 1; nothing here is a confirmatory result):

  fidelity   CDC re-implementation vs. the original AutoGluon implementation on the same stacked batch
  seedvar    CDC flag recall / untouched alert rate / ranking AUC over calibration seeds and confidence levels
  matrix     one minimal real execution per (detector, dataset) pair -> PASS / CONDITIONAL / INCOMPATIBLE /
             BLOCKED / NOT TESTED, with the evidence that supports the verdict

Outputs: results/qualification/cdc_fidelity.json, cdc_seed_variance.json, compatibility_matrix.csv

Usage: python scripts/qualify_detectors.py [fidelity] [seedvar] [matrix]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score

from dq_framework import paths
from dq_framework.contracts import load_contract
from dq_framework.datasets import get_spec, load_contract_table, load_pair, make_split
from dq_framework.detectors.cdc import ConformalDataCleaningHGB
from dq_framework.detectors.iforest import IsolationForestRow
from dq_framework.detectors.subprocess_adapter import OriginalCDC, Raha
from dq_framework.injection import Scenario, inject

warnings.filterwarnings("ignore")
QDIR = paths.RESULTS_DIR / "qualification"


def _data(ds):
    c = load_contract(ds)
    df = load_contract_table(ds, c)
    part = make_split(df, c, seed=1)
    return c, df[part == "reference"].reset_index(drop=True), df[part == "dev"].reset_index(drop=True)


def _stack(c, ref, dev, cases, rate=0.05, seed=3):
    parts, logs = [], []
    for col, op, opp in cases:
        sc = Scenario(c.dataset, col, op, "soft_ecar", rate, seed, opp, {})
        r = inject(dev, sc, c, ref)
        parts.append(r.corrupted.assign(_scenario_id=sc.scenario_id))
        logs.append(r.log)
    parts.append(dev.assign(_scenario_id="untouched"))
    return pd.concat(parts, ignore_index=True), pd.concat(logs, ignore_index=True)


def _cell_metrics(scores, log, targets):
    out = {}
    for sid, g in scores.groupby("_scenario_id"):
        lg = log[log["scenario_id"] == sid]
        for col in targets:
            gc = g[g["column"] == col]
            y = gc["_row_id"].isin(set(lg[lg["column"] == col]["_row_id"]))
            key = f"{'untouched' if sid == 'untouched' else sid.split('.')[0] + '.' + sid.split('.')[1]}|{col}"
            r = {"flag_rate_untouched_cells": float(gc.loc[~y, "flag"].mean())}
            if y.any():
                r["recall_flag"] = float(gc.loc[y, "flag"].mean())
                if gc["score"].notna().all() and (~y).any():
                    r["auc"] = float(roc_auc_score(y, gc["score"]))
            out[key] = r
    return out


def fidelity() -> dict:
    c, ref, dev = _data("uci_credit")
    targets = ["BILL_AMT1", "PAY_0"]
    batch, log = _stack(c, ref, dev, [("BILL_AMT1", "scale", {"factor": 10}), ("PAY_0", "category_swap", {"weighing": "frequency"})])
    res = {"setup": "uci_credit dev partition (split seed 1), 5% ECAR errors per scenario, targets BILL_AMT1 and PAY_0, confidence 0.999"}
    dets = {
        "cdc_hgb (inclusive sets)": ConformalDataCleaningHGB(confidence=0.999, max_iter=100, target_columns=targets),
        "cdc_hgb (strict_original sets)": ConformalDataCleaningHGB(confidence=0.999, max_iter=100, target_columns=targets, set_rule="strict_original"),
        "cdc_original (contract typing)": OriginalCDC(confidence=0.999, typing="contract", num_trials=2, target_columns=targets),
        "cdc_original (original heuristic typing)": OriginalCDC(confidence=0.999, typing="original_heuristic", num_trials=2, target_columns=targets),
    }
    for name, det in dets.items():
        comp = det.check_compatibility(c, ref)
        if comp.verdict.startswith("BLOCKED"):
            res[name] = {"status": "blocked", "reasons": comp.reasons}
            continue
        t = time.perf_counter()
        det.fit(ref, c)
        out = det.score(batch)
        res[name] = {"status": out.status, "wall_seconds": round(time.perf_counter() - t, 1),
                     "typing_used": out.environment.get("typing_used"), "metrics": _cell_metrics(out.scores, log, targets)
                     if out.status == "ok" else None, "warnings": out.warnings[:1]}
        print(name, json.dumps(res[name]["metrics"]), flush=True)
    return res


def seedvar() -> dict:
    c, ref, dev = _data("uci_credit")
    targets = ["BILL_AMT1", "PAY_0"]
    batch, log = _stack(c, ref, dev, [("BILL_AMT1", "scale", {"factor": 10}), ("PAY_0", "category_swap", {"weighing": "frequency"})])
    rows = []
    for conf in (0.999, 0.99):
        for seed in range(5):
            det = ConformalDataCleaningHGB(confidence=conf, max_iter=100, target_columns=targets, seed=seed).fit(ref, c)
            m = _cell_metrics(det.score(batch).scores, log, targets)
            for k, v in m.items():
                if k.startswith("untouched"):
                    continue
                rows.append({"confidence": conf, "seed": seed, "case": k, **v})
    d = pd.DataFrame(rows)
    summ = d.groupby(["confidence", "case"]).agg(["mean", "min", "max"]).round(4)
    print(summ.to_string(), flush=True)
    return {"rows": rows, "setup": "5 calibration seeds x 2 confidence levels; same injected batch"}


def _raha_on_controlled(ds, cases, n=1000):
    c, ref, dev = _data(ds)
    sub = dev.sample(n, random_state=0).reset_index(drop=True)
    det = Raha(labeling_budget=20, seed=0).fit(ref, c)
    ev = []
    for col, op, opp in cases:
        sc = Scenario(ds, col, op, "soft_ecar", 0.05, 3, opp, {})
        r = inject(sub, sc, c, ref)
        out = det.score_pair(r.corrupted, sub, sc.scenario_id)
        if out.status != "ok":
            ev.append(f"{col}/{op}: failed")
            continue
        s = out.scores[~out.scores["labeled"]]
        inj = set(zip(r.log["_row_id"], r.log["column"], strict=True))
        hit = [(a, b) in inj for a, b in zip(s["_row_id"], s["column"], strict=True)]
        s = s.assign(inj=hit)
        rec = float((s["flag"] & s["inj"]).sum() / max(s["inj"].sum(), 1))
        ev.append(f"{col}/{op} @5% in {n} rows: labelled error cells {out.environment.get('n_labeled_error_cells')}, "
                  f"recall {rec:.2f}, flags on untouched cells {int((s['flag'] & ~s['inj']).sum())}, {out.score_seconds:.0f}s")
    return ev


def _raha_on_flights():
    dirty, clean = load_pair(get_spec("raha_flights"))
    with tempfile.TemporaryDirectory(prefix="raha_flights_") as td:
        td = Path(td)
        dirty.to_csv(td / "dirty.csv", index=False)
        clean.to_csv(td / "clean.csv", index=False)
        job = {"dirty_csv": str(td / "dirty.csv"), "clean_csv": str(td / "clean.csv"), "out": str(td / "out.parquet"),
               "labeling_budget": 20, "seed": 0, "algorithms": ["OD", "PVD", "RVD", "KBVD"],
               "row_ids": list(range(len(dirty))), "scenario_id": "flights"}
        (td / "job.json").write_text(json.dumps(job))
        p = subprocess.run([str(paths.ROOT / "envs/raha/.venv/bin/python"), "-I", str(paths.ROOT / "envs/raha/run_raha.py"),
                            str(td / "job.json")], capture_output=True, text=True, cwd=td, env={**os.environ, "TMPDIR": str(td)})
        if p.returncode != 0:
            return "FAIL", p.stderr[-500:]
        o = pd.read_parquet(td / "out.parquet")
    cols = list(dirty.columns)
    diff = dirty.to_numpy() != clean.to_numpy()
    truth = {(i, cols[j]) for i, j in zip(*diff.nonzero(), strict=True)}
    flag = set(zip(o["_row_id"][o["flag"]], o["column"][o["flag"]], strict=True))
    tp = len(flag & truth)
    pr, rc = tp / max(len(flag), 1), tp / len(truth)
    return "PASS", f"published Flights pair, 20 labelled tuples, seed 0: P={pr:.3f} R={rc:.3f} F1={2 * pr * rc / (pr + rc):.3f}"


def _run_in_process(det, ds):
    c, ref, dev = _data(ds)
    comp = det.check_compatibility(c, ref)
    t = time.perf_counter()
    det.fit(ref, c)
    out = det.score(dev.assign(_scenario_id="untouched"))
    rate = float(out.scores["flag"].mean())
    return comp, f"fit+score on {len(ref)}/{len(dev)} rows in {time.perf_counter() - t:.0f}s; flag rate on untouched dev = {rate:.4f}"


def matrix() -> pd.DataFrame:
    rows = []

    def add(detector, dataset, verdict, evidence, reasons=""):
        rows.append({"detector": detector, "dataset": dataset, "verdict": verdict, "evidence": evidence, "reasons": reasons})
        print(f"[{verdict}] {detector} x {dataset}: {evidence}", flush=True)

    for ds in ("uci_credit", "uci_bank_marketing"):
        comp, ev = _run_in_process(ConformalDataCleaningHGB(confidence=0.999, max_iter=100), ds)
        add("cdc_hgb", ds, comp.verdict, ev, "; ".join(comp.reasons))
        comp, ev = _run_in_process(IsolationForestRow(), ds)
        add("iforest_row", ds, comp.verdict, ev, "; ".join(comp.reasons))
    fid = QDIR / "cdc_fidelity.json"
    if fid.exists():
        add("cdc_original", "uci_credit", "CONDITIONAL",
            "executed (results/qualification/cdc_fidelity.json); RF+XT only, flags only",
            "strict '<' set rule -> ~10% untouched PAY_0 cells flagged; heuristic typing makes LIMIT_BAL/AGE categorical")
    c, ref, dev = _data("uci_bank_marketing")
    det = OriginalCDC(confidence=0.999, typing="contract", num_trials=2, target_columns=["job", "age"]).fit(ref, c)
    out = det.score(dev.assign(_scenario_id="untouched"))
    add("cdc_original", "uci_bank_marketing", "CONDITIONAL" if out.status == "ok" else "FAIL",
        f"targets job, age: status {out.status}; untouched flag rate job={out.scores[out.scores.column == 'job'].flag.mean():.4f}, "
        f"age={out.scores[out.scores.column == 'age'].flag.mean():.4f}" if out.status == "ok" else out.warnings[:1],
        "flags only; RF+XT only")
    ev = _raha_on_controlled("uci_credit", [("BILL_AMT1", "scale", {"factor": 10}), ("PAY_0", "category_swap", {"weighing": "frequency"})])
    add("raha", "uci_credit", "CONDITIONAL", " | ".join(ev),
        "few-label supervision from the batch under test; at low single-column error rates the labelled tuples contain no errors")
    ev = _raha_on_controlled("uci_bank_marketing", [("job", "category_swap", {"weighing": "frequency"})])
    add("raha", "uci_bank_marketing", "CONDITIONAL", " | ".join(ev), "same supervision issue")
    v, ev = _raha_on_flights()
    add("raha", "raha_flights", v, ev, "real inter-source errors; transductive detector exploits redundancy")
    pf = QDIR / "flights_typed_probe.json"
    if pf.exists():
        p = json.loads(pf.read_text())["cdc_on_real_value_errors"]
        aucs = ", ".join(f"{k}={v.get('auc_value_errors', float('nan')):.2f}" for k, v in p.items())
        add("cdc_hgb", "raha_flights", "INCOMPATIBLE", f"typed probe, split by flight: AUC on real value errors {aucs}",
            "errors are conflicts between rows of the same flight; per-row conditional models cannot see them; string times need typing")
    pt = QDIR / "tax_bart_probe.json"
    if pt.exists():
        p = json.loads(pt.read_text())["per_column"]
        txt = "; ".join(f"{k}: AUC BART {v.get('auc_bart', float('nan')):.2f} vs ours {v['auc_ours_mean']:.2f}" for k, v in p.items())
        add("cdc_hgb", "raha_tax", "CONDITIONAL", f"typed probe (scripts/probe_tax_bart.py): {txt}",
            "high-cardinality strings excluded; zip/area_code used as numeric features")
    add("iforest_row", "raha_flights", "NOT TESTED", "-", "string-only table; record-level detector not meaningful for inter-source conflicts")
    add("raha", "raha_tax", "NOT TESTED", "-", "runtime on 200k rows; not needed for the research question")
    add("lucario", "all", "NOT TESTED", "-", "paper not readable here (403); code availability not verified")
    add("saged", "all", "NOT TESTED", "-", "requires labelled historical datasets; repository has no licence file")
    df = pd.DataFrame(rows)
    df.to_csv(QDIR / "compatibility_matrix.csv", index=False)
    return df


def main(argv: list[str]) -> int:
    QDIR.mkdir(parents=True, exist_ok=True)
    todo = argv or ["fidelity", "seedvar", "matrix"]
    if "fidelity" in todo:
        (QDIR / "cdc_fidelity.json").write_text(json.dumps(fidelity(), indent=2, default=str))
    if "seedvar" in todo:
        (QDIR / "cdc_seed_variance.json").write_text(json.dumps(seedvar(), indent=2, default=str))
    if "matrix" in todo:
        matrix()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
