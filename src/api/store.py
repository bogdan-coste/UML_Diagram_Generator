"""Bounded in-memory history of generations.

Deliberately not persisted: this is a single-process demo server, and writing
generated diagrams to disk would sit next to the training corpus without a
retention story. Restarting the server clears the list.

Sync routes in FastAPI run in a threadpool, so access is lock-guarded.
"""
from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable

from .schemas import HistoryEntry


class HistoryStore:
    """A fixed-size, newest-first store of :class:`HistoryEntry` records."""

    def __init__(self, maxlen: int = 50) -> None:
        self._entries: deque[HistoryEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    @property
    def maxlen(self) -> int:
        return self._entries.maxlen or 0

    def add(self, entry: HistoryEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def recent(self, limit: int = 10) -> list[HistoryEntry]:
        """Return up to *limit* entries, most recent first."""
        limit = max(1, min(limit, self.maxlen))
        with self._lock:
            newest_first: Iterable[HistoryEntry] = reversed(self._entries)
            return list(newest_first)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
