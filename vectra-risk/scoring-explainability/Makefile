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

# Cobertura de ramas de la logica pura (NFR-U7-40) con las PBT-U7-01..06 en el perfil `ci`, 500 ejemplos (NFR-U7-42): 100 % en `policy`, `narrative` y `factuality`. Los modulos viven en los paquetes
# `scoring` y `explainability`, asi que se miden los paquetes y el 100 % se fija por modulo. Corre las mismas pruebas que `test`.
# `mutmut` sobre `policy` y `factuality` (NFR-U7-41) se difiere (T3, enmienda §2.3).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/unit scoring-explainability/tests/property -q -p no:cacheprovider --import-mode=importlib --cov=scoring --cov=explainability --cov-branch
	cd $(ROOT) && uv run coverage report --include="*/scoring/policy.py,*/explainability/narrative.py,*/explainability/factuality.py" --fail-under=100
	test -s $(ROOT)/aidlc-docs/construction/scoring-explainability/code/logic.md

# Verificaciones estaticas y pruebas (AUTONOMIA-01). `coverage` corre las pruebas de `test` con la medicion. Crece con los pasos del plan.
check: lint coverage
