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


class _FakeKaggleApi:
    """Stands in for the official client: writes ``<file>.zip`` as Kaggle does."""

    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = []

    def dataset_download_file(self, dataset, file_name, path=None, force=False, quiet=True):
        self.calls.append((dataset, file_name))
        with zipfile.ZipFile(f"{path}/{file_name}.zip", "w") as z:
            z.writestr(file_name, self.payload)


def _kaggle_spec(sha256=None):
    raw = {"optional": True, "acquisition": {"source": "kaggle", "kaggle_dataset": "owner/slug"}}
    return DatasetSpec("kdemo", "kdemo", [FileSpec("Base.csv", "https://example.org", path="Base.csv", sha256=sha256)], raw)


def test_kaggle_acquisition_extracts_hashes_and_cleans_up(tmp_path, monkeypatch):
    from dq_framework.acquisition.kaggle import acquire_kaggle

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "MANIFEST_DIR", tmp_path / "manifests")
    payload = b"fraud_bool,income\n0,0.5\n"
    spec = _kaggle_spec(acquisition.sha256_bytes(payload))
    assert spec.source == "kaggle" and spec.optional and not spec.manual
    api = _FakeKaggleApi(payload)
    res = acquire_kaggle(spec, api=api)
    assert res["status"] == "VERIFIED"
    p = tmp_path / "raw" / "kdemo" / "Base.csv"
    assert p.read_bytes() == payload
    assert not (p.stat().st_mode & stat.S_IWUSR), "raw file must be read-only"
    assert sorted(x.name for x in p.parent.iterdir()) == ["Base.csv"], "staging directory must be removed"
    assert (tmp_path / "manifests" / "kdemo.acquisition.json").exists()
    acquire_kaggle(spec, api=api)
    assert len(api.calls) == 1, "present file must not be re-downloaded"


def test_kaggle_hash_mismatch_fails_and_leaves_no_file(tmp_path, monkeypatch):
    from dq_framework.acquisition.kaggle import acquire_kaggle

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    with pytest.raises(AcquisitionError, match="sha256 mismatch"):
        acquire_kaggle(_kaggle_spec("0" * 64), api=_FakeKaggleApi(b"a\n1\n"))
    assert not list((tmp_path / "raw" / "kdemo").iterdir())


def test_kaggle_client_error_is_reported_with_cause(tmp_path, monkeypatch):
    from dq_framework.acquisition.kaggle import acquire_kaggle

    class Failing:
        def dataset_download_file(self, *a, **k):
            raise RuntimeError("403 Client Error: Forbidden for url")

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    with pytest.raises(AcquisitionError, match="accept the dataset's terms"):
        acquire_kaggle(_kaggle_spec(), api=Failing())


def test_baf_is_optional_and_never_a_required_dataset():
    reg = acquisition.load_registry()
    assert reg["baf"].optional and reg["baf"].source == "kaggle"
    assert all(not s.optional for k, s in reg.items() if k != "baf")
