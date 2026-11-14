#!/bin/sh
# Verifica D4 (dashboard.md), un paso por llamada: `dashboard.sh <paso>`. Solo lectura. Salida: 0 esperado, 1 no, 2 no se pudo leer.
# shellcheck source=/dev/null
. "$(dirname "$0")/lib.sh"

case "${1:-}" in
  1)
    # Grafana esta arriba: hay un pod suyo Running en vectra-observability (el presentador entra por port-forward con grafana-admin).
    PHASE="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vectra-observability -l app.kubernetes.io/name=grafana -o jsonpath='{.items[*].status.phase}' 2>/dev/null)" || cannot_read "lectura de pods de Grafana"
    case "$PHASE" in
      *Running*) expected "Grafana esta Running" ;;
      *) not_expected "Grafana no esta Running (${PHASE:-sin pods})" ;;
    esac
    ;;
  2)
    # Las cuatro series de los paneles tienen valor (el dia D + 1, tras la pasada de las 02:30 UTC).
    open_prom
    for EXPR in \
      'vectra:product_north_star_ratio:dedup{period="day", channel="all", outcome="all", model_version_id="all"}' \
      'vectra:product_recommendation_sustained_ratio:dedup{period="30d", channel="all", outcome="all"}' \
      'vectra:product_explanation_view_ratio:dedup{period="7d", channel="all"}' \
      'vectra:product_noise_days_below_floor:dedup'; do
      COUNT="$(prom_count "$EXPR")" || exit 2
      [ "$COUNT" -ge 1 ] || not_expected "sin valor: $EXPR"
    done
    expected "las cuatro series tienen valor"
    ;;
  3)
    # La alerta ProductMetricsStale no esta en firing.
    open_prom
    COUNT="$(prom_count 'ALERTS{alertname="ProductMetricsStale", alertstate="firing"}')" || exit 2
    [ "$COUNT" -eq 0 ] || not_expected "ProductMetricsStale esta en firing"
    expected "ProductMetricsStale no esta en firing"
    ;;
  4)
    # La evidencia dashboard que la CLI ya escribio (seccion u11).
    RESULT="$(evidence_result demo-dashboard.json)" || exit 2
    [ "$RESULT" = "pasa" ] || not_expected "dashboard no paso"
    expected "dashboard pasa"
    ;;
  *)
    say "uso: dashboard.sh <1|2|3|4>" >&2
    exit 2
    ;;
esac
