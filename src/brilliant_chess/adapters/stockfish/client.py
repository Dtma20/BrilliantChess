"""Cliente UCI do Stockfish.

Um processo por instancia, acesso serializado por lock, encerramento garantido
mesmo com excecao, e reinicio limitado apos crash.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

import chess
import chess.engine

from brilliant_chess.adapters.stockfish.diagnostics import file_sha256
from brilliant_chess.adapters.stockfish.mapping import COLOR_FROM_CHESS, move_evaluation
from brilliant_chess.domain.errors import (
    EngineError,
    EngineNotFoundError,
    EngineProtocolError,
    EngineTimeoutError,
    InvalidFenError,
)
from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    Position,
)
from brilliant_chess.domain.strength import EngineStrength

logger = logging.getLogger(__name__)

MAX_RESTARTS = 2
_EXPECTED_NAME_PREFIX = "stockfish"


@dataclass(frozen=True)
class EngineOptions:
    threads: int = 1
    hash_mb: int = 256
    syzygy_path: str | None = None
    show_wdl: bool = True

    def as_uci(self) -> dict[str, str | int | bool]:
        options: dict[str, str | int | bool] = {
            "Threads": self.threads,
            "Hash": self.hash_mb,
            "UCI_ShowWDL": self.show_wdl,
        }
        if self.syzygy_path:
            options["SyzygyPath"] = self.syzygy_path
        return options


class StockfishEngine:
    """Implementacao de ``ports.engine.ChessEngine`` sobre um processo UCI."""

    def __init__(
        self,
        binary_path: Path,
        options: EngineOptions | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not binary_path.is_file():
            raise EngineNotFoundError(f"Executavel do motor nao encontrado: {binary_path}")
        self._binary_path = binary_path
        self._options = options or EngineOptions()
        self._timeout = timeout_seconds
        self._lock = threading.RLock()
        self._engine: chess.engine.SimpleEngine | None = None
        self._closed = False
        self._sha256: str | None = None
        self._applied_strength: str | None = None
        self._start()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def identity(self) -> EngineIdentity:
        with self._lock:
            engine = self._require_engine()
            raw_name = str(engine.id.get("name", "desconhecido"))
            if self._sha256 is None:
                self._sha256 = file_sha256(self._binary_path)
            return EngineIdentity(
                name=raw_name.split(maxsplit=1)[0] if raw_name else "desconhecido",
                version=_version_from(raw_name),
                binary_sha256=self._sha256,
                nnue_name=_nnue_from(engine),
                options=dict(self._options.as_uci()),
            )

    def analyze(
        self,
        position: Position,
        budget: AnalysisBudget,
        multipv: int = 1,
        root_moves: Sequence[Move] | None = None,
    ) -> Sequence[MoveEvaluation]:
        board = _board_from(position)
        if board.is_game_over():
            return ()
        mover = COLOR_FROM_CHESS[board.turn]
        limit = _limit_from(budget)
        moves = _root_moves(board, root_moves)
        with self._lock, self._retrying():
            engine = self._require_engine()
            # Analise sempre em forca total, mesmo se uma partida fraca rodou antes.
            self._restore_full_strength(engine)
            raw = engine.analyse(
                board,
                limit,
                multipv=multipv,
                root_moves=moves,
                info=chess.engine.INFO_ALL,
            )
        lines = raw if isinstance(raw, list) else [raw]
        evaluations = [
            move_evaluation(board, info, mover, fallback_nodes=budget.nodes or 0) for info in lines
        ]
        evaluations.sort(key=lambda item: (-item.expected_points, item.move_uci))
        return tuple(evaluations)

    def play_move(self, position: Position, strength: EngineStrength) -> Move:
        """Escolhe uma jogada com forca limitada pelo proprio motor."""
        board = _board_from(position)
        if board.is_game_over():
            raise EngineError("Partida encerrada: nao ha jogada a fazer")
        limit = _limit_from(strength.budget())
        with self._lock, self._retrying():
            engine = self._require_engine()
            self._apply_strength(engine, strength)
            result = engine.play(board, limit)
        if result.move is None:
            raise EngineProtocolError("Motor nao devolveu jogada")
        return Move(uci=result.move.uci(), san=board.san(result.move))

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._shutdown()

    def _apply_strength(self, engine: chess.engine.SimpleEngine, strength: EngineStrength) -> None:
        if self._applied_strength == strength.key:
            return
        options: dict[str, str | int | bool] = {"UCI_LimitStrength": strength.elo is not None}
        if strength.elo is not None:
            options["UCI_Elo"] = strength.elo
        engine.configure(options)
        self._applied_strength = strength.key

    def _restore_full_strength(self, engine: chess.engine.SimpleEngine) -> None:
        if self._applied_strength is None:
            return
        engine.configure({"UCI_LimitStrength": False})
        self._applied_strength = None

    def _start(self) -> None:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(str(self._binary_path))
        except (OSError, chess.engine.EngineError) as exc:
            raise EngineNotFoundError(f"Falha ao iniciar {self._binary_path}: {exc}") from exc
        name = str(engine.id.get("name", ""))
        if _EXPECTED_NAME_PREFIX not in name.lower():
            engine.quit()
            raise EngineProtocolError(f"Executavel nao se identificou como Stockfish: {name!r}")
        try:
            engine.configure(self._options.as_uci())
        except chess.engine.EngineError as exc:
            engine.quit()
            raise EngineProtocolError(f"Opcoes UCI rejeitadas: {exc}") from exc
        self._engine = engine
        self._applied_strength = None
        logger.info("motor iniciado: %s (%s)", name, self._binary_path)

    def _require_engine(self) -> chess.engine.SimpleEngine:
        if self._closed:
            raise EngineError("Motor ja encerrado")
        if self._engine is None:
            raise EngineError("Motor indisponivel")
        return self._engine

    def _shutdown(self) -> None:
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except (chess.engine.EngineError, OSError) as exc:
            logger.warning("encerramento do motor falhou, matando processo: %s", exc)
            engine.close()

    @contextmanager
    def _retrying(self) -> Iterator[None]:
        """Reinicia o processo apos crash, com limite de tentativas."""
        for attempt in range(MAX_RESTARTS + 1):
            try:
                yield
            except chess.engine.EngineTerminatedError as exc:
                if self._closed or attempt == MAX_RESTARTS:
                    raise EngineError(f"Motor encerrou inesperadamente: {exc}") from exc
                logger.warning("motor caiu, reiniciando (tentativa %d)", attempt + 1)
                self._shutdown()
                self._start()
                continue
            except chess.engine.EngineError as exc:
                raise EngineProtocolError(f"Erro do motor: {exc}") from exc
            except TimeoutError as exc:
                raise EngineTimeoutError(f"Motor excedeu {self._timeout}s") from exc
            return


def _board_from(position: Position) -> chess.Board:
    try:
        return chess.Board(position.fen)
    except ValueError as exc:
        raise InvalidFenError(position.fen, str(exc)) from exc


def _limit_from(budget: AnalysisBudget) -> chess.engine.Limit:
    """Limite por nos e o padrao; tempo existe so para o modo interativo."""
    return chess.engine.Limit(
        nodes=budget.nodes,
        depth=budget.depth,
        time=budget.time_seconds,
    )


def _root_moves(board: chess.Board, root_moves: Sequence[Move] | None) -> list[chess.Move] | None:
    if root_moves is None:
        return None
    parsed: list[chess.Move] = []
    for move in root_moves:
        candidate = chess.Move.from_uci(move.uci)
        if not board.is_legal(candidate):
            raise EngineError(f"root_move ilegal na posicao: {move.uci}")
        parsed.append(candidate)
    return parsed


def _version_from(raw_name: str) -> str:
    parts = raw_name.split()
    return parts[1] if len(parts) > 1 else "desconhecida"


def _nnue_from(engine: chess.engine.SimpleEngine) -> str | None:
    option = engine.options.get("EvalFile")
    if option is None:
        return None
    default = option.default
    return str(default) if default else None
