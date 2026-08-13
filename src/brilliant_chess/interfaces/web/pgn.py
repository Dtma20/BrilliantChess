"""Serializacao pura de partidas locais para PGN."""

from __future__ import annotations

from brilliant_chess.application import play_game, play_match
from brilliant_chess.domain.strength import strength_by_key
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


def build_match_pgn(
    state: play_match.MatchState,
    initial: BoardView,
    current: BoardView,
    *,
    standard_fen: str,
) -> str:
    """Serializa uma partida de motores com a politica de cada lance auditavel."""
    result = (
        "1/2-1/2" if state.is_capped else _result(current.status, current.position.side_to_move)
    )
    headers = [
        ("Event", "Brilliant Chess - Laboratório de motores"),
        ("Site", "Localhost"),
        ("White", _match_player_name(state.white)),
        ("Black", _match_player_name(state.black)),
        ("Result", result),
    ]
    if initial.position.fen != standard_fen:
        headers.extend((("SetUp", "1"), ("FEN", initial.position.fen)))
    movetext = _movetext_with_comments(
        state,
        initial.snapshot.fullmove_number,
        initial.position.side_to_move,
        result,
    )
    return "".join(f'[{name} "{_escape(value)}"]\n' for name, value in headers) + f"\n{movetext}\n"


def _match_player_name(profile: play_match.MatchProfile) -> str:
    label = strength_by_key(profile.strength_key).label.split(" (", 1)[0]
    if profile.strength_key == "maximo":
        label = "Máximo"
    return f"Stockfish ({label}, {profile.policy.value})"


def _movetext_with_comments(
    state: play_match.MatchState,
    fullmove_number: int,
    side_to_move: Color,
    result: str,
) -> str:
    tokens: list[str] = []
    move_number = fullmove_number
    side = side_to_move
    for move in state.moves:
        if side is Color.WHITE:
            tokens.append(f"{move_number}.")
        elif not tokens:
            tokens.append(f"{move_number}...")
        tokens.append(move.san)
        tokens.append(_selection_comment(state, move))
        if side is Color.BLACK:
            move_number += 1
        side = side.opponent
    if state.is_capped:
        tokens.append("{result=experimental_move_limit fullmoves=100}")
    tokens.append(result)
    return " ".join(tokens)


def _selection_comment(state: play_match.MatchState, move: play_match.MatchMove) -> str:
    profile = state.white if move.color is Color.WHITE else state.black
    if move.selection is play_match.SelectionKind.NORMAL:
        return "{policy=normal selection=normal}"
    if move.selection is play_match.SelectionKind.FALLBACK:
        return "{policy=strict_v1 selection=fallback reason=no_eligible_candidate}"
    if move.audit is None:
        return f"{{policy={profile.policy.value} selection={move.selection.value}}}"
    decision = move.audit.decision
    return (
        f"{{policy={profile.policy.value} selection={move.selection.value} "
        f"score={decision.score:.2f} rule_set={decision.rule_set_version}}}"
    )


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
        elif not tokens:
            tokens.append(f"{move_number}...")
        tokens.append(san)
        if side is Color.BLACK:
            move_number += 1
        side = side.opponent
    tokens.append(result)
    return " ".join(tokens)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
