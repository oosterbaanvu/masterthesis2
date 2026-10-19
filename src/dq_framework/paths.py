"""Repository-relative paths. All paths can be overridden with DQF_ROOT for out-of-tree use."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("DQF_ROOT")
    if env:
        return Path(env).resolve()
    # src/dq_framework/paths.py -> repository root
    return Path(__file__).resolve().parents[2]


ROOT = repo_root()
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_DIR = DATA_DIR / "manifests"
INTERIM_DIR = DATA_DIR / "interim"
SCENARIO_DIR = DATA_DIR / "scenarios"
DBT_DIR = ROOT / "dbt"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
