from __future__ import annotations

from pathlib import Path

import pytest

from brilliant_chess.application.diagnose import CheckStatus, run_doctor
from brilliant_chess.bootstrap.config import ENGINE_PATH_ENV_VAR, LEGACY_ENGINE_PATH_ENV_VAR
from brilliant_chess.bootstrap.container import build_container


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        "engine:\n"
        "  threads: 1\n"
        "  workers: 1\n"
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(autouse=True)
def _isolated_engine_lookup(monkeypatch, tmp_path):
    """Isola a busca do motor: nem PATH nem o diretorio local do repositorio."""
    monkeypatch.delenv(ENGINE_PATH_ENV_VAR, raising=False)
    monkeypatch.delenv(LEGACY_ENGINE_PATH_ENV_VAR, raising=False)
    monkeypatch.setattr(
        "brilliant_chess.adapters.stockfish.diagnostics.LOCAL_ENGINE_DIR",
        tmp_path / "sem-motor",
    )
    monkeypatch.setattr("shutil.which", lambda _name: None)


def check_named(report, name):
    return next(check for check in report.checks if check.name == name)


def test_missing_engine_is_a_critical_failure(config_path):
    report = run_doctor(build_container(config_path))
    assert check_named(report, "motor:localizacao").status is CheckStatus.FAIL
    assert report.exit_code == 1
    assert "BRILLIANT_CHESS_STOCKFISH" in check_named(report, "motor:localizacao").detail


def test_handshake_is_not_reported_as_ok_without_a_binary(config_path):
    report = run_doctor(build_container(config_path))
    handshake = check_named(report, "motor:handshake_uci")
    assert handshake.status is CheckStatus.FAIL
    assert "indisponivel" in handshake.detail


def test_configured_path_that_does_not_exist_is_reported(config_path, tmp_path, monkeypatch):
    monkeypatch.setenv(ENGINE_PATH_ENV_VAR, str(tmp_path / "sem_stockfish.exe"))
    report = run_doctor(build_container(config_path))
    assert check_named(report, "motor:localizacao").status is CheckStatus.FAIL


def test_binary_that_is_not_stockfish_fails_the_handshake(config_path, tmp_path, monkeypatch):
    """Um arquivo qualquer nao pode ser aceito como motor."""
    binary = tmp_path / "stockfish.exe"
    binary.write_bytes(b"nao sou um motor")
    monkeypatch.setenv(ENGINE_PATH_ENV_VAR, str(binary))
    report = run_doctor(build_container(config_path))
    assert report.engine.sha256 is not None
    assert len(report.engine.sha256) == 64
    assert check_named(report, "motor:handshake_uci").status is CheckStatus.FAIL


def test_local_engine_directory_is_searched_before_path(config_path, tmp_path, monkeypatch):
    engines = tmp_path / "engines"
    engines.mkdir()
    binary = engines / "stockfish.exe"
    binary.write_bytes(b"nao sou um motor")
    monkeypatch.setattr("brilliant_chess.adapters.stockfish.diagnostics.LOCAL_ENGINE_DIR", engines)
    report = run_doctor(build_container(config_path))
    assert report.engine.path == binary
    assert "diretorio local" in check_named(report, "motor:localizacao").detail


def test_oversubscribed_cpu_is_a_warning_not_a_failure(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "engine:\n  threads: 64\n  workers: 64\n"
        f"storage:\n  database_path: {(tmp_path / 'db.sqlite3').as_posix()}\n",
        encoding="utf-8",
    )
    report = run_doctor(build_container(path))
    assert check_named(report, "cpu").status is CheckStatus.WARN


def test_storage_directory_is_created_and_writable(config_path, tmp_path):
    report = run_doctor(build_container(config_path))
    assert check_named(report, "escrita").status is CheckStatus.OK
    assert tmp_path.exists()


def test_all_required_dependencies_are_importable(config_path):
    report = run_doctor(build_container(config_path))
    dependency_checks = [c for c in report.checks if c.name.startswith("dependencia:")]
    assert dependency_checks
    assert all(check.status is CheckStatus.OK for check in dependency_checks)
