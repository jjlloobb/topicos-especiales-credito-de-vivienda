# Imagen del explainer de U6 (`vectra_explainer`): `python -m vectra_explainer` sirve `:explain` en 8080 y las sondas y metricas en 8081.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C model-serving image-explainer`), porque lleva `vectra_contracts` y
# `vectra_common` de U0. La etapa final trae solo el runtime: sin pytest ni hypothesis (dependencias de desarrollo del
# workspace), sin hatchling ni las fuentes (herramientas de build) y sin `shap` ni `scikit-learn` (NFR-U6-01; los cubre
# el contrato de import-linter y `pip list` de la imagen).
# `xgboost` se instala con `--no-deps`: su unica dependencia extra, `nvidia-nccl` (~300 MB, solo para entrenamiento
# distribuido en GPU), no se usa al servir; `numpy` y `scipy` van con las versiones de `uv.lock`.
# Sin firma, SBOM ni attestations (T1 de la demo) y sin push: el operador lo hace en el Paso 11 (AUTONOMIA-01).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY model-serving/pyproject.toml /src/model-serving/pyproject.toml
COPY model-serving/common/src /src/model-serving/common/src
COPY model-serving/predictor/src /src/model-serving/predictor/src
COPY model-serving/explainer/src /src/model-serving/explainer/src
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common numpy==2.5.4 scipy==1.18.1 \
 && pip install --no-cache-dir --no-deps --prefix=/install xgboost==3.4.1 /src/model-serving
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); `readOnlyRootFilesystem`: la imagen no escribe en disco.
USER 65532:65532
EXPOSE 8080 8081
CMD ["python", "-m", "vectra_explainer"]
