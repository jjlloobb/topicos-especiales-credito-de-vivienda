#!/bin/sh
# Diagnostico de arranque (K-05, K-06, K-08, K-10 a K-17, K-23): `arranque.sh [--estricto] <namespace>...`. Solo lectura. Por cada namespace pedido informa los pods que no estan `Running` o `Completed`,
# los `ImagePullBackOff`/`ErrImagePull`/`CreateContainerConfigError`/`CrashLoopBackOff`, los `OOMKilled`, los contenedores que **salieron con codigo 0 y sin mensaje** (un reinicio con
# `lastState.terminated.exitCode == 0`: falta una variable o la llave, K-13), y los `ExternalSecret` que no estan `SecretSynced`; ademas, las Applications de Argo CD fuera de `Healthy`.
# Siempre lee tambien `linkerd-cni` (aunque no se pida): su Application puede verse `Healthy` mientras sus pods fallan con `too many open files` (el limite de inotify no sobrevive a un reinicio; F-04),
# y marca un pod de la boveda (`vault`) que se **reinicio y no se resembro despues**, con cualquier codigo de salida: un reinicio de la maquina la deja vacia (guarda todo en memoria) con un codigo que no es el 0 ni el OOM (K-05).
# `restartCount` no baja nunca (y vuelve a 0 si el pod se recrea), asi que no sirve de puerta: **siempre**, con cualquier numero de reinicios, la boveda cuenta como resembrada si el contenedor arranco
# (`state.running.startedAt`) **antes** de la ultima sincronizacion de **todos** los `ExternalSecret` del cluster (`status.refreshTime`) y todos estan `Ready=True`/`SecretSynced`. Un `ExternalSecret` que se
# refresca solo por su intervalo contra una boveda vacia falla la lectura y pasa a `Ready=False`: sigue marcado. Un pod recreado (0 reinicios) y vacio, con ExternalSecret sincronizados antes de su arranque, FALLA.
# Reiniciada y resembrada es un AVISO (sale 0); sin resembrar (con o sin reinicios), FALLA (sale 1); sin reinicios y resembrada, nada que decir. Sin ningun ExternalSecret con el que comparar, FALLA y lo dice.
# Una Application `OutOfSync` es un AVISO (las cinco de U1 lo estan: `cierre-acotado.md`); con `--estricto` tambien falla.
# Salida: 0 sin hallazgos, 1 con hallazgos, 2 no se pudo leer. Sin esperas.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

STRICT=0
if [ "${1:-}" = "--estricto" ]; then STRICT=1; shift; fi
[ "$#" -ge 1 ] || { say "uso: arranque.sh [--estricto] <namespace>..." >&2; exit 2; }

FAIL=0

# Se leen antes que los pods: la puerta de la boveda compara el arranque de su contenedor con la sincronizacion de los ExternalSecret.
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get externalsecret -A -o json > "$TMP_DIR/es.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los ExternalSecret: $(head -c 200 "$TMP_DIR/err")"

NAMESPACES="$*"
case " $NAMESPACES " in *" linkerd-cni "*) ;; *) NAMESPACES="$NAMESPACES linkerd-cni" ;; esac
# shellcheck disable=SC2086 # los namespaces no llevan espacios: se parte la lista a proposito
for NS in $NAMESPACES; do
  kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n "$NS" -o json > "$TMP_DIR/pods.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los pods de $NS: $(head -c 200 "$TMP_DIR/err")"
  python3 - "$NS" "$TMP_DIR/pods.json" "$TMP_DIR/es.json" <<'PY' || FAIL=1
import json, sys
from datetime import datetime, timezone

namespace, path, es_path = sys.argv[1:4]


def instant(text):
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def vault_unseeded(started_at):
    """(motivo, lista): `unreadable` (el arranque no se lee), `empty` (no hay ExternalSecret con que comparar), o `stale` con los ExternalSecret que no prueban una siembra posterior al arranque (vacia: resembrada)."""
    started = instant(started_at)
    items = json.load(open(es_path))["items"]
    if started is None:
        return "unreadable", []
    if not items:
        return "empty", []
    stale = []
    for item in items:
        status = item.get("status", {})
        ready = [c for c in status.get("conditions", []) if c.get("type") == "Ready"]
        synced = bool(ready) and ready[0].get("status") == "True" and ready[0].get("reason") == "SecretSynced"
        refreshed = instant(status.get("refreshTime"))
        if not synced or refreshed is None or refreshed < started:
            stale.append(item["metadata"]["namespace"] + "/" + item["metadata"]["name"])
    return "stale", stale


BAD_WAITING = {"ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError", "CreateContainerError", "CrashLoopBackOff", "InvalidImageName"}
findings = []
pods = json.load(open(path))["items"]
for pod in pods:
    name = pod["metadata"]["name"]
    status = pod.get("status", {})
    phase = status.get("phase", "?")
    if phase not in ("Running", "Succeeded"):
        findings.append(f"{namespace}/{name}: fase {phase}")
    statuses = status.get("containerStatuses", []) + status.get("initContainerStatuses", [])
    for container in statuses:
        waiting = container.get("state", {}).get("waiting", {}).get("reason")
        if waiting in BAD_WAITING:
            findings.append(f"{namespace}/{name} [{container['name']}]: {waiting}")
        last = container.get("lastState", {}).get("terminated")
        if namespace == "vault":
            restarts = container.get("restartCount", 0)
            started_at = container.get("state", {}).get("running", {}).get("startedAt")
            reason, stale = vault_unseeded(started_at)
            if restarts > 0:
                what = f"{namespace}/{name} [{container['name']}]: la boveda se reinicio ({restarts} reinicios, ultimo codigo {(last or {}).get('exitCode', '?')})"
            else:
                what = f"{namespace}/{name} [{container['name']}]: la boveda arranco el {started_at or '?'} (0 reinicios)"
            reseed = "en kind guarda todo en memoria; vuelve a sembrar (`seed-vault.sh` y `seed-vault.sh identity`; K-05)"
            if reason == "unreadable":
                findings.append(f"{what} y no se pudo leer su arranque para compararlo con la sincronizacion de los ExternalSecret: {reseed}")
            elif reason == "empty":
                findings.append(f"{what} y no hay ningun ExternalSecret en el cluster con el que comprobar que se resembro: {reseed}")
            elif stale:
                findings.append(
                    f"{what} y {len(stale)} ExternalSecret no se sincronizaron despues de su arranque ({', '.join(stale[:3])}{'...' if len(stale) > 3 else ''}): {reseed}"
                )
            elif restarts > 0:
                print(f"AVISO {what}, resembrada: todos los ExternalSecret se sincronizaron despues de su arranque (K-05)")
        if last and container.get("restartCount", 0) > 0:
            if last.get("exitCode") == 0:
                findings.append(
                    f"{namespace}/{name} [{container['name']}]: salio con codigo 0 y sin mensaje ({container['restartCount']} reinicios, "
                    f"reason {last.get('reason')}): falta una variable o la llave private_key_jwt; mira `logs --previous` y el ExternalSecret de esa unidad (K-13)"
                )
            if last.get("reason") == "OOMKilled":
                findings.append(f"{namespace}/{name} [{container['name']}]: OOMKilled")
    if phase == "Running" and not any(c.get("state", {}).get("waiting") for c in statuses):
        not_ready = [c["name"] for c in status.get("containerStatuses", []) if not c.get("ready")]
        if not_ready:
            findings.append(f"{namespace}/{name}: contenedores no listos {', '.join(not_ready)}")
for line in findings:
    print("FALLA " + line)
if namespace == "linkerd-cni" and findings:
    print("linkerd-cni: si el log dice `too many open files`, es el limite de inotify del host (F0): vuelve a aplicarlo y sigue `Despues de reiniciar la maquina`, de la guia")
print(f"{namespace}: {len(pods)} pods, {len(findings)} hallazgos")
sys.exit(1 if findings else 0)
PY
done

python3 - "$TMP_DIR/es.json" "$@" <<'PY' || FAIL=1
import json, sys

path, *namespaces = sys.argv[1:]
unsynced = []
total = 0
for item in json.load(open(path))["items"]:
    meta = item["metadata"]
    if meta["namespace"] not in namespaces:
        continue
    total += 1
    ready = [c for c in item.get("status", {}).get("conditions", []) if c.get("type") == "Ready"]
    if not ready or ready[0].get("status") != "True" or ready[0].get("reason") != "SecretSynced":
        reason = ready[0].get("reason") if ready else "sin estado"
        unsynced.append(f"{meta['namespace']}/{meta['name']}: {reason} (ruta sin sembrar en la boveda, o la boveda se reinicio: K-05)")
for line in unsynced:
    print("FALLA ExternalSecret " + line)
print(f"ExternalSecret: {total} en los namespaces pedidos, {len(unsynced)} sin SecretSynced")
sys.exit(1 if unsynced else 0)
PY

kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get applications.argoproj.io -n argocd -o json > "$TMP_DIR/apps.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer las Applications: $(head -c 200 "$TMP_DIR/err")"
python3 - "$TMP_DIR/apps.json" "$STRICT" <<'PY' || FAIL=1
import json, sys

path, strict = sys.argv[1], sys.argv[2] == "1"
bad, warn = [], []
apps = json.load(open(path))["items"]
for app in apps:
    name = app["metadata"]["name"]
    status = app.get("status", {})
    sync = status.get("sync", {}).get("status", "?")
    health = status.get("health", {}).get("status", "?")
    if health != "Healthy":
        bad.append(f"Application {name}: salud {health} (sync {sync})")
    elif sync != "Synced":
        warn.append(f"Application {name}: {sync}")
for line in bad:
    print("FALLA " + line)
for line in warn:
    print(("FALLA " if strict else "AVISO ") + line)
print(f"Applications: {len(apps)}, {len(bad)} fuera de Healthy, {len(warn)} fuera de Synced")
sys.exit(1 if bad or (strict and warn) else 0)
PY

[ "$FAIL" -eq 0 ] || { say "arranque: HAY HALLAZGOS" >&2; exit 1; }
say "arranque: sin hallazgos"
