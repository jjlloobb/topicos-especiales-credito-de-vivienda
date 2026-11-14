# Imagen de `system-verification` (U12, Paso 15, INF-U12-01): la herramienta `vectra-verification`, sus guiones y `verify`, `kubectl` y el Chromium sin interfaz del login (Playwright 1.64.0, revision 1248).
# Corre en la estacion del operador, no en el cluster (`docker run`; ver README.md). Contexto de construccion: la raiz de vectra-risk/ (`make -C system-verification image`).
# Sin `vectra_common`, sin binario de Argo CD, sin `helm`, `k6`, `git` ni `curl`, sin manifiestos de Kubernetes. Sin escaneo, SBOM ni firma (T1 de la demo) y sin push: lo hace el operador (U12-T06).
# Descargas de la construccion (P-8, autorizadas por el usuario el 2026-11-13), cada una con version fija y SHA-256 comprobado AQUI: los paquetes del sistema de Chromium (`image/apt.lock`: version y suma de cada .deb),
# el Chromium headless shell de la revision 1248 y `kubectl` v1.37.x (la del nodo de kind, `platform/kind/cluster.yaml`). Cambiar un digito de una suma rompe la construccion (`tests/image/test_image.py`).
# Las dependencias de Python salen de `image/requirements.txt` (`uv export` del `uv.lock`, con hashes: `pip --require-hashes`).

# Etapa 1: el lock de los paquetes del sistema (una etapa propia para que la prueba pueda sustituirlo con `--build-context applock=<dir>`).
FROM scratch AS applock
COPY system-verification/image/apt.lock /apt.lock

# Etapa 2: los .deb de Chromium, por version exacta y con la suma de cada uno comprobada contra `apt.lock`.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS debs
COPY --from=applock /apt.lock /apt.lock
WORKDIR /debs
# hadolint ignore=DL3008
RUN set -eu; \
    apt-get update -qq; \
    mkdir -p /debs/partial; \
    awk '{print $1 "=" $2}' /apt.lock > /pins; \
    xargs -a /pins apt-get install -y --no-install-recommends --download-only -o Dir::Cache::archives=/debs; \
    awk '{print $4 "  " $5}' /apt.lock > /sums; \
    sha256sum -c /sums; \
    set -- /debs/*.deb; \
    test "$#" -eq "$(wc -l < /apt.lock)"

# Etapa 3: `kubectl` y el Chromium headless shell, descargados con la suma comprobada.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS fetch
COPY system-verification/image/fetch.py /fetch.py
ARG KUBECTL_VERSION=v1.37.0
ARG KUBECTL_SHA256=6129359f4e1f3848a5572ccb0b26cf28b8ca08cef38c95a765b2f64a2c961a2f
RUN python3 /fetch.py get "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" "${KUBECTL_SHA256}" /out/kubectl --mode 0755
ARG CHROMIUM_VERSION=156.0.8078.4
ARG CHROMIUM_REVISION=1248
ARG CHROMIUM_SHA256=c3e50596aef52c58f8fda3c6b3411c33d34c88b177b3ed1c2243359fd3b8ba20
RUN python3 /fetch.py get "https://cdn.playwright.dev/builds/cft/${CHROMIUM_VERSION}/linux64/chrome-headless-shell-linux64.zip" "${CHROMIUM_SHA256}" /dl/chromium.zip \
    && python3 /fetch.py unzip /dl/chromium.zip "/out/browsers/chromium_headless_shell-${CHROMIUM_REVISION}" \
    && touch "/out/browsers/chromium_headless_shell-${CHROMIUM_REVISION}/INSTALLATION_COMPLETE" \
    && chmod -R a+rX,go-w /out/browsers

# Etapa 4: las dependencias de Python con hash y los dos paquetes del workspace. `vectra-verification` queda en modo editable sobre /opt/system-verification:
# `cli.py` busca `report/story-map.yaml` junto a `src/`, y los guiones y `verify` viven en el mismo arbol.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
COPY system-verification/image/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps --prefix=/install -r /requirements.txt
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY system-verification/pyproject.toml /opt/system-verification/pyproject.toml
COPY system-verification/src /opt/system-verification/src
RUN pip install --no-cache-dir --no-deps --prefix=/install /src/vectra_contracts \
    && pip install --no-cache-dir --no-deps --prefix=/install -e /opt/system-verification

FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright HOME=/tmp VERIFICATION_CHROMIUM_SANDBOX=1
RUN --mount=from=debs,source=/debs,target=/debs --mount=from=applock,source=/apt.lock,target=/apt.lock \
    awk '{print "/debs/" $5}' /apt.lock > /tmp/debs.list \
    && xargs -a /tmp/debs.list dpkg -i \
    && rm -f /tmp/debs.list
COPY --from=fetch /out/kubectl /usr/local/bin/kubectl
COPY --from=fetch /out/browsers /opt/ms-playwright
COPY --from=build /install /usr/local
COPY --from=build /opt/system-verification /opt/system-verification
COPY system-verification/demos /opt/system-verification/demos
COPY system-verification/report /opt/system-verification/report
# El perfil `seccomp` que el operador pasa a `docker run` (`--security-opt seccomp=`): `docker run --rm --entrypoint cat <imagen> /opt/system-verification/seccomp/chrome.json > chrome.json`.
COPY system-verification/seccomp /opt/system-verification/seccomp
# Usuario numerico distinto de root; el operador la corre con `--user "$(id -u):$(id -g)"` y cualquier uid sirve (HOME en el tmpfs, navegadores legibles por todos).
# El directorio de evidencias se monta en /verification/evidence (`--dir` por omision).
WORKDIR /verification
# La huella de las fuentes (`image/source_digest.py`): la prueba de la imagen la compara y rechaza una imagen anterior a las fuentes.
ARG SOURCE_DIGEST=desconocida
LABEL org.vectra.system-verification.source-digest="${SOURCE_DIGEST}"
USER 65532:65532
ENTRYPOINT ["vectra-verification"]
CMD ["--help"]
