"""Run the ORIGINAL Conformal Data Cleaning detector inside its isolated Python 3.9 environment.

Called by dq_framework.detectors.subprocess_adapter with a JSON job file:
  {"reference": path.parquet, "batch": path.parquet, "out": path.parquet,
   "columns": [...], "categorical": [...], "typing": "original_heuristic" | "contract",
   "confidence": 0.999, "hyperparameters": {"RF": {}, "XT": {}}, "num_trials": 5, "seed": 0}

Output parquet: _scenario_id, _row_id, column, flag (score is not provided by the original).
The upstream code is used unmodified. With typing == "contract" the cleaner's column
typing (a random cardinality heuristic) is replaced by the contract's declared types by
overriding the instance method; this is reported in the output metadata.
"""

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def main(job_path: str) -> None:
    job = json.loads(Path(job_path).read_text())
    from conformal_data_cleaning.cleaner.conformal import ConformalAutoGluonCleaner

    cols = job["columns"]
    ref = pd.read_parquet(job["reference"])
    batch = pd.read_parquet(job["batch"])
    # AutoGluon needs plain dtypes: categorical columns as strings, numeric as float
    def prep(df):
        out = pd.DataFrame(index=df.index)
        for c in cols:
            if c in job["categorical"]:
                out[c] = df[c].astype(object).map(lambda v: None if pd.isna(v) else str(v))
            else:
                out[c] = df[c].astype("float64")
        return out

    R, B = prep(ref), prep(batch)
    np.random.seed(job.get("seed", 0))
    cleaner = ConformalAutoGluonCleaner(confidence_level=job["confidence"], seed=job.get("seed", 0) or None)
    meta = {"typing": job["typing"]}
    if job["typing"] == "contract":
        cat = list(job["categorical"])

        def _guess_dtypes(data, _cat=cat):
            cleaner._categorical_columns = [c for c in data.columns if c in _cat]
            cleaner._numerical_columns = [c for c in data.columns if c not in _cat]

        cleaner._guess_dtypes = _guess_dtypes
    t0 = time.perf_counter()
    workdir = Path(job["out"]).with_suffix("")
    cleaner.fit(
        R,
        target_columns=job.get("target_columns") or cols,
        ci_ag_fit_params={
            "verbosity": 0,
            "hyperparameters": job.get("hyperparameters", {"RF": {}, "XT": {}}),
            "hyperparameter_tune_kwargs": {"num_trials": job.get("num_trials", 5)},
        },
        ci_ag_predictor_params={"path_prefix": workdir / "AutogluonModels"},
    )
    fit_s = time.perf_counter() - t0
    meta["categorical_used"] = list(cleaner._categorical_columns)
    meta["numerical_used"] = list(cleaner._numerical_columns)
    t0 = time.perf_counter()
    _, outlier_mask, _ = cleaner.remove_outliers(B, empty_pred_sets_are_inliers=True)
    score_s = time.perf_counter() - t0
    frames = []
    for c in outlier_mask.columns:
        frames.append(pd.DataFrame({
            "_scenario_id": batch["_scenario_id"].to_numpy() if "_scenario_id" in batch else "",
            "_row_id": batch["_row_id"].to_numpy(),
            "column": c,
            "score": np.nan,
            "flag": outlier_mask[c].to_numpy(dtype=bool),
        }))
    pd.concat(frames, ignore_index=True).to_parquet(job["out"], index=False)
    meta.update({"fit_seconds": fit_s, "score_seconds": score_s})
    Path(job["out"] + ".meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
