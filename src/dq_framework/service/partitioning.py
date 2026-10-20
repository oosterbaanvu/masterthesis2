"""Dirty-only, entity-aware exploratory splits; the seed-1 research holdout is reserved."""

from __future__ import annotations

import hashlib
import re

import pandas as pd

from dq_framework.datasets import make_split


def grouped_partitions(raw, typed, contract, group_columns, seed=11, history_fraction=0.6):
    """Union equal dirty identifiers, reserve whole groups touching the existing holdout.

    Group labels and selection never inspect a clean table. Restaurant's dirty class can group
    known entity annotations, but '?' never joins unrelated records. Approximate identifiers are
    deliberately conservative; this is not a verified entity-resolution algorithm.
    """
    if not 0 < history_fraction < 1:
        raise ValueError("history_fraction must be between zero and one")
    if len(raw) != len(typed) or typed["_row_id"].duplicated().any():
        raise ValueError("dirty raw/typed rows must correspond with unique row IDs")
    parent = list(range(len(raw)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for column in group_columns:
        seen = {}
        for i, value in enumerate(raw[column]):
            if pd.isna(value) or str(value).strip() in ("", "?", "-1"):
                continue
            key = re.sub(r"\W+", "", str(value).casefold())
            if not key:
                continue
            if key in seen:
                a, b = root(i), root(seen[key])
                parent[max(a, b)] = min(a, b)
            else:
                seen[key] = i
    groups = pd.Series([root(i) for i in range(len(raw))], index=typed.index)
    heldout = make_split(typed, contract, seed=1) == "test"
    heldout_groups = set(groups[heldout])
    assignment = {}
    for group in sorted(set(groups)):
        u = int.from_bytes(hashlib.sha256(f"{seed}|{group}".encode()).digest()[:8], "big") / 2**64
        assignment[group] = "holdout" if group in heldout_groups else ("history" if u < history_fraction else "batch")
    return pd.DataFrame({"_row_id": typed["_row_id"], "group": groups, "partition": groups.map(assignment)})
