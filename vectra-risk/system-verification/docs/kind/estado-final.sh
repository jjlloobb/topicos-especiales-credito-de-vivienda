#!/bin/sh
# El cluster queda como estaba (K-49, K-52, K-61, K-65; BR-U12-10): `estado-final.sh --modelos <archivo|->`. Solo lectura. El estado de los modelos sale de `humo.py modelos` (la API de la consola
# necesita un token); el resto, de `kubectl get` y de Prometheus:
#  - el modelo de referencia `activo` (uno solo) y ninguna version `congelado` (del JSON que da `humo.py modelos`);
#  - ningun `InferenceService` de staging (`vectra-staging`) y el activo presente en `vectra-serving`;
#  - los cinco recursos de F22 otra vez presentes (el PR de reversion fusionado y `network` sincronizada con prune);
#  - informa (no falla) lo que queda: el gauge de fallos persistentes y las alertas en `firing`.
# Salida: 0 como estaba, 1 no, 2 no se pudo leer. Sin esperas.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

[ "${1:-}" = "--modelos" ] && [ -n "${2:-}" ] || { say "uso: estado-final.sh --modelos <archivo|-> (la salida de humo.py modelos)" >&2; exit 2; }
if [ "$2" = "-" ]; then cat > "$TMP_DIR/modelos.json"; else cp "$2" "$TMP_DIR/modelos.json" || cannot_read "no se pudo leer $2"; fi

FAIL=0
python3 - "$TMP_DIR/modelos.json" <<'PY'
import json, sys

try:
    models = json.load(open(sys.argv[1]))
    states = [(m["model_version_id"], m["state"]) for m in models]
except (ValueError, KeyError, TypeError):
    print("NO SE PUDO LEER el JSON de humo.py modelos", file=sys.stderr)
    sys.exit(2)
active = [v for v, s in states if s == "activo"]
frozen = [v for v, s in states if s == "congelado"]
print(f"modelos: {len(states)}; activos {len(active)}; congelados {len(frozen)}")
for v in frozen:
    print(f"FALLA la version {v} sigue congelado (el rollback al modelo de referencia no se hizo)")
if len(active) != 1:
    print(f"FALLA debe haber un solo modelo activo (el de referencia) y hay {len(active)}")
sys.exit(1 if frozen or len(active) != 1 else 0)
PY
RC=$?
[ "$RC" -ne 2 ] || exit 2
[ "$RC" -eq 0 ] || FAIL=1

kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get inferenceservices.serving.kserve.io -n vectra-staging -o name > "$TMP_DIR/staging" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los InferenceService de vectra-staging: $(head -c 200 "$TMP_DIR/err")"
if [ -s "$TMP_DIR/staging" ]; then say "FALLA quedan InferenceService en vectra-staging: $(tr '\n' ' ' < "$TMP_DIR/staging")(retira proxy-staging y rt3-staging)"; FAIL=1; else say "OK   sin InferenceService de staging"; fi
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get inferenceservices.serving.kserve.io -n vectra-serving -o name > "$TMP_DIR/serving" 2> "$TMP_DIR/err" || cannot_read "no se pudo leer los InferenceService de vectra-serving: $(head -c 200 "$TMP_DIR/err")"
if [ -s "$TMP_DIR/serving" ]; then say "OK   InferenceService en vectra-serving: $(tr '\n' ' ' < "$TMP_DIR/serving")"; else say "FALLA no hay InferenceService en vectra-serving"; FAIL=1; fi

# Los cinco recursos de F22 (demos/prs/f22-apagado/README.md): si falta alguno, la reversion no se sincronizo con prune. `f22 <codigo> <recurso>` (el codigo es el de la lectura): solo un `NotFound` es «falta» (1);
# cualquier otro fallo de la lectura (la API caida, un permiso, un tiempo agotado) es «no se pudo leer» (2), no una reversion que no se sincronizo (F-05).
f22() {
  if [ "$1" -ne 0 ] && ! grep -q "NotFound" "$TMP_DIR/err"; then cannot_read "no se pudo leer $2: $(head -c 200 "$TMP_DIR/err")"; fi
  if [ "$1" -eq 0 ] && [ -s "$TMP_DIR/f22" ]; then say "OK   F22: $(head -n 1 "$TMP_DIR/f22")"; else say "FALLA F22: falta $2 (K-49)"; FAIL=1; fi
}
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get networkpolicy allow-f22-explainability-service-to-explainer-egress -n vectra-app -o name > "$TMP_DIR/f22" 2> "$TMP_DIR/err"; f22 "$?" "NetworkPolicy allow-f22-explainability-service-to-explainer-egress"
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get networkpolicy allow-f22-to-explainer-ingress -n vectra-serving -o name > "$TMP_DIR/f22" 2> "$TMP_DIR/err"; f22 "$?" "NetworkPolicy allow-f22-to-explainer-ingress"
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get authorizationpolicy.policy.linkerd.io f22-explainer-8080 -n vectra-serving -o name > "$TMP_DIR/f22" 2> "$TMP_DIR/err"; f22 "$?" "AuthorizationPolicy f22-explainer-8080"
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get meshtlsauthentication.policy.linkerd.io f22-explainer-8080-mtls -n vectra-serving -o name > "$TMP_DIR/f22" 2> "$TMP_DIR/err"; f22 "$?" "MeshTLSAuthentication f22-explainer-8080-mtls"
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get server.policy.linkerd.io explainer-8080 -n vectra-serving -o name > "$TMP_DIR/f22" 2> "$TMP_DIR/err"; f22 "$?" "Server explainer-8080"

open_prom
prom_api /api/v1/query 'query=max(vectra_cases_failclosed_persistent)' > "$TMP_DIR/gauge.json" || exit 2
prom_api /api/v1/query 'query=ALERTS{alertstate="firing"}' > "$TMP_DIR/alerts.json" || exit 2
python3 - "$TMP_DIR/gauge.json" "$TMP_DIR/alerts.json" <<'PY'
import json, sys

gauge = json.load(open(sys.argv[1]))["result"]
print("queda (se anota): casos en fallo persistente (no_disponible de D1) = " + (gauge[0]["value"][1] if gauge else "sin serie"))
names = sorted({s["metric"].get("alertname", "?") for s in json.load(open(sys.argv[2]))["result"]})
print("queda (se anota): alertas en firing = " + (", ".join(names) if names else "ninguna"))
PY

[ "$FAIL" -eq 0 ] || { say "estado final: NO ES COMO ESTABA" >&2; exit 1; }
say "estado final: como estaba"
