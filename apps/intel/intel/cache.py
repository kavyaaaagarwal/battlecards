"""Small cache for search results, pages and API calls, kept in the Store so it survives
between serverless invocations. Empty/failed results are never cached."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from .store import Store


class DiskCache:
    def __init__(self, store: Store, ttl_hours: float, clock: Callable[[], float] = time.time):
        self.store = store
        self.ttl = ttl_hours * 3600
        self.enabled = ttl_hours > 0
        self.clock = clock

    def _key(self, namespace: str, key: Any) -> str:
        digest = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()
        return f"cache/{namespace}/{digest}.json"

    def get_or_set(self, namespace: str, key: Any, fn: Callable[[], Any]) -> Any:
        k = self._key(namespace, key)
        if self.enabled:
            hit = self.store.get_json(k)
            if isinstance(hit, dict) and self.clock() - hit.get("saved_at", 0) < self.ttl:
                return hit.get("value")
        value = fn()
        if self.enabled and value:
            self.store.put_json(k, {"saved_at": self.clock(), "value": value})
        return value
