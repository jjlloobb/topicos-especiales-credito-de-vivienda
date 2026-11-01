#!/usr/bin/env python3
"""Genera AppProject, root y una Application por componente (P-U1-12). `--check` compara con lo versionado."""

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
PREFIX = "vectra-risk/"  # el repositorio es el monorepo
ENVS = ("kind", "staging", "prod")
CLUSTER_KINDS = [
    ("", "Namespace"),
    ("apiextensions.k8s.io", "CustomResourceDefinition"),
    ("apiregistration.k8s.io", "APIService"),
    ("scheduling.k8s.io", "PriorityClass"),
    ("rbac.authorization.k8s.io", "ClusterRole"),
    ("rbac.authorization.k8s.io", "ClusterRoleBinding"),
    ("kyverno.io", "ClusterPolicy"),
    ("external-secrets.io", "ClusterSecretStore"),
    ("cert-manager.io", "ClusterIssuer"),
    ("trust.cert-manager.io", "Bundle"),
    ("admissionregistration.k8s.io", "ValidatingWebhookConfiguration"),
    ("admissionregistration.k8s.io", "MutatingWebhookConfiguration"),
    ("gateway.networking.k8s.io", "GatewayClass"),
    ("serving.kserve.io", "ClusterServingRuntime"),
]
MESHED = ["vectra-edge", "vectra-app", "vectra-serving", "vectra-staging", "vectra-data", "vectra-identity", "vectra-observability", "vectra-restore-drill"]
Doc = dict[str, Any]


def chart_repo(component: Doc, env: str, config: Doc) -> str:
    return str(component["repo"]) if env == "kind" else str(config["chart_mirror"])


def project(env: str, config: Doc, components: list[Doc]) -> Doc:
    namespaces = [n for n in [*MESHED, *config["system_namespaces"]] if n != "vault" or env == "kind"]
    if env != "prod":
        namespaces.append("vectra-mock")
    repos = {config["git"][env], *(chart_repo(c, env, config) for c in components if "chart" in c)}
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": f"vectra-{env}", "namespace": "argocd"},
        "spec": {
            "description": f"Vectra Risk, entorno {env}",
            "sourceRepos": sorted(repos),
            "destinations": [{"server": "https://kubernetes.default.svc", "namespace": n} for n in sorted(namespaces)],
            "clusterResourceWhitelist": [{"group": g, "kind": k} for g, k in CLUSTER_KINDS],
        },
    }


def metadata(name: str, wave: int) -> Doc:
    return {"name": name, "namespace": "argocd", "annotations": {"argocd.argoproj.io/sync-wave": str(wave)}}


def root(env: str, config: Doc) -> Doc:
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": metadata("root", 0),
        "spec": {
            "project": f"vectra-{env}",
            "source": {"repoURL": config["git"][env], "targetRevision": "main", "path": f"{PREFIX}vectra-risk-gitops/apps/{env}"},
            "destination": {"server": "https://kubernetes.default.svc", "namespace": "argocd"},
            "syncPolicy": {"syncOptions": ["ServerSideApply=true"]},
        },
    }


def value_files(component: Doc, env: str) -> list[str]:
    """Los de `components.yaml`, y `values/<env>/<nombre>.yaml` si existe: ahi van los de cada unidad."""
    own = f"vectra-risk-gitops/values/{env}/{component['name']}.yaml"
    files = [*component.get("values", []), *(component.get("kind_values", []) if env == "kind" else [])]
    return [*files, own] if (HERE.parent / own).is_file() else files


def application(component: Doc, env: str, config: Doc) -> Doc:
    git = config["git"][env]
    env_values = f"{PREFIX}vectra-risk-gitops/envs/{env}/values.yaml"
    spec: Doc = {"project": f"vectra-{env}"}
    files = value_files(component, env)
    if "chart" in component:
        source: Doc = {"repoURL": chart_repo(component, env, config), "chart": component["chart"], "targetRevision": component["version"]}
        if files:
            source["helm"] = {"valueFiles": [f"$values/{PREFIX}{f}" for f in files]}
        spec["sources"] = [source, {"repoURL": git, "targetRevision": "main", "ref": "values"}]
    else:
        source = {"repoURL": git, "targetRevision": "main", "path": PREFIX + component["path"].replace("{env}", env)}
        directory = {k: component[k].replace("{env}", env) for k in ("include", "exclude") if k in component}
        if directory:
            source["directory"] = directory
        helm_files = [f"/{env_values}"] if component.get("env_values") else []
        helm_files += [f"/{PREFIX}{f}" for f in files]
        if helm_files:
            source["helm"] = {"valueFiles": helm_files}
        spec["source"] = source
    spec["destination"] = {"server": "https://kubernetes.default.svc", "namespace": component["namespace"]}
    options = ["ServerSideApply=true"]
    if component["namespace"] in config["system_namespaces"]:
        options.append("CreateNamespace=true")
    spec["syncPolicy"] = {"syncOptions": options}
    return {"apiVersion": "argoproj.io/v1alpha1", "kind": "Application", "metadata": metadata(component["name"], component["wave"]), "spec": spec}


def env_values(env: str) -> Doc:
    secure = env != "kind"
    return {
        "storageClass": "vectra-encrypted" if secure else "standard",
        "imageRegistry": "registro.banco.internal/vectra" if secure else "kind-registry:5000",
        "mockEnabled": env != "prod",
        "verificationOperator": env != "prod",
    }


def write(out: Path, config: Doc) -> None:
    for env in ENVS:
        components = [c for c in config["components"] if env in c.get("envs", ENVS)]
        folder = out / "apps" / env
        folder.mkdir(parents=True)
        documents = {"project": project(env, config, components), "root": root(env, config)}
        documents |= {c["name"]: application(c, env, config) for c in components}
        for name, document in documents.items():
            (folder / f"{name}.yaml").write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        values = out / "envs" / env
        values.mkdir(parents=True)
        (values / "values.yaml").write_text(yaml.safe_dump(env_values(env), sort_keys=False), encoding="utf-8")


def tree(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*.yaml"))}


def main() -> int:
    config = yaml.safe_load((HERE / "components.yaml").read_text(encoding="utf-8"))
    if "--check" in sys.argv:
        with tempfile.TemporaryDirectory() as temporary:
            write(Path(temporary), config)
            generated = tree(Path(temporary))
        current = {k: v for k, v in tree(HERE).items() if k.startswith(("apps/", "envs/"))}
        if generated != current:
            print("Los manifiestos de GitOps no coinciden con components.yaml")
            return 1
        return 0
    for name in ("apps", "envs"):
        shutil.rmtree(HERE / name, ignore_errors=True)
    write(HERE, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
