# Imagen de `case-management` (U8, Paso 19; P-U8-10): UNA imagen y tres ordenes que fija el chart (U08-T05): `python -m vectra_case.app` (case-service,
# 8080/8081; el CMD), `python -m vectra_case.worker` (case-worker, solo 8081) y `alembic -c /app/alembic.ini upgrade head` (el Job de migracion: por eso
# la imagen lleva `alembic.ini` y `migrations/` en /app). El plan nombra tambien `case-retention`: es la misma imagen, pero su CLI es del Paso 16 (diferido,
# T5) y no se anade ningun punto de entrada para ella.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C case-management image`), porque lleva `vectra_contracts` y `vectra_common` de U0.
# La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest ni hypothesis, sin ruff ni mypy, sin hatchling ni las fuentes
# (herramientas de build), sin `core_banking_mock` y sin libreria de circuit breaking (NFR-U8-34: el breaker es el de vectra_common.deps).
# Sin firma, SBOM ni escaneo (T1 de la demo) y sin push: el operador lo hace en la verificacion consolidada de U12 Paso 18 (case-management/docs/imagenes.md).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY case-management/pyproject.toml /src/case-management/pyproject.toml
COPY case-management/src /src/case-management/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/case-management

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Lo que necesita el Job de migracion: `alembic -c /app/alembic.ini upgrade head` (`script_location = %(here)s/migrations`).
COPY case-management/alembic.ini /app/alembic.ini
COPY case-management/migrations /app/migrations
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
# case-service; el chart fija su propio `command` para el worker y la migracion.
CMD ["python", "-m", "vectra_case.app"]
