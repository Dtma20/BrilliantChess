"""Traducao entre python-chess e o dominio.

Nenhum objeto de python-chess atravessa esta fronteira (ADR 0004). O ponto de
vista e sempre o do lado a jogar na posicao raiz, nunca o do lado que jogaria
depois da candidata.
"""

from __future__ import annotations

from typing import Any

import chess
import chess.engine

from brilliant_chess.domain.errors import InvalidEvaluationError
from brilliant_chess.domain.models import (
    MoveEvaluation,
    NormalizedEvaluation,
    PrincipalVariation,
)
from brilliant_chess.domain.values import Color

COLOR_FROM_CHESS = {chess.WHITE: Color.WHITE, chess.BLACK: Color.BLACK}
COLOR_TO_CHESS = {Color.WHITE: chess.WHITE, Color.BLACK: chess.BLACK}


def normalized_evaluation(info: chess.engine.InfoDict, mover: Color) -> NormalizedEvaluation:
    """Converte score e WDL para o ponto de vista de ``mover``."""
    score = info.get("score")
    if score is None:
        raise InvalidEvaluationError("Motor devolveu linha sem score")
    pov_score = score.pov(COLOR_TO_CHESS[mover])
    mate_in = pov_score.mate()
    centipawns = pov_score.score()
    return NormalizedEvaluation.create(
        mover=mover,
        centipawns=centipawns,
        mate_in=mate_in,
        wdl=_wdl_from(info, mover),
    )


def principal_variation(board: chess.Board, moves: list[chess.Move]) -> PrincipalVariation:
    """Gera UCI e SAN da PV sem mutar o tabuleiro recebido."""
    working = board.copy(stack=False)
    uci: list[str] = []
    san: list[str] = []
    for move in moves:
        if not working.is_legal(move):
            break
        san.append(working.san(move))
        uci.append(move.uci())
        working.push(move)
    return PrincipalVariation(moves_uci=tuple(uci), moves_san=tuple(san))


def move_evaluation(
    board: chess.Board,
    info: chess.engine.InfoDict,
    mover: Color,
    fallback_nodes: int = 0,
) -> MoveEvaluation:
    """Constroi a avaliacao de uma linha de MultiPV ou de uma confirmacao."""
    pv_moves = list(info.get("pv") or [])
    if not pv_moves:
        raise InvalidEvaluationError("Motor devolveu linha sem variante principal")
    first = pv_moves[0]
    if not board.is_legal(first):
        raise InvalidEvaluationError(f"Motor devolveu jogada ilegal: {first.uci()}")
    return MoveEvaluation(
        move_uci=first.uci(),
        move_san=board.san(first),
        evaluation=normalized_evaluation(info, mover),
        pv=principal_variation(board, pv_moves),
        depth=int(info.get("depth") or 0),
        nodes=int(info.get("nodes") or fallback_nodes),
        seldepth=_optional_int(info.get("seldepth")),
        multipv_rank=_optional_int(info.get("multipv")),
    )


def _wdl_from(info: chess.engine.InfoDict, mover: Color) -> tuple[int, int, int] | None:
    raw: Any = info.get("wdl")
    if raw is None:
        return None
    pov = raw.pov(COLOR_TO_CHESS[mover])
    return (int(pov.wins), int(pov.draws), int(pov.losses))


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
