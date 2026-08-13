"""Evidencia de sacrificio e calculo de confianca.

Entrega 1 define o contrato e a aritmetica de confianca. Os detectores concretos
(oferta na casa de destino, peca deixada pendurada, sacrificio de qualidade)
entram na Entrega 4 e devem produzir exatamente estes objetos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.material import is_sacrificeable
from brilliant_chess.domain.rule_set import SacrificeConfidenceWeights
from brilliant_chess.domain.values import PieceType, ReasonCode, SacrificeKind

_MAX_CONFIDENCE = 1.0
_MIN_CONFIDENCE = 0.0


@dataclass(frozen=True)
class SacrificeSignals:
    """Evidencias binarias observadas. Cada uma conta uma unica vez."""

    legal_capture_available: bool = False
    material_deficit_in_acceptance: bool = False
    engine_considers_acceptance: bool = False
    tactical_mechanism_in_pv: bool = False
    #: ``None`` quando o estagio de estabilidade nao foi executado.
    persists_under_deeper_search: bool | None = None


@dataclass(frozen=True)
class SacrificeEvidence:
    detected: bool
    kind: SacrificeKind | None = None
    offered_piece_square: str | None = None
    offered_piece_type: PieceType | None = None
    nominal_value: float = 0.0
    acceptance_moves: tuple[str, ...] = ()
    material_trajectory: tuple[float, ...] = ()
    confidence: float = 0.0
    reasons: tuple[ReasonCode, ...] = ()
    signals: SacrificeSignals = field(default_factory=SacrificeSignals)

    def __post_init__(self) -> None:
        if not _MIN_CONFIDENCE <= self.confidence <= _MAX_CONFIDENCE:
            raise DomainError(f"confidence fora de [0,1]: {self.confidence!r}")
        if self.detected and self.kind is None:
            raise DomainError("Sacrificio detectado exige um SacrificeKind")
        if self.nominal_value < 0.0:
            raise DomainError("nominal_value nao pode ser negativo")

    @property
    def offers_piece(self) -> bool:
        """strict_v1 exige cavalo, bispo, torre ou dama; peao sozinho nao basta."""
        return self.offered_piece_type is not None and is_sacrificeable(self.offered_piece_type)


NO_SACRIFICE = SacrificeEvidence(detected=False)


def sacrifice_confidence(
    signals: SacrificeSignals,
    weights: SacrificeConfidenceWeights,
) -> float:
    """Soma ponderada das evidencias, limitada a [0, 1].

    Confianca nunca substitui um portao: ela apenas alimenta
    ``GATE_SACRIFICE_001`` e a pontuacao de estilo.
    """
    total = 0.0
    if signals.legal_capture_available:
        total += weights.legal_capture_available
    if signals.material_deficit_in_acceptance:
        total += weights.material_deficit_in_acceptance
    if signals.engine_considers_acceptance:
        total += weights.engine_considers_acceptance
    if signals.tactical_mechanism_in_pv:
        total += weights.tactical_mechanism_in_pv
    if signals.persists_under_deeper_search:
        total += weights.persists_under_deeper_search
    return min(_MAX_CONFIDENCE, max(_MIN_CONFIDENCE, total))


def reasons_for(signals: SacrificeSignals) -> tuple[ReasonCode, ...]:
    """Traduz sinais em codigos de motivo auditaveis."""
    reasons: list[ReasonCode] = []
    if signals.legal_capture_available:
        reasons.append(ReasonCode.LEGAL_CAPTURE_OF_OFFERED_PIECE)
    if signals.material_deficit_in_acceptance:
        reasons.append(ReasonCode.MATERIAL_DEFICIT_IN_ACCEPTANCE_LINE)
    if signals.engine_considers_acceptance:
        reasons.append(ReasonCode.ENGINE_CONSIDERS_ACCEPTANCE)
    if signals.tactical_mechanism_in_pv:
        reasons.append(ReasonCode.TACTICAL_MECHANISM_IN_PV)
    if signals.persists_under_deeper_search:
        reasons.append(ReasonCode.PATTERN_PERSISTS_DEEPER)
    return tuple(reasons)
