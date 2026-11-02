#!/usr/bin/env bash
# Siembra Vault dev de kind y crea el Secret `vault-token` que lee ESO (INF-U1-10). Lo corre un operador; nunca CI.
#
#   seed-vault.sh                sembrar: conserva lo que exista y genera el resto al azar. Se puede repetir.
#   seed-vault.sh grafana-token  crear la cuenta de servicio de Grafana y guardar su token (F110). Con Grafana arriba.
#
# Vault dev guarda todo en memoria: si se reinicia hay que sembrar de nuevo, y las claves cambian (install.md, "Vault
# reiniciado"). Requiere kubectl, helm y uv. Solo escribe en el contexto de kind indicado.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
context="${VECTRA_KIND_CONTEXT:-kind-vectra}"
token="${VAULT_DEV_TOKEN:-root}" # server.dev.devRootToken de platform/operators/vault-kind.yaml

case "$context" in
  kind-*) ;;
  *) echo "Solo se siembra un cluster de kind; contexto recibido: $context" >&2; exit 2 ;;
esac
kube() { kubectl --context "$context" "$@"; }

seed() {
  kube wait -n vault pod/vault-0 --for=condition=Ready --timeout=180s
  (cd "$here/../.." && uv run python platform/kind/vault_paths.py seed "$context" "$token")
  kube create secret generic vault-token -n external-secrets --from-literal=token="$token" --dry-run=client -o yaml | kube apply -f -
  if kube get crd externalsecrets.external-secrets.io >/dev/null 2>&1; then
    kube annotate externalsecrets.external-secrets.io --all -A "force-sync=$(date +%s)" --overwrite
  fi
}

grafana_token() {
  local namespace=vectra-observability port=13000 password url id body key
  password="$(kube get secret grafana-admin -n "$namespace" -o 'jsonpath={.data.admin-password}' | base64 -d)"
  # exec: que $! sea kubectl y no el subshell de kube(), o el kill del trap no llega al port-forward.
  (exec kubectl --context "$context" port-forward -n "$namespace" svc/kube-prometheus-stack-grafana "$port:80" >/dev/null) &
  forward=$!
  trap 'kill "$forward" 2>/dev/null || true' EXIT
  url="http://127.0.0.1:$port"
  until curl -fsS -o /dev/null "$url/api/health"; do sleep 1; done
  api() { curl -fsS -K <(printf 'user = "admin:%s"\n' "$password") -H 'Content-Type: application/json' "$@"; }
  id="$(api "$url/api/serviceaccounts/search?query=folder-permissions" | python3 -c '
import json, sys
accounts = [a["id"] for a in json.load(sys.stdin)["serviceAccounts"] if a["name"] == "folder-permissions"]
print(accounts[0] if accounts else "")')"
  if [ -z "$id" ]; then
    id="$(api -X POST "$url/api/serviceaccounts" -d '{"name":"folder-permissions","role":"Admin"}' | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')"
  fi
  body="{\"name\":\"job-$(date +%s)\"}"
  key="$(api -X POST "$url/api/serviceaccounts/$id/tokens" -d "$body" | python3 -c 'import json, sys; print(json.load(sys.stdin)["key"])')"
  printf '{"token":"%s"}' "$key" | kube exec -i -n vault vault-0 -- env "VAULT_TOKEN=$token" vault kv put secret/grafana/folder-permissions -
  # El ExternalSecret llega con grafana-config, despues de este paso; al crearse ya lee el token.
  if kube get externalsecret grafana-folder-permissions-token -n "$namespace" >/dev/null 2>&1; then
    kube annotate externalsecret grafana-folder-permissions-token -n "$namespace" "force-sync=$(date +%s)" --overwrite
  fi
}

case "${1:-seed}" in
  seed) seed ;;
  grafana-token) grafana_token ;;
  *) echo "Uso: seed-vault.sh [seed|grafana-token]" >&2; exit 2 ;;
esac
