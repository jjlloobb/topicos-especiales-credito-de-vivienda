#!/bin/sh
# Funciones comunes de los `verify` de las demos (U12-T04, BR-U12-09). Solo lectura: `kubectl get`, `logs`, `auth can-i` y `port-forward` a **un pod** (K16), la API de lectura de Prometheus por 127.0.0.1 y los
# archivos que la CLI ya escribio en el directorio de la verificacion (VERIFICATION_DIR, por omision `evidence`). No inicia sesion, no lee la boveda y no escribe en `evidence/`.
# Salida: 0 (el estado esperado), 1 (no lo es), 2 (no se pudo leer). Cada orden de `kubectl` lleva `--context` literal: el detector de verbos no entiende una funcion que la envuelva.

VERIFICATION_DIR="${VERIFICATION_DIR:-evidence}"
TMP_DIR="$(mktemp -d)"
PF_PID=""
PROM_PORT=""

cleanup() {
  if [ -n "$PF_PID" ]; then kill "$PF_PID" 2>/dev/null; fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

say() { printf '%s\n' "$*"; }
cannot_read() { say "NO SE PUDO LEER: $*" >&2; exit 2; }
expected() { say "OK: $*"; exit 0; }
not_expected() { say "NO ES LO ESPERADO: $*"; exit 1; }

# El `runId` de la verificacion, del manifiesto que escribio `prepare`.
run_id() {
  [ -f "$VERIFICATION_DIR/manifest.json" ] || cannot_read "no hay $VERIFICATION_DIR/manifest.json: corre prepare primero"
  sed -n 's/.*"run_id": *"\([0-9]\{8\}-[0-9]\{4\}\)".*/\1/p' "$VERIFICATION_DIR/manifest.json" | head -n 1
}

# `manifest_value <clave> [<clave>...]`: el valor (texto) que el manifiesto que escribio la CLI tiene en esa ruta de claves, o vacio si no esta (por ejemplo `sections decisions result` o `closing_rt3 result`).
manifest_value() {
  [ -f "$VERIFICATION_DIR/manifest.json" ] || cannot_read "no hay $VERIFICATION_DIR/manifest.json: corre prepare primero"
  python3 - "$VERIFICATION_DIR/manifest.json" "$@" <<'PY' || cannot_read "el manifiesto no se pudo leer"
import json, sys
node = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2:]:
    node = node.get(key) if isinstance(node, dict) else None
print("" if node is None else node)
PY
}

# `evidence_result <archivo>`: el resultado (`pasa` o `falla`) de una evidencia que la CLI ya escribio.
evidence_result() {
  [ -f "$VERIFICATION_DIR/$1" ] || cannot_read "no existe la evidencia $1 en $VERIFICATION_DIR"
  sed -n 's/.*"result": *"\(pasa\|falla\)".*/\1/p' "$VERIFICATION_DIR/$1" | head -n 1
}

# Abre un `port-forward` a **un pod** de Prometheus (K16: `pods/portforward`, nunca `svc/...`) y deja el puerto local en PROM_PORT.
open_prom() {
  POD="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vectra-observability -l app.kubernetes.io/name=prometheus -o name 2>/dev/null | head -n 1)"
  [ -n "$POD" ] || cannot_read "no hay pod de Prometheus en vectra-observability"
  kubectl --context "${KUBE_CONTEXT:-kind-vectra}" port-forward -n vectra-observability --address=127.0.0.1 "$POD" :9090 > "$TMP_DIR/pf.log" 2>&1 &
  PF_PID=$!
  tries=0
  while [ "$tries" -lt 50 ]; do
    PROM_PORT="$(sed -n 's/.*127\.0\.0\.1:\([0-9]*\) ->.*/\1/p' "$TMP_DIR/pf.log" | head -n 1)"
    [ -n "$PROM_PORT" ] && return 0
    kill -0 "$PF_PID" 2>/dev/null || cannot_read "el port-forward a Prometheus cayo: $(head -c 200 "$TMP_DIR/pf.log")"
    tries=$((tries + 1))
    sleep 0.2
  done
  cannot_read "el port-forward a Prometheus no abrio"
}

# `prom_count <expr>`: cuantas series devuelve la consulta; `prom_max <expr>`: el mayor valor (vacio si no hay).
prom_json() {
  [ -n "$PROM_PORT" ] || cannot_read "falta open_prom antes de consultar Prometheus"
  python3 - "$PROM_PORT" "$1" <<'PY' || cannot_read "Prometheus no respondio a la consulta"
import json, sys, urllib.parse, urllib.request
url = f"http://127.0.0.1:{sys.argv[1]}/api/v1/query?" + urllib.parse.urlencode({"query": sys.argv[2]})
with urllib.request.urlopen(url, timeout=20) as answer:
    body = json.load(answer)
if body.get("status") != "success":
    sys.exit(1)
print(json.dumps(body["data"]["result"]))
PY
}

prom_count() {
  prom_json "$1" | python3 -c 'import json, sys; print(len(json.load(sys.stdin)))'
}

prom_max() {
  prom_json "$1" | python3 -c 'import json, sys; v = [float(i["value"][1]) for i in json.load(sys.stdin)]; print(max(v) if v else "")'
}
