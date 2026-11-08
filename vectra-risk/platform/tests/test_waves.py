#!/usr/bin/env python3
"""Cada Application de una raiz tiene sync-wave y el orden respeta P-U1-12 y las dependencias entre componentes.

`--root X` (por omision `vectra-risk-gitops/apps`) es una carpeta con `root.yaml` o que contiene varias. La wave de cada
componente sale de `vectra-risk-gitops/components.yaml`, y `STRICT` y `SAME_WAVE_OK` dice que tiene que estar listo antes de que.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "vectra-risk-gitops/components.yaml"
WAVE_ANNOTATION = "argocd.argoproj.io/sync-wave"
WAVES = range(7)  # P-U1-12: waves 0 a 6
#: Wave de cada Application de una unidad, segun P-U1-12 y su plan: `components.yaml` no se puede corregir a si mismo.
FIXED_WAVES = {
    "decision-registry": 5,
    "scoring-explainability": 5,
    "governance": 5,
    "case-management": 5,
    "bias-monitoring": 5,
    "console-bff": 5,
    "console-spa": 5,
    "product-metrics": 5,
    "model-serving": 6,
    "decision-registry-rebuild": 6,
}
#: (requisito, consumidor). El CRD o el operador va en una wave anterior a quien lo usa.
STRICT = {
    ("cert-manager", "mesh-certificates"),
    ("trust-manager", "mesh-certificates"),
    ("linkerd-crds", "linkerd-control-plane"),
    ("kyverno", "kyverno-policies"),
    ("external-secrets", "secret-store"),
    ("cloudnative-pg", "postgres"),
    ("namespaces", "postgres"),
    ("namespaces", "minio"),
    ("secret-store", "postgres"),
    ("secret-store", "minio"),
    ("prometheus-operator-crds", "kube-prometheus-stack"),
    ("postgres", "keycloak"),
    ("valkey", "gateway"),
    ("envoy-gateway", "gateway"),
    ("secret-store", "ratelimit"),
    ("prometheus-operator-crds", "identity-rules"),
    ("prometheus-operator-crds", "identity-monitors"),
    ("minio", "loki"),
    ("minio", "tempo"),
    ("postgres", "kube-prometheus-stack"),
    ("kube-prometheus-stack", "restore-drill"),
    ("postgres", "restore-drill"),
    ("kserve", "decision-registry-rebuild"),
    ("decision-registry", "decision-registry-rebuild"),
}
#: Basta con la misma wave: dentro de una wave Argo CD ordena por tipo y nombre y espera a que cada una este sana.
SAME_WAVE_OK = {
    ("namespaces", "quotas"),
    ("namespaces", "network"),
    ("priority-classes", "linkerd-control-plane"),
    ("mesh-certificates", "linkerd-control-plane"),
    ("keycloak", "identity-jobs"),
    ("kube-prometheus-stack", "observability-rules"),
    ("kube-prometheus-stack", "grafana-config"),
}
Doc = dict[str, Any]


def applications(folder: Path) -> dict[str, Doc]:
    found: dict[str, Doc] = {}
    for path in sorted(folder.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(document, dict) and document.get("kind") == "Application":
                found[document["metadata"]["name"]] = document
    return found


def wave_of(application: Doc) -> int | None:
    value = ((application.get("metadata") or {}).get("annotations") or {}).get(WAVE_ANNOTATION)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def expected_waves() -> dict[str, int]:
    config = yaml.safe_load(COMPONENTS.read_text(encoding="utf-8"))
    return {**{c["name"]: int(c["wave"]) for c in config["components"]}, **FIXED_WAVES}


def problems_in(apps: dict[str, Doc], expected: dict[str, int]) -> list[str]:
    problems: list[str] = []
    if "root" not in apps:
        problems.append("falta root.yaml")
    waves: dict[str, int] = {}
    for name, application in apps.items():
        wave = wave_of(application)
        if wave is None:
            problems.append(f"{name}: sin wave")
        elif wave not in WAVES:
            problems.append(f"{name}: wave {wave} fuera de P-U1-12")
        else:
            waves[name] = wave
            if name in expected and wave != expected[name]:
                problems.append(f"{name}: wave {wave}, se esperaba {expected[name]}")
    for prerequisite, consumer in sorted(STRICT):
        if prerequisite in waves and consumer in waves and waves[prerequisite] >= waves[consumer]:
            problems.append(f"{consumer} (wave {waves[consumer]}) necesita {prerequisite} antes (wave {waves[prerequisite]})")
    for prerequisite, consumer in sorted(SAME_WAVE_OK):
        if prerequisite in waves and consumer in waves and waves[prerequisite] > waves[consumer]:
            problems.append(f"{consumer} (wave {waves[consumer]}) corre antes que {prerequisite} (wave {waves[prerequisite]})")
    return problems


def roots_in(folder: Path) -> list[Path]:
    if (folder / "root.yaml").is_file():
        return [folder]
    return sorted(p for p in folder.iterdir() if p.is_dir() and (p / "root.yaml").is_file())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="vectra-risk-gitops/apps", help="carpeta relativa a vectra-risk/")
    args = parser.parse_args(argv)
    folder = ROOT / args.root
    if not folder.is_dir() or not roots_in(folder):
        print(f"{args.root}: sin Applications que revisar")
        return 1
    expected = expected_waves()
    failures = 0
    for root in roots_in(folder):
        apps = applications(root)
        problems = problems_in(apps, expected)
        failures += len(problems)
        print("\n".join(f"{root.name}: {p}" for p in problems) if problems else f"{root.name}: {len(apps)} Applications en orden")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
