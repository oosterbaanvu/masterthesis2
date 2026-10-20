"""Adapters for detectors that run in isolated environments (envs/<name>/.venv).

Data is exchanged through Parquet files and a JSON job description; the child
process never imports the framework, so incompatible dependency stacks
(Python 3.9 / AutoGluon 0.8.2 / pandas 2.1 for Raha) stay separated.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dq_framework import paths
from dq_framework.contracts import Contract
from dq_framework.detectors.base import (
    BLOCKED,
    CONDITIONAL,
    INCOMPATIBLE,
    Compatibility,
    Detector,
    DetectorOutput,
)

ENVS = paths.ROOT / "envs"


def _env_python(name: str) -> Path:
    return ENVS / name / ".venv" / "bin" / "python"


class OriginalCDC(Detector):
    """The published CDC implementation (AutoGluon 0.8.2) in envs/cdc_aistats."""

    name = "cdc_original"
    granularity = "cell"
    supervision = "reference_data"
    limitations = [
        "Original implementation without the FASTAI model family (RF + XT only); see envs/cdc_aistats/requirements.txt.",
        "Produces flags only (no scores), so it cannot be evaluated at a fixed review budget.",
        "Original categorical prediction sets use a strict '<' (see detectors/cdc.py, deviation 6).",
    ]

    def __init__(self, confidence: float = 0.999, typing: str = "contract", num_trials: int = 3,
                 hyperparameters: dict[str, Any] | None = None, seed: int = 0,
                 target_columns: list[str] | None = None, timeout_s: int = 7200) -> None:
        super().__init__(confidence=confidence, typing=typing, num_trials=num_trials,
                         hyperparameters=hyperparameters or {"RF": {}, "XT": {}}, seed=seed,
                         target_columns=target_columns, timeout_s=timeout_s)

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        if not _env_python("cdc_aistats").exists():
            return Compatibility(BLOCKED, ["isolated environment envs/cdc_aistats not installed (run envs/cdc_aistats/install.sh)"])
        if reference[contract.column_names].isna().any().any():
            return Compatibility(CONDITIONAL, ["missing values in reference: original imputes them and counts them as cleaned"])
        return Compatibility(CONDITIONAL, ["flags only; RF+XT only (FASTAI omitted)"],
                             ["categorical columns passed as strings"])

    def fit(self, reference: pd.DataFrame, contract: Contract) -> OriginalCDC:
        self._ref = reference
        self._contract = contract
        return self

    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        c = self._contract
        with tempfile.TemporaryDirectory(prefix="cdc_orig_") as td:
            td = Path(td)
            cols = c.column_names
            self._ref[["_row_id", *cols]].to_parquet(td / "ref.parquet", index=False)
            keep = ["_scenario_id", "_row_id", *cols] if "_scenario_id" in batch else ["_row_id", *cols]
            batch[keep].to_parquet(td / "batch.parquet", index=False)
            job = {
                "reference": str(td / "ref.parquet"), "batch": str(td / "batch.parquet"), "out": str(td / "out.parquet"),
                "columns": cols, "categorical": c.categorical_columns,
                "target_columns": self.config["target_columns"],
                "typing": self.config["typing"], "confidence": self.config["confidence"],
                "hyperparameters": self.config["hyperparameters"], "num_trials": self.config["num_trials"],
                "seed": self.config["seed"],
            }
            (td / "job.json").write_text(json.dumps(job))
            t0 = time.perf_counter()
            proc = subprocess.run(
                [str(_env_python("cdc_aistats")), "-I", str(ENVS / "cdc_aistats" / "run_cdc_original.py"), str(td / "job.json")],
                capture_output=True, text=True, timeout=self.config["timeout_s"], check=False,
            )
            elapsed = time.perf_counter() - t0
            if proc.returncode != 0 or not (td / "out.parquet").exists():
                return DetectorOutput(self.name, "cell", pd.DataFrame(columns=["_scenario_id", "_row_id", "column", "score", "flag"]),
                                      status="failed", config=dict(self.config),
                                      warnings=[proc.stderr[-2000:]], limitations=list(self.limitations))
            out = pd.read_parquet(td / "out.parquet")
            meta = json.loads((td / "out.parquet.meta.json").read_text())
        return DetectorOutput(
            detector=self.name, granularity="cell", scores=out, config=dict(self.config),
            fit_seconds=meta["fit_seconds"], score_seconds=meta["score_seconds"],
            limitations=list(self.limitations),
            environment={"env": "envs/cdc_aistats", "python": "3.9", "autogluon": "0.8.2", "wall_seconds": elapsed,
                         "typing_used": {"categorical": meta["categorical_used"], "numerical": meta["numerical_used"]}},
        )


__all__ = ["OriginalCDC", "INCOMPATIBLE"]


def _format_csv(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Render values as strings the way a delivery file would carry them (integers without '.0')."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        s = df[c]

        def fmt(v):
            if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
                return ""
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)

        out[c] = s.astype(object).map(fmt)
    return out


class Raha(Detector):
    """The published Raha implementation (BigDaMa/raha 1.26) in envs/raha.

    Semi-supervised: receives ``labeling_budget`` labeled tuples from a simulated user
    (the injection ground truth of the same batch). It is therefore NOT a like-for-like
    alternative to unsupervised detectors and is reported separately.
    """

    name = "raha"
    granularity = "cell"
    supervision = "few_labels"
    limitations = [
        "Needs labeled tuples from the batch under test (simulated from injection ground truth).",
        "Transductive: runs on the batch itself; no reference model, no scores (flags only).",
        "Runtime grows with rows x columns x strategies; batches are subsampled for feasibility.",
    ]

    def __init__(self, labeling_budget: int = 20, seed: int = 0, algorithms: list[str] | None = None,
                 timeout_s: int = 7200) -> None:
        super().__init__(labeling_budget=labeling_budget, seed=seed,
                         algorithms=algorithms or ["OD", "PVD", "RVD", "KBVD"], timeout_s=timeout_s)

    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility:
        if not _env_python("raha").exists():
            return Compatibility(BLOCKED, ["isolated environment envs/raha not installed"])
        return Compatibility(CONDITIONAL, ["requires labeled tuples (different supervision)", "flags only"],
                             ["values serialised to strings (Raha reads CSV as text)"])

    def fit(self, reference: pd.DataFrame, contract: Contract) -> Raha:
        self._contract = contract
        return self

    def score_pair(self, dirty: pd.DataFrame, clean: pd.DataFrame, scenario_id: str) -> DetectorOutput:
        cols = self._contract.column_names
        with tempfile.TemporaryDirectory(prefix="raha_") as td:
            td = Path(td)
            _format_csv(dirty, cols).to_csv(td / "dirty.csv", index=False)
            _format_csv(clean, cols).to_csv(td / "clean.csv", index=False)
            job = {"dirty_csv": str(td / "dirty.csv"), "clean_csv": str(td / "clean.csv"), "out": str(td / "out.parquet"),
                   "labeling_budget": self.config["labeling_budget"], "seed": self.config["seed"],
                   "algorithms": self.config["algorithms"], "row_ids": [int(x) for x in dirty["_row_id"]],
                   "scenario_id": scenario_id}
            (td / "job.json").write_text(json.dumps(job))
            # Raha writes intermediate files to tempfile.gettempdir() under names that depend only on the
            # dataset name and strategy; a private TMPDIR prevents collisions between concurrent jobs.
            env = {**os.environ, "TMPDIR": str(td)}
            proc = subprocess.run([str(_env_python("raha")), "-I", str(ENVS / "raha" / "run_raha.py"), str(td / "job.json")],
                                  capture_output=True, text=True, timeout=self.config["timeout_s"], check=False, cwd=td, env=env)
            if proc.returncode != 0 or not (td / "out.parquet").exists():
                return DetectorOutput(self.name, "cell", pd.DataFrame(columns=["_scenario_id", "_row_id", "column", "score", "flag"]),
                                      status="failed", config=dict(self.config), warnings=[proc.stderr[-3000:]],
                                      limitations=list(self.limitations))
            out = pd.read_parquet(td / "out.parquet")
            meta = json.loads((td / "out.parquet.meta.json").read_text())
        return DetectorOutput(self.name, "cell", out, config=dict(self.config), score_seconds=meta["seconds"],
                              limitations=list(self.limitations), environment={"env": "envs/raha", **meta})

    def score(self, batch: pd.DataFrame) -> DetectorOutput:
        raise NotImplementedError("Raha needs the pre-injection batch for simulated labels; use score_pair()")
