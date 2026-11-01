# Simulacro de restauracion (P-U1-05). Construir desde esta carpeta.
# `vectra-registry` (U3) y `case-retention` (U8) se agregan a esta imagen cuando esas unidades existan.
FROM registry.k8s.io/kubectl:v1.37.2@sha256:fe049faa65ae483ac200009a949a68fa4c9985daea12c9cb1195c9c7965301fc AS kubectl
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl
RUN pip install --no-cache-dir "psycopg[binary]==3.3.6"
COPY drill.py /app/drill.py
COPY restore-cluster.sh /usr/local/bin/restore-cluster.sh
USER 65532
ENTRYPOINT ["python", "/app/drill.py"]
