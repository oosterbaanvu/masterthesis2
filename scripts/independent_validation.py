#!/usr/bin/env python
"""Independent ground-truth checks for the pilot's candidate detectors (bounded validity checks, not estimates).

Track A - out-of-generator (Raha Tax, BART-generated errors; synthetic, but from a generator we did not write):
  reference-trained candidates are fitted on CLEAN values of 20,000 rows and scored on the DIRTY values of
  10,000 other rows (BART errors, formatting artefacts removed by typing); batch-learned candidates learn on the
  dirty test rows. The same candidates are then evaluated on OUR injected errors in the same columns of the same
  clean test rows. Question: would a selection made on our injections pick the detector that is best on BART
  errors? (selection agreement + regret, per budget)
Track B - existing real errors (Raha Flights: inter-source conflicts; Raha Beers: manually cleaned listings):
  transductive candidates only (CDC is incompatible with Flights, see method_compatibility.md); flags evaluated
  against the published dirty/clean difference, and compared with the same candidates on our injected errors in
  the clean file.

No candidate sees the clean values of the rows it is evaluated on. There is no conventional-control baseline for
these tables (no contract), so increments are over an empty baseline.

Usage: python scripts/independent_validation.py [--out results/qualification/independent_validation.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from dq_framework import paths
from dq_framework.contracts import Column, Contract
from dq_framework.datasets import get_spec, load_pair
from dq_framework.detectors.registry import make_detector
from dq_framework.injection import Scenario, inject
from dq_framework.pilot import metrics as M

warnings.filterwarnings("ignore")
BUDGETS = (10.0, 25.0, 50.0)
REF_DETECTORS = {
    "cdc": {"name": "cdc_hgb", "params": {"confidence": 0.999, "max_iter": 100, "seed": 0, "rank_score": "normalized_residual"}},
    "dboost_gaussian": {"name": "dboost", "params": {"model": "gaussian", "params": [3.0], "corr_threshold": 0.5}},
    "dboost_gaussian_text": {"name": "dboost", "params": {"model": "gaussian", "params": [3.0], "corr_threshold": 0.5, "type_mode": "text"}},
    "dboost_histogram": {"name": "dboost", "params": {"model": "histogram", "params": [0.8, 0.2], "corr_threshold": 0.5}},
}
BATCH_DETECTORS = {
    "dboost_gaussian_batch": {"name": "dboost", "params": {"model": "gaussian", "params": [3.0], "corr_threshold": 0.5, "fit_on": "batch"}},
    "dboost_gaussian_text_batch": {"name": "dboost", "params": {"model": "gaussian", "params": [3.0], "corr_threshold": 0.5,
                                                                 "fit_on": "batch", "type_mode": "text"}},
    "dboost_histogram_text_batch": {"name": "dboost", "params": {"model": "histogram", "params": [0.8, 0.2], "corr_threshold": 0.5,
                                                                  "fit_on": "batch", "type_mode": "text"}},
    "lucario_core": {"name": "lucario_core", "params": {"fit_on": "batch"}},
    "sd_outlier": {"name": "sd_outlier", "params": {"fit_on": "batch"}},
    "iqr_outlier": {"name": "iqr_outlier", "params": {"fit_on": "batch"}},
}


def _matrix(scores: pd.DataFrame, row_ids: np.ndarray, cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    pos = pd.Series(np.arange(len(row_ids)), index=row_ids)
    ci = {c: j for j, c in enumerate(cols)}
    f = np.zeros((len(row_ids), len(cols)), bool)
    s = np.full((len(row_ids), len(cols)), np.nan)
    r = pos.reindex(scores["_row_id"].to_numpy()).to_numpy()
    c = scores["column"].map(ci).to_numpy()
    ok = ~(pd.isna(r) | pd.isna(c))
    f[r[ok].astype(int), c[ok].astype(int)] = scores["flag"].to_numpy(bool)[ok]
    s[r[ok].astype(int), c[ok].astype(int)] = scores["score"].to_numpy(float)[ok]
    return f, s


def evaluate(det_key, det, truth: np.ndarray, f: np.ndarray, s: np.ndarray) -> dict:
    base = np.zeros_like(truth)
    m = M.cell_metrics(truth, base, f, s if det.provides_scores else None, BUDGETS)
    tp = int((truth & f).sum())
    m["f1_flags"] = 2 * tp / (truth.sum() + f.sum()) if (truth.sum() + f.sum()) else np.nan
    m["n_errors"] = int(truth.sum())
    for b in BUDGETS:
        m[f"utility@{b:g}"] = m[M.utility_key(det.provides_scores, b)]
    return {"detector": det_key, **{k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in m.items()}}


def run_detectors(specs, ref, batch, contract, cols, truth):
    out = []
    for key, spec in specs.items():
        det = make_detector(spec)
        det.fit(ref, contract)
        o = det.score(batch.assign(_scenario_id="b"))
        f, s = _matrix(o.scores, batch["_row_id"].to_numpy(), cols)
        out.append(evaluate(key, det, truth, f, s))
    return out


def agreement(real: list[dict], synth: list[dict], key: str) -> dict:
    r = pd.DataFrame(real).set_index("detector")[key]
    s = pd.DataFrame(synth).groupby("detector")[key].mean()
    s = s.reindex(r.index)
    pick, best = s.idxmax(), r.idxmax()
    from scipy.stats import spearmanr

    rho = spearmanr(r.to_numpy(), s.to_numpy()).statistic if len(r) > 2 else np.nan
    return {"metric": key, "selected_on_ours": pick, "best_on_independent": best, "agree": bool(pick == best),
            "regret": float(r[best] - r[pick]), "spearman_rank_corr": float(rho),
            "independent": r.round(4).to_dict(), "ours": s.round(4).to_dict()}


# --------------------------------------------------------------------------- Track A: Tax / BART
CAT = ["gender", "state", "marital_status", "has_child"]
NUM = ["salary", "rate", "single_exemp", "married_exemp", "child_exemp", "zip", "area_code"]


def track_tax() -> dict:
    dirty, clean = load_pair(get_spec("raha_tax"))

    def typed(df):
        out = pd.DataFrame(index=df.index)
        for c in CAT:
            out[c] = df[c].astype("string")
        for c in NUM:
            out[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        return out

    rng = np.random.default_rng(7)
    idx = rng.choice(len(clean), 30_000, replace=False)
    ref_idx, test_idx = idx[:20_000], idx[20_000:]
    td, tc = typed(dirty), typed(clean)
    cols = CAT + NUM
    contract = Contract("tax_typed", "tax", "independent validation", None,
                        [Column(c, "categorical") for c in CAT] + [Column(c, "numeric") for c in NUM], {}, [])
    ref = tc.iloc[ref_idx].reset_index(drop=True).assign(_row_id=np.arange(len(ref_idx)))
    rid = np.arange(10**6, 10**6 + len(test_idx))
    test_dirty = td.iloc[test_idx].reset_index(drop=True).assign(_row_id=rid)
    test_clean = tc.iloc[test_idx].reset_index(drop=True).assign(_row_id=rid)
    a, b = test_dirty[cols], test_clean[cols]
    truth = np.zeros((len(rid), len(cols)), bool)
    for j, c in enumerate(cols):
        if c in CAT:
            truth[:, j] = (a[c].astype(str) != b[c].astype(str)).to_numpy()
        else:
            truth[:, j] = ~((a[c] == b[c]) | (a[c].isna() & b[c].isna())).to_numpy()
    specs = {**REF_DETECTORS, **BATCH_DETECTORS}
    real = run_detectors(specs, ref, test_dirty, contract, cols, truth)
    synth = []
    cases = [("state", "category_swap", {"weighing": "frequency"}), ("marital_status", "category_swap", {"weighing": "frequency"}),
             ("has_child", "category_swap", {"weighing": "frequency"}), ("salary", "scale", {"factor": 10.0}),
             ("single_exemp", "plausible_substitution", {}), ("child_exemp", "plausible_substitution", {})]
    for col, op, prm in cases:
        for seed in (11, 22):
            inj = inject(test_clean, Scenario("tax_typed", col, op, "soft_ecar", 0.01, seed, prm, {}), contract, ref)
            t = np.zeros_like(truth)
            j = cols.index(col)
            t[:, j] = test_clean["_row_id"].isin(set(inj.log["_row_id"])).to_numpy()
            for r in run_detectors(specs, ref, inj.corrupted, contract, cols, t):
                synth.append({**r, "case": f"{col}.{op}", "seed": seed})
    per_col = {c: int(truth[:, j].sum()) for j, c in enumerate(cols)}
    return {"n_reference": len(ref), "n_test": len(rid), "bart_errors_per_column": per_col,
            "independent": real, "ours": synth,
            "agreement": [agreement(real, synth, f"utility@{b:g}") for b in BUDGETS]
            + [agreement(real, synth, "f1_flags")]}


# --------------------------------------------------------------------------- Track B: Flights / Beers (real errors)
def track_pair(key: str, exclude: list[str], cases: list[tuple[str, str, dict]]) -> dict:
    dirty, clean = load_pair(get_spec(key))
    cols = [c for c in dirty.columns if c not in exclude]
    contract = Contract(key, key, "independent validation", None, [Column(c, "categorical") for c in cols], {}, [])
    rid = np.arange(1, len(dirty) + 1)
    d = dirty[cols].replace("", pd.NA).astype("string").assign(_row_id=rid)
    c = clean[cols].replace("", pd.NA).astype("string").assign(_row_id=rid)
    truth = (dirty[cols].to_numpy() != clean[cols].to_numpy())
    specs = {k: v for k, v in BATCH_DETECTORS.items() if k not in ("sd_outlier", "iqr_outlier", "dboost_gaussian_batch")}
    empty_ref = c.iloc[0:0]
    real = run_detectors(specs, empty_ref, d, contract, cols, truth)
    synth = []
    for col, op, prm in cases:
        for seed in (11, 22):
            # replacement values are drawn from the clean column (a relabelled copy, so inject's leakage guard holds);
            # the detectors never see it
            inj = inject(c, Scenario(key, col, op, "soft_ecar", 0.05, seed, prm, {}), contract,
                         c.assign(_row_id=c["_row_id"] + 10**7))
            t = np.zeros_like(truth)
            t[:, cols.index(col)] = c["_row_id"].isin(set(inj.log["_row_id"])).to_numpy()
            for r in run_detectors(specs, empty_ref, inj.corrupted, contract, cols, t):
                synth.append({**r, "case": f"{col}.{op}", "seed": seed})
    return {"rows": len(d), "columns": cols, "n_errors": int(truth.sum()), "error_cell_rate": float(truth.mean()),
            "independent": real, "ours": synth, "agreement": [agreement(real, synth, "f1_flags"),
                                                                agreement(real, synth, "utility@50")]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "qualification" / "independent_validation.json")
    args = ap.parse_args(argv)
    res = {"tax_bart": track_tax()}
    print(json.dumps(res["tax_bart"]["agreement"], indent=1), flush=True)
    res["flights_real"] = track_pair("raha_flights", ["tuple_id"], [
        ("act_dep_time", "category_swap", {"weighing": "frequency"}), ("act_arr_time", "category_swap", {"weighing": "frequency"}),
        ("sched_dep_time", "plausible_substitution", {})])
    print(json.dumps(res["flights_real"]["agreement"], indent=1), flush=True)
    res["beers_real"] = track_pair("raha_beers", ["index", "id"], [
        ("abv", "plausible_substitution", {}), ("ounces", "category_swap", {"weighing": "frequency"}),
        ("state", "category_swap", {"weighing": "frequency"})])
    print(json.dumps(res["beers_real"]["agreement"], indent=1), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2, default=str) + "\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
