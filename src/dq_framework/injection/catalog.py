"""Expand the scenario catalog (config/experiments/scenario_catalog.yaml) into Scenario objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dq_framework import paths
from dq_framework.contracts import Contract
from dq_framework.injection import Scenario


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    path = path or paths.CONFIG_DIR / "experiments" / "scenario_catalog.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def mechanism_params(cat: dict[str, Any], dataset: str, mech: str, column: str, contract: Contract) -> dict[str, Any] | None:
    """Parameters for ``mech`` on ``column``; None if the combination is not defined."""
    ds = cat["datasets"][dataset]
    strength = cat["defaults"]["soft_strength"]
    cond = ds["ear_condition"]
    if mech in ("soft_ecar", "tab_err_ecar"):
        return {}
    if mech.endswith("_ear"):
        c = cond["column"]
        if c == column:
            return None
        if mech == "tab_err_ear":
            return {"condition_column": c}
        p: dict[str, Any] = {"condition_column": c, "strength": strength}
        if "segment_values" in cond:
            p["segment_values"] = cond["segment_values"]
        else:
            p["direction"] = cond.get("direction", "high")
        return p
    if mech.endswith("_enar"):
        is_cat = contract.column(column).type == "categorical"
        if mech == "tab_err_enar":
            return {}
        if is_cat:
            seg = (ds.get("categorical_enar_segment") or {}).get(column)
            return None if seg is None else {"strength": strength, "segment_values": seg}
        return {"strength": strength, "direction": "high"}
    raise ValueError(mech)


def expand(dataset: str, contract: Contract, cat: dict[str, Any] | None = None, seeds: list[int] | None = None,
           roles: tuple[str, ...] = ("primary", "sanity"), mechanisms: list[str] | None = None) -> list[Scenario]:
    cat = cat or load_catalog()
    ds = cat["datasets"][dataset]
    seeds = seeds or cat["defaults"]["seeds"]
    mechs = mechanisms or [m["name"] for m in cat["mechanisms"]]
    out = []
    for case in ds["cases"]:
        if case.get("role", "primary") not in roles:
            continue
        for mech in mechs:
            mp = mechanism_params(cat, dataset, mech, case["column"], contract)
            if mp is None:
                continue
            for seed in seeds:
                out.append(
                    Scenario(
                        dataset=dataset,
                        column=case["column"],
                        operation=case["operation"],
                        mechanism=mech,
                        rate=float(case.get("rate", cat["defaults"]["rate"])),
                        seed=int(seed),
                        op_params=dict(case.get("params", {})),
                        mech_params=mp,
                        tag=case.get("role", "primary"),
                    )
                )
    return out
