#!/usr/bin/env bash
# Operador (U01-T17): el kubeconfig de solo lectura con el que corren los agentes del loop.
#
#   readonly-kubeconfig.sh write [ruta]   lee el token y la CA de la ServiceAccount `vectra-readonly-agent` y escribe un kubeconfig
#   readonly-kubeconfig.sh check [ruta]   comprueba con `kubectl auth can-i` que esa identidad lee y no escribe ni lee un Secret
#
# `ruta` es por omision ~/.kube/kind-vectra-readonly. El archivo tiene UN solo contexto, `kind-vectra` (el nombre que llevan escrito los guiones y las
# pruebas del repositorio): con el en KUBECONFIG, `kubectl --context kind-vectra ...` resuelve a esta identidad. Se escribe 0600 y FUERA del repositorio.
#
# `write` usa el kubeconfig de administrador (el de siempre: KUBECONFIG o ~/.kube/config) SOLO para dos lecturas: `kubectl get secret
# vectra-readonly-agent-token -n argocd` (el token y la CA; no crea tokens) y `kubectl config view --minify` (la URL del API, un archivo local). Nunca imprime el token.
# `check` solo ejecuta `kubectl auth can-i` y `kubectl config get-contexts`: no escribe nada en el cluster.
#
# Salidas. write: 0 escrito; 2 se niega (contexto que no es kind-*, ruta dentro del repositorio, el kubeconfig de administrador o un archivo que este guion no escribio, uso); 4 el Secret aun no tiene token;
# 5 kubectl fallo. check: 0 toda la tabla como se espera; 1 alguna fila distinta; 2 el archivo no existe, no es 0600 o no tiene un solo contexto; 3 alguna fila sin respuesta.
#
# Variables: VECTRA_KIND_CONTEXT (kind-vectra), VECTRA_READONLY_NAMESPACE (argocd), VECTRA_READONLY_SECRET (vectra-readonly-agent-token).
set -euo pipefail
set -f # los `*` de la tabla son literales

context="${VECTRA_KIND_CONTEXT:-kind-vectra}"
namespace="${VECTRA_READONLY_NAMESPACE:-argocd}"
secret="${VECTRA_READONLY_SECRET:-vectra-readonly-agent-token}"
user="vectra-readonly-agent"
temporary="" # global: el trap EXIT corre cuando la funcion ya termino
MARKER="# escrito por platform/kind/readonly-kubeconfig.sh (U01-T17); se regenera con write"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/../../.." && pwd -P)"

usage() {
  echo "Uso: $0 write [ruta] | check [ruta]   (ruta por omision: ~/.kube/kind-vectra-readonly)" >&2
  exit 2
}

[ $# -ge 1 ] && [ $# -le 2 ] || usage
command_name="$1"
default_path="${HOME:-/nonexistent}/.kube/kind-vectra-readonly"
target="${2:-$default_path}"
absolute="$(realpath -m -- "$target")"

case "$context" in
  kind-*) ;;
  *) echo "Solo se trabaja con un cluster de kind; contexto recibido: $context" >&2; exit 2 ;;
esac

write_kubeconfig() {
  case "$absolute/" in
    "$repo_root"/*) echo "Se niega a escribir dentro del repositorio ($absolute): un kubeconfig lleva un token y no se versiona. Usa una ruta fuera de $repo_root." >&2; exit 2 ;;
  esac
  local server token_b64 ca_b64 token admin_path
  # El kubeconfig de administrador (~/.kube/config y cada archivo de KUBECONFIG al invocar) no se sobrescribe, ni cualquier archivo que este guion no haya escrito:
  # los suyos llevan MARKER en la primera linea.
  for admin_path in "${HOME:-/nonexistent}/.kube/config" ${KUBECONFIG:+${KUBECONFIG//:/ }}; do
    if [ "$(realpath -m -- "$admin_path")" = "$absolute" ]; then
      echo "Se niega a escribir sobre $absolute: es un kubeconfig de administrador (~/.kube/config o un archivo de KUBECONFIG)." >&2; exit 2
    fi
  done
  if [ -e "$absolute" ] && [ "$(head -n 1 -- "$absolute" 2>/dev/null)" != "$MARKER" ]; then
    echo "Se niega a sobrescribir $absolute: ya existe y no lo escribio este guion (no empieza por '$MARKER'). Usa otra ruta o borralo tu." >&2; exit 2
  fi
  if ! server="$(kubectl --context "$context" config view --minify --raw -o 'jsonpath={.clusters[0].cluster.server}')"; then
    echo "No se pudo leer la URL del API del contexto $context (kubectl config view fallo, arriba el motivo)." >&2; exit 5
  fi
  if ! token_b64="$(kubectl --context "$context" get secret "$secret" -n "$namespace" -o 'jsonpath={.data.token}')" \
    || ! ca_b64="$(kubectl --context "$context" get secret "$secret" -n "$namespace" -o 'jsonpath={.data.ca\.crt}')"; then
    echo "No se pudo leer el Secret $namespace/$secret con el contexto $context (arriba el motivo). Se corre con el kubeconfig de administrador, no con el de solo lectura." >&2; exit 5
  fi
  if [ -z "$server" ] || [ -z "$token_b64" ] || [ -z "$ca_b64" ]; then
    echo "El Secret $namespace/$secret aun no tiene token o CA (o el contexto no tiene URL). Comprueba que la Application readonly-agent-rbac-kind sincronizo y espera unos segundos." >&2; exit 4
  fi
  token="$(printf '%s' "$token_b64" | base64 -d)"
  mkdir -p -- "$(dirname -- "$absolute")"
  temporary="$(umask 077 && mktemp -- "$absolute.XXXXXX")"
  trap '[ -z "$temporary" ] || rm -f -- "$temporary"' EXIT # el temporal lleva el token: no queda si algo falla o se corta antes del mv
  {
    printf '%s\n' "$MARKER"
    printf 'apiVersion: v1\nkind: Config\n'
    printf 'clusters:\n- name: %s\n  cluster:\n    server: %s\n    certificate-authority-data: %s\n' "$context" "$server" "$ca_b64"
    printf 'users:\n- name: %s\n  user:\n    token: %s\n' "$user" "$token"
    printf 'contexts:\n- name: %s\n  context:\n    cluster: %s\n    user: %s\n' "$context" "$context" "$user"
    printf 'current-context: %s\n' "$context"
  } > "$temporary"
  chmod 600 -- "$temporary"
  mv -f -- "$temporary" "$absolute"
  echo "Escrito $absolute (0600), un solo contexto: $context, identidad $user. El token no se imprime."
  echo "Uso: KUBECONFIG=$absolute kubectl --context $context get pods -A    y despues: $0 check"
}

# esperado|verbo|recurso. La tabla minima esta fijada por una prueba: quitar una fila de «no» la hace fallar.
# Un subrecurso se escribe `recurso/subrecurso` (asi se lee y se imprime), pero a kubectl se le pregunta con `--subresource`: `can-i get pods/proxy` es
# TIPO/NOMBRE (el pod que se llama `proxy`), no el subrecurso.
ROWS=(
  "yes|get|pods"
  "yes|list|deployments"
  "yes|get|pods/log"
  "yes|list|applications.argoproj.io"
  "yes|list|externalsecrets.external-secrets.io"
  "no|get|secrets"
  "no|list|secrets"
  "no|delete|deployments"
  "no|delete|pods"
  "no|delete|*"
  "no|create|pods"
  "no|create|deployments"
  "no|patch|deployments"
  "no|update|deployments"
  "no|create|pods/exec"
  "no|create|pods/portforward"
  "no|create|pods/attach"
  "no|impersonate|users"
  "no|get|nodes/proxy"
  "no|get|pods/proxy"
  "no|get|services/proxy"
  "no|get|nodes/log"
  "no|create|serviceaccounts/token"
  "no|escalate|clusterroles"
  "no|bind|clusterroles"
)
SCOPES=("vectra-app" "vectra-edge" "vectra-data" "cluster")
CLUSTER_ROWS=("yes|get|nodes")
# Recursos de ambito de cluster (sin namespace): sus filas solo se preguntan en el ambito `cluster`; en un namespace kubectl avisa (`resource 'nodes' is not namespace scoped`) y la respuesta no dice nada nuevo.
CLUSTER_SCOPED=("nodes" "clusterroles")

check_kubeconfig() {
  if [ ! -f "$absolute" ]; then
    echo "No existe $absolute: corre primero '$0 write'." >&2; exit 2
  fi
  local mode contexts
  mode="$(stat -c '%a' -- "$absolute")"
  if [ "$mode" != "600" ]; then
    echo "$absolute tiene permisos $mode y lleva un token: debe ser 600 (chmod 600 $absolute)." >&2; exit 2
  fi
  contexts="$(kubectl --kubeconfig "$absolute" config get-contexts -o name)"
  if [ "$contexts" != "$context" ]; then
    echo "$absolute debe tener un solo contexto, $context; tiene: $(echo "$contexts" | tr '\n' ' ')" >&2; exit 2
  fi
  local failures=0 unanswered=0 total=0 row expected verb resource scope answer flag status
  printf '%-8s %-9s %-14s %-12s %-44s %s\n' "esperado" "obtenido" "ambito" "verbo" "recurso" "fila"
  ask() { # esperado verbo recurso ambito
    expected="$1" verb="$2" resource="$3" scope="$4"
    local base="${resource%%/*}" sub="" subflag=()
    if [ "$base" != "$resource" ]; then sub="${resource#*/}"; subflag=("--subresource=$sub"); fi
    if [ "$scope" = cluster ]; then flag="-A"; else flag="-n $scope"; fi
    # shellcheck disable=SC2086
    answer="$(kubectl --kubeconfig "$absolute" --context "$context" auth can-i "$verb" "$base" "${subflag[@]}" $flag 2>/dev/null || true)"
    answer="${answer%%[[:space:]]*}" # `no - <motivo>` (el SAR trae `reason`) sigue siendo un no: solo cuenta la primera palabra
    answer="${answer:0:8}"
    total=$((total + 1))
    if [ "$answer" != yes ] && [ "$answer" != no ]; then
      status="SIN RESPUESTA"; unanswered=$((unanswered + 1))
    elif [ "$answer" = "$expected" ]; then
      status="ok"
    else
      status="FALLA"; failures=$((failures + 1))
    fi
    printf '%-8s %-9s %-14s %-12s %-44s %s\n' "$expected" "${answer:--}" "$scope" "$verb" "$resource" "$status"
    if [ "$status" != ok ]; then echo "  -> $status: can-i $verb $resource ($scope): se esperaba $expected y respondio ${answer:-nada}" >&2; fi
  }
  for scope in "${SCOPES[@]}"; do
    for row in "${ROWS[@]}"; do
      IFS='|' read -r expected verb resource <<< "$row"
      if [ "$scope" != cluster ] && [[ " ${CLUSTER_SCOPED[*]} " == *" ${resource%%/*} "* ]]; then continue; fi
      ask "$expected" "$verb" "$resource" "$scope"
    done
  done
  for row in "${CLUSTER_ROWS[@]}"; do
    IFS='|' read -r expected verb resource <<< "$row"
    ask "$expected" "$verb" "$resource" cluster
  done
  echo "Filas: $total; distintas de lo esperado: $failures; sin respuesta: $unanswered."
  if [ "$failures" -gt 0 ]; then echo "La identidad NO es de solo lectura (o no es la esperada): no la uses." >&2; exit 1; fi
  if [ "$unanswered" -gt 0 ]; then echo "Alguna fila no obtuvo respuesta (kubectl fallo o el API no contesta)." >&2; exit 3; fi
  echo "OK: la identidad lee y no escribe ni lee un Secret, en vectra-app, vectra-edge, vectra-data y a nivel de cluster."
}

case "$command_name" in
  write) write_kubeconfig ;;
  check) check_kubeconfig ;;
  *) usage ;;
esac
