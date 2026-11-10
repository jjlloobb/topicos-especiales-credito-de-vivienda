# Comandos de U9 (bias-monitoring). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint imports test property coverage coverage-bias simulation check

lint:
	$(UV) ruff check bias-monitoring
	$(UV) ruff format --check bias-monitoring

imports:
	$(UV) lint-imports --config bias-monitoring/.importlinter

# Pasos 1 a 8: pruebas con el perfil `ci` (500 ejemplos, semilla impresa). La simulacion tiene su propio objetivo.
# Las pruebas de la libreria y la simulacion tienen sus propios objetivos (`coverage` y `simulation`): no se corren dos veces.
# Las propiedades del Bloque C (`tests/property` salvo las de la libreria) corren en el objetivo `property`.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -p no:cacheprovider -m "not simulation" \
		--ignore=bias-monitoring/tests/unit/test_stats.py --ignore=bias-monitoring/tests/unit/test_disparity_examples.py \
		--ignore=bias-monitoring/tests/property --ignore=bias-monitoring/tests/simulation

# Pasos 6 a 9: PBT-U9-03 (publish), 04, 05, 07 (compare) y 08 con el perfil `ci` y la semilla impresa (sin `-q`, que oculta la cabecera con la semilla). `test_run_machine.py` fija sus
# propios ejemplos (NFR-U9-52): PBT-U9-05 va con 120 secuencias de hasta 80 pasos, no 500 x 80 (una corrida completa contra los dobles
# cuesta ~0,15 s y 500 x 80 pasaba de 6 min); conserva todos los comandos e invariantes. La decision esta en `code/services.md`.
property:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_freeze_rule.py \
		bias-monitoring/tests/property/test_context.py bias-monitoring/tests/property/test_publish.py \
		bias-monitoring/tests/property/test_run_machine.py bias-monitoring/tests/property/test_compare.py -p no:cacheprovider

# Paso 5 (NFR-U9-50): cobertura de ramas del 100 % en la libreria. `bias-monitoring/pytest.ini` apunta la cobertura a
# `vectra_disparity` y no a la de U0 de la raiz.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py -q -p no:cacheprovider --cov=vectra_disparity --cov-branch --cov-fail-under=100

# Paso 10 (NFR-U9-50): cobertura de ramas de `vectra_bias` (CronJob y servicio): >= 95 % en el conjunto y 100 % en `freeze_rule`, `context` y
# `window`. `--cov=vectra_bias` reemplaza el `source` de `coveragerc` (que mide solo la libreria). Mide **todas** las pruebas de
# `bias-monitoring/tests` salvo la simulacion (que tiene su objetivo): repite las de `test` y `property`, porque la cobertura de ramas se
# mide sobre una sola corrida; es el costo de un numero real y no de la suma de dos.
coverage-bias:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -p no:cacheprovider -m "not simulation" \
		--cov=vectra_bias --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include='*/freeze_rule.py,*/context.py,*/window.py' --fail-under=100

# Paso 5 (NFR-U9-53): simulacion estadistica, 10 000 repeticiones. El workflow nocturno esta diferido (T4).
simulation:
	cd $(ROOT) && uv run pytest bias-monitoring/tests/simulation -m simulation -q -p no:cacheprovider -s

# `mutmut` en stats y disparity esta diferido por la demo (T3).
check: lint imports test property coverage coverage-bias simulation
