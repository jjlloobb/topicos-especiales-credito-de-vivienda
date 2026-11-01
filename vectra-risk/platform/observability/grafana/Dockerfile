# Job y CronJob de permisos de carpetas (F110, F113). Construir desde esta carpeta.
FROM docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN pip install --no-cache-dir pyyaml==6.0.3
COPY folder_permissions.py folder-permissions.yaml /app/
USER 65532
ENTRYPOINT ["python", "/app/folder_permissions.py"]
