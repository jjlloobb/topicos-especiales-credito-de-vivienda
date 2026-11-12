# Imagen de `product-metrics` (U11, Paso 10): un solo proceso (`python -m vectra_product.main`) que sirve 8081 (`/metrics`, `/healthz`, `/readyz`); sin 8080 ni rutas de negocio.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C product-metrics image`), porque lleva `vectra_contracts` y `vectra_common` de U0.
# La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest, hypothesis, ruff, mypy ni hatchling, y sin las fuentes (herramientas de build).
# FastAPI llega solo como dependencia de `vectra_common` (el `import-linter` de la unidad prohibe que un modulo de `vectra_product` lo importe).
# Sin firma, SBOM ni escaneo (T1 de la demo) y sin push: el operador lo hace en la verificacion consolidada de U12 (product-metrics/docs/imagenes.md).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY product-metrics/pyproject.toml /src/product-metrics/pyproject.toml
COPY product-metrics/src /src/product-metrics/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/product-metrics

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8081
CMD ["python", "-m", "vectra_product.main"]
