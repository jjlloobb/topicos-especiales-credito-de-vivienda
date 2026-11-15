# Comandos de U12 (system-verification). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
# Pasos 1 a 6, 12 y 13 (U12-T01 a U12-T04): lint, tipos, contratos de imports, pruebas y coberturas; shellcheck y enlaces (U12-T04). U12-T05 (Pasos 15 y 17): `image`, `test-image` y `traceability`.
# `check` construye la imagen **antes** de probarla; `check-fast` es el ciclo corto, sin imagen. Docker es compartido con kind: la imagen se etiqueta y no se publica (lo hace el operador, U12-T06).
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
IMAGE := localhost:5001/vectra/system-verification:dev

.PHONY: lint types imports test shellcheck links image test-image traceability check check-fast

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
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests --ignore=system-verification/tests/image -p no:cacheprovider --cov=vectra_verification --cov-branch --cov-fail-under=85 --cov-report=term-missing
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/unit system-verification/tests/property -p no:cacheprovider \
		--cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100 --cov-report=term-missing

# U12-T04 (Paso 12): los `verify` de las demos pasan por shellcheck (`shellcheck-py`; sin red si ya esta en la cache de `uv`) y los enlaces de los Markdown de la raiz (guiones, `cli.md`) se comprueban con la prueba de enlaces de U1.
# U12-T06: `shellcheck` y `links` alcanzan tambien `docs/` (los guiones de lectura de `docs/kind/` y la guia `docs/paso-18-kind.md`; `test_links.py` recorre todos los Markdown de `vectra-risk/`).
shellcheck:
	cd $(ROOT) && uvx --from shellcheck-py shellcheck system-verification/demos/verify/*.sh system-verification/docs/kind/*.sh

links:
	$(UV) python platform/tests/test_links.py

# Paso 15: la imagen (contexto: la raiz de vectra-risk/). Sin escaneo, SBOM ni firma (T1) y sin push. La etiqueta `source-digest` deja a la prueba rechazar una imagen anterior a las fuentes.
image:
	cd $(ROOT) && docker build -f system-verification/Dockerfile --build-arg SOURCE_DIGEST="$$(python3 system-verification/image/source_digest.py)" -t $(IMAGE) .

# Paso 15 (CA-2 a CA-5): la imagen real, con Docker. Fuera de `make test` (`--ignore`): sin Docker **falla**, no se omite.
test-image:
	cd $(ROOT) && uv run pytest system-verification/tests/image -p no:cacheprovider --no-cov -v

# Paso 17: la trazabilidad de la unidad con la lista «Diferido por la demo» (`DECISIONES-LOOP.md` §6).
traceability:
	$(UV) python platform/tests/test_traceability.py --unit system-verification --all

check: lint types imports test shellcheck image test-image links traceability

check-fast: lint types imports test shellcheck links traceability
