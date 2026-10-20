"""dBoost (Pit-Claudel, Mariet, Harding & Madden, MIT CSAIL TR 2016): tuple expansion + simple statistical models.

Two implementations, kept apart like CDC:

* :class:`DBoost` (``dboost``) - a clean-room, vectorised **re-implementation** written from the paper and from
  reading the behaviour of the original program (no code copied; the original is GPL-3.0, this repository is
  MIT). Fast enough for the pilot.
* :class:`OriginalDBoost` (``dboost_original``) - runs the **original** program (cpitclaudel/dBoost @a47cb564,
  pure Python 3) in a child process through ``envs/dboost/run_dboost_original.py`` (GPL-3.0-or-later, not
  imported here). Used for fidelity checks; ~60 s per 3,000 rows, too slow for the full pilot.

Method (as implemented by the original at the pinned commit)
-------------------------------------------------------------
1. *Tuple expansion.* The type of each field (int / float / str) is inferred from the first row. Every value is
   expanded into derived features: int -> id, nil, 8 ``gmtime`` date parts, is-weekend, bits 0-5, divisible by 3
   and 5, mod 10; float -> id, 8 date parts of ``int(x)``, fractional part; str -> case flags, is-digit, length,
   unicode signature, digit-normalised string, e-mail check and domain, id, empty.
2. *Analyzer* (``statistical``): mean and population standard deviation of every numeric feature on the
   training data, and Pearson correlation between numeric features of different fields; pairs with
   |r| > ``corr_threshold`` become "hints" (correlated feature pairs).
3. *Models* (one per detector configuration):
   ``gaussian(t)``: a field is flagged if any of its numeric features lies more than ``t`` standard deviations
   from the training mean (a constant feature flags any other value).
   ``histogram(peak_s, outlier_s)``: per feature with at most 16 distinct training values whose top
   ``max(1, min(3, k // 2))`` classes hold more than ``peak_s`` of the mass, a value is flagged if its class
   holds less than ``outlier_s`` of the training values; hint pairs are tested the same way, but only for rows
   without other discrepancies.
   ``partitioned(jmp, peak_s, outlier_s)``: for every hint pair (a, b) and every value of a, the histogram of b
   is "peaked" if it has 2-16 classes and the largest ratio between consecutive sorted counts exceeds ``jmp``
   with the upper part holding more than ``peak_s`` of the mass; b is flagged if its class holds less than
   ``outlier_s`` of the rows with that value of a. Both fields of the pair are implicated.
4. *Output:* flagged fields per row - binary in the original. For the Gaussian model this module also returns
   the model's own test statistic max_f |x_f - mean_f| / sd_f as ``score`` (flag <=> score > t, verified in
   tests), so it can be evaluated at a review budget like CDC (decision D-27: an extension, not part of the
   published method). The histogram models have no such statistic and stay binary (``score`` NaN).

Behaviour reproduced on purpose (it changes what dBoost can detect): test rows whose values do not parse with
the inferred field types (e.g. a non-integer or empty value in an integer field) are skipped by the original
reader, so errors that change a value's type - or missing values - are never flagged. ``skip_unparseable``
keeps this behaviour (default) and reports the number of skipped rows.

``type_mode='text'`` reproduces how Raha and REIN call dBoost (CSV written with a header row, so the first row
types every field as a string): numbers are then expanded as text (length, digit/sign signature, template),
and no row is ever skipped. Integral numbers are rendered without a decimal part, as in the source files.

Information used: the training data only (``fit_on='reference'``, the original's ``--train-with``) or the batch
under test itself (``fit_on='batch'``, the original's default usage, transductive). No labels.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dq_framework import paths
from dq_framework.contracts import Contract
from dq_framework.detectors.base import (
    BLOCKED,
    CONDITIONAL,
    PASS,
    Compatibility,
    Detector,
    DetectorOutput,
    environment_info,
)

MAX_HIST = 16
DATE_NAMES = ["tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday"]


# --------------------------------------------------------------------------- tuple expansion (vectorised)


def _date_parts(sec: np.ndarray) -> list[np.ndarray]:
    t = sec.astype("int64").astype("datetime64[s]")
    day = t.astype("datetime64[D]")
    sod = (t - day).astype("int64")
    d = day.astype("int64")
    year = t.astype("datetime64[Y]")
    month = t.astype("datetime64[M]")
    return [year.astype("int64") + 1970, month.astype("int64") % 12 + 1, (day - month.astype("datetime64[D]")).astype("int64") + 1,
            sod // 3600, (sod % 3600) // 60, sod % 60, (d + 3) % 7, (day - year.astype("datetime64[D]")).astype("int64") + 1]


def expand_column(values: pd.Series, ftype: str) -> tuple[list[str], list[np.ndarray], list[bool]]:
    """Expanded features of one field: (names, arrays, is_numeric). Values must already parse with ``ftype``."""
    if ftype == "int":
        x = values.to_numpy(dtype="float64").astype("int64")
        dates = _date_parts(x)
        wday = dates[6]
        names = ["id", *DATE_NAMES, "is weekend", *[f"bit {p}" for p in range(6)], "div 3", "div 5", "mod 10"]
        arrs = [x, *dates, np.isin(wday, (5, 6)).astype("int64"), *[(x >> p) & 1 for p in range(6)],
                (np.mod(x, 3) == 0).astype("int64"), (np.mod(x, 5) == 0).astype("int64"), np.mod(x, 10)]
        return names, [a.astype("float64") for a in arrs], [True] * len(names)
    if ftype == "float":
        x = values.to_numpy(dtype="float64")
        names = ["id", *DATE_NAMES, "frac part"]
        arrs = [x, *[a.astype("float64") for a in _date_parts(np.trunc(x))], x - np.trunc(x)]
        return names, arrs, [True] * len(names)
    def _text(v):
        if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))  # delivered files carry integers without a decimal part
        return str(v)

    s = values.astype(object).map(_text)
    import re
    import unicodedata

    email = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
                       r"(?:\.(?P<ext>[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*$")
    num = re.compile(r"(^s)?\d+")
    m = s.map(email.match)
    names = ["upper case", "lower case", "title case", "is digit", "length", "signature", "strp",
             "simple email check", "email domain", "id", "empty"]
    arrs = [s.map(str.isupper), s.map(str.islower), s.map(str.istitle), s.map(str.isdigit), s.map(len),
            s.map(lambda v: ",".join(map(unicodedata.category, v))), s.map(lambda v: num.sub("<num>", v)),
            m.map(lambda r: r is not None), m.map(lambda r: r.group("ext").lower() if r else "NONE"), s,
            s.map(lambda v: v == "" or v.isspace())]
    numeric = [True, True, True, True, True, False, False, True, False, False, True]
    out = [a.to_numpy(dtype="float64") if n else a.to_numpy(dtype=object) for a, n in zip(arrs, numeric, strict=True)]
    return names, out, numeric


def field_types(contract: Contract, reference: pd.DataFrame) -> dict[str, str]:
    """dBoost infers int / float / str from the delivered text; integral numeric columns arrive as ints."""
    out = {}
    for c in contract.columns:
        v = reference[c.name].dropna()
        if c.type == "categorical" and not pd.api.types.is_numeric_dtype(v):
            out[c.name] = "str"
        else:
            vv = pd.to_numeric(v, errors="coerce")
            out[c.name] = "int" if len(vv) and vv.notna().all() and np.all(np.mod(vv.to_numpy(float), 1) == 0) else "float"
    return out


def parseable(batch: pd.DataFrame, types: dict[str, str]) -> np.ndarray:
    """Rows the original reader keeps: every value parses with the field's type (empty never parses as a number)."""
    ok = np.ones(len(batch), dtype=bool)
    for c, t in types.items():
        if t == "str":
            continue
        x = pd.to_numeric(batch[c].astype(object), errors="coerce").to_numpy(dtype="float64")
        good = np.isfinite(x)
        if t == "int":
            good &= np.mod(np.where(good, x, 0), 1) == 0
        ok &= good
    return ok


def _counts(a: np.ndarray) -> dict[Any, int]:
    vals, cnt = np.unique(a.astype(object) if a.dtype == object else a, return_counts=True)
    return dict(zip(vals.tolist(), cnt.tolist(), strict=True))


def _hist_peaked(counts: dict[Any, int], peak_s: float) -> bool:
    if len(counts) > MAX_HIST:
        return False
    k = max(1, min(3, len(counts) // 2))
    v = sorted(counts.values(), reverse=True)
    return sum(v[:k]) > peak_s * sum(v)


def _part_peaked(counts: dict[Any, int], jmp: float, peak_s: float) -> bool:
    if len(counts) > MAX_HIST or len(counts) < 2:
        return False
    ys = sorted(counts.values())
    delta, _, _, start = max((ys[i + 1] / ys[i], ys[i + 1], ys[i], i + 1) for i in range(len(ys) - 1))
    lo, hi = sum(ys[:start]), sum(ys[start:])
    return delta > jmp and hi > peak_s * (hi + lo)


class DBoost(Detector):
    name = "dboost"
    granularity = "cell"
    supervision = "reference_data"
    provides_scores = False
    limitations = [
        "Gaussian ranking uses the existing test-statistic extension; histogram variants have binary flags only.",
        "Rows whose values do not parse with the inferred field types (missing values, non-integers in integer "
        "fields) are skipped, as in the original, so type-changing errors are never flagged.",
        "Bit/modulo/date expansions of plain integers are applied to amounts and codes as in the original; they "
        "carry no domain meaning and can dominate the alerts.",
        "Re-implementation (clean room); fidelity checked against the original on samples.",
    ]

    def __init__(self, model: str = "gaussian", params: list[float] | None = None, corr_threshold: float = 0.8,
                 fit_on: str = "reference", skip_unparseable: bool = True, max_fit_rows: int | None = None,
                 seed: int = 0, explain: bool = False, type_mode: str = "inferred", score: bool = True) -> None:
        if type_mode not in ("inferred", "text"):
            raise ValueError("type_mode must be 'inferred' or 'text'")
        defaults = {"gaussian": [3.0], "histogram": [0.8, 0.2], "partitioned": [5.0, 0.8, 0.2]}
        if model not in defaults:
            raise ValueError(f"model must be one of {sorted(defaults)}")
        if fit_on not in ("reference", "batch"):
            raise ValueError("fit_on must be 'reference' or 'batch'")
        super().__init__(model=model, params=list(params or defaults[model]), corr_threshold=corr_threshold,
                         fit_on=fit_on, skip_unparseable=skip_unparseable, max_fit_rows=max_fit_rows, seed=seed,
                         explain=explain, type_mode=type_mode, score=score)
        self.fit_scope = fit_on
        # Gaussian model: score = max over the field's expanded features of |x - mean| / sd, the statistic the
        # model thresholds (flag <=> score > t, tested). Ranking by it is an extension (decision D-27); the
        # histogram models have no such statistic and stay binary.
        self.provides_scores = bool(score and model == "gaussian")

    @property
    def label(self) -> str:
        return f"dboost_{self.config['model']}" + ("_batch" if self.config["fit_on"] == "batch" else "")

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        t = ["fields typed int / float / str as dBoost's reader would type the delivered text",
             "integral numeric columns expanded as integers (bits, mod, div, gmtime date parts)"]
        reasons = ["Gaussian test-statistic ranking is an extension; native flags are also retained"
                   if self.provides_scores else "binary output only; budget-capped flags use label-blind ordering"]
        types = field_types(contract, reference)
        if self.config["type_mode"] == "text":
            types = {c: "str" for c in contract.column_names}
            t = ["all fields expanded as text; declared missing values represented as empty strings"]
        n_skip = int((~parseable(reference, types)).sum())
        if n_skip:
            reasons.append(f"{n_skip} reference rows do not parse with the inferred types and are not used")
        return Compatibility(CONDITIONAL if n_skip else PASS, reasons, t)

    # ------------------------------------------------------------------ fit
    def _expand(self, df: pd.DataFrame) -> dict[str, tuple[list[str], list[np.ndarray], list[bool]]]:
        return {c: expand_column(df[c], self._types[c]) for c in self._cols}

    def fit(self, reference: pd.DataFrame, contract: Contract) -> DBoost:
        self._contract = contract
        self._cols = contract.column_names
        self._types = field_types(contract, reference)
        if self.config["type_mode"] == "text":
            # Raha and REIN write the CSV with a header row, so dBoost's first-row typing makes every field a string
            self._types = {c: "str" for c in self._cols}
        if self.config["fit_on"] == "reference":
            self._fit_model(reference)
        return self

    def _fit_model(self, train: pd.DataFrame) -> None:
        t0 = time.perf_counter()
        train = train[parseable(train, self._types)]
        if self.config["max_fit_rows"] and len(train) > self.config["max_fit_rows"]:
            train = train.sample(self.config["max_fit_rows"], random_state=self.config["seed"])
        ex = self._expand(train)
        n = len(train)
        # statistical analyzer: per numeric feature mean / population sigma, Pearson hints across fields
        self._stats: dict[tuple[str, int], tuple[float, float]] = {}
        num_keys, num_cols = [], []
        for c, (_names, arrs, isnum) in ex.items():
            for j, (a, isn) in enumerate(zip(arrs, isnum, strict=True)):
                if isn:
                    mu = float(a.mean())
                    sd = float(np.sqrt(max(0.0, (a * a).mean() - mu * mu)))
                    self._stats[(c, j)] = (mu, sd)
                    num_keys.append((c, j))
                    num_cols.append(a)
        self._hints: list[tuple[tuple[str, int], tuple[str, int]]] = []
        if self.config["model"] in ("histogram", "partitioned") and num_cols:
            M = np.column_stack(num_cols)
            mu = M.mean(axis=0)
            sd = np.sqrt(np.maximum(0.0, (M * M).mean(axis=0) - mu * mu))
            C = (M.T @ M / n - np.outer(mu, mu))
            with np.errstate(divide="ignore", invalid="ignore"):
                R = C / np.outer(sd, sd)
            field = np.array([self._cols.index(k[0]) for k in num_keys])
            ii, jj = np.nonzero(np.triu(np.abs(np.nan_to_num(R, nan=0.0)) > self.config["corr_threshold"], k=1)
                                & (field[:, None] != field[None, :]) & (np.outer(sd, sd) != 0))
            self._hints = sorted((min(num_keys[i], num_keys[j], key=lambda k: (self._cols.index(k[0]), k[1])),
                                  max(num_keys[i], num_keys[j], key=lambda k: (self._cols.index(k[0]), k[1])))
                                 for i, j in zip(ii, jj, strict=True))
        model = self.config["model"]
        if model == "histogram":
            peak_s = self.config["params"][0]
            self._hist = {}
            for c, (_names, arrs, _isnum) in ex.items():
                for j, a in enumerate(arrs):
                    cnt = _counts(a)
                    if _hist_peaked(cnt, peak_s):
                        self._hist[(c, j)] = cnt
            self._hint_hist = {}
            for h in self._hints:
                a, b = ex[h[0][0]][1][h[0][1]], ex[h[1][0]][1][h[1][1]]
                # a joint histogram of a hint pair is discarded beyond 16 distinct pairs; it can only stay within
                # that limit if both features have <= 16 distinct values
                if len(np.unique(a)) > MAX_HIST or len(np.unique(b)) > MAX_HIST:
                    continue
                g = pd.DataFrame({"a": a, "b": b}).groupby(["a", "b"], sort=False).size()
                cnt = dict(zip(g.index.tolist(), g.to_numpy().tolist(), strict=True))
                if _hist_peaked(cnt, peak_s):
                    self._hint_hist[h] = cnt
        elif model == "partitioned":
            jmp, peak_s, _ = self._params3()
            self._part = {}
            for h in self._hints:
                key = ex[h[0][0]][1][h[0][1]]
                val = ex[h[1][0]][1][h[1][1]]
                g = pd.DataFrame({"k": key, "v": val}).groupby(["k", "v"], sort=False).size().rename("n").reset_index()
                nv = g.groupby("k", sort=False)["v"].transform("size")
                g = g[(nv >= 2) & (nv <= MAX_HIST)]
                if g.empty:
                    continue
                rows = []
                for _k, sub in g.groupby("k", sort=False):
                    cnt = dict(zip(sub["v"].tolist(), sub["n"].tolist(), strict=True))
                    if _part_peaked(cnt, jmp, peak_s):
                        rows.append(sub.assign(size=int(sub["n"].sum())))
                if rows:
                    tab = pd.concat(rows, ignore_index=True)
                    self._part[h] = (pd.Index(tab["k"].unique()), tab.set_index(["k", "v"])["n"],
                                     tab.groupby("k")["size"].first())
        self._n_train = n
        self.fit_seconds_ = time.perf_counter() - t0

    def _params3(self) -> tuple[float, float, float]:
        p = self.config["params"]
        return float(p[0]), float(p[1]), float(p[2])

    # ------------------------------------------------------------------ score
    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        if self.config["fit_on"] == "batch":
            self._fit_model(batch)
        t0 = time.perf_counter()
        ok = parseable(batch, self._types) if self.config["skip_unparseable"] else np.ones(len(batch), bool)
        sub = batch[ok]
        ex = self._expand(sub)
        n = len(sub)
        flags = {c: np.zeros(n, dtype=bool) for c in self._cols}
        why: dict[str, np.ndarray] = {c: np.full(n, None, dtype=object) for c in self._cols} if self.config["explain"] else {}
        model = self.config["model"]

        def mark(c: str, hit: np.ndarray, text: str) -> None:
            new = hit & ~flags[c]
            flags[c] |= hit
            if why:
                why[c][new] = text

        zmax = {c: np.zeros(n) for c in self._cols} if model == "gaussian" else {}
        if model == "gaussian":
            t = float(self.config["params"][0])
            for (c, j), (mu, sd) in self._stats.items():
                a = ex[c][1][j]
                dev = np.abs(a - mu)
                mark(c, dev > t * sd, f"dBoost gaussian: '{ex[c][0][j]}' outside mean ± {t:g} sd "
                     f"[{mu - t * sd:.4g}, {mu + t * sd:.4g}]")
                # the model's own test statistic; a constant training feature (sd = 0) flags any deviation, so its
                # z is "infinite" and is represented as 1e6 + deviation to keep an order among such cells
                with np.errstate(divide="ignore", invalid="ignore"):
                    z = np.where(sd > 0, dev / sd, np.where(dev > 0, 1e6 + dev, 0.0))
                zmax[c] = np.maximum(zmax[c], z)
        elif model == "histogram":
            outlier_s = float(self.config["params"][1])
            for (c, j), cnt in self._hist.items():
                a = ex[c][1][j]
                cnt_arr = pd.Series(a).map(lambda v, cnt=cnt: cnt.get(v, 0)).to_numpy(dtype=float)
                mark(c, cnt_arr < outlier_s * self._n_train, f"dBoost histogram: '{ex[c][0][j]}' value rare in training")
            any_flag = np.zeros(n, dtype=bool)
            for c in self._cols:
                any_flag |= flags[c]
            for h, cnt in self._hint_hist.items():
                a = list(zip(ex[h[0][0]][1][h[0][1]].tolist(), ex[h[1][0]][1][h[1][1]].tolist(), strict=True))
                hit = np.array([cnt.get(p, 0) for p in a], dtype=float) < outlier_s * self._n_train
                hit &= ~any_flag
                for c in (h[0][0], h[1][0]):
                    mark(c, hit, f"dBoost histogram: rare pair ({h[0][0]}, {h[1][0]})")
        else:
            _, _, outlier_s = self._params3()
            for h, (keys, counts, sizes) in self._part.items():
                key = pd.Series(ex[h[0][0]][1][h[0][1]])
                val = pd.Series(ex[h[1][0]][1][h[1][1]])
                known = keys.get_indexer(key) >= 0
                if not known.any():
                    continue
                cnt = counts.reindex(pd.MultiIndex.from_arrays([key, val])).fillna(0).to_numpy()
                size = sizes.reindex(key).to_numpy()
                hit = known & (cnt < outlier_s * np.nan_to_num(size, nan=0.0))
                for c in (h[0][0], h[1][0]):
                    mark(c, hit, f"dBoost partitioned histogram: {h[1][0]} unusual given {h[0][0]}")
        frames = []
        sid = sub["_scenario_id"].to_numpy() if "_scenario_id" in sub else np.full(n, "", dtype=object)
        for c in self._cols:
            col_score = zmax[c] if (zmax and self.provides_scores) else np.nan
            f = pd.DataFrame({"_scenario_id": sid, "_row_id": sub["_row_id"].to_numpy(), "column": c,
                              "score": col_score, "flag": flags[c]})
            if why:
                f["explanation"] = why[c]
            frames.append(f)
        out = pd.concat(frames, ignore_index=True)
        warn = [f"{int((~ok).sum())} rows not analysed (values do not parse with the inferred field types)"] if (~ok).any() else []
        return DetectorOutput(self.name, "cell", out, config=dict(self.config), fit_seconds=getattr(self, "fit_seconds_", 0.0),
                              score_seconds=time.perf_counter() - t0, warnings=warn, limitations=list(self.limitations),
                              environment=environment_info({"n_hints": len(self._hints), "n_skipped_rows": int((~ok).sum())}))


# --------------------------------------------------------------------------- original program (child process)

DBOOST_ENV = paths.ROOT / "envs" / "dboost"


def _to_tsv(df: pd.DataFrame, cols: list[str], types: dict[str, str], path: Path) -> None:
    out = pd.DataFrame(index=df.index)
    for c in cols:
        s = df[c].astype(object)
        if types[c] == "int":
            out[c] = s.map(lambda v: "" if pd.isna(v) else (str(int(v)) if float(v).is_integer() else repr(float(v))))
        elif types[c] == "float":
            out[c] = s.map(lambda v: "" if pd.isna(v) else repr(float(v)))
        else:
            out[c] = s.map(lambda v: "" if pd.isna(v) else str(v))
    out.to_csv(path, sep="\t", header=False, index=False)


class OriginalDBoost(Detector):
    """The original dBoost program (GPL-3.0) in a child process; for fidelity checks on samples."""

    name = "dboost_original"
    granularity = "cell"
    supervision = "reference_data"
    provides_scores = False
    limitations = ["Pure-Python original: about 60 s for 2,000 training + 1,000 test rows on 23 fields (Credit).",
                   "Binary flags only."]
    MODEL_IDS = {"gaussian": "gaussian", "histogram": "histogram", "partitioned": "partitionedhistogram"}

    def __init__(self, model: str = "gaussian", params: list[float] | None = None, corr_threshold: float = 0.8,
                 timeout_s: int = 3600) -> None:
        defaults = {"gaussian": [3.0], "histogram": [0.8, 0.2], "partitioned": [5.0, 0.8, 0.2]}
        super().__init__(model=model, params=list(params or defaults[model]), corr_threshold=corr_threshold,
                         timeout_s=timeout_s)

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        if not (DBOOST_ENV / "src" / "dboost" / "__init__.py").exists():
            return Compatibility(BLOCKED, ["original not fetched: run envs/dboost/install.sh"])
        return Compatibility(CONDITIONAL, ["slow pure-Python original; use on samples only", "binary flags only"])

    def fit(self, reference: pd.DataFrame, contract: Contract) -> OriginalDBoost:
        self._ref, self._contract = reference, contract
        self._types = field_types(contract, reference)
        return self

    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        cols = self._contract.column_names
        ok = parseable(batch, self._types)
        sub = batch[ok]
        with tempfile.TemporaryDirectory(prefix="dboost_") as td:
            td = Path(td)
            _to_tsv(self._ref[parseable(self._ref, self._types)], cols, self._types, td / "train.tsv")
            _to_tsv(sub, cols, self._types, td / "test.tsv")
            job = {"dboost_src": str(DBOOST_ENV / "src"), "train": str(td / "train.tsv"), "test": str(td / "test.tsv"),
                   "out": str(td / "out.tsv"),
                   "model": [self.MODEL_IDS[self.config["model"]], *[repr(float(p)) for p in self.config["params"]]],
                   "analyzer": ["statistical", repr(float(self.config["corr_threshold"]))]}
            (td / "job.json").write_text(json.dumps(job))
            proc = subprocess.run([sys.executable, "-I", str(DBOOST_ENV / "run_dboost_original.py"), str(td / "job.json")],
                                  capture_output=True, text=True, timeout=self.config["timeout_s"], check=False)
            if proc.returncode != 0:
                return DetectorOutput(self.name, "cell", pd.DataFrame(columns=["_scenario_id", "_row_id", "column", "score", "flag"]),
                                      status="failed", config=dict(self.config), warnings=[proc.stderr[-2000:]])
            meta = json.loads((td / "out.tsv.meta.json").read_text())
            hits = pd.read_csv(td / "out.tsv", sep="\t", header=None, names=["row", "col", "model", "kind", "feature"])
        if meta["n_test_rows_parsed"] != len(sub):
            raise RuntimeError(f"original dBoost parsed {meta['n_test_rows_parsed']} of {len(sub)} rows: index mapping unsafe")
        flag = np.zeros((len(sub), len(cols)), dtype=bool)
        flag[hits["row"].to_numpy(int), hits["col"].to_numpy(int)] = True
        sid = sub["_scenario_id"].to_numpy() if "_scenario_id" in sub else np.full(len(sub), "", dtype=object)
        out = pd.concat([pd.DataFrame({"_scenario_id": sid, "_row_id": sub["_row_id"].to_numpy(), "column": c,
                                       "score": np.nan, "flag": flag[:, j]}) for j, c in enumerate(cols)], ignore_index=True)
        return DetectorOutput(self.name, "cell", out, config=dict(self.config), score_seconds=meta["seconds"],
                              limitations=list(self.limitations),
                              environment={"env": "envs/dboost", "commit": "a47cb564e900c3e5220413f810e810b00046d561", **meta})
