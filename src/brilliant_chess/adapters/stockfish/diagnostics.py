"""Localizacao e inspecao estatica do executavel do motor.

O handshake UCI real entra na Entrega 2, junto com o cliente. Ate la o
``doctor`` reporta o handshake como pendente, nunca como aprovado.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

_CANDIDATE_NAMES = ("stockfish", "stockfish.exe")
_SHA_CHUNK_BYTES = 1024 * 1024

#: Diretorio local onde a instalacao assistida coloca o motor. Fica fora do
#: controle de versao (ver .gitignore) e e procurado antes do PATH.
LOCAL_ENGINE_DIR = Path("engines")
_LOCAL_PATTERNS = ("stockfish*.exe", "stockfish*")


@dataclass(frozen=True)
class EngineBinaryInfo:
    path: Path | None
    exists: bool
    is_executable: bool
    size_bytes: int | None
    sha256: str | None
    source: str

    @property
    def usable(self) -> bool:
        return self.exists and self.is_executable


def locate_engine_binary(configured_path: str | None) -> EngineBinaryInfo:
    """Precedencia: caminho informado, diretorio local ``engines/``, PATH."""
    if configured_path:
        return _inspect(Path(configured_path), source="configuracao ou variavel de ambiente")
    local = _find_in_local_directory()
    if local is not None:
        return _inspect(local, source=f"diretorio local {LOCAL_ENGINE_DIR}")
    for name in _CANDIDATE_NAMES:
        found = shutil.which(name)
        if found:
            return _inspect(Path(found), source="PATH")
    return EngineBinaryInfo(
        path=None,
        exists=False,
        is_executable=False,
        size_bytes=None,
        sha256=None,
        source="nao encontrado",
    )


def file_sha256(path: Path) -> str:
    """SHA-256 do binario; entra na chave de cache das analises."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_SHA_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _find_in_local_directory() -> Path | None:
    """Primeiro executavel plausivel em ``engines/``, em ordem estavel."""
    if not LOCAL_ENGINE_DIR.is_dir():
        return None
    for pattern in _LOCAL_PATTERNS:
        matches = sorted(
            candidate
            for candidate in LOCAL_ENGINE_DIR.rglob(pattern)
            if candidate.is_file() and os.access(candidate, os.X_OK)
        )
        if matches:
            return matches[0]
    return None


def _inspect(path: Path, source: str) -> EngineBinaryInfo:
    exists = path.is_file()
    if not exists:
        return EngineBinaryInfo(
            path=path,
            exists=False,
            is_executable=False,
            size_bytes=None,
            sha256=None,
            source=source,
        )
    executable = os.access(path, os.X_OK)
    return EngineBinaryInfo(
        path=path,
        exists=True,
        is_executable=executable,
        size_bytes=path.stat().st_size,
        sha256=file_sha256(path) if executable else None,
        source=source,
    )
