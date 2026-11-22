# Servidor MCP de solo lectura del loop. Se ejecuta desde cualquier sitio; corre en la raiz del workspace `vectra-risk/`. Ninguna orden toca un cluster.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
UV := cd $(ROOT) && uv run

.PHONY: lint types test check

lint:
	$(UV) ruff check loop/mcp-solo-lectura
	$(UV) ruff format --check loop/mcp-solo-lectura

types:
	$(UV) mypy loop/mcp-solo-lectura/src/vectra_mcp_readonly

# Sin cluster: `kubectl` es un doble. Incluye la prueba que compara las herramientas registradas con `.mcp.json`, `.claude/settings.json` y los agentes.
# La misma orden que la CI (`.github/workflows/tests.yml`, con `path: loop/mcp-solo-lectura`), mas la cobertura.
test:
	cd $(ROOT) && uv run pytest loop/mcp-solo-lectura --rootdir=loop/mcp-solo-lectura --import-mode=importlib -p no:cacheprovider \
		--cov=vectra_mcp_readonly --cov-branch --cov-fail-under=90 --cov-report=term-missing

check: lint types test
