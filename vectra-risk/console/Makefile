# Comandos de U10 `console` (`console-bff` y `console-spa`). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
NPM := cd $(ROOT) && npm run -w console/spa

.PHONY: lint-bff lint-spa lint test-bff test-spa test check

lint-bff:
	$(UV) ruff check console
	$(UV) ruff format --check console
	cd $(ROOT) && MYPYPATH=console/bff/src uv run mypy --strict console/bff/src console/bff/tools
	$(UV) lint-imports --config console/bff/.importlinter

# `npm ci` ya lo dejo hecho el `contracts check` o el desarrollador; aqui solo se invocan los scripts del workspace.
lint-spa:
	$(NPM) lint
	$(NPM) typecheck

lint: lint-bff lint-spa

# CA-7 (U10-T01): cobertura de ramas del 100 % en `object_rules` y `errors` (NFR-U10-60); `mutmut` diferido por la demo (T3).
# CA-7 (U10-T02): ademas, >= 90 % en todo `console_bff` con **toda** la suite (unit, property, integration y doubles).
COV_PURE := --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100
COV_ALL := --cov=console_bff --cov-branch --cov-fail-under=90
# `console/bff/pytest.ini` apunta la cobertura a `console_bff` y no a la de U0 de la raiz. Las corridas son en serie (maquina compartida).
test-bff:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests -q -p no:cacheprovider --rootdir=console/bff $(COV_ALL)
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/unit console/bff/tests/property -q -p no:cacheprovider --rootdir=console/bff $(COV_PURE)
	cd $(ROOT) && uv run python console/bff/tools/role_matrix.py --check

test-spa:
	$(NPM) test

test: test-bff test-spa

check: lint test
