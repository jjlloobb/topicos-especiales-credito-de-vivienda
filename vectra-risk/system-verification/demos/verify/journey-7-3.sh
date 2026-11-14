#!/bin/sh
# Verifica D1 (journey-7-3.md), un paso por llamada: `journey-7-3.sh <paso>`. Solo lectura (K16 y Prometheus por port-forward). Salida: 0 esperado, 1 no, 2 no se pudo leer.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

case "${1:-}" in
  1)
    # Tras sincronizar el PR de F22 apagado, los pods de vectra-serving siguen vivos: lo que cae es la red hacia el explainer, no los pods.
    PODS="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vectra-serving -o name 2>/dev/null)" || cannot_read "lectura de pods en vectra-serving"
    [ -n "$PODS" ] || not_expected "no hay pods en vectra-serving"
    expected "hay pods en vectra-serving"
    ;;
  2)
    # Con F22 apagado el gauge de casos en fail-closed persistente sube a 1 o mas.
    open_prom
    VALUE="$(prom_max 'max(vectra_cases_failclosed_persistent)')" || exit 2
    [ -n "$VALUE" ] || not_expected "la serie vectra_cases_failclosed_persistent no tiene valor"
    python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) >= 1 else 1)' "$VALUE" || not_expected "vectra_cases_failclosed_persistent vale $VALUE"
    expected "vectra_cases_failclosed_persistent vale $VALUE"
    ;;
  3)
    # La alerta FailClosedPersistente esta en firing (1 min tras el gauge de 30 s).
    open_prom
    COUNT="$(prom_count 'ALERTS{alertname="FailClosedPersistente", alertstate="firing"}')" || exit 2
    [ "$COUNT" -ge 1 ] || not_expected "FailClosedPersistente no esta en firing"
    expected "FailClosedPersistente en firing"
    ;;
  4)
    # Revertido el PR de F22: el gauge vuelve a 0 y la alerta se apaga (puede tardar unos minutos).
    open_prom
    VALUE="$(prom_max 'max(vectra_cases_failclosed_persistent)')" || exit 2
    COUNT="$(prom_count 'ALERTS{alertname="FailClosedPersistente", alertstate="firing"}')" || exit 2
    [ "$COUNT" -eq 0 ] || not_expected "FailClosedPersistente sigue en firing"
    [ -z "$VALUE" ] || python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) == 0 else 1)' "$VALUE" || not_expected "vectra_cases_failclosed_persistent vale $VALUE"
    expected "la alerta se apago"
    ;;
  5)
    # La evidencia de la seccion rt3 que la CLI ya escribio.
    RESULT="$(evidence_result RT-3.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "RT-3 no paso"
    RESULT="$(evidence_result demo-journey-7-3.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "journey-7-3 no paso"
    expected "RT-3 y journey-7-3 pasan"
    ;;
  *)
    say "uso: journey-7-3.sh <1|2|3|4|5>" >&2
    exit 2
    ;;
esac
