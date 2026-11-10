# Imagen de `bias-monitoring` (U9): UNA imagen con los dos puntos de entrada (P-U9-05): el servicio (`python -m vectra_bias.app`, 8080/8081,
# el CMD) y el CronJob de congelacion (`python -m vectra_bias.run`, que fija su propio `command` en el chart).
# Contexto de construccion: la raiz de vectra-risk/ (`make -C bias-monitoring image`), porque lleva `vectra_contracts` y `vectra_common` de U0.
# La etapa final trae solo el runtime y sus dependencias del workspace: sin numpy, scipy, pandas, Fairlearn ni scikit-learn (solo sirven a las
# pruebas y a la simulacion), sin pytest ni hypothesis, y sin hatchling ni las fuentes (herramientas de build).
# Sin firma, SBOM ni escaneo (T1 de la demo) y sin push: el operador lo hace en la verificacion consolidada de U12 (bias-monitoring/docs/imagenes.md).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY bias-monitoring/disparity /src/bias-monitoring/disparity
COPY bias-monitoring/pyproject.toml /src/bias-monitoring/pyproject.toml
COPY bias-monitoring/src /src/bias-monitoring/src
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/bias-monitoring/disparity /src/bias-monitoring

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
# El servicio; el CronJob fija su propio `command` (`python -m vectra_bias.run`).
CMD ["python", "-m", "vectra_bias.app"]
