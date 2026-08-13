"""Modelos imutaveis de posicao, orcamento, identidade do motor e avaliacao."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self

from brilliant_chess.domain.errors import (
    DomainError,
    InvalidEvaluationError,
    InvalidFenError,
    InvalidMoveError,
)
from brilliant_chess.domain.expected_points import (
    clamp_expected_points,
    expected_points_from_centipawns,
    expected_points_from_mate,
    expected_points_from_wdl,
    flip_expected_points,
    flip_wdl,
)
from brilliant_chess.domain.material import PiecePlacement
from brilliant_chess.domain.values import EP_MAX, EP_MIN, Color

_FEN_SIDE_TO_COLOR = {"w": Color.WHITE, "b": Color.BLACK}
_MIN_FEN_FIELDS = 4
_FEN_RANK_SEPARATORS = 7
_UCI_MIN_LEN = 4
_UCI_MAX_LEN = 5


@dataclass(frozen=True)
class Position:
    """Posicao identificada pela FEN normalizada."""

    fen: str
    side_to_move: Color

    def __post_init__(self) -> None:
        fields = self.fen.split()
        if len(fields) < _MIN_FEN_FIELDS:
            raise InvalidFenError(self.fen, f"esperados ao menos {_MIN_FEN_FIELDS} campos")
        if fields[1] not in _FEN_SIDE_TO_COLOR:
            raise InvalidFenError(self.fen, "campo de lado a jogar deve ser 'w' ou 'b'")
        if _FEN_SIDE_TO_COLOR[fields[1]] is not self.side_to_move:
            raise InvalidFenError(self.fen, "side_to_move nao corresponde a FEN")
        if fields[0].count("/") != _FEN_RANK_SEPARATORS:
            raise InvalidFenError(self.fen, "campo de pecas deve ter 8 fileiras")

    @classmethod
    def from_fen(cls, fen: str) -> Self:
        fields = fen.split()
        if len(fields) < _MIN_FEN_FIELDS:
            raise InvalidFenError(fen, f"esperados ao menos {_MIN_FEN_FIELDS} campos")
        side = _FEN_SIDE_TO_COLOR.get(fields[1])
        if side is None:
            raise InvalidFenError(fen, "campo de lado a jogar deve ser 'w' ou 'b'")
        return cls(fen=fen, side_to_move=side)


@dataclass(frozen=True)
class PositionSnapshot:
    """Posicao mais a ocupacao das casas, produzida por um adapter."""

    position: Position
    placement: PiecePlacement
    halfmove_clock: int
    fullmove_number: int


@dataclass(frozen=True)
class Move:
    """Jogada em UCI. SAN e opcional porque depende do contexto da posicao."""

    uci: str
    san: str | None = None

    def __post_init__(self) -> None:
        if not _UCI_MIN_LEN <= len(self.uci) <= _UCI_MAX_LEN:
            raise InvalidMoveError(self.uci, "UCI deve ter 4 ou 5 caracteres")


@dataclass(frozen=True)
class AnalysisBudget:
    """Ao menos um limite deve existir. Prefira nos para reprodutibilidade."""

    nodes: int | None = None
    depth: int | None = None
    time_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.nodes is None and self.depth is None and self.time_seconds is None:
            raise DomainError("AnalysisBudget exige nodes, depth ou time_seconds")
        for name, value in (("nodes", self.nodes), ("depth", self.depth)):
            if value is not None and value <= 0:
                raise DomainError(f"{name} deve ser positivo")
        if self.time_seconds is not None and self.time_seconds <= 0:
            raise DomainError("time_seconds deve ser positivo")

    @property
    def is_deterministic(self) -> bool:
        """Orcamento por tempo nao e reproduzivel e nao pode entrar em golden tests."""
        return self.time_seconds is None


@dataclass(frozen=True)
class EngineIdentity:
    name: str
    version: str
    binary_sha256: str
    nnue_name: str | None
    options: Mapping[str, str | int | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedEvaluation:
    """Avaliacao sempre do ponto de vista de ``mover``.

    ``expected_points`` e derivado de WDL quando disponivel; senao do fallback de
    centipawns; scores de mate usam a faixa reservada.
    """

    mover: Color
    centipawns: int | None
    mate_in: int | None
    expected_points: float
    wdl: tuple[int, int, int] | None = None

    def __post_init__(self) -> None:
        if self.centipawns is None and self.mate_in is None:
            raise InvalidEvaluationError("Avaliacao exige centipawns ou mate_in")
        if not EP_MIN <= self.expected_points <= EP_MAX:
            raise InvalidEvaluationError(f"expected_points fora de [0,1]: {self.expected_points!r}")

    @property
    def is_mate(self) -> bool:
        return self.mate_in is not None

    @classmethod
    def create(
        cls,
        mover: Color,
        centipawns: int | None = None,
        mate_in: int | None = None,
        wdl: tuple[int, int, int] | None = None,
    ) -> Self:
        """Deriva EP na ordem mate > WDL > fallback de centipawns."""
        if mate_in is not None:
            expected = expected_points_from_mate(mate_in)
        elif wdl is not None:
            expected = expected_points_from_wdl(wdl)
        elif centipawns is not None:
            expected = expected_points_from_centipawns(centipawns)
        else:
            raise InvalidEvaluationError("Avaliacao exige centipawns, mate_in ou wdl")
        return cls(
            mover=mover,
            centipawns=centipawns,
            mate_in=mate_in,
            expected_points=clamp_expected_points(expected),
            wdl=wdl,
        )

    def flipped(self) -> NormalizedEvaluation:
        """Inverte o ponto de vista. Usado apos ``push`` para nao trocar o POV."""
        return NormalizedEvaluation(
            mover=self.mover.opponent,
            centipawns=None if self.centipawns is None else -self.centipawns,
            mate_in=None if self.mate_in is None else -self.mate_in,
            expected_points=flip_expected_points(self.expected_points),
            wdl=None if self.wdl is None else flip_wdl(self.wdl),
        )


@dataclass(frozen=True)
class PrincipalVariation:
    moves_uci: tuple[str, ...] = ()
    moves_san: tuple[str, ...] = ()

    def overlap_plies(self, other: PrincipalVariation) -> int:
        """Quantos lances iniciais coincidem. Base de GATE_STABILITY_001."""
        count = 0
        for mine, theirs in zip(self.moves_uci, other.moves_uci, strict=False):
            if mine != theirs:
                break
            count += 1
        return count


@dataclass(frozen=True)
class MoveEvaluation:
    move_uci: str
    move_san: str
    evaluation: NormalizedEvaluation
    pv: PrincipalVariation
    depth: int
    nodes: int
    seldepth: int | None = None
    multipv_rank: int | None = None

    @property
    def expected_points(self) -> float:
        return self.evaluation.expected_points
