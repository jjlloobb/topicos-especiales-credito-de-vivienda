"""U02-T12 (CA-2): los selectores que `flows.yaml` y lo generado dan al borde seleccionan los pods reales.

Lecciones de F-12 de U02-T10 y de F-01 de U02-T11: una etiqueta que ningun pod lleva deja una NetworkPolicy o un `Server` que no
seleccionan nada, y nada lo nota hasta el clúster. Los pods reales salen de los modelos de U2, no de un literal de esta prueba:
- el data plane: `data_plane_deployment` de `test_data_plane_policies.py` (v1.9.3, `envoyLabels`) sobre `identity-edge/gateway/generated/<env>/`;
- `envoy-ratelimit`: `ratelimit_deployment` de `test_ratelimit_deployment.py` (`rateLimitLabels()`, `InfraName`) sobre el chart del controlador;
- Valkey y Sentinel: los StatefulSet de `identity-edge/charts/valkey/rendered/<env>/`.
De lo generado se toman el `podSelector` y el `namespaceSelector` de cada NetworkPolicy y `Server` de cada trabajador del borde.
"""

import copy
import functools
from pathlib import Path
from typing import Any

import gateway_checks as gc
import pytest
import test_data_plane_policies as data_plane
import test_ratelimit_deployment as ratelimit
import yaml
from generate import ENVS, build, endpoint, exists_in, labels_of, load

ROOT = Path(__file__).resolve().parents[3]
VALKEY_RENDERED = ROOT / "identity-edge" / "charts" / "valkey" / "rendered"
DATA, FORBIDDEN = load()
EDGE_WORKLOADS = ("api-gateway", "rate-limit", "valkey", "sentinel")
NS_KEY = "kubernetes.io/metadata.name"


def selects(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return bool(selector) and all(labels.get(k) == v for k, v in selector.items())


@functools.cache
def real_pods(env: str) -> dict[str, dict[str, Any]]:
    """Trabajador -> {ns, sa, pods: [etiquetas de cada pod]} segun los modelos de cada unidad."""
    plane = data_plane.data_plane_deployment(gc.load_env(env), env)
    limiter = ratelimit.ratelimit_deployment(ratelimit.controller_config(ratelimit.render(env)))
    sets = [d for d in yaml.safe_load_all((VALKEY_RENDERED / env / "valkey.yaml").read_text(encoding="utf-8")) if d and d["kind"] == "StatefulSet"]

    def of_sets(prefix: str) -> dict[str, Any]:
        mine = [d for d in sets if d["metadata"]["name"].startswith(prefix)]
        assert mine, prefix
        (sa,) = {d["spec"]["template"]["spec"]["serviceAccountName"] for d in mine}
        (ns,) = {d["metadata"]["namespace"] for d in mine}
        return {"ns": ns, "sa": sa, "pods": [d["spec"]["template"]["metadata"]["labels"] for d in mine]}

    return {
        "api-gateway": {"ns": plane["metadata"]["namespace"], "sa": None, "pods": [plane["spec"]["template"]["metadata"]["labels"]]},
        "rate-limit": {
            "ns": limiter["metadata"]["namespace"],
            "sa": limiter["spec"]["template"]["spec"]["serviceAccountName"],
            "pods": [limiter["spec"]["template"]["metadata"]["labels"]],
        },
        "valkey": of_sets("valkey-"),
        "sentinel": of_sets("sentinel-"),
    }


def generated_selectors(built: dict[str, list[dict[str, Any]]], data: dict[str, Any], env: str, name: str) -> list[tuple[str, str | None, dict[str, str]]]:
    """(documento, namespace, etiquetas del podSelector) de lo que lo generado dice de `name`.

    Un `Server` y una NetworkPolicy propios traen `metadata.namespace` y `spec.podSelector`; las ajenas, el par que nombra a `name`
    como origen (`from` de la ingress, en el orden de `flows.yaml`) o como destino (`to` de la egress). El nombre de cada documento
    lo arma el generador con la clave del trabajador, que no cambia (`FIXED_WAVES` de `test_waves.py`).
    """
    found: list[tuple[str, str | None, dict[str, str]]] = []
    for docs in built.values():
        for doc in docs:
            meta = doc["metadata"]
            if doc["kind"] == "Server" and meta["name"].rsplit("-", 1)[0] == name and meta["name"].rsplit("-", 1)[1].isdigit():
                found.append((f"Server {meta['name']}", meta["namespace"], doc["spec"]["podSelector"].get("matchLabels", {})))
            if doc["kind"] != "NetworkPolicy" or "vectra.io/flow" not in meta.get("labels", {}) or not meta["name"].startswith("allow-f"):
                continue
            flow_id, rest = meta["labels"]["vectra.io/flow"], meta["name"].split("-", 2)[2]
            label = f"NetworkPolicy {meta['name']}"
            if rest == f"to-{name}-ingress":
                found.append((label, meta["namespace"], doc["spec"]["podSelector"].get("matchLabels", {})))
            if rest.startswith(f"{name}-to-") and rest.endswith("-egress"):
                found.append((label, meta["namespace"], doc["spec"]["podSelector"].get("matchLabels", {})))
            if rest.endswith(f"-to-{name}-egress"):
                peer = doc["spec"]["egress"][0]["to"][0]
                found.append((f"{label} (destino)", peer["namespaceSelector"]["matchLabels"][NS_KEY], peer.get("podSelector", {}).get("matchLabels", {})))
            if rest.startswith("to-") and rest.endswith("-ingress"):
                dest = rest.removeprefix("to-").removesuffix("-ingress")
                for item in (f for f in data["flows"] if f["id"] == flow_id and dest in f["to"]):
                    sources = [s for s in item["from"] if not s.startswith("external:") and exists_in(endpoint(s, data), env)]
                    for source, peer in zip(sources, doc["spec"]["ingress"][0].get("from", []), strict=False):
                        if source == name:
                            found.append((f"{label} (origen)", peer["namespaceSelector"]["matchLabels"][NS_KEY], peer.get("podSelector", {}).get("matchLabels", {})))
    return found


def problems(env: str, data: dict[str, Any]) -> list[str]:
    """Diferencias entre los selectores de `flows.yaml` y lo generado, y los pods reales. Vacio si seleccionan."""
    found: list[str] = []
    built = build(env, data, FORBIDDEN)[0]
    for name in EDGE_WORKLOADS:
        real, workload = real_pods(env)[name], data["workloads"][name]
        if workload["ns"] != real["ns"]:
            found.append(f"{name}: flows.yaml lo pone en {workload['ns']} y el pod esta en {real['ns']}")
        if real["sa"] and workload["sa"] != real["sa"]:
            found.append(f"{name}: sa {workload['sa']} y el pod usa {real['sa']}")
        for labels in real["pods"]:
            if not selects(labels_of(workload), labels):
                found.append(f"{name}: {labels_of(workload)} no selecciona un pod que lleva {labels}")
        documents = generated_selectors(built, data, env, name)
        if not documents:
            found.append(f"{name}: lo generado no lo nombra")
        for label, ns, labels in documents:
            if ns != real["ns"]:
                found.append(f"{name}: {label} apunta al namespace {ns} y el pod esta en {real['ns']}")
            for pod in real["pods"]:
                if not selects(labels, pod):
                    found.append(f"{name}: {label} con {labels} no selecciona un pod que lleva {pod}")
    return found


@pytest.mark.parametrize("env", ENVS)
def test_the_selectors_of_the_edge_select_the_real_pods(env):
    assert problems(env, DATA) == []


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("name", EDGE_WORKLOADS)
def test_every_edge_workload_is_named_by_both_policies_and_servers(env, name):
    """La prueba no es vacua: cada trabajador tiene su NetworkPolicy propia, una que lo nombra como origen o destino, y los de la malla su `Server`."""
    labels = [label for label, _, _ in generated_selectors(build(env, DATA, FORBIDDEN)[0], DATA, env, name)]
    assert any(label.startswith("NetworkPolicy") and "(" not in label for label in labels), labels
    assert any("(origen)" in label or "(destino)" in label for label in labels), labels
    if DATA["workloads"][name]["ns"] in DATA["meshed_namespaces"]:
        assert any(label.startswith("Server") for label in labels), labels


def mutated(change) -> dict[str, Any]:
    data = copy.deepcopy(DATA)
    change(data["workloads"])
    return data


def another_label(name: str):
    """El trabajador pasa a seleccionar por una etiqueta que ningun pod lleva."""

    def change(workloads: dict[str, Any]) -> None:
        workloads[name] = {"ns": workloads[name]["ns"], "sa": workloads[name]["sa"], "labels": {"app.kubernetes.io/name": "ninguno"}}

    return change


MUTATIONS = {
    **{f"etiqueta de {name}": another_label(name) for name in EDGE_WORKLOADS},
    "rate-limit vuelve a vectra-edge": lambda w: w["rate-limit"].update(ns="vectra-edge"),
    "api-gateway por app.kubernetes.io/name (antes de Z1)": lambda w: w.update({"api-gateway": {"ns": "vectra-edge", "sa": "api-gateway", "name": "api-gateway"}}),
    "rate-limit sin la etiqueta de component": lambda w: w["rate-limit"].update(labels={k: v for k, v in w["rate-limit"]["labels"].items() if k != "app.kubernetes.io/component"} | {"app.kubernetes.io/component": "otro"}),
    "sentinel con la etiqueta de valkey": lambda w: w.update({"sentinel": {**w["sentinel"], "name": "valkey"}}),
    "serviceAccount de rate-limit": lambda w: w["rate-limit"].update(sa="rate-limit"),
}


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("case", MUTATIONS)
def test_a_selector_that_does_not_select_fails(env, case):
    """Cada cambio contrario, en una copia de `flows.yaml`, hace fallar la comprobacion."""
    assert problems(env, mutated(MUTATIONS[case])) != [], case
