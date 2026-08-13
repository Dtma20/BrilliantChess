"""Caso de uso de partida local entre uma pessoa e o motor.

Escopo deliberado: a partida acontece **dentro** deste projeto, com tabuleiro
proprio. Nada aqui le tela, controla mouse, cria overlay ou conversa com
plataforma externa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.strength import EngineStrength, strength_by_key
from brilliant_chess.domain.values import GAME_STATUS_TEXTS, Color, GameStatus
from brilliant_chess.ports.board import BoardService, BoardView
from brilliant_chess.ports.engine import PlayableEngine


@dataclass(frozen=True)
class GameState:
    game_id: str
    initial_fen: str
    moves_uci: tuple[str, ...]
    moves_san: tuple[str, ...]
    human_color: Color
    strength_key: str

    @property
    def strength(self) -> EngineStrength:
        return strength_by_key(self.strength_key)


def start_game(
    game_id: str,
    initial_fen: str,
    human_color: Color,
    strength_key: str,
) -> GameState:
    strength_by_key(strength_key)
    return GameState(
        game_id=game_id,
        initial_fen=initial_fen,
        moves_uci=(),
        moves_san=(),
        human_color=human_color,
        strength_key=strength_key,
    )


def current_view(board: BoardService, state: GameState) -> BoardView:
    return board.view(state.initial_fen, state.moves_uci)


def is_engine_turn(board: BoardService, state: GameState) -> bool:
    view = current_view(board, state)
    if view.status.is_finished:
        return False
    return view.position.side_to_move is not state.human_color


def play_human_move(board: BoardService, state: GameState, move: str) -> GameState:
    """Aplica a jogada da pessoa, aceitando UCI ou SAN."""
    view = current_view(board, state)
    if view.status.is_finished:
        raise DomainError("Partida encerrada")
    if view.position.side_to_move is not state.human_color:
        raise DomainError("Nao e a vez da pessoa")
    normalized = board.normalize_move(view.position, move)
    return _append(state, normalized.uci, normalized.san or normalized.uci)


def play_engine_move(
    board: BoardService,
    engine: PlayableEngine,
    state: GameState,
) -> GameState:
    view = current_view(board, state)
    if view.status.is_finished:
        raise DomainError("Partida encerrada")
    if view.position.side_to_move is state.human_color:
        raise DomainError("Nao e a vez do motor")
    chosen = engine.play_move(view.position, state.strength)
    return _append(state, chosen.uci, chosen.san or chosen.uci)


def undo_full_move(board: BoardService, state: GameState) -> GameState:
    """Volta ate a pessoa poder jogar de novo (normalmente dois meios-lances)."""
    working = state
    while working.moves_uci:
        working = replace(
            working,
            moves_uci=working.moves_uci[:-1],
            moves_san=working.moves_san[:-1],
        )
        view = current_view(board, working)
        if view.position.side_to_move is working.human_color:
            break
    return working


_DRAW_TEXTS = {
    status: text for status, text in GAME_STATUS_TEXTS.items() if status is not GameStatus.CHECKMATE
}


def result_text(status: GameStatus, side_to_move: Color, human_color: Color) -> str:
    if status is GameStatus.CHECKMATE:
        # Quem esta a jogar na posicao de mate e quem perdeu.
        lost = side_to_move is human_color
        return "Voce perdeu por xeque-mate" if lost else "Voce venceu por xeque-mate"
    return _DRAW_TEXTS.get(status, "Partida em andamento")


def _append(state: GameState, uci: str, san: str) -> GameState:
    return replace(
        state,
        moves_uci=(*state.moves_uci, uci),
        moves_san=(*state.moves_san, san),
    )
