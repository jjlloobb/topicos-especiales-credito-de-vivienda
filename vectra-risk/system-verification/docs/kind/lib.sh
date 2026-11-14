#!/bin/sh
# Funciones comunes de los guiones de lectura de `docs/kind/` (U12-T06). Solo lectura: `kubectl get`, `logs`, `auth can-i` y `port-forward` a **un pod**, y la API de lectura de Prometheus por 127.0.0.1.
# Los guiones corren con el kubeconfig de administrador de kind del operador (no con K16). Salida: 0 todo bien, 1 hubo hallazgos, 2 no se pudo leer. Ningun guion espera con `sleep`: el unico sondeo
# (el del `port-forward`) es el de `demos/verify/lib.sh`, con un plazo de 10 s. Selectores y puertos de Prometheus: los de ese archivo (un solo sitio).
# shellcheck source=/dev/null
. "$(dirname "$0")/../../demos/verify/lib.sh"

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
