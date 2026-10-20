#!/usr/bin/env python
"""Qualification: compare CDC ranking scores (CQR edge distance vs. normalised residual) on numeric targets.

Dev partition of split seed 1, ECAR, 1% errors, 3 injection seeds; metric = AUC of the detector score on
the corrupted column (threshold-free). Output: results/qualification/cdc_rank_score_comparison.csv
"""

import sys
import warnings

import pandas as pd
from sklearn.metrics import roc_auc_score

from dq_framework import paths
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_contract_table, make_split
from dq_framework.detectors.cdc import ConformalDataCleaningHGB
from dq_framework.injection import Scenario, inject
from dq_framework.injection.catalog import load_catalog

warnings.filterwarnings("ignore")


def main() -> int:
    cat = load_catalog()
    rows = []
    for ds in ("uci_credit", "uci_bank_marketing"):
        c = load_contract(ds)
        df = load_contract_table(ds, c)
        part = make_split(df, c, seed=1)
        ref, dev = df[part == "reference"].reset_index(drop=True), df[part == "dev"].reset_index(drop=True)
        cases = [k for k in cat["datasets"][ds]["cases"] if c.column(k["column"]).type == "numeric" and k.get("role") == "primary"]
        targets = sorted({k["column"] for k in cases})
        dets = {rs: ConformalDataCleaningHGB(confidence=0.999, max_iter=100, target_columns=targets, rank_score=rs).fit(ref, c)
                for rs in ("cqr", "normalized_residual")}
        for k in cases:
            for seed in (101, 202, 303):
                sc = Scenario(ds, k["column"], k["operation"], "soft_ecar", 0.01, seed, dict(k.get("params", {})), {})
                r = inject(dev, sc, c, ref)
                b = r.corrupted.assign(_scenario_id="x")
                for rs, det in dets.items():
                    s = det.score(b).scores
                    s = s[s["column"] == k["column"]]
                    y = s["_row_id"].isin(set(r.log["_row_id"]))
                    rows.append({"dataset": ds, "column": k["column"], "operation": k["operation"],
                                 "params": str(k.get("params", {})), "seed": seed, "rank_score": rs,
                                 "auc": roc_auc_score(y, s["score"])})
    out = pd.DataFrame(rows)
    piv = out.pivot_table(index=["dataset", "column", "operation", "params"], columns="rank_score", values="auc", aggfunc="mean")
    print(piv.round(3).to_string())
    print("\nmean AUC:", out.groupby("rank_score")["auc"].mean().round(3).to_dict())
    out.to_csv(paths.RESULTS_DIR / "qualification" / "cdc_rank_score_comparison.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
