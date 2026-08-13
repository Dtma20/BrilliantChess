"""Ponto de entrada da CLI."""

from __future__ import annotations

from brilliant_chess.interfaces.cli.commands import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
