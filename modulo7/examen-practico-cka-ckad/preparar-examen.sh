#!/usr/bin/env bash
# Prepara los tres problemas del examen.
set -euo pipefail
cd "$(dirname "$0")"
./preparar-01-pod-estatico.sh
./preparar-02-memoria.sh
./preparar-03-red.sh
echo "Examen listo. Tiempo: 40 minutos. Califica con ./verificar-examen.sh"
