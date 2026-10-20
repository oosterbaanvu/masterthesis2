# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the ORIGINAL dBoost (cpitclaudel/dBoost, GPL-3.0) on a training file and a test file.

This file imports dBoost and is therefore kept separate from the MIT-licensed framework: it lives in
envs/dboost/, is licensed GPL-3.0-or-later, and is only executed as a child process
(dq_framework.detectors.dboost.OriginalDBoost). dBoost itself is cloned at a pinned commit by
envs/dboost/install.sh into envs/dboost/src (git-ignored); no dBoost code is copied into the repository.

Job JSON:
  {"dboost_src": ".../envs/dboost/src", "train": "train.tsv", "test": "test.tsv", "out": "out.tsv",
   "model": ["gaussian", "3"] | ["histogram", "0.8", "0.2"] | ["partitionedhistogram", "5", "0.8", "0.2"],
   "analyzer": ["statistical", "0.5"], "disabled_rules": [...], "floats_only": false}
The input files are tab-separated without header; every row of the test file is written to the output as
discrepancies: one line per (test_row_index, column_index, model, kind, feature_index) where kind is
"field" (a single field) or "hint" (a correlated pair; column_index is then each of the two fields).
"""

import json
import sys
import time


def main(job_path):
    job = json.load(open(job_path))
    sys.path.insert(0, job["dboost_src"])
    import dboost
    from dboost import analyzers, features, models
    from dboost.utils.read import stream_tuples

    by_id = {m.ID: m for m in models.ALL()}
    an_by_id = {a.ID: a for a in analyzers.ALL()}
    model = by_id[job["model"][0]].from_parse(job["model"][1:])
    analyzer = an_by_id[job["analyzer"][0]].from_parse(job["analyzer"][1:])
    disabled = set(job.get("disabled_rules", []))
    rules = {t: [r for r in rs if r.__name__ not in disabled] for t, rs in features.rules.items()}
    floats_only = bool(job.get("floats_only", False))
    train = stream_tuples(open(job["train"]), "\t", floats_only, True)
    test = stream_tuples(open(job["test"]), "\t", floats_only, True)
    t0 = time.perf_counter()
    found = list(dboost.outliers(train, test, analyzer, model, rules, float("+inf")))
    elapsed = time.perf_counter() - t0
    n_test = len(test())
    with open(job["out"], "w") as fh:
        for index, (_x, _X, discrepancies) in found:
            for group in discrepancies:
                for field_id, feature_id in group:
                    if field_id == 0:  # correlation pseudo-field: implicates both fields of the hint pair
                        (nx, _), (ny, _) = analyzer.hints[feature_id]
                        for col in (nx, ny):
                            fh.write(f"{index}\t{col}\t{job['model'][0]}\thint\t{feature_id}\n")
                    else:
                        fh.write(f"{index}\t{field_id - 1}\t{job['model'][0]}\tfield\t{feature_id}\n")
    json.dump({"seconds": elapsed, "n_test_rows_parsed": n_test, "n_outlier_rows": len(found),
               "n_hints": len(analyzer.hints)}, open(job["out"] + ".meta.json", "w"))


if __name__ == "__main__":
    main(sys.argv[1])
