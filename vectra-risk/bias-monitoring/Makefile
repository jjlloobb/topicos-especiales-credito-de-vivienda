# Comandos de U9 (bias-monitoring). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint imports test property coverage simulation check

lint:
	$(UV) ruff check bias-monitoring
	$(UV) ruff format --check bias-monitoring

imports:
	$(UV) lint-imports --config bias-monitoring/.importlinter

# Pasos 1 a 8: pruebas con el perfil `ci` (500 ejemplos, semilla impresa). La simulacion tiene su propio objetivo.
# Las pruebas de la libreria y la simulacion tienen sus propios objetivos (`coverage` y `simulation`): no se corren dos veces.
# Las propiedades del Bloque C (`tests/property` salvo las de la libreria) corren en el objetivo `property`.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -q -p no:cacheprovider -m "not simulation" \
		--ignore=bias-monitoring/tests/unit/test_stats.py --ignore=bias-monitoring/tests/unit/test_disparity_examples.py \
		--ignore=bias-monitoring/tests/property --ignore=bias-monitoring/tests/simulation

# Pasos 6 a 8: PBT-U9-03 (publish), 04, 05 y 08 con el perfil `ci` y la semilla impresa. `test_run_machine.py` fija sus propios
# ejemplos (30 secuencias de hasta 60 pasos, ~40 corridas cada una): una corrida completa contra los dobles cuesta ~0,15 s.
property:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_freeze_rule.py \
		bias-monitoring/tests/property/test_context.py bias-monitoring/tests/property/test_publish.py \
		bias-monitoring/tests/property/test_run_machine.py -q -p no:cacheprovider

# Paso 5 (NFR-U9-50): cobertura de ramas del 100 % en la libreria. `bias-monitoring/pytest.ini` apunta la cobertura a
# `vectra_disparity` y no a la de U0 de la raiz.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py -q -p no:cacheprovider --cov=vectra_disparity --cov-branch --cov-fail-under=100

# Paso 5 (NFR-U9-53): simulacion estadistica, 10 000 repeticiones. El workflow nocturno esta diferido (T4).
simulation:
	cd $(ROOT) && uv run pytest bias-monitoring/tests/simulation -m simulation -q -p no:cacheprovider -s

# `mutmut` en stats y disparity esta diferido por la demo (T3).
check: lint imports test property coverage simulation
