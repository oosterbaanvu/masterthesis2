"""Detector registry: one place that maps a configuration ``{"name": ..., "params": {...}}`` to an adapter."""

from __future__ import annotations

from typing import Any

from dq_framework.detectors.base import Detector


def make_detector(spec: dict[str, Any]) -> Detector:
    name = spec["name"]
    params = dict(spec.get("params", {}) or {})
    if name == "cdc_hgb":
        from dq_framework.detectors.cdc import ConformalDataCleaningHGB

        return ConformalDataCleaningHGB(**params)
    if name == "iforest_row":
        from dq_framework.detectors.iforest import IsolationForestRow

        return IsolationForestRow(**params)
    if name == "cdc_original":
        from dq_framework.detectors.subprocess_adapter import OriginalCDC

        return OriginalCDC(**params)
    if name == "dboost":
        from dq_framework.detectors.dboost import DBoost

        return DBoost(**params)
    if name == "dboost_original":
        from dq_framework.detectors.dboost import OriginalDBoost

        return OriginalDBoost(**params)
    if name in ("sd_outlier", "iqr_outlier", "lucario_core"):
        from dq_framework.detectors import univariate

        cls = {"sd_outlier": univariate.SDOutlier, "iqr_outlier": univariate.IQROutlier,
               "lucario_core": univariate.LucarioCore}[name]
        return cls(**params)
    raise ValueError(f"unknown detector {name}")
