# Imagen de `decision-registry` (U3): el servicio (8080/8081), la CLI `vectra-registry` (CronJob del agregador) y las migraciones
# de Alembic (Job de migracion, F44). Una sola imagen para los tres, como el chart: lo que cambia es el `command`.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C decision-registry image`), porque lleva `vectra_contracts` y
# `vectra_common` de U0. La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest, hypothesis ni
# testcontainers (dependencias de desarrollo del workspace) y sin hatchling ni las fuentes (herramientas de build).
# Sin firma, SBOM ni attestations (T1 de la demo) y sin push: el operador lo hace en el Bloque H (AUTONOMIA-01).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY decision-registry/pyproject.toml /src/decision-registry/pyproject.toml
COPY decision-registry/src /src/decision-registry/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/decision-registry

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# `alembic upgrade head` del Job de migracion: `alembic.ini` + `migrations/` (script_location = %(here)s/migrations).
COPY decision-registry/alembic.ini /app/alembic.ini
COPY decision-registry/migrations /app/migrations
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
# El servicio; los CronJobs y el Job de migracion fijan su propio `command`.
CMD ["python", "-m", "vectra_registry.service"]
