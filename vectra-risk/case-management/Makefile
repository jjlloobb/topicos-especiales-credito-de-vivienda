# Comandos de U8 `case-management`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test check

lint:
	$(UV) ruff check case-management
	$(UV) ruff format --check case-management
	cd $(ROOT) && MYPYPATH=case-management/src:case-management/core_banking_mock/src uv run mypy --strict case-management/src case-management/core_banking_mock/src
	$(UV) lint-imports --config case-management/.importlinter

# Las pruebas de migraciones levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
# `case-management/pytest.ini` apunta la cobertura a `vectra_case` y no a la de U0 de la raiz.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests case-management/core_banking_mock/tests -q -p no:cacheprovider --rootdir=case-management

check: lint test
