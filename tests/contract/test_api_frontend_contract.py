"""Contrato entre os enums do backend e as unioes de tipos do front.

O front nao valida schema em tempo de execucao: se um valor novo aparecer no
backend sem entrar em ``frontend/src/lib/api.ts``, o erro so apareceria na tela.
Este teste transforma esse descompasso em falha de build.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from brilliant_chess.application.play_match import MatchPolicy, SelectionKind
from brilliant_chess.domain.values import GameStatus, GateStatus, PieceType, SacrificeKind
from brilliant_chess.interfaces.web.schemas import API_SCHEMA_VERSION

API_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api.ts"

_UNION = re.compile(r"export type (?P<name>\w+) =(?P<body>(?:[^\n]*\n(?:\s*\|[^\n]*\n)*))")


def _unions() -> dict[str, set[str]]:
    """Le cada ``export type X = "a" | "b"`` como um conjunto de literais."""
    source = API_TS.read_text(encoding="utf-8")
    found: dict[str, set[str]] = {}
    for match in _UNION.finditer(source):
        literals = set(re.findall(r'"([^"]+)"', match.group("body")))
        if literals:
            found[match.group("name")] = literals
    return found


@pytest.fixture(scope="module")
def unions() -> dict[str, set[str]]:
    return _unions()


@pytest.mark.parametrize(
    ("type_name", "enum"),
    [
        ("SelectionKind", SelectionKind),
        ("MatchPolicy", MatchPolicy),
        ("GateStatus", GateStatus),
        ("GameStatus", GameStatus),
        ("SacrificeKind", SacrificeKind),
        ("PieceName", PieceType),
    ],
)
def test_frontend_union_matches_the_backend_enum(unions, type_name, enum):
    assert type_name in unions, f"{type_name} nao esta declarado em api.ts"
    assert unions[type_name] == {member.value for member in enum}


def test_frontend_pins_the_current_schema_version():
    source = API_TS.read_text(encoding="utf-8")
    match = re.search(r'API_SCHEMA_VERSION = "([^"]+)"', source)
    assert match is not None, "api.ts precisa fixar a versao de schema conhecida"
    assert match.group(1) == API_SCHEMA_VERSION
