"""Ciclo de vida puro de uma partida entre dois perfis de motor."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.models import Move
from brilliant_chess.domain.scoring import BrilliantDecision
from brilliant_chess.domain.strength import strength_by_key
from brilliant_chess.domain.values import Color, GameStatus
from brilliant_chess.ports.board import BoardService, BoardView


class MatchPolicy(StrEnum):
    NORMAL = "normal"
    STRICT_V1 = "strict_v1"


class SelectionKind(StrEnum):
    NORMAL = "normal"
    STRICT_V1 = "strict_v1"
    NEAR_BRILLIANT = "near_brilliant"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class MatchProfile:
    strength_key: str
    policy: MatchPolicy


@dataclass(frozen=True)
class MatchAudit:
    decision: BrilliantDecision
    best_defense_uci: str | None
    stability_depth: int | None


@dataclass(frozen=True)
class MatchMove:
    color: Color
    uci: str
    san: str
    selection: SelectionKind
    audit: MatchAudit | None


@dataclass(frozen=True)
class MatchState:
    match_id: str
    initial_fen: str
    current_fen: str
    white: MatchProfile
    black: MatchProfile
    moves_uci: tuple[str, ...] = ()
    moves_san: tuple[str, ...] = ()
    moves: tuple[MatchMove, ...] = ()
    max_plies: int = 200

    @property
    def is_capped(self) -> bool:
        return len(self.moves_uci) >= self.max_plies

    def is_finished(self, board: BoardService) -> bool:
        return self.is_capped or current_view(board, self).status.is_finished


def start_match(
    match_id: str,
    initial_fen: str,
    white: MatchProfile,
    black: MatchProfile,
    max_plies: int = 200,
) -> MatchState:
    strength_by_key(white.strength_key)
    strength_by_key(black.strength_key)
    if max_plies <= 0:
        raise DomainError("max_plies deve ser positivo")
    return MatchState(
        match_id=match_id,
        initial_fen=initial_fen,
        current_fen=initial_fen,
        white=white,
        black=black,
        max_plies=max_plies,
    )


def current_view(board: BoardService, state: MatchState) -> BoardView:
    return board.view(state.initial_fen, state.moves_uci)


def can_step(board: BoardService, state: MatchState) -> bool:
    return not state.is_finished(board)


def record_move(
    board: BoardService,
    state: MatchState,
    move: Move,
    selection: SelectionKind,
    audit: MatchAudit | None,
) -> MatchState:
    if state.is_finished(board):
        raise DomainError("Partida encerrada")
    view = current_view(board, state)
    normalized = board.normalize_move(view.position, move.uci)
    next_uci = (*state.moves_uci, normalized.uci)
    next_view = board.view(state.initial_fen, next_uci)
    match_move = MatchMove(
        color=view.position.side_to_move,
        uci=normalized.uci,
        san=normalized.san or next_view.moves_san[-1],
        selection=selection,
        audit=audit,
    )
    return replace(
        state,
        current_fen=next_view.position.fen,
        moves_uci=next_uci,
        moves_san=(*state.moves_san, match_move.san),
        moves=(*state.moves, match_move),
    )


def result_text(board: BoardService, state: MatchState) -> str:
    if state.is_capped:
        return "Empate por limite experimental (100 lances)"
    status = current_view(board, state).status
    if status.is_finished:
        return _RESULT_TEXTS.get(status, "Partida encerrada")
    return "Partida em andamento"


_RESULT_TEXTS: dict[GameStatus, str] = {
    GameStatus.CHECKMATE: "Xeque-mate",
    GameStatus.STALEMATE: "Empate por afogamento",
    GameStatus.DRAW_INSUFFICIENT_MATERIAL: "Empate por material insuficiente",
    GameStatus.DRAW_FIFTY_MOVES: "Empate pela regra dos cinquenta lances",
    GameStatus.DRAW_THREEFOLD_REPETITION: "Empate por tripla repeticao",
}
