"""Human-readable, auditable evaluation report (Markdown) for one pipeline run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dq_framework.evaluation import DecisionRule, bootstrap_ci

UNTOUCHED = "untouched"


def _fmt(x: Any, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    if isinstance(x, float | np.floating):
        return f"{x:.{nd}f}"
    return str(x)


def _table(df: pd.DataFrame, nd: int = 3) -> str:
    if df.empty:
        return "_(none)_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(_fmt(r[c], nd) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def render(run: dict[str, Any], rule: DecisionRule | None = None, title: str | None = None) -> str:
    man = run["manifest"]
    row_level = man["detector"].get("granularity") == "row"
    if rule is None:
        rule = (DecisionRule(metric="row_incremental_recall_at_10_per_1k") if row_level else DecisionRule())
    burden_col = "row_extra_alerts_untouched_per_1k" if row_level else "extra_alerts_untouched_per_1k"
    m: pd.DataFrame = run["metrics"]
    sc = m[m["scenario_id"] != UNTOUCHED].copy()
    unt = m[m["scenario_id"] == UNTOUCHED].iloc[0]
    det = man["detector"]
    out = []
    out.append(f"# {title or 'Data-quality control evaluation'}: `{man['dataset']}`\n")
    out.append(
        "> Exploratory evidence from controlled, synthetic error injection on public data. "
        "It shows which *injected* errors the configured controls catch; it does not estimate real error rates "
        "and alerts on untouched cells are not verified false positives.\n"
    )
    out.append("## Run\n")
    s = man["split"]
    out.append(
        f"- Run id `{man['run_id']}`, framework {man['framework_version']}, started {man['started_utc']}, "
        f"{man['elapsed_s']} s.\n"
        f"- Split: {s['scheme']} (seed {s['seed']}); reference {s['n_reference']} rows; evaluated partition "
        f"`{s['partition']}` with {s['n_evaluated_rows']} rows per scenario; {man['n_scenarios']} scenarios + 1 untouched copy.\n"
        f"- Conventional controls: dbt Core ({man['dbt']['version']}), {man['contract']['rules_active_deterministic']} "
        f"deterministic and {man['contract']['rules_active_statistical']} statistical rule definitions; dbt test statuses "
        f"{man['dbt']['tests']} (warn = failing rows found). Recorded but not enforced: "
        f"{', '.join(man['contract']['rules_recorded_not_enforced']) or 'none'}.\n"
        f"- Learned detector: `{det.get('detector', '?')}` ({det.get('compatibility', {}).get('verdict')}), "
        f"config {json.dumps(det.get('config', {}))}, fit {det.get('fit_seconds')} s, score {det.get('score_seconds')} s.\n"
    )
    for lim in det.get("limitations", []):
        out.append(f"  - limitation: {lim}\n")
    out.append("\n## Alert burden on the untouched partition\n")
    out.append(
        f"Baseline controls implicate {_fmt(unt.get('baseline_alert_cells_untouched_per_1k'), 1)} cells per 1,000 rows; "
        f"the learned detector flags {_fmt(unt.get('L_alerts_untouched_per_1k'), 1)} cells per 1,000 rows "
        f"({_fmt(unt.get('extra_alerts_untouched_per_1k'), 1)} not already implicated by the baseline).\n\n"
    )
    br = run["burden_rules"].head(10)[["rule_id", "tier", "rule_status", "alerts", "alerts_per_1k_rows"]]
    out.append("Top rules by alerts on untouched data:\n\n" + _table(br, 2))
    if run.get("burden_detector") is not None:
        bd = run["burden_detector"].head(8)
        out.append("\nDetector flags on untouched data (top columns):\n\n" + _table(bd, 4))
    if row_level:
        out.append(
            f"\nRecord level: the learned detector flags {_fmt(unt.get('row_extra_alerts_untouched_per_1k'), 1)} untouched "
            "records per 1,000 rows that the baseline does not already alert.\n"
        )
    out.append("\n## Detection of injected errors\n")
    out.append(
        "Recall is the share of injected cells implicated by a control (`det` = deterministic rules only, "
        "`B` = deterministic + statistical, `L` = learned detector at its own threshold). "
        "`ΔR@k` is the share of injected cells found by the k highest-ranked learned-detector cells per 1,000 rows "
        "that the baseline did not already implicate (fixed extra review capacity).\n\n"
    )
    keep = ["column", "operation", "mechanism", "tag", "recall_det", "recall_B", "recall_L", "incremental_recall",
            "incremental_recall_at_5_per_1k", "incremental_recall_at_10_per_1k", "auc_L_target"]
    keep = [k for k in keep if k in sc]
    if row_level:
        keep = ["column", "operation", "mechanism", "tag", "recall_det", "recall_B", "row_recall_B", "row_recall_L",
                "row_incremental_recall", "row_incremental_recall_at_5_per_1k", "row_incremental_recall_at_10_per_1k"]
        keep = [k for k in keep if k in sc]
    agg = sc.groupby(["column", "operation", "mechanism", "tag"])[keep[4:]].mean().reset_index()
    agg = agg.rename(columns={"incremental_recall": "ΔR(flag)", "incremental_recall_at_5_per_1k": "ΔR@5",
                              "incremental_recall_at_10_per_1k": "ΔR@10", "auc_L_target": "AUC_L",
                              "row_recall_B": "rowR_B", "row_recall_L": "rowR_L", "row_incremental_recall": "rowΔR(flag)",
                              "row_incremental_recall_at_5_per_1k": "rowΔR@5", "row_incremental_recall_at_10_per_1k": "rowΔR@10"})
    if row_level:
        out.append("Row-level detector: cell-level columns refer to the baseline only; `rowR`/`rowΔR` are record-level "
                   "(a record counts as found when any control alerts any of its cells).\n\n")
    out.append(_table(agg))
    out.append("\n### By mechanism class (mean over operations, columns and seeds)\n\n")
    bym = sc.groupby("mechanism_class")[[c for c in ["recall_B", "row_recall_B", "incremental_recall_at_10_per_1k",
                                                     "row_incremental_recall_at_10_per_1k", "auc_L_target"] if c in sc]].mean().reset_index()
    out.append(_table(bym))
    out.append("\n## Adoption indication under the pre-registered rule\n")
    out.append(
        f"Rule: ADOPT if the lower 95% bootstrap bound of `{rule.metric}` ≥ {rule.min_gain} and the extra alert burden "
        f"≤ {rule.max_extra_alerts_per_1k} per 1,000 rows; DO_NOT_ADOPT if the upper bound < {rule.min_gain} or the burden "
        f"is exceeded; otherwise INSUFFICIENT_EVIDENCE. Computed per error case over seeds and mechanisms "
        f"(n is small in a demonstration run; this is an indication, not a confirmatory result).\n\n"
    )
    rows = []
    prim = sc[sc["tag"] == "primary"]
    for (col, op), g in prim.groupby(["column", "operation"]):
        d = rule.decide(g[rule.metric].to_numpy(), g[burden_col].to_numpy() if burden_col in g else np.array([]))
        rows.append({"column": col, "operation": op, "n": d["n"], f"{rule.metric} mean": d["gain_mean"],
                     "CI low": d["gain_ci"][0], "CI high": d["gain_ci"][1], "decision": d["decision"]})
    out.append(_table(pd.DataFrame(rows)))
    if len(prim):
        mean, lo, hi = bootstrap_ci(prim[rule.metric].to_numpy())
        out.append(f"\nPooled over primary cases: {rule.metric} = {_fmt(mean)} [{_fmt(lo)}, {_fmt(hi)}] (scenario-level bootstrap; "
                   "scenarios share rows, so this interval is optimistic).\n")
    out.append("\n## Caveats\n")
    out.append(
        "- Injected errors are synthetic; detection of these errors is not evidence about real error prevalence.\n"
        "- Multi-column rules implicate all referenced cells; their cell-level precision is bounded by design.\n"
        "- The reference partition is assumed clean; source anomalies in it are not adjudicated.\n"
        "- Decisions here are not confirmatory: settings were not frozen and the number of seeds is small.\n"
    )
    return "".join(out)


def write(run: dict[str, Any], path: Path, **kw: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(run, **kw), encoding="utf-8")
    return path
