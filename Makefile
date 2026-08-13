# Brilliant Chess - atalhos locais.
#
# `make` sozinho mostra a ajuda. `make run` constroi a interface e sobe o
# servidor: e o comando para rodar o projeto inteiro de uma vez.
#
# Tudo escuta em loopback. Nenhum alvo aqui abre porta para a rede.

FRONTEND := frontend
HOST ?= 127.0.0.1
PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help install build run dev api web test test-py test-web check lint types clean doctor

help:
	@echo "Brilliant Chess"
	@echo ""
	@echo "  make install   instala dependencias do Python e do front"
	@echo "  make run       constroi a interface e sobe o servidor local"
	@echo "  make dev       Vite em 5173 e API em 8000, lado a lado"
	@echo "  make build     so constroi a interface"
	@echo "  make api       so sobe a API, sem construir o front"
	@echo "  make test      pytest e vitest"
	@echo "  make check     lint, tipos e testes dos dois lados"
	@echo "  make doctor    verifica a instalacao do Stockfish"
	@echo "  make clean     remove build da interface e caches"
	@echo ""
	@echo "  HOST e PORT sobrescrevem o endereco: make run PORT=8080"

install:
	uv sync
	npm --prefix $(FRONTEND) install

# Projeto inteiro em um comando: build da interface + servidor.
run: build api

build:
	npm --prefix $(FRONTEND) run build

api:
	uv run brilliant-chess serve --host $(HOST) --port $(PORT)

web:
	npm --prefix $(FRONTEND) run dev

# Os dois processos em paralelo, sem depender de sintaxe de shell.
# Ctrl-C derruba ambos. A interface fica em http://127.0.0.1:5173.
dev:
	$(MAKE) -j2 web api

test: test-py test-web

test-py:
	uv run pytest

test-web:
	npm --prefix $(FRONTEND) test

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy src
	npm --prefix $(FRONTEND) run typecheck

check: lint types test

doctor:
	uv run brilliant-chess doctor

clean:
	uv run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['frontend/dist', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov']]"
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('src').rglob('__pycache__')]"
