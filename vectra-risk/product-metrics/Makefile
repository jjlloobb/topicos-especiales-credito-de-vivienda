# Comandos de U11 (product-metrics). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint types imports test coverage check

lint:
	$(UV) ruff check product-metrics
	$(UV) ruff format --check product-metrics

# NFR-U11-30: mypy en modo estricto sobre `vectra_product` (la configuracion `strict` esta en el `pyproject.toml` de la raiz).
types:
	$(UV) mypy product-metrics/src/vectra_product

imports:
	$(UV) lint-imports --config product-metrics/.importlinter

# Pasos 1 a 7: todas las pruebas con el perfil `ci` (500 ejemplos, semilla impresa en la cabecera, sin `-q`). No corre `-m volume` (Paso 7).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests -p no:cacheprovider -m "not volume"

# Paso 5 (NFR-U11-30): cobertura de ramas del 100 % en `compute` y `noise`. `mutmut` esta diferido por la demo (T3).
# Paso 8 (NFR-U11-30): cobertura de ramas >= 90 % en el resto (`vectra_product` entero); corre todas las pruebas, tambien las del
# proceso real, con el perfil por omision (la de `ci` ya la corre `test`). No corre `-m volume` (diferida, T3).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/unit product-metrics/tests/property -p no:cacheprovider \
		--cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100
	cd $(ROOT) && uv run pytest product-metrics/tests -p no:cacheprovider -m "not volume" \
		--cov=vectra_product --cov-branch --cov-fail-under=90 --cov-report=term-missing

check: lint types imports test coverage
