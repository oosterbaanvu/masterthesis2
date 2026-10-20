"""Conformal Data Cleaning (detection step) - lightweight re-implementation.

Method (Jaeger & Biessmann, AISTATS 2024; original code se-jaeger/conformal-data-cleaning):
for every target column fit a model that predicts the column from all other columns
on (assumed clean) reference data and calibrate it with split conformal prediction:

* numeric target: conformalised quantile regression (Romano et al., 2019) with
  quantiles (alpha/2, 0.5, 1-alpha/2), alpha = 1 - confidence; nonconformity
  ``max(q_lo - y, y - q_hi)``; the cell is flagged when y lies outside
  ``[q_lo - Q, q_hi + Q]``.
* categorical target: class-conditional (Mondrian) conformal classification with
  nonconformity ``1 - p(y | x)``; the cell is flagged when the observed label is not
  in the prediction set.

Deviations from the original (documented in docs/method_compatibility.md):
1. Base learner: scikit-learn HistGradientBoosting instead of AutoGluon (RF/XT/FastAI
   + HPO). The conformal wrapper and calibration logic follow the original.
2. Column types come from the source contract, not from the original's random
   cardinality heuristic (which can type integer amounts or ages as categorical).
3. The interval test is strict (y < lower or y > upper) - the original uses <= / >=,
   which flags values *on* the interval boundary (frequent for integer data).
4. Cells additionally receive a conformal p-value, so cells can be ranked for a
   fixed review budget (score = 1 - p, plus a tie-breaker < 1e-5 on the normalised
   nonconformity, because many cells share the minimal p-value 1/(n_cal + 1)). For categorical columns the ranking uses the
   *marginal* p-value; class-conditional p-values are bounded below by 1/(n_label + 1)
   and are not comparable between rare and frequent labels.
6. Categorical prediction sets are inclusive (label in set iff s <= q_hat), the
   standard split-conformal definition. The original uses s < q_hat; with tied
   tree-model probabilities this excludes labels whose score equals q_hat and
   inflates alerts on untouched cells (observed: 12-43% of PAY_x cells at c = 0.999).
5. Empty prediction sets are treated as inliers, as in the original experiments
   (``empty_pred_sets_are_inliers=True`` in scripts/run_experiment.py).
"""

from __future__ import annotations

import hashlib
import time
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from dq_framework.contracts import Contract
from dq_framework.detectors.base import (
    CONDITIONAL,
    INCOMPATIBLE,
    PASS,
    Compatibility,
    Detector,
    DetectorOutput,
    environment_info,
)

# Conformal p-values have resolution 1/(n_cal + 1); many cells share the minimum p-value. A tiny,
# monotone tie-breaker (always < the p-value resolution for n_cal < 10,000) orders cells within a tie
# by how far they lie from the model's prediction, so that fixed review budgets are not filled in
# arbitrary (file) order.
TIE_EPS = 1e-5


def _q_hat(scores: np.ndarray, confidence: float) -> float | None:
    """Conformal quantile, identical to conformal_inference.models.utils.calculate_q_hat."""
    n = len(scores)
    if n == 0:
        return None
    q = min(1.0, max(0.0, confidence * (1 + 1 / n)))
    return float(np.quantile(scores, q, method="higher"))


def _p_values(cal_sorted: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Conformal p-value p = (1 + #{cal >= s}) / (n + 1) for each test score s."""
    n = len(cal_sorted)
    n_ge = n - np.searchsorted(cal_sorted, s, side="left")
    return (1.0 + n_ge) / (n + 1.0)


class ConformalDataCleaningHGB(Detector):
    name = "cdc_hgb"
    granularity = "cell"
    supervision = "reference_data"
    limitations = [
        "Assumes the reference partition is (mostly) error-free; errors in it widen intervals.",
        "Mondrian calibration: labels with few calibration examples get wide sets and are rarely flagged.",
        "Re-implementation with a different base learner than the published experiments.",
    ]

    def __init__(
        self,
        confidence: float = 0.999,
        calibration_rows: int = 1000,
        max_iter: int = 200,
        learning_rate: float = 0.1,
        min_samples_leaf: int = 20,
        seed: int = 0,
        target_columns: list[str] | None = None,
        base_quantile: float | None = None,
        set_rule: str = "inclusive",
    ) -> None:
        if set_rule not in ("inclusive", "strict_original"):
            raise ValueError("set_rule must be 'inclusive' or 'strict_original'")
        super().__init__(
            set_rule=set_rule,
            base_quantile=base_quantile,
            confidence=confidence,
            calibration_rows=calibration_rows,
            max_iter=max_iter,
            learning_rate=learning_rate,
            min_samples_leaf=min_samples_leaf,
            seed=seed,
            target_columns=target_columns,
        )

    # ------------------------------------------------------------------ compatibility
    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        reasons, transforms = [], []
        n = len(reference)
        cal = self.config["calibration_rows"]
        if n < 2 * cal:
            return Compatibility(INCOMPATIBLE, [f"reference has {n} rows; needs >= {2 * cal} for training + calibration"])
        if len(contract.columns) < 2:
            return Compatibility(INCOMPATIBLE, ["needs >= 2 columns to predict a column from the others"])
        verdict = PASS
        for c in contract.categorical_columns:
            vc = reference[c].value_counts()
            k = len(vc)
            if k > 200:
                return Compatibility(INCOMPATIBLE, [f"{c}: {k} categories (too many for per-class calibration)"])
            exp_cal = vc / n * cal
            rare = int((exp_cal < 1 / (1 - self.config["confidence"]) / 10).sum())
            if rare:
                reasons.append(f"{c}: {rare} of {k} labels expected to have too few calibration examples to ever be flagged")
                verdict = CONDITIONAL
        miss = reference[contract.column_names].isna().mean()
        if (miss > 0).any():
            transforms.append("missing feature values passed natively to HistGradientBoosting (no imputation)")
            reasons.append(f"missing values present in {list(miss[miss > 0].index)}; reference rows with a missing target are not used for that column")
        transforms.append("categorical columns encoded as pandas categories fixed to reference levels")
        return Compatibility(verdict, reasons, transforms)

    # ------------------------------------------------------------------ fit
    def _features(self, df: pd.DataFrame, target: str) -> pd.DataFrame:
        X = df[[c for c in self._cols if c != target]].copy()
        for c in self._cat_cols:
            if c in X:
                X[c] = pd.Categorical(X[c].astype(object), categories=self._levels[c])
        return X

    def fit(self, reference: pd.DataFrame, contract: Contract) -> ConformalDataCleaningHGB:
        t0 = time.perf_counter()
        cfg = self.config
        self._contract = contract
        self._cols = contract.column_names
        self._cat_cols = contract.categorical_columns
        self._levels = {c: sorted(reference[c].dropna().unique().tolist(), key=lambda v: (str(type(v)), v)) for c in self._cat_cols}
        targets = cfg["target_columns"] or self._cols
        alpha = 1 - cfg["confidence"]
        self.models_: dict[str, dict[str, Any]] = {}
        self.warnings_: list[str] = []
        for target in targets:
            ref = reference[reference[target].notna()]
            n = len(ref)
            # per-column generator: the calibration split does not depend on the order of targets
            col_seed = int.from_bytes(hashlib.sha256(f"{cfg['seed']}|{target}".encode()).digest()[:4], "little")
            perm = np.random.default_rng(col_seed).permutation(n)
            n_cal = min(cfg["calibration_rows"], n // 2)
            cal_idx, tr_idx = perm[:n_cal], perm[n_cal:]
            tr, cal = ref.iloc[tr_idx], ref.iloc[cal_idx]
            Xtr, Xcal = self._features(tr, target), self._features(cal, target)
            common = {
                "max_iter": cfg["max_iter"],
                "learning_rate": cfg["learning_rate"],
                "min_samples_leaf": cfg["min_samples_leaf"],
                "categorical_features": "from_dtype",
                "random_state": cfg["seed"],
                "early_stopping": False,
            }
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if target in self._cat_cols:
                    ytr = tr[target].astype(object).map(str)
                    clf = HistGradientBoostingClassifier(**common).fit(Xtr, ytr)
                    classes = list(clf.classes_)
                    proba = clf.predict_proba(Xcal)
                    ycal = cal[target].astype(object).map(str).to_numpy()
                    col_of = {lab: j for j, lab in enumerate(classes)}
                    known = np.array([v in col_of for v in ycal])
                    s_obs = np.ones(len(ycal))
                    s_obs[known] = 1.0 - proba[np.flatnonzero(known), [col_of[v] for v in ycal[known]]]
                    cal_scores = {lab: np.sort(s_obs[ycal == lab]) for lab in classes}
                    self.models_[target] = {"kind": "cat", "model": clf, "classes": classes, "cal": cal_scores,
                                            "cal_marginal": np.sort(s_obs),
                                            "qhat": {k: _q_hat(v, cfg["confidence"]) for k, v in cal_scores.items()}}
                else:
                    ytr = tr[target].astype("float64")
                    # original: base quantiles at alpha/2; optionally a less extreme, more stable level
                    bq = cfg["base_quantile"] if cfg["base_quantile"] is not None else alpha / 2
                    qs = [bq, 0.5, 1 - bq]
                    regs = [HistGradientBoostingRegressor(loss="quantile", quantile=q, **common).fit(Xtr, ytr) for q in qs]
                    pred = np.column_stack([r.predict(Xcal) for r in regs])
                    ycal = cal[target].astype("float64").to_numpy()
                    s = np.maximum(pred[:, 0] - ycal, ycal - pred[:, 2])
                    self.models_[target] = {"kind": "num", "models": regs, "cal": np.sort(s),
                                            "qhat": _q_hat(s, cfg["confidence"])}
        self.fit_seconds_ = time.perf_counter() - t0
        return self

    # ------------------------------------------------------------------ score
    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        t0 = time.perf_counter()
        frames = []
        for target, m in self.models_.items():
            X = self._features(batch, target)
            y = batch[target]
            present = y.notna().to_numpy()
            score = np.full(len(batch), np.nan)
            flag = np.zeros(len(batch), dtype=bool)
            if m["kind"] == "num":
                pred = np.column_stack([r.predict(X) for r in m["models"]])
                yv = y.astype("float64").to_numpy()
                s = np.maximum(pred[:, 0] - yv, yv - pred[:, 2])
                p = _p_values(m["cal"], s)
                # tie-break among equal p-values by the nonconformity relative to the predicted interval width
                width = np.maximum(pred[:, 2] - pred[:, 0], 1e-9)
                score = 1.0 - p + TIE_EPS * (1.0 - np.exp(-np.maximum(s / width, 0.0)))
                flag = (yv < pred[:, 0] - m["qhat"]) | (yv > pred[:, 2] + m["qhat"])
            else:
                proba = m["model"].predict_proba(X)
                lab = y.astype(object).map(lambda v: str(v) if pd.notna(v) else None).to_numpy()
                col_of = {c: j for j, c in enumerate(m["classes"])}
                j_obs = np.array([col_of.get(v, -1) if v is not None else -1 for v in lab])
                known = j_obs >= 0
                s_obs = np.ones(len(batch))
                s_obs[known] = 1.0 - proba[np.flatnonzero(known), j_obs[known]]
                # ranking score: marginal conformal p-value (comparable across labels and columns)
                score = 1.0 - _p_values(m["cal_marginal"], s_obs) + TIE_EPS * s_obs
                # flag: class-conditional (Mondrian) prediction set, inclusive: y in C(x) iff s(x, y) <= q_hat(y)
                qh = np.array([m["qhat"][c] if m["qhat"][c] is not None else np.inf for c in m["classes"]])
                if self.config["set_rule"] == "inclusive":
                    in_any = ((1.0 - proba) <= qh[None, :]).any(axis=1)  # non-empty prediction set
                    in_set = np.zeros(len(batch), dtype=bool)
                    in_set[known] = s_obs[known] <= qh[j_obs[known]]
                else:  # reproduces conformal_inference ConformalClassifier.predict (strict '<')
                    in_any = ((1.0 - proba) < qh[None, :]).any(axis=1)
                    in_set = np.zeros(len(batch), dtype=bool)
                    in_set[known] = s_obs[known] < qh[j_obs[known]]
                unseen = (~known) & np.array([v is not None for v in lab])
                flag = (~in_set & in_any) | unseen  # empty set -> inlier (original setting); unseen label -> flagged
                score[unseen] = 1.0
            score[~present] = np.nan
            flag[~present] = False
            frames.append(
                pd.DataFrame(
                    {
                        "_scenario_id": batch["_scenario_id"].to_numpy() if "_scenario_id" in batch else "",
                        "_row_id": batch["_row_id"].to_numpy(),
                        "column": target,
                        "score": score,
                        "flag": flag,
                    }
                )
            )
        out = pd.concat(frames, ignore_index=True)
        return DetectorOutput(
            detector=self.name,
            granularity="cell",
            scores=out,
            config=dict(self.config),
            fit_seconds=getattr(self, "fit_seconds_", 0.0),
            score_seconds=time.perf_counter() - t0,
            limitations=list(self.limitations),
            environment=environment_info(),
        )
