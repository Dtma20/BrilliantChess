"""Renderizacao humana e JSON. Nenhuma regra de dominio vive aqui."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from brilliant_chess.application.diagnose import CheckStatus, DoctorReport

#: Versao do contrato JSON publico. Mudancas incompativeis exigem incremento.
JSON_SCHEMA_VERSION = "1"

_STATUS_STYLE = {
    CheckStatus.OK: "green",
    CheckStatus.WARN: "yellow",
    CheckStatus.FAIL: "red",
    CheckStatus.PENDING: "cyan",
}


def render_doctor_human(report: DoctorReport, console: Console) -> None:
    table = Table(title="brilliant-chess doctor", show_lines=False)
    table.add_column("verificacao", no_wrap=True)
    table.add_column("estado", no_wrap=True)
    table.add_column("detalhe", overflow="fold")
    for check in report.checks:
        style = _STATUS_STYLE[check.status]
        table.add_row(check.name, f"[{style}]{check.status.value}[/{style}]", check.detail)
    console.print(table)
    if report.has_critical_failure:
        console.print("[red]Falha critica: veja as linhas marcadas como fail.[/red]")


def doctor_payload(report: DoctorReport) -> dict[str, Any]:
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "command": "doctor",
        "exit_code": report.exit_code,
        "checks": [
            {"name": c.name, "status": c.status.value, "detail": c.detail} for c in report.checks
        ],
        "engine_binary": {
            "path": str(report.engine.path) if report.engine.path else None,
            "source": report.engine.source,
            "exists": report.engine.exists,
            "is_executable": report.engine.is_executable,
            "sha256": report.engine.sha256,
            "size_bytes": report.engine.size_bytes,
        },
    }


def render_json(payload: dict[str, Any], console: Console) -> None:
    console.print_json(json.dumps(payload, ensure_ascii=False, sort_keys=True))
