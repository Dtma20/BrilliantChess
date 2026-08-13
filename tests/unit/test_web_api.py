"""Testes da API local com motor falso injetado no lugar do Stockfish."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brilliant_chess.adapters.board.service import STARTING_FEN
from brilliant_chess.application import play_game
from brilliant_chess.bootstrap.container import build_container
from brilliant_chess.domain.values import Color
from brilliant_chess.interfaces.web.app import create_app
from tests.fakes.stub_engine import StubSession

MATE_IN_ONE_FEN = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"


def save_game(client, initial_fen=STARTING_FEN, moves=()):
    board = client.app.state.board
    store = client.app.state.games
    state = play_game.start_game(store.new_id(), initial_fen, Color.WHITE, "clube")
    view = board.view(initial_fen, moves)
    state = play_game.GameState(
        game_id=state.game_id,
        initial_fen=initial_fen,
        moves_uci=tuple(moves),
        moves_san=view.moves_san,
        human_color=state.human_color,
        strength_key=state.strength_key,
    )
    return store.save(state)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    config = tmp_path / "config.yaml"
    config.write_text(
        "engine:\n  threads: 1\n  workers: 1\n"
        "web:\n  analysis_multipv: 3\n  max_arrows: 2\n"
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n",
        encoding="utf-8",
    )
    app = create_app(build_container(config))
    app.state.engine_session = StubSession()
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_the_rule_set(client):
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["rule_set"] == "strict_v1"


def test_strengths_are_listed(client):
    levels = client.get("/api/strengths").json()
    keys = [level["key"] for level in levels]
    assert "iniciante" in keys
    assert "maximo" in keys
    assert levels[-1]["elo"] is None


def test_pages_are_served(client):
    for path in ("/", "/jogar", "/analise"):
        assert client.get(path).status_code == 200
    assert client.get("/static/board.js").status_code == 200


def test_new_game_as_white_waits_for_the_human(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()
    assert game["board"]["fen"] == STARTING_FEN
    assert game["moves_uci"] == []
    assert game["engine_thinking"] is False


def test_new_game_as_black_gets_an_engine_opening_move(client):
    game = client.post("/api/game", json={"human_color": "black"}).json()
    assert len(game["moves_uci"]) == 1
    assert game["board"]["side_to_move"] == "black"
    assert game["engine_thinking"] is False


def test_human_move_is_answered_by_the_engine(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()
    played = client.post(f"/api/game/{game['game_id']}/move", json={"move": "e4"}).json()
    assert played["moves_san"][0] == "e4"
    assert len(played["moves_uci"]) == 2
    assert played["board"]["side_to_move"] == "white"


def test_illegal_move_returns_400(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()
    response = client.post(f"/api/game/{game['game_id']}/move", json={"move": "e2e5"})
    assert response.status_code == 400


def test_unknown_game_returns_400(client):
    assert client.get("/api/game/naoexiste").status_code == 400


def test_game_pgn_download_returns_attachment(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()

    response = client.get(f"/api/game/{game['game_id']}/pgn")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-chess-pgn"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="brilliant-chess-{game["game_id"]}.pgn"'
    )
    assert '[Result "*"]' in response.text


def test_game_pgn_download_reports_unknown_game(client):
    response = client.get("/api/game/naoexiste/pgn")

    assert response.status_code == 400


def test_game_pgn_download_serializes_checkmate(client):
    state = save_game(
        client,
        moves=("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"),
    )

    response = client.get(f"/api/game/{state.game_id}/pgn")

    assert response.status_code == 200
    assert '[Result "1-0"]' in response.text
    assert response.text.rstrip().endswith("1-0")


def test_game_pgn_download_serializes_custom_fen(client):
    fen = "8/5k2/8/8/8/8/8/R5K1 b - - 0 12"
    state = save_game(client, initial_fen=fen)

    response = client.get(f"/api/game/{state.game_id}/pgn")

    assert response.status_code == 200
    assert '[SetUp "1"]' in response.text
    assert f'[FEN "{fen}"]' in response.text


def test_undo_returns_the_turn_to_the_human(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()
    client.post(f"/api/game/{game['game_id']}/move", json={"move": "e4"})
    undone = client.post(f"/api/game/{game['game_id']}/undo").json()
    assert undone["moves_uci"] == []
    assert undone["engine_thinking"] is False


def test_board_endpoint_applies_moves_and_returns_san(client):
    payload = client.post("/api/board", json={"fen": None, "moves": ["e2e4", "c7c5"]}).json()
    assert payload["moves_san"] == ["e4", "c5"]
    assert payload["side_to_move"] == "white"
    assert "g1f3" in payload["legal_moves"]


def test_board_endpoint_rejects_bad_fen(client):
    assert client.post("/api/board", json={"fen": "invalida"}).status_code == 400


def test_analysis_returns_ranked_candidates_and_arrows(client):
    payload = client.post("/api/analyze", json={"fen": STARTING_FEN}).json()
    assert payload["schema_version"] == "1"
    assert payload["side_to_move"] == "white"
    assert len(payload["candidates"]) == 3
    assert [item["rank"] for item in payload["candidates"]] == [1, 2, 3]
    assert len(payload["arrows"]) == 2
    arrow = payload["arrows"][0]
    assert len(arrow["from_square"]) == 2
    assert arrow["color"].startswith("#")


def test_analysis_of_a_finished_position_has_no_arrows(client):
    checkmate = "7k/5QQ1/8/8/8/8/8/7K b - - 0 1"
    payload = client.post("/api/analyze", json={"fen": checkmate}).json()
    assert payload["candidates"] == []
    assert payload["arrows"] == []


def test_analysis_honours_the_requested_line_count(client):
    payload = client.post("/api/analyze", json={"fen": MATE_IN_ONE_FEN, "multipv": 2}).json()
    assert len(payload["candidates"]) == 2


def test_engine_is_closed_on_shutdown(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n", encoding="utf-8"
    )
    app = create_app(build_container(config))
    session = StubSession()
    app.state.engine_session = session
    with TestClient(app):
        pass
    assert session.closed is True
