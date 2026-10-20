#!/usr/bin/env bash
# Problema 2: prepara el escenario. No leas este archivo antes del examen (honor).
set -euo pipefail

command -v kubectl >/dev/null || { echo "ERROR: falta kubectl"; exit 1; }
kubectl get nodes >/dev/null 2>&1 || { echo "ERROR: kubectl no alcanza el clúster (revisa KUBECONFIG)"; exit 1; }

kubectl apply -f - <<'YAML' >/dev/null
apiVersion: v1
kind: Namespace
metadata:
  name: examen2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reporte
  namespace: examen2
spec:
  replicas: 1
  selector:
    matchLabels: { app: reporte }
  template:
    metadata:
      labels: { app: reporte }
    spec:
      containers:
      - name: reporte
        image: python:3.12-alpine
        env:
        - { name: MB, value: "150" }
        command: ["python", "-c"]
        args:
        - |
          import os, time
          datos = b"x" * (int(os.environ["MB"]) * 1024 * 1024)
          print("reporte listo, memoria reservada:", len(datos) // (1024 * 1024), "MB", flush=True)
          while True:
              time.sleep(5)
        resources:
          requests: { memory: 64Mi, cpu: 50m }
          limits:   { memory: 64Mi }
YAML

echo "Problema 2 preparado. Revisa el namespace examen2."
