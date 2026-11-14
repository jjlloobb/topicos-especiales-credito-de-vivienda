#!/bin/sh
# Verifica D2 (journey-7-4.md), un paso por llamada: `journey-7-4.sh <paso> [isvc]`. Solo lectura. Salida: 0 esperado, 1 no, 2 no se pudo leer.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

case "${1:-}" in
  1)
    # Tras el PR de promocion y su sync, el InferenceService de la version del proxy (isvc-<8 hex>, segundo argumento) esta listo en vectra-serving.
    [ -n "${2:-}" ] || cannot_read "falta el nombre del InferenceService (isvc-<8 hex>)"
    READY="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get inferenceservices.serving.kserve.io "$2" -n vectra-serving -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" || cannot_read "lectura de inferenceservice $2"
    [ "$READY" = "True" ] || not_expected "$2 no esta Ready"
    expected "$2 esta Ready"
    ;;
  2)
    # El cron de bias corrio bien: la ultima corrida termino con exito y hay marca de tiempo.
    open_prom
    OK="$(prom_max 'min(vectra_bias_last_run_ok)')" || exit 2
    TS="$(prom_max 'max(vectra_bias_last_run_timestamp)')" || exit 2
    [ -n "$OK" ] && [ -n "$TS" ] || not_expected "faltan las series vectra_bias_last_run_ok o vectra_bias_last_run_timestamp"
    python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) == 1 else 1)' "$OK" || not_expected "vectra_bias_last_run_ok vale $OK"
    expected "la ultima corrida de bias termino bien"
    ;;
  3)
    # La evidencia de rt2: el paquete de congelamiento y la reactivacion con la modalidad usada.
    RESULT="$(evidence_result RT-2.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "RT-2 no paso"
    RESULT="$(evidence_result demo-journey-7-4.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "journey-7-4 no paso"
    RESULT="$(evidence_result RT2-LATENCY.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "RT2-LATENCY no paso"
    expected "RT-2, RT2-LATENCY y journey-7-4 pasan"
    ;;
  4)
    # Cerrado D2 (rollback), el modelo de referencia vuelve a servir: su InferenceService (segundo argumento) esta listo.
    [ -n "${2:-}" ] || cannot_read "falta el nombre del InferenceService de referencia (isvc-<8 hex>)"
    READY="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get inferenceservices.serving.kserve.io "$2" -n vectra-serving -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" || cannot_read "lectura de inferenceservice $2"
    [ "$READY" = "True" ] || not_expected "$2 no esta Ready"
    expected "$2 esta Ready"
    ;;
  *)
    say "uso: journey-7-4.sh <1|2|3|4> [isvc]" >&2
    exit 2
    ;;
esac
