#!/bin/sh
# El chart de MinIO arranca con `/usr/bin/docker-entrypoint.sh minio server ...`; la imagen oficial lo traia.
# Esta imagen no tiene nada que preparar antes: solo ejecuta el comando recibido.
exec "$@"
