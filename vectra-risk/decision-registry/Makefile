# Comandos de U3 `decision-registry`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test check

lint:
	$(UV) ruff check decision-registry
	cd $(ROOT) && MYPYPATH=decision-registry/src uv run mypy --strict decision-registry/src
	$(UV) lint-imports --config decision-registry/.importlinter

# Las pruebas de integracion levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests -q

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test
