"""Caso de uso ``doctor``: verifica ambiente, motor, escrita e configuracao.

Nao renderiza nada. A CLI decide como mostrar e qual codigo de saida usar.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from brilliant_chess.adapters.stockfish.client import EngineOptions, StockfishEngine
from brilliant_chess.adapters.stockfish.diagnostics import EngineBinaryInfo, locate_engine_binary
from brilliant_chess.bootstrap.container import Container
from brilliant_chess.domain.errors import EngineError

MINIMUM_PYTHON = (3, 12)
_REQUIRED_MODULES = ("chess", "pydantic", "typer", "rich", "yaml", "structlog")
_SHA_PREVIEW_CHARS = 16
_PROBE_THREADS = 1
_PROBE_HASH_MB = 16
_PROBE_TIMEOUT_SECONDS = 30.0


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    PENDING = "pending"


@dataclass(frozen=True)
class Check:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[Check, ...]
    engine: EngineBinaryInfo

    @property
    def has_critical_failure(self) -> bool:
        return any(check.status is CheckStatus.FAIL for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 1 if self.has_critical_failure else 0


def run_doctor(container: Container) -> DoctorReport:
    engine = locate_engine_binary(container.settings.resolved_engine_path())
    checks = (
        _python_check(),
        *_dependency_checks(),
        _config_check(container),
        *_engine_checks(engine),
        _cpu_check(container),
        _storage_check(container),
        _database_schema_check(),
    )
    return DoctorReport(checks=checks, engine=engine)


def _python_check() -> Check:
    current = sys.version_info[:3]
    ok = current >= MINIMUM_PYTHON
    return Check(
        name="python",
        status=CheckStatus.OK if ok else CheckStatus.FAIL,
        detail=f"{'.'.join(map(str, current))} (minimo {'.'.join(map(str, MINIMUM_PYTHON))})",
    )


def _dependency_checks() -> tuple[Check, ...]:
    return tuple(
        Check(
            name=f"dependencia:{module}",
            status=(CheckStatus.OK if importlib.util.find_spec(module) else CheckStatus.FAIL),
            detail="importavel" if importlib.util.find_spec(module) else "ausente",
        )
        for module in _REQUIRED_MODULES
    )


def _config_check(container: Container) -> Check:
    return Check(
        name="configuracao",
        status=CheckStatus.OK,
        detail=(
            f"{container.config_path} valida; rule_set={container.rules.id} "
            f"perfil={container.rules.rating_profile}"
        ),
    )


def _engine_checks(engine: EngineBinaryInfo) -> tuple[Check, ...]:
    if engine.path is None:
        located = Check(
            name="motor:localizacao",
            status=CheckStatus.FAIL,
            detail=(
                "Stockfish nao encontrado. Defina BRILLIANT_CHESS_STOCKFISH, "
                "engine.binary_path na configuracao, ou coloque o binario no PATH."
            ),
        )
    elif not engine.exists:
        located = Check(
            name="motor:localizacao",
            status=CheckStatus.FAIL,
            detail=f"Caminho informado nao existe: {engine.path} (origem: {engine.source})",
        )
    elif not engine.is_executable:
        located = Check(
            name="motor:localizacao",
            status=CheckStatus.FAIL,
            detail=f"Arquivo encontrado mas nao executavel: {engine.path}",
        )
    else:
        sha = (engine.sha256 or "")[:_SHA_PREVIEW_CHARS]
        located = Check(
            name="motor:localizacao",
            status=CheckStatus.OK,
            detail=f"{engine.path} (origem: {engine.source}, sha256 {sha}...)",
        )
    return (located, _handshake_check(engine))


def _handshake_check(engine: EngineBinaryInfo) -> Check:
    """Sobe o processo, faz o handshake UCI e encerra, mesmo em caso de erro."""
    if engine.path is None or not engine.usable:
        return Check(
            name="motor:handshake_uci",
            status=CheckStatus.FAIL,
            detail="Nao executado: executavel do motor indisponivel",
        )
    try:
        with StockfishEngine(
            engine.path,
            EngineOptions(threads=_PROBE_THREADS, hash_mb=_PROBE_HASH_MB),
            timeout_seconds=_PROBE_TIMEOUT_SECONDS,
        ) as probe:
            identity = probe.identity()
    except EngineError as exc:
        return Check(name="motor:handshake_uci", status=CheckStatus.FAIL, detail=str(exc))
    nnue = identity.nnue_name or "nao informada"
    return Check(
        name="motor:handshake_uci",
        status=CheckStatus.OK,
        detail=f"{identity.name} {identity.version} · NNUE {nnue}",
    )


def _cpu_check(container: Container) -> Check:
    logical = os.cpu_count() or 1
    engine = container.settings.engine
    demand = engine.threads * engine.workers
    if demand > logical:
        status = CheckStatus.WARN
        detail = (
            f"threads({engine.threads}) x workers({engine.workers}) = {demand} "
            f"excede {logical} CPUs logicas"
        )
    else:
        status = CheckStatus.OK
        detail = f"threads={engine.threads} workers={engine.workers} cpus={logical}"
    return Check(name="cpu", status=status, detail=detail)


def _storage_check(container: Container) -> Check:
    directory = container.database_path.parent or Path()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".brilliant_chess_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check(name="escrita", status=CheckStatus.FAIL, detail=f"{directory}: {exc}")
    return Check(name="escrita", status=CheckStatus.OK, detail=f"{directory} gravavel")


def _database_schema_check() -> Check:
    return Check(
        name="banco:schema",
        status=CheckStatus.PENDING,
        detail="Migrations e schema SQLite chegam na Entrega 7",
    )
