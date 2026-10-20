"""End-to-end evaluation run: controls (dbt) + controlled errors + learned detector -> evidence.

One run = one dataset, one split seed, one evaluation partition (dev or test), a list
of scenarios and one learned detector configuration. All scenarios are stacked into a
single batch (distinguished by ``_scenario_id``) so dbt is invoked once per run.
An ``untouched`` copy of the partition is always included to measure alert burden.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from dq_framework import __version__, paths
from dq_framework.contracts import Contract, load_contract
from dq_framework.controls import alerts_to_cells, fit_reference_stats, run_controls
from dq_framework.datasets import load_contract_table, make_split
from dq_framework.detectors.base import Detector
from dq_framework.detectors.cdc import ConformalDataCleaningHGB
from dq_framework.evaluation import evaluate_rows, evaluate_scenario
from dq_framework.injection import Scenario, inject
from dq_framework.injection.catalog import expand, load_catalog

UNTOUCHED = "untouched"


@dataclass
class RunConfig:
    dataset: str
    split_seed: int = 1
    split_scheme: str = "random"
    partition: str = "dev"
    scenarios: list[Scenario] = field(default_factory=list)
    detector: dict[str, Any] = field(default_factory=lambda: {"name": "cdc_hgb", "params": {}})
    budgets_per_1k: tuple[float, ...] = (5.0, 10.0, 25.0)
    max_rows: int | None = None  # optional subsample of the evaluation partition (engineering demos)
    run_name: str = "run"

    @classmethod
    def from_yaml(cls, path: str | Path) -> RunConfig:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        ds = doc["dataset"]
        contract = load_contract(ds)
        sel = doc.get("scenarios", {})
        cat = load_catalog()
        scs = expand(ds, contract, cat, seeds=sel.get("seeds"), roles=tuple(sel.get("roles", ["primary", "sanity"])),
                     mechanisms=sel.get("mechanisms"))
        if sel.get("columns"):
            scs = [s for s in scs if s.column in sel["columns"]]
        if sel.get("operations"):
            scs = [s for s in scs if s.operation in sel["operations"]]
        if sel.get("rate") is not None:
            scs = [replace(s, rate=float(sel["rate"])) for s in scs]
        return cls(
            dataset=ds,
            split_seed=doc.get("split_seed", 1),
            split_scheme=doc.get("split_scheme", "random"),
            partition=doc.get("partition", "dev"),
            scenarios=scs,
            detector=doc.get("detector", {"name": "cdc_hgb", "params": {}}),
            budgets_per_1k=tuple(doc.get("budgets_per_1k", [5, 10, 25])),
            max_rows=doc.get("max_rows"),
            run_name=doc.get("name", Path(path).stem),
        )


def make_detector(spec: dict[str, Any]) -> Detector:
    name = spec["name"]
    params = spec.get("params", {}) or {}
    if name == "cdc_hgb":
        return ConformalDataCleaningHGB(**params)
    if name == "iforest_row":
        from dq_framework.detectors.iforest import IsolationForestRow

        return IsolationForestRow(**params)
    if name == "cdc_original":
        from dq_framework.detectors.subprocess_adapter import OriginalCDC

        return OriginalCDC(**params)
    raise ValueError(f"unknown detector {name}")


def run(cfg: RunConfig, out_root: Path | None = None) -> dict[str, Any]:
    t_start = time.perf_counter()
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    contract: Contract = load_contract(cfg.dataset)
    df = load_contract_table(cfg.dataset, contract)
    part = make_split(df, contract, seed=cfg.split_seed, scheme=cfg.split_scheme)
    ref = df[part == "reference"].reset_index(drop=True)
    evald = df[part == cfg.partition].reset_index(drop=True)
    if cfg.max_rows and len(evald) > cfg.max_rows:
        evald = evald.sample(cfg.max_rows, random_state=cfg.split_seed).reset_index(drop=True)
    run_id = f"{cfg.run_name}-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%S')}"
    out_dir = (out_root or paths.RESULTS_DIR / "runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. controlled errors on copies of the evaluation partition
    batches = [evald.assign(_scenario_id=UNTOUCHED)]
    logs, inj_summ = [], []
    for sc in cfg.scenarios:
        r = inject(evald, sc, contract, ref)
        batches.append(r.corrupted.assign(_scenario_id=sc.scenario_id))
        logs.append(r.log)
        inj_summ.append(r.summary)
    batch = pd.concat(batches, ignore_index=True)
    log = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame(columns=["scenario_id", "_row_id", "column"])

    # 2. conventional controls (fitted on reference, executed by dbt on the whole stacked batch)
    stats = fit_reference_stats(contract, ref)
    ctl = run_controls(contract, batch, stats, out_dir / "controls")
    cells = alerts_to_cells(ctl.alerts)

    # 3. learned detector (fitted on reference only), scored in chunks of scenarios to bound memory
    det = make_detector(cfg.detector)
    compat = det.check_compatibility(contract, ref)
    det_meta: dict[str, Any] = {"compatibility": compat.__dict__}
    usable = compat.verdict in ("PASS", "CONDITIONAL")
    if usable:
        det.fit(ref, contract)
    else:
        det_meta["status"] = "incompatible"

    # 4. evaluation per scenario
    n_rows, n_cols = len(evald), len(contract.column_names)
    k_max = int(round(max(cfg.budgets_per_1k) * n_rows / 1000))
    sid_of = [UNTOUCHED] + [sc.scenario_id for sc in cfg.scenarios]
    sc_of = {sc.scenario_id: sc for sc in cfg.scenarios}
    rows, kept_scores, score_s, n_scored, n_flagged = [], [], 0.0, 0, 0
    chunk = max(1, int(cfg.detector.get("chunk_scenarios", 8)))
    for i in range(0, len(sid_of), chunk):
        sids = sid_of[i:i + chunk]
        sub = batch[batch["_scenario_id"].isin(sids)]
        scores = None
        if usable:
            dout = det.score(sub)
            score_s += dout.score_seconds
            if dout.status == "ok":
                scores = dout.scores
                n_scored += len(scores)
                n_flagged += int(scores["flag"].sum())
            det_meta.update({k: v for k, v in dout.meta().items() if k not in ("n_scored", "n_flagged", "score_seconds")})
        for sid in sids:
            sc = sc_of.get(sid)
            lg = log[log["scenario_id"] == sid] if sc is not None else log.iloc[0:0]
            bc = cells[cells["_scenario_id"] == sid]
            ds_ = scores[scores["_scenario_id"] == sid] if scores is not None else None
            if det.granularity == "cell":
                ev_metrics = evaluate_scenario(lg, bc, ds_, n_rows, n_cols, target_column=None if sc is None else sc.column,
                                               budgets_per_1k=cfg.budgets_per_1k).metrics
            else:  # row-level detector: cell-level metrics are not defined; baseline-only cell metrics are kept
                ev_metrics = evaluate_scenario(lg, bc, None, n_rows, n_cols, budgets_per_1k=cfg.budgets_per_1k).metrics
            ev_metrics.update(evaluate_rows(lg, bc, ds_, n_rows, budgets_per_1k=cfg.budgets_per_1k))
            meta = {"scenario_id": sid}
            if sc is not None:
                meta.update({k: v for k, v in sc.to_dict().items() if k != "scenario_id"})
                meta["op_params"] = json.dumps(sc.op_params)
                meta["mech_params"] = json.dumps(sc.mech_params)
            rows.append({**meta, **ev_metrics})
            if ds_ is not None:
                # keep only what reports need: flags, the top-k_max cells, and the target column
                d = ds_.copy()
                d["rank"] = d["score"].rank(ascending=False, method="first")
                keep = d["flag"] | (d["rank"] <= k_max) | (sid == UNTOUCHED)
                if sc is not None and det.granularity == "cell":
                    keep |= d["column"] == sc.column
                kept_scores.append(d[keep].drop(columns="rank"))
    det_meta.update({"score_seconds": round(score_s, 3), "n_scored": n_scored, "n_flagged": n_flagged})
    res = pd.DataFrame(rows)
    scores = pd.concat(kept_scores, ignore_index=True) if kept_scores else None

    # untouched-batch alert burden per rule and per detector column
    unt_alerts = ctl.alerts[ctl.alerts["_scenario_id"] == UNTOUCHED]
    burden_rules = (unt_alerts.groupby(["rule_id", "tier", "rule_status"]).size().rename("alerts")
                    .reset_index().sort_values("alerts", ascending=False))
    burden_rules["alerts_per_1k_rows"] = 1000 * burden_rules["alerts"] / n_rows
    burden_det = None
    if scores is not None:
        u = scores[scores["_scenario_id"] == UNTOUCHED].assign(column=lambda x: x["column"].fillna("<row>"))
        burden_det = (u.groupby("column")["flag"].agg(["sum", "mean"]).rename(columns={"sum": "flags", "mean": "flag_rate"})
                      .reset_index().sort_values("flags", ascending=False))

    # 5. persist (large artefacts stay under results/runs, which is git-ignored)
    res.to_csv(out_dir / "scenario_metrics.csv", index=False)
    # original/injected values are stored as text: scenarios mix numeric and categorical columns
    log_out = log.copy()
    for c in ("original", "injected"):
        log_out[c] = log_out[c].map(lambda v: None if pd.isna(v) else str(v))
    log_out.to_parquet(out_dir / "injection_log.parquet", index=False)
    ctl.alerts.to_parquet(out_dir / "control_alerts.parquet", index=False)
    ctl.tests.to_csv(out_dir / "dbt_tests.csv", index=False)
    burden_rules.to_csv(out_dir / "untouched_rule_burden.csv", index=False)
    if burden_det is not None:
        burden_det.to_csv(out_dir / "untouched_detector_burden.csv", index=False)
    if scores is not None:
        scores.to_parquet(out_dir / "detector_scores.parquet", index=False)
    manifest = {
        "run_id": run_id,
        "framework_version": __version__,
        "started_utc": started,
        "elapsed_s": round(time.perf_counter() - t_start, 1),
        "dataset": cfg.dataset,
        "split": {"seed": cfg.split_seed, "scheme": cfg.split_scheme, "partition": cfg.partition,
                  "n_reference": len(ref), "n_evaluated_rows": n_rows},
        "contract": {"rules_active_deterministic": len(contract.active_rules(("deterministic",))),
                     "rules_active_statistical": len(contract.active_rules(("statistical",))),
                     "rules_recorded_not_enforced": [r.id for r in contract.rules if not r.active]},
        "dbt": {"version": ctl.dbt_version, "elapsed_s": round(ctl.elapsed_s, 1),
                "tests": ctl.tests["status"].value_counts().to_dict(), "returncode": ctl.meta.get("returncode")},
        "detector": det_meta,
        "n_scenarios": len(cfg.scenarios),
        "injection": inj_summ,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return {"out_dir": out_dir, "metrics": res, "manifest": manifest, "burden_rules": burden_rules,
            "burden_detector": burden_det, "contract": contract}


def summarise(metrics: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    m = metrics[metrics["scenario_id"] != UNTOUCHED]
    cols = [c for c in ["recall_det", "recall_B", "recall_L", "incremental_recall", "incremental_recall_at_5_per_1k",
                        "incremental_recall_at_10_per_1k", "incremental_recall_at_25_per_1k", "extra_alerts_untouched_per_1k",
                        "auc_L_target"] if c in m]
    g = m.groupby(by)[cols].agg(["mean", "std", "count"]) if len(m) else pd.DataFrame()
    return g


def np_json(o: Any) -> Any:
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(type(o))
