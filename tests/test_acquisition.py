import io
import stat
import zipfile

import pytest

from dq_framework import acquisition, paths
from dq_framework.acquisition import AcquisitionError, DatasetSpec, ExtractSpec, FileSpec


def _nested_zip(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("folder/data.csv", "a,b\n1,2\n")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("inner.zip", inner.getvalue())
        z.writestr("readme.txt", "hello")
    return outer


def test_acquire_nested_zip_verifies_hash_and_makes_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "MANIFEST_DIR", tmp_path / "manifests")
    outer = _nested_zip(tmp_path)
    member_sha = acquisition.sha256_bytes(b"a,b\n1,2\n")
    spec = DatasetSpec("demo", "demo", [FileSpec("outer.zip", outer.as_uri(), sha256=acquisition.sha256_file(outer),
                                                 extract=[ExtractSpec("inner.zip!/folder/data.csv", "data.csv", member_sha)])], raw={})
    res = acquisition.acquire(spec)
    assert res["status"] == "VERIFIED"
    p = tmp_path / "raw" / "demo" / "data.csv"
    assert p.read_text() == "a,b\n1,2\n"
    assert not (p.stat().st_mode & stat.S_IWUSR), "raw file must be read-only"
    assert (tmp_path / "manifests" / "demo.acquisition.json").exists()


def test_hash_mismatch_fails_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    outer = _nested_zip(tmp_path)
    spec = DatasetSpec("demo", "demo", [FileSpec("outer.zip", outer.as_uri(), sha256="0" * 64,
                                                 extract=[ExtractSpec("readme.txt", "readme.txt")])], raw={})
    with pytest.raises(AcquisitionError, match="sha256 mismatch"):
        acquisition.acquire(spec)
    assert not (tmp_path / "raw" / "demo" / "readme.txt").exists()
    assert not list((tmp_path / "raw" / "demo" / "_archives").glob("*.part"))


def test_unpinned_hash_is_reported_not_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "MANIFEST_DIR", tmp_path / "manifests")
    f = tmp_path / "x.csv"
    f.write_text("a\n1\n")
    spec = DatasetSpec("demo", "demo", [FileSpec("x.csv", f.as_uri(), path="x.csv")], raw={})
    assert acquisition.acquire(spec)["status"] == "UNPINNED"


def test_registry_pins_every_automatic_file():
    reg = acquisition.load_registry()
    for key, spec in reg.items():
        if spec.manual:
            continue
        for f in spec.files:
            assert f.sha256, f"{key}/{f.name} has no pinned archive hash"
            for e in f.extract:
                assert e.sha256, f"{key}/{e.path} has no pinned member hash"
