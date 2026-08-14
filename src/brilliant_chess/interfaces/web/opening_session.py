"""Controle de novidade de aberturas na sessao do servidor."""

from __future__ import annotations

import threading


class OpeningSession:
    """Rastreia deterministica e thread-safely o uso de linhas na sessao."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage_counts: dict[str, int] = {}

    def record_usage(self, line_id: str) -> None:
        with self._lock:
            self._usage_counts[line_id] = self._usage_counts.get(line_id, 0) + 1

    def usage_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._usage_counts)

    def snapshot(self) -> dict[str, int]:
        return self.usage_snapshot()

    def reset(self) -> None:
        with self._lock:
            self._usage_counts.clear()
