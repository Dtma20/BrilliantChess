"""Logica de aplicacao para selecao e amostragem de aberturas no laboratorio."""

from __future__ import annotations

import math
import random

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.models import AnalysisBudget, Move, Position
from brilliant_chess.domain.opening import (
    OpeningConfig,
    OpeningExitReason,
    OpeningLine,
    OpeningMode,
    OpeningMoveAudit,
)
from brilliant_chess.ports.board import BoardService
from brilliant_chess.ports.engine import ChessEngine


class OpeningSelector:
    """Seleciona deterministicamente linhas da suite e amostra lances extras."""

    def __init__(self, lines: tuple[OpeningLine, ...], board: BoardService) -> None:
        self._lines = tuple(sorted(lines, key=lambda line: line.line_id))
        self._board = board

    @property
    def lines(self) -> tuple[OpeningLine, ...]:
        return self._lines

    def choose(
        self,
        initial_fen: str,
        config: OpeningConfig,
        usage_counts: dict[str, int] | None = None,
    ) -> tuple[OpeningLine | None, int, OpeningExitReason | None]:
        if config.mode is OpeningMode.OFF:
            return None, 0, OpeningExitReason.DISABLED

        rng = random.Random(config.seed)
        compatible: list[OpeningLine] = []
        for line in self._lines:
            try:
                self._board.view(initial_fen, line.moves_uci)
                compatible.append(line)
            except DomainError:
                continue

        if not compatible:
            return None, 0, OpeningExitReason.NO_COMPATIBLE_LINE

        if config.line_id is not None:
            matching = [line for line in compatible if line.line_id == config.line_id]
            if not matching:
                return None, 0, OpeningExitReason.NO_COMPATIBLE_LINE
            selected_line = matching[0]
            planned_exit_ply = len(selected_line.moves_uci)
            return selected_line, planned_exit_ply, None

        if usage_counts is not None:
            weights = [
                line.weight / (1.0 + float(usage_counts.get(line.line_id, 0)))
                for line in compatible
            ]
        else:
            weights = [line.weight for line in compatible]

        selected_line = rng.choices(compatible, weights=weights, k=1)[0]
        exit_fullmove = rng.randint(config.min_fullmove, config.max_fullmove)
        planned_exit_ply = min(exit_fullmove * 2, len(selected_line.moves_uci))

        return selected_line, planned_exit_ply, None

    def sample_multipv_move(  # noqa: PLR0913
        self,
        position: Position,
        engine: ChessEngine,
        config: OpeningConfig,
        rng: random.Random,
        *,
        opening_ply: int,
        planned_exit_ply: int,
        eco: str = "",
        name: str = "",
        variation: str | None = None,
    ) -> tuple[Move | None, OpeningMoveAudit | None, OpeningExitReason | None]:
        try:
            evals = engine.analyze(
                position,
                budget=AnalysisBudget(nodes=config.budget_nodes),
                multipv=config.multipv,
            )
        except Exception:
            return None, None, OpeningExitReason.ENGINE_ERROR

        if not evals:
            return None, None, OpeningExitReason.ENGINE_ERROR

        best_ep = max(e.expected_points for e in evals)
        candidates = [
            e for e in evals if (best_ep - e.expected_points) <= (config.max_ep_loss + 1e-9)
        ]

        if not candidates:
            return None, None, OpeningExitReason.NO_ACCEPTABLE_CANDIDATE

        sorted_candidates = sorted(candidates, key=lambda e: e.move_uci)
        temp = max(config.temperature, 1e-9)
        weights = [math.exp(-(best_ep - e.expected_points) / temp) for e in sorted_candidates]
        chosen = rng.choices(sorted_candidates, weights=weights, k=1)[0]

        weight_sum = sum(weights)
        chosen_idx = sorted_candidates.index(chosen)
        norm_weight = weights[chosen_idx] / weight_sum if weight_sum > 0 else 1.0

        audit = OpeningMoveAudit(
            opening_mode=config.mode,
            seed=config.seed or 0,
            eco=eco,
            name=name,
            variation=variation,
            source="multipv_sampling",
            candidate_rank=chosen.multipv_rank,
            candidate_ep_loss=best_ep - chosen.expected_points,
            sampling_weight=norm_weight,
            candidates_considered=tuple(e.move_uci for e in evals),
            quality_cutoff=config.max_ep_loss,
            search_budget=AnalysisBudget(nodes=config.budget_nodes),
            opening_ply=opening_ply,
            planned_exit_ply=planned_exit_ply,
            sampling_mode="temperature",
            experimental=config.experimental,
        )
        return Move(chosen.move_uci, chosen.move_san), audit, None
