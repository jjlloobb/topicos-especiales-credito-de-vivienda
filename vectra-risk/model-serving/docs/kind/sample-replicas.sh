#!/usr/bin/env bash
# Muestrea las replicas de los Deployment que KServe crea (escenario 2 del Paso 11 de U6): el activo nunca baja de --min (por omision, 2).
# Uso: sample-replicas.sh --namespace NS --deployments D1,D2 [--min 2] [--duration S] [--interval S] [--out ARCHIVO] [--dry-run]
# Solo lee (`kubectl get`). KUBECTL cambia el ejecutable (las pruebas usan un doble). Codigo de salida: 0 si ninguna muestra bajo del minimo.
set -euo pipefail

namespace="" deployments="" min=2 duration=120 interval=2 out="" dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --namespace) namespace="$2"; shift 2 ;;
    --deployments) deployments="$2"; shift 2 ;;
    --min) min="$2"; shift 2 ;;
    --duration) duration="$2"; shift 2 ;;
    --interval) interval="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) echo "argumento desconocido: $1" >&2; exit 64 ;;
  esac
done
[ -n "$namespace" ] && [ -n "$deployments" ] || { echo "faltan --namespace o --deployments" >&2; exit 64; }
kubectl_bin="${KUBECTL:-kubectl}"
if [ "$dry" = 1 ]; then
  echo "dry-run: $kubectl_bin get deployment {$deployments} -n $namespace durante ${duration}s cada ${interval}s; minimo $min"
  exit 0
fi

: "${out:=$(mktemp)}"
: > "$out"
below=0 samples=0 lowest=""
end=$((SECONDS + duration))
IFS=, read -r -a names <<< "$deployments"
while [ "$SECONDS" -lt "$end" ]; do
  for name in "${names[@]}"; do
    read -r desired ready < <("$kubectl_bin" get deployment "$name" -n "$namespace" -o 'jsonpath={.spec.replicas} {.status.readyReplicas}' || true) || true
    desired=${desired:-0} ready=${ready:-0}
    printf '%s %s spec=%s ready=%s\n' "$(date -u +%FT%TZ)" "$name" "$desired" "$ready" >> "$out"
    samples=$((samples + 1))
    low=$(( desired < ready ? desired : ready ))
    if [ -z "$lowest" ] || [ "$low" -lt "$lowest" ]; then lowest=$low; fi
    [ "$low" -ge "$min" ] || below=$((below + 1))
  done
  sleep "$interval"
done
echo "muestras=$samples minimo_observado=${lowest:-0} bajo_el_minimo=$below (minimo exigido $min; detalle en $out)"
[ "$below" -eq 0 ]
