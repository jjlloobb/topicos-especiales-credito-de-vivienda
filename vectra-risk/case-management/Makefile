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
# Paso 18 (U08-T04, NFR-U8-50): ramas >= 95 % en `vectra_case` y 100 % en los ocho modulos que entran (`retention` sin umbral: diferido por la
# demo; `mutmut` diferido, T3). `case-management/pytest.ini` apunta la cobertura a `vectra_case` y no a la de U0.
COV_100 := --include='*/vectra_case/case_fsm.py,*/vectra_case/backoff.py,*/vectra_case/decision.py,*/vectra_case/views.py,*/vectra_case/intake.py,*/vectra_case/evidence.py,*/vectra_case/evaluation.py,*/vectra_case/sweeps.py'
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests case-management/core_banking_mock/tests -q -p no:cacheprovider --rootdir=case-management --cov=vectra_case --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --rcfile=case-management/coveragerc --fail-under=100 $(COV_100)

check: lint test
