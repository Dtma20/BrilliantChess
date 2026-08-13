"""Serializacao pura de partidas locais para PGN."""

from __future__ import annotations

from brilliant_chess.application import play_game
from brilliant_chess.domain.values import Color, GameStatus
from brilliant_chess.ports.board import BoardView


def build_pgn(
    state: play_game.GameState,
    initial: BoardView,
    current: BoardView,
    *,
    standard_fen: str,
) -> str:
    result = _result(current.status, current.position.side_to_move)
    white = "Voce" if state.human_color is Color.WHITE else f"Motor ({state.strength.label})"
    black = "Voce" if state.human_color is Color.BLACK else f"Motor ({state.strength.label})"

    headers = [
        ("Event", "Brilliant Chess - Partida local"),
        ("Site", "Localhost"),
        ("White", white),
        ("Black", black),
        ("Result", result),
    ]
    if initial.position.fen != standard_fen:
        headers.extend((("SetUp", "1"), ("FEN", initial.position.fen)))

    movetext = _movetext(
        state.moves_san,
        initial.snapshot.fullmove_number,
        initial.position.side_to_move,
        result,
    )
    return "".join(f'[{name} "{_escape(value)}"]\n' for name, value in headers) + f"\n{movetext}\n"


def _result(status: GameStatus, side_to_move: Color) -> str:
    if status is GameStatus.CHECKMATE:
        return "0-1" if side_to_move is Color.WHITE else "1-0"
    if status.is_finished:
        return "1/2-1/2"
    return "*"


def _movetext(
    moves: tuple[str, ...], fullmove_number: int, side_to_move: Color, result: str
) -> str:
    tokens: list[str] = []
    move_number = fullmove_number
    side = side_to_move
    for san in moves:
        if side is Color.WHITE:
            tokens.append(f"{move_number}.")
        elif not tokens or (tokens and tokens[-1].endswith("...")):
            tokens.append(f"{move_number}...")
        tokens.append(san)
        if side is Color.BLACK:
            move_number += 1
        side = side.opponent
    tokens.append(result)
    return " ".join(tokens)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
