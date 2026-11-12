# Imagen de `explainability-service` (U7, Paso 14): el servicio (8080/8081), que arranca con `vectra_common.ops_server.run_service(app)`
# desde `explainability.app.main`. Contexto de construccion: la raiz de vectra-risk/ (`make -C scoring-explainability image-explainability`).
# Las plantillas versionadas (`template_v1.txt`, `applicant_v1.txt`) van dentro de la imagen: la rueda las lleva en `explainability/templates`
# (`force-include` del pyproject). La etapa final trae solo el runtime y sus dependencias del workspace: sin pytest ni hypothesis, sin cliente
# de LLM (la narrativa es de plantilla, NFR-U7-32) ni libreria de circuit breaking, y sin hatchling ni las fuentes.
# Sin firma, SBOM ni escaneo (T1) y sin push: el operador lo hace en U12 Paso 18 (scoring-explainability/docs/imagenes.md).
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
WORKDIR /src
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
COPY scoring-explainability/explainability/pyproject.toml /src/explainability/pyproject.toml
COPY scoring-explainability/explainability/src /src/explainability/src
COPY scoring-explainability/explainability/templates /src/explainability/templates
# Las versiones de las dependencias estan fijadas en cada pyproject (==); `--prefix` deja el runtime aparte de las herramientas.
RUN pip install --no-cache-dir --prefix=/install /src/vectra_contracts /src/vectra_common /src/explainability

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart.
USER 65532:65532
EXPOSE 8080 8081
# `explainability.app` no tiene guarda `__main__`: se llama a `main()`, que lee las variables de `REQUIRED_ENV` y llama a `run_service`.
CMD ["python", "-c", "from explainability.app import main; main()"]
