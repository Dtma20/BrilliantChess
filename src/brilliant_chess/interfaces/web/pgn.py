"""Serializacao pura de partidas locais para PGN."""

from __future__ import annotations

from brilliant_chess.application import play_game, play_match
from brilliant_chess.domain.strength import strength_by_key
from brilliant_chess.domain.values import Color, GameStatus, GateStatus
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
    """Comentario de um lance: pares ``chave=valor`` legiveis por pessoa e script.

    Somente evidencia medida entra. Um campo ausente significa "nao medido", nao
    "zero", por isso nada e preenchido com valor neutro.
    """
    profile = state.white if move.color is Color.WHITE else state.black
    if move.selection is play_match.SelectionKind.NORMAL:
        return "{policy=normal selection=normal}"
    if move.selection is play_match.SelectionKind.FALLBACK:
        return "{policy=strict_v1 selection=fallback reason=no_eligible_candidate}"
    if move.audit is None:
        return f"{{policy={profile.policy.value} selection={move.selection.value}}}"
    fields = [
        f"policy={profile.policy.value}",
        f"selection={move.selection.value}",
        f"score={move.audit.decision.score:.2f}",
        f"rule_set={move.audit.decision.rule_set_version}",
        *_evidence_fields(move.audit),
    ]
    return "{" + " ".join(fields) + "}"


def _evidence_fields(audit: play_match.MatchAudit) -> list[str]:
    fields: list[str] = []
    evidence = audit.decision.sacrifice
    if evidence.detected and evidence.kind is not None:
        offered = evidence.offered_piece_type
        piece = "" if offered is None else f"/{offered.value}"
        fields.append(f"sacrifice={evidence.kind.value}@{evidence.offered_piece_square}{piece}")
        fields.append(f"accepted={'yes' if audit.defense_accepted else 'no'}")
        if audit.defense_accepted:
            fields.append(f"conceded={audit.material_conceded:.2f}")
    if audit.best_defense_san is not None:
        fields.append(f"best_defense={audit.best_defense_san}")
    unmet = [
        gate.gate_id.value for gate in audit.decision.gates if gate.status is not GateStatus.PASSED
    ]
    if unmet:
        fields.append("unmet=" + ",".join(unmet))
    if audit.terminal_status is not None:
        fields.append(f"end={audit.terminal_status.value}")
    fields.extend(_v2_evidence_fields(audit))
    return fields


def _v2_evidence_fields(audit: play_match.MatchAudit) -> list[str]:
    fields: list[str] = []
    if audit.exchange is not None:
        exchange = audit.exchange
        fields.append(f"exchange={exchange.disposition.value}")
        fields.append(f"net_concession={exchange.net_material_concession:.2f}")
        fields.append(f"clean_trade={'yes' if exchange.clean_trade else 'no'}")
        if exchange.sequence_uci:
            fields.append("exchange_line=" + ",".join(exchange.sequence_uci))
    if audit.non_obviousness is not None:
        evidence = audit.non_obviousness
        condition = "none" if evidence.condition is None else evidence.condition.value
        fields.append(f"non_obvious={condition}")
        if evidence.shallow_rank is not None:
            fields.append(f"shallow_rank={evidence.shallow_rank}")
        if evidence.deep_rank is not None:
            fields.append(f"deep_rank={evidence.deep_rank}")
        if evidence.expected_points_improvement is not None:
            fields.append(f"ep_improvement={evidence.expected_points_improvement:.4f}")
    if audit.detector_version is not None:
        fields.append(f"detector={audit.detector_version}")
    if audit.engine_identity is not None:
        identity = audit.engine_identity
        fields.append(f"engine={identity.name}@{identity.version}")
        fields.append(f"nnue={identity.nnue_name or 'unknown'}")
    nodes = _node_fields(audit)
    if nodes:
        fields.append("nodes=" + ",".join(nodes))
    return fields


def _node_fields(audit: play_match.MatchAudit) -> list[str]:
    values = (
        ("shallow", audit.shallow_budget),
        ("discovery", audit.discovery_budget),
        ("confirmation", audit.confirmation_budget),
        ("best_defense", audit.best_defense_budget),
        ("stability", audit.stability_budget),
    )
    fields = [f"{name}:{budget.nodes}" for name, budget in values if budget is not None]
    if audit.shallow_multipv is not None:
        fields.append(f"shallow_multipv:{audit.shallow_multipv}")
    return fields


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
