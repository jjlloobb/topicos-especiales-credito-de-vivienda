# Imagen del `model-validation-job` de U4 (Paso 13): AUC, disparidad inicial y sincronia predictor/explicador. Lleva las librerias de
# inferencia (onnxruntime, xgboost, lightgbm) que el servicio NO lleva (NFR-U4-24): por eso es otra imagen que la del servicio.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C governance image-validation`), porque lleva `vectra_contracts`,
# `vectra_common` (U0) y `vectra_disparity` (U9, la libreria real). Las versiones de las dependencias salen del extra `validation` de
# `governance/pyproject.toml` (==). La etapa final trae solo el runtime: sin pytest, hatchling ni fuentes de build.
# Sin firma, SBOM ni attestations (T1 de la demo) y sin push: el operador lo hace en U04-T07 (AUTONOMIA-01). El digest de la imagen
# resultante lo fija el operador en los values.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY bias-monitoring/disparity /src/vectra_disparity
COPY governance/pyproject.toml /src/governance/pyproject.toml
COPY governance/src /src/governance/src
COPY governance/validation_job/vectra_validation /src/governance/validation_job/vectra_validation
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/vectra_disparity "/src/governance[validation]"

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# `libgomp1` (OpenMP) lo cargan lightgbm y xgboost; la base `slim` no la trae. Version fijada (DL3008): la de Debian 13 de la base por digest;
# al cambiar el digest de la base hay que releerla (`apt-cache policy libgomp1`).
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1=14.2.0-19 && rm -rf /var/lib/apt/lists/*
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root): el mismo `runAsNonRoot` de la plantilla del Job (`k8s_jobs.py`).
USER 65532:65532
ENTRYPOINT ["python", "-m", "vectra_validation"]
