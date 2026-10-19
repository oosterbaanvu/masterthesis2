"""Controlled error injection: scenario specification, execution and an auditable error log.

A *scenario* = (target column, operation, mechanism, rate, seed). Injection works
on a copy of the batch under test; the original values and injected values of every
changed cell are logged. Only cells that actually changed count as injected errors
(the realised count can be lower than the intended count when an operation is a
no-op for a cell; this is recorded, never hidden).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from dq_framework.contracts import Contract
from dq_framework.injection.mechanisms import make_mechanism, mechanism_class
from dq_framework.injection.operations import OpContext, make_operation

LOG_COLUMNS = ["scenario_id", "_row_id", "column", "original", "injected", "operation", "mechanism"]


@dataclass(frozen=True)
class Scenario:
    dataset: str
    column: str
    operation: str
    mechanism: str
    rate: float
    seed: int
    op_params: dict[str, Any] = field(default_factory=dict)
    mech_params: dict[str, Any] = field(default_factory=dict)
    tag: str = ""

    @property
    def mechanism_class(self) -> str:
        return mechanism_class(self.mechanism)

    @property
    def scenario_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        h = hashlib.sha1(payload.encode()).hexdigest()[:10]
        return f"{self.column}.{self.operation}.{self.mechanism}.r{self.rate}.s{self.seed}.{h}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scenario_id"] = self.scenario_id
        d["mechanism_class"] = self.mechanism_class
        return d


@dataclass
class InjectionResult:
    scenario: Scenario
    corrupted: pd.DataFrame
    log: pd.DataFrame
    intended: int
    realised: int
    eligible: int
    n_rows: int
    notes: list[str]

    @property
    def summary(self) -> dict[str, Any]:
        return {
            **self.scenario.to_dict(),
            "n_rows": self.n_rows,
            "eligible_cells": self.eligible,
            "intended_errors": self.intended,
            "realised_errors": self.realised,
            "realised_rate": self.realised / self.n_rows if self.n_rows else 0.0,
            "notes": self.notes,
        }


def reference_domain(contract: Contract, reference: pd.DataFrame, column: str) -> list[Any]:
    """Valid categories for swaps: values observed in the reference partition (sorted)."""
    vals = reference[column].dropna().unique().tolist()
    try:
        return sorted(vals)
    except TypeError:
        return sorted(vals, key=str)


def inject(batch: pd.DataFrame, scenario: Scenario, contract: Contract, reference: pd.DataFrame) -> InjectionResult:
    """Apply one scenario to a copy of ``batch`` (which must not contain reference rows)."""
    if set(batch["_row_id"]) & set(reference["_row_id"]):
        raise ValueError("batch overlaps the reference partition (leakage)")
    col = scenario.column
    ctype = contract.column(col).type
    op = make_operation(scenario.operation, **scenario.op_params)
    if ctype not in op.column_types:
        raise ValueError(f"operation {op.name} does not apply to {ctype} column {col}")
    ctx = OpContext(
        column_type=ctype,
        reference_values=reference[col],
        batch=batch,
        domain=reference_domain(contract, reference, col) if ctype == "categorical" else [],
    )
    s = batch[col]
    elig = op.eligible(s, ctx).fillna(False).astype(bool)
    n = int(round(scenario.rate * len(batch)))
    notes: list[str] = []
    mech = make_mechanism(scenario.mechanism, **scenario.mech_params)
    rows = mech.select(batch, col, elig, n, seed=scenario.seed)
    new_vals = op.apply(s, rows, ctx, seed=scenario.seed + 7919)
    old = s.loc[rows]
    changed = ~_equal(old, new_vals)
    if (~changed).any():
        notes.append(f"{int((~changed).sum())} selected cells unchanged by the operation (not counted)")
    rows_changed = rows[changed.to_numpy()]
    out = batch.copy()
    if ctype == "numeric":
        out[col] = out[col].astype("float64")
        out.loc[rows_changed, col] = pd.to_numeric(new_vals.loc[rows_changed]).astype("float64")
    else:
        target_dtype = out[col].dtype
        tmp = out[col].astype(object)
        tmp.loc[rows_changed] = new_vals.loc[rows_changed].astype(object)
        try:
            out[col] = tmp.astype(target_dtype)
        except (TypeError, ValueError):
            out[col] = tmp  # e.g. an invalid string code in an integer column
            notes.append("column dtype widened to object to hold injected value")
    log = pd.DataFrame(
        {
            "scenario_id": scenario.scenario_id,
            "_row_id": batch.loc[rows_changed, "_row_id"].to_numpy(),
            "column": col,
            "original": old.loc[rows_changed].astype(object).to_numpy(),
            "injected": new_vals.loc[rows_changed].astype(object).to_numpy(),
            "operation": scenario.operation,
            "mechanism": scenario.mechanism,
        },
        columns=LOG_COLUMNS,
    )
    return InjectionResult(
        scenario=scenario,
        corrupted=out,
        log=log,
        intended=n,
        realised=int(changed.sum()),
        eligible=int(elig.sum()),
        n_rows=len(batch),
        notes=notes,
    )


def _equal(a: pd.Series, b: pd.Series) -> pd.Series:
    av, bv = a.astype(object).to_numpy(), b.astype(object).to_numpy()
    out = np.zeros(len(av), dtype=bool)
    for i, (x, y) in enumerate(zip(av, bv, strict=True)):
        if pd.isna(x) and pd.isna(y):
            out[i] = True
        elif pd.isna(x) or pd.isna(y):
            out[i] = False
        else:
            try:
                out[i] = float(x) == float(y)
            except (TypeError, ValueError):
                out[i] = x == y
    return pd.Series(out, index=a.index)
