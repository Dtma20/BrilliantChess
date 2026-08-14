from __future__ import annotations

from pathlib import Path

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.adapters.openings.suite import DEFAULT_SUITE_PATH, load_opening_suite
from brilliant_chess.domain.errors import ConfigurationError


def test_loading_default_suite_returns_at_least_16_legal_lines():
    lines = load_opening_suite(DEFAULT_SUITE_PATH)
    assert len(lines) >= 16

    families = {line.family for line in lines}
    assert "e4" in families
    assert "d4" in families
    assert "c4" in families
    assert "Nf3" in families
    assert "flank" in families
    assert "gambit" in families

    board = PythonChessBoardService()
    for line in lines:
        assert line.line_id
        assert line.eco
        assert line.name
        assert len(line.moves_uci) >= 10
        # Validates that the full line is legal from standard starting FEN
        view = board.view(STARTING_FEN, line.moves_uci)
        assert len(view.moves_san) == len(line.moves_uci)


def test_missing_file_raises_configuration_error(tmp_path: Path):
    with pytest.raises(ConfigurationError, match="Arquivo de aberturas nao encontrado"):
        load_opening_suite(tmp_path / "non_existent.yaml")


def test_malformed_yaml_raises_configuration_error(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("openings: [not_a_dict]", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_opening_suite(bad)


def test_empty_moves_raises_configuration_error(tmp_path: Path):
    bad = tmp_path / "bad_empty.yaml"
    bad.write_text(
        """
openings:
  - line_id: "test"
    family: "e4"
    eco: "C50"
    name: "Test"
    moves_uci: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_opening_suite(bad)
