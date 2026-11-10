#!/usr/bin/env bash
# Memoria y CPU de `vectra-app` (`kubectl top`), antes y despues de instalar governance (DD-3 b). Escribe a stdout; el operador lo redirige a
# `evidence/kind/memoria.md` (la guia lo indica). Solo lectura.
#
#   memoria.sh [--dry-run] <etiqueta>     p. ej. antes, despues
set -euo pipefail

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
etiqueta="${1:?uso: memoria.sh [--dry-run] <etiqueta>}"
ctx="${CTX:-kind-vectra}"

echo "## $etiqueta ($(date -u +%FT%TZ))"
echo
echo '```text'
if [ "$dry" = 1 ]; then
  echo "dry-run: kubectl --context $ctx top pod -n vectra-app; kubectl --context $ctx top node"
else
  kubectl --context "$ctx" top pod -n vectra-app
  kubectl --context "$ctx" top node
fi
echo '```'
