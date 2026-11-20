#!/bin/sh
# Memoria (K-01, K-09, K-23, K-47, K-54, K-59): `memoria.sh antes|durante|despues`. Solo lectura. Imprime `free -m`, `docker stats --no-stream` de los nodos de kind y del contenedor de U12
# (`VERIF_CONTAINER`, por omision el de la orden `docker run` de la guia) y, por pod de `vectra-*`, la memoria de trabajo que mide Prometheus (`container_memory_working_set_bytes`) frente al request
# que declara el pod (`kubectl get pods -o json`, con `Ki`, `Mi`, `Gi` y bytes normalizados a MiB). No usa la orden `top`: no es un verbo permitido.
# Puertas: `antes` pide al menos 3072 MiB disponibles, `durante` al menos 1536 MiB, `despues` ninguna. El guion lee los pods y Prometheus, asi que solo corre con el cluster ya instalado:
# `antes` es antes de una fase pesada, no antes de instalar (los 8 GiB de K-01 se miran con `free -m`). Sus 3072 MiB son la puerta de `durante` (1536), el limite del contenedor de U12
# (`--memory 1g`) y 512 MiB para los pods de modelo que agrega D2. Las dos se cambian con `MIN_DISPONIBLE_ANTES_MIB` y `MIN_DISPONIBLE_DURANTE_MIB`. Falla (1) si no se
# cumple la puerta o si algun pod se reinicio por `OOMKilled`; 2 si no se pudo leer. Sin esperas.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

PHASE="${1:-}"
case "$PHASE" in
  antes) MIN_MIB="${MIN_DISPONIBLE_ANTES_MIB:-3072}" ;;
  durante) MIN_MIB="${MIN_DISPONIBLE_DURANTE_MIB:-1536}" ;;
  despues) MIN_MIB=0 ;;
  *) say "uso: memoria.sh antes|durante|despues" >&2; exit 2 ;;
esac

say "== free -m"
free -m > "$TMP_DIR/free.txt" || cannot_read "free -m"
cat "$TMP_DIR/free.txt"
AVAILABLE="$(awk '/^Mem:/ {print $7}' "$TMP_DIR/free.txt")"
[ -n "$AVAILABLE" ] || cannot_read "no se pudo leer la columna disponible de free -m"

say "== docker stats (nodos de kind, registro y U12)"
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.MemPerc}}' > "$TMP_DIR/docker.txt" 2> "$TMP_DIR/err" || cannot_read "docker stats: $(head -c 200 "$TMP_DIR/err")"
grep -E "^(vectra-|kind-registry|${VERIF_CONTAINER:-vectra-verification})" "$TMP_DIR/docker.txt" || say "ningun contenedor de kind ni de U12 en docker stats"

kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -A -o json > "$TMP_DIR/pods.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los pods: $(head -c 200 "$TMP_DIR/err")"
open_prom
prom_api /api/v1/query 'query=sum by (namespace, pod) (container_memory_working_set_bytes{namespace=~"vectra-.*", container!="", container!="POD"})' > "$TMP_DIR/ws.json" || exit 2

say "== memoria de trabajo por pod frente al request (MiB)"
python3 - "$TMP_DIR/pods.json" "$TMP_DIR/ws.json" "$AVAILABLE" "$MIN_MIB" "$PHASE" <<'PY'
import json, re, sys

pods_path, ws_path, available, minimum, phase = sys.argv[1:]
UNITS = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1024 * 1024, "k": 1000 / 2**20, "M": 1e6 / 2**20, "G": 1e9 / 2**20, "": 1 / 2**20}


def mib(quantity: str) -> float:
    """Una cantidad de Kubernetes (`128Mi`, `1Gi`, `262144Ki`, `134217728`) en MiB."""
    match = re.fullmatch(r"([0-9.]+)(Ki|Mi|Gi|Ti|k|M|G)?", quantity)
    if match is None:
        raise ValueError(f"cantidad de memoria que no entiendo: {quantity}")
    return float(match.group(1)) * UNITS[match.group(2) or ""]


requests, oom = {}, []
for pod in json.load(open(pods_path))["items"]:
    namespace, name = pod["metadata"]["namespace"], pod["metadata"]["name"]
    if not namespace.startswith("vectra-"):
        continue
    total = 0.0
    for container in pod["spec"].get("containers", []):
        quantity = container.get("resources", {}).get("requests", {}).get("memory")
        total += mib(quantity) if quantity else 0.0
    requests[(namespace, name)] = total
    for status in pod.get("status", {}).get("containerStatuses", []):
        if status.get("lastState", {}).get("terminated", {}).get("reason") == "OOMKilled":
            oom.append(f"{namespace}/{name} [{status['name']}]")
rows = []
for series in json.load(open(ws_path))["result"]:
    key = (series["metric"].get("namespace", "?"), series["metric"].get("pod", "?"))
    used = float(series["value"][1]) / 2**20
    rows.append((key, used, requests.get(key, 0.0)))
for (namespace, name), used, requested in sorted(rows):
    mark = "  SOBRE EL REQUEST" if requested and used > requested else ""
    print(f"{namespace}/{name}: {used:.0f} MiB de trabajo, request {requested:.0f} MiB{mark}")
print(f"{len(rows)} pods medidos; fase {phase}; disponible {available} MiB (puerta {minimum} MiB)")
problems = []
if int(available) < int(minimum):
    problems.append(f"FALLA solo hay {available} MiB disponibles y la puerta de `{phase}` pide {minimum}: cierra todo lo demas y no sigas (riesgo R-4)")
for pod in oom:
    problems.append(f"FALLA OOMKilled: {pod}")
for line in problems:
    print(line)
sys.exit(1 if problems else 0)
PY
