"""Contrato de regras de tabuleiro.

Existe para manter python-chess dentro de ``adapters`` (ADR 0004). O historico
de lances e passado explicitamente porque repeticao e regra dos cinquenta lances
dependem dele, nao apenas da FEN atual.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from brilliant_chess.domain.exchange import ExchangeTrace
from brilliant_chess.domain.models import Move, Position, PositionSnapshot
from brilliant_chess.domain.values import GameStatus


@dataclass(frozen=True)
class BoardView:
    """Tudo que uma interface precisa para desenhar e validar um lance."""

    position: Position
    snapshot: PositionSnapshot
    legal_moves: tuple[Move, ...]
    status: GameStatus
    is_check: bool
    last_move_uci: str | None
    move_number: int
    #: SAN dos lances aplicados desde a FEN inicial, na ordem em que ocorreram.
    moves_san: tuple[str, ...] = ()


class BoardService(Protocol):
    def position_after(self, initial_fen: str, moves_uci: Sequence[str]) -> Position: ...

    def view(self, initial_fen: str, moves_uci: Sequence[str]) -> BoardView: ...

    def normalize_move(self, position: Position, move: str) -> Move:
        """Aceita UCI ou SAN e devolve a jogada legal correspondente."""
        ...

    def pv_san(self, position: Position, moves_uci: Sequence[str]) -> tuple[str, ...]: ...

    def exchange_lines(
        self,
        initial_fen: str,
        moves_uci: Sequence[str],
        candidate_move: str,
        max_plies: int,
    ) -> tuple[ExchangeTrace, ...]: ...
