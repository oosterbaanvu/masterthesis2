#!/usr/bin/env python3
"""Idempotently append literature benchmark entries to config/datasets.yaml.

This intentionally preserves the main registry's comments/formatting rather than
rewriting its existing YAML. Review the diff before committing to Git.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def apply(root: Path, dry_run: bool = False) -> list[str]:
    base_path = root / "config" / "datasets.yaml"
    extension_path = root / "config" / "published_benchmark_entries.yaml"
    if not base_path.is_file() or not extension_path.is_file():
        raise FileNotFoundError("Run from a checkout with config/datasets.yaml and config/published_benchmark_entries.yaml")
    old = base_path.read_text(encoding="utf-8")
    extension = extension_path.read_text(encoding="utf-8")
    present = yaml.safe_load(old)["datasets"]
    additions = yaml.safe_load(extension)["datasets"]
    duplicate = set(additions) & set(present)
    if duplicate:
        if len(duplicate) == len(additions) and all(present[k] == additions[k] for k in additions):
            return []  # Already installed, byte-for-byte no-op.
        raise ValueError(f"Conflicting or partial registration, investigate manually: {sorted(duplicate)}")
    tail = extension.split("\ndatasets:\n", 1)
    if len(tail) != 2:
        raise ValueError("Expected one YAML datasets section in extension")
    updated = old.rstrip() + "\n\n# Published literature benchmark extensions (see docs/published_benchmark_datasets.md)\n" + tail[1].rstrip() + "\n"
    merged = yaml.safe_load(updated)["datasets"]
    if (any(merged[k] != additions[k] for k in additions)
            or any(merged[k] != present[k] for k in present)
            or len(merged) != len(present) + len(additions)):
        raise ValueError("YAML round-trip validation failed; no files modified")
    if not dry_run:
        base_path.write_text(updated, encoding="utf-8")
    return list(additions)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    added = apply(root, dry_run=args.dry_run)
    print(("Would register" if args.dry_run else "Registered") + ": " + (", ".join(added) if added else "already present"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
