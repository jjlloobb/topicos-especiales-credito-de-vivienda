# Comandos de U5 (reference-model). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Directorio de la entrega (ignorado por el control de versiones): datasets/, package/ y reference-policy.json.
OUT ?= $(ROOT)/reference-model/.out

.PHONY: lint imports test check release release-base verify-release runbooks traceability not-applicable

lint:
	$(UV) ruff check reference-model
	$(UV) ruff format --check reference-model

imports:
	$(UV) lint-imports --config reference-model/.importlinter

# Pasos 2 a 7 y 10: cobertura de ramas >= 90 % en vectra_reference y 100 % en envelope/confidence.py (NFR-U5-33).
# `reference-model/pytest.ini` apunta la cobertura a vectra_reference y no a la de U0 de la raiz.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests -q -p no:cacheprovider --rootdir=reference-model --import-mode=importlib --cov --cov-branch --cov-fail-under=90
	$(UV) coverage report --include="*/vectra_reference/envelope/confidence.py" --fail-under=100

# Paso 9: el procedimiento sigue la plantilla y cada paso de verificacion nombra un comando.
runbooks:
	$(UV) python platform/tests/test_runbooks.py --operational --root reference-model/docs

# Paso 10: cada identificador de diseno de U5 tiene codigo que lo implementa.
traceability:
	$(UV) python platform/tests/test_traceability.py --unit reference-model --all

# Paso 11: U5 no tiene runtime, base de datos, API ni interfaz.
not-applicable:
	test ! -d $(ROOT)/reference-model/chart && test ! -d $(ROOT)/reference-model/migrations

# Pasos 1 a 11 en orden; el Paso 8 (workflow y release firmada) esta diferido por la demo.
check: lint imports test runbooks traceability not-applicable

# Paso 9: verifica cada SHA-256 de los manifiestos de `make release` (package y los 5 de proxy). Lo corre el operador
# antes de subir; ver docs/release.md.
verify-release:
	python3 $(ROOT)/reference-model/scripts/verify_release.py --out $(OUT)

# Genera los datos, entrena, ajusta la envolvente, calibra y empaqueta (Pasos 2 a 5), y ademas la variante proxy de RT-2
# (5 paquetes en proxy/run-N, Paso 6) y el conjunto adversarial (adversarial/manifest.json, Paso 7).
# Falla si una regla de calidad no se cumple (AUC, disparidad, calibracion, paridad del explicador, paquete).
release:
	$(UV) python -m vectra_reference.release --out $(OUT)

# Solo el modelo base (Pasos 2 a 5): lo que tarda menos cuando no se necesita RT-2 ni RT-1/RT-3/RT-4.
release-base:
	$(UV) python -m vectra_reference.release --out $(OUT) --only base
