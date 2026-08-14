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
        ("RuleSetWhite", state.white.policy.value),
        ("RuleSetBlack", state.black.policy.value),
    ]
    if state.opening_config is not None:
        headers.append(("OpeningMode", state.opening_config.mode.value))
    elif state.opening_phase is not None:
        headers.append(("OpeningMode", state.opening_phase.mode.value))
    if state.opening_seed is not None:
        headers.append(("OpeningSeed", str(state.opening_seed)))
    if state.opening_identity is not None:
        headers.append(("ECO", state.opening_identity.eco))
        headers.append(("Opening", state.opening_identity.name))
        if state.opening_identity.variation:
            headers.append(("Variation", state.opening_identity.variation))
    if state.opening_phase is not None and state.opening_phase.exit_reason is not None:
        headers.append(("OpeningExitReason", state.opening_phase.exit_reason.value))
        headers.append(("OpeningExitPly", str(state.opening_phase.completed_opening_plies)))
    if state.opening_dataset_version:
        headers.append(("OpeningDatasetVersion", state.opening_dataset_version))
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
    if move.selection is play_match.SelectionKind.OPENING_EXPLORATION:
        if move.opening_audit is not None:
            audit = move.opening_audit
            fields = [
                "policy=opening_exploration",
                "selection=opening_exploration",
                f"mode={audit.opening_mode.value}",
                f"source={audit.source}",
                f"seed={audit.seed}",
                f"ply={audit.opening_ply}",
                f"planned_exit={audit.planned_exit_ply}",
                f"eco={audit.eco}",
                f"name={audit.name}",
            ]
            if audit.variation:
                fields.append(f"variation={audit.variation}")
            if audit.candidate_rank is not None:
                fields.append(f"rank={audit.candidate_rank}")
            if audit.candidate_ep_loss is not None:
                fields.append(f"ep_loss={audit.candidate_ep_loss:.4f}")
            if audit.sampling_weight is not None:
                fields.append(f"weight={audit.sampling_weight:.4f}")
            if audit.candidates_considered:
                fields.append(f"candidates={','.join(audit.candidates_considered)}")
            if audit.quality_cutoff is not None:
                fields.append(f"cutoff={audit.quality_cutoff:.4f}")
            if audit.search_budget and audit.search_budget.nodes is not None:
                fields.append(f"nodes={audit.search_budget.nodes}")
            return "{" + " ".join(fields) + "}"
        return "{policy=opening_exploration selection=opening_exploration}"
    if move.selection is play_match.SelectionKind.NORMAL:
        return "{policy=normal selection=normal}"
    if move.selection is play_match.SelectionKind.FALLBACK:
        return f"{{policy={profile.policy.value} selection=fallback reason=no_eligible_candidate}}"
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
    if audit.decision.rule_set_version == "strict_v2":
        fields.extend(_v2_evidence_fields(audit))
    return fields


def _v2_evidence_fields(audit: play_match.MatchAudit) -> list[str]:
    fields: list[str] = []
    if audit.exchange is not None:
        exchange = audit.exchange
        fields.append(f"exchange={exchange.disposition.value}")
        fields.append(f"net_concession={exchange.net_material_concession:.2f}")
        fields.append(f"clean_trade={'yes' if exchange.clean_trade else 'no'}")
        fields.extend(
            (
                f"ex_before={exchange.material_before:.2f}",
                f"ex_after={exchange.material_immediately_after:.2f}",
                f"ex_accept={_optional_measure(exchange.material_after_best_acceptance)}",
                f"ex_captured={exchange.material_captured_by_candidate:.2f}",
                f"ex_lost={exchange.material_lost_by_mover:.2f}",
                f"ex_later={exchange.material_captured_later_by_mover:.2f}",
                f"ex_net={exchange.net_material_concession:.2f}",
                f"ex_uci={_sequence_value(exchange.sequence_uci)}",
                f"ex_san={_sequence_value(exchange.sequence_san)}",
                f"ex_clean={'yes' if exchange.clean_trade else 'no'}",
                f"ex_obvious={'yes' if exchange.obvious_recapture else 'no'}",
                f"ex_temporary={'yes' if exchange.temporary_offer else 'no'}",
                f"ex_favorable={'yes' if exchange.favorable_trade else 'no'}",
                f"ex_xray={'yes' if exchange.xray_recapture else 'no'}",
            )
        )
        if exchange.sequence_uci:
            fields.append("exchange_line=" + ",".join(exchange.sequence_uci))
    if audit.non_obviousness is not None:
        evidence = audit.non_obviousness
        condition = "none" if evidence.condition is None else evidence.condition.value
        fields.append(f"non_obvious={condition}")
        fields.extend(
            (
                f"shallow_rank={_optional_int(evidence.shallow_rank)}",
                f"deep_rank={_optional_int(evidence.deep_rank)}",
                f"shallow_ep={_optional_measure(evidence.shallow_expected_points, 4)}",
                f"deep_ep={_optional_measure(evidence.deep_expected_points, 4)}",
                f"ep_improvement={_optional_measure(evidence.expected_points_improvement, 4)}",
                f"shallow_measure_nodes={_optional_int(evidence.shallow_nodes)}",
                f"shallow_measure_multipv={_optional_int(evidence.shallow_multipv)}",
            )
        )
    if audit.detector_version is not None:
        fields.append(f"detector={audit.detector_version}")
    if audit.engine_identity is not None:
        identity = audit.engine_identity
        fields.append(f"engine={identity.name}@{identity.version}")
        fields.append(f"nnue={identity.nnue_name or 'unknown'}")
        fields.append(f"binary_sha256={identity.binary_sha256}")
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
    if not any(budget is not None for _, budget in values) and audit.shallow_multipv is None:
        return []
    fields = [
        f"{name}:{_optional_int(None if budget is None else budget.nodes)}"
        for name, budget in values
    ]
    fields.append(f"shallow_multipv:{_optional_int(audit.shallow_multipv)}")
    return fields


def _optional_measure(value: float | None, places: int = 2) -> str:
    return "none" if value is None else f"{value:.{places}f}"


def _optional_int(value: int | None) -> str:
    return "none" if value is None else str(value)


def _sequence_value(values: tuple[str, ...]) -> str:
    return "none" if not values else ",".join(values)


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
