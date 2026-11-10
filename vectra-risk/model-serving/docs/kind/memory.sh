#!/usr/bin/env bash
# Memoria de los pods de U6 con `kubectl top` (punto 6 del Paso 11): una fotografia por llamada (antes, durante, despues de la promocion).
# Uso: memory.sh --namespace NS --label antes|durante|despues [--budget-mib N] [--out ARCHIVO] [--dry-run]
# --budget-mib es lo pedido (requests) por los pods de U6 en esa fotografia: lo que el presupuesto de test_kind_profile.py asume
# (256 MiB + 20 MiB de proxy por pod). `kubectl top` mide uso real, no requests: debe quedar por debajo.
# Solo lee. KUBECTL cambia el ejecutable. Codigo de salida: 0 si el uso total no pasa de --budget-mib (o si no se dio).
set -euo pipefail

namespace="" label="" budget="" out="" dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --namespace) namespace="$2"; shift 2 ;;
    --label) label="$2"; shift 2 ;;
    --budget-mib) budget="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) echo "argumento desconocido: $1" >&2; exit 64 ;;
  esac
done
[ -n "$namespace" ] && [ -n "$label" ] || { echo "faltan --namespace o --label" >&2; exit 64; }
kubectl_bin="${KUBECTL:-kubectl}"
if [ "$dry" = 1 ]; then
  echo "dry-run: $kubectl_bin top pods -n $namespace ($label), presupuesto ${budget:-sin dato} MiB"
  exit 0
fi

: "${out:=/dev/stdout}"
table=$("$kubectl_bin" top pods -n "$namespace" --no-headers)
total=$(printf '%s\n' "$table" | awk '{ gsub(/Mi/, "", $3); sum += $3 } END { print sum + 0 }')
pods=$(printf '%s\n' "$table" | grep -c . || true)
{
  echo "## $label ($(date -u +%FT%TZ))"
  printf '%s\n' "$table"
  echo "pods=$pods uso_total_mib=$total presupuesto_mib=${budget:--}"
} >> "$out"
[ -z "$budget" ] || [ "$total" -le "$budget" ]
