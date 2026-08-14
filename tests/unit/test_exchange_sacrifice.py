from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application.exchange_sacrifice import detect_exchange_aware_sacrifice
from brilliant_chess.domain.exchange import ExchangeDisposition
from brilliant_chess.domain.gates import gate_sacrifice_v2, gate_soundness
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.values import ReasonCode, SacrificeKind

#: 8.Bxc6+ bxc6 e uma troca bispo-por-cavalo aproximadamente igual.
REGRESSION_FEN = "r2qkb1r/pp2pppp/2n2n2/1Bpp4/3P4/4Pb1P/PPPB1PP1/RN1QK2R w KQkq - 0 8"

#: Rxa2+ Kxa2 e uma troca limpa de torres.
EQUAL_TRADE_CASES = (
    ("8/8/8/8/8/8/rk6/R5K1 w - - 0 1", "a1a2"),
    ("8/8/8/8/8/8/qk6/Q5K1 w - - 0 1", "a1a2"),
)

#: Bxb2+ Kxb2: bispo por cavalo, aproximadamente igual pela tolerancia.
BISHOP_FOR_KNIGHT_FEN = "8/8/8/8/8/8/1nk5/B6K w - - 0 1"
BISHOP_FOR_KNIGHT_MOVE = "a1b2"

#: Nxb3+ Kxb3: cavalo por bispo, aproximadamente igual pela tolerancia.
KNIGHT_FOR_BISHOP_FEN = "8/8/8/8/8/1bk5/8/N6K w - - 0 1"
KNIGHT_FOR_BISHOP_MOVE = "a1b3"

#: Rxa2+ Kxa2 concede qualidade liquida (torre por cavalo).
ROOK_FOR_MINOR_FEN = "8/8/8/8/8/8/nk6/R5K1 w - - 0 1"
ROOK_CAPTURE_MOVE = "a1a2"

#: Qxd5 exd5 Rxd5 usa a dama para limpar o raio-x da torre.
XRAY_FEN = "7k/8/4p3/3p4/8/8/3Q4/3R2K1 w - - 0 1"
XRAY_CANDIDATE = "d2d5"

#: Qh7 Rxh7 Rxh7 Kxh7: a oferta e recuperada antes da troca se encerrar.
RECOVERED_OFFER_FEN = "6kr/8/8/7Q/8/8/8/6KR w - - 0 1"
RECOVERED_OFFER_MOVE = "h5h7"

#: A torre de b1 ja esta na diagonal de f5; 14.e3 nao a salva nem a defende.
LEFT_HANGING_ROOK_FEN = "r2qkb1r/1p3p1p/5np1/3Ppb2/7Q/p1N2N2/PP2PPPP/1RB1KB1R w Kkq - 2 14"
LEFT_HANGING_ROOK_MOVE = "e2e3"

# Rxa2+ Kxa2 captures a queen for a rook; the final trade is favorable and
# therefore negative evidence for a sacrifice despite the immediate recapture.
FAVORABLE_TRADE_FEN = "8/8/8/8/8/8/qk6/R5K1 w - - 0 1"
FAVORABLE_TRADE_MOVE = "a1a2"

# Both black pawns can accept Qd5 and the rook recaptures either one. The
# material result ties, so the defender-best line must choose c6d5 first.
TIED_XRAY_FEN = "7k/8/2p1p3/8/8/8/3Q4/3R2K1 w - - 0 1"
TIED_XRAY_CANDIDATE = "d2d5"

# Qh7 offers the queen to the king/rook without capturing first. The remaining
# rook is the material compensation represented by a passing soundness gate.
COMPENSATED_PIECE_OFFER_FEN = "6kr/8/8/7Q/8/8/8/R5K1 w - - 0 1"
COMPENSATED_PIECE_OFFER_MOVE = "h5h7"

# The same legal offer without the remaining rook is structurally detectable,
# but the independent best-defense soundness evidence must reject it.
UNSOUND_PIECE_OFFER_FEN = "6kr/8/8/7Q/8/8/8/6K1 w - - 0 1"
UNSOUND_PIECE_OFFER_MOVE = "h5h7"


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


@pytest.fixture
def rules_v2() -> RuleSet:
    return RuleSet(id="strict_v2")


def test_bxc6_bxc6_is_a_clean_equal_exchange_not_a_sacrifice(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        REGRESSION_FEN,
        (),
        "b5c6",
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is False
    assert evidence.kind is None
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.CLEAN_EQUAL_TRADE
    assert evidence.exchange.clean_trade is True
    assert evidence.exchange.obvious_recapture is True
    assert evidence.exchange.net_material_concession == pytest.approx(0.1)
    assert evidence.exchange.material_captured_by_candidate == pytest.approx(3.2)
    assert evidence.exchange.material_lost_by_mover == pytest.approx(3.3)
    assert evidence.exchange.material_captured_later_by_mover == pytest.approx(0.0)
    assert evidence.exchange.sequence_uci == ("b5c6", "b7c6")
    assert evidence.exchange.sequence_san == ("Bxc6+", "bxc6")
    assert evidence.exchange.trace is not None
    assert evidence.reasons == (
        ReasonCode.LEGAL_CAPTURE_OF_OFFERED_PIECE,
        ReasonCode.EQUAL_EXCHANGE,
        ReasonCode.OBVIOUS_RECAPTURE,
    )


@pytest.mark.parametrize(("fen", "move"), EQUAL_TRADE_CASES)
def test_equal_rook_and_queen_trades_are_not_sacrifices(board, rules_v2, fen, move):
    evidence = detect_exchange_aware_sacrifice(
        board,
        fen,
        (),
        move,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is False
    assert evidence.exchange is not None
    assert evidence.exchange.disposition in {
        ExchangeDisposition.CLEAN_EQUAL_TRADE,
        ExchangeDisposition.OBVIOUS_RECAPTURE,
    }
    assert evidence.exchange.sequence_uci[0] == move
    assert evidence.exchange.material_after_best_acceptance is not None
    assert ReasonCode.LEGAL_CAPTURE_OF_OFFERED_PIECE in evidence.reasons


@pytest.mark.parametrize(
    ("fen", "move"),
    [
        (BISHOP_FOR_KNIGHT_FEN, BISHOP_FOR_KNIGHT_MOVE),
        (KNIGHT_FOR_BISHOP_FEN, KNIGHT_FOR_BISHOP_MOVE),
    ],
)
def test_bishop_and_knight_exchange_directions_stay_rejected_with_complete_evidence(
    board, rules_v2, fen, move
):
    evidence = detect_exchange_aware_sacrifice(
        board,
        fen,
        (),
        move,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is False
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.CLEAN_EQUAL_TRADE
    assert evidence.exchange.clean_trade is True
    assert evidence.exchange.obvious_recapture is True
    assert abs(evidence.exchange.material_before) == pytest.approx(0.1, abs=0.01)
    assert evidence.exchange.material_immediately_after > evidence.exchange.material_before
    assert evidence.exchange.material_after_best_acceptance == pytest.approx(
        evidence.exchange.material_before,
        abs=rules_v2.sacrifice.equal_trade_tolerance,
    )
    assert evidence.exchange.sequence_uci[0] == move
    assert evidence.exchange.sequence_san
    assert evidence.exchange.trace is not None
    assert evidence.reasons == (
        ReasonCode.LEGAL_CAPTURE_OF_OFFERED_PIECE,
        ReasonCode.EQUAL_EXCHANGE,
        ReasonCode.OBVIOUS_RECAPTURE,
    )


def test_rook_for_minor_exchange_can_pass_the_net_concession_threshold(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        ROOK_FOR_MINOR_FEN,
        (),
        ROOK_CAPTURE_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.EXCHANGE_SACRIFICE
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.EXCHANGE_SACRIFICE
    assert evidence.exchange.net_material_concession >= (
        rules_v2.sacrifice.min_net_material_concession
    )
    assert evidence.exchange.sequence_uci == ("a1a2", "b2a2")
    assert ReasonCode.NET_MATERIAL_CONCESSION in evidence.reasons


def test_xray_sequence_is_classified_as_clearance_or_deflection(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        XRAY_FEN,
        (),
        XRAY_CANDIDATE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.CLEARANCE_OR_DEFLECTION
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.CLEARANCE_OR_DEFLECTION
    assert evidence.exchange.xray_recapture is True
    assert evidence.exchange.material_captured_by_candidate == pytest.approx(1.0)
    assert evidence.exchange.material_lost_by_mover == pytest.approx(9.0)
    assert evidence.exchange.material_captured_later_by_mover == pytest.approx(1.0)
    assert evidence.exchange.sequence_uci == ("d2d5", "e6d5", "d1d5")
    assert evidence.exchange.sequence_san == ("Qxd5", "exd5", "Rxd5")
    assert ReasonCode.XRAY_RECAPTURE in evidence.reasons
    assert ReasonCode.NET_MATERIAL_CONCESSION in evidence.reasons


def test_recovered_offer_is_rejected_as_temporary_even_with_net_loss(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        RECOVERED_OFFER_FEN,
        (),
        RECOVERED_OFFER_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is False
    assert evidence.kind is None
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.TEMPORARY_OFFER
    assert evidence.exchange.temporary_offer is True
    assert evidence.exchange.sequence_uci == ("h5h7", "h8h7", "h1h7", "g8h7")
    assert evidence.exchange.sequence_san == ("Qh7+", "Rxh7", "Rxh7", "Kxh7")
    assert evidence.exchange.material_captured_by_candidate == pytest.approx(0.0)
    assert evidence.exchange.material_lost_by_mover == pytest.approx(14.0)
    assert evidence.exchange.material_captured_later_by_mover == pytest.approx(5.0)
    assert evidence.exchange.net_material_concession == pytest.approx(9.0)
    assert ReasonCode.RECOVERED_MATERIAL in evidence.reasons


def test_left_hanging_offer_still_uses_exchange_evidence_for_v2(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        LEFT_HANGING_ROOK_FEN,
        (),
        LEFT_HANGING_ROOK_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.LEFT_HANGING
    assert evidence.exchange.sequence_uci == ("e2e3", "f5b1", "c3b1")
    assert evidence.exchange.material_captured_by_candidate == pytest.approx(0.0)
    assert evidence.exchange.material_lost_by_mover == pytest.approx(5.0)
    assert evidence.exchange.material_captured_later_by_mover == pytest.approx(3.3)
    assert evidence.exchange.net_material_concession == pytest.approx(1.7)
    assert ReasonCode.NET_MATERIAL_CONCESSION in evidence.reasons


def test_favorable_immediate_recapture_is_rejected_with_reason_codes(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        FAVORABLE_TRADE_FEN,
        (),
        FAVORABLE_TRADE_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is False
    assert evidence.kind is None
    assert evidence.exchange is not None
    assert evidence.exchange.favorable_trade is True
    assert evidence.exchange.obvious_recapture is True
    assert evidence.exchange.disposition is ExchangeDisposition.FAVORABLE_TRADE
    assert ReasonCode.FAVORABLE_EXCHANGE in evidence.reasons
    assert ReasonCode.OBVIOUS_RECAPTURE in evidence.reasons


def test_obvious_recapture_disposition_is_explicit_when_below_configured_threshold(board, rules_v2):
    thresholds = replace(rules_v2.sacrifice, min_net_material_concession=2.0)
    evidence = detect_exchange_aware_sacrifice(
        board,
        ROOK_FOR_MINOR_FEN,
        (),
        ROOK_CAPTURE_MOVE,
        material_values=rules_v2.material_values,
        thresholds=thresholds,
    )

    assert evidence.detected is False
    assert evidence.exchange is not None
    assert evidence.exchange.disposition is ExchangeDisposition.OBVIOUS_RECAPTURE
    assert evidence.exchange.obvious_recapture is True
    assert ReasonCode.OBVIOUS_RECAPTURE in evidence.reasons


def test_defender_best_ordering_uses_lexicographically_first_tied_line(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        TIED_XRAY_FEN,
        (),
        TIED_XRAY_CANDIDATE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.exchange is not None
    assert evidence.exchange.sequence_uci == ("d2d5", "c6d5", "d1d5", "e6d5")


def test_compensated_piece_offer_stays_eligible_only_with_soundness_evidence(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        COMPENSATED_PIECE_OFFER_FEN,
        (),
        COMPENSATED_PIECE_OFFER_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.DESTINATION_OFFER
    assert evidence.exchange is not None
    assert evidence.exchange.material_captured_by_candidate == pytest.approx(0.0)
    assert evidence.exchange.net_material_concession >= (
        rules_v2.sacrifice.min_net_material_concession
    )
    assert evidence.exchange.obvious_recapture is False
    assert gate_sacrifice_v2(evidence, rules_v2.sacrifice).passed
    assert gate_soundness(0.004, rules_v2.quality).passed


def test_unsound_piece_offer_is_structural_evidence_but_fails_soundness_gate(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        UNSOUND_PIECE_OFFER_FEN,
        (),
        UNSOUND_PIECE_OFFER_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.DESTINATION_OFFER
    assert gate_sacrifice_v2(evidence, rules_v2.sacrifice).passed
    soundness = gate_soundness(
        0.25,
        rules_v2.quality,
        depends_on_opponent_error=True,
    )
    assert soundness.passed is False
