"""Evidencia pura para trocas e concessoes materiais em strict_v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from brilliant_chess.domain.material import Piece
from brilliant_chess.domain.models import Move, PositionSnapshot


class ExchangeDisposition(StrEnum):
    NONE = "none"
    DESTINATION_OFFER = "destination_offer"
    LEFT_HANGING = "left_hanging"
    EXCHANGE_SACRIFICE = "exchange_sacrifice"
    DECLINED_RECAPTURE = "declined_recapture"
    CLEARANCE_OR_DEFLECTION = "clearance_or_deflection"
    CLEAN_EQUAL_TRADE = "clean_equal_trade"
    FAVORABLE_TRADE = "favorable_trade"
    OBVIOUS_RECAPTURE = "obvious_recapture"
    TEMPORARY_OFFER = "temporary_offer"


@dataclass(frozen=True)
class ExchangePly:
    before: PositionSnapshot
    move: Move
    after: PositionSnapshot
    captured_piece: Piece | None = None


@dataclass(frozen=True)
class ExchangeTrace:
    root: PositionSnapshot
    after_candidate: PositionSnapshot
    target_square: str
    candidate: Move
    acceptance_moves: tuple[ExchangePly, ...]


@dataclass(frozen=True)
class ExchangeEvidence:
    disposition: ExchangeDisposition
    material_before: float
    material_immediately_after: float
    material_after_best_acceptance: float | None = None
    material_captured_by_candidate: float = 0.0
    material_lost_by_mover: float = 0.0
    material_captured_later_by_mover: float = 0.0
    net_material_concession: float = 0.0
    sequence_uci: tuple[str, ...] = ()
    sequence_san: tuple[str, ...] = ()
    clean_trade: bool = False
    obvious_recapture: bool = False
    temporary_offer: bool = False
    favorable_trade: bool = False
    xray_recapture: bool = False
    trace: ExchangeTrace | None = None
