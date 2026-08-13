"""Contrato do motor de xadrez, independente de python-chess e de subprocesso."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    Position,
)
from brilliant_chess.domain.strength import EngineStrength


@runtime_checkable
class ChessEngine(Protocol):
    """Motor de analise.

    Invariantes exigidas de qualquer implementacao:

    * ``analyze`` devolve avaliacoes normalizadas do ponto de vista do lado a
      jogar em ``position``, nunca do lado que jogaria depois;
    * a ordem devolvida e decrescente por qualidade para o lado a jogar;
    * ``root_moves`` restringe a busca as jogadas informadas;
    * ``close`` e idempotente e encerra o processo mesmo apos excecao.
    """

    def identity(self) -> EngineIdentity: ...

    def analyze(
        self,
        position: Position,
        budget: AnalysisBudget,
        multipv: int = 1,
        root_moves: Sequence[Move] | None = None,
    ) -> Sequence[MoveEvaluation]: ...

    def close(self) -> None: ...


@runtime_checkable
class PlayableEngine(Protocol):
    """Motor capaz de jogar uma partida local com forca ajustavel.

    Separado de ``ChessEngine`` porque analise e jogo tem contratos diferentes:
    analise devolve avaliacoes; jogo devolve uma unica jogada legal.
    """

    def play_move(self, position: Position, strength: EngineStrength) -> Move: ...
