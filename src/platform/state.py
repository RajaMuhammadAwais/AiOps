"""Thread-safe bounded state primitives for the adapter layer."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
from typing import Any, Deque, Dict, Iterable


class BoundedStore:
    """Bounded append-only collections with snapshot semantics."""

    def __init__(self, max_entries: int = 1000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._collections: Dict[str, Deque[Any]] = {}
        self._values: Dict[str, Any] = {}
        self._last_updated = datetime.now(timezone.utc)
        self._lock = threading.RLock()

    def replace(self, name: str, values: Iterable[Any]) -> None:
        with self._lock:
            self._collections[name] = deque(
                list(values)[-self._max_entries :], maxlen=self._max_entries
            )
            self._touch()

    def append(self, name: str, value: Any) -> None:
        with self._lock:
            collection = self._collections.setdefault(
                name, deque(maxlen=self._max_entries)
            )
            collection.append(value)
            self._touch()

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._values[name] = value
            self._touch()

    def get_list(self, name: str, limit: int | None = None) -> list[Any]:
        with self._lock:
            values = list(self._collections.get(name, ()))
        if limit is None:
            return values
        return values[-max(0, min(limit, self._max_entries)) :]

    def get_value(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(name, default)

    @property
    def last_updated(self) -> datetime:
        with self._lock:
            return self._last_updated

    def _touch(self) -> None:
        self._last_updated = datetime.now(timezone.utc)
