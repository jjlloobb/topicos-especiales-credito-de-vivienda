# Imagen de `scoring-service` (U7, Paso 14): el servicio (8080/8081), que arranca con `vectra_common.ops_server.run_service(app)` desde
# `scoring.app.main`. Contexto de construccion: la raiz de vectra-risk/ (`make -C scoring-explainability image-scoring`), porque lleva
# `vectra_contracts` y `vectra_common` de U0. La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest ni hypothesis
# (dependencias de desarrollo del workspace), sin cliente de LLM ni libreria de circuit breaking (NFR-U7-32, NFR-U7-43) y sin hatchling ni
# las fuentes (herramientas de build). Sin firma, SBOM ni escaneo (T1 de la demo) y sin push: el operador lo hace en la verificacion
# consolidada de U12 Paso 18 (scoring-explainability/docs/imagenes.md).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY scoring-explainability/scoring/pyproject.toml /src/scoring/pyproject.toml
COPY scoring-explainability/scoring/src /src/scoring/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/scoring

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
CMD ["python", "-m", "scoring.app"]
