#!/usr/bin/env python
"""R2 feasibility probe: can a numeric/categorical cell-level detector (CDC) be evaluated on the
real errors of Raha Flights, and what does the necessary typing step do to the error population?

Steps
1. Parse the four time columns (strings such as '7:10 a.m.', 'Thu 7:45', '12/02/2011 6:55 a.m.')
   into minutes after midnight. Unparseable non-empty strings become NaN and are counted.
2. Classify every published dirty/clean difference after typing:
     missing_in_dirty      dirty empty, clean present
     unparseable           dirty non-empty but not a time
     representation_only   dirty != clean as strings, equal after parsing (format variant)
     value_error           both parse, minutes differ (the real conflicting-time errors)
3. Group-aware split by flight (no flight in both partitions). The detector is fitted on the
   CLEAN rows of reference flights (a validated history) and scored on the DIRTY rows of the
   held-out flights. Reported: AUC and recall@own-flag on value errors, alert rate on cells
   whose dirty value equals the clean value.

This is qualification evidence only; nothing here is tuned on the results.
"""

from __future__ import annotations

import json
import re
import sys
import warnings

import numpy as np

from dq_framework import paths
from dq_framework.contracts import Column, Contract
from dq_framework.datasets import get_spec, load_pair
from dq_framework.detectors.cdc import ConformalDataCleaningHGB

warnings.filterwarnings("ignore")
TIME_COLS = ["sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time"]
_re = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", re.I)
_re24 = re.compile(r"(?<![\d/])(\d{1,2}):(\d{2})(?!\s*[ap]\.?m)", re.I)


def parse_time(s: str) -> float:
    if s is None or s.strip() == "":
        return np.nan
    m = _re.search(s)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        if h == 12:
            h = 0
        if ap == "p":
            h += 12
        return float(h * 60 + mi)
    m = _re24.search(s)
    if m:
        return float(int(m.group(1)) * 60 + int(m.group(2)))
    return np.nan


def main() -> int:
    dirty, clean = load_pair(get_spec("raha_flights"))
    out: dict = {"n_rows": len(dirty)}
    typed_d = dirty[["tuple_id", "src", "flight"]].copy()
    typed_c = clean[["tuple_id", "src", "flight"]].copy()
    comp = {"missing_in_dirty": 0, "unparseable": 0, "representation_only": 0, "value_error": 0, "clean_unparseable": 0}
    for c in TIME_COLS:
        d = dirty[c].map(parse_time)
        k = clean[c].map(parse_time)
        typed_d[c], typed_c[c] = d, k
        diff = dirty[c] != clean[c]
        comp["clean_unparseable"] += int((k.isna() & (clean[c].str.strip() != "")).sum())
        comp["missing_in_dirty"] += int((diff & (dirty[c].str.strip() == "")).sum())
        comp["unparseable"] += int((diff & (dirty[c].str.strip() != "") & d.isna()).sum())
        comp["representation_only"] += int((diff & d.notna() & k.notna() & (d == k)).sum())
        comp["value_error"] += int((diff & d.notna() & k.notna() & (d != k)).sum())
    out["published_error_cells"] = int((dirty[TIME_COLS] != clean[TIME_COLS]).to_numpy().sum())
    out["composition_after_typing"] = comp

    cols = [Column("src", "categorical"), Column("flight", "categorical")] + [Column(c, "numeric") for c in TIME_COLS]
    contract = Contract("flights_typed", "flights", "typed probe", None, cols, {}, [])
    flights = np.array(sorted(clean["flight"].unique()))
    rng = np.random.default_rng(1)
    ref_f = set(rng.choice(flights, size=int(0.6 * len(flights)), replace=False))
    ref_mask = clean["flight"].isin(ref_f)
    ref = typed_c[ref_mask].assign(_row_id=lambda x: x["tuple_id"].astype(int)).reset_index(drop=True)
    ref = ref.dropna(subset=TIME_COLS, how="any")
    test = typed_d[~ref_mask].assign(_row_id=lambda x: x["tuple_id"].astype(int), _scenario_id="flights").reset_index(drop=True)
    tclean = typed_c[~ref_mask].reset_index(drop=True)
    out["split"] = {"reference_flights": len(ref_f), "reference_rows": len(ref), "test_rows": len(test),
                    "flights_in_both": 0}
    det = ConformalDataCleaningHGB(confidence=0.99, calibration_rows=min(400, len(ref) // 3), max_iter=100,
                                   min_samples_leaf=5, target_columns=TIME_COLS)
    compat = det.check_compatibility(contract, ref)
    out["cdc_compatibility"] = compat.__dict__
    det.fit(ref, contract)
    s = det.score(test).scores
    res = {}
    from sklearn.metrics import roc_auc_score

    for c in TIME_COLS:
        sc = s[s["column"] == c].reset_index(drop=True)
        d, k = test[c].to_numpy(), tclean[c].to_numpy()
        both = ~np.isnan(d) & ~np.isnan(k)
        val_err = both & (d != k)
        ok = both & (d == k)
        y = val_err[both]
        r = {"value_errors": int(val_err.sum()), "correct_cells": int(ok.sum())}
        if y.any() and (~y).any():
            r["auc_value_errors"] = float(roc_auc_score(y, sc.loc[both, "score"]))
        r["recall_flag_value_errors"] = float(sc.loc[val_err, "flag"].mean()) if val_err.any() else None
        r["flag_rate_on_correct_cells"] = float(sc.loc[ok, "flag"].mean())
        res[c] = r
    out["cdc_on_real_value_errors"] = res
    qdir = paths.RESULTS_DIR / "qualification"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "flights_typed_probe.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
