#!/bin/sh
# Diagnostico de arranque (K-05, K-06, K-08, K-10 a K-17, K-23): `arranque.sh [--estricto] <namespace>...`. Solo lectura. Por cada namespace pedido informa los pods que no estan `Running` o `Completed`,
# los `ImagePullBackOff`/`ErrImagePull`/`CreateContainerConfigError`/`CrashLoopBackOff`, los `OOMKilled`, los contenedores que **salieron con codigo 0 y sin mensaje** (un reinicio con
# `lastState.terminated.exitCode == 0`: falta una variable o la llave, K-13), y los `ExternalSecret` que no estan `SecretSynced`; ademas, las Applications de Argo CD fuera de `Healthy`.
# Una Application `OutOfSync` es un AVISO (las cinco de U1 lo estan: `cierre-acotado.md`); con `--estricto` tambien falla.
# Salida: 0 sin hallazgos, 1 con hallazgos, 2 no se pudo leer. Sin esperas.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

STRICT=0
if [ "${1:-}" = "--estricto" ]; then STRICT=1; shift; fi
[ "$#" -ge 1 ] || { say "uso: arranque.sh [--estricto] <namespace>..." >&2; exit 2; }

FAIL=0

for NS in "$@"; do
  kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n "$NS" -o json > "$TMP_DIR/pods.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los pods de $NS: $(head -c 200 "$TMP_DIR/err")"
  python3 - "$NS" "$TMP_DIR/pods.json" <<'PY' || FAIL=1
import json, sys

namespace, path = sys.argv[1:3]
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
print(f"{namespace}: {len(pods)} pods, {len(findings)} hallazgos")
sys.exit(1 if findings else 0)
PY
done

kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get externalsecret -A -o json > "$TMP_DIR/es.json" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los ExternalSecret: $(head -c 200 "$TMP_DIR/err")"
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
