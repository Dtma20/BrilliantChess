import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN
from brilliant_chess.adapters.game_source.pgn import parse_pgn
from brilliant_chess.domain.errors import GameSourceError


def test_parse_pgn_returns_the_mainline_from_the_standard_position():
    parsed = parse_pgn(
        """[Event "Partida de teste"]

1. e4 e5 2. Nf3 Nc6 *
"""
    )

    assert parsed.initial_fen == STARTING_FEN
    assert parsed.moves_uci == ("e2e4", "e7e5", "g1f3", "b8c6")
    assert parsed.moves_san == ("e4", "e5", "Nf3", "Nc6")


def test_parse_pgn_respects_a_custom_initial_fen():
    initial_fen = "8/5k2/8/8/8/8/8/R5K1 b - - 0 12"

    parsed = parse_pgn(
        f"""[SetUp "1"]
[FEN "{initial_fen}"]

12... Ke6 *
"""
    )

    assert parsed.initial_fen == initial_fen
    assert parsed.moves_uci == ("f7e6",)
    assert parsed.moves_san == ("Ke6",)


def test_parse_pgn_rejects_a_game_without_moves():
    with pytest.raises(GameSourceError, match="nao possui lances"):
        parse_pgn('[Event "Vazia"]\n\n*\n')


def test_parse_pgn_rejects_empty_text():
    with pytest.raises(GameSourceError, match="PGN vazio"):
        parse_pgn("")


def test_parse_pgn_rejects_corrupted_movetext_instead_of_returning_a_partial_game():
    with pytest.raises(GameSourceError, match="PGN corrompido"):
        parse_pgn("1. e4 e5 2. e5 *")


def test_parse_pgn_reclassifies_an_invalid_setup_fen():
    with pytest.raises(GameSourceError, match="PGN corrompido"):
        parse_pgn('[SetUp "1"]\n[FEN "invalida"]\n\n1. e4 *')
