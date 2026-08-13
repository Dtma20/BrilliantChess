"""Contrato de fontes de partidas (PGN local; futuras fontes publicas offline)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from brilliant_chess.domain.models import Position


@dataclass(frozen=True)
class GameMove:
    ply: int
    position_before: Position
    move_uci: str
    move_san: str


@dataclass(frozen=True)
class Game:
    game_id: str
    headers: Mapping[str, str]
    moves: tuple[GameMove, ...]
    #: Origem e termos do dado, exigidos para qualquer importacao externa.
    source: str = "local_pgn"
    provenance: Mapping[str, str] = field(default_factory=dict)

    @property
    def ply_count(self) -> int:
        return len(self.moves)


class GameSource(Protocol):
    """Importar partidas nunca dispara analise automaticamente."""

    def games(self) -> Iterator[Game]: ...

    def game_ids(self) -> Sequence[str]: ...
