# Comandos de U7 `scoring-explainability`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
SRC := scoring-explainability/scoring/src:scoring-explainability/explainability/src

.PHONY: lint test check

lint:
	$(UV) ruff check scoring-explainability
	$(UV) ruff format --check scoring-explainability
	cd $(ROOT) && MYPYPATH=$(SRC) uv run mypy --strict scoring-explainability/scoring/src scoring-explainability/explainability/src
	$(UV) lint-imports --config scoring-explainability/.importlinter

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib

# Verificaciones estaticas y pruebas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test
