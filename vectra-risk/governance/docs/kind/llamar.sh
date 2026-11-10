#!/usr/bin/env bash
# Llama a governance-service desde un pod efimero de `vectra-app` con la identidad `console-bff` (la unica que la malla admite para el
# camino `console`; el BFF de U10 todavia no existe). Los nombres internos del cluster no resuelven fuera de el.
#
#   token.sh cro-2 | llamar.sh [--dry-run] <pod> <METODO> <ruta>
#   { token.sh ingeniero-1; cat cuerpo.json; } | llamar.sh <pod> POST /v1/models
#
# stdin: la primera linea es el token Bearer; el resto, el cuerpo (opcional). El token entra al pod por stdin (`kubectl run -i`): no hay
# Secret ni variable ni argumento de proceso, asi que no queda en etcd (Kyverno `disallow-plain-secrets`) ni en `ps`.
# El pod cumple la admision de U1 (digest, no root, raiz de solo lectura, recursos, prioridad, criticidad) y se borra al terminar (`--rm`).
# Sale 0 si la respuesta es 2xx; imprime `<estado> <cuerpo>`.
#
# La suma de `--override-type=strategic` es necesaria: el valor por omision (`merge`) reemplaza la lista de contenedores y pierde el comando.
# --dry-run: imprime el manifiesto del Pod (`kubectl run --dry-run=client -o yaml`, sin servidor) para correr `kyverno apply` sobre el.
set -euo pipefail

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
pod="${1:?uso: llamar.sh [--dry-run] <pod> <METODO> <ruta>}"
metodo="${2:?falta el metodo}"
ruta="${3:?falta la ruta}"
ctx="${CTX:-kind-vectra}"
registro="${REGISTRY_LOCAL:-localhost:5001}"

if [ "$dry" = 1 ]; then
  digest="${DIGEST:-sha256:0000000000000000000000000000000000000000000000000000000000000002}"
else
  # El digest publicado en `kind-registry` (imagenes.sh); Kyverno exige digest en `vectra-app`.
  digest="${DIGEST:-$(docker inspect --format '{{index .RepoDigests 0}}' "$registro/vectra/governance:dev" | sed 's/^.*@//')}"
fi
imagen="kind-registry:5000/vectra/governance@$digest"

read -r -d '' cliente <<'PY' || true
import sys, urllib.request, urllib.error
metodo, ruta = sys.argv[1], sys.argv[2]
token, _, cuerpo = sys.stdin.buffer.read().partition(b"\n")  # una sola lectura: readline() + buffer.read() pierde el cuerpo
token = token.decode().strip()
req = urllib.request.Request("http://governance-service.vectra-app.svc.cluster.local:8080" + ruta, data=None if metodo == "GET" else cuerpo, method=metodo)
req.add_header("Authorization", "Bearer " + token)
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
    sys.exit(1)
PY

printf -v overrides '%s' '{"metadata":{"labels":{"app.kubernetes.io/name":"console-bff","vectra.io/criticality":"medium"},"annotations":{"config.alpha.linkerd.io/proxy-enable-native-sidecar":"true"}},"spec":{"serviceAccountName":"console-bff","priorityClassName":"vectra-low","securityContext":{"runAsNonRoot":true,"runAsUser":65532,"runAsGroup":65532,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"'"$pod"'","image":"'"$imagen"'","securityContext":{"allowPrivilegeEscalation":false,"readOnlyRootFilesystem":true,"capabilities":{"drop":["ALL"]}},"resources":{"requests":{"cpu":"50m","memory":"64Mi"},"limits":{"cpu":"200m","memory":"128Mi"}}}]}}'

if [ "$dry" = 1 ]; then
  exec kubectl --context "$ctx" -n vectra-app run "$pod" --image="$imagen" --restart=Never --override-type=strategic --overrides="$overrides" --dry-run=client -o yaml --command -- python -c "$cliente" "$metodo" "$ruta"
fi
exec kubectl --context "$ctx" -n vectra-app run "$pod" --image="$imagen" --restart=Never -i --rm --quiet --override-type=strategic --overrides="$overrides" --command -- python -c "$cliente" "$metodo" "$ruta"
