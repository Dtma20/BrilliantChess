from __future__ import annotations

from pathlib import Path

from brilliant_chess.bootstrap.config import Settings
from brilliant_chess.interfaces.web.engine_pair_session import EnginePairSession


class FakeEngine:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_pair_session_creates_two_engines_with_split_resources(monkeypatch):
    settings = Settings.model_validate(
        {
            "engine": {
                "threads": 6,
                "hash_mb": 1024,
                "timeout_seconds": 30.0,
            }
        }
    )
    created: list[FakeEngine] = []
    captured_options: list[tuple[Path, int, int, float]] = []

    monkeypatch.setattr(
        "brilliant_chess.interfaces.web.engine_pair_session.locate_engine_binary",
        lambda _: type("Info", (), {"path": Path("fake/stockfish"), "usable": True})(),
    )

    def create(binary_path, options, timeout_seconds):
        captured_options.append((binary_path, options.threads, options.hash_mb, timeout_seconds))
        engine = FakeEngine()
        created.append(engine)
        return engine

    monkeypatch.setattr(
        "brilliant_chess.interfaces.web.engine_pair_session.StockfishEngine", create
    )

    pair = EnginePairSession(settings)

    assert pair.white_engine() is not pair.black_engine()
    assert captured_options == [
        (Path("fake/stockfish"), 3, 512, 30.0),
        (Path("fake/stockfish"), 3, 512, 30.0),
    ]

    pair.close()
    pair.close()

    assert all(engine.closed for engine in created)


def test_pair_session_applies_minimum_split_resource_floors(monkeypatch):
    settings = Settings.model_validate({"engine": {"threads": 1, "hash_mb": 16}})
    captured_options: list[tuple[int, int]] = []

    monkeypatch.setattr(
        "brilliant_chess.interfaces.web.engine_pair_session.locate_engine_binary",
        lambda _: type("Info", (), {"path": Path("fake/stockfish"), "usable": True})(),
    )
    monkeypatch.setattr(
        "brilliant_chess.interfaces.web.engine_pair_session.StockfishEngine",
        lambda _, options, __: (
            captured_options.append((options.threads, options.hash_mb)) or FakeEngine()
        ),
    )

    pair = EnginePairSession(settings)

    pair.white_engine()
    pair.black_engine()

    assert captured_options == [(1, 16), (1, 16)]
