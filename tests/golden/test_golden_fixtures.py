"""Validacao estrutural das fixtures golden.

O julgamento golden completo depende do motor real e entra na Entrega 8. Este
teste garante desde ja que nenhuma fixture invalida ou com campo faltando entre
no repositorio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "positions"
REQUIRED_FIELDS = {
    "id",
    "fen",
    "candidate_uci",
    "expected",
    "expected_passed_gates",
    "expected_failed_gates",
    "source",
    "verified_by",
    "rule_set",
}
VALID_EXPECTATIONS = {"brilliant", "not_brilliant", "indeterminate"}


def fixture_files() -> list[Path]:
    return sorted(FIXTURES.glob("position_*.json"))


@pytest.mark.golden
def test_fixture_directory_exists():
    assert FIXTURES.is_dir()


@pytest.mark.golden
@pytest.mark.parametrize("path", fixture_files(), ids=lambda p: p.stem)
def test_fixture_has_the_documented_schema(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_FIELDS - data.keys()
    assert not missing, f"{path.name} sem campos {sorted(missing)}"
    assert data["expected"] in VALID_EXPECTATIONS
    assert data["id"] == path.stem


@pytest.mark.golden
def test_corpus_is_pending():
    if not fixture_files():
        pytest.skip("Corpus golden entra na Entrega 8; nenhuma fixture presente ainda")
