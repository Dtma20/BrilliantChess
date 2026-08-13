"""Erros de dominio. Adapters devem reclassificar excecoes externas nestes tipos."""

from __future__ import annotations


class BrilliantChessError(Exception):
    """Raiz de todos os erros do projeto."""


class DomainError(BrilliantChessError):
    """Violacao de invariante ou entrada invalida no dominio."""


class InvalidFenError(DomainError):
    def __init__(self, fen: str, reason: str) -> None:
        super().__init__(f"FEN invalida ({reason}): {fen!r}")
        self.fen = fen
        self.reason = reason


class InvalidMoveError(DomainError):
    def __init__(self, move: str, reason: str) -> None:
        super().__init__(f"Jogada invalida ({reason}): {move!r}")
        self.move = move
        self.reason = reason


class IllegalMoveError(DomainError):
    def __init__(self, move: str, fen: str) -> None:
        super().__init__(f"Jogada ilegal {move!r} na posicao {fen!r}")
        self.move = move
        self.fen = fen


class InvalidEvaluationError(DomainError):
    """Score do motor ausente, contraditorio ou fora do dominio esperado."""


class ConfigurationError(BrilliantChessError):
    """Configuracao ausente, invalida ou inconsistente."""


class EngineError(BrilliantChessError):
    """Falha na comunicacao ou no ciclo de vida do motor."""


class EngineNotFoundError(EngineError):
    pass


class EngineProtocolError(EngineError):
    pass


class EngineTimeoutError(EngineError):
    pass


class RepositoryError(BrilliantChessError):
    """Falha de persistencia."""


class GameSourceError(BrilliantChessError):
    """PGN corrompido ou fonte de partidas indisponivel."""
