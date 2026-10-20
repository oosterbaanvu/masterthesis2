"""Offline tests for the published benchmark extensions; no third-party data required."""
from pathlib import Path

import pytest
import yaml
from scripts.qualify_published_pairs import audit, compare_pair, main, numerically_equivalent
from scripts.register_published_benchmarks import apply

from dq_framework import paths
from dq_framework.acquisition import DatasetSpec, load_registry, sha256_bytes
from dq_framework.datasets import check_table_shape


def test_number_formatting_is_not_a_value_error():
    assert numerically_equivalent("3504.", "3504.0")
    assert numerically_equivalent("2e2", "200")
    assert not numerically_equivalent("12", "13")
    assert not numerically_equivalent("abc", "abc")


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", "", "?"])
def test_nonfinite_or_missing_values_are_not_numeric_equivalents(value):
    assert not numerically_equivalent(value, value)


def test_pair_audit(tmp_path):
    d, c = tmp_path / "dirty.csv", tmp_path / "clean.csv"
    d.write_text("id,Amount,Status\n1,3504.,ok\n2,15.0,bad\n", encoding="utf-8")
    c.write_text("id,Amount,Status\n1,3504.0,ok\n2,25.0,ok\n", encoding="utf-8")
    v = compare_pair(d, c, numeric_columns=("Amount",))
    assert v["rows"] == 2
    assert v["raw_differences"] == 3
    assert v["numeric_format_only"] == 1
    assert v["remaining_candidate_differences"] == 2
    # Numeric-looking identifiers must remain literal unless explicitly declared numeric.
    assert compare_pair(d, c)["remaining_candidate_differences"] == 3


def test_reject_unaligned_pairs(tmp_path):
    d, c = tmp_path / "dirty.csv", tmp_path / "clean.csv"
    d.write_text("a,b\n1,2\n", encoding="utf-8")
    c.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unequal row count"):
        compare_pair(d, c)


@pytest.mark.parametrize(("dirty", "clean", "kwargs", "error"), [
    ("id,v\n1,a\n2,b\n", "id,v\n2,b\n1,a\n", {"alignment_columns": ("id",)}, "Row alignment"),
    ("a,b\n1,2\n", "a,c\n1,2\n", {}, "Incompatible columns"),
    ("a,b\n1\n", "a,b\n1,2\n", {}, "Unequal row width"),
    ("", "a,b\n1,2\n", {}, "header"),
    ("a,b\n", "a,b\n", {}, "data rows"),
    ("a,b\n1,2\n", "a,a\n1,2\n", {"positional_headers": True}, "Duplicated column"),
    ("a,b\n1,2\n", "a,b\n1,2\n", {"numeric_columns": ("typo",)}, "Unknown comparison"),
])
def test_pair_audit_rejects_ambiguous_structure(tmp_path, dirty, clean, kwargs, error):
    d, c = tmp_path / "dirty.csv", tmp_path / "clean.csv"
    d.write_text(dirty, encoding="utf-8")
    c.write_text(clean, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        compare_pair(d, c, **kwargs)


def test_positional_header_mapping_is_explicit(tmp_path):
    d, c = tmp_path / "dirty.csv", tmp_path / "clean.csv"
    d.write_text("old_name\nbad\n", encoding="utf-8")
    c.write_text("new_name\ngood\n", encoding="utf-8")
    assert compare_pair(d, c, positional_headers=True)["by_column_raw"] == {"old_name": 1}


@pytest.mark.parametrize("clean", ["id,v\n1,a\n", "id,w\n1,a\n2,b\n", "id,v\n2,b\n1,a\n"])
def test_table_declaration_does_not_hide_bad_clean_pair(tmp_path, monkeypatch, clean):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path)
    d = tmp_path / "demo"
    d.mkdir()
    (d / "dirty.csv").write_text("id,v\n1,a\n2,b\n", encoding="utf-8")
    (d / "clean.csv").write_text(clean, encoding="utf-8")
    spec = DatasetSpec("demo", "demo", [], raw={
        "table": {"file": "dirty.csv", "format": "csv", "expected_rows": 2, "expected_columns": ["id", "v"]},
        "pair": {"dirty": "dirty.csv", "clean": "clean.csv", "alignment_columns": ["id"]},
    })
    assert not check_table_shape(spec)["ok"]
    assert audit(spec)["status"] == "SHAPE_FAIL"


@pytest.mark.parametrize("explicit", [False, True])
def test_optional_pair_failure_is_skipped_only_when_absent_and_not_requested(tmp_path, monkeypatch, explicit):
    from dq_framework import acquisition

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    spec = load_registry()["jung_cars"]
    monkeypatch.setattr(acquisition, "load_registry", lambda: {"jung_cars": spec})
    monkeypatch.setattr("scripts.qualify_published_pairs.DEFAULT_KEYS", ("jung_cars",))
    monkeypatch.setattr("sys.argv", ["audit", *(["jung_cars"] if explicit else [])])
    assert main() == int(explicit)
    # A corrupt optional pair must fail even in the default run.
    spec.raw_dir.mkdir(parents=True)
    for file in spec.files:
        (spec.raw_dir / file.path).write_bytes(b"bad data\n")
    monkeypatch.setattr("sys.argv", ["audit"])
    assert main() == 1


def test_extension_hashes_and_idempotence(tmp_path):
    source = Path(__file__).resolve().parents[1] / "config" / "published_benchmark_entries.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))["datasets"]
    assert {"raha_rayyan", "jung_restaurant", "jung_cars"} <= set(data)
    for key, spec in data.items():
        assert spec["cell_error_ground_truth"]
        assert len(spec["acquisition"]["files"]) == 2
        for f in spec["acquisition"]["files"]:
            assert len(bytes.fromhex(f["sha256"])) == 32
            commit = spec["version"].split("commit ")[1].split(";")[0]
            assert f"/{commit}/" in f["url"]
        assert load_registry()[key].raw == spec
    config = tmp_path / "config"
    config.mkdir()
    (config / "datasets.yaml").write_text("datasets:\n  old_data:\n    title: old\n", encoding="utf-8")
    (config / "published_benchmark_entries.yaml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    before = (config / "datasets.yaml").read_bytes()
    assert len(apply(tmp_path, dry_run=True)) == 3
    assert (config / "datasets.yaml").read_bytes() == before
    assert len(apply(tmp_path)) == 3
    contents = (config / "datasets.yaml").read_text(encoding="utf-8")
    assert apply(tmp_path) == []
    assert (config / "datasets.yaml").read_text(encoding="utf-8") == contents
    assert yaml.safe_load(contents)["datasets"]["old_data"] == {"title": "old"}
    conflicting = before.decode() + "  jung_cars: {title: conflict}\n"
    (config / "datasets.yaml").write_text(conflicting, encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting"):
        apply(tmp_path)
    assert (config / "datasets.yaml").read_text(encoding="utf-8") == conflicting


def test_audit_refuses_unpinned_or_corrupt_bytes(tmp_path, monkeypatch):
    from dq_framework.acquisition import FileSpec

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path)
    d = tmp_path / "demo"
    d.mkdir()
    for filename in ("dirty.csv", "clean.csv"):
        (d / filename).write_bytes(b"v\na\n")
    spec = DatasetSpec("demo", "demo", [FileSpec("dirty.csv", "file:///unused", path="dirty.csv")], raw={
        "pair": {"dirty": "dirty.csv", "clean": "clean.csv"},
    })
    assert audit(spec)["status"] == "UNPINNED"
    spec.files[0].sha256 = sha256_bytes(b"other bytes")
    assert audit(spec)["status"] == "FAIL"
