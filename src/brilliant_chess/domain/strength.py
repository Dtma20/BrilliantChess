"""Niveis de forca do motor para partidas locais contra uma pessoa.

Forca reduzida usa ``UCI_LimitStrength``/``UCI_Elo`` do proprio Stockfish. O Elo
declarado e o do motor, nao uma promessa de equivalencia com rating de
plataforma.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.models import AnalysisBudget

#: Faixa aceita pelo Stockfish para UCI_Elo.
MIN_UCI_ELO: Final[int] = 1320
MAX_UCI_ELO: Final[int] = 3190


@dataclass(frozen=True)
class EngineStrength:
    key: str
    label: str
    #: ``None`` significa forca maxima, sem limitacao.
    elo: int | None
    move_time_seconds: float
    nodes: int | None = None

    def __post_init__(self) -> None:
        if self.elo is not None and not MIN_UCI_ELO <= self.elo <= MAX_UCI_ELO:
            raise DomainError(f"UCI_Elo fora da faixa [{MIN_UCI_ELO}, {MAX_UCI_ELO}]: {self.elo}")
        if self.move_time_seconds <= 0:
            raise DomainError("move_time_seconds deve ser positivo")

    def budget(self) -> AnalysisBudget:
        """Partida usa tempo por lance; analise reproduzivel continua usando nos."""
        if self.nodes is not None:
            return AnalysisBudget(nodes=self.nodes)
        return AnalysisBudget(time_seconds=self.move_time_seconds)


STRENGTH_LEVELS: Final[tuple[EngineStrength, ...]] = (
    EngineStrength(key="iniciante", label="Iniciante (~1320)", elo=1320, move_time_seconds=0.20),
    EngineStrength(key="casual", label="Casual (~1600)", elo=1600, move_time_seconds=0.25),
    EngineStrength(key="clube", label="Clube (~1900)", elo=1900, move_time_seconds=0.30),
    EngineStrength(key="forte", label="Forte (~2200)", elo=2200, move_time_seconds=0.40),
    EngineStrength(key="mestre", label="Mestre (~2600)", elo=2600, move_time_seconds=0.60),
    EngineStrength(key="maximo", label="Máximo (sem limite)", elo=None, move_time_seconds=1.00),
)

DEFAULT_STRENGTH_KEY: Final[str] = "clube"


def strength_by_key(key: str) -> EngineStrength:
    for level in STRENGTH_LEVELS:
        if level.key == key:
            return level
    raise DomainError(f"Nivel de forca desconhecido: {key!r}")
