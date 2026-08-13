"""Ajuda a instalar o Stockfish sem baixar nada por conta propria.

Por padrao o script apenas explica o que fazer. O download so acontece com
``--url``, ``--sha256`` e ``--yes`` informados explicitamente pela pessoa que
executa, porque baixar e executar binarios exige decisao humana consciente.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

INSTRUCTIONS = """
Stockfish nao e baixado automaticamente por este projeto.

Opcoes:
  1. Baixe em https://stockfishchess.org/download/ e aponte o caminho com
     a variavel de ambiente BRILLIANT_CHESS_STOCKFISH ou com engine.binary_path
     em config/strict_v1.yaml.
  2. Instale por gerenciador de pacotes (winget, scoop, brew, apt).
  3. Rode este script com --url, --sha256 e --yes se preferir automatizar,
     conferindo antes o hash publicado pelo projeto Stockfish.

Depois execute: brilliant-chess doctor
"""

_CHUNK = 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Instalacao assistida do Stockfish")
    parser.add_argument("--url", help="URL do binario oficial.")
    parser.add_argument("--sha256", help="SHA-256 esperado do arquivo baixado.")
    parser.add_argument("--dest", default="engines", help="Diretorio de destino.")
    parser.add_argument("--yes", action="store_true", help="Confirma o download.")
    args = parser.parse_args(argv)

    if not (args.url and args.sha256 and args.yes):
        print(INSTRUCTIONS.strip())
        return 0

    destination = Path(args.dest)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / Path(args.url).name
    print(f"Baixando {args.url} -> {target}")
    with urllib.request.urlopen(args.url) as response, target.open("wb") as handle:
        while chunk := response.read(_CHUNK):
            handle.write(chunk)

    digest = hashlib.sha256()
    with target.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != args.sha256.lower():
        target.unlink(missing_ok=True)
        print(f"SHA-256 divergente. Esperado {args.sha256}, obtido {actual}. Arquivo removido.")
        return 1

    print(f"Arquivo verificado: {target}")
    print("Aponte BRILLIANT_CHESS_STOCKFISH para o executavel e rode: brilliant-chess doctor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
