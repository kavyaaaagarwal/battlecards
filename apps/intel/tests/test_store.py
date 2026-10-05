import pytest

from intel.cache import DiskCache
from intel.store import LocalStore, MemoryStore


@pytest.mark.parametrize("make", [lambda p: LocalStore(p), lambda p: MemoryStore()])
def test_round_trip_and_list(tmp_path, make):
    s = make(tmp_path)
    assert s.get_json("runs/abc.json") is None
    s.put_json("runs/abc.json", {"a": 1})
    s.put_json("runs/def.json", {"b": 2})
    s.put_json("cache/x.json", [1])
    assert s.get_json("runs/abc.json") == {"a": 1}
    assert sorted(s.list_keys("runs/")) == ["runs/abc.json", "runs/def.json"]


def test_local_store_rejects_escaping_keys(tmp_path):
    s = LocalStore(tmp_path / "data")
    with pytest.raises(ValueError):
        s.put_json("../escape.json", {})
    with pytest.raises(ValueError):
        s.get_json("/etc/passwd")


def test_cache_respects_ttl_and_skips_empty():
    now = [1000.0]
    cache = DiskCache(MemoryStore(), ttl_hours=1, clock=lambda: now[0])
    calls = []
    fn = lambda: calls.append(1) or {"hits": 3}  # noqa: E731
    assert cache.get_or_set("search", {"q": "x"}, fn) == {"hits": 3}
    assert cache.get_or_set("search", {"q": "x"}, fn) == {"hits": 3}
    assert len(calls) == 1
    now[0] += 3601
    cache.get_or_set("search", {"q": "x"}, fn)
    assert len(calls) == 2
    assert cache.get_or_set("search", {"q": "empty"}, lambda: []) == []
    assert cache.store.get_json(cache._key("search", {"q": "empty"})) is None


def test_cache_disabled_when_ttl_zero():
    cache = DiskCache(MemoryStore(), ttl_hours=0)
    calls = []
    for _ in range(2):
        cache.get_or_set("s", "k", lambda: calls.append(1) or {"v": 1})
    assert len(calls) == 2


from types import SimpleNamespace  # noqa: E402

from vercel.blob import BlobNotFoundError  # noqa: E402

from intel.store import BlobStore  # noqa: E402


class FakeBlobClient:
    """Mirrors vercel.blob.AsyncBlobClient: get() returns .content bytes, raises when missing."""

    def __init__(self):
        self.objects, self.get_kwargs = {}, []

    async def put(self, path, body, *, access, overwrite):
        self.objects[path] = body

    async def get(self, path, *, access, use_cache):
        self.get_kwargs.append({"access": access, "use_cache": use_cache})
        if path not in self.objects:
            raise BlobNotFoundError()
        return SimpleNamespace(status_code=200, content=self.objects[path])


def test_blob_store_round_trip(monkeypatch):
    client = FakeBlobClient()
    monkeypatch.setattr("intel.store._list_blobs",
                        lambda prefix: [k for k in client.objects if k.startswith(prefix)])
    s = BlobStore(client=client)
    s.put_json("runs/a.json", {"x": 1})
    assert s.get_json("runs/a.json") == {"x": 1}
    assert s.get_json("runs/missing.json") is None
    assert s.list_keys("runs/") == ["runs/a.json"]
    # run documents change after every stage - reads must never come from a cache
    assert all(k == {"access": "private", "use_cache": False} for k in client.get_kwargs)
