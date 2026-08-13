"""Motor falso dirigido por fixture.

Permite testar mudanca de rank entre discovery e confirmation, drift em
stability, crash com retry, score ausente, mate e multiplas PVs sem depender do
binario do Stockfish.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    NormalizedEvaluation,
    Position,
    PrincipalVariation,
)
from brilliant_chess.domain.values import Color

DEFAULT_IDENTITY = EngineIdentity(
    name="ScriptedEngine",
    version="fake-1",
    binary_sha256="0" * 64,
    nnue_name=None,
    options={"Threads": 1, "Hash": 16},
)


@dataclass(frozen=True)
class ScriptKey:
    fen: str
    root_moves: tuple[str, ...] = ()
    nodes: int | None = None


@dataclass(frozen=True)
class RecordedCall:
    position: Position
    budget: AnalysisBudget
    multipv: int
    root_moves: tuple[str, ...]


@dataclass
class ScriptedEngine:
    """Implementacao de ``ChessEngine`` cujo retorno vem do script."""

    script: dict[ScriptKey, Sequence[MoveEvaluation]] = field(default_factory=dict)
    engine_identity: EngineIdentity = DEFAULT_IDENTITY
    crashes_remaining: int = 0
    calls: list[RecordedCall] = field(default_factory=list)
    close_count: int = 0

    def identity(self) -> EngineIdentity:
        return self.engine_identity

    def analyze(
        self,
        position: Position,
        budget: AnalysisBudget,
        multipv: int = 1,
        root_moves: Sequence[Move] | None = None,
    ) -> Sequence[MoveEvaluation]:
        roots = tuple(move.uci for move in root_moves) if root_moves else ()
        self.calls.append(
            RecordedCall(position=position, budget=budget, multipv=multipv, root_moves=roots)
        )
        if self.crashes_remaining > 0:
            self.crashes_remaining -= 1
            raise EngineError("ScriptedEngine: crash injetado")
        for key in (
            ScriptKey(position.fen, roots, budget.nodes),
            ScriptKey(position.fen, roots, None),
            ScriptKey(position.fen, (), None),
        ):
            if key in self.script:
                return tuple(self.script[key])
        raise EngineError(f"ScriptedEngine sem resposta para {position.fen!r} roots={roots}")

    def close(self) -> None:
        self.close_count += 1


def evaluation(
    move_uci: str,
    mover: Color,
    *,
    centipawns: int | None = None,
    mate_in: int | None = None,
    wdl: tuple[int, int, int] | None = None,
    pv: tuple[str, ...] = (),
    depth: int = 20,
    nodes: int = 100_000,
    rank: int | None = None,
    san: str | None = None,
) -> MoveEvaluation:
    """Constroi uma ``MoveEvaluation`` normalizada para o lado que jogou."""
    return MoveEvaluation(
        move_uci=move_uci,
        move_san=san or move_uci,
        evaluation=NormalizedEvaluation.create(
            mover=mover, centipawns=centipawns, mate_in=mate_in, wdl=wdl
        ),
        pv=PrincipalVariation(moves_uci=pv or (move_uci,)),
        depth=depth,
        nodes=nodes,
        multipv_rank=rank,
    )
