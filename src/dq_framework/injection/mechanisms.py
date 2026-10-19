"""Error *mechanisms*: where errors occur (which eligible cells are selected).

Definitions follow the missing-data analogy used for tabular errors
(ECAR / EAR / ENAR, cf. Jung et al. and the tab_err framework):

* ECAR  - selection independent of all data values.
* EAR   - selection depends on an *observed other* attribute of the row.
* ENAR  - selection depends on the (unobserved, original) value of the cell itself.

Two families are provided and must not be silently mixed:

``tab_err_*``  delegates to tab_err 0.2.1. Its EAR/ENAR select one *contiguous
               window* of the sorted conditioning values at a uniformly random
               start position. Dependence is therefore maximal ("hard window") and
               *which* value region is hit varies with the seed.

``soft_*``     (custom) samples without replacement with probability proportional
               to ``exp(strength * z)``, ``z`` the centred rank of the conditioning
               value (numeric) or a 0/1 segment indicator (categorical). ``strength``
               = 0 reproduces ECAR; the direction and dose of the dependence are explicit
               design parameters instead of seed noise.

Both satisfy the qualitative definitions; they differ in the *shape* and
*strength* of the dependence, which is itself an experimental factor.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
import pandas as pd


class Mechanism(ABC):
    name: ClassVar[str]
    family: ClassVar[str]
    needs_condition: ClassVar[bool] = False

    def __init__(self, **params: Any) -> None:
        self.params = params

    def describe(self) -> dict[str, Any]:
        return {"mechanism": self.name, "family": self.family, "params": self.params}

    def conditioning_column(self, target: str) -> str | None:
        if self.name.endswith("ear"):
            return self.params["condition_column"]
        if self.name.endswith("enar"):
            return target
        return None

    @abstractmethod
    def select(self, batch: pd.DataFrame, target: str, eligible: pd.Series, n: int, seed: int) -> pd.Index:
        """Return the index labels of ``n`` selected eligible rows."""


def _check_n(eligible: pd.Series, n: int) -> pd.Index:
    idx = eligible[eligible].index
    if n > len(idx):
        raise ValueError(f"need {n} eligible cells but only {len(idx)} are eligible")
    return idx


# --------------------------------------------------------------------------- tab_err family


class _TabErrMechanism(Mechanism):
    family = "tab_err"
    te_class: ClassVar[str]

    def select(self, batch, target, eligible, n, seed):
        import tab_err.error_mechanism as tem

        idx = _check_n(eligible, n)
        if n == 0:
            return pd.Index([])
        sub = batch.loc[idx].copy()
        cond = self.params.get("condition_column")
        # tab_err sorts the conditioning values; categorical codes are sorted by their value.
        rate = min(1.0, (n + 0.5) / len(sub))  # int(len * rate) == n
        kw: dict[str, Any] = {"seed": int(seed)}
        if cond is not None:
            kw["condition_to_column"] = cond
        mech = getattr(tem, self.te_class)(**kw)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mask = mech.sample(sub, target, rate)
        sel = mask.index[mask[target].to_numpy()]
        if len(sel) != n:
            raise RuntimeError(f"tab_err {self.te_class} selected {len(sel)} instead of {n}")
        return pd.Index(sel)


class TabErrECAR(_TabErrMechanism):
    name = "tab_err_ecar"
    te_class = "ECAR"


class TabErrEAR(_TabErrMechanism):
    name = "tab_err_ear"
    te_class = "EAR"
    needs_condition = True


class TabErrENAR(_TabErrMechanism):
    name = "tab_err_enar"
    te_class = "ENAR"


# --------------------------------------------------------------------------- soft (dose-controlled) family


def _centred_rank(x: pd.Series) -> np.ndarray:
    r = x.rank(method="average").to_numpy(dtype=float)
    return (r - 0.5) / len(r) - 0.5  # in (-0.5, 0.5)


def _weighted_sample(idx: pd.Index, logits: np.ndarray, n: int, seed: int) -> pd.Index:
    rng = np.random.default_rng(seed)
    w = np.exp(logits - logits.max())
    p = w / w.sum()
    pos = rng.choice(len(idx), size=n, replace=False, p=p)
    return idx[np.sort(pos)]


class SoftECAR(Mechanism):
    name = "soft_ecar"
    family = "soft"

    def select(self, batch, target, eligible, n, seed):
        idx = _check_n(eligible, n)
        return _weighted_sample(idx, np.zeros(len(idx)), n, seed)


class _SoftConditional(Mechanism):
    family = "soft"

    def _logits(self, values: pd.Series) -> np.ndarray:
        strength = float(self.params.get("strength", 4.0))
        if "segment_values" in self.params:  # categorical conditioning: segment indicator
            seg = values.astype(object).isin(self.params["segment_values"]).to_numpy(dtype=float)
            return strength * seg
        direction = self.params.get("direction", "high")
        z = _centred_rank(values.astype("float64"))
        return strength * (z if direction == "high" else -z)

    def _values(self, batch, target, idx):
        raise NotImplementedError

    def select(self, batch, target, eligible, n, seed):
        idx = _check_n(eligible, n)
        return _weighted_sample(idx, self._logits(self._values(batch, target, idx)), n, seed)


class SoftEAR(_SoftConditional):
    name = "soft_ear"
    needs_condition = True

    def _values(self, batch, target, idx):
        return batch.loc[idx, self.params["condition_column"]]


class SoftENAR(_SoftConditional):
    name = "soft_enar"

    def _values(self, batch, target, idx):
        return batch.loc[idx, target]


MECHANISMS: dict[str, type[Mechanism]] = {
    cls.name: cls for cls in (TabErrECAR, TabErrEAR, TabErrENAR, SoftECAR, SoftEAR, SoftENAR)
}


def make_mechanism(name: str, **params: Any) -> Mechanism:
    cls = MECHANISMS[name]
    if cls.needs_condition and "condition_column" not in params:
        raise ValueError(f"{name} requires a justified condition_column")
    return cls(**params)


def mechanism_class(name: str) -> str:
    """Map a mechanism name to its error-model class: ECAR, EAR or ENAR."""
    return name.split("_")[-1].upper()
