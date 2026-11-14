#!/bin/sh
POD=$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get pods -n vectra-observability -l app.kubernetes.io/name=prometheus -o name | head -1)
kubectl --context "${KUBE_CONTEXT:-kind-vectra}" port-forward "$POD" 9090 &
