import pytest

from dq_framework.contracts import load_contract
from dq_framework.controls import dbt_gen


@pytest.mark.parametrize("ds", ["uci_credit", "uci_bank_marketing"])
def test_contracts_load_and_expand(ds):
    c = load_contract(ds)
    assert c.columns and c.rules
    ids = [r.id for r in c.rules]
    assert len(ids) == len(set(ids))
    assert all("{i" not in r.id for r in c.rules), "templated ids must be expanded"
    # unsupported rules are recorded but never active
    assert all(not r.active for r in c.rules if r.status == "unsupported")


def test_for_each_expansion_uci_credit():
    c = load_contract("uci_credit")
    mom = [r for r in c.rules if r.id.startswith("S_BILL_MOM")]
    assert [r.id for r in mom] == [f"S_BILL_MOM{i}" for i in range(1, 6)]
    assert mom[0].columns == ["BILL_AMT1", "BILL_AMT2", "LIMIT_BAL"]


@pytest.mark.parametrize("ds", ["uci_credit", "uci_bank_marketing"])
def test_generated_dbt_files_are_up_to_date(ds):
    """The committed dbt models/tests must equal what the contract generates."""
    sql, yml = dbt_gen.render(load_contract(ds))
    assert (dbt_gen.GENERATED_DIR / f"stg_{ds}.sql").read_text() == sql
    assert (dbt_gen.GENERATED_DIR / f"{ds}.yml").read_text() == yml


def test_invalid_contract_rejected(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("dataset: x\ntable: t\ncolumns: [{name: a, type: numeric}]\nrules:\n"
                 "  - {id: R1, kind: range, columns: [b], status: verified}\n")
    with pytest.raises(ValueError, match="unknown columns"):
        load_contract(p)
