from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from brilliant_chess.interfaces.cli.commands import EXIT_NOT_IMPLEMENTED, app

runner = CliRunner()
STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        "engine:\n  threads: 1\n  workers: 1\n"
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n",
        encoding="utf-8",
    )
    return path


def test_doctor_json_output_is_machine_readable(config_path):
    result = runner.invoke(app, ["doctor", "--config", str(config_path), "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["command"] == "doctor"
    assert payload["schema_version"] == "1"
    assert payload["checks"]
    assert "engine_binary" in payload


def test_doctor_human_output_lists_checks(config_path):
    result = runner.invoke(app, ["doctor", "--config", str(config_path)])
    assert "doctor" in result.stdout
    assert "python" in result.stdout


def test_doctor_with_missing_config_exits_with_usage_error(tmp_path):
    result = runner.invoke(app, ["doctor", "--config", str(tmp_path / "ausente.yaml")])
    assert result.exit_code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ["analyze-position", "--fen", STARTPOS],
        ["classify-move", "--fen", STARTPOS, "--move", "e2e4"],
        ["choose-move", "--fen", STARTPOS],
        ["analyze-pgn", "partida.pgn"],
        ["explain", "--analysis-id", "abc"],
    ],
)
def test_unimplemented_commands_fail_loudly(arguments):
    result = runner.invoke(app, arguments)
    assert result.exit_code == EXIT_NOT_IMPLEMENTED
