#!/usr/bin/env bash
# Corre dos veces el script `custom-command` que renderiza el chart de MinIO contra un MinIO real en Docker,
# con buckets nuevos y sin reglas, y cuenta las reglas ilm que quedan. Debe quedar una por bucket.
# Uso, desde vectra-risk/: bash platform/data/minio/tests/ilm_idempotente.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
MINIO_IMAGE="${MINIO_IMAGE:-localhost:5001/minio:dev}"
MC_IMAGE="${MC_IMAGE:-localhost:5001/mc:dev}"
PREFIX=u01t02
NET="${PREFIX}-net"
SERVER="${PREFIX}-minio"
WORK="$(mktemp -d)"

cleanup() {
  docker rm -f "$SERVER" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

run_variant() { # $1 = etiqueta, $2 = buckets a crear (el primero con lock), resto = archivos values
  local label="$1" buckets="$2"; shift 2
  local values=() f
  for f in "$@"; do values+=(-f "$ROOT/$f"); done
  echo "=== $label"
  # Script de los comandos personalizados, tal como lo renderiza el chart con esos values.
  helm template minio "$ROOT/platform/.charts/minio/minio" "${values[@]}" \
    --set-string rootUser=u01t02root,rootPassword=u01t02-secret-pass --show-only templates/configmap.yaml |
    awk '/^  custom-command: /{f=1; next} f && /^    /{sub(/^    /,""); print; next} f{exit}' >"$WORK/custom-command"
  [ -s "$WORK/custom-command" ] || { echo "no se pudo extraer custom-command" >&2; exit 2; }
  printf 'u01t02root' >"$WORK/rootUser"
  printf 'u01t02-secret-pass' >"$WORK/rootPassword"
  chmod -R a+rX "$WORK"

  docker rm -f "$SERVER" >/dev/null 2>&1 || true
  docker run -d --name "$SERVER" --network "$NET" -e MINIO_ROOT_USER=u01t02root -e MINIO_ROOT_PASSWORD=u01t02-secret-pass \
    --tmpfs /data:mode=1777 --entrypoint minio "$MINIO_IMAGE" server /data >/dev/null

  # Buckets nuevos y con lock, como los deja el Job de buckets del chart: `retention set` lo exige.
  mc_sh setup 'for i in $(seq 1 30); do /usr/bin/mc alias set myminio http://$MINIO_ENDPOINT:$MINIO_PORT u01t02root u01t02-secret-pass >/dev/null 2>&1 && break; sleep 1; done
for b in '"$buckets"'; do /usr/bin/mc mb --with-lock myminio/$b || exit 1; done'

  local pass
  for pass in 1 2; do
    echo "--- pasada $pass del script del chart"
    mc_sh "pasada$pass" "/bin/sh /config/custom-command" # set -e del script: falla si un comando falla
  done

  loki="$(count loki)"
  tempo="$(count tempo)"
  echo "loki: $loki, tempo: $tempo"
  echo "reglas tras 2 pasadas: $loki"
  [ "$loki" = 1 ] && [ "$tempo" = 1 ] || failed=1
}

count() { mc_sh "count" "/usr/bin/mc alias set myminio http://\$MINIO_ENDPOINT:\$MINIO_PORT u01t02root u01t02-secret-pass >/dev/null && /usr/bin/mc ilm rule ls --json myminio/$1" |
  grep -o '"ID"' | wc -l; }

docker network create "$NET" >/dev/null
# mc: contenedor de un solo uso (siempre con prefijo y --rm, ademas del trap).
mc_sh() { # $1 = nombre, $2 = script sh
  docker run --rm --name "${PREFIX}-mc-$1" --network "$NET" -e HOME=/tmp --tmpfs /tmp:exec --tmpfs /etc/minio/mc:mode=1777 \
    -e MINIO_ENDPOINT="$SERVER" -e MINIO_PORT=9000 -v "$WORK:/config:ro" --entrypoint /bin/sh "$MC_IMAGE" -c "$2"
}

failed=0
# Base, y overlay de kind: Helm reemplaza las listas, asi que en kind `customCommands` sale entero de values-kind.yaml.
run_variant "values.yaml" "loki tempo" platform/data/minio/values.yaml
run_variant "values.yaml + values-kind.yaml" "loki tempo vectra-registry-checkpoints vectra-registry-archive vectra-model-archive" \
  platform/data/minio/values.yaml platform/data/minio/values-kind.yaml
[ "$failed" = 0 ]
