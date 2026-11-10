# Comandos de U7 `scoring-explainability`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
SRC := scoring-explainability/scoring/src:scoring-explainability/explainability/src

.PHONY: lint test coverage check

# Contratos de import-linter (`.importlinter`): BR-U7-11 (factuality no importa narrative), P-U0-07 y NFR-U7-43 (sin httpx directo
# ni librerias de circuit breaking: el breaker es el de vectra_common.deps), NFR-U7-32 (sin clientes de LLM; narrativa de plantilla).
# NFR-U7-30 y P-U7-07 (sin salida al core ni a internet desde U7) los cubre tests/unit/test_no_core_client.py.
lint:
	$(UV) ruff check scoring-explainability
	$(UV) ruff format --check scoring-explainability
	cd $(ROOT) && MYPYPATH=$(SRC) uv run mypy --strict scoring-explainability/scoring/src scoring-explainability/explainability/src
	$(UV) lint-imports --config scoring-explainability/.importlinter

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib

# Cobertura de ramas (NFR-U7-40, 42): toda la suite (logica pura, ejemplos, integracion con dobles, PBT-U7-01..08 en el perfil `ci`, 500
# ejemplos) con >= 95 % en los dos servicios; despues el 100 % por modulo: `policy`, `narrative` y `factuality` (logica pura, Paso 7)
# y `orchestrator` (Paso 13). `--cov` sin argumento mediria el `source` de la raiz (U0), por eso se nombran los paquetes.
# `mutmut` sobre `policy` y `factuality` (NFR-U7-41) se difiere (T3, enmienda §2.3).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib --cov=scoring --cov=explainability --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/scoring/*" --fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/explainability/*" --fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/scoring/policy.py,*/explainability/narrative.py,*/explainability/factuality.py" --fail-under=100
	cd $(ROOT) && uv run coverage report --include="*/scoring/orchestrator.py" --fail-under=100
	test -s $(ROOT)/aidlc-docs/construction/scoring-explainability/code/logic.md
	test -s $(ROOT)/aidlc-docs/construction/scoring-explainability/code/services.md

# Verificaciones estaticas y pruebas (AUTONOMIA-01). `coverage` corre las pruebas de `test` con la medicion. Crece con los pasos del plan.
check: lint coverage
