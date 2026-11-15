#!/bin/sh
# Funciones comunes de los guiones de lectura de `docs/kind/` (U12-T06). Solo lectura: `kubectl get`, `logs`, `auth can-i` y `port-forward` a **un pod**, y la API de lectura de Prometheus por 127.0.0.1.
# Los guiones corren con el kubeconfig de administrador de kind del operador (no con K16). Salida: 0 todo bien, 1 hubo hallazgos, 2 no se pudo leer. Ningun guion espera con un `sleep` fijo: el unico sondeo es el del `port-forward` (`open_prom` de
# `demos/verify/lib.sh` y `wait_forward` de aqui, la misma espera: 50 vueltas de 0,2 s, un plazo de 10 s). Selectores y puertos de Prometheus: los de ese archivo (un solo sitio).
# shellcheck source=/dev/null
. "$(dirname "$0")/../../demos/verify/lib.sh"

# `wait_forward <registro> <pid> <que>`: espera, con plazo (50 vueltas de 0,2 s = 10 s, como `open_prom`), a que el `port-forward` en segundo plano `<pid>` imprima `Forwarding from 127.0.0.1:<puerto>`
# en `<registro>`, y deja el puerto en FORWARD_PORT. Sale con 2 si el proceso cae o si vence el plazo. El `kubectl` real tarda mas de 0,2 s en imprimir: sin pausa por vuelta el plazo seria de ~100 ms (F-01).
wait_forward() {
  FORWARD_PORT=""
  forward_tries=0
  while [ "$forward_tries" -lt 50 ]; do
    FORWARD_PORT="$(sed -n 's/.*127\.0\.0\.1:\([0-9]*\) ->.*/\1/p' "$1" | head -n 1)"
    [ -n "$FORWARD_PORT" ] && return 0
    kill -0 "$2" 2>/dev/null || cannot_read "el port-forward a $3 cayo: $(head -c 200 "$1")"
    forward_tries=$((forward_tries + 1))
    sleep 0.2
  done
  cannot_read "el port-forward a $3 no abrio"
}

# `prom_api <ruta> [clave=valor ...]`: el JSON de una ruta de la API de lectura de Prometheus (requiere `open_prom` antes). Falla con 2 si no responde o no dice `success`.
prom_api() {
  [ -n "$PROM_PORT" ] || cannot_read "falta open_prom antes de consultar Prometheus"
  python3 - "$PROM_PORT" "$@" <<'PY' || cannot_read "Prometheus no respondio a $2"
import json, sys, urllib.parse, urllib.request
port, path, *pairs = sys.argv[1:]
params = [tuple(p.split("=", 1)) for p in pairs]
url = f"http://127.0.0.1:{port}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
with urllib.request.urlopen(url, timeout=20) as answer:
    body = json.load(answer)
if body.get("status") != "success":
    sys.exit(1)
print(json.dumps(body["data"]))
PY
}
