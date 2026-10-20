"""``dqf scan``: analyse a new batch with the existing controls and configured learned detectors."""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from dq_framework import __version__, paths
from dq_framework.contracts import load_contract
from dq_framework.controls import alerts_to_cells, fit_reference_stats, run_controls
from dq_framework.datasets import get_spec, load_contract_table, load_raw_table
from dq_framework.detectors.base import BLOCKED, INCOMPATIBLE
from dq_framework.detectors.registry import make_detector
from dq_framework.pilot.splits import design_pool
from dq_framework.service.partitioning import grouped_partitions
from dq_framework.service.review import review_order

BATCH_ID = "batch"
FEEDBACK_VERDICTS = ("confirmed_error", "not_an_error", "unsure")


def _select(df: pd.DataFrame, spec: dict[str, Any], seed: int = 0, *, raw=None, contract=None) -> pd.Series:
    kind = spec.get("select", "periods")
    if kind == "periods":
        return df["_period"].isin(spec["periods"])
    if kind == "row_range":
        return df["_row_id"].between(spec["start"], spec["end"])
    if kind == "modulo":  # deterministic, non-temporal selection: _row_id mod m in values (e.g. a new extract)
        return (df["_row_id"] % int(spec["mod"])).isin(spec["values"])
    if kind == "sample":
        rng = np.random.default_rng(spec.get("seed", seed))
        m = np.zeros(len(df), dtype=bool)
        m[rng.choice(len(df), size=min(spec["n"], len(df)), replace=False)] = True
        return pd.Series(m, index=df.index)
    if kind == "group_split":
        parts = grouped_partitions(raw, df, contract, spec["group_columns"],
                                   spec.get("seed", 11), spec.get("history_fraction", 0.6))
        return df["_row_id"].isin(parts.loc[parts["partition"] == spec["partition"], "_row_id"])
    raise ValueError(f"unknown selection {kind}")


def _fmt(v: Any) -> str:
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def load_evidence(path: Path | None, dataset: str) -> pd.DataFrame:
    if path is None or not Path(path).exists():
        return pd.DataFrame()
    ev = pd.read_csv(path)
    return ev[ev["dataset"] == dataset]


def recommend(det_key: str, provides_scores: bool, evidence: pd.DataFrame, baseline: str, budget: float, scheme: str,
              burden_per_1k: float, shift_ratio: float, rule: dict[str, Any]) -> dict[str, Any]:
    """ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE for one detector on this source.

    Evidence = held-out utility of this detector in the offline pilot (mean and bootstrap CI over pilot
    replications) for the same dataset, baseline, budget and split scheme. ADOPT needs the lower bound >= min_gain,
    an observed extra-alert burden within the cap and no strong shift between this batch and the evaluation
    conditions; DO_NOT_ADOPT if the upper bound < min_gain or the burden cap is exceeded.
    """
    min_gain, cap, max_shift = rule.get("min_gain", 0.05), rule.get("max_extra_alerts_per_1k", 50.0), rule.get("max_shift_ratio", 3.0)
    reasons: list[str] = []
    e = evidence[(evidence["detector"] == det_key) & (evidence["baseline"] == baseline) & (evidence["budget"] == budget)
                 & (evidence["test_set"] == "test_heldout")] if len(evidence) else evidence
    if len(e) and "scheme" in e and (e["scheme"] == scheme).any():
        e = e[e["scheme"] == scheme]
    if not len(e):
        return {"detector": det_key, "recommendation": "INSUFFICIENT_EVIDENCE",
                "reasons": ["no offline evaluation evidence for this dataset / baseline / budget"]}
    r = e.iloc[0]
    reasons.append(f"offline held-out utility at {budget:g} reviews/1k rows: {r['utility']:.3f} "
                   f"[{r['utility_lo']:.3f}, {r['utility_hi']:.3f}] over {int(r['n_replications'])} pilot replications "
                   f"({'ranked' if provides_scores else 'budget-capped flags'}; scheme {r.get('scheme', '?')})")
    if not provides_scores:
        reasons.append(f"extra alerts on this batch beyond the existing controls: {burden_per_1k:.1f} per 1,000 rows (cap {cap:g})")
    if int(r["n_replications"]) < rule.get("min_replications", 3):
        reasons.append(f"only {int(r['n_replications'])} independent pilot replication(s): an interval over replications "
                       f"is not meaningful (ADOPT needs >= {rule.get('min_replications', 3)})")
    if shift_ratio > max_shift:
        reasons.append(f"this batch triggers {shift_ratio:.1f}x the existing controls' alert rate of the evaluation "
                       f"partitions: offline evidence may not transfer (shift)")
    if (not provides_scores and burden_per_1k > cap) or r["utility_hi"] < min_gain:
        rec = "DO_NOT_ADOPT"
    elif r["utility_lo"] >= min_gain and shift_ratio <= max_shift and int(r["n_replications"]) >= rule.get("min_replications", 3):
        rec = "ADOPT"
    else:
        rec = "INSUFFICIENT_EVIDENCE"
    return {"detector": det_key, "recommendation": rec, "reasons": reasons,
            "evidence": {k: (float(r[k]) if isinstance(r[k], (int, float, np.floating)) else r[k]) for k in r.index}}


def run_scan(config_path: str | Path, out_dir: Path | None = None) -> Path:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    t_start = time.perf_counter()
    ds = cfg["dataset"]
    contract = load_contract(cfg.get("contract", ds))
    df = load_contract_table(ds, contract)
    if cfg.get("exclude_research_holdout", True):
        df = df[design_pool(df, contract, int(cfg.get("holdout_seed", 1)))].reset_index(drop=True)
    raw = load_raw_table(get_spec(ds)) if any(cfg[k].get("select") == "group_split" for k in ("history", "batch")) else None
    hist = df[_select(df, cfg["history"], raw=raw, contract=contract)].reset_index(drop=True)
    batch = df[_select(df, cfg["batch"], raw=raw, contract=contract)].reset_index(drop=True)
    if set(hist["_row_id"]) & set(batch["_row_id"]):
        raise ValueError("history and batch overlap")
    if not len(hist) or not len(batch):
        raise ValueError("history and batch must both contain rows")
    out_dir = Path(out_dir or paths.RESULTS_DIR / "runs" / "scans" / f"{cfg.get('name', ds)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(batch)
    budget = float(cfg.get("budget_per_1k", 25))
    k = int(round(budget * n / 1000))

    # existing controls
    stats = fit_reference_stats(contract, hist)
    ctl = run_controls(contract, batch.assign(_scenario_id=BATCH_ID), stats, out_dir / "controls")
    a = ctl.alerts.copy()
    cells = alerts_to_cells(a)
    cells.to_parquet(out_dir / "control_cells.parquet", index=False)
    rule_cells = set(zip(cells["_row_id"].astype("int64"), cells["column"], strict=True))
    det_rule_cells = set(zip(cells.loc[cells["tier"] == "deterministic", "_row_id"].astype("int64"),
                             cells.loc[cells["tier"] == "deterministic", "column"], strict=True))
    base_set = rule_cells if cfg.get("baseline", "full") == "full" else det_rule_cells
    key_col = contract.row_id
    value_of = batch.set_index("_row_id")
    findings: list[dict[str, Any]] = []
    for _, r in a.iterrows():
        for col in str(r["implicated_columns"]).split(","):
            findings.append({"_row_id": int(r["_row_id"]), "record_key": _fmt(value_of.at[int(r["_row_id"]), key_col]) if key_col else "",
                             "column": col, "value": _fmt(value_of.at[int(r["_row_id"]), col]) if col in value_of else "",
                             "source": f"rule:{r['rule_id']}", "tier": r["tier"], "rule_status": r["rule_status"],
                             "score": np.nan, "explanation": f"observed {r['observed']}; expected {r['expected']}"})

    # learned detectors
    det_rows, rec_rows, score_frames = [], [], []
    # shift check: implicated baseline cells per 1,000 rows on this batch vs. on the untouched evaluation partitions
    stat_rate_batch = 1000 * len(rule_cells) / max(n, 1)
    evidence = load_evidence(Path(cfg["evidence"]) if cfg.get("evidence") else None, ds)
    ref_rate = cfg.get("evaluation_baseline_alerts_per_1k")
    rates_path = paths.RESULTS_DIR / "pilot" / "evaluation_alert_rates.csv"
    if ref_rate is None and rates_path.exists():
        rr = pd.read_csv(rates_path)
        rr = rr[(rr["dataset"] == ds) & (rr["scheme"] == cfg.get("evidence_scheme", "random")) & (rr["baseline"] == "full")
                & (rr["partition"] == "test")]
        ref_rate = float(rr["alerts_per_1k"].mean()) if len(rr) else None
    shift_ratio = stat_rate_batch / ref_rate if ref_rate else 1.0
    for key, spec in cfg["detectors"].items():
        params = dict(spec.get("params", {}))
        if spec["name"] == "dboost":
            params["explain"] = True
        det = make_detector({"name": spec["name"], "params": params})
        comp = det.check_compatibility(contract, hist)
        common = {"detector": key, "name": spec["name"], "granularity": det.granularity,
                  "fit_scope": det.fit_scope, "provides_scores": det.provides_scores,
                  "compatibility": comp.verdict, "compatibility_reasons": comp.reasons,
                  "transformations": comp.transformations, "config": params}
        if comp.verdict in (INCOMPATIBLE, BLOCKED):
            det_rows.append({**common, "status": "incompatible", "seconds": 0, "flags": 0,
                             "extra_flags_beyond_controls": 0, "extra_flags_per_1k": 0,
                             "findings_listed": 0, "warnings": comp.reasons})
            continue
        t0 = time.perf_counter()
        try:
            det.fit(hist, contract)
            out = det.score(batch.assign(_scenario_id=BATCH_ID))
            if out.status != "ok":
                raise RuntimeError(f"detector status {out.status}: {out.warnings}")
        except Exception as exc:
            if not cfg.get("continue_on_detector_error", False):
                raise
            det_rows.append({**common, "status": "failed", "seconds": round(time.perf_counter() - t0, 3),
                             "flags": 0, "extra_flags_beyond_controls": 0, "extra_flags_per_1k": 0,
                             "findings_listed": 0, "warnings": [f"{type(exc).__name__}: {exc}"]})
            continue
        secs = time.perf_counter() - t0
        s = out.scores
        if det.granularity == "row":
            s = s.assign(column="<record>")
        s = s.assign(_row_id=s["_row_id"].astype("int64"))
        in_base = pd.Series([(rid, c) in base_set for rid, c in zip(s["_row_id"], s["column"], strict=True)], index=s.index)
        selected = review_order(s[~in_base], ranked=det.provides_scores, seed=cfg.get("review_seed", 0)).head(k)
        selected_keys = set(zip(selected["_row_id"], selected["column"], strict=True))
        s["review_selected"] = [(rid, col) in selected_keys for rid, col in zip(s["_row_id"], s["column"], strict=True)]
        score_frames.append(s.assign(detector=key))
        selected = s.loc[selected.index].copy()
        if det.provides_scores and det.granularity == "cell":
            pick = selected
            pick = pd.concat([pick, s[s["flag"] & ~in_base & ~s.index.isin(pick.index)]])
            if hasattr(det, "explain_cells") and len(pick):
                pick = pick.assign(explanation=det.explain_cells(batch, pick).to_numpy())
        elif det.provides_scores:
            pick = s[s["flag"] | (s["score"].rank(ascending=False, method="first") <= k)]
            pick = pick.assign(explanation=f"{det.name}: record-level outlier score (reference threshold "
                               f"{getattr(det, 'threshold_', float('nan')):.4f})")
        else:
            pick = s[s["flag"] & ~in_base]
        extra = int((s["flag"] & ~in_base).sum())
        burden = 1000 * extra / n
        det_rows.append({**common, "status": "ok", "seconds": round(secs, 3),
                         "flags": int(s["flag"].sum()), "extra_flags_beyond_controls": extra,
                         "extra_flags_per_1k": round(burden, 1), "findings_listed": len(pick), "warnings": out.warnings,
                         "scored_cells": len(s), "finite_scores": int(np.isfinite(s["score"]).sum()),
                         "review_selected": len(selected), "metadata": out.meta()})
        for _, r in pick.iterrows():
            col = r["column"]
            explanation = r.get("explanation")
            if pd.isna(explanation) or not explanation:
                explanation = f"{det.name}: {'native flag' if r['flag'] else 'ranked review candidate, not a native flag'}"
            findings.append({"_row_id": int(r["_row_id"]),
                             "record_key": _fmt(value_of.at[int(r["_row_id"]), key_col]) if key_col else "",
                             "column": col, "value": _fmt(value_of.at[int(r["_row_id"]), col]) if col in value_of else "",
                             "source": f"detector:{key}", "tier": "learned" if det.supervision != "none" else "statistical-baseline",
                             "rule_status": "", "score": r["score"],
                             "review_selected": bool(r.get("review_selected", False)), "explanation": explanation})
        if det.granularity == "cell":
            rec_rows.append(recommend(key, det.provides_scores, evidence, cfg.get("baseline", "full"), budget,
                                      cfg.get("evidence_scheme", "random"), burden, shift_ratio, cfg.get("decision", {})))
    scores = pd.concat(score_frames, ignore_index=True) if score_frames else pd.DataFrame(
        columns=["_scenario_id", "_row_id", "column", "score", "flag", "review_selected", "detector"])
    scores.to_parquet(out_dir / "detector_scores.parquet", index=False)
    f = pd.DataFrame(findings, columns=["_row_id", "record_key", "column", "value", "source", "tier",
                                      "rule_status", "score", "review_selected", "explanation"])
    f.insert(0, "finding_id", [f"F{i:05d}" for i in range(1, len(f) + 1)])
    f.to_csv(out_dir / "findings.csv", index=False)
    fb = f[["finding_id", "_row_id", "record_key", "column", "value", "source"]].assign(verdict="", note="")
    if not (out_dir / "feedback.csv").exists():
        fb.to_csv(out_dir / "feedback.csv", index=False)
    summary = {
        "scan": cfg.get("name", ds), "dataset": ds, "framework_version": __version__,
        "run_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "elapsed_s": round(time.perf_counter() - t_start, 1),
        "history": {"rows": len(hist), **cfg["history"]}, "batch": {"rows": n, **cfg["batch"]},
        "excluded_research_holdout": bool(cfg.get("exclude_research_holdout", True)),
        "controls": {"dbt": ctl.dbt_version, "tests": ctl.tests["status"].value_counts().to_dict(),
                     "alerts": len(a), "alerts_by_tier": a["tier"].value_counts().to_dict(),
                     "baseline_alert_cells_per_1k_rows": round(stat_rate_batch, 1),
                     "evaluation_baseline_alert_cells_per_1k_rows": None if ref_rate is None else round(ref_rate, 1),
                     "shift_ratio": round(shift_ratio, 2)},
        "budget_per_1k": budget, "review_slots": k, "baseline": cfg.get("baseline", "full"),
        "detectors": det_rows, "recommendations": rec_rows,
        "findings": {"total": len(f), "by_source": f["source"].value_counts().to_dict()},
        "ingestion_missing_tokens": {c.name: c.missing_tokens for c in contract.columns if c.missing_tokens},
        "notes": ["This service reads dirty input only; findings are candidates, not verified errors.",
                  "Published references, when available, are evaluated separately after the scan.",
                  "Recommendations require source-specific offline evidence; no evidence is inferred from these findings."],
    }
    (out_dir / "scan_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out_dir / "scan_report.md").write_text(render_report(summary, f), encoding="utf-8")
    return out_dir


def render_report(s: dict[str, Any], f: pd.DataFrame, max_rows: int = 40) -> str:
    L = [f"# Data-quality scan: {s['scan']}", "",
         f"Dataset `{s['dataset']}` · history {s['history']['rows']:,} rows · new batch {s['batch']['rows']:,} rows · "
         f"run {s['run_utc']} · framework {s['framework_version']}", "",
         "> Findings are **review candidates**, not verified errors. The service has no access to a clean reference. "
         "Recommendations require source-specific offline evidence.", "",
         "## Existing controls", "",
         f"dbt tests: {s['controls']['tests']}; alerts: {s['controls']['alerts']} ({s['controls']['alerts_by_tier']}); "
         f"implicated cells {s['controls']['baseline_alert_cells_per_1k_rows']} per 1,000 rows "
         f"(untouched evaluation partitions of the pilot: {s['controls']['evaluation_baseline_alert_cells_per_1k_rows']}; "
         f"ratio {s['controls']['shift_ratio']}).", "",
         "## Learned and literature detectors", "",
         "| detector | status | level | learns on | scores | flags | extra beyond controls (per 1k rows) | listed | seconds |",
         "|---|---|---|---|---|---|---|---|---|"]
    for d in s["detectors"]:
        L.append(f"| {d['detector']} | {d.get('status', 'ok')} | {d['granularity']} | {d['fit_scope']} | {'yes' if d['provides_scores'] else 'no'} | "
                 f"{d['flags']} | {d['extra_flags_beyond_controls']} ({d['extra_flags_per_1k']}) | {d['findings_listed']} | {d['seconds']} |")
    for d in s["detectors"]:
        if d.get("status", "ok") != "ok":
            L.append(f"\n{d['detector']}: **{d['status']}** — " + "; ".join(d.get("warnings", [])) + "\n")
    L += ["", f"Review budget: {s['budget_per_1k']:g} extra cells per 1,000 rows = {s['review_slots']} cells for this batch; "
          "scored detectors list their top cells within that budget plus their own flags, binary detectors list their flags.", "",
          "## Recommendation per detector", ""]
    for r in s["recommendations"]:
        L.append(f"- **{r['detector']}: {r['recommendation']}** – " + "; ".join(r["reasons"]))
    L += ["", f"## Findings (first {max_rows} of {len(f)}; full list in findings.csv)", "",
          "| id | record | column | value | source | score | explanation |", "|---|---|---|---|---|---|---|"]
    order = f.assign(_o=f["source"].str.startswith("detector").astype(int)).sort_values(["_o", "source", "score"], ascending=[True, True, False])
    shown = pd.concat([order[order["_o"] == 0].head(max_rows // 2), order[order["_o"] == 1].groupby("source").head(max(1, max_rows // 8))])
    for _, r in shown.head(max_rows).iterrows():
        sc = "" if pd.isna(r["score"]) else f"{r['score']:.4f}"
        L.append(f"| {r['finding_id']} | {r['record_key'] or r['_row_id']} | {r['column']} | {r['value']} | {r['source']} | {sc} | "
                 f"{str(r['explanation'])[:140]} |")
    L += ["", "## Feedback", "", "Annotate `feedback.csv` (verdict: " + " / ".join(FEEDBACK_VERDICTS) +
          ") and run `dqf feedback <scan_dir>` for adjudicated precision per source.", ""]
    return "\n".join(L)


def summarise_feedback(scan_dir: Path) -> pd.DataFrame:
    fb = pd.read_csv(Path(scan_dir) / "feedback.csv", dtype=str, keep_default_na=False)
    bad = set(fb["verdict"]) - {"", *FEEDBACK_VERDICTS}
    if bad:
        raise ValueError(f"unknown verdicts {sorted(bad)}; use one of {FEEDBACK_VERDICTS}")
    g = fb.groupby("source")["verdict"]
    out = pd.DataFrame({"findings": g.size(), "annotated": g.apply(lambda v: int((v != "").sum())),
                        "confirmed": g.apply(lambda v: int((v == "confirmed_error").sum())),
                        "not_an_error": g.apply(lambda v: int((v == "not_an_error").sum())),
                        "unsure": g.apply(lambda v: int((v == "unsure").sum()))}).reset_index()
    decided = out["confirmed"] + out["not_an_error"]
    out["adjudicated_precision"] = np.where(decided > 0, out["confirmed"] / decided.replace(0, 1), np.nan)
    return out
