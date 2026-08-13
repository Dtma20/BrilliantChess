"""Ciclo de vida de dois processos Stockfish independentes para o laboratorio."""

from __future__ import annotations

import threading
from pathlib import Path

from brilliant_chess.adapters.stockfish.client import EngineOptions, StockfishEngine
from brilliant_chess.adapters.stockfish.diagnostics import locate_engine_binary
from brilliant_chess.bootstrap.config import Settings
from brilliant_chess.domain.errors import EngineNotFoundError


class EnginePairSession:
    """Cria sob demanda um motor por cor e encerra os dois de forma segura."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._binary_path: Path | None = None
        self._white: StockfishEngine | None = None
        self._black: StockfishEngine | None = None

    def white_engine(self) -> StockfishEngine:
        with self._lock:
            if self._white is None:
                self._white = self._create()
            return self._white

    def black_engine(self) -> StockfishEngine:
        with self._lock:
            if self._black is None:
                self._black = self._create()
            return self._black

    def close(self) -> None:
        with self._lock:
            engines = (self._white, self._black)
            self._white = None
            self._black = None

        failure: BaseException | None = None
        for engine in engines:
            if engine is None:
                continue
            try:
                engine.close()
            except BaseException as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure

    def _create(self) -> StockfishEngine:
        engine_settings = self._settings.engine
        return StockfishEngine(
            self._resolved_binary_path(),
            EngineOptions(
                threads=max(1, engine_settings.threads // 2),
                hash_mb=max(16, engine_settings.hash_mb // 2),
            ),
            engine_settings.timeout_seconds,
        )

    def _resolved_binary_path(self) -> Path:
        if self._binary_path is None:
            info = locate_engine_binary(self._settings.resolved_engine_path())
            if info.path is None or not info.usable:
                raise EngineNotFoundError(
                    "Stockfish nao encontrado. Rode 'brilliant-chess doctor' para "
                    "ver como apontar o executavel."
                )
            self._binary_path = info.path
        return self._binary_path
