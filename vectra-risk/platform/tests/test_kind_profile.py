"""El perfil liviano de kind cabe en una maquina de 14 GiB, y conserva lo que los simulacros necesitan."""

from pathlib import Path

import integration
import yaml

PLATFORM = Path(__file__).resolve().parents[1]
#: Memoria pedida por todos los pods de kind, proxies incluidos. Es lo que el planificador reserva, no el uso real.
# Provisional (decisión del usuario, 2026-11-08, U02-T17): U1 + U2 piden 5,47 GiB. Se revisa con la medición del Paso 16 de U2
# (DD-3 y T6 de `aidlc-docs/construction/plans/demo-kind-alcance.md`).
BUDGET_GIB = 5.5
PROXY_GIB = 20 / 1024
MESHED = {
    "vectra-edge", "vectra-app", "vectra-serving", "vectra-staging", "vectra-data", "vectra-identity", "vectra-mock",
    "vectra-observability", "vectra-restore-drill",
}  # fmt: skip
UNITS = {"Ki": 1 / 1024**2, "Mi": 1 / 1024, "Gi": 1}


def gib(value: object) -> float:
    text = str(value)
    for suffix, factor in UNITS.items():
        if text.endswith(suffix):
            return float(text.removesuffix(suffix)) * factor
    return float(text) / 1024**3 if text.isdigit() else 0.0


def pod_memory(spec: dict) -> float:
    return sum(gib(c.get("resources", {}).get("requests", {}).get("memory", 0)) for c in spec.get("containers", []))


def rendered() -> list[dict]:
    return [d for _, group in integration.render_env("kind") for d in group]


def requested_gib() -> float:
    total = 0.0
    for document in rendered():
        namespace = document["metadata"].get("namespace", "")
        proxy = PROXY_GIB if namespace in MESHED else 0.0
        kind = document["kind"]
        if kind in {"Deployment", "StatefulSet"}:
            total += document["spec"].get("replicas", 1) * (pod_memory(document["spec"]["template"]["spec"]) + proxy)
        elif kind == "DaemonSet":
            total += 2 * (pod_memory(document["spec"]["template"]["spec"]) + proxy)  # dos nodos de trabajo
        elif kind == "Cluster":
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"]["instances"] * (memory + proxy)
        elif kind in {"Prometheus", "Alertmanager"}:
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"].get("replicas", 1) * (memory + proxy)
    return total


def test_the_profile_requests_fit_the_budget():
    assert requested_gib() <= BUDGET_GIB, requested_gib()


def test_kind_has_no_synchronous_replica_but_production_does():
    clusters = {e: [d for d in integration.render_env(e) for d in d[1] if d["kind"] == "Cluster"] for e in ("kind", "prod")}
    assert all(c["spec"]["instances"] == 1 and "minSyncReplicas" not in c["spec"] for c in clusters["kind"])
    assert all(c["spec"]["instances"] == 3 and c["spec"]["minSyncReplicas"] == 1 for c in clusters["prod"])


def test_minio_keeps_several_drives_for_object_lock():
    values = yaml.safe_load((PLATFORM / "data/minio/values-kind.yaml").read_text(encoding="utf-8"))
    assert values["replicas"] == 1 and values["drivesPerNode"] >= 4


def test_linkerd_loses_ha_only_in_kind():
    assert yaml.safe_load((PLATFORM / "mesh/linkerd-kind.yaml").read_text(encoding="utf-8"))["controllerReplicas"] == 1
    assert yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))["controllerReplicas"] == 3
