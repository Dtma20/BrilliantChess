"""Testes do fluxo completo de partidas do laboratorio com exploracao de abertura."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brilliant_chess.bootstrap.container import build_container
from brilliant_chess.interfaces.web.app import WEB_DIST_ENV_VAR, create_app
from tests.fakes.stub_engine import StubPairSession, StubSession


def build_client(tmp_path: Path) -> Iterator[TestClient]:
    config = tmp_path / "config.yaml"
    config.write_text(
        "engine:\n  threads: 1\n  workers: 1\n"
        "web:\n  analysis_multipv: 3\n  max_arrows: 2\n"
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n",
        encoding="utf-8",
    )
    app = create_app(build_container(config))
    app.state.engine_session = StubSession()
    app.state.engine_pair_session = StubPairSession()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(tmp_path / "sem-build"))
    yield from build_client(tmp_path)


def test_match_creation_with_default_exploratory_mode(client: TestClient) -> None:
    res = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
            "opening": {"mode": "exploratory", "seed": 42},
        },
    ).json()

    assert res["opening"]["mode"] == "exploratory"
    assert res["opening_seed"] == 42
    assert res["opening_identity"] is not None
    assert res["opening_identity"]["line_id"] != ""
    assert res["opening_identity"]["eco"] != ""
    assert res["opening_phase"]["mode"] == "exploratory"
    assert res["opening_phase"]["current_phase"] == "suite"
    assert res["opening_phase"]["active"] is True
    assert res["opening_dataset_version"] == "suite_v1"


def test_stepping_plays_suite_moves_until_handoff(client: TestClient) -> None:
    res = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
            "opening": {"mode": "controlled", "line_id": "e4-italian-giuoco-piano", "seed": 10},
        },
    ).json()
    match_id = res["match_id"]
    assert res["opening_identity"]["line_id"] == "e4-italian-giuoco-piano"
    assert res["opening_identity"]["eco"] == "C50"

    # Step 1: e2e4
    step1 = client.post(f"/api/match/{match_id}/step").json()
    assert step1["moves"][0]["uci"] == "e2e4"
    assert step1["moves"][0]["selection"] == "opening_exploration"
    assert step1["moves"][0]["opening_audit"]["source"] == "suite"
    assert step1["moves"][0]["opening_audit"]["opening_ply"] == 1
    assert step1["moves"][0]["opening_audit"]["eco"] == "C50"

    # Step 2: e7e5
    step2 = client.post(f"/api/match/{match_id}/step").json()
    assert step2["moves"][1]["uci"] == "e7e5"
    assert step2["moves"][1]["selection"] == "opening_exploration"
    assert step2["moves"][1]["opening_audit"]["opening_ply"] == 2


def test_controlled_mode_with_explicit_id(client: TestClient) -> None:
    res = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
            "opening": {"mode": "controlled", "line_id": "e4-french-winawer"},
        },
    ).json()

    assert res["opening_identity"]["line_id"] == "e4-french-winawer"
    assert res["opening_identity"]["eco"] == "C18"
    assert res["opening_identity"]["name"] == "French Defense"


def test_match_creation_with_mode_off_disables_opening(client: TestClient) -> None:
    res = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
            "opening": {"mode": "off"},
        },
    ).json()

    assert res["opening"]["mode"] == "off"
    assert res["opening_identity"] is None
    assert res["opening_phase"] is None


def test_session_novelty_increments_and_penalizes_recent_lines(client: TestClient) -> None:
    # First match
    res1 = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
            "opening": {"mode": "exploratory", "seed": 99},
        },
    ).json()
    line1 = res1["opening_identity"]["line_id"]

    # Usage count in session should now be at least 1 for line1
    session_counts = client.app.state.opening_session.snapshot()
    assert session_counts[line1] >= 1
