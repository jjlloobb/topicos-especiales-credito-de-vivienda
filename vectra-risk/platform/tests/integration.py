#!/usr/bin/env python3
"""Renderiza todo lo que se instalaria en un entorno: charts upstream, charts propios y manifiestos.

`--out DIR` escribe un YAML por componente, con su namespace, para pasarlo a `kyverno apply`.
`--chart RUTA --namespace NS --out DIR` hace lo mismo con el chart de una unidad.
"""

import argparse
import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import yaml

# Algunos CRDs usan `=` como valor de enum, y YAML 1.1 lo toma por una etiqueta especial.
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node))

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
CHARTS = ROOT / "platform/.charts"
Doc = dict[str, Any]
CONFIG = yaml.safe_load((ROOT / "vectra-risk-gitops/components.yaml").read_text(encoding="utf-8"))
#: Lo que se pasa a helm solo para poder renderizar sin secretos ni el ancla, que se resuelven en el cluster.
RENDER_ONLY = {"linkerd-control-plane": ["--set-string", "identityTrustAnchorsPEM=x"]}


def is_chart(component: Doc) -> bool:
    return "chart" in component and str(component["repo"]).startswith("https://")


def helm(name: str, chart: Path, namespace: str, values: list[Path], *extra: str) -> list[Doc]:
    command = ["helm", "template", name, str(chart), "--namespace", namespace, "--skip-tests", "--include-crds"]
    for path in values:
        command += ["-f", str(path)]
    output = subprocess.run([*command, *extra], check=True, capture_output=True, text=True).stdout
    documents = [admitted(without_nulls(d)) for d in yaml.safe_load_all(output) if d]
    for document in documents:
        document.setdefault("metadata", {})
        if document["kind"] not in CLUSTER_SCOPED:
            document["metadata"].setdefault("namespace", namespace)
    return documents


CLUSTER_SCOPED = {
    "Namespace", "CustomResourceDefinition", "ClusterRole", "ClusterRoleBinding", "PriorityClass", "ClusterPolicy",
    "ClusterSecretStore", "ClusterIssuer", "ValidatingWebhookConfiguration", "MutatingWebhookConfiguration",
    "Bundle", "GatewayClass", "APIService", "ClusterExternalSecret", "ClusterPushSecret", "ClusterGenerator",
}  # fmt: skip


def without_nulls(value: Any) -> Any:
    """Como la API de Kubernetes, ignora las claves nulas que dejan las plantillas (`volumes:` vacio)."""
    if isinstance(value, dict):
        return {k: without_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [without_nulls(v) for v in value]
    return value


#: Lo que `platform/policies/kyverno/add-priority-to-minio-job.yaml` agrega al admitir: el chart no lo permite.
MINIO_JOB_PRIORITY = "vectra-normal"


def admitted(document: Doc) -> Doc:
    if document["kind"] == "Job" and document["metadata"].get("name") == "minio-post-job":
        document["spec"]["template"]["spec"].setdefault("priorityClassName", MINIO_JOB_PRIORITY)
    return document


def manifests(path: Path) -> list[Doc]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def directory_docs(component: Doc, env: str) -> list[Doc]:
    folder = ROOT / component["path"].replace("{env}", env)
    include = component.get("include", "").replace("{env}", env).strip("{}").split(",") if "include" in component else None
    exclude = component.get("exclude", "").strip("{}").split(",") if "exclude" in component else []
    documents: list[Doc] = []
    for path in sorted(folder.glob("*.yaml")):
        if path.name == "kustomization.yaml" or path.name in exclude or (include and path.name not in include):
            continue
        documents += manifests(path)
    return documents


@cache
def render_env(env: str) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    result: list[tuple[str, tuple[Any, ...]]] = []
    for component in CONFIG["components"]:
        if env not in component.get("envs", ("kind", "staging", "prod")):
            continue
        name = component["name"]
        if is_chart(component):
            files = [ROOT / f for f in component.get("values", [])]
            if env == "kind":
                files += [ROOT / f for f in component.get("kind_values", [])]
            documents = helm(name, CHARTS / name / component["chart"], component["namespace"], files, *RENDER_ONLY.get(name, []))
        elif "chart" in component:
            documents = []  # OCI: fuera de esta prueba
        elif component.get("env_values"):
            values = ROOT / f"vectra-risk-gitops/envs/{env}/values.yaml"
            own = [ROOT / f for f in component.get("kind_values", [])] if env == "kind" else []
            documents = helm(name, ROOT / component["path"], component["namespace"], [values, *own])
        elif component["name"] == "grafana-dashboards":
            documents = []
        else:
            documents = directory_docs(component, env)
        result.append((name, tuple(documents)))
    return tuple(result)


def documents(env: str = "prod") -> list[Doc]:
    return [d for _, group in render_env(env) for d in group]


def pod_spec(document: Doc) -> Doc | None:
    """El spec del pod de un workload, o None si el documento no crea pods directamente."""
    spec = document.get("spec") or {}
    if document["kind"] in {"Deployment", "DaemonSet", "StatefulSet", "Job"}:
        return spec["template"]["spec"]
    if document["kind"] == "CronJob":
        return spec["jobTemplate"]["spec"]["template"]["spec"]
    return None


def pod_labels(document: Doc) -> Doc:
    spec = document["spec"]
    template = spec["jobTemplate"]["spec"]["template"] if document["kind"] == "CronJob" else spec["template"]
    return template.get("metadata", {}).get("labels", {})


#: RBAC de todo el cluster: un comodin en un ClusterRole upstream importa tanto como uno propio (NFR-U1-27).
CLUSTER_WIDE_KINDS = {"Role", "ClusterRole"}


def evaluated(document: Doc) -> bool:
    """Lo que `kyverno apply` debe ver: lo de vectra-* y, sin importar el namespace, todo el RBAC."""
    if document["kind"] == "CustomResourceDefinition":
        return False
    return document["kind"] in CLUSTER_WIDE_KINDS or document["metadata"].get("namespace", "").startswith("vectra-")


def chart_renders(chart: str, only_env: str | None, namespace: str) -> Iterator[tuple[str, str, str, list[Path]]]:
    """Lo que Argo CD renderizara: cada entrada de `components.yaml` con ese chart, en cada entorno suyo y con sus values.

    Un chart que aun no tiene entrada se renderiza con los values del entorno, en el namespace pedido.
    """
    spec = importlib.util.spec_from_file_location("gitops_generate", ROOT / "vectra-risk-gitops/generate.py")
    assert spec and spec.loader
    gitops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gitops)
    config = yaml.safe_load((ROOT / "vectra-risk-gitops/components.yaml").read_text(encoding="utf-8"))
    components = [c for c in config["components"] if c.get("path") == chart]
    for env in [only_env] if only_env else list(gitops.ENVS):
        common = [ROOT / f"vectra-risk-gitops/envs/{env}/values.yaml"]
        if not components:
            yield Path(chart).name, env, namespace, common
        for component in components:
            if env in component.get("envs", gitops.ENVS):
                own = [ROOT / f for f in gitops.value_files(component, env)]
                yield component["name"], env, component["namespace"], [*(common if component.get("env_values") else []), *own]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--env")
    parser.add_argument("--chart", help="chart de una unidad, relativo a vectra-risk/")
    parser.add_argument("--namespace", default="vectra-app")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.chart:
        chart = ROOT / args.chart
        if not (chart / "Chart.yaml").is_file():
            print(f"{args.chart}: no es un chart")
            return 1
        for name, env, namespace, values in chart_renders(args.chart, args.env, args.namespace):
            group = helm(chart.name, chart, namespace, values)
            (args.out / f"{name}-{env}.yaml").write_text(yaml.safe_dump_all(group, sort_keys=False), encoding="utf-8")
        return 0
    for name, group in render_env(args.env or "prod"):
        kept = [d for d in group if evaluated(d)]
        if kept:
            (args.out / f"{name}.yaml").write_text(yaml.safe_dump_all(kept, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
