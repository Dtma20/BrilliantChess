"""Enums e constantes do dominio. Nenhuma string livre deve virar logica interna."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Color(StrEnum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opponent(self) -> Color:
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class PieceType(StrEnum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


class SacrificeKind(StrEnum):
    DESTINATION_OFFER = "destination_offer"
    LEFT_HANGING = "left_hanging"
    EXCHANGE_SACRIFICE = "exchange_sacrifice"
    DECLINED_RECAPTURE = "declined_recapture"
    CLEARANCE_OR_DEFLECTION = "clearance_or_deflection"


class GateId(StrEnum):
    """Identificadores estaveis das regras. Ver docs/domain-rules.md."""

    LEGAL = "GATE_LEGAL_001"
    QUALITY = "GATE_QUALITY_001"
    SACRIFICE = "GATE_SACRIFICE_001"
    SOUNDNESS = "GATE_SOUNDNESS_001"
    NOT_BAD_AFTER = "GATE_NOT_BAD_AFTER_001"
    NOT_ALREADY_WON = "GATE_NOT_ALREADY_WON_001"
    STABILITY = "GATE_STABILITY_001"
    NON_OBVIOUS = "GATE_NON_OBVIOUS_001"


class GateStatus(StrEnum):
    """Um portao pode nao ter evidencia suficiente; ver ADR 0003."""

    PASSED = "passed"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class AnalysisStage(StrEnum):
    DISCOVERY = "discovery"
    CONFIRMATION = "confirmation"
    STABILITY = "stability"


class GameStatus(StrEnum):
    """Estado de uma partida local entre pessoa e motor."""

    IN_PROGRESS = "in_progress"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW_INSUFFICIENT_MATERIAL = "draw_insufficient_material"
    DRAW_FIFTY_MOVES = "draw_fifty_moves"
    DRAW_THREEFOLD_REPETITION = "draw_threefold_repetition"

    @property
    def is_finished(self) -> bool:
        return self is not GameStatus.IN_PROGRESS


#: Texto canonico de cada desfecho. Vive aqui para que o seletor e o ciclo de
#: partida descrevam o mesmo termino com as mesmas palavras.
GAME_STATUS_TEXTS: Final[dict[GameStatus, str]] = {
    GameStatus.CHECKMATE: "Xeque-mate",
    GameStatus.STALEMATE: "Empate por afogamento",
    GameStatus.DRAW_INSUFFICIENT_MATERIAL: "Empate por material insuficiente",
    GameStatus.DRAW_FIFTY_MOVES: "Empate pela regra dos cinquenta lances",
    GameStatus.DRAW_THREEFOLD_REPETITION: "Empate por tripla repetição",
}


class AnalysisState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReasonCode(StrEnum):
    """Motivos legiveis anexados a decisoes e evidencias."""

    BEST_OR_NEAR_BEST = "best_or_near_best"
    SOUND_PIECE_SACRIFICE = "sound_piece_sacrifice"
    POSITION_NOT_BAD_AFTER = "position_not_bad_after"
    POSITION_NOT_ALREADY_WINNING = "position_not_already_completely_winning"
    STABLE_UNDER_DEEPER_SEARCH = "stable_under_deeper_search"
    LEGAL_CAPTURE_OF_OFFERED_PIECE = "legal_capture_of_offered_piece"
    MATERIAL_DEFICIT_IN_ACCEPTANCE_LINE = "material_deficit_in_acceptance_line"
    ENGINE_CONSIDERS_ACCEPTANCE = "engine_considers_acceptance"
    TACTICAL_MECHANISM_IN_PV = "tactical_mechanism_in_pv"
    PATTERN_PERSISTS_DEEPER = "pattern_persists_deeper"
    EQUAL_EXCHANGE = "equal_exchange"
    OBVIOUS_RECAPTURE = "obvious_recapture"
    FAVORABLE_EXCHANGE = "favorable_exchange"
    RECOVERED_MATERIAL = "recovered_material"
    NET_MATERIAL_CONCESSION = "net_material_concession"
    XRAY_RECAPTURE = "xray_recapture"
    PIECE_ALREADY_LOST = "piece_already_lost"
    PROTECTED_CAPTURE_WINS_MATERIAL = "protected_capture_wins_material"
    ONLY_WORKS_AFTER_BLUNDER = "only_works_after_blunder"


class WarningCode(StrEnum):
    """Avisos que nunca devem ser silenciados."""

    STABILITY_BUDGET_NOT_RUN = "stability_budget_not_run"
    EP_LOSS_CLAMPED_TO_ZERO = "ep_loss_clamped_to_zero"
    MATE_SCORE_PRESENT = "mate_score_present"
    WDL_UNAVAILABLE_FALLBACK_USED = "wdl_unavailable_fallback_used"
    RANK_CHANGED_AFTER_CONFIRMATION = "rank_changed_after_confirmation"
    SHALLOW_BUDGET = "shallow_budget"


EP_MIN: Final[float] = 0.0
EP_MAX: Final[float] = 1.0

#: Tolerancia para ruido numerico ao comparar pontos esperados.
EP_NOISE_TOLERANCE: Final[float] = 1e-6

#: Versao da regra padrao deste projeto. Nao e "chess_com_exact".
DEFAULT_RULE_SET_VERSION: Final[str] = "strict_v1"
