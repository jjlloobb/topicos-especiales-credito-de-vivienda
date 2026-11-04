"""Convierte los CRDs del chart `gateway-helm` (Envoy Gateway y Gateway API) a esquemas JSON para `kubeconform`.

U02-T09 (V8, INF-U2-10): `platform/charts.sh` descarga el chart a `platform/.charts/envoy-gateway/gateway-helm/`; su
subchart `crds` trae los CRDs de Envoy Gateway y de Gateway API. Los esquemas van a `identity-edge/.tools/schemas/`
(no se versiona) como `<grupo>/<kind en minusculas>_<version>.json`, el formato de `-schema-location` de `kubeconform`.

Para que `-strict` rechace los campos desconocidos, todo objeto con `properties` recibe `additionalProperties: false`
salvo los que declaran `x-kubernetes-preserve-unknown-fields`. Los demas `x-kubernetes-*` se descartan.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

EDGE = Path(__file__).resolve().parents[1]
ROOT = EDGE.parent
DEFAULT_CHART = ROOT / "platform" / ".charts" / "envoy-gateway" / "gateway-helm"
DEFAULT_ESO_CHART = ROOT / "platform" / ".charts" / "external-secrets" / "external-secrets"
DEFAULT_HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
DEFAULT_OUT = EDGE / ".tools" / "schemas"
_DROP = {"default", "format", "example", "x-kubernetes-validations", "x-kubernetes-list-type", "x-kubernetes-list-map-keys", "x-kubernetes-map-type", "x-kubernetes-embedded-resource"}


def to_json_schema(node: Any) -> Any:
    """El esquema OpenAPI v3 de un CRD, como JSON Schema estricto."""
    if isinstance(node, list):
        return [to_json_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    if node.get("x-kubernetes-int-or-string"):
        rest = {k: to_json_schema(v) for k, v in node.items() if k not in _DROP | {"x-kubernetes-int-or-string", "anyOf", "type"}}
        return {**rest, "oneOf": [{"type": "string"}, {"type": "integer"}]}
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _DROP or key == "x-kubernetes-preserve-unknown-fields" or key == "nullable":
            continue
        if key == "properties":
            out[key] = {name: to_json_schema(sub) for name, sub in value.items()}
        elif key == "additionalProperties" and isinstance(value, dict):
            out[key] = to_json_schema(value)
        else:
            out[key] = to_json_schema(value) if isinstance(value, (dict, list)) else value
    if node.get("nullable") and isinstance(out.get("type"), str):
        out["type"] = [out["type"], "null"]
    if "properties" in out and "additionalProperties" not in out and not node.get("x-kubernetes-preserve-unknown-fields"):
        out["additionalProperties"] = False
    return out


def crd_files(chart: Path) -> list[Path]:
    return sorted((chart / "charts" / "crds" / "crds").rglob("*.yaml"))


def eso_crds(chart: Path, helm: Path) -> list[dict[str, Any]]:
    """Los CRDs de External Secrets: el chart los trae como plantillas, asi que se renderizan con `helm template`."""
    run = subprocess.run(  # noqa: S603 - helm fijo de platform/.tools
        [str(helm), "template", "eso", str(chart), "--set", "installCRDs=true", "--show-only", "templates/crds/externalsecret.yaml"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if run.returncode != 0:
        raise SystemExit(f"crd_schemas: helm template de {chart} fallo: {run.stderr.strip()}")
    return [d for d in yaml.safe_load_all(run.stdout) if d]


def convert(chart: Path, out: Path, eso_chart: Path | None = None, helm: Path = DEFAULT_HELM) -> list[Path]:
    """Escribe un esquema por version de cada CRD. Devuelve los archivos escritos.

    Con `eso_chart` (el chart de External Secrets de `components.yaml`, que baja `charts.sh`) agrega el `ExternalSecret`
    que genera F09.
    """
    written = []
    docs = [d for path in crd_files(chart) for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    if eso_chart is not None:
        docs += eso_crds(eso_chart, helm)
    for doc in docs:
        if doc.get("kind") != "CustomResourceDefinition":
            continue
        group, kind = doc["spec"]["group"], doc["spec"]["names"]["kind"]
        for version in doc["spec"]["versions"]:
            schema = to_json_schema(version["schema"]["openAPIV3Schema"])
            target = out / group / f"{kind.lower()}_{version['name']}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            written.append(target)
    if not written:
        raise SystemExit(f"crd_schemas: {chart} no trae CRDs: corre platform/charts.sh")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CRDs de gateway-helm -> esquemas JSON para kubeconform")
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--eso-chart", type=Path, default=DEFAULT_ESO_CHART)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    written = convert(args.chart, args.out, args.eso_chart)
    print(f"crd_schemas: {len(written)} esquemas en {args.out}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
