# Comandos de U5 (reference-model). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Directorio de la entrega; el Paso 5 (empaquetado) lo ampliara.
OUT ?= $(ROOT)/reference-model/.out

.PHONY: lint imports test check release

lint:
	$(UV) ruff check reference-model
	$(UV) ruff format --check reference-model

imports:
	$(UV) lint-imports --config reference-model/.importlinter

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests -q -p no:cacheprovider --rootdir=reference-model --import-mode=importlib

check: lint imports test

# En U05-T01 solo genera los datos (Paso 2). El empaquetado llega en el Paso 5.
release:
	$(UV) python -m vectra_reference.generate --out $(OUT)/datasets
