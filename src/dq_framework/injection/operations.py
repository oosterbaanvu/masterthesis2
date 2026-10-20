"""Error *operations*: how a selected cell value is changed.

An operation is separated from the *mechanism* that decides where errors occur
(``mechanisms.py``). Each operation declares

* ``column_types``: logical types it applies to,
* ``eligible(...)``: the cells where it produces a real, semantically valid change
  (e.g. scaling a 0 changes nothing, so zeros are not eligible), and
* ``apply(...)``: new values for the selected rows.

Where tab_err implements the operation appropriately it is used (WrongUnit,
MissingValue, Outlier; CategorySwap only as the explicitly named ``code_remap``). Financial operations missing from tab_err
(sign flip, digit transposition, period shift, rounding, plausible substitution)
are small custom injectors, tested in tests/test_injection.py.
"""

from __future__ import annotations

import random
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd


@dataclass
class OpContext:
    """Information an operation may use. Only reference-partition data is exposed."""

    column_type: str  # numeric | categorical
    reference_values: pd.Series  # values of the column in the reference partition
    batch: pd.DataFrame  # the batch being corrupted (uncorrupted values)
    domain: list[Any] = field(default_factory=list)  # valid categories (reference-observed)


class Operation(ABC):
    name: ClassVar[str]
    column_types: ClassVar[tuple[str, ...]]
    uses_tab_err: ClassVar[bool] = False
    sanity_only: ClassVar[bool] = False  # trivially detectable by design; used as sanity checks

    def __init__(self, **params: Any) -> None:
        self.params = params

    def describe(self) -> dict[str, Any]:
        return {"operation": self.name, "params": self.params, "tab_err": self.uses_tab_err}

    @abstractmethod
    def eligible(self, s: pd.Series, ctx: OpContext) -> pd.Series: ...

    @abstractmethod
    def apply(self, s: pd.Series, rows: pd.Index, ctx: OpContext, seed: int) -> pd.Series:
        """Return new values for ``rows`` (index aligned)."""


# --------------------------------------------------------------------------- tab_err-backed operations


def _tab_err_apply(error_type, s: pd.Series, rows: pd.Index) -> pd.Series:
    df = s.to_frame("v")
    mask = pd.DataFrame(False, index=df.index, columns=["v"])
    mask.loc[rows, "v"] = True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = error_type.apply(df, mask, "v")
    return out.loc[rows]


class Scale(Operation):
    """Unit / magnitude error (x10, x100, x1000, /100) via tab_err WrongUnit."""

    name = "scale"
    column_types = ("numeric",)
    uses_tab_err = True

    def eligible(self, s, ctx):
        return s.notna() & (s != 0)

    def apply(self, s, rows, ctx, seed):
        from tab_err.error_type import WrongUnit

        f = float(self.params.get("factor", 10.0))
        et = WrongUnit(config={"wrong_unit_scaling": lambda x, f=f: x * f}, seed=seed)
        return _tab_err_apply(et, s.astype("float64"), rows)


class CategorySwap(Operation):
    """Valid-but-wrong category, drawn independently per cell (custom, reproducible).

    ``weighing='frequency'`` (default) draws the wrong code with probability proportional to its
    reference frequency (excluding the true code): wrong codes are then as plausible as real ones.
    ``weighing='uniform'`` draws uniformly over the other reference-observed codes, which over-represents
    rare codes and makes swaps easy for rare-category controls.

    Not delegated to tab_err: in tab_err 0.2.1 (with pandas 2.3) CategorySwap applies its sampling
    function once per *category* instead of once per cell, so all cells sharing a true code receive
    the same wrong code (see ``CodeRemap`` and tests/test_tab_err_behaviour.py).
    """

    name = "category_swap"
    column_types = ("categorical",)

    def eligible(self, s, ctx):
        return s.notna() & s.isin(ctx.domain) & (len(ctx.domain) > 1)

    def apply(self, s, rows, ctx, seed):
        rng = np.random.default_rng(seed)
        weighing = self.params.get("weighing", "frequency")
        dom = list(ctx.domain)
        if weighing == "frequency":
            freq = ctx.reference_values.dropna().astype(object).value_counts()
            w_all = np.array([float(freq.get(v, 0.0)) for v in dom])
        elif weighing == "uniform":
            w_all = np.ones(len(dom))
        else:
            raise ValueError("weighing must be 'frequency' or 'uniform'")
        pos = {v: i for i, v in enumerate(dom)}
        out = []
        for v in s.loc[rows].astype(object):
            w = w_all.copy()
            w[pos[v]] = 0.0
            out.append(dom[int(rng.choice(len(dom), p=w / w.sum()))])
        return pd.Series(out, index=rows, dtype=object)


class CodeRemap(Operation):
    """Systematic code-mapping error via tab_err 0.2.1 CategorySwap (uniform).

    Because tab_err applies its sampling per category, every selected cell with true code ``a``
    receives the same wrong code ``f(a)`` within one scenario: a faulty mapping table rather than
    independent mislabels. Kept as a separate, explicitly named operation.
    """

    name = "code_remap"
    column_types = ("categorical",)
    uses_tab_err = True

    def eligible(self, s, ctx):
        return s.notna() & s.isin(ctx.domain) & (len(ctx.domain) > 1)

    def apply(self, s, rows, ctx, seed):
        from tab_err.error_type import CategorySwap as TECategorySwap

        cat = pd.Series(pd.Categorical(s.astype(object), categories=list(ctx.domain)), index=s.index)
        et = TECategorySwap(config={"mislabel_weighing": "uniform"}, seed=seed)
        state = random.getstate()  # tab_err seeds the global `random` module; restore it afterwards
        try:
            out = _tab_err_apply(et, cat, rows)
        finally:
            random.setstate(state)
        return out.astype(object)


class Missing(Operation):
    """Missing value in a mandatory field (sanity check: not_null catches it) via tab_err MissingValue."""

    name = "missing"
    column_types = ("numeric", "categorical")
    uses_tab_err = True
    sanity_only = True

    def eligible(self, s, ctx):
        return s.notna()

    def apply(self, s, rows, ctx, seed):
        from tab_err.error_type import MissingValue

        base = s.astype("float64") if ctx.column_type == "numeric" else s.astype(object)
        return _tab_err_apply(MissingValue(seed=seed), base, rows)


class Outlier(Operation):
    """Extreme value beyond the IQR fences (tab_err Outlier). Sanity check."""

    name = "outlier"
    column_types = ("numeric",)
    uses_tab_err = True
    sanity_only = True

    def eligible(self, s, ctx):
        return s.notna()

    def apply(self, s, rows, ctx, seed):
        from tab_err.error_type import Outlier as TEOutlier

        et = TEOutlier(config={"outlier_coefficient": float(self.params.get("coefficient", 1.0))}, seed=seed)
        return _tab_err_apply(et, s.astype("float64"), rows)


# --------------------------------------------------------------------------- custom financial operations


class SignFlip(Operation):
    """Debit/credit sign convention error: x -> -x."""

    name = "sign_flip"
    column_types = ("numeric",)

    def eligible(self, s, ctx):
        return s.notna() & (s != 0)

    def apply(self, s, rows, ctx, seed):
        return -s.loc[rows].astype("float64")


def _transpose(v: float, rng: np.random.Generator) -> float | None:
    neg = v < 0
    digits = list(str(int(round(abs(v)))))
    cand = [i for i in range(len(digits) - 1) if digits[i] != digits[i + 1]]
    # transposing into a leading zero would also change the magnitude; exclude it
    cand = [i for i in cand if not (i == 0 and digits[1] == "0")]
    if not cand:
        return None
    i = int(rng.choice(cand))
    digits[i], digits[i + 1] = digits[i + 1], digits[i]
    out = float(int("".join(digits)))
    return -out if neg else out


class DigitTransposition(Operation):
    """Manual-entry error: two adjacent (different) digits of an integer amount swapped."""

    name = "digit_transposition"
    column_types = ("numeric",)

    def eligible(self, s, ctx):
        rng = np.random.default_rng(0)
        ok = s.notna() & (s.abs() >= 10) & np.isclose(s.fillna(0) % 1, 0)
        return ok & s.where(ok, 0).map(lambda v: _transpose(v, rng) is not None)

    def apply(self, s, rows, ctx, seed):
        rng = np.random.default_rng(seed)
        return pd.Series([_transpose(v, rng) for v in s.loc[rows]], index=rows, dtype="float64")


class PeriodShift(Operation):
    """Column misalignment: the value of an adjacent period column is delivered in this column."""

    name = "period_shift"
    column_types = ("numeric", "categorical")

    def eligible(self, s, ctx):
        src = ctx.batch[self.params["source_column"]]
        return s.notna() & src.notna() & (s.astype(object) != src.astype(object))

    def apply(self, s, rows, ctx, seed):
        return ctx.batch.loc[rows, self.params["source_column"]].astype(s.dtype if s.dtype != "Int64" else object)


class Rounding(Operation):
    """Precision loss: amount rounded to the nearest ``unit`` (e.g. 1000)."""

    name = "rounding"
    column_types = ("numeric",)

    def eligible(self, s, ctx):
        unit = float(self.params.get("unit", 1000))
        r = (s / unit).round() * unit
        return s.notna() & (r != s)

    def apply(self, s, rows, ctx, seed):
        unit = float(self.params.get("unit", 1000))
        return (s.loc[rows] / unit).round() * unit


class PlausibleSubstitution(Operation):
    """Wrong-but-plausible value: drawn from the reference distribution of the column.

    For numeric columns the draw must differ from the original by at least
    ``min_rel_diff`` (relative) so the change is material; the new value lies inside
    the observed reference range by construction.
    """

    name = "plausible_substitution"
    column_types = ("numeric", "categorical")

    def eligible(self, s, ctx):
        return s.notna()

    def apply(self, s, rows, ctx, seed):
        rng = np.random.default_rng(seed)
        pool = ctx.reference_values.dropna().to_numpy()
        min_rel = float(self.params.get("min_rel_diff", 0.2))
        out = []
        for v in s.loc[rows]:
            for _ in range(100):
                w = pool[rng.integers(len(pool))]
                if ctx.column_type == "categorical":
                    if w != v:
                        break
                elif abs(w - v) > min_rel * max(abs(v), 1.0):
                    break
            else:
                w = v  # no material change found: left unchanged and recorded as unrealised
            out.append(w)
        return pd.Series(out, index=rows, dtype=object if ctx.column_type == "categorical" else "float64")


class OrdinalShift(Operation):
    """Period / position shift of an ordered code: the value is replaced by its neighbour in ``order``.

    Example: ``month`` delivered as the previous month (``step: -1``) - a stale period label. With
    ``require_observed`` (default) the new value must occur in the reference partition, so the error stays a
    plausible, valid code; without wrap-around the first/last value of the order is not eligible.
    """

    name = "ordinal_shift"
    column_types = ("categorical",)

    def _target(self, v, ctx):
        order = list(self.params["order"])
        step = int(self.params.get("step", 1))
        if v not in order:
            return None
        i = order.index(v) + step
        if self.params.get("wrap", False):
            i %= len(order)
        elif not 0 <= i < len(order):
            return None
        w = order[i]
        if self.params.get("require_observed", True) and w not in set(ctx.domain):
            return None
        return w

    def eligible(self, s, ctx):
        return s.astype(object).map(lambda v: pd.notna(v) and self._target(v, ctx) is not None).astype(bool)

    def apply(self, s, rows, ctx, seed):
        return pd.Series([self._target(v, ctx) for v in s.loc[rows].astype(object)], index=rows, dtype=object)


class InvalidCode(Operation):
    """Out-of-domain category code (sanity check: accepted_values catches it)."""

    name = "invalid_code"
    column_types = ("categorical",)
    sanity_only = True

    def eligible(self, s, ctx):
        return s.notna()

    def apply(self, s, rows, ctx, seed):
        code = self.params.get("code", -99)
        return pd.Series([code] * len(rows), index=rows, dtype=object)


OPERATIONS: dict[str, type[Operation]] = {
    cls.name: cls
    for cls in (Scale, CategorySwap, CodeRemap, Missing, Outlier, SignFlip, DigitTransposition, PeriodShift, Rounding,
                PlausibleSubstitution, InvalidCode, OrdinalShift)
}


def make_operation(name: str, **params: Any) -> Operation:
    return OPERATIONS[name](**params)
