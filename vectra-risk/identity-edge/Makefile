# Comandos de U2. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test check

lint:
	$(UV) ruff check identity-edge

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test
