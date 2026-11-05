# Imagen del backend de eco de kind (U02-T14, H1). Contexto de construccion: identity-edge/tests/e2e/echo/.
# La construye y la sube a `kind-registry:5000/vectra/e2e-echo` el operador en el Paso 16; aqui no se construye.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

COPY server.py /app/server.py

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["python", "-u", "/app/server.py"]
