"""Run the ORIGINAL Raha detector (BigDaMa/raha 1.26) in its isolated Python 3.9 environment.

Job JSON: {"dirty_csv": ..., "clean_csv": ..., "out": path.parquet, "labeling_budget": 20,
           "seed": 0, "algorithms": ["OD", "PVD", "RVD", "KBVD"], "row_ids": [...], "scenario_id": "..."}

Raha is semi-supervised: it asks a user to label ``labeling_budget`` tuples. In benchmark
mode (as in the Raha paper) these labels are simulated from ``clean_csv``. Here the clean
file is the batch *before* injection, so the simulated user labels injected errors only.
Output parquet: _scenario_id, _row_id, column, score (NaN), flag, labeled (tuple was labeled).
"""

import json
import os
import random
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def main(job_path: str) -> None:
    job = json.loads(Path(job_path).read_text())
    # numpy drives Raha's tuple sampling; the global `random` module shuffles strategies.
    random.seed(job["seed"])
    np.random.seed(job["seed"])
    assert os.environ.get("TMPDIR"), "run with a private TMPDIR (see subprocess_adapter.Raha)"
    import raha

    app = raha.Detection()
    app.LABELING_BUDGET = int(job["labeling_budget"])
    app.ERROR_DETECTION_ALGORITHMS = list(job["algorithms"])
    app.VERBOSE = False
    app.SAVE_RESULTS = False
    dd = {"name": "batch", "path": job["dirty_csv"], "clean_path": job["clean_csv"]}
    t0 = time.perf_counter()
    d = app.initialize_dataset(dd)
    app.run_strategies(d)
    app.generate_features(d)
    app.build_clusters(d)
    while len(d.labeled_tuples) < app.LABELING_BUDGET:
        app.sample_tuple(d)
        app.label_with_ground_truth(d)
    app.propagate_labels(d)
    app.predict_labels(d)
    elapsed = time.perf_counter() - t0
    cols = list(d.dataframe.columns)
    row_ids = job["row_ids"]
    labeled = set(d.labeled_tuples.keys())
    detected = set(d.detected_cells.keys())
    recs = []
    for i in range(d.dataframe.shape[0]):
        for j, c in enumerate(cols):
            recs.append((job["scenario_id"], row_ids[i], c, np.nan, (i, j) in detected, i in labeled))
    out = pd.DataFrame(recs, columns=["_scenario_id", "_row_id", "column", "score", "flag", "labeled"])
    out.to_parquet(job["out"], index=False)
    n_err_labels = int(sum(1 for v in d.labeled_cells.values() if int(v[0]) == 1))
    Path(job["out"] + ".meta.json").write_text(json.dumps({"seconds": elapsed, "n_labeled_tuples": len(labeled),
                                                           "n_labeled_error_cells": n_err_labels,
                                                           "strategies": len(getattr(d, "strategy_profiles", []))}))


if __name__ == "__main__":
    main(sys.argv[1])
