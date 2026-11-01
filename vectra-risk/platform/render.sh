#!/usr/bin/env bash
# Snapshots de `helm template` por entorno (Paso 16). No toca ningun cluster.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for env in kind staging prod; do
  out="$here/rendered/$env"
  values="$here/../vectra-risk-gitops/envs/$env/values.yaml"
  rm -rf "$out"; mkdir -p "$out"
  helm template namespaces "$here/namespaces" -f "$values" > "$out/namespaces.yaml"
  kind_values=(); if [ "$env" = kind ]; then kind_values=(-f "$here/data/chart/values-kind.yaml"); fi
  helm template data "$here/data/chart" -f "$values" "${kind_values[@]}" > "$out/data.yaml"
  cp "$here/restore-drill/cronjob.yaml" "$out/restore-drill.yaml"
  cp "$here/restore-drill/configmap-$env.yaml" "$out/restore-drill-config.yaml"
  cp "$here/observability/grafana/manifests.yaml" "$out/grafana.yaml"
  cp "$here/observability/grafana/external-secrets.yaml" "$out/grafana-secrets.yaml"
  cp "$here/policies/quotas/generated.yaml" "$out/quotas.yaml"
  if [ "$env" != prod ]; then cp "$here/rbac/verification-operator/k16.yaml" "$out/k16.yaml"; fi
done
