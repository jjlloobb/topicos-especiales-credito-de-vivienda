# Comandos de U9 (bias-monitoring). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint imports test coverage simulation check

lint:
	$(UV) ruff check bias-monitoring
	$(UV) ruff format --check bias-monitoring

imports:
	$(UV) lint-imports --config bias-monitoring/.importlinter

# Pasos 1 a 5: pruebas con el perfil `ci` (500 ejemplos, semilla impresa). La simulacion tiene su propio objetivo.
# Las pruebas de la libreria y la simulacion tienen sus propios objetivos (`coverage` y `simulation`): no se corren dos veces.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -q -p no:cacheprovider -m "not simulation" \
		--ignore=bias-monitoring/tests/unit/test_stats.py --ignore=bias-monitoring/tests/unit/test_disparity_examples.py \
		--ignore=bias-monitoring/tests/property --ignore=bias-monitoring/tests/simulation

# Paso 5 (NFR-U9-50): cobertura de ramas del 100 % en la libreria. `bias-monitoring/pytest.ini` apunta la cobertura a
# `vectra_disparity` y no a la de U0 de la raiz.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py -q -p no:cacheprovider --cov=vectra_disparity --cov-branch --cov-fail-under=100

# Paso 5 (NFR-U9-53): simulacion estadistica, 10 000 repeticiones. El workflow nocturno esta diferido (T4).
simulation:
	cd $(ROOT) && uv run pytest bias-monitoring/tests/simulation -m simulation -q -p no:cacheprovider -s

# `mutmut` en stats y disparity esta diferido por la demo (T3).
check: lint imports test coverage simulation
