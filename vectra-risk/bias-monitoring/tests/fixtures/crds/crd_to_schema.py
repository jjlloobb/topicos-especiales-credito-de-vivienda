"""Convierte un CRD a un esquema JSON para `kubeconform -strict` (fixtures de U09-T04, CA-2).

Fuentes (las versiones de `vectra-risk-gitops/components.yaml`; los SHA-256 estan en la bitacora de U09-T04):
- `ExternalSecret` v1: chart `external-secrets` 2.14.0, `helm template ... --set installCRDs=true --show-only templates/crds/externalsecret.yaml`.
- `ServiceMonitor` v1: chart `prometheus-operator-crds` 32.0.2 (CRD de prometheus-operator v0.94.2),
  `helm template ... --set servicemonitors.enabled=true --show-only charts/crds/templates/crd-servicemonitors.yaml`.
Uso: `python crd_to_schema.py <crd.yaml> <version> <salida.json>` (kubeconform busca el kind en minusculas). Quita `description`, `default`,
`format`, `example` y los `x-kubernetes-*` (salvo int-or-string y preserve-unknown-fields) y cierra con `additionalProperties: false`
todo objeto con `properties`.
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

DROP = {
    "description",
    "default",
    "format",
    "example",
    "x-kubernetes-validations",
    "x-kubernetes-list-type",
    "x-kubernetes-list-map-keys",
    "x-kubernetes-map-type",
    "x-kubernetes-embedded-resource",
    "nullable",
}


def convert(node: Any) -> Any:
    if isinstance(node, list):
        return [convert(x) for x in node]
    if not isinstance(node, dict):
        return node
    if node.get("x-kubernetes-int-or-string"):
        rest = {
            k: convert(v)
            for k, v in node.items()
            if k not in DROP | {"x-kubernetes-int-or-string", "anyOf", "type", "pattern"}
        }
        return {**rest, "oneOf": [{"type": "string"}, {"type": "integer"}]}
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in DROP or key == "x-kubernetes-preserve-unknown-fields":
            continue
        if key == "properties":
            out[key] = {name: convert(sub) for name, sub in value.items()}
        else:
            out[key] = convert(value) if isinstance(value, (dict, list)) else value
    if node.get("nullable") and isinstance(out.get("type"), str):
        out["type"] = [out["type"], "null"]
    if (
        "properties" in out
        and "additionalProperties" not in out
        and not node.get("x-kubernetes-preserve-unknown-fields")
    ):
        out["additionalProperties"] = False
    return out


def main() -> None:
    crd = next(d for d in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")) if d)
    version = next(v for v in crd["spec"]["versions"] if v["name"] == sys.argv[2])
    schema = convert(version["schema"]["openAPIV3Schema"])
    Path(sys.argv[3]).write_text(
        json.dumps(schema, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
