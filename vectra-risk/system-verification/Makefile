# Comandos de U12 (system-verification). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
# Pasos 1 a 6, 12 y 13 (U12-T01 a U12-T04): lint, tipos, contratos de imports, pruebas y coberturas. Los pasos de imagen, workflow, README, enlaces y trazabilidad
# (Pasos 15 a 17) los agrega U12-T04: `traceability` falla hasta el Paso 17 y no hay Markdown en la unidad hasta entonces.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint types imports test shellcheck links check

lint:
	$(UV) ruff check system-verification
	$(UV) ruff format --check system-verification

# NFR-U12-40: mypy en modo estricto sobre `vectra_verification` (la configuracion `strict` esta en el `pyproject.toml` de la raiz).
types:
	$(UV) mypy system-verification/src/vectra_verification

imports:
	$(UV) lint-imports --config system-verification/.importlinter

# Pasos 1 a 6 (U12-T02): todas las pruebas (`unit`, `property` e `integration`: Keycloak y PostgreSQL de Testcontainers, `case-service` y el BFF reales en proceso) con el perfil `ci` (500 ejemplos, semilla impresa en
# la cabecera, sin `-q`) y la cobertura de ramas del paquete >= 85 % (NFR-U12-40; antes nadie la comprobaba: candidata de U12-T01); y en una segunda pasada, solo `unit` y `property`, la cobertura del 100 % en `report` y
# `sampler`. `mutmut` esta diferido por la demo (T3). Las pruebas con Docker necesitan Docker y Chromium: sin ellos **fallan**, no se omiten.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests -p no:cacheprovider --cov=vectra_verification --cov-branch --cov-fail-under=85 --cov-report=term-missing
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/unit system-verification/tests/property -p no:cacheprovider \
		--cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100 --cov-report=term-missing

# U12-T04 (Paso 12): los `verify` de las demos pasan por shellcheck (`shellcheck-py`; sin red si ya esta en la cache de `uv`) y los enlaces de los Markdown de la raiz (guiones, `cli.md`) se comprueban con la prueba de enlaces de U1.
shellcheck:
	cd $(ROOT) && uvx --from shellcheck-py shellcheck system-verification/demos/verify/*.sh

links:
	$(UV) python platform/tests/test_links.py

check: lint types imports test shellcheck links
