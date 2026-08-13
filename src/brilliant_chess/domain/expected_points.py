"""Conversao de avaliacoes do motor em pontos esperados (EP) no intervalo [0, 1].

Toda conversao e versionada. Nao espalhe formulas de centipawn pelo codigo:
qualquer novo mapeamento entra aqui e ganha um identificador proprio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from brilliant_chess.domain.errors import InvalidEvaluationError
from brilliant_chess.domain.values import EP_MAX, EP_MIN, EP_NOISE_TOLERANCE

#: Mapeamento WDL -> EP. Incrementar quando a formula mudar (invalida cache).
WDL_MAPPING_VERSION: Final[str] = "wdl_v1"

#: Fallback centipawn -> EP quando o motor nao reporta WDL.
CP_MAPPING_VERSION: Final[str] = "cp_logistic_400_v1"

#: Escala logistica do fallback (mesma forma da curva de score esperado de Elo).
CP_LOGISTIC_SCALE: Final[float] = 400.0

#: Faixa reservada para scores de mate, garantindo mate > qualquer score comum.
MATE_EP_EPSILON: Final[float] = 1e-4
MATE_DISTANCE_CAP: Final[int] = 100
NON_MATE_EP_CEILING: Final[float] = EP_MAX - 2 * MATE_EP_EPSILON
NON_MATE_EP_FLOOR: Final[float] = EP_MIN + 2 * MATE_EP_EPSILON


@dataclass(frozen=True)
class ExpectedPointsLoss:
    """Perda de EP da candidata em relacao a melhor jogada.

    ``clamped_noise`` marca diferencas negativas dentro da tolerancia numerica
    que foram zeradas; elas indicam ruido de busca, nao superioridade real.
    """

    value: float
    raw_difference: float
    clamped_noise: bool


def clamp_expected_points(value: float) -> float:
    """Prende EP em [0, 1]. Use apenas para ruido numerico, nao para esconder bug."""
    if math.isnan(value):
        raise InvalidEvaluationError("EP nao pode ser NaN")
    return min(EP_MAX, max(EP_MIN, value))


def expected_points_from_wdl(wdl: tuple[int, int, int]) -> float:
    """EP = (wins + 0.5 * draws) / total, com WDL do ponto de vista do jogador."""
    wins, draws, losses = wdl
    if wins < 0 or draws < 0 or losses < 0:
        raise InvalidEvaluationError(f"WDL com componente negativo: {wdl!r}")
    total = wins + draws + losses
    if total == 0:
        raise InvalidEvaluationError("WDL com total zero nao define pontos esperados")
    raw = (wins + 0.5 * draws) / total
    return _reserve_mate_band(raw)


def expected_points_from_centipawns(centipawns: int) -> float:
    """Fallback versionado. Monotonico crescente, EP(0) = 0.5."""
    raw = 1.0 / (1.0 + 10.0 ** (-centipawns / CP_LOGISTIC_SCALE))
    return _reserve_mate_band(raw)


def expected_points_from_mate(mate_in: int) -> float:
    """Mate a favor tende a 1, mate contra tende a 0.

    A distancia de mate so desempata dentro da faixa reservada; ela nunca entra
    em aritmetica de centipawns.
    """
    if mate_in == 0:
        raise InvalidEvaluationError("mate_in == 0 e ambiguo")
    distance = min(abs(mate_in), MATE_DISTANCE_CAP)
    offset = MATE_EP_EPSILON * (distance / MATE_DISTANCE_CAP)
    return EP_MAX - offset if mate_in > 0 else EP_MIN + offset


def flip_expected_points(expected_points: float) -> float:
    """Troca o ponto de vista de uma avaliacao ja normalizada."""
    return clamp_expected_points(EP_MAX - expected_points)


def flip_wdl(wdl: tuple[int, int, int]) -> tuple[int, int, int]:
    wins, draws, losses = wdl
    return (losses, draws, wins)


def expected_points_loss(
    best_expected_points: float,
    candidate_expected_points: float,
    tolerance: float = EP_NOISE_TOLERANCE,
) -> ExpectedPointsLoss:
    """Perda de EP da candidata; nunca negativa apos tolerancia."""
    raw = best_expected_points - candidate_expected_points
    if raw < -tolerance:
        raise InvalidEvaluationError(
            "Candidata superou a melhor jogada alem da tolerancia de ruido "
            f"(diferenca={raw:.9f}); revise o estagio de confirmacao."
        )
    if raw < 0.0:
        return ExpectedPointsLoss(value=0.0, raw_difference=raw, clamped_noise=True)
    return ExpectedPointsLoss(value=raw, raw_difference=raw, clamped_noise=False)


def _reserve_mate_band(raw: float) -> float:
    """Mantem scores nao-mate estritamente dentro da faixa nao reservada."""
    return min(NON_MATE_EP_CEILING, max(NON_MATE_EP_FLOOR, clamp_expected_points(raw)))
