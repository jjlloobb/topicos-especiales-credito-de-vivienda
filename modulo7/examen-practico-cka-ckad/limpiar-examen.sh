#!/usr/bin/env bash
# Deja el clúster sin rastro del examen. Seguro de repetir.
set -euo pipefail
command -v docker >/dev/null || { echo "ERROR: falta docker"; exit 1; }

for nodo in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
  docker exec "$nodo" rm -f /etc/kubernetes/manifests/vigia.yaml
done
kubectl delete namespace examen1 examen2 examen3 --ignore-not-found --wait=true >/dev/null
echo "Examen limpiado."
