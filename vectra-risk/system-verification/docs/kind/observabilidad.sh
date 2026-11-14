#!/bin/sh
# Lectura de Prometheus (K-04, K-19 a K-21, K-25, K-41 a K-43, K-51, K-56): `observabilidad.sh reglas [alerta...] | targets | consulta <expr> | serie <nombre>`. Solo lectura: un `port-forward` a **un pod**
# (nunca `svc/...`) y la API de lectura de Prometheus por 127.0.0.1. Salida: 0 bien, 1 hallazgo (regla ausente, target caido, serie inexistente), 2 no se pudo leer.
#   reglas [alerta...]  los grupos de reglas cargados; falla si falta alguna de las alertas pedidas (por omision CoreWriteAttempt, FailClosedPersistente y ProductMetricsStale: U8 y U11)
#   targets             los targets por job, namespace y salud; falla si el target `linkerd-proxy` de `vectra-mock` no esta `up` o si algun target de `vectra-app` o `vectra-mock` esta caido
#   consulta <expr>     una consulta instantanea: imprime cada serie con sus etiquetas y su valor; sin series dice `sin resultados` (y sale 0: una alerta apagada no es un error)
#   serie <nombre>      el conjunto de etiquetas que de verdad emite una serie (K-41); falla si no existe
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

COMMAND="${1:-}"
[ -n "$COMMAND" ] || { say "uso: observabilidad.sh reglas [alerta...] | targets | consulta <expr> | serie <nombre>" >&2; exit 2; }
shift
open_prom

case "$COMMAND" in
  reglas)
    prom_api /api/v1/rules > "$TMP_DIR/rules.json" || exit 2
    python3 - "$TMP_DIR/rules.json" "$@" <<'PY'
import json, sys

path, *wanted = sys.argv[1:]
wanted = wanted or ["CoreWriteAttempt", "FailClosedPersistente", "ProductMetricsStale"]
groups = json.load(open(path))["groups"]
alerts = set()
for group in groups:
    names = [r["name"] for r in group["rules"] if r.get("type") == "alerting"]
    alerts |= set(names)
    print(f"grupo {group['name']}: {len(group['rules'])} reglas" + (f" ({', '.join(names)})" if names else ""))
missing = [name for name in wanted if name not in alerts]
for name in missing:
    print(f"FALLA la alerta {name} no esta cargada")
print(f"{len(groups)} grupos; pedidas: {', '.join(wanted)}")
sys.exit(1 if missing else 0)
PY
    ;;
  targets)
    prom_api /api/v1/targets > "$TMP_DIR/targets.json" || exit 2
    python3 - "$TMP_DIR/targets.json" <<'PY'
import json, sys
from collections import Counter

targets = json.load(open(sys.argv[1]))["activeTargets"]
count = Counter()
problems = []
proxy_up = False
for target in targets:
    labels = target.get("labels", {})
    job, namespace, health = labels.get("job", "?"), labels.get("namespace", "?"), target.get("health", "?")
    count[(job, namespace, health)] += 1
    if job == "linkerd-proxy" and namespace == "vectra-mock" and health == "up":
        proxy_up = True
    if health != "up" and namespace in ("vectra-app", "vectra-mock"):
        problems.append(f"FALLA target {job} en {namespace}: {health} {str(target.get('lastError', ''))[:120]}")
for (job, namespace, health), n in sorted(count.items()):
    print(f"{job} {namespace} {health} x{n}")
if not proxy_up:
    problems.append("FALLA el target linkerd-proxy de vectra-mock no esta up (K-21: el Server del 4191 puede bloquear el raspado)")
for line in problems:
    print(line)
sys.exit(1 if problems else 0)
PY
    ;;
  consulta)
    [ -n "${1:-}" ] || { say "uso: observabilidad.sh consulta <expr>" >&2; exit 2; }
    prom_api /api/v1/query "query=$1" > "$TMP_DIR/query.json" || exit 2
    python3 - "$TMP_DIR/query.json" <<'PY'
import json, sys

result = json.load(open(sys.argv[1]))["result"]
if not result:
    print("sin resultados")
for series in result:
    labels = ",".join(f'{k}="{v}"' for k, v in sorted(series.get("metric", {}).items()))
    print(f"{{{labels}}} {series['value'][1]}")
PY
    ;;
  serie)
    [ -n "${1:-}" ] || { say "uso: observabilidad.sh serie <nombre>" >&2; exit 2; }
    prom_api /api/v1/series "match[]=$1" > "$TMP_DIR/series.json" || exit 2
    python3 - "$TMP_DIR/series.json" "$1" <<'PY'
import json, sys

found = json.load(open(sys.argv[1]))
if not found:
    print(f"FALLA la serie {sys.argv[2]} no existe en Prometheus")
    sys.exit(1)
sets = sorted({",".join(f'{k}="{v}"' for k, v in sorted(s.items()) if k != "__name__") for s in found})
for labels in sets:
    print(f"{sys.argv[2]}{{{labels}}}")
PY
    ;;
  *)
    say "uso: observabilidad.sh reglas [alerta...] | targets | consulta <expr> | serie <nombre>" >&2
    exit 2
    ;;
esac
