"""Which registered datasets are present locally, and which are correctly verified?

Read-only: hashes and shapes are re-checked, nothing is downloaded or modified. The result is written to
``data/local_manifest.json`` (git-ignored: it describes this machine, not the repository).

Status per dataset:

* ``VERIFIED``  every pinned file present, SHA-256 matches, table shape as declared
* ``ABSENT``    no file present (``optional`` datasets: not a failure)
* ``PARTIAL``   some files present, others missing
* ``FAIL``      a hash or shape mismatch
* ``UNPINNED``  present but at least one hash is not pinned yet

For Kaggle datasets the credential *source* (environment variable or file name) is reported, never its value.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from dq_framework import paths
from dq_framework.acquisition import DatasetSpec, load_registry, verify


def _expected_files(spec: DatasetSpec) -> list[str]:
    out: list[str] = []
    for f in spec.files:
        out += [e.path for e in f.extract] if f.extract else [f.path or f.name]
    return out


def auth_requirement(spec: DatasetSpec) -> str:
    if spec.source == "kaggle":
        return "Kaggle account + API token: KAGGLE_API_TOKEN (or KAGGLE_USERNAME/KAGGLE_KEY, ~/.kaggle/access_token)"
    if spec.manual:
        return "manual download"
    return "none (public URL)"


def dataset_status(spec: DatasetSpec, check_shape: bool = True) -> dict[str, Any]:
    expected = _expected_files(spec)
    present = [p for p in expected if (spec.raw_dir / p).exists()]
    rec: dict[str, Any] = {
        "dataset": spec.key,
        "title": spec.title,
        "optional": spec.optional,
        "source": spec.source,
        "authentication": auth_requirement(spec),
        "licence": spec.raw.get("licence"),
        "version": spec.raw.get("version"),
        "roles": spec.raw.get("roles", []),
        "files_expected": len(expected),
        "files_present": len(present),
        "problems": [],
        "note": spec.raw.get("status"),
    }
    if spec.source == "kaggle":
        from dq_framework.acquisition.kaggle import credential_source

        rec["credential_source"] = credential_source() or "none found"
    if not present:
        rec["status"] = "ABSENT"
        return rec
    v = verify(spec)
    rec["files"] = [{k: f[k] for k in ("path", "sha256", "bytes", "writable")} for f in v["files"]]
    rec["problems"] = v["problems"] + v["unpinned"]
    if len(present) < len(expected):
        rec["status"] = "PARTIAL"
        return rec
    rec["status"] = v["status"]
    if rec["status"] == "VERIFIED" and check_shape:
        from dq_framework.datasets import check_table_shape

        shape = check_table_shape(spec)
        rec["shape"] = shape["summary"]
        if not shape["ok"]:
            rec["status"] = "FAIL"
            rec["problems"] += shape["problems"]
    writable = [f["path"] for f in rec.get("files", []) if f["writable"]]
    if writable:
        rec["warnings"] = [f"raw files writable (expected read-only): {writable}"]
    return rec


def collect(keys: list[str] | None = None, check_shape: bool = True) -> dict[str, Any]:
    reg = load_registry()
    keys = keys or list(reg)
    return {
        "checked_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "raw_dir": str(paths.RAW_DIR),
        "datasets": [dataset_status(reg[k], check_shape=check_shape) for k in keys],
    }


def write_local_manifest(report: dict[str, Any], path: Path | None = None) -> Path:
    path = path or paths.DATA_DIR / "local_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def format_table(report: dict[str, Any]) -> str:
    head = f"{'dataset':<20} {'status':<9} {'files':<6} {'optional':<8} {'shape':<40} authentication"
    lines = [head, "-" * len(head)]
    for r in report["datasets"]:
        lines.append(f"{r['dataset']:<20} {r['status']:<9} {r['files_present']}/{r['files_expected']:<4} "
                     f"{'yes' if r['optional'] else 'no':<8} {r.get('shape', '-'):<40} {r['authentication']}")
        for p in r["problems"] + r.get("warnings", []):
            lines.append(f"    - {p}")
        if r.get("note") and r["status"] != "VERIFIED":
            lines.append(f"    note: {r['note']}")
        if "credential_source" in r:
            lines.append(f"    credentials: {r['credential_source']}")
    return "\n".join(lines)
