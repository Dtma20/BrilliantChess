"""Contrato de persistencia e cache de analises."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity, Move, MoveEvaluation
from brilliant_chess.domain.values import AnalysisState


@dataclass(frozen=True)
class AnalysisCacheKey:
    """Chave completa do cache (secao 17.1).

    Um resultado raso nunca pode ser reaproveitado como analise profunda, por
    isso orcamento, MultiPV e versoes de mapeamento fazem parte da chave.
    """

    fen: str
    root_moves_uci: tuple[str, ...]
    engine_binary_sha256: str
    engine_version: str
    nnue_name: str | None
    engine_options_fingerprint: str
    budget_fingerprint: str
    multipv: int
    wdl_mapping_version: str
    rule_set_version: str


@dataclass(frozen=True)
class StoredAnalysis:
    analysis_id: str
    state: AnalysisState
    key: AnalysisCacheKey
    identity: EngineIdentity
    budget: AnalysisBudget
    evaluations: tuple[MoveEvaluation, ...]
    error: str | None = None


class AnalysisRepository(Protocol):
    def get(self, key: AnalysisCacheKey) -> StoredAnalysis | None: ...

    def save(self, analysis: StoredAnalysis) -> None: ...

    def mark(self, analysis_id: str, state: AnalysisState, error: str | None = None) -> None: ...

    def list_for_position(self, fen: str) -> Sequence[StoredAnalysis]: ...


def root_moves_fingerprint(root_moves: Sequence[Move] | None) -> tuple[str, ...]:
    """Ordem estavel para que a chave nao dependa da ordem de chamada."""
    if root_moves is None:
        return ()
    return tuple(sorted(move.uci for move in root_moves))
