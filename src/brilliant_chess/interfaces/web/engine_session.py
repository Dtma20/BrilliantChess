"""Ciclo de vida do processo do motor no servidor local.

Um unico processo Stockfish e compartilhado, e o proprio ``StockfishEngine``
serializa o acesso com lock. O processo e iniciado sob demanda e encerrado no
shutdown, mesmo quando um pedido falha.
"""

from __future__ import annotations

import threading
from pathlib import Path

from brilliant_chess.adapters.stockfish.client import EngineOptions, StockfishEngine
from brilliant_chess.adapters.stockfish.diagnostics import locate_engine_binary
from brilliant_chess.bootstrap.config import Settings
from brilliant_chess.domain.errors import EngineNotFoundError


class EngineSession:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._engine: StockfishEngine | None = None

    @property
    def binary_path(self) -> Path | None:
        info = locate_engine_binary(self._settings.resolved_engine_path())
        return info.path if info.usable else None

    def engine(self) -> StockfishEngine:
        with self._lock:
            if self._engine is None:
                self._engine = self._create()
            return self._engine

    def close(self) -> None:
        with self._lock:
            engine, self._engine = self._engine, None
            if engine is not None:
                engine.close()

    def _create(self) -> StockfishEngine:
        info = locate_engine_binary(self._settings.resolved_engine_path())
        if info.path is None or not info.usable:
            raise EngineNotFoundError(
                "Stockfish nao encontrado. Rode 'brilliant-chess doctor' para "
                "ver como apontar o executavel."
            )
        engine_settings = self._settings.engine
        return StockfishEngine(
            binary_path=info.path,
            options=EngineOptions(
                threads=engine_settings.threads,
                hash_mb=engine_settings.hash_mb,
            ),
            timeout_seconds=engine_settings.timeout_seconds,
        )
