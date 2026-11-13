# Imagen de `core-banking-mock` (U8, Paso 19; INF-U8-02): el core simulado de solo lectura (kind y staging), con su fixture en
# /app/fixtures/credits.json (la ruta de `core_banking_mock.app.DEFAULT_FIXTURES`; sin ConfigMap ni volumen). Arranca con
# `python -m core_banking_mock.app` (8080/8081). La imagen NO lleva `vectra_case` (el mock no depende de case-service).
# Contexto de construccion: la raiz de vectra-risk/ (`make -C case-management image-mock`). Sin firma, SBOM ni escaneo (T1) y sin push (U12 Paso 18).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY case-management/core_banking_mock/pyproject.toml /src/core_banking_mock/pyproject.toml
COPY case-management/core_banking_mock/src /src/core_banking_mock/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/core_banking_mock

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
COPY case-management/core_banking_mock/fixtures/credits.json /app/fixtures/credits.json
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
CMD ["python", "-m", "core_banking_mock.app"]
