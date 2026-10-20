#!/usr/bin/env bash
# Problema 1: prepara el escenario. No leas este archivo antes del examen (honor).
set -euo pipefail

command -v kubectl >/dev/null || { echo "ERROR: falta kubectl"; exit 1; }
command -v docker  >/dev/null || { echo "ERROR: falta docker";  exit 1; }
kubectl get nodes >/dev/null 2>&1 || { echo "ERROR: kubectl no alcanza el clúster (revisa KUBECONFIG)"; exit 1; }

NS=examen1
NOMBRE=vigia
# Siempre en el último nodo worker; si no hay workers, en el control-plane.
NODO=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o jsonpath='{.items[-1:].metadata.name}')
[ -n "$NODO" ] || NODO=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

docker exec -i "$NODO" sh -c "cat > /etc/kubernetes/manifests/${NOMBRE}.yaml" <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${NOMBRE}
  namespace: ${NS}
  labels:
    app: ${NOMBRE}
spec:
  terminationGracePeriodSeconds: 5
  containers:
  - name: vigia
    image: busybox:1.37.0
    command: ["sh", "-c", "while true; do date; sleep 30; done"]
YAML

echo "Problema 1 preparado. Espera unos segundos y revisa el namespace ${NS}."
