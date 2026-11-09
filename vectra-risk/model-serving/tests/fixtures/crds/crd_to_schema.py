"""Convierte el CRD de `InferenceService` de KServe a un esquema JSON para `kubeconform -strict` (fixture de U06-T02, CA-1).

Fuente: https://raw.githubusercontent.com/kserve/kserve/v0.21.0/config/crd/full/serving.kserve.io_inferenceservices.yaml
(KServe v0.21.0, la version de `vectra-risk-gitops/components.yaml`; SHA-256 del YAML en la bitacora de U06-T02).
Uso: `python crd_to_schema.py <crd.yaml> inferenceservice.json` (kubeconform busca el kind en minusculas). Quita `description`, `default`, `format`, `example` y los
`x-kubernetes-*` (salvo int-or-string y preserve-unknown-fields) y cierra con `additionalProperties: false` todo objeto con `properties`.
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
    crd = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
    version = next(v for v in crd["spec"]["versions"] if v["name"] == "v1beta1")
    schema = convert(version["schema"]["openAPIV3Schema"])
    Path(sys.argv[2]).write_text(
        json.dumps(schema, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
