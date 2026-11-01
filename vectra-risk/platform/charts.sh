#!/usr/bin/env bash
# Descarga a `platform/.charts/` (ignorado por Git) los charts upstream de components.yaml,
# para renderizarlos con nuestros values. No toca ningun cluster.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 - "$here/../vectra-risk-gitops/components.yaml" <<'PY' | while read -r name repo chart version; do
import sys, yaml
for c in yaml.safe_load(open(sys.argv[1]))["components"]:
    if "chart" in c and c["repo"].startswith("https://"):
        print(c["name"], c["repo"], c["chart"], c["version"])
PY
  target="$here/.charts/$name"
  [ -d "$target/$chart" ] && continue
  mkdir -p "$target"
  helm pull "$chart" --repo "$repo" --version "$version" --untar --untardir "$target"
done
