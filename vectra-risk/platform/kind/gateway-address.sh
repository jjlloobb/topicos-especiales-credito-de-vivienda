#!/usr/bin/env bash
# Solo lectura: dice si la maquina llega al gateway de kind por el nombre de la demo (U01-T16).
#
# El gateway es un Service LoadBalancer de `cloud-provider-kind`, y su direccion externa cambia cuando Docker reasigna las de la red `kind`
# (por ejemplo al reiniciar la maquina). La maquina llega a el por /etc/hosts con esa direccion. Este guion:
#   1. lee la direccion externa del Service del gateway (`kubectl get`);
#   2. comprueba que responde en el 443 (`curl --resolve`, sin credenciales: solo importa que conteste, no lo que conteste);
#   3. compara con lo que resuelve el nombre en esta maquina.
# Sale 0 si coinciden y responde. Si no, dice que linea hace falta en /etc/hosts y sale distinto de 0. NO escribe ese archivo: es del operador.
#
# Salidas: 0 coincide y responde; 1 el nombre resuelve a otra direccion; 2 contexto que no es de kind; 3 el Service no tiene direccion; 4 no responde.
#
# Variables: VECTRA_KIND_CONTEXT (kind-vectra), VECTRA_GATEWAY_HOST (vectra.localtest.me), VECTRA_GATEWAY_NAMESPACE (vectra-edge),
#            VECTRA_GATEWAY_SERVICE (api-gateway).
set -euo pipefail
context="${VECTRA_KIND_CONTEXT:-kind-vectra}"
host="${VECTRA_GATEWAY_HOST:-vectra.localtest.me}"
namespace="${VECTRA_GATEWAY_NAMESPACE:-vectra-edge}"
service="${VECTRA_GATEWAY_SERVICE:-api-gateway}"

case "$context" in
  kind-*) ;;
  *) echo "Solo se mira un cluster de kind; contexto recibido: $context" >&2; exit 2 ;;
esac

address="$(kubectl --context "$context" get svc "$service" -n "$namespace" -o 'jsonpath={.status.loadBalancer.ingress[0].ip}')"
if [ -z "$address" ]; then
  echo "El Service $namespace/$service no tiene direccion externa. Comprueba que cloud-provider-kind corre (docker ps --filter name=cloud-provider-kind) y mira de nuevo en unos segundos." >&2
  exit 3
fi

code="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 10 --resolve "$host:443:$address" "https://$host/" || true)"
if [ -z "$code" ] || [ "$code" = 000 ]; then
  echo "El gateway no responde en $address:443 (Service $namespace/$service). Revisa que cloud-provider-kind corre y que el Service sigue anunciando esa direccion." >&2
  exit 4
fi

resolved="$(getent hosts "$host" | awk 'NR == 1 { print $1 }' || true)"
if [ "$resolved" = "$address" ]; then
  echo "OK: $host resuelve a $address, la direccion del gateway, y responde (HTTP $code)."
  exit 0
fi
echo "El gateway responde en $address (HTTP $code), pero $host resuelve a ${resolved:-nada} en esta maquina." >&2
echo "Hace falta esta linea en /etc/hosts (la agrega el operador, como administrador; reemplaza la anterior de $host si la hay):" >&2
echo "$address $host" >&2
exit 1
