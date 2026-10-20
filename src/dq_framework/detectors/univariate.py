"""Column-wise (univariate) cell detectors used as literature baselines. All produce binary flags only.

* ``sd_outlier``  - REIN's "SD" outlier detector family: a numeric cell is flagged if it lies more than ``n_sd``
  standard deviations from the column mean (Abdelaal et al., EDBT 2023, Table 1). REIN's code carries
  "All Rights Reserved" headers and is not reused; this is the textbook rule with the common default n = 3.
* ``iqr_outlier`` - REIN's "IQR" detector: flagged outside [Q1 - k IQR, Q3 + k IQR], textbook k = 1.5.
* ``lucario_core`` - the numerical and categorical constraints of LUCARIO (Qin, Li & Merlo, Information and
  Software Technology 192, 2026, 108035), **partial and provisional**: re-implemented from a written
  description of the public replication repository (mooselab/Detect-Cell-level-Data-Anomalies-With-LUCARIO
  @3664bfa8, which has no licence file, so no code was copied or executed) because the paper full text could
  not be read. Rules: null tokens flagged; type constraint (majority of float-parseable vs string values,
  unless the binary entropy of the two shares is >= 0.5); numerical constraint median +- 3 MAD (unscaled),
  **dropped for the column if more than 5 % of the batch's cells violate it**; categorical constraint by
  the largest jump in the ascending frequency list (a dummy count 1 prepended), accepted only if the
  categories above the jump cover > 95 % (or the top value alone does). The pattern (regex) constraints
  are **not** implemented: our analysed columns are typed numbers and codes. Whether LUCARIO applies the
  categorical constraint to numeric columns is not documented in what we could read; here it is applied to
  every column and is void when the coverage condition fails (assumption).

Native usage of all three is transductive (statistics of the batch under test, ``fit_on='batch'``); fitting
on the reference partition (``fit_on='reference'``) is available for an information-matched comparison.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from dq_framework.contracts import Contract
from dq_framework.detectors.base import PASS, Compatibility, Detector, DetectorOutput, environment_info

NULL_TOKENS = {"", "NULL", "None", "N/A", "NaN", "nan", "<NA>"}


def _as_text(s: pd.Series) -> pd.Series:
    def f(v):
        if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    return s.astype(object).map(f)


def _float_or_nan(t: pd.Series) -> np.ndarray:
    return pd.to_numeric(t.where(~t.isin(NULL_TOKENS)), errors="coerce").to_numpy(dtype="float64")


class _ColumnwiseDetector(Detector):
    granularity = "cell"
    supervision = "none"
    provides_scores = False

    def __init__(self, fit_on: str = "batch", **config) -> None:
        if fit_on not in ("reference", "batch"):
            raise ValueError("fit_on must be 'reference' or 'batch'")
        super().__init__(fit_on=fit_on, **config)
        self.fit_scope = fit_on

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        return Compatibility(PASS, ["binary output only (no ranking score)"], ["values compared as numbers / text"])

    def fit(self, reference: pd.DataFrame, contract: Contract):
        self._contract = contract
        self._cols = contract.column_names
        if self.config["fit_on"] == "reference":
            self._fit_stats(reference)
        return self

    def _fit_stats(self, train: pd.DataFrame) -> None:
        raise NotImplementedError

    def _flags(self, batch: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        raise NotImplementedError

    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        t0 = time.perf_counter()
        if self.config["fit_on"] == "batch":
            self._fit_stats(batch)
        flags = self._flags(batch)
        sid = batch["_scenario_id"].to_numpy() if "_scenario_id" in batch else np.full(len(batch), "", dtype=object)
        frames = []
        for c in self._cols:
            f, why = flags.get(c, (np.zeros(len(batch), bool), np.full(len(batch), None, dtype=object)))
            frames.append(pd.DataFrame({"_scenario_id": sid, "_row_id": batch["_row_id"].to_numpy(), "column": c,
                                        "score": np.nan, "flag": f, "explanation": np.where(f, why, None)}))
        return DetectorOutput(self.name, "cell", pd.concat(frames, ignore_index=True), config=dict(self.config),
                              score_seconds=time.perf_counter() - t0, limitations=list(self.limitations),
                              environment=environment_info())


class SDOutlier(_ColumnwiseDetector):
    name = "sd_outlier"
    limitations = ["Numeric columns only; univariate; mean and SD are not robust to the errors themselves."]

    def __init__(self, n_sd: float = 3.0, fit_on: str = "batch") -> None:
        super().__init__(fit_on=fit_on, n_sd=n_sd)

    def _fit_stats(self, train):
        self._stats = {c: (float(train[c].astype("float64").mean()), float(train[c].astype("float64").std(ddof=0)))
                       for c in self._contract.numeric_columns}

    def _flags(self, batch):
        out, k = {}, self.config["n_sd"]
        for c, (mu, sd) in self._stats.items():
            x = batch[c].astype("float64").to_numpy()
            f = np.abs(x - mu) > k * sd
            out[c] = (f, np.full(len(x), f"SD rule: outside mean ± {k:g} sd [{mu - k * sd:.4g}, {mu + k * sd:.4g}]", dtype=object))
        return out


class IQROutlier(_ColumnwiseDetector):
    name = "iqr_outlier"
    limitations = ["Numeric columns only; univariate; skewed or zero-inflated amounts produce many alerts."]

    def __init__(self, k: float = 1.5, fit_on: str = "batch") -> None:
        super().__init__(fit_on=fit_on, k=k)

    def _fit_stats(self, train):
        self._stats = {}
        for c in self._contract.numeric_columns:
            q1, q3 = np.nanquantile(train[c].astype("float64"), [0.25, 0.75])
            self._stats[c] = (float(q1), float(q3))

    def _flags(self, batch):
        out, k = {}, self.config["k"]
        for c, (q1, q3) in self._stats.items():
            lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
            x = batch[c].astype("float64").to_numpy()
            f = (x < lo) | (x > hi)
            out[c] = (f, np.full(len(x), f"IQR rule: outside [{lo:.4g}, {hi:.4g}]", dtype=object))
        return out


def _binary_entropy(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p)))


def categorical_constraint(counts: pd.Series, coverage: float = 0.95) -> set | None:
    """Accepted values by the largest frequency jump, or None if the coverage condition fails."""
    if counts.empty:
        return None
    total = float(counts.sum())
    top = counts.sort_values(ascending=False)
    if top.iloc[0] / total > coverage:
        return {top.index[0]}
    asc = counts.sort_values(ascending=True, kind="mergesort")
    f = np.concatenate([[1.0], asc.to_numpy(dtype=float)])
    ratios = f[1:] / f[:-1]
    cut = int(np.argmax(ratios))  # values asc.iloc[cut:] lie above the largest jump
    accepted = asc.iloc[cut:]
    if accepted.sum() / total > coverage:
        return set(accepted.index)
    return None


class LucarioCore(_ColumnwiseDetector):
    name = "lucario_core"
    limitations = [
        "Partial re-implementation (numerical + categorical constraints; no regex pattern constraints).",
        "Provisional: written from a description of the unlicensed replication code, not from the paper text; "
        "no fidelity check against the original was possible.",
        "The numerical constraint switches itself off for a column when > 5 % of the batch violates it.",
    ]

    def __init__(self, k_mad: float = 3.0, coverage: float = 0.95, fit_on: str = "batch") -> None:
        super().__init__(fit_on=fit_on, k_mad=k_mad, coverage=coverage)

    def _fit_stats(self, train):
        cov = self.config["coverage"]
        self._spec = {}
        for c in self._cols:
            t = _as_text(train[c])
            nonnull = t[~t.isin(NULL_TOKENS)]
            x = _float_or_nan(nonnull)
            p_num = float(np.isfinite(x).mean()) if len(x) else 0.0
            ctype = "mixed" if _binary_entropy(p_num) >= 0.5 else ("numeric" if p_num >= 0.5 else "string")
            spec = {"type": ctype}
            if ctype == "numeric":
                v = x[np.isfinite(x)]
                med = float(np.median(v))
                mad = float(np.median(np.abs(v - med)))
                spec["range"] = (med - self.config["k_mad"] * mad, med + self.config["k_mad"] * mad)
            spec["accepted"] = categorical_constraint(nonnull.value_counts(), cov)
            self._spec[c] = spec

    def _flags(self, batch):
        out = {}
        drop_share = 1.0 - self.config["coverage"]
        for c, spec in self._spec.items():
            t = _as_text(batch[c])
            n = len(t)
            f = np.zeros(n, dtype=bool)
            why = np.full(n, None, dtype=object)
            null = t.isin(NULL_TOKENS).to_numpy()
            f |= null
            why[null] = "LUCARIO: null token"
            x = _float_or_nan(t)
            isnum = np.isfinite(x)
            if spec["type"] == "numeric":
                bad = ~null & ~isnum
                why[bad & ~f] = "LUCARIO: type constraint (non-numeric value in numeric column)"
                f |= bad
                lo, hi = spec["range"]
                viol = isnum & ((x < lo) | (x > hi))
                if viol.mean() <= drop_share:  # the numerical constraint is dropped above 5 % violations
                    why[viol & ~f] = f"LUCARIO: outside median ± {self.config['k_mad']:g} MAD [{lo:.4g}, {hi:.4g}]"
                    f |= viol
            elif spec["type"] == "string":
                bad = ~null & isnum
                why[bad & ~f] = "LUCARIO: type constraint (numeric value in text column)"
                f |= bad
            if spec["accepted"] is not None:
                viol = ~null & ~t.isin(spec["accepted"]).to_numpy()
                why[viol & ~f] = "LUCARIO: categorical constraint (value outside the dominant categories)"
                f |= viol
            out[c] = (f, why)
        return out
