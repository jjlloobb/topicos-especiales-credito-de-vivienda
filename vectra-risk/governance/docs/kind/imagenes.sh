#!/usr/bin/env bash
# Build y push a `kind-registry` de `governance` y de `model-validation-job`, y el digest real de cada una en el formato del archivo de values
# `vectra-risk-gitops/values/kind/governance.yaml` (T1 de la demo: sin firma, SBOM ni attestation). No toca el cluster ni los values: el digest
# entra por PR (paso 1 de la guia).
#
#   imagenes.sh [--dry-run]    con --dry-run solo imprime lo que haria
set -euo pipefail

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
registro="${REGISTRY_LOCAL:-localhost:5001}"

digests=()
for par in governance:image model-validation-job:image-validation; do
  nombre="${par%%:*}"
  objetivo="${par##*:}"
  if [ "$dry" = 1 ]; then
    echo "dry-run: make -C governance $objetivo; docker push $registro/vectra/$nombre:dev; docker inspect $registro/vectra/$nombre:dev"
    digests+=("sha256:dry-run-$nombre")
    continue
  fi
  make -C "$root/governance" "$objetivo"
  docker push "$registro/vectra/$nombre:dev"
  referencia="$(docker inspect --format '{{index .RepoDigests 0}}' "$registro/vectra/$nombre:dev")"
  digests+=("${referencia##*@}")
done

echo
echo "# vectra-risk-gitops/values/kind/governance.yaml (por PR; despues: uv run python vectra-risk-gitops/generate.py)"
echo "image:"
echo "  digest: ${digests[0]}"
echo "validation:"
echo "  image:"
echo "    digest: ${digests[1]}"
