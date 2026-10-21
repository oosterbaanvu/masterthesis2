"""One pilot replication: (dataset, pilot seed, split scheme) -> per-scenario metrics for every detector.

Execution plan
1. partitions (``splits.pilot_split``); the confirmatory hold-out is excluded before anything is read;
2. all scenario sets are injected into copies of the selection / test partitions (``scenarios.build_all``);
3. **one** dbt invocation executes the generated controls on the stacked batch (untouched partitions +
   every scenario); statistical bounds are fitted on the reference partition only;
4. each detector is fitted once on the reference partition (or, for transductive methods, on each batch)
   and scored. Reference-fitted detectors score rows independently, so a scenario's scores equal the scores
   of the untouched partition except on rows that contain an injected cell; only those rows are re-scored
   (exact, and two orders of magnitude cheaper than re-scoring every scenario batch);
5. metrics per (scenario, detector, baseline) are computed on (row x column) matrices (``metrics``).

Nothing here looks at test scenarios when configuring anything: all configuration comes from the YAML file.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from dq_framework import __version__, paths
from dq_framework.contracts import load_contract
from dq_framework.controls import alerts_to_cells, fit_reference_stats, run_controls
from dq_framework.datasets import load_contract_table
from dq_framework.detectors.registry import make_detector
from dq_framework.injection import inject
from dq_framework.pilot import metrics as M
from dq_framework.pilot import total_budget
from dq_framework.pilot.scenarios import PilotScenario, build_all
from dq_framework.pilot.splits import delivery_split, pilot_split

UNTOUCHED = {"selection": "untouched:selection", "test": "untouched:test"}
BASELINES = ("deterministic", "full")


def load_config(path: str | Path) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg["_path"] = str(path)
    return cfg


class _Grid:
    """Maps (_row_id, column) of one partition to matrix positions."""

    def __init__(self, frame: pd.DataFrame, columns: list[str]):
        self.columns = columns
        self.col_idx = {c: j for j, c in enumerate(columns)}
        self.pos = pd.Series(np.arange(len(frame)), index=frame["_row_id"].astype("int64").to_numpy())
        self.shape = (len(frame), len(columns))

    def cells(self, row_ids, cols) -> tuple[np.ndarray, np.ndarray]:
        r = self.pos.reindex(pd.Index(np.asarray(row_ids, dtype="int64"))).to_numpy()
        c = pd.Series(cols, dtype=object).map(self.col_idx).to_numpy()
        ok = ~(pd.isna(r) | pd.isna(c))
        return r[ok].astype(int), c[ok].astype(int)

    def mask(self, row_ids, cols) -> np.ndarray:
        out = np.zeros(self.shape, dtype=bool)
        r, c = self.cells(row_ids, cols)
        out[r, c] = True
        return out

    def rows(self, row_ids) -> np.ndarray:
        out = np.zeros(self.shape[0], dtype=bool)
        r = self.pos.reindex(pd.Index(np.asarray(row_ids, dtype="int64"))).dropna().to_numpy().astype(int)
        out[r] = True
        return out


def _to_matrices(scores: pd.DataFrame, grid: _Grid, granularity: str) -> tuple[np.ndarray, np.ndarray]:
    if granularity == "row":
        f = np.zeros(grid.shape[0], dtype=bool)
        s = np.full(grid.shape[0], np.nan)
        r = grid.pos.reindex(pd.Index(scores["_row_id"].astype("int64").to_numpy())).to_numpy()
        ok = ~pd.isna(r)
        f[r[ok].astype(int)] = scores["flag"].to_numpy(bool)[ok]
        s[r[ok].astype(int)] = scores["score"].to_numpy(float)[ok]
        return f, s
    f = np.zeros(grid.shape, dtype=bool)
    s = np.full(grid.shape, np.nan)
    r, c = grid.cells(scores["_row_id"].to_numpy(), scores["column"].to_numpy())
    keep = ~(pd.isna(grid.pos.reindex(pd.Index(scores["_row_id"].astype("int64").to_numpy())).to_numpy())
             | pd.isna(pd.Series(scores["column"], dtype=object).map(grid.col_idx).to_numpy()))
    f[r, c] = scores["flag"].to_numpy(bool)[keep]
    s[r, c] = scores["score"].to_numpy(float)[keep]
    return f, s


def run_replication(cfg: dict[str, Any], pilot_seed: int, scheme: str = "random", out_root: Path | None = None,
                    detectors: list[str] | None = None, max_scenarios: int | None = None,
                    measure_memory: bool = False) -> Path:
    t_start = time.perf_counter()
    ds = cfg["dataset"]
    contract = load_contract(ds)
    cols = contract.column_names
    df = load_contract_table(ds, contract)
    if scheme == "delivery":  # consecutive deliveries; pilot_seed indexes cfg["deliveries"] (1-based)
        delivery = cfg["deliveries"][pilot_seed - 1]
        part = delivery_split(df, contract, delivery, holdout_seed=int(cfg.get("holdout_seed", 1)))
    else:
        part = pilot_split(df, contract, pilot_seed, scheme=scheme, fractions=tuple(cfg.get("fractions", (0.5, 0.25, 0.25))),
                           holdout_seed=int(cfg.get("holdout_seed", 1)), pool_max_rows=cfg.get("pool_max_rows"))
    frames = {p: df[part == p].reset_index(drop=True) for p in ("reference", "selection", "test")}
    ref = frames["reference"]
    grids = {p: _Grid(frames[p], cols) for p in ("selection", "test")}
    name = f"{ds}-{scheme}-{'d' if scheme == 'delivery' else 's'}{pilot_seed}"
    out_dir = (out_root or paths.RESULTS_DIR / "runs" / "pilot") / name
    out_dir.mkdir(parents=True, exist_ok=True)
    budgets = tuple(float(b) for b in cfg["budgets_per_1k"])

    # 1-2. scenarios -------------------------------------------------------------------------------------
    pscs: list[PilotScenario] = build_all(cfg, contract, pilot_seed)
    if max_scenarios:
        pscs = pscs[:max_scenarios]
    batches = [frames["selection"].assign(_scenario_id=UNTOUCHED["selection"]),
               frames["test"].assign(_scenario_id=UNTOUCHED["test"])]
    corrupted: dict[str, pd.DataFrame] = {}
    logs: dict[str, pd.DataFrame] = {}
    scen_rows, failures = [], []
    t0 = time.perf_counter()
    for ps in pscs:
        try:
            r = inject(frames[ps.partition], ps.scenario, contract, ref)
        except (ValueError, RuntimeError) as exc:
            failures.append({"sid": ps.sid, "set": ps.set_name, "case_id": ps.case_id, "stage": "injection", "error": str(exc)})
            continue
        if r.realised == 0:
            failures.append({"sid": ps.sid, "set": ps.set_name, "case_id": ps.case_id, "stage": "injection",
                             "error": "no cell changed"})
            continue
        corrupted[ps.sid] = r.corrupted.assign(_scenario_id=ps.sid)
        logs[ps.sid] = r.log
        batches.append(corrupted[ps.sid])
        sc = ps.scenario
        scen_rows.append({"sid": ps.sid, "set": ps.set_name, "partition": ps.partition, "case_id": ps.case_id,
                          "family": ps.family, "mechanism_setting": ps.mechanism_setting, "column": sc.column,
                          "operation": sc.operation, "op_params": json.dumps(sc.op_params), "mechanism": sc.mechanism,
                          "mechanism_class": sc.mechanism_class, "mech_params": json.dumps(sc.mech_params, default=str),
                          "rate": sc.rate, "seed": sc.seed, "role": sc.tag, "n_rows": r.n_rows,
                          "eligible": r.eligible, "intended": r.intended, "realised": r.realised})
    inj_seconds = time.perf_counter() - t0
    live = [ps for ps in pscs if ps.sid in corrupted]

    # 3. conventional controls ---------------------------------------------------------------------------
    stats = fit_reference_stats(contract, ref)
    batch = pd.concat(batches, ignore_index=True)
    ctl = run_controls(contract, batch, stats, out_dir / "controls")
    del batch
    cells = alerts_to_cells(ctl.alerts)
    by_sid_cells = dict(tuple(cells.groupby("_scenario_id", sort=False)))
    by_sid_rows = dict(tuple(ctl.alerts.groupby("_scenario_id", sort=False)))
    empty = cells.iloc[0:0]

    def base_masks(sid: str, grid: _Grid) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        c = by_sid_cells.get(sid, empty)
        a = by_sid_rows.get(sid, ctl.alerts.iloc[0:0])
        out = {}
        for b in BASELINES:
            cc = c if b == "full" else c[c["tier"] == "deterministic"]
            aa = a if b == "full" else a[a["tier"] == "deterministic"]
            out[b] = (grid.mask(cc["_row_id"].to_numpy(), cc["column"].to_numpy()), grid.rows(aa["_row_id"].to_numpy()))
        return out

    # 4. detectors -----------------------------------------------------------------------------------------
    det_cfg = {k: v for k, v in cfg["detectors"].items() if detectors is None or k in detectors}
    det_meta, outputs = {}, {}
    for key, spec in det_cfg.items():
        det = make_detector(spec)
        comp = det.check_compatibility(contract, ref)
        meta = {"detector": key, "name": spec["name"], "params": spec.get("params", {}), "granularity": det.granularity,
                "provides_scores": det.provides_scores, "fit_scope": det.fit_scope, "supervision": det.supervision,
                "compatibility": comp.verdict, "reasons": comp.reasons, "transformations": comp.transformations}
        if comp.verdict not in ("PASS", "CONDITIONAL"):
            meta["status"] = "not run (incompatible or blocked)"
            det_meta[key] = meta
            continue
        if measure_memory:
            tracemalloc.start()
        t0 = time.perf_counter()
        det.fit(ref, contract)
        meta["fit_seconds"] = time.perf_counter() - t0
        if measure_memory:
            meta["fit_peak_mb"] = tracemalloc.get_traced_memory()[1] / 1e6
            tracemalloc.reset_peak()
        score_s = 0.0
        res: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        untouched = {}
        warnings: list[str] = []
        for p, sid0 in UNTOUCHED.items():
            t0 = time.perf_counter()
            o = det.score(frames[p].assign(_scenario_id=sid0))
            score_s += time.perf_counter() - t0
            warnings += o.warnings
            untouched[p] = _to_matrices(o.scores, grids[p], det.granularity)
            res[sid0] = untouched[p]
        for ps in live:
            g = grids[ps.partition]
            cb = corrupted[ps.sid]
            t0 = time.perf_counter()
            if det.fit_scope == "reference":
                rows = np.unique(g.pos.reindex(pd.Index(logs[ps.sid]["_row_id"].astype("int64").to_numpy())).to_numpy().astype(int))
                f, s = (a.copy() for a in untouched[ps.partition])
                o = det.score(cb.iloc[rows])
                f2, s2 = _to_matrices(o.scores, g, det.granularity)
                f[rows], s[rows] = f2[rows], s2[rows]
            else:
                o = det.score(cb)
                f, s = _to_matrices(o.scores, g, det.granularity)
            score_s += time.perf_counter() - t0
            res[ps.sid] = (f, s)
        meta["score_seconds"] = score_s
        meta["n_score_calls"] = len(live) + 2
        meta["warnings_sample"] = sorted(set(warnings))[:5]
        if measure_memory:
            meta["score_peak_mb"] = tracemalloc.get_traced_memory()[1] / 1e6
            tracemalloc.stop()
        meta["status"] = "ok"
        det_meta[key] = meta
        outputs[key] = res

    # 5. metrics -----------------------------------------------------------------------------------------
    cell_dets = [k for k in outputs if det_meta[k]["granularity"] == "cell"]
    row_dets = [k for k in outputs if det_meta[k]["granularity"] == "row"]
    met_rows, base_rows, overlap_rows, burden_rows, shared_overlaps, pr_rows = [], [], [], [], [], []
    pr_seen = set()
    for p, sid0 in UNTOUCHED.items():
        g = grids[p]
        bm = base_masks(sid0, g)
        zero = np.zeros(g.shape, dtype=bool)
        for b, (bc, br) in bm.items():
            burden_rows.append({"partition": p, "detector": "<baseline>", "baseline": b,
                                "alerts_per_1k": 1000 * bc.sum() / g.shape[0], "rows_per_1k": 1000 * br.sum() / g.shape[0]})
            for k in cell_dets:
                f, _s = outputs[k][sid0]
                burden_rows.append({"partition": p, "detector": k, "baseline": b,
                                    "alerts_per_1k": 1000 * (f & ~bc).sum() / g.shape[0],
                                    "flags_per_1k": 1000 * f.sum() / g.shape[0]})
            for k in row_dets:
                f, _s = outputs[k][sid0]
                burden_rows.append({"partition": p, "detector": k, "baseline": b,
                                    "rows_per_1k": 1000 * (f & ~br).sum() / g.shape[0],
                                    "flags_per_1k": 1000 * f.sum() / g.shape[0]})
        del zero
    for ps in live:
        g = grids[ps.partition]
        lg = logs[ps.sid]
        inj = g.mask(lg["_row_id"].to_numpy(), lg["column"].to_numpy())
        tcol = g.col_idx[ps.scenario.column]
        bm = base_masks(ps.sid, g)
        for b, (bc, br) in bm.items():
            base_rows.append({"sid": ps.sid, "baseline": b, **M.baseline_metrics(inj, bc, g.shape[0]),
                              "row_recall_B_rules": float((inj.any(1) & br).sum() / inj.any(1).sum())})
            found = {}
            for k in cell_dets:
                f, s = outputs[k][ps.sid]
                sc = s if det_meta[k]["provides_scores"] else None
                m = M.cell_metrics(inj, bc, f, sc, budgets, target_col=tcol)
                if cfg.get("shared_total_budget"):
                    m.update(total_budget.metrics(inj, bc, f, sc, budgets))
                    if b == BASELINES[0] and sc is not None and (ps.family, k) not in pr_seen and ps.partition == "test":
                        from sklearn.metrics import precision_recall_curve

                        finite = np.isfinite(sc)
                        if inj[finite].any():
                            precision, recall, _ = precision_recall_curve(inj[finite], sc[finite])
                            for level in np.linspace(0, 1, 51):
                                precision_at = float(precision[recall >= level].max()) if (recall >= level).any() else 0.0
                                pr_rows.append({"sid": ps.sid, "family": ps.family, "column": ps.scenario.column,
                                                "detector": k, "recall": level, "precision": precision_at})
                            pr_seen.add((ps.family, k))
                met_rows.append({"sid": ps.sid, "detector": k, "baseline": b, **m})
                if cfg.get("shared_total_budget"):
                    _, selected, _ = total_budget.queues(bc, f, sc, int(round(25 * g.shape[0] / 1000)))
                    found[k] = selected & inj
                else:
                    found[k] = M.found_mask(inj, bc, f, sc, float(cfg.get("overlap_budget", 25)))
                if sc is not None:  # record-level view of a cell detector (max score per row)
                    rs = np.nanmax(np.where(np.isfinite(s), s, -np.inf), axis=1)
                    rm = M.row_metrics(inj, br, f.any(1), rs, budgets)
                    met_rows.append({"sid": ps.sid, "detector": f"{k}@row", "baseline": b, **rm})
            for k in row_dets:
                f, s = outputs[k][ps.sid]
                rm = M.row_metrics(inj, br, f, s if det_meta[k]["provides_scores"] else None, budgets)
                met_rows.append({"sid": ps.sid, "detector": k, "baseline": b, **rm})
            n_inj = int(inj.sum())
            union = np.zeros(g.shape, dtype=bool)
            for i, a in enumerate(cell_dets):
                union |= found[a]
                for bb in cell_dets[i + 1:]:
                    overlap_rows.append({"sid": ps.sid, "baseline": b, "a": a, "b": bb, "n_injected": n_inj,
                                         "a_found": int(found[a].sum()), "b_found": int(found[bb].sum()),
                                         "both": int((found[a] & found[bb]).sum()),
                                         "either": int((found[a] | found[bb]).sum())})
                    if cfg.get("shared_total_budget"):
                        shared_overlaps.append({"sid": ps.sid, "baseline": b, "a": a, "b": bb,
                                                "a_only": int((found[a] & ~found[bb]).sum()),
                                                "b_only": int((found[bb] & ~found[a]).sum()),
                                                "both": int((found[a] & found[bb]).sum()), "n_injected": n_inj})
            if cell_dets:
                overlap_rows.append({"sid": ps.sid, "baseline": b, "a": "<all>", "b": "<all>", "n_injected": n_inj,
                                     "a_found": int(union.sum()), "b_found": int(union.sum()), "both": int(union.sum()),
                                     "either": int(union.sum())})

    # 6. persist -------------------------------------------------------------------------------------------
    pd.DataFrame(scen_rows).to_csv(out_dir / "scenarios.csv", index=False)
    pd.DataFrame(met_rows).to_csv(out_dir / "detector_metrics.csv", index=False)
    pd.DataFrame(base_rows).to_csv(out_dir / "baseline_metrics.csv", index=False)
    pd.DataFrame(overlap_rows).to_csv(out_dir / "overlap.csv", index=False)
    pd.DataFrame(burden_rows).to_csv(out_dir / "untouched_burden.csv", index=False)
    if cfg.get("shared_total_budget"):
        pd.DataFrame(shared_overlaps).to_csv(out_dir / "shared_overlap.csv", index=False)
        pd.DataFrame(pr_rows).to_csv(out_dir / "pr_curves.csv", index=False)
        exact_logs = [lg.assign(sid=sid, original=lg["original"].map(repr), injected=lg["injected"].map(repr))
                      for sid, lg in logs.items()]
        pd.concat(exact_logs, ignore_index=True).to_parquet(out_dir / "injection_log.parquet", index=False)
    pd.DataFrame(failures, columns=["sid", "set", "case_id", "stage", "error"]).to_csv(out_dir / "failures.csv", index=False)
    rule_burden = (ctl.alerts[ctl.alerts["_scenario_id"].isin(UNTOUCHED.values())]
                   .groupby(["_scenario_id", "rule_id", "tier", "rule_status"]).size().rename("alerts").reset_index())
    rule_burden.to_csv(out_dir / "untouched_rule_burden.csv", index=False)
    import sklearn

    manifest = {
        "replication": name, "dataset": ds, "pilot_seed": pilot_seed, "scheme": scheme, "config": cfg["_path"],
        "framework_version": __version__, "started_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "elapsed_s": round(time.perf_counter() - t_start, 1), "injection_seconds": round(inj_seconds, 1),
        "partitions": {p: len(frames[p]) for p in frames} | {"holdout_excluded": int((part == "holdout").sum()),
                                                              "unused": int((part == "unused").sum())},
        "delivery": cfg["deliveries"][pilot_seed - 1] if scheme == "delivery" else None,
        "n_scenarios": len(live), "n_failed_scenarios": len(failures), "budgets_per_1k": list(budgets),
        "dbt": {"version": ctl.dbt_version, "elapsed_s": round(ctl.elapsed_s, 1),
                "tests": ctl.tests["status"].value_counts().to_dict()},
        "detectors": det_meta,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                        "sklearn": sklearn.__version__, "machine": platform.machine(), "cpus": __import__("os").cpu_count()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return out_dir
