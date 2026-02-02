import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    expires_at: float
    value: Any


class TTLCache:
    def __init__(self, *, max_items: int = 5000, ttl_s: int = 86400) -> None:
        self._max_items = max(1, int(max_items or 1))
        self._ttl_s = max(1, int(ttl_s or 1))
        self._items: dict[str, _Entry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._evict_if_needed()
        self._items[key] = _Entry(expires_at=time.time() + self._ttl_s, value=value)

    def _evict_if_needed(self) -> None:
        if len(self._items) < self._max_items:
            return
        now = time.time()
        for k in list(self._items.keys()):
            if self._items.get(k) and self._items[k].expires_at <= now:
                self._items.pop(k, None)
        while len(self._items) >= self._max_items and self._items:
            self._items.pop(next(iter(self._items)), None)


def stable_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_hash_key(prefix: str, payload: Any) -> str:
    blob = stable_json_dumps(payload)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"
