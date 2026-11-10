#!/usr/bin/env bash
# Escenario 7 (acotado): cuanto tarda el `etag` y el estado de `serving-config` en cambiar, en cada replica de governance, despues de un `freeze`.
# Con U7 y U9 ausentes se mide solo hasta `serving-config`; el escenario sigue pendiente hasta U7 Paso 18.
#
# Entra por `kubectl exec -i` a cada replica y llama a 127.0.0.1:8080 (el servicio valida el token, no la identidad del pod): la malla solo
# admite `serving-config` a scoring/case-service y `freeze` al `bias-monitoring-job`, que todavia no existen. Los tokens de servicio entran por
# stdin (una linea por token), nunca por argumento ni por variable.
#
#   medir-freeze.sh [--dry-run] <model_version_id>
#
# Necesita en el entorno lo mismo que `token.sh --servicio`. Escribe una linea por replica `<pod> cambio_en=<s>` y `maximo=<s>`; el escenario
# pasa con `maximo` <= 6. Despues del freeze, la reactivacion (`frozen-resolution`, cumplimiento-1) la hace la guia.
set -euo pipefail

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
modelo="${1:?uso: medir-freeze.sh [--dry-run] <model_version_id>}"
ctx="${CTX:-kind-vectra}"
aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

read -r -d '' sonda <<'PY' || true
import json, sys, time, urllib.request, urllib.error
accion = sys.argv[1]
token, _, resto = sys.stdin.buffer.read().partition(b"\n")  # una sola lectura: readline() + buffer.read() pierde el cuerpo
token = token.decode().strip()
base = "http://127.0.0.1:8080"
def pedir(metodo, ruta, cuerpo=None, etag=None):
    req = urllib.request.Request(base + ruta, data=cuerpo, method=metodo)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers.get("ETag"), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("ETag"), e.read().decode()
if accion == "sondear":
    estado, etag, _ = pedir("GET", "/v1/serving-config")
    print("listo", estado, etag, flush=True)
    inicio = time.time()
    while time.time() - inicio < 30:
        estado, nuevo, cuerpo = pedir("GET", "/v1/serving-config", etag=etag)
        if estado == 200 and nuevo != etag:
            print("cambio", time.time(), json.loads(cuerpo)["state"], nuevo, flush=True)
            sys.exit(0)
        time.sleep(0.2)
    print("sin_cambio", flush=True)
    sys.exit(1)
instante = time.time()
estado, _, cuerpo = pedir("POST", "/v1/models/" + sys.argv[2] + "/freeze", resto)
print("freeze", instante, estado, cuerpo, flush=True)
sys.exit(0 if estado == 204 else 1)
PY

if [ "$dry" = 1 ]; then
  echo "dry-run: sondear serving-config en cada replica de governance-service, freeze de $modelo y medir"
  echo "dry-run: kubectl --context $ctx -n vectra-app exec -i <replica> -c governance-service -- python -c <sonda> sondear"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mapfile -t replicas < <(kubectl --context "$ctx" -n vectra-app get pods -l app.kubernetes.io/name=governance-service -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
[ "${#replicas[@]}" -ge 2 ] || { echo "se esperaban 2 replicas de governance-service y hay ${#replicas[@]}" >&2; exit 1; }

pids=()
for replica in "${replicas[@]}"; do
  "$aqui/token.sh" --servicio scoring-service governance:read-serving \
    | kubectl --context "$ctx" -n vectra-app exec -i "$replica" -c governance-service -- python -c "$sonda" sondear > "$tmp/$replica" &
  pids+=($!)
done
sleep "${ESPERA_SONDAS:-3}"   # las sondas ya leyeron el etag inicial
{ "$aqui/token.sh" --servicio bias-monitoring-job governance:freeze; "$aqui/freeze-cuerpo.sh" "$modelo"; } \
  | kubectl --context "$ctx" -n vectra-app exec -i "${replicas[0]}" -c governance-service -- python -c "$sonda" freeze "$modelo" > "$tmp/freeze"
for pid in "${pids[@]}"; do wait "$pid" || true; done

inicio="$(awk '$1 == "freeze" {print $2}' "$tmp/freeze")"
maximo=0
for replica in "${replicas[@]}"; do
  fin="$(awk '$1 == "cambio" {print $2}' "$tmp/$replica")"
  if [ -z "$fin" ]; then echo "$replica sin_cambio"; maximo=999; continue; fi
  segundos="$(awk -v a="$inicio" -v b="$fin" 'BEGIN {printf "%.2f", b - a}')"
  echo "$replica cambio_en=$segundos"
  maximo="$(awk -v a="$maximo" -v b="$segundos" 'BEGIN {print (b > a) ? b : a}')"
done
echo "maximo=$maximo"
