import shutil

import pytest

from dq_framework import paths
from dq_framework.controls import alerts_to_cells, dbt_gen, fit_reference_stats, run_controls

pytestmark = pytest.mark.dbt


def test_dbt_executes_generated_tests_and_returns_evidence(tmp_path, toy_contract, toy_data):
    if shutil.which("dbt") is None:
        pytest.skip("dbt not installed")
    proj = tmp_path / "dbt"
    shutil.copytree(paths.DBT_DIR, proj, ignore=shutil.ignore_patterns("target", "logs", "generated"))
    (proj / "models" / "generated").mkdir(parents=True, exist_ok=True)
    dbt_gen.write(toy_contract, proj / "models" / "generated")
    ref, batch = toy_data
    b = batch.copy()
    b.loc[b.index[0], "status"] = "Z"          # violates accepted_values
    b.loc[b.index[1], "limit_amt"] = 0          # violates range
    b.loc[b.index[2], "id"] = b.loc[b.index[3], "id"]  # duplicate key
    b.loc[b.index[4], "balance"] = 10_000_000   # violates expression + envelope
    stats = fit_reference_stats(toy_contract, ref)
    run = run_controls(toy_contract, b.assign(_scenario_id="s1"), stats, tmp_path / "work", dbt_dir=proj)
    got = set(zip(run.alerts["rule_id"], run.alerts["_row_id"], strict=True))
    rid = b["_row_id"].tolist()
    assert ("D_STATUS", rid[0]) in got
    assert ("D_LIMIT_POS", rid[1]) in got
    assert ("D_UNIQUE_ID", rid[2]) in got and ("D_UNIQUE_ID", rid[3]) in got
    assert ("D_BAL_LE_2LIMIT", rid[4]) in got and ("S_ENV_balance", rid[4]) in got
    assert "D_DISABLED" not in set(run.alerts["rule_id"])  # unsupported rules are not executed
    cells = alerts_to_cells(run.alerts)
    assert {"balance", "limit_amt"} <= set(cells.loc[cells["_row_id"] == rid[4], "column"])
