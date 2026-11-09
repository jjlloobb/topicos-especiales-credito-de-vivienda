# Comandos de U4 `governance`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test rules check

lint:
	$(UV) ruff check governance
	cd $(ROOT) && MYPYPATH=governance/src uv run mypy --strict governance/src
	$(UV) lint-imports --config governance/.importlinter

# Las pruebas de integracion levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest governance/tests -q

# Reglas de alerta con `promtool` (P-3: `CompensationEventPending`). Usa el del PATH o `platform/.tools/bin/promtool`; si ninguno
# existe (un worktree sin `make -C platform tools`), lo dice y lo omite: la prueba `test_observability.py` lee la regla y el CI
# corre `check-tools` de U1.
PROMTOOL := $(firstword $(shell command -v promtool) $(wildcard $(ROOT)/platform/.tools/bin/promtool))
rules:
	@if [ -z "$(PROMTOOL)" ]; then echo "promtool no disponible: se omite (lo corre el CI)"; else \
	  cd $(ROOT) && $(PROMTOOL) check rules governance/observability/*.yaml && $(PROMTOOL) test rules governance/observability/tests/*.yaml; fi

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint rules test
