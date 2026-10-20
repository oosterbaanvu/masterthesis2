"""Row-level learned detector: Isolation Forest (Liu, Ting & Zhou, 2008) fitted on the reference partition.

Different inductive bias from CDC: a *joint*, unsupervised outlier score per record instead of
per-column conditional models. It produces **row-level** output only (``column`` is None);
it is evaluated with record-level metrics and never mapped to cells.

Transformation (documented): categorical columns are ordinal-encoded with the reference
levels (unseen level -> -1); numeric columns are used as-is (trees are scale-invariant).
Missing values are encoded as a sentinel (-1e12) because IsolationForest does not accept NaN.
The alert threshold is the reference-score quantile ``1 - reference_alert_rate``.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from dq_framework.contracts import Contract
from dq_framework.detectors.base import PASS, Compatibility, Detector, DetectorOutput, environment_info

MISSING_SENTINEL = -1e12


class IsolationForestRow(Detector):
    name = "iforest_row"
    granularity = "row"
    supervision = "reference_data"
    limitations = [
        "Row-level only: says which record is unusual, not which field.",
        "Ordinal encoding of categorical codes imposes an arbitrary order.",
        "Global outlierness: plausible-but-wrong values inside the joint distribution are not detectable.",
    ]

    def __init__(self, n_estimators: int = 300, max_samples: int | str = 1024, reference_alert_rate: float = 0.01,
                 seed: int = 0) -> None:
        super().__init__(n_estimators=n_estimators, max_samples=max_samples,
                         reference_alert_rate=reference_alert_rate, seed=seed)

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        t = ["categorical columns ordinal-encoded with reference levels", "missing values encoded as a sentinel"]
        return Compatibility(PASS, ["row-level output; evaluated at record level only"], t)

    def _encode(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for c in self._cols:
            if c in self._levels:
                m = {v: i for i, v in enumerate(self._levels[c])}
                cols.append(df[c].astype(object).map(lambda v, m=m: m.get(v, -1) if pd.notna(v) else MISSING_SENTINEL).astype(float))
            else:
                cols.append(df[c].astype("float64").fillna(MISSING_SENTINEL))
        return np.column_stack(cols)

    def fit(self, reference: pd.DataFrame, contract: Contract) -> IsolationForestRow:
        t0 = time.perf_counter()
        self._cols = contract.column_names
        self._levels = {c: sorted(reference[c].dropna().unique().tolist(), key=str) for c in contract.categorical_columns}
        X = self._encode(reference)
        self.model_ = IsolationForest(n_estimators=self.config["n_estimators"], max_samples=self.config["max_samples"],
                                      random_state=self.config["seed"], n_jobs=-1).fit(X)
        ref_scores = -self.model_.score_samples(X)
        self.threshold_ = float(np.quantile(ref_scores, 1 - self.config["reference_alert_rate"]))
        self.fit_seconds_ = time.perf_counter() - t0
        return self

    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        t0 = time.perf_counter()
        s = -self.model_.score_samples(self._encode(batch))
        out = pd.DataFrame({
            "_scenario_id": batch["_scenario_id"].to_numpy() if "_scenario_id" in batch else "",
            "_row_id": batch["_row_id"].to_numpy(),
            "column": None,
            "score": s,
            "flag": s > self.threshold_,
        })
        return DetectorOutput(self.name, "row", out, config=dict(self.config), fit_seconds=self.fit_seconds_,
                              score_seconds=time.perf_counter() - t0, limitations=list(self.limitations),
                              environment=environment_info())
