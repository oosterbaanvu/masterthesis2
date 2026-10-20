"""Repository hygiene: no secrets, no raw third-party data, no large files in git."""

import re
import subprocess

import pytest

from dq_framework import paths

SECRET_PATTERNS = [
    r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}", r"KGAT_[A-Za-z0-9]{16,}", r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r'"key"\s*:\s*"[a-f0-9]{32}"',  # legacy kaggle.json
]


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=paths.ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ln for ln in out.splitlines() if ln]


def test_no_secrets_in_tracked_files():
    rx = re.compile("|".join(SECRET_PATTERNS))
    hits = []
    for f in _tracked():
        p = paths.ROOT / f
        if not p.is_file() or p.stat().st_size > 5_000_000:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{f}: {m.group(0)[:8]}..." for m in rx.finditer(text)]
    assert not hits, hits


def test_no_raw_data_or_large_files_tracked():
    bad = [f for f in _tracked() if f.startswith("data/raw/") and not f.endswith("README.md")]
    bad += [f for f in _tracked() if f.endswith((".parquet", ".duckdb", ".xls", ".zip", ".pkl"))]
    big = [f for f in _tracked() if (paths.ROOT / f).is_file() and (paths.ROOT / f).stat().st_size > 1_000_000
           and f != "uv.lock"]
    assert not bad, bad
    assert not big, big
