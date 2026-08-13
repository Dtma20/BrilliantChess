"""Armazenamento volatil e limitado das partidas do laboratorio."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict

from brilliant_chess.application.play_match import MatchState
from brilliant_chess.domain.errors import DomainError

MAX_MATCHES = 16


class MatchStore:
    def __init__(self, max_matches: int = MAX_MATCHES) -> None:
        self._matches: OrderedDict[str, MatchState] = OrderedDict()
        self._lock = threading.Lock()
        self._max_matches = max_matches

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def get(self, match_id: str) -> MatchState:
        with self._lock:
            state = self._matches.get(match_id)
        if state is None:
            raise DomainError(f"Partida desconhecida: {match_id}")
        return state

    def save(self, state: MatchState) -> MatchState:
        with self._lock:
            self._matches[state.match_id] = state
            self._matches.move_to_end(state.match_id)
            while len(self._matches) > self._max_matches:
                self._matches.popitem(last=False)
        return state

    def __len__(self) -> int:
        with self._lock:
            return len(self._matches)
