"""Reproducible dataset acquisition and verification.

Every dataset is declared in ``config/datasets.yaml``: authoritative URL, pinned
version (commit or archive hash), expected SHA-256 per file, members to extract
from (possibly nested) zip archives, and the expected table shape.

Design rules
------------
* Raw files are written once to ``data/raw/<dataset>/`` and made read-only.
* A download is accepted only if its SHA-256 matches the pinned hash. When no
  hash is pinned yet (first acquisition), the observed hash is reported and must
  be pinned by a human before the dataset is considered verified.
* Partial downloads go to a ``.part`` file and are renamed only after the
  hash check, so an interrupted run never leaves a file that looks complete.
* Kaggle-hosted datasets (``source: kaggle``) go through the official client in
  :mod:`dq_framework.acquisition.kaggle`, an optional extra.
* A manifest with URL, acquisition time, size and hash is written to
  ``data/manifests/<dataset>.acquisition.json``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import stat
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dq_framework import paths

CHUNK = 1 << 20


class AcquisitionError(RuntimeError):
    """Raised when a download or verification step fails."""


@dataclass
class ExtractSpec:
    member: str  # path inside the archive; nested archives separated by '!/' e.g. 'a.zip!/b.csv'
    path: str  # destination path relative to data/raw/<dataset>/
    sha256: str | None = None


@dataclass
class FileSpec:
    name: str
    url: str
    path: str | None = None  # destination for non-archive files
    sha256: str | None = None
    extract: list[ExtractSpec] = field(default_factory=list)
    keep_archive: bool = False


@dataclass
class DatasetSpec:
    key: str
    title: str
    files: list[FileSpec]
    raw: dict[str, Any]

    @property
    def raw_dir(self) -> Path:
        return paths.RAW_DIR / self.key

    @property
    def manual(self) -> bool:
        return bool(self.raw.get("acquisition", {}).get("manual", False))

    @property
    def source(self) -> str:
        """``http`` (default: plain URL download) or ``kaggle`` (official client, optional extra)."""
        return self.raw.get("acquisition", {}).get("source", "http")

    @property
    def optional(self) -> bool:
        """Optional datasets are skipped unless requested by name; their absence is not a failure."""
        return bool(self.raw.get("optional", False))


def load_registry(path: Path | None = None) -> dict[str, DatasetSpec]:
    path = path or (paths.CONFIG_DIR / "datasets.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    out: dict[str, DatasetSpec] = {}
    for key, raw in doc["datasets"].items():
        files = []
        for f in raw.get("acquisition", {}).get("files", []):
            files.append(
                FileSpec(
                    name=f["name"],
                    url=f["url"],
                    path=f.get("path"),
                    sha256=f.get("sha256"),
                    extract=[ExtractSpec(**e) for e in f.get("extract", [])],
                    keep_archive=f.get("keep_archive", False),
                )
            )
        out[key] = DatasetSpec(key=key, title=raw.get("title", key), files=files, raw=raw)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(url: str, dest: Path, timeout: int = 120) -> tuple[str, int]:
    """Stream ``url`` to ``dest.part``; return (sha256, size). Caller renames after checks."""
    part = dest.with_name(dest.name + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "dq-framework/0.1 (research; reproducible download)"})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
        expected_len = resp.headers.get("Content-Length")
        for chunk in iter(lambda: resp.read(CHUNK), b""):
            out.write(chunk)
            h.update(chunk)
            size += len(chunk)
    if expected_len is not None and int(expected_len) != size:
        part.unlink(missing_ok=True)
        raise AcquisitionError(f"Truncated download for {url}: got {size} of {expected_len} bytes")
    return h.hexdigest(), size


def _read_member(archive_bytes: bytes, member: str) -> bytes:
    """Read a (possibly nested, '!/'-separated) member from zip bytes."""
    parts = member.split("!/")
    data = archive_bytes
    for part in parts:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            try:
                data = zf.read(part)
            except KeyError as exc:
                raise AcquisitionError(f"Archive member not found: {part!r} (in {member!r})") from exc
    return data


def _make_read_only(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    _make_read_only(path)


def _check_hash(observed: str, pinned: str | None, what: str, problems: list[str], unpinned: list[str]) -> None:
    if pinned is None:
        unpinned.append(f"{what}: observed sha256 {observed} (not pinned)")
    elif observed != pinned:
        problems.append(f"{what}: sha256 mismatch, expected {pinned}, observed {observed}")


def acquire(spec: DatasetSpec, force: bool = False) -> dict[str, Any]:
    """Download and extract one dataset; returns the acquisition manifest."""
    if spec.manual:
        return verify(spec)
    if spec.source == "kaggle":
        from dq_framework.acquisition.kaggle import acquire_kaggle

        return acquire_kaggle(spec, force=force)
    problems: list[str] = []
    unpinned: list[str] = []
    records: list[dict[str, Any]] = []
    for f in spec.files:
        targets = [spec.raw_dir / e.path for e in f.extract] or [spec.raw_dir / (f.path or f.name)]
        if not force and all(t.exists() for t in targets):
            # Already present: verify instead of re-downloading.
            continue
        archive_dest = spec.raw_dir / "_archives" / f.name
        digest, size = _download(f.url, archive_dest)
        part = archive_dest.with_name(archive_dest.name + ".part")
        _check_hash(digest, f.sha256, f"{spec.key}/{f.name}", problems, unpinned)
        if problems:
            part.unlink(missing_ok=True)
            raise AcquisitionError("; ".join(problems))
        rec: dict[str, Any] = {
            "file": f.name,
            "url": f.url,
            "sha256": digest,
            "bytes": size,
            "retrieved_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "extracted": [],
        }
        if f.extract:
            blob = part.read_bytes()
            for e in f.extract:
                data = _read_member(blob, e.member)
                d = sha256_bytes(data)
                _check_hash(d, e.sha256, f"{spec.key}/{e.path}", problems, unpinned)
                if problems:
                    part.unlink(missing_ok=True)
                    raise AcquisitionError("; ".join(problems))
                _write_immutable(spec.raw_dir / e.path, data)
                rec["extracted"].append({"member": e.member, "path": e.path, "sha256": d, "bytes": len(data)})
            if f.keep_archive:
                os.replace(part, archive_dest)
                _make_read_only(archive_dest)
            else:
                part.unlink(missing_ok=True)
        else:
            dest = spec.raw_dir / (f.path or f.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest.chmod(dest.stat().st_mode | stat.S_IWUSR)
            os.replace(part, dest)
            _make_read_only(dest)
            rec["path"] = f.path or f.name
        records.append(rec)
    manifest = verify(spec)
    if records:
        manifest["downloads"] = records
        manifest["unpinned_at_download"] = unpinned
        _write_manifest(spec, manifest)
    return manifest


def verify(spec: DatasetSpec) -> dict[str, Any]:
    """Re-hash every expected raw file against the pinned hashes. Never modifies data."""
    problems: list[str] = []
    unpinned: list[str] = []
    files: list[dict[str, Any]] = []
    expected: list[tuple[str, str | None]] = []
    for f in spec.files:
        if f.extract:
            expected += [(e.path, e.sha256) for e in f.extract]
        else:
            expected.append((f.path or f.name, f.sha256))
    for rel, pinned in expected:
        p = spec.raw_dir / rel
        if not p.exists():
            problems.append(f"missing file {p.relative_to(paths.ROOT)}")
            continue
        d = sha256_file(p)
        _check_hash(d, pinned, f"{spec.key}/{rel}", problems, unpinned)
        writable = bool(p.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        files.append({"path": rel, "sha256": d, "bytes": p.stat().st_size, "writable": writable})
    status = "FAIL" if problems else ("UNPINNED" if unpinned else "VERIFIED")
    return {
        "dataset": spec.key,
        "title": spec.title,
        "status": status,
        "checked_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "files": files,
        "problems": problems,
        "unpinned": unpinned,
    }


def _write_manifest(spec: DatasetSpec, manifest: dict[str, Any]) -> Path:
    paths.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = paths.MANIFEST_DIR / f"{spec.key}.acquisition.json"
    meta = {k: spec.raw.get(k) for k in ("landing_page", "licence", "version", "citation")}
    out.write_text(json.dumps({**meta, **manifest}, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return out
