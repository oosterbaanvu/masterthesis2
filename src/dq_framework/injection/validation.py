"""Validation of one injected scenario (used by tests and by scripts/validate_injection.py).

Checks
------
real_change        every logged cell differs from its original value; realised vs intended count
no_side_effects    the corrupted copy differs from the original only in logged cells
reproducible       re-running with the same seed yields an identical log
seed_sensitive     a different seed selects different cells (unless the selection is forced)
semantics          operation-specific property holds (e.g. injected = factor * original)
placement          dependence of the selection on (a) the conditioning column, (b) the cell's own
                   value, and (c) a column unrelated to the mechanism, measured with a two-sample
                   Kolmogorov-Smirnov statistic (numeric) or Cramér's V (categorical) between
                   selected and eligible-but-unselected cells
triviality         share of injected values outside the reference range / reference domain
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from dq_framework.contracts import Contract
from dq_framework.injection import InjectionResult, Scenario, inject
from dq_framework.injection.operations import OpContext, make_operation


def _dependence(values: pd.Series, selected: pd.Series, is_cat: bool) -> dict[str, float]:
    v = values[values.notna()]
    sel = selected.loc[v.index]
    if sel.sum() == 0 or (~sel).sum() == 0:
        return {"stat": np.nan, "p": np.nan}
    if is_cat:
        tab = pd.crosstab(v.astype(str), sel)
        if tab.shape[0] < 2:
            return {"stat": 0.0, "p": 1.0}
        chi2, p, _, _ = stats.chi2_contingency(tab)
        n = tab.to_numpy().sum()
        return {"stat": float(np.sqrt(chi2 / (n * (min(tab.shape) - 1)))), "p": float(p), "measure": "cramers_v"}
    ks = stats.ks_2samp(v[sel].astype(float), v[~sel].astype(float))
    return {"stat": float(ks.statistic), "p": float(ks.pvalue), "measure": "ks"}


def validate(
    batch: pd.DataFrame,
    scenario: Scenario,
    contract: Contract,
    reference: pd.DataFrame,
    control_column: str | None = None,
) -> dict[str, Any]:
    res: InjectionResult = inject(batch, scenario, contract, reference)
    col = scenario.column
    out: dict[str, Any] = {"scenario": scenario.to_dict(), **res.summary}
    log = res.log
    # real change
    out["real_change_all"] = bool(len(log) == res.realised and res.realised > 0)
    out["realised_fraction_of_intended"] = res.realised / res.intended if res.intended else np.nan
    # side effects
    orig = batch.set_index("_row_id")
    corr = res.corrupted.set_index("_row_id")
    changed_cells = 0
    for c in contract.column_names:
        a, b = orig[c].astype(object), corr[c].astype(object)
        diff = ~((a == b) | (a.isna() & b.isna()))
        changed_cells += int(diff.sum())
    out["no_side_effects"] = bool(changed_cells == len(log))
    # reproducibility
    res2 = inject(batch, scenario, contract, reference)
    out["reproducible"] = bool(res2.log.reset_index(drop=True).equals(log.reset_index(drop=True)))
    sc_other = Scenario(**{**{k: v for k, v in scenario.to_dict().items() if k in Scenario.__dataclass_fields__},
                           "seed": scenario.seed + 1})
    res3 = inject(batch, sc_other, contract, reference)
    out["seed_sensitive"] = bool(set(res3.log["_row_id"]) != set(log["_row_id"]))
    # semantics
    o = pd.to_numeric(log["original"], errors="coerce")
    n = pd.to_numeric(log["injected"], errors="coerce")
    op = scenario.operation
    if op == "scale":
        f = float(scenario.op_params.get("factor", 10))
        sem = bool(np.allclose(n, o * f))
    elif op == "sign_flip":
        sem = bool(np.allclose(n, -o))
    elif op in ("category_swap", "code_remap"):
        dom = set(map(str, reference[col].dropna().unique()))
        sem = bool(log["injected"].map(str).isin(dom).all() and (log["injected"].map(str) != log["original"].map(str)).all())
    elif op == "digit_transposition":
        sem = bool(all(sorted(str(int(abs(a)))) == sorted(str(int(abs(b)))) for a, b in zip(o, n, strict=True)))
    elif op == "rounding":
        unit = float(scenario.op_params.get("unit", 1000))
        sem = bool(np.allclose(n % unit, 0) & np.all(np.abs(n - o) <= unit / 2 + 1e-9))
    elif op == "plausible_substitution" and contract.column(col).type == "numeric":
        r = reference[col]
        sem = bool(((n >= r.min()) & (n <= r.max())).all())
    elif op == "period_shift":
        src = orig.loc[log["_row_id"], scenario.op_params["source_column"]].astype(object).to_numpy()
        sem = bool(all(str(a) == str(b) for a, b in zip(src, log["injected"].astype(object), strict=True)))
    elif op == "missing":
        sem = bool(log["injected"].isna().all())
    else:
        sem = True
    out["semantics_ok"] = sem
    # placement
    opx = make_operation(op, **scenario.op_params)
    ctx = OpContext(contract.column(col).type, reference[col], batch,
                    sorted(reference[col].dropna().unique().tolist(), key=str))
    elig = opx.eligible(batch[col], ctx).fillna(False).astype(bool)
    selected = pd.Series(False, index=batch.index)
    sel_rows = batch.index[batch["_row_id"].isin(set(log["_row_id"]))]
    selected.loc[sel_rows] = True
    e_idx = elig[elig].index
    placement = {}
    cond = scenario.mech_params.get("condition_column")
    candidates = {"own": col}
    if cond:
        candidates["cond"] = cond
    if control_column:
        candidates["control"] = control_column
    for label, c in candidates.items():
        is_cat = contract.column(c).type == "categorical" if c in contract.column_names else False
        placement[label] = {"column": c, **_dependence(batch.loc[e_idx, c], selected.loc[e_idx], is_cat)}
    out["placement"] = placement
    # triviality
    if contract.column(col).type == "numeric":
        r = reference[col]
        out["share_outside_reference_range"] = float(((n < r.min()) | (n > r.max())).mean()) if len(n) else np.nan
        lo, hi = r.quantile(0.0005), r.quantile(0.9995)
        out["share_outside_reference_envelope"] = float(((n < lo) | (n > hi)).mean()) if len(n) else np.nan
    else:
        dom = set(map(str, reference[col].dropna().unique()))
        out["share_outside_reference_domain"] = float((~log["injected"].map(str).isin(dom)).mean()) if len(log) else np.nan
    return out
