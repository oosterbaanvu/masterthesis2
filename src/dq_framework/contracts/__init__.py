"""Source contracts: declared schema, semantics and conventional data-quality controls.

A contract (``config/contracts/<dataset>.yaml``) is the single versioned source of
truth for a data source. It declares

* the analysed columns, their logical type (numeric / categorical) and semantics,
* columns that are *excluded* (e.g. prediction targets) with a reason,
* deterministic rules (not_null, unique, accepted_values, range, expression),
* statistical controls whose thresholds are *fitted on the reference partition*
  (envelope over a SQL expression), and
* per rule an evidence ``status``: ``verified`` (documented semantics and no
  violations on untouched data), ``provisional`` (plausible or data-derived;
  failure rate on untouched data reported), or ``unsupported`` (recorded but
  disabled, e.g. a documented domain that the published data contradicts).

dbt models and tests are generated from the contract (see ``controls.dbt_gen``),
so onboarding a new source means writing a contract, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dq_framework import paths

RULE_KINDS = {"not_null", "unique", "accepted_values", "range", "expression"}
STAT_KINDS = {"envelope", "rare_category"}
STATUSES = {"verified", "provisional", "unsupported"}


@dataclass
class Column:
    name: str
    type: str  # numeric | categorical
    semantic: str = ""
    required: bool = True
    description: str = ""
    documented_values: list[Any] | None = None
    unit: str | None = None
    missing_tokens: list[str] = field(default_factory=list)

    @property
    def sql_name(self) -> str:
        return quote_ident(self.name)


@dataclass
class Rule:
    id: str
    kind: str
    columns: list[str]
    status: str
    evidence: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    tier: str = "deterministic"  # deterministic | statistical

    @property
    def active(self) -> bool:
        return self.enabled and self.status != "unsupported"


@dataclass
class Contract:
    dataset: str
    table: str
    description: str
    row_id: str | None
    columns: list[Column]
    excluded_columns: dict[str, str]
    rules: list[Rule]
    derived_columns: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def numeric_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.type == "numeric"]

    @property
    def categorical_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.type == "categorical"]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)

    def active_rules(self, tiers: tuple[str, ...] = ("deterministic", "statistical")) -> list[Rule]:
        return [r for r in self.rules if r.active and r.tier in tiers]


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _expand(columns: Any, all_cols: list[str]) -> list[str]:
    if columns == "all":
        return list(all_cols)
    if isinstance(columns, str):
        return [columns]
    return list(columns)


def load_contract(path_or_dataset: str | Path) -> Contract:
    p = Path(path_or_dataset)
    if not p.suffix:
        p = paths.CONFIG_DIR / "contracts" / f"{path_or_dataset}.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    cols = [Column(**c) for c in doc["columns"]]
    names = [c.name for c in cols]
    rules: list[Rule] = []
    for tier, key in (("deterministic", "rules"), ("statistical", "statistical_controls")):
        for r in doc.get(key, []) or []:
            rules.extend(_expand_rule(r, names, tier))
    c = Contract(
        dataset=doc["dataset"],
        table=doc["table"],
        description=doc.get("description", ""),
        row_id=doc.get("row_id"),
        columns=cols,
        excluded_columns=doc.get("excluded_columns", {}) or {},
        rules=rules,
        derived_columns=doc.get("derived_columns", {}) or {},
        raw=doc,
    )
    validate_contract(c)
    return c


def _expand_rule(r: dict[str, Any], names: list[str], tier: str) -> list[Rule]:
    """Expand templated rules: ``for_each`` substitutes {i} in id/columns/params (e.g. months 1..6)."""
    base = {k: v for k, v in r.items() if k not in ("id", "kind", "columns", "status", "evidence", "enabled", "for_each")}
    loops = r.get("for_each")
    instances = [None] if loops is None else list(loops)
    out = []
    for i in instances:

        def sub(x: Any, i: Any = i) -> Any:
            if i is None:
                return x
            if isinstance(x, str):
                return x.replace("{i}", str(i)).replace("{i1}", str(int(i) + 1) if str(i).isdigit() else "")
            if isinstance(x, list):
                return [sub(v) for v in x]
            if isinstance(x, dict):
                return {k: sub(v) for k, v in x.items()}
            return x

        out.append(
            Rule(
                id=sub(r["id"]),
                kind=r["kind"],
                columns=sub(_expand(r["columns"], names)),
                status=r["status"],
                evidence=r.get("evidence", ""),
                params=sub(base),
                enabled=r.get("enabled", True),
                tier=tier,
            )
        )
    return out


def validate_contract(c: Contract) -> None:
    names = set(c.column_names)
    ids = set()
    for col in c.columns:
        if col.type not in ("numeric", "categorical"):
            raise ValueError(f"{c.dataset}.{col.name}: type must be numeric or categorical")
    for r in c.rules:
        if r.id in ids:
            raise ValueError(f"duplicate rule id {r.id}")
        ids.add(r.id)
        kinds = RULE_KINDS if r.tier == "deterministic" else STAT_KINDS
        if r.kind not in kinds:
            raise ValueError(f"{r.id}: unknown {r.tier} kind {r.kind}")
        if r.status not in STATUSES:
            raise ValueError(f"{r.id}: status must be one of {STATUSES}")
        unknown = [x for x in r.columns if x not in names and x != c.row_id]
        if unknown:
            raise ValueError(f"{r.id}: unknown columns {unknown}")
        if r.kind in ("expression", "envelope") and "expression" not in r.params:
            raise ValueError(f"{r.id}: {r.kind} needs an 'expression'")
