"""Integracao com o Stockfish real.

Marcado como lento e pulavel enquanto o binario nao estiver disponivel. O
adapter completo (handshake, MultiPV, root moves, POV) chega na Entrega 2 e
reutiliza os testes de contrato em ``tests/contract``.
"""

from __future__ import annotations

import pytest

from brilliant_chess.adapters.stockfish.diagnostics import locate_engine_binary
from brilliant_chess.bootstrap.config import load_settings

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def engine_binary():
    settings = load_settings()
    info = locate_engine_binary(settings.resolved_engine_path())
    if not info.usable:
        pytest.skip("Stockfish nao encontrado; defina BRILLIANT_CHESS_STOCKFISH")
    return info


def test_binary_is_executable_and_hashable(engine_binary):
    assert engine_binary.usable
    assert engine_binary.sha256 is not None
    assert len(engine_binary.sha256) == 64


def test_binary_has_plausible_size(engine_binary):
    assert engine_binary.size_bytes is not None
    assert engine_binary.size_bytes > 100_000
