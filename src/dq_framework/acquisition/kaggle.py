"""Optional acquisition from Kaggle through the official ``kaggle`` client (used for BAF).

The client is an optional extra (``uv sync --extra kaggle`` or ``pip install kaggle``); the rest of the
framework never imports it. Authentication follows the official client, in this order: the
``KAGGLE_API_TOKEN`` environment variable, ``KAGGLE_USERNAME`` + ``KAGGLE_KEY``, or a credentials file in
``~/.kaggle/`` (or ``KAGGLE_CONFIG_DIR``). Credentials are never printed, logged or written to manifests.

Kaggle serves single files as a zip archive. The archive is not a stable artefact (Kaggle may re-compress
it), so the pinned SHA-256 is that of the extracted file, which is what the framework reads.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import os
import shutil
import stat
import zipfile
from pathlib import Path
from typing import Any

from dq_framework.acquisition import (
    CHUNK,
    AcquisitionError,
    DatasetSpec,
    _check_hash,
    _make_read_only,
    _write_manifest,
    sha256_file,
    verify,
)

INSTALL_HINT = "install the optional extra: `uv sync --extra kaggle` (or `pip install kaggle`)"


def credential_source() -> str | None:
    """Describe which credential the official client will find, without reading or revealing it."""
    if os.environ.get("KAGGLE_API_TOKEN"):
        return "KAGGLE_API_TOKEN environment variable"
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return "KAGGLE_USERNAME/KAGGLE_KEY environment variables"
    cfg = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    for name in ("access_token", "kaggle.json"):
        if (cfg / name).exists():
            return f"{cfg / name}"
    return None


def likely_cause(exc: BaseException) -> str:
    """Map a client error to its most likely cause (heuristic, from the error text only)."""
    text = f"{type(exc).__name__}: {exc}"
    if "401" in text or "Unauthorized" in text:
        return "credentials rejected: the token is invalid, expired or revoked (create a new one on kaggle.com/settings)"
    if "403" in text or "Forbidden" in text:
        return ("access refused: accept the dataset's terms on its Kaggle page while logged in, "
                "or the token lacks permission")
    if "404" in text or "Not Found" in text:
        return "dataset or file name not found (check the dataset slug and file name)"
    if any(k in text for k in ("ConnectionError", "ProxyError", "SSLError", "Timeout", "NameResolution")):
        return "network problem: no route to kaggle.com, a proxy blocks it, or TLS verification failed"
    return "unknown; see the error text"


def authenticate() -> Any:
    """Return an authenticated ``KaggleApi``; raise :class:`AcquisitionError` with the likely cause."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise AcquisitionError(f"The Kaggle client is not installed; {INSTALL_HINT}") from exc
    api = KaggleApi()
    try:
        api.authenticate()
    except (Exception, SystemExit) as exc:  # the client calls sys.exit when it cannot authenticate
        if credential_source() is None:
            cause = ("no credentials found: set KAGGLE_API_TOKEN (kaggle.com > Settings > API > Generate New "
                     "Token), save it to ~/.kaggle/access_token, or run `kaggle auth login`")
        elif isinstance(exc, SystemExit):
            cause = (f"credentials from {credential_source()} were rejected: token invalid, expired or revoked, "
                     "or kaggle.com unreachable to check it")
        else:
            cause = likely_cause(exc)
        raise AcquisitionError(f"Kaggle authentication failed ({type(exc).__name__}). Likely cause: {cause}") from exc
    return api


def _extract_hashed(downloaded: Path, member: str, dest_part: Path) -> tuple[str, int]:
    """Copy ``member`` out of a Kaggle zip (or the plain file) to ``dest_part``, streaming and hashing."""
    h = hashlib.sha256()
    size = 0
    with contextlib.ExitStack() as stack:
        if zipfile.is_zipfile(downloaded):
            zf = stack.enter_context(zipfile.ZipFile(downloaded))
            if member not in zf.namelist():
                raise AcquisitionError(f"Archive member {member!r} not found in {downloaded.name}: {zf.namelist()}")
            src = stack.enter_context(zf.open(member))
        else:
            src = stack.enter_context(open(downloaded, "rb"))
        out = stack.enter_context(open(dest_part, "wb"))
        for chunk in iter(lambda: src.read(CHUNK), b""):
            out.write(chunk)
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def acquire_kaggle(spec: DatasetSpec, force: bool = False, api: Any = None) -> dict[str, Any]:
    """Download the registry's files of one Kaggle dataset into ``data/raw/<key>/`` (read-only)."""
    acq = spec.raw["acquisition"]
    competition = acq.get("kaggle_competition")
    dataset = competition or acq["kaggle_dataset"]
    todo = [f for f in spec.files if force or not (spec.raw_dir / (f.path or f.name)).exists()]
    records: list[dict[str, Any]] = []
    unpinned: list[str] = []
    if todo:
        api = api or authenticate()
        staging = spec.raw_dir / "_kaggle_download.part"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            for f in todo:
                try:
                    if competition:
                        api.competition_download_file(competition, f.name, path=str(staging), force=True, quiet=False)
                    else:
                        api.dataset_download_file(dataset, f.name, path=str(staging), force=True, quiet=False)
                except (Exception, SystemExit) as exc:
                    cause = likely_cause(exc)
                    if competition and ("403" in str(exc) or "Forbidden" in str(exc)):
                        cause = (f"the competition rules are not accepted for this account: log in on kaggle.com, open "
                                 f"https://www.kaggle.com/competitions/{competition}/rules and accept them, then retry")
                    raise AcquisitionError(
                        f"Kaggle download of {dataset}/{f.name} failed: {type(exc).__name__}: {exc}. Likely cause: {cause}"
                    ) from exc
                got = sorted(p for p in staging.iterdir() if p.name in (f.name, f.name + ".zip"))
                if not got:
                    raise AcquisitionError(f"Kaggle reported success but no file for {f.name} in {staging}")
                downloaded = got[-1]
                dest = spec.raw_dir / (f.path or f.name)
                part = staging / (dest.name + ".extracted")
                digest, size = _extract_hashed(downloaded, f.name, part)
                problems: list[str] = []
                _check_hash(digest, f.sha256, f"{spec.key}/{f.path or f.name}", problems, unpinned)
                if problems:
                    raise AcquisitionError("; ".join(problems))
                if dest.exists():
                    dest.chmod(dest.stat().st_mode | stat.S_IWUSR)
                os.replace(part, dest)
                _make_read_only(dest)
                records.append({
                    "file": f.name,
                    "url": f"kaggle://{'competitions/' if competition else ''}{dataset}/{f.name}",
                    "archive": downloaded.name if zipfile.is_zipfile(downloaded) else None,
                    "archive_sha256": sha256_file(downloaded),
                    "archive_bytes": downloaded.stat().st_size,
                    "sha256": digest,
                    "bytes": size,
                    "path": f.path or f.name,
                    "retrieved_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                })
                downloaded.unlink()
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    manifest = verify(spec)
    if records:
        manifest["downloads"] = records
        manifest["unpinned_at_download"] = unpinned
        _write_manifest(spec, manifest)
    return manifest
