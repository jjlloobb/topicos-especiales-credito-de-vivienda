# Imagen de `governance-service` de U4 (Paso 16, agregado por el usuario el 2026-11-09): el servicio (8080/8081) y las migraciones de
# Alembic (Job de migracion, F44). Una sola imagen para los dos, como `decision-registry`: lo que cambia es el `command` del chart.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C governance image`), porque lleva `vectra_contracts` y `vectra_common` de U0.
# Solo el runtime de `vectra-governance`: SIN ONNX Runtime, `xgboost` ni `lightgbm` (NFR-U4-24; son del extra `validation`, que
# lleva la otra imagen, `validation_job/Dockerfile`) y sin `vectra_validation` ni `vectra_promotion` (el hatch del pyproject empaqueta los
# directorios que existen). La etapa final no trae pytest, hypothesis ni testcontainers ni hatchling ni las fuentes de build.
# `tzdata` (America/Bogota, INF-U4-01, P-U4-05): la base `python:3.12-slim` por digest ya trae /usr/share/zoneinfo; CA-9 de U04-T06 lo
# comprueba con `zoneinfo.ZoneInfo("America/Bogota")`, de modo que un cambio de base que lo pierda se ve al construir.
# Sin firma, SBOM ni attestations (T1 de la demo) y sin push: el operador lo hace en U04-T07 (AUTONOMIA-01).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY governance/pyproject.toml /src/governance/pyproject.toml
COPY governance/src /src/governance/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/governance

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# `alembic upgrade head` del Job de migracion: `alembic.ini` + `migrations/` (script_location = %(here)s/migrations).
COPY governance/alembic.ini /app/alembic.ini
COPY governance/migrations /app/migrations
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
# El servicio; el Job de migracion fija su propio `command`. `vectra_governance.service` (U04-T08: `config_from_env`, `build_app` y `main`)
# lee del entorno la configuracion que le entrega el chart; `tests/integration/test_container_start.py` arranca esta imagen de verdad.
CMD ["python", "-m", "vectra_governance.service"]
