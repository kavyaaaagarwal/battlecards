"""Where runs, caches and usage counters live: local files in dev, Vercel Blob when deployed.

Methods are synchronous; never call them from inside a running event loop."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Protocol


class Store(Protocol):
    def get_json(self, key: str) -> Any | None: ...
    def put_json(self, key: str, value: Any) -> None: ...
    def list_keys(self, prefix: str) -> list[str]: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if key.startswith("/") or not p.is_relative_to(self.root):
            raise ValueError(f"Store key escapes the store: {key!r}")
        return p

    def get_json(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None

    def put_json(self, key: str, value: Any) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False))
        tmp.replace(p)  # atomic: readers never see a half-written file

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix.rstrip("/")) if prefix.strip("/") else self.root
        if not base.exists():
            return []
        return [p.relative_to(self.root).as_posix() for p in base.rglob("*.json")]


class MemoryStore:
    """For tests."""

    def __init__(self):
        self.data: dict[str, str] = {}

    def get_json(self, key: str) -> Any | None:
        return json.loads(self.data[key]) if key in self.data else None

    def put_json(self, key: str, value: Any) -> None:
        self.data[key] = json.dumps(value)

    def list_keys(self, prefix: str) -> list[str]:
        return [k for k in self.data if k.startswith(prefix)]


def _list_blobs(prefix: str) -> list[str]:
    from vercel.blob import list_objects

    keys, cursor = [], None
    while True:
        page = list_objects(prefix=prefix, limit=1000, cursor=cursor)
        keys += [b.pathname for b in page.blobs]
        cursor = getattr(page, "cursor", None)
        if not getattr(page, "has_more", False) or not cursor:
            return keys


class BlobStore:
    """Vercel Blob (private). Sync wrapper over the async SDK; call from worker threads only."""

    def __init__(self, client=None):
        if client is None:
            from vercel.blob import AsyncBlobClient

            client = AsyncBlobClient()
        self.client = client

    def get_json(self, key: str) -> Any | None:
        from vercel.blob import BlobNotFoundError

        async def go():
            try:
                # use_cache=False: run documents change after every stage
                return await self.client.get(key, access="private", use_cache=False)
            except BlobNotFoundError:
                return None

        res = asyncio.run(go())
        if res is None or res.status_code != 200 or not res.content:
            return None
        return json.loads(res.content)

    def put_json(self, key: str, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        asyncio.run(self.client.put(key, body, access="private", overwrite=True))

    def list_keys(self, prefix: str) -> list[str]:
        return _list_blobs(prefix)


def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")


BLOB_TOKEN_VARS = ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN")  # the names the Blob SDK reads


class StorageNotConfigured(RuntimeError):
    """On Vercel without a Blob token: the filesystem is read-only, so there is nowhere to save runs."""


def make_store() -> Store:
    if any(os.getenv(v) for v in BLOB_TOKEN_VARS):
        return BlobStore()
    if os.getenv("VERCEL"):
        raise StorageNotConfigured(
            "Storage isn't connected. In Vercel, create a Blob store (Storage tab), connect it to this "
            "project for Production, then redeploy. BLOB_READ_WRITE_TOKEN must appear in Environment Variables."
        )
    return LocalStore(data_dir())
