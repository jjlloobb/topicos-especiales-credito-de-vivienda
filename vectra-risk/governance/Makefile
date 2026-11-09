# Comandos de U4 `governance`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test check

lint:
	$(UV) ruff check governance
	cd $(ROOT) && MYPYPATH=governance/src uv run mypy --strict governance/src
	$(UV) lint-imports --config governance/.importlinter

# Las pruebas de integracion levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest governance/tests -q

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test
