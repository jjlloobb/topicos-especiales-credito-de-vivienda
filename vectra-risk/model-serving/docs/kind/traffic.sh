#!/usr/bin/env bash
# Trafico continuo contra `:predict` (escenario 1 del Paso 11 de U6). Cada respuesta debe traer un `model_version_id` de los permitidos.
# Uso: traffic.sh --url URL --payload ARCHIVO --versions V1[,V2] [--duration S] [--interval S] [--out ARCHIVO] [--dry-run]
#   --payload  un `{"instances": [<FeatureVector>]}` valido (sin credenciales ni datos reales; ver la guia, seccion 3).
#   --versions los `model_version_id` aceptados; una respuesta 200 con otro id (o sin id), o con `version_mismatch`, cuenta como desajuste.
# Salida: una linea por solicitud en --out (marca, codigo, version, clase) y un resumen. Codigo de salida: 0 sin desajustes ni errores;
# 1 con algun desajuste; 2 solo con errores de transporte o de estado (503, etc.).
set -euo pipefail

url="" payload="" versions="" duration=60 interval=0.2 out="" dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --url) url="$2"; shift 2 ;;
    --payload) payload="$2"; shift 2 ;;
    --versions) versions="$2"; shift 2 ;;
    --duration) duration="$2"; shift 2 ;;
    --interval) interval="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) echo "argumento desconocido: $1" >&2; exit 64 ;;
  esac
done
[ -n "$url" ] && [ -n "$payload" ] && [ -n "$versions" ] || { echo "faltan --url, --payload o --versions" >&2; exit 64; }
[ -f "$payload" ] || { echo "no existe el payload: $payload" >&2; exit 64; }
if [ "$dry" = 1 ]; then
  echo "dry-run: POST $url con $payload durante ${duration}s cada ${interval}s; versiones aceptadas: $versions"
  exit 0
fi

: "${out:=$(mktemp)}"
: > "$out"
total=0 ok=0 mismatch=0 errors=0
end=$((SECONDS + duration))
while [ "$SECONDS" -lt "$end" ]; do
  body=$(mktemp)
  code=$(curl -s -o "$body" -w '%{http_code}' --max-time 5 -H 'Content-Type: application/json' --data-binary "@$payload" "$url" || true)
  version=$(sed -n 's/.*"model_version_id" *: *"\([^"]*\)".*/\1/p' "$body" | head -n 1)
  class=error
  if [ "$code" = 200 ]; then
    case ",$versions," in *",$version,"*) [ -n "$version" ] && class=ok || class=version_mismatch ;; *) class=version_mismatch ;; esac
  elif grep -q version_mismatch "$body"; then
    class=version_mismatch
  fi
  rm -f "$body"
  printf '%s %s %s %s\n' "$(date -u +%FT%TZ)" "${code:-000}" "${version:--}" "$class" >> "$out"
  total=$((total + 1))
  case "$class" in ok) ok=$((ok + 1)) ;; version_mismatch) mismatch=$((mismatch + 1)) ;; *) errors=$((errors + 1)) ;; esac
  sleep "$interval"
done
echo "total=$total ok=$ok version_mismatch=$mismatch errores=$errors (detalle en $out)"
awk '$4 == "ok" { n[$3]++ } END { for (v in n) print "  " v ": " n[v] }' "$out" | sort
[ "$mismatch" -eq 0 ] || exit 1
[ "$errors" -eq 0 ] || exit 2
