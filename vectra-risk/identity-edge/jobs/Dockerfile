# Imagen de los CronJobs de identidad (INF-U2-09, decision R3): `realm-drift` y `signing-key-age`.
# Contexto de construccion: la raiz de vectra-risk/ (`docker build -f identity-edge/jobs/Dockerfile .`), porque lleva
# `vectra_common` y `vectra_contracts` de U0 y `realm_diff.py` de identity-edge/tools/.
# La construye, escanea y firma supply-chain.yml (U1); aqui no se construye.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

WORKDIR /app
COPY contracts/python/vectra_contracts /src/vectra_contracts
COPY contracts/python/vectra_common /src/vectra_common
RUN pip install --no-cache-dir /src/vectra_contracts /src/vectra_common "pyyaml==6.0.3" \
    && rm -rf /src
COPY identity-edge/tools/realm_diff.py /app/realm_diff.py
COPY identity-edge/jobs/keycloak_admin.py identity-edge/jobs/realm_drift.py identity-edge/jobs/signing_key_age.py /app/

# Usuario numerico distinto de root (supply-chain.yml de U1 y require-run-as-non-root).
USER 65532
