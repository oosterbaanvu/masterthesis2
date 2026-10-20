#!/usr/bin/env python
"""Qualification of the pilot's candidate detectors (dev-free: reference/selection partitions of pilot seed 11).

Per dataset and detector: compatibility verdict, fit and score time, peak Python memory (tracemalloc; numpy
buffers included, native library memory not), alert rate on the untouched selection partition, and - for
dBoost - cell-level agreement of the re-implementation with the ORIGINAL program on a sample
(2,000 reference rows, 1,000 selection rows; the original is pure Python and slow).

Usage: python scripts/qualify_pilot_detectors.py [--out results/qualification/pilot_detector_qualification.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

from dq_framework import paths
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_contract_table
from dq_framework.detectors.dboost import DBoost, OriginalDBoost
from dq_framework.detectors.registry import make_detector
from dq_framework.pilot.runner import load_config
from dq_framework.pilot.splits import pilot_split


def fidelity(contract, ref, sel, model, params, corr, columns=None):
    c = contract
    if columns is not None:  # restrict the contract to a column subset (e.g. when the original crashes)
        import copy

        c = copy.deepcopy(contract)
        c.columns = [col for col in c.columns if col.name in columns]
    a = DBoost(model=model, params=params, corr_threshold=corr).fit(ref, c).score(sel)
    t = time.perf_counter()
    b = OriginalDBoost(model=model, params=params, corr_threshold=corr).fit(ref, c).score(sel)
    t_orig = time.perf_counter() - t
    rec = {"model": model, "params": params, "corr_threshold": corr, "columns": "all" if columns is None else columns,
           "original_status": b.status, "original_seconds": round(t_orig, 1)}
    if b.status != "ok":
        rec["original_error"] = (b.warnings[0] if b.warnings else "")[-400:]
        return rec
    m = a.scores.merge(b.scores, on=["_row_id", "column"], suffixes=("_re", "_orig"))
    rec.update({"cells": len(m), "flags_reimpl": int(m.flag_re.sum()), "flags_original": int(m.flag_orig.sum()),
                "disagreements": int((m.flag_re != m.flag_orig).sum()),
                "cell_agreement": float((m.flag_re == m.flag_orig).mean())})
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "qualification" / "pilot_detector_qualification.json")
    ap.add_argument("--skip-fidelity", action="store_true")
    args = ap.parse_args(argv)
    report = {}
    for ds in ("uci_credit", "uci_bank_marketing"):
        cfg = load_config(paths.CONFIG_DIR / "pilot" / f"pilot_{ds}.yaml")
        c = load_contract(ds)
        df = load_contract_table(ds, c)
        p = pilot_split(df, c, 11)
        ref, sel = df[p == "reference"], df[p == "selection"].assign(_scenario_id="untouched")
        rows = []
        for key, spec in cfg["detectors"].items():
            det = make_detector(spec)
            comp = det.check_compatibility(c, ref)
            tracemalloc.start()
            t = time.perf_counter()
            det.fit(ref, c)
            fit_s = time.perf_counter() - t
            t = time.perf_counter()
            out = det.score(sel)
            score_s = time.perf_counter() - t
            peak = tracemalloc.get_traced_memory()[1] / 1e6
            tracemalloc.stop()
            unit = "rows" if det.granularity == "row" else "cells"
            rows.append({"detector": key, "name": spec["name"], "granularity": det.granularity,
                         "provides_scores": det.provides_scores, "fit_scope": det.fit_scope,
                         "supervision": det.supervision, "verdict": comp.verdict, "reasons": comp.reasons,
                         "fit_seconds_traced": round(fit_s, 2), "score_seconds_traced": round(score_s, 2),
                         "peak_python_mb": round(peak, 1), f"flagged_{unit}_per_1k_rows": round(1000 * out.scores["flag"].sum() / len(sel), 1),
                         "warnings": out.warnings[:3]})
            print(ds, rows[-1], flush=True)
        rec = {"n_reference": len(ref), "n_selection": len(sel), "detectors": rows}
        if not args.skip_fidelity:
            r2, s2 = ref.head(2000), sel.head(1000)
            fid = [fidelity(c, r2, s2, m, prm, 0.5) for m, prm in (("gaussian", [3.0]), ("histogram", [0.8, 0.2]),
                                                                    ("partitioned", [5.0, 0.8, 0.2]))]
            if any(f["original_status"] != "ok" for f in fid):
                ints = [col.name for col in c.columns if col.type == "categorical" or col.name not in
                        ("emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed")]
                fid += [fidelity(c, r2, s2, m, prm, 0.5, columns=ints) for m, prm in (("gaussian", [3.0]), ("histogram", [0.8, 0.2]))]
            rec["dboost_fidelity"] = fid
            print(ds, json.dumps(fid, indent=1), flush=True)
        report[ds] = rec
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
