"""Common detector adapter interface and standardised output.

Every detector - in-process or running in an isolated environment - returns a
``DetectorOutput`` with one row per scored cell (or row, for row-level methods):

    _scenario_id, _row_id, column (None for row-level), score, flag

``score`` is "higher = more suspicious" and comparable *within* a detector run
(for conformal methods it is 1 - conformal p-value, hence also comparable across
columns). ``flag`` is the detector's own decision at its configured threshold.
Metadata records configuration, status, runtime, warnings and limitations.
A detector that cannot run on a dataset reports status INCOMPATIBLE with reasons;
it is never assigned an artificial score.
"""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import pandas as pd

from dq_framework.contracts import Contract

PASS, CONDITIONAL, INCOMPATIBLE, BLOCKED = "PASS", "CONDITIONAL", "INCOMPATIBLE", "BLOCKED / NOT TESTED"
OUTPUT_COLUMNS = ["_scenario_id", "_row_id", "column", "score", "flag"]


@dataclass
class Compatibility:
    verdict: str
    reasons: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)


@dataclass
class DetectorOutput:
    detector: str
    granularity: str  # cell | row
    scores: pd.DataFrame
    status: str = "ok"  # ok | failed | incompatible
    config: dict[str, Any] = field(default_factory=dict)
    fit_seconds: float = 0.0
    score_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)

    def meta(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "granularity": self.granularity,
            "status": self.status,
            "config": self.config,
            "fit_seconds": round(self.fit_seconds, 3),
            "score_seconds": round(self.score_seconds, 3),
            "n_scored": int(len(self.scores)),
            "n_flagged": int(self.scores["flag"].sum()) if len(self.scores) else 0,
            "warnings": self.warnings,
            "limitations": self.limitations,
            "environment": self.environment,
        }


class Detector(ABC):
    name: ClassVar[str]
    granularity: ClassVar[str] = "cell"
    supervision: ClassVar[str] = "none"  # none | reference_data | few_labels
    # True if ``score`` is a ranking score published with (or derived in the paper of) the method; binary-only
    # methods return NaN scores and are never ranked (no ranking is constructed for them).
    provides_scores: ClassVar[bool] = True
    # Where the method learns its model: "reference" (historical data) or "batch" (the unlabelled batch under
    # test, i.e. transductive). Recorded per run; it changes what information the method uses.
    fit_scope: ClassVar[str] = "reference"
    limitations: ClassVar[list[str]] = []

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def check_compatibility(self, contract: Contract, reference: pd.DataFrame) -> Compatibility: ...

    @abstractmethod
    def fit(self, reference: pd.DataFrame, contract: Contract) -> Detector: ...

    @abstractmethod
    def score(self, batch: pd.DataFrame) -> DetectorOutput: ...


def environment_info(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    import sklearn

    info = {"python": platform.python_version(), "sklearn": sklearn.__version__, "pandas": pd.__version__}
    info.update(extra or {})
    return info
