"""Comandos da CLI.

Comandos ainda nao entregues falham de forma explicita com codigo 3. Eles nao
devem imprimir resultado plausivel enquanto a implementacao nao existir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

from brilliant_chess.application.diagnose import run_doctor
from brilliant_chess.bootstrap.container import build_container
from brilliant_chess.domain.errors import BrilliantChessError
from brilliant_chess.interfaces.cli.rendering import (
    doctor_payload,
    render_doctor_human,
    render_json,
)
from brilliant_chess.interfaces.web.app import create_app

EXIT_NOT_IMPLEMENTED = 3
EXIT_USAGE_ERROR = 2

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Analise e selecao de jogadas brilhantes com regras auditaveis.",
)
console = Console()
error_console = Console(stderr=True)

ConfigOption = Annotated[
    Path,
    typer.Option("--config", "-c", help="Arquivo YAML de configuracao."),
]
FormatOption = Annotated[
    str,
    typer.Option("--format", "-f", help="Formato de saida: human ou json."),
]

_DEFAULT_CONFIG = Path("config/strict_v1.yaml")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@app.command()
def doctor(
    config: ConfigOption = _DEFAULT_CONFIG,
    output_format: FormatOption = "human",
) -> None:
    """Verifica ambiente, dependencias, motor, CPU e permissoes de escrita."""
    try:
        container = build_container(config)
    except BrilliantChessError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=EXIT_USAGE_ERROR) from exc

    report = run_doctor(container)
    if output_format == "json":
        render_json(doctor_payload(report), console)
    else:
        render_doctor_human(report, console)
    raise typer.Exit(code=report.exit_code)


@app.command()
def serve(
    config: ConfigOption = _DEFAULT_CONFIG,
    host: Annotated[str | None, typer.Option("--host", help="Endereco de escuta.")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Porta de escuta.")] = None,
) -> None:
    """Sobe a interface web local: partida contra o motor e tabuleiro de analise."""
    try:
        container = build_container(config)
    except BrilliantChessError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=EXIT_USAGE_ERROR) from exc

    web = container.settings.web
    bind_host = host or web.host
    bind_port = port or web.port
    if bind_host not in _LOOPBACK_HOSTS:
        error_console.print(
            f"[yellow]Aviso: escutando em {bind_host}, fora do loopback. "
            "Este app e para estudo offline; exposto na rede ele pode ser usado "
            "para trapaca em partidas ao vivo.[/yellow]"
        )
    console.print(f"[green]Brilliant Chess em http://{bind_host}:{bind_port}[/green]")
    uvicorn.run(create_app(container), host=bind_host, port=bind_port, log_level="info")


@app.command("analyze-position")
def analyze_position(
    fen: Annotated[str, typer.Option("--fen", help="Posicao em FEN.")],
    rating: Annotated[int, typer.Option("--rating", help="Perfil aproximado por rating.")] = 1800,
) -> None:
    """Analisa uma posicao e classifica as candidatas (Entrega 5)."""
    _not_implemented("analyze-position", entrega=5, detail=f"fen={fen!r} rating={rating}")


@app.command("classify-move")
def classify_move(
    fen: Annotated[str, typer.Option("--fen", help="Posicao em FEN.")],
    move: Annotated[str, typer.Option("--move", help="Jogada em UCI ou SAN.")],
) -> None:
    """Classifica uma jogada especifica (Entrega 5)."""
    _not_implemented("classify-move", entrega=5, detail=f"fen={fen!r} move={move!r}")


@app.command("choose-move")
def choose_move(
    fen: Annotated[str, typer.Option("--fen", help="Posicao em FEN.")],
    rating: Annotated[int, typer.Option("--rating", help="Perfil aproximado por rating.")] = 1800,
) -> None:
    """Escolhe a jogada mais brilhante entre as objetivamente seguras (Entrega 6)."""
    _not_implemented("choose-move", entrega=6, detail=f"fen={fen!r} rating={rating}")


@app.command("analyze-pgn")
def analyze_pgn(
    pgn: Annotated[Path, typer.Argument(help="Arquivo PGN a analisar.")],
    output: Annotated[Path | None, typer.Option("--output", help="Relatorio JSON.")] = None,
) -> None:
    """Analisa uma partida completa offline (Entrega 7)."""
    _not_implemented("analyze-pgn", entrega=7, detail=f"pgn={pgn} output={output}")


@app.command()
def explain(
    analysis_id: Annotated[str, typer.Option("--analysis-id", help="Identificador da analise.")],
) -> None:
    """Mostra portoes, evidencias e limiares de uma analise salva (Entrega 7)."""
    _not_implemented("explain", entrega=7, detail=f"analysis_id={analysis_id!r}")


def _not_implemented(command: str, entrega: int, detail: str) -> None:
    error_console.print(
        f"[yellow]{command} ainda nao implementado (previsto para a Entrega {entrega}).[/yellow]\n"
        f"Argumentos recebidos: {detail}"
    )
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)
