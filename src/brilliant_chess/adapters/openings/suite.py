"""Carregamento e validacao da suite de aberturas offline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from brilliant_chess.domain.errors import ConfigurationError
from brilliant_chess.domain.opening import OpeningLine

DEFAULT_SUITE_PATH = Path("data/openings/suite_v1.yaml")


def load_opening_suite(path: Path | None = None) -> tuple[OpeningLine, ...]:
    target = path or DEFAULT_SUITE_PATH
    if not target.exists():
        raise ConfigurationError(f"Arquivo de aberturas nao encontrado: {target}")
    try:
        raw: Any = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML de aberturas invalido em {target}: {exc}") from exc

    if not isinstance(raw, dict) or "openings" not in raw or not isinstance(raw["openings"], list):
        raise ConfigurationError(f"Formato invalido no arquivo de aberturas: {target}")

    lines: list[OpeningLine] = []
    for index, item in enumerate(raw["openings"]):
        if not isinstance(item, dict):
            raise ConfigurationError(f"Item de abertura invalido na posicao {index}: {item}")
        try:
            line_id = str(item["line_id"])
            family = str(item["family"])
            eco = str(item["eco"])
            name = str(item["name"])
            variation = str(item["variation"]) if item.get("variation") is not None else None
            moves = item.get("moves_uci")
            if not isinstance(moves, list) or not moves:
                raise ValueError("moves_uci deve ser uma lista nao-vazia")
            moves_uci = tuple(str(m) for m in moves)
            weight = float(item.get("weight", 1.0))
            if weight <= 0.0:
                raise ValueError("weight deve ser positivo")
            lines.append(
                OpeningLine(
                    line_id=line_id,
                    family=family,
                    eco=eco,
                    name=name,
                    variation=variation,
                    moves_uci=moves_uci,
                    weight=weight,
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ConfigurationError(
                f"Erro ao processar linha de abertura {item.get('line_id', index)}: {exc}"
            ) from exc

    if not lines:
        raise ConfigurationError(f"Nenhuma linha valida encontrada em {target}")

    return tuple(sorted(lines, key=lambda line: line.line_id))
