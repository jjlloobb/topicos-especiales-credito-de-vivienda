#!/bin/sh
# Identidad y acceso del operador (K-27, K-32, K-33, K-34): `identidad.sh`. Solo lectura, con el kubeconfig de administrador de kind.
#  1. K16: `kubectl auth can-i` con el grupo `vectra-verification-operators` para cada recurso que lee un `verify` (esperado `yes`) y para lo que K16 no da (esperado `no`: `vectra-mock`, `vectra-staging`).
#  2. El Job `keycloak-config-cli`: terminado, y sus avisos (el de la politica de contrasenas es esperado; K-27).
#  3. Los **nombres** de las claves de `identity/synthetic-users` en la boveda (nunca los valores): deben estar las de los usuarios de las demos, incluidos analista-2, cro-2 y cumplimiento-2 (K-33).
#     Necesita `VAULT_TOKEN` (en kind, el token de desarrollo) y un `port-forward` al pod de la boveda con ese kubeconfig.
# Salida: 0 todo bien, 1 hallazgos, 2 no se pudo leer. Sin esperas.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

FAIL=0
AS_USER="operador"
AS_GROUP="vectra-verification-operators"

# `check <esperado> <verbo> <recurso> <namespace>`: compara con `kubectl auth can-i`. Exit 1 de can-i significa `no`; cualquier otro fallo es no poder leer.
check() {
  ANSWER="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" auth can-i "$2" "$3" -n "$4" "--as=$AS_USER" "--as-group=$AS_GROUP" 2> "$TMP_DIR/err")"
  RC=$?
  if [ "$RC" -ne 0 ] && [ "$RC" -ne 1 ]; then cannot_read "auth can-i $2 $3 -n $4: $(head -c 200 "$TMP_DIR/err")"; fi
  if [ "$ANSWER" = "$1" ]; then say "OK   K16 $2 $3 en $4: $ANSWER"; else say "FALLA K16 $2 $3 en $4: dio '$ANSWER' y se esperaba '$1' (K-34)"; FAIL=1; fi
}

check yes get pods vectra-app
check yes get pods vectra-edge
check yes get pods vectra-serving
check yes get pods vectra-identity
check yes get pods vectra-data
check yes get pods vectra-observability
check yes get jobs vectra-app
check yes get pods/log vectra-app
check yes create pods/portforward vectra-app
check yes create pods/portforward vectra-observability
check yes get inferenceservices.serving.kserve.io vectra-serving
check no get pods vectra-mock
check no get pods vectra-staging
check no get pods/log vectra-staging
check no get secrets vectra-app
check no get networkpolicies vectra-serving

kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get job keycloak-config-cli -n vectra-identity -o jsonpath='{.status.succeeded}' > "$TMP_DIR/succeeded" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer el Job keycloak-config-cli: $(head -c 200 "$TMP_DIR/err")"
if [ "$(cat "$TMP_DIR/succeeded")" = "1" ]; then say "OK   Job keycloak-config-cli terminado"; else say "FALLA el Job keycloak-config-cli no termino (succeeded=$(cat "$TMP_DIR/succeeded")): resincroniza keycloak (K-27)"; FAIL=1; fi
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" logs job/keycloak-config-cli -n vectra-identity > "$TMP_DIR/config-cli.log" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer el log del Job: $(head -c 200 "$TMP_DIR/err")"
if grep -q "Password policy violation" "$TMP_DIR/config-cli.log"; then say "AVISO el log trae 'Password policy violation ... NOT updated': esperado, config-cli no reaplica contrasenas (K-27)"; fi
ERRORS="$(grep -c -E "(^|[ \[])ERROR([ \]]|:)" "$TMP_DIR/config-cli.log")"
if [ "${ERRORS:-0}" -gt 0 ]; then say "FALLA el log de config-cli trae $ERRORS lineas ERROR"; FAIL=1; else say "OK   el log de config-cli sin lineas ERROR"; fi

[ -n "${VAULT_TOKEN:-}" ] || cannot_read "falta VAULT_TOKEN (en kind, el token de desarrollo de la boveda)"
VAULT_POD="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vault -o name 2> "$TMP_DIR/err" | grep -E '^pod/vault-0$' | head -n 1)"
[ -n "$VAULT_POD" ] || cannot_read "no hay pod vault-0 en el namespace vault: $(head -c 200 "$TMP_DIR/err")"
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" port-forward -n vault --address=127.0.0.1 "$VAULT_POD" :8200 > "$TMP_DIR/vault-pf.log" 2>&1 &
PF_PID=$!
VAULT_PORT=""
TRIES=0
while [ "$TRIES" -lt 50 ]; do
  VAULT_PORT="$(sed -n 's/.*127\.0\.0\.1:\([0-9]*\) ->.*/\1/p' "$TMP_DIR/vault-pf.log" | head -n 1)"
  [ -n "$VAULT_PORT" ] && break
  kill -0 "$PF_PID" 2>/dev/null || cannot_read "el port-forward a la boveda cayo: $(head -c 200 "$TMP_DIR/vault-pf.log")"
  TRIES=$((TRIES + 1))
done
[ -n "$VAULT_PORT" ] || { kill "$PF_PID" 2>/dev/null; cannot_read "el port-forward a la boveda no abrio"; }
python3 - "$VAULT_PORT" <<'PY'
import json, os, sys, urllib.request

request = urllib.request.Request(
    f"http://127.0.0.1:{sys.argv[1]}/v1/secret/data/identity/synthetic-users", headers={"X-Vault-Token": os.environ["VAULT_TOKEN"]}
)
try:
    with urllib.request.urlopen(request, timeout=20) as answer:
        names = set(json.load(answer)["data"]["data"])
except Exception as error:  # noqa: BLE001 - el motivo, sin el cuerpo de la respuesta
    print(f"NO SE PUDO LEER la boveda: {type(error).__name__}", file=sys.stderr)
    sys.exit(2)
wanted = {
    f"SYNTH_{user.upper().replace('-', '_')}_{suffix}"
    for user in ("analista-1", "analista-2", "ingeniero-1", "cro-1", "cro-2", "cumplimiento-1", "cumplimiento-2")
    for suffix in ("PASSWORD", "TOTP_SEED")
}
print(f"identity/synthetic-users: {len(names)} claves (solo nombres)")
missing = sorted(wanted - names)
for name in missing:
    print(f"FALLA falta la clave {name}")
sys.exit(1 if missing else 0)
PY
RC=$?
kill "$PF_PID" 2>/dev/null
[ "$RC" -ne 2 ] || exit 2
[ "$RC" -eq 0 ] || FAIL=1

[ "$FAIL" -eq 0 ] || { say "identidad: HAY HALLAZGOS" >&2; exit 1; }
say "identidad: sin hallazgos"
