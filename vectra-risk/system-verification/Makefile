# Comandos de U12 (system-verification). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
# Pasos 1 a 4 (U12-T01): lint, tipos, contratos de imports, pruebas y cobertura de la logica pura. Los pasos de imagen, workflow, README, enlaces y trazabilidad
# (Pasos 15 a 17) los agrega U12-T04: `traceability` falla hasta el Paso 17 y no hay Markdown en la unidad hasta entonces.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint types imports test check

lint:
	$(UV) ruff check system-verification
	$(UV) ruff format --check system-verification

# NFR-U12-40: mypy en modo estricto sobre `vectra_verification` (la configuracion `strict` esta en el `pyproject.toml` de la raiz).
types:
	$(UV) mypy system-verification/src/vectra_verification

imports:
	$(UV) lint-imports --config system-verification/.importlinter

# Pasos 1 a 4: las pruebas de `tests/unit` y `tests/property` con el perfil `ci` (500 ejemplos, semilla impresa en la cabecera, sin `-q`), y en la misma corrida la
# cobertura de ramas del 100 % en `report` y `sampler` (NFR-U12-40). `mutmut` esta diferido por la demo (T3). El >= 85 % del resto del paquete es del Paso 16 (U12-T04).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/unit system-verification/tests/property -p no:cacheprovider \
		--cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100 --cov-report=term-missing

check: lint types imports test
