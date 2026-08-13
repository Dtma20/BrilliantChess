from __future__ import annotations

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN
from brilliant_chess.application.play_match import MatchPolicy, MatchProfile, start_match
from brilliant_chess.domain.errors import DomainError
from brilliant_chess.interfaces.web.match_store import MatchStore


def make_state(match_id: str):
    return start_match(
        match_id,
        STARTING_FEN,
        MatchProfile("maximo", MatchPolicy.NORMAL),
        MatchProfile("iniciante", MatchPolicy.NORMAL),
    )


def test_store_saves_gets_and_evicts_oldest_match():
    store = MatchStore(max_matches=2)
    first = store.save(make_state("first"))
    store.save(make_state("second"))
    store.save(make_state("third"))

    assert store.get("third") == make_state("third")
    assert len(store) == 2
    with pytest.raises(DomainError):
        store.get(first.match_id)


def test_store_new_id_is_usable():
    store = MatchStore()
    match_id = store.new_id()
    assert isinstance(match_id, str)
    assert len(match_id) == 12
