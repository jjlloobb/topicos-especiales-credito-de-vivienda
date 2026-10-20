#!/usr/bin/env bash
# Problema 3: prepara el escenario. No leas este archivo antes del examen (honor).
set -euo pipefail

command -v kubectl >/dev/null || { echo "ERROR: falta kubectl"; exit 1; }
kubectl get nodes >/dev/null 2>&1 || { echo "ERROR: kubectl no alcanza el clúster (revisa KUBECONFIG)"; exit 1; }

kubectl apply -f - <<'YAML' >/dev/null
apiVersion: v1
kind: Namespace
metadata:
  name: examen3
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: examen3
spec:
  replicas: 1
  selector:
    matchLabels: { app: web }
  template:
    metadata:
      labels: { app: web }
    spec:
      containers:
      - name: nginx
        image: nginx:1.29.5-alpine
        ports: [{ containerPort: 80 }]
---
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: examen3
spec:
  type: NodePort
  selector: { app: web }
  ports:
  - { port: 80, targetPort: 80, nodePort: 30080 }
YAML

kubectl -n examen3 rollout status deployment/web --timeout=120s >/dev/null

# La política se aplica al final, con la app ya sana.
kubectl apply -f - <<'YAML' >/dev/null
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: examen3
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
YAML
echo "Problema 3 preparado. Revisa el namespace examen3."
