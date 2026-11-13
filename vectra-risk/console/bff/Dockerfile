# Imagen de `console-bff` (U10, Paso 17; INF-U10-01): un solo proceso (`python -m console_bff.app`) que sirve 8080 (la API de la SPA) y 8081 (`/metrics`, `/healthz`, `/readyz`).
# Contexto de construccion: la raiz de vectra-risk/ (`make -C console image-bff`), porque lleva `vectra_contracts` y `vectra_common` de U0.
# La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest, hypothesis, ruff, mypy ni hatchling, sin `tests/` y sin las fuentes (herramientas de build).
# Sin firma, SBOM ni escaneo (T1 de la demo) y sin push: el operador lo hace en la verificacion consolidada de U12 (console/README.md, seccion «Imagenes»).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY console/bff/pyproject.toml /src/console-bff/pyproject.toml
COPY console/bff/src /src/console-bff/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/console-bff

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
CMD ["python", "-m", "console_bff.app"]
