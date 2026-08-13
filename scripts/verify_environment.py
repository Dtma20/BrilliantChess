"""Atalho para o diagnostico do ambiente sem instalar o pacote."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brilliant_chess.application.diagnose import run_doctor
from brilliant_chess.bootstrap.container import build_container


def main() -> int:
    container = build_container(Path("config/strict_v1.yaml"))
    report = run_doctor(container)
    for check in report.checks:
        print(f"{check.status.value.upper():>8}  {check.name:<28} {check.detail}")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
