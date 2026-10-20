"""Scenario sets of the pilot: strategies ``simple`` and ``diverse`` with equal budgets, plus a held-out family.

Equal budget by construction: for every error case and every error rate each strategy gets the same number
of scenarios (``seeds_per_cell``) on the same partition, so both strategies inject the same number of errors
into the same rows and cost the same to evaluate. The strategies differ only in *where* the errors fall:

* ``simple``  - every scenario uses ECAR (uniformly random eligible cells);
* ``diverse`` - the scenarios of a cell rotate through a pool of mechanisms (ECAR, context-dependent EAR/ENAR,
  tab_err windows and realistic segment/batch mechanisms), deterministically so each mechanism is used
  about equally often.

The held-out family uses error cases (columns or column x operation pairs) and mechanism settings that appear
in neither strategy; selection never sees it.

Scenario seeds are derived from (pilot seed, set, case, rate, slot), so selection and test scenarios never
share seeds, and every scenario is reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from dq_framework.contracts import Contract
from dq_framework.injection import Scenario


@dataclass(frozen=True)
class PilotScenario:
    scenario: Scenario
    set_name: str  # sel_simple | sel_diverse | sanity | test_simple | test_diverse | test_heldout
    partition: str  # selection | test
    case_id: str
    family: str  # error family (e.g. scale, valid_category, substitution, shift, sanity)
    mechanism_setting: str

    @property
    def sid(self) -> str:
        return f"{self.set_name}:{self.scenario.scenario_id}"


def _seed(*parts: Any) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:4], "little") % 1_000_000_007


def mechanism_for(setting: dict[str, Any], column: str, contract: Contract) -> tuple[str, dict[str, Any]] | None:
    """Resolve a named mechanism setting for a target column; None if it does not apply to that column."""
    mech = setting["mechanism"]
    params = dict(setting.get("params", {}) or {})
    if params.get("condition_column") == column:
        return None
    if mech == "soft_enar" and contract.column(column).type == "categorical":
        seg = (setting.get("categorical_segments") or {}).get(column)
        if seg is None:
            return None
        params = {"strength": params.get("strength", 4.0), "segment_values": seg}
    return mech, params


def _scenario(dataset: str, case: dict[str, Any], mech: str, mparams: dict[str, Any], rate: float, seed: int) -> Scenario:
    return Scenario(dataset=dataset, column=case["column"], operation=case["operation"], mechanism=mech, rate=float(rate),
                    seed=int(seed), op_params=dict(case.get("params", {}) or {}), mech_params=mparams,
                    tag=case.get("role", "primary"))


def build_set(cfg: dict[str, Any], contract: Contract, pilot_seed: int, set_name: str, cases: list[dict[str, Any]],
              mechanism_names: list[str], partition: str, seeds_per_cell: int, rotate: bool) -> list[PilotScenario]:
    out: list[PilotScenario] = []
    settings = cfg["mechanisms"]
    for ci, case in enumerate(cases):
        applicable = [m for m in mechanism_names if mechanism_for(settings[m], case["column"], contract) is not None]
        if not applicable:
            raise ValueError(f"no mechanism of {mechanism_names} applies to case {case['id']}")
        for ri, rate in enumerate(cfg["rates"]):
            for slot in range(seeds_per_cell):
                name = applicable[(ci * 7 + ri * seeds_per_cell + slot) % len(applicable)] if rotate else applicable[0]
                mech, mp = mechanism_for(settings[name], case["column"], contract)
                seed = _seed(pilot_seed, set_name, case["id"], rate, slot)
                out.append(PilotScenario(_scenario(cfg["dataset"], case, mech, mp, rate, seed), set_name, partition,
                                         case["id"], case.get("family", "other"), name))
    return out


def build_all(cfg: dict[str, Any], contract: Contract, pilot_seed: int) -> list[PilotScenario]:
    k = int(cfg.get("seeds_per_cell", 3))
    simple = cfg["strategies"]["simple"]["mechanisms"]
    diverse = cfg["strategies"]["diverse"]["mechanisms"]
    held = cfg["heldout"]["mechanisms"]
    leaked = (set(held) - {"ecar"}) & (set(simple) | set(diverse))
    if leaked:
        raise ValueError(f"held-out mechanisms also used by a strategy: {sorted(leaked)}")
    sel_ids = {c["id"] for c in cfg["cases"]}
    sel_pairs = {(c["column"], c["operation"]) for c in cfg["cases"]}
    for c in cfg["heldout"]["cases"]:
        if c["id"] in sel_ids or (c["column"], c["operation"]) in sel_pairs:
            raise ValueError(f"held-out case {c['id']} repeats a selection case")
    prim = [c for c in cfg["cases"] if c.get("role", "primary") == "primary"]
    sanity = [c for c in cfg["cases"] if c.get("role") == "sanity"]
    out = []
    out += build_set(cfg, contract, pilot_seed, "sel_simple", prim, simple, "selection", k, rotate=False)
    out += build_set(cfg, contract, pilot_seed, "sel_diverse", prim, diverse, "selection", k, rotate=True)
    out += build_set(cfg, contract, pilot_seed, "sanity", sanity, ["ecar"], "selection", 1, rotate=False)
    out += build_set(cfg, contract, pilot_seed, "test_simple", prim, simple, "test", k, rotate=False)
    out += build_set(cfg, contract, pilot_seed, "test_diverse", prim, diverse, "test", k, rotate=True)
    out += build_set(cfg, contract, pilot_seed, "test_heldout", cfg["heldout"]["cases"], held, "test", k, rotate=True)
    return out
