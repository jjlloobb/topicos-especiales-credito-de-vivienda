# Comandos de U5 (reference-model). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Directorio de la entrega (ignorado por el control de versiones): datasets/, package/ y reference-policy.json.
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

# Genera los datos, entrena, ajusta la envolvente, calibra y empaqueta (Pasos 2 a 5). Falla si una regla de calidad no se cumple.
release:
	$(UV) python -m vectra_reference.release --out $(OUT)
