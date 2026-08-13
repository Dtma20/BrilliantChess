from __future__ import annotations

import pytest

from brilliant_chess.domain.rule_set import RuleSet

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
BLACK_TO_MOVE_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


@pytest.fixture
def rules() -> RuleSet:
    """RuleSet strict_v1 com os valores padrao do dominio."""
    return RuleSet()
