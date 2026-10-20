"""Conventional controls: fit statistical thresholds on reference data, execute dbt tests, collect evidence.

The deterministic and statistical controls are executed by **dbt Core on DuckDB**
(not re-implemented in Python). Python only (1) fits the reference statistics the
statistical tests need, (2) writes the batch under test to Parquet, (3) invokes
``dbt build`` and (4) unions the stored failure tables into one standard
exception table.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from dq_framework import paths
from dq_framework.contracts import Contract
from dq_framework.controls.dbt_gen import model_name

ALERT_COLUMNS = ["rule_id", "_scenario_id", "_row_id", "implicated_columns", "observed", "expected"]


@dataclass
class ReferenceStats:
    bounds: pd.DataFrame  # rule_id, lower_bound, upper_bound, n_reference
    categories: pd.DataFrame  # rule_id, value, share

    def to_json(self) -> dict[str, Any]:
        return {"bounds": self.bounds.to_dict("records"), "categories": self.categories.to_dict("records")}


@dataclass
class ControlRun:
    alerts: pd.DataFrame
    tests: pd.DataFrame  # one row per executed dbt test: name, rule_id, status, failures, execution_time
    dbt_version: str
    command: list[str]
    elapsed_s: float
    workdir: Path
    log_tail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def fit_reference_stats(contract: Contract, reference: pd.DataFrame) -> ReferenceStats:
    """Fit envelope bounds and frequent-category sets on the reference partition with DuckDB SQL.

    Uses the same SQL expressions as the dbt tests, so fitted and executed statistics agree.
    """
    con = duckdb.connect()
    con.register("ref", reference)
    b_rows, c_rows = [], []
    for r in contract.active_rules(("statistical",)):
        expr = r.params["expression"]
        if r.kind == "envelope":
            lo, hi = r.params.get("lower_q", 0.0005), r.params.get("upper_q", 0.9995)
            q = con.execute(
                f"select quantile_cont(({expr})::double, {lo}), quantile_cont(({expr})::double, {hi}), "
                f"count(({expr})) from ref"
            ).fetchone()
            b_rows.append({"rule_id": r.id, "lower_bound": q[0], "upper_bound": q[1], "n_reference": q[2]})
        elif r.kind == "rare_category":
            min_share = float(r.params.get("min_share", 0.0))
            rows = con.execute(
                f"select cast(({expr}) as varchar) as v, count(*)::double / sum(count(*)) over () as share "
                f"from ref where ({expr}) is not null group by 1"
            ).fetchall()
            for v, share in rows:
                if share >= min_share and share > 0:
                    c_rows.append({"rule_id": r.id, "value": v, "share": share})
    con.close()
    return ReferenceStats(
        bounds=pd.DataFrame(b_rows, columns=["rule_id", "lower_bound", "upper_bound", "n_reference"]),
        categories=pd.DataFrame(c_rows, columns=["rule_id", "value", "share"]),
    )


def _dbt_executable() -> list[str]:
    exe = shutil.which("dbt", path=str(Path(sys.executable).parent)) or shutil.which("dbt")
    if exe is None:
        raise RuntimeError("dbt executable not found; install dbt-core and dbt-duckdb")
    return [exe]


def dbt_version() -> str:
    out = subprocess.run([*_dbt_executable(), "--version"], capture_output=True, text=True, check=False)
    lines = [ln.strip() for ln in out.stdout.splitlines() if "installed" in ln or ln.strip().startswith("- duckdb")]
    return "; ".join(lines)


def run_controls(
    contract: Contract,
    batch: pd.DataFrame,
    stats: ReferenceStats,
    workdir: Path,
    tiers: tuple[str, ...] = ("deterministic", "statistical"),
    dbt_dir: Path | None = None,
) -> ControlRun:
    """Execute the generated dbt tests for ``contract`` against ``batch``.

    ``batch`` must contain ``_scenario_id`` and ``_row_id`` plus the contract columns.
    """
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    batch_path = workdir / "batch.parquet"
    batch.to_parquet(batch_path, index=False)
    db_path = workdir / "dq.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.register("b_df", stats.bounds)
    con.register("c_df", stats.categories)
    con.execute("create or replace table main.dq_reference_bounds as select * from b_df")
    con.execute("create or replace table main.dq_reference_categories as select * from c_df")
    con.close()

    target = workdir / "dbt_target"
    cmd = [
        *_dbt_executable(), "build",
        "--project-dir", str(dbt_dir or paths.DBT_DIR),
        "--profiles-dir", str(dbt_dir or paths.DBT_DIR),
        "--target-path", str(target),
        "--log-path", str(workdir / "dbt_logs"),
        "--select", f"{model_name(contract)}+",
        "--vars", json.dumps({"batch_path": str(batch_path)}),
        "--no-partial-parse",
        "--quiet",
    ]
    env = {**os.environ, "DQF_DUCKDB_PATH": str(db_path), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    elapsed = time.perf_counter() - t0
    rr_path = target / "run_results.json"
    if not rr_path.exists():
        raise RuntimeError(f"dbt did not produce run_results.json (exit {proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    rr = json.loads(rr_path.read_text())
    manifest = json.loads((target / "manifest.json").read_text())
    test_rows, frames = [], []
    con = duckdb.connect(str(db_path), read_only=True)
    for res in rr["results"]:
        uid = res["unique_id"]
        if not uid.startswith("test."):
            if res["status"] not in ("success",):
                raise RuntimeError(f"dbt node {uid} status {res['status']}: {res.get('message')}")
            continue
        node = manifest["nodes"][uid]
        meta = node.get("config", {}).get("meta", {}) or {}
        tier = meta.get("tier")
        test_rows.append(
            {
                "test_name": node["name"],
                "rule_id": meta.get("rule_id"),
                "tier": tier,
                "status": res["status"],
                "failures": res.get("failures"),
                "execution_time_s": res.get("execution_time"),
                "message": res.get("message"),
            }
        )
        if res["status"] == "error":
            raise RuntimeError(f"dbt test {node['name']} errored: {res.get('message')}")
        if tier in tiers and (res.get("failures") or 0) > 0 and res.get("relation_name"):
            frames.append(con.execute(f"select * from {res['relation_name']}").df())
    con.close()
    alerts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ALERT_COLUMNS)
    alerts = alerts[ALERT_COLUMNS]
    tier_of = {r.id: r.tier for r in contract.rules}
    status_of = {r.id: r.status for r in contract.rules}
    alerts["tier"] = alerts["rule_id"].map(tier_of)
    alerts["rule_status"] = alerts["rule_id"].map(status_of)
    return ControlRun(
        alerts=alerts,
        tests=pd.DataFrame(test_rows),
        dbt_version=dbt_version(),
        command=cmd,
        elapsed_s=elapsed,
        workdir=workdir,
        log_tail=(proc.stdout + proc.stderr)[-2000:],
        meta={"returncode": proc.returncode},
    )


def alerts_to_cells(alerts: pd.DataFrame) -> pd.DataFrame:
    """Expand rule alerts to implicated cells: one row per (_scenario_id, _row_id, column, rule_id).

    A multi-column rule implicates every referenced column. This is how an engineer
    sees the exception; cell-level precision of such rules is therefore bounded by design.
    """
    if alerts.empty:
        return pd.DataFrame(columns=["_scenario_id", "_row_id", "column", "rule_id", "tier"])
    a = alerts.assign(column=alerts["implicated_columns"].str.split(",")).explode("column")
    return a[["_scenario_id", "_row_id", "column", "rule_id", "tier"]].reset_index(drop=True)
