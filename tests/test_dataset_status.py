import os

from dq_framework import acquisition, paths
from dq_framework.acquisition import DatasetSpec, FileSpec
from dq_framework.acquisition.status import dataset_status, format_table, write_local_manifest


def _spec(tmp_path, sha, optional=False, source="http"):
    raw = {"optional": optional, "acquisition": {"source": source}, "licence": "x"}
    return DatasetSpec("demo", "demo", [FileSpec("a.csv", "file:///nowhere", path="a.csv", sha256=sha),
                                        FileSpec("b.csv", "file:///nowhere", path="b.csv", sha256=sha)], raw=raw)


def test_status_absent_partial_verified_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    d = tmp_path / "raw" / "demo"
    payload = b"a\n1\n"
    sha = acquisition.sha256_bytes(payload)
    assert dataset_status(_spec(tmp_path, sha), check_shape=False)["status"] == "ABSENT"
    d.mkdir(parents=True)
    (d / "a.csv").write_bytes(payload)
    assert dataset_status(_spec(tmp_path, sha), check_shape=False)["status"] == "PARTIAL"
    (d / "b.csv").write_bytes(payload)
    rec = dataset_status(_spec(tmp_path, sha), check_shape=False)
    assert rec["status"] == "VERIFIED"
    assert rec["warnings"], "writable raw files must be reported"
    rec = dataset_status(_spec(tmp_path, "0" * 64), check_shape=False)
    assert rec["status"] == "FAIL" and "mismatch" in rec["problems"][0]


def test_kaggle_status_reports_credential_source_never_the_value(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secret-value-123")
    rec = dataset_status(_spec(tmp_path, "0" * 64, optional=True, source="kaggle"), check_shape=False)
    assert rec["status"] == "ABSENT" and rec["optional"]
    assert rec["credential_source"] == "KAGGLE_API_TOKEN environment variable"
    report = {"checked_utc": "t", "raw_dir": "x", "datasets": [rec]}
    out = write_local_manifest(report, tmp_path / "m.json")
    assert "secret-value-123" not in out.read_text()
    assert "secret-value-123" not in format_table(report)
    assert os.environ["KAGGLE_API_TOKEN"] == "secret-value-123"
