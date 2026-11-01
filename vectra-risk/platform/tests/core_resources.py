#!/usr/bin/env python3
"""Deja solo lo que `kubectl diff` puede evaluar contra un kind vacio (NFR-U1-42).

`kubectl diff` hace un dry-run en el servidor, y en el kind efimero del workflow no hay CRDs ni namespaces de Vectra:
nunca se aplica nada. Un recurso personalizado o un objeto de un namespace ausente terminan en error (salida > 1), no
en un diff. Se conservan los tipos del nucleo de Kubernetes que son de cluster o de un namespace que ya existe, y lo
excluido queda en `limits.txt`, para que el revisor sepa lo que este diff no cubre.

Uso: core_resources.py ENTRADA... --out DIR [--namespace NS]...
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

#: Grupos de la API que existen en cualquier cluster, sin CRDs.
CORE_GROUPS = {
    "", "admissionregistration.k8s.io", "apiextensions.k8s.io", "apiregistration.k8s.io", "apps", "authentication.k8s.io",
    "authorization.k8s.io", "autoscaling", "batch", "certificates.k8s.io", "coordination.k8s.io", "discovery.k8s.io",
    "events.k8s.io", "flowcontrol.apiserver.k8s.io", "networking.k8s.io", "node.k8s.io", "policy", "rbac.authorization.k8s.io",
    "resource.k8s.io", "scheduling.k8s.io", "storage.k8s.io",
}  # fmt: skip
CLUSTER_SCOPED_CORE = {
    "Namespace", "Node", "PersistentVolume", "ClusterRole", "ClusterRoleBinding", "PriorityClass", "StorageClass",
    "CSIDriver", "CSINode", "VolumeAttachment", "CustomResourceDefinition", "APIService", "IngressClass", "RuntimeClass",
    "MutatingWebhookConfiguration", "ValidatingWebhookConfiguration", "ValidatingAdmissionPolicy", "ValidatingAdmissionPolicyBinding",
    "FlowSchema", "PriorityLevelConfiguration", "CertificateSigningRequest",
}  # fmt: skip

Doc = dict[str, Any]


def group_of(document: Doc) -> str:
    version = str(document.get("apiVersion", ""))
    return version.split("/")[0] if "/" in version else ""


def exclusion(document: Doc, namespaces: set[str]) -> str | None:
    """Por que `kubectl diff` no puede evaluar el documento, o None si puede."""
    if group_of(document) not in CORE_GROUPS:
        return "CRD ausente en el kind efimero"
    if document.get("kind") in CLUSTER_SCOPED_CORE:
        return None
    namespace = (document.get("metadata") or {}).get("namespace", "default")
    return None if namespace in namespaces else f"namespace {namespace} ausente en el kind efimero"


def select(documents: list[Doc], namespaces: set[str]) -> tuple[list[Doc], Counter[str]]:
    kept: list[Doc] = []
    excluded: Counter[str] = Counter()
    for document in documents:
        reason = exclusion(document, namespaces)
        if reason:
            excluded[f"{document.get('kind')}: {reason}"] += 1
        else:
            kept.append(document)
    return kept, excluded


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--namespace", action="append", default=[], help="namespace que existe en el cluster")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    namespaces = {n.removeprefix("namespace/") for n in args.namespace}
    limits: Counter[str] = Counter()
    total = 0
    for path in args.inputs:
        documents = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
        kept, excluded = select(documents, namespaces)
        limits += excluded
        total += len(kept)
        # Un archivo vacio haria fallar `kubectl diff -f`.
        if kept:
            (args.out / path.name).write_text(yaml.safe_dump_all(kept, sort_keys=False), encoding="utf-8")
    lines = [f"{count} {reason}" for reason, count in sorted(limits.items())]
    (args.out / "limits.txt").write_text("\n".join(["Excluidos de kubectl diff:", *lines, ""]), encoding="utf-8")
    if not total:
        print("Ningun recurso que `kubectl diff` pueda evaluar: la evidencia quedaria vacia")
        return 1
    print(f"{total} recursos para `kubectl diff`; excluidos: {sum(limits.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
