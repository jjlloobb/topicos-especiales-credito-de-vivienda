# MinIO y mc ya no publican imagenes oficiales accesibles sin autenticacion: se construyen desde el tag del codigo.
# Construir desde esta carpeta. AGPL-3.0: revisar con cumplimiento antes de distribuir la imagen.
# --target server produce `minio`; --target client produce `mc`. El chart ejecuta /bin/sh en ambas.
FROM docker.io/library/golang:1.25-alpine@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59 AS build
RUN apk add --no-cache git \
 && git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio /src/minio \
 && git clone --depth 1 --branch RELEASE.2025-08-13T08-35-41Z https://github.com/minio/mc /src/mc \
 && cd /src/minio && CGO_ENABLED=0 go build -trimpath -o /out/minio . \
 && cd /src/mc && CGO_ENABLED=0 go build -trimpath -o /out/mc .

FROM docker.io/library/alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f AS server
COPY --from=build /out/minio /usr/bin/minio
COPY docker-entrypoint.sh /usr/bin/docker-entrypoint.sh
RUN chmod 0555 /usr/bin/docker-entrypoint.sh
USER 65532

FROM docker.io/library/alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f AS client
COPY --from=build /out/mc /usr/bin/mc
USER 65532
