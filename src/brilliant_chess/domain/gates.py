"""Portoes obrigatorios de strict_v1, como funcoes puras e independentes.

Cada portao tem identificador estavel, valor medido, limiar e explicacao.
A decisao final exige aprovacao de todos. Ver docs/domain-rules.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from brilliant_chess.domain.exchange import ExchangeDisposition
from brilliant_chess.domain.non_obviousness import NonObviousnessEvidence
from brilliant_chess.domain.rule_set import (
    NonObviousnessThresholds,
    PriorPositionThresholds,
    QualityThresholds,
    ResultingPositionThresholds,
    RobustnessThresholds,
    RuleSet,
    SacrificeThresholds,
)
from brilliant_chess.domain.sacrifice import SacrificeEvidence
from brilliant_chess.domain.values import GateId, GateStatus

MeasuredValue = float | int | str | bool | None


@dataclass(frozen=True)
class GateResult:
    gate_id: GateId
    status: GateStatus
    measured_value: MeasuredValue
    threshold: MeasuredValue
    explanation: str

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASSED


@dataclass(frozen=True)
class GateInputs:
    """Tudo que os portoes precisam, ja normalizado do POV de quem jogou."""

    is_legal: bool
    expected_points_before: float
    expected_points_after: float
    expected_points_loss: float
    confirmed_rank: int
    sacrifice: SacrificeEvidence
    non_obviousness: NonObviousnessEvidence | None = None
    expected_points_loss_after_best_defense: float | None = None
    depends_on_opponent_error: bool = False
    forced_draw_accepted: bool = False
    expected_points_drift: float | None = None
    pv_overlap_plies: int | None = None
    sacrifice_persisted: bool | None = None


def gate_legal(*, is_legal: bool) -> GateResult:
    return GateResult(
        gate_id=GateId.LEGAL,
        status=GateStatus.PASSED if is_legal else GateStatus.FAILED,
        measured_value=is_legal,
        threshold=True,
        explanation="Jogada legal na posicao" if is_legal else "Jogada ilegal na posicao",
    )


def gate_quality(
    expected_points_loss: float,
    confirmed_rank: int,
    thresholds: QualityThresholds,
) -> GateResult:
    """Melhor ou quase melhor, medida apos confirmacao individual da candidata."""
    loss_ok = expected_points_loss <= thresholds.max_expected_points_loss
    rank_ok = confirmed_rank <= thresholds.require_top_n
    passed = loss_ok and rank_ok
    return GateResult(
        gate_id=GateId.QUALITY,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=expected_points_loss,
        threshold=thresholds.max_expected_points_loss,
        explanation=(
            f"EP_loss={expected_points_loss:.4f} (limite "
            f"{thresholds.max_expected_points_loss:.4f}), rank confirmado={confirmed_rank} "
            f"(top {thresholds.require_top_n})"
        ),
    )


def gate_sacrifice(evidence: SacrificeEvidence, thresholds: SacrificeThresholds) -> GateResult:
    """Sacrificio real de peca, com valor, confianca e linha de aceitacao."""
    checks = (
        evidence.detected,
        evidence.offers_piece,
        evidence.nominal_value >= thresholds.min_nominal_value,
        evidence.confidence >= thresholds.min_confidence,
    )
    passed = all(checks)
    return GateResult(
        gate_id=GateId.SACRIFICE,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=evidence.nominal_value,
        threshold=thresholds.min_nominal_value,
        explanation=(
            f"detectado={evidence.detected}, tipo={evidence.kind}, "
            f"peca={evidence.offered_piece_type}, valor={evidence.nominal_value:.2f}, "
            f"confianca={evidence.confidence:.2f} (minima {thresholds.min_confidence:.2f})"
        ),
    )


def gate_sacrifice_v2(evidence: SacrificeEvidence, thresholds: SacrificeThresholds) -> GateResult:
    exchange = evidence.exchange
    negative_dispositions = {
        ExchangeDisposition.CLEAN_EQUAL_TRADE,
        ExchangeDisposition.FAVORABLE_TRADE,
        ExchangeDisposition.OBVIOUS_RECAPTURE,
        ExchangeDisposition.DECLINED_RECAPTURE,
        ExchangeDisposition.TEMPORARY_OFFER,
    }
    if exchange is not None and (
        exchange.clean_trade
        or exchange.favorable_trade
        or exchange.obvious_recapture
        or exchange.temporary_offer
        or exchange.disposition in negative_dispositions
        or abs(exchange.net_material_concession) <= thresholds.equal_trade_tolerance
    ):
        return GateResult(
            gate_id=GateId.SACRIFICE,
            status=GateStatus.FAILED,
            measured_value=exchange.net_material_concession,
            threshold=thresholds.min_net_material_concession,
            explanation=(
                f"disposicao={exchange.disposition}: troca limpa de material aproximadamente "
                "igual, favoravel, recaptura obvia, recaptura recusada ou oferta temporaria/recuperada; "
                "não satisfaz o portão de sacrifício"
            ),
        )
    if exchange is not None:
        passed = exchange.net_material_concession >= thresholds.min_net_material_concession
        return GateResult(
            gate_id=GateId.SACRIFICE,
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            measured_value=exchange.net_material_concession,
            threshold=thresholds.min_net_material_concession,
            explanation=(
                f"disposicao={exchange.disposition}, concessao liquida="
                f"{exchange.net_material_concession:.2f} "
                f"(minima {thresholds.min_net_material_concession:.2f})"
            ),
        )
    return gate_sacrifice(evidence, thresholds)


def gate_soundness(
    expected_points_loss_after_best_defense: float | None,
    thresholds: QualityThresholds,
    *,
    depends_on_opponent_error: bool = False,
) -> GateResult:
    """A ideia precisa sobreviver a melhor defesa, nao apenas a uma resposta ruim."""
    if expected_points_loss_after_best_defense is None:
        return GateResult(
            gate_id=GateId.SOUNDNESS,
            status=GateStatus.INDETERMINATE,
            measured_value=None,
            threshold=thresholds.max_expected_points_loss,
            explanation="Melhor defesa ainda nao avaliada",
        )
    within_limit = expected_points_loss_after_best_defense <= thresholds.max_expected_points_loss
    passed = within_limit and not depends_on_opponent_error
    return GateResult(
        gate_id=GateId.SOUNDNESS,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=expected_points_loss_after_best_defense,
        threshold=thresholds.max_expected_points_loss,
        explanation=(
            f"EP_loss apos melhor defesa={expected_points_loss_after_best_defense:.4f}, "
            f"depende de erro adversario={depends_on_opponent_error}"
        ),
    )


def gate_not_bad_after(
    expected_points_after: float,
    thresholds: ResultingPositionThresholds,
    *,
    forced_draw_accepted: bool = False,
) -> GateResult:
    passed = expected_points_after >= thresholds.min_expected_points_after or forced_draw_accepted
    return GateResult(
        gate_id=GateId.NOT_BAD_AFTER,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=expected_points_after,
        threshold=thresholds.min_expected_points_after,
        explanation=(
            f"EP apos a candidata={expected_points_after:.4f} "
            f"(minimo {thresholds.min_expected_points_after:.4f}), "
            f"empate forcado aceito={forced_draw_accepted}"
        ),
    )


def gate_not_already_won(
    expected_points_before: float,
    thresholds: PriorPositionThresholds,
) -> GateResult:
    """Usa o EP da posicao anterior, nunca o da posicao resultante."""
    passed = expected_points_before < thresholds.max_expected_points_before
    return GateResult(
        gate_id=GateId.NOT_ALREADY_WON,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=expected_points_before,
        threshold=thresholds.max_expected_points_before,
        explanation=(
            f"EP antes da candidata={expected_points_before:.4f} "
            f"(maximo {thresholds.max_expected_points_before:.4f})"
        ),
    )


def gate_stability(
    expected_points_drift: float | None,
    pv_overlap_plies: int | None,
    sacrifice_persisted: bool | None,
    thresholds: RobustnessThresholds,
    *,
    near_threshold: bool,
) -> GateResult:
    """Sem estagio de estabilidade, candidata proxima de limiar fica indeterminada."""
    if expected_points_drift is None:
        status = GateStatus.INDETERMINATE if near_threshold else GateStatus.PASSED
        explanation = (
            "Estagio de estabilidade nao executado e candidata proxima de um limiar"
            if near_threshold
            else "Estagio de estabilidade nao executado, candidata longe dos limiares"
        )
        return GateResult(
            gate_id=GateId.STABILITY,
            status=status,
            measured_value=None,
            threshold=thresholds.max_ep_drift_on_deeper_search,
            explanation=explanation,
        )
    drift_ok = abs(expected_points_drift) <= thresholds.max_ep_drift_on_deeper_search
    overlap_ok = pv_overlap_plies is None or pv_overlap_plies >= thresholds.min_pv_overlap_plies
    mechanism_ok = sacrifice_persisted is not False
    passed = drift_ok and overlap_ok and mechanism_ok
    return GateResult(
        gate_id=GateId.STABILITY,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=expected_points_drift,
        threshold=thresholds.max_ep_drift_on_deeper_search,
        explanation=(
            f"drift={expected_points_drift:.4f}, sobreposicao de PV={pv_overlap_plies}, "
            f"mecanismo persistiu={sacrifice_persisted}"
        ),
    )


def gate_non_obviousness(
    evidence: NonObviousnessEvidence | None,
    thresholds: NonObviousnessThresholds,
) -> GateResult:
    if evidence is None:
        return GateResult(
            gate_id=GateId.NON_OBVIOUS,
            status=GateStatus.FAILED,
            measured_value=None,
            threshold=True,
            explanation="Evidencia de nao obviedade ausente",
        )
    if (
        evidence.shallow_nodes is None
        or evidence.shallow_multipv is None
        or evidence.deep_rank is None
        or evidence.shallow_rank is None
        or evidence.expected_points_improvement is None
    ):
        return GateResult(
            gate_id=GateId.NON_OBVIOUS,
            status=GateStatus.FAILED,
            measured_value=False,
            threshold=True,
            explanation="Evidencia de nao obviedade indeterminada",
        )
    rank_improvement = evidence.shallow_rank - evidence.deep_rank
    passed = (
        evidence.shallow_nodes >= thresholds.shallow_nodes
        and evidence.shallow_multipv >= thresholds.shallow_multipv
        and evidence.shallow_rank > thresholds.max_obvious_shallow_rank
        and evidence.deep_rank <= thresholds.max_confirmed_rank
        and rank_improvement >= thresholds.min_rank_improvement
        and evidence.expected_points_improvement
        >= thresholds.min_expected_points_improvement
        and evidence.passed
    )
    return GateResult(
        gate_id=GateId.NON_OBVIOUS,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured_value=rank_improvement,
        threshold=thresholds.min_rank_improvement,
        explanation=(
            f"rank raso={evidence.shallow_rank}, rank profundo={evidence.deep_rank}, "
            f"ganho_EP={evidence.expected_points_improvement:.4f}"
        ),
    )


def is_near_threshold(inputs: GateInputs, rules: RuleSet) -> bool:
    """Candidata a menos de uma margem de qualquer limiar continuo."""
    margin = rules.robustness.stability_threshold_margin
    distances = (
        rules.quality.max_expected_points_loss - inputs.expected_points_loss,
        inputs.expected_points_after - rules.resulting_position.min_expected_points_after,
        rules.prior_position.max_expected_points_before - inputs.expected_points_before,
    )
    return any(abs(distance) <= margin for distance in distances)


def evaluate_gates(inputs: GateInputs, rules: RuleSet) -> tuple[GateResult, ...]:
    """Executa os portoes na ordem legalidade -> qualidade -> elegibilidade."""
    sacrifice_result = (
        gate_sacrifice_v2(inputs.sacrifice, rules.sacrifice)
        if rules.id == "strict_v2"
        else gate_sacrifice(inputs.sacrifice, rules.sacrifice)
    )
    results = (
        gate_legal(is_legal=inputs.is_legal),
        gate_quality(inputs.expected_points_loss, inputs.confirmed_rank, rules.quality),
        sacrifice_result,
        gate_soundness(
            inputs.expected_points_loss_after_best_defense,
            rules.quality,
            depends_on_opponent_error=inputs.depends_on_opponent_error,
        ),
        gate_not_bad_after(
            inputs.expected_points_after,
            rules.resulting_position,
            forced_draw_accepted=inputs.forced_draw_accepted,
        ),
        gate_not_already_won(inputs.expected_points_before, rules.prior_position),
        gate_stability(
            inputs.expected_points_drift,
            inputs.pv_overlap_plies,
            inputs.sacrifice_persisted,
            rules.robustness,
            near_threshold=is_near_threshold(inputs, rules),
        ),
    )
    if rules.id != "strict_v2":
        return results
    return results + (gate_non_obviousness(inputs.non_obviousness, rules.non_obviousness),)


def all_gates_passed(results: tuple[GateResult, ...]) -> bool:
    return all(result.passed for result in results)


def failed_gates(results: tuple[GateResult, ...]) -> tuple[GateId, ...]:
    return tuple(r.gate_id for r in results if r.status is GateStatus.FAILED)


def indeterminate_gates(results: tuple[GateResult, ...]) -> tuple[GateId, ...]:
    return tuple(r.gate_id for r in results if r.status is GateStatus.INDETERMINATE)
