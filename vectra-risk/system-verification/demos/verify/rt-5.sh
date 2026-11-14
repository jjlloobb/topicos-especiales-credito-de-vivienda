#!/bin/sh
# Verifica D3 (rt-5.md), un paso por llamada: `rt-5.sh <paso>`. Solo lectura. Salida: 0 esperado, 1 no, 2 no se pudo leer.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

RUN_ID="$(run_id)" || exit 2
[ -n "$RUN_ID" ] || cannot_read "el manifiesto no tiene run_id"
JOB="rt5-demo-$RUN_ID"

case "${1:-}" in
  1)
    # Tras el PR de runId y su sync existe el Job rt5-demo-<runId> en vectra-app.
    kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get "job/$JOB" -n vectra-app -o name > "$TMP_DIR/job" 2>/dev/null || not_expected "no existe job/$JOB en vectra-app"
    expected "existe job/$JOB"
    ;;
  2)
    # El Job termino bien: un solo intento (backoffLimit 0) y succeeded=1.
    SUCCEEDED="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get "job/$JOB" -n vectra-app -o jsonpath='{.status.succeeded}' 2>/dev/null)" || cannot_read "lectura de job/$JOB"
    [ "$SUCCEEDED" = "1" ] || not_expected "job/$JOB tiene succeeded=${SUCCEEDED:-vacio}"
    expected "job/$JOB termino bien"
    ;;
  3)
    # El log del Job: el 403 lo dio el proxy de Linkerd (l5d-proxy-error con valor), no la aplicacion.
    POD="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vectra-app -l "job-name=$JOB" -o name 2>/dev/null | head -n 1)"
    [ -n "$POD" ] || cannot_read "no hay pod del job $JOB"
    LOG="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" logs "$POD" -n vectra-app 2>/dev/null)" || cannot_read "lectura del log de $POD"
    printf '%s\n' "$LOG" | grep -q -- '-> 403 l5d-proxy-error: ' || not_expected "el log no trae el 403 con l5d-proxy-error"
    if printf '%s\n' "$LOG" | grep -q 'l5d-proxy-error: None'; then not_expected "el 403 lo dio la aplicacion (l5d-proxy-error: None)"; fi
    expected "el 403 lo dio el proxy"
    ;;
  4)
    # La alerta CoreWriteAttempt (sin for:, ventana de 5 min): se ve en firing los ~5 min siguientes al Job.
    open_prom
    COUNT="$(prom_count 'ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}')" || exit 2
    [ "$COUNT" -ge 1 ] || not_expected "CoreWriteAttempt no esta en firing (pasaron mas de 5 min desde el Job: ensena la evidencia de rt5)"
    expected "CoreWriteAttempt en firing"
    ;;
  5)
    # El proxy del mock denego la escritura: la serie de denegaciones vale 1 o mas; el contador del mock sigue en 0.
    open_prom
    DENY="$(prom_max 'inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}')" || exit 2
    [ -n "$DENY" ] || not_expected "no hay serie inbound_http_authz_deny_total del proxy de vectra-mock"
    python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) >= 1 else 1)' "$DENY" || not_expected "denegaciones: $DENY"
    COUNTER="$(prom_max 'max(vectra_core_write_attempts_total)')" || exit 2
    [ -z "$COUNTER" ] || python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) == 0 else 1)' "$COUNTER" || not_expected "el contador del mock vale $COUNTER"
    expected "el proxy denego y el mock no recibio la escritura"
    ;;
  6)
    # La evidencia de rt5 que la CLI ya escribio.
    RESULT="$(evidence_result RT-5.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "RT-5 no paso"
    RESULT="$(evidence_result demo-rt-5.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "rt-5 no paso"
    expected "RT-5 y rt-5 pasan"
    ;;
  *)
    say "uso: rt-5.sh <1|2|3|4|5|6>" >&2
    exit 2
    ;;
esac
