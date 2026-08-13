"""Armazenamento em memoria das partidas locais.

Deliberadamente volatil: o app e de estudo e roda em loopback. Persistencia de
partidas entra junto com o SQLite da Entrega 7.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict

from brilliant_chess.application.play_game import GameState
from brilliant_chess.domain.errors import DomainError

MAX_GAMES = 64


class GameStore:
    def __init__(self, max_games: int = MAX_GAMES) -> None:
        self._games: OrderedDict[str, GameState] = OrderedDict()
        self._lock = threading.Lock()
        self._max_games = max_games

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def get(self, game_id: str) -> GameState:
        with self._lock:
            state = self._games.get(game_id)
        if state is None:
            raise DomainError(f"Partida desconhecida: {game_id}")
        return state

    def save(self, state: GameState) -> GameState:
        with self._lock:
            self._games[state.game_id] = state
            self._games.move_to_end(state.game_id)
            while len(self._games) > self._max_games:
                self._games.popitem(last=False)
        return state

    def __len__(self) -> int:
        with self._lock:
            return len(self._games)
