# Comandos de U6 `model-serving`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
SRC := model-serving/common/src:model-serving/predictor/src:model-serving/explainer/src
REGISTRY ?= localhost:5001
TAG ?= dev

.PHONY: lint test check image-predictor image-explainer

lint:
	$(UV) ruff check model-serving
	$(UV) ruff format --check model-serving
	cd $(ROOT) && MYPYPATH=$(SRC) uv run mypy --strict model-serving/common/src model-serving/predictor/src model-serving/explainer/src
	$(UV) lint-imports --config model-serving/.importlinter

# Los artefactos RT-3 y el modelo base salen de la entrega real de U5 (una vez por sesion, ~1 min).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests -q -p no:cacheprovider

# Las imagenes se construyen en local con el contexto en `vectra-risk/`; el push y el digest real son del Paso 11 (operador).
image-predictor:
	docker build -f $(ROOT)/model-serving/predictor/Dockerfile -t $(REGISTRY)/vectra/model-predictor:$(TAG) $(ROOT)

image-explainer:
	docker build -f $(ROOT)/model-serving/explainer/Dockerfile -t $(REGISTRY)/vectra/model-explainer:$(TAG) $(ROOT)

# Verificaciones estaticas y pruebas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test
