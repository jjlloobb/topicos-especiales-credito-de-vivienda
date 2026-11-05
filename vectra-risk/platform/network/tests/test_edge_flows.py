"""U02-T12 (CA-1): los flujos del borde de U2 en lo generado de los tres entornos (decisiones T1 a T3, INF-U2-04).

Los valores que el diseno fija no se escriben aqui: los puertos de gRPC, metricas y tracing salen de INF-U2-03 y 04 (`valkey_design`), los
de Valkey, Sentinel y el exportador del chart renderizado, y las etiquetas de `envoy-ratelimit` y su namespace del modelo de v1.9.3
(`test_ratelimit_deployment`). Cada comprobacion tiene su cambio contrario: aplicado en una copia de `flows.yaml`, falla.
"""

import copy
from pathlib import Path
from typing import Any

import pytest
import test_ratelimit_deployment as ratelimit
import valkey_design as design
import yaml
from generate import ENVS, LINKERD_INBOUND_PORT, LINKERD_OPAQUE_PORTS, build, endpoint, exists_in, labels_of, load

ROOT = Path(__file__).resolve().parents[3]
DATA, FORBIDDEN = load()
NS_KEY = "kubernetes.io/metadata.name"
LIMITER_NS = ratelimit.NAMESPACE
Check = list[str]


def chart_ports(env: str) -> dict[str, int]:
    """Los puertos de contenedor de Valkey, Sentinel y el exportador, del render versionado del chart."""
    path = ROOT / "identity-edge" / "charts" / "valkey" / "rendered" / env / "valkey.yaml"
    sets = {d["metadata"]["name"]: d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d and d["kind"] == "StatefulSet"}
    by_name = {c["name"]: c["ports"][0]["containerPort"] for c in sets["valkey-a"]["spec"]["template"]["spec"]["containers"]}
    sentinel = {c["name"]: c["ports"][0]["containerPort"] for c in sets["sentinel-a"]["spec"]["template"]["spec"]["containers"]}
    return {"valkey": by_name["valkey"], "exporter": by_name["exporter"], "sentinel": sentinel["sentinel"]}


def trace_port() -> int:
    return int(design.ratelimit_tracing()[0].rsplit(":", 1)[1])


def peer(name: str, data: dict[str, Any]) -> dict[str, Any]:
    workload = data["workloads"][name]
    return {"namespaceSelector": {"matchLabels": {NS_KEY: workload["ns"]}}, "podSelector": {"matchLabels": labels_of(workload)}}


def documents(env: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    return [d for items in build(env, data, FORBIDDEN)[0].values() for d in items]


def named(docs: list[dict[str, Any]], kind: str, name: str) -> list[dict[str, Any]]:
    return [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]


def ports_of(policy: dict[str, Any]) -> set[int]:
    rules = policy["spec"].get("ingress") or policy["spec"].get("egress")
    return {p["port"] for rule in rules for p in rule["ports"]}


def network_policy(docs: list[dict[str, Any]], name: str, ns: str, selector: dict[str, str]) -> tuple[dict[str, Any] | None, Check]:
    found = [d for d in named(docs, "NetworkPolicy", name) if d["metadata"]["namespace"] == ns]
    if len(found) != 1:
        return None, [f"{name} en {ns}: {len(found)} NetworkPolicy"]
    if found[0]["spec"]["podSelector"] != {"matchLabels": selector}:
        return found[0], [f"{name}: podSelector {found[0]['spec']['podSelector']}"]
    return found[0], []


def pair(docs: list[dict[str, Any]], flow_id: str, src: str, dest: str, src_ns: str, dest_ns: str, src_labels: dict[str, str], dest_labels: dict[str, str], from_peers: list[dict[str, Any]], to_peer: dict[str, Any], expected_ports: set[int]) -> Check:
    """La NetworkPolicy de salida del origen y la de entrada del destino: namespaces, pods, el otro extremo y los puertos exactos."""
    found: Check = []
    ingress, errors = network_policy(docs, f"allow-{flow_id.lower()}-to-{dest}-ingress", dest_ns, dest_labels)
    found += errors
    if ingress:
        if ingress["spec"]["policyTypes"] != ["Ingress"] or ingress["spec"]["ingress"][0].get("from") != from_peers:
            found.append(f"{flow_id} {dest}: el origen de la ingress no es {from_peers}")
        if ports_of(ingress) != expected_ports:
            found.append(f"{flow_id} {dest}: la ingress abre {sorted(ports_of(ingress))} y no {sorted(expected_ports)}")
    egress, errors = network_policy(docs, f"allow-{flow_id.lower()}-{src}-to-{dest}-egress", src_ns, src_labels)
    found += errors
    if egress:
        if egress["spec"]["policyTypes"] != ["Egress"] or egress["spec"]["egress"][0]["to"] != [to_peer]:
            found.append(f"{flow_id} {src}: el destino de la egress no es {to_peer}")
        if ports_of(egress) != expected_ports:
            found.append(f"{flow_id} {src}: la egress abre {sorted(ports_of(egress))} y no {sorted(expected_ports)}")
    return found


def server(docs: list[dict[str, Any]], ns: str, name: str, port: int, labels: dict[str, str]) -> tuple[dict[str, Any] | None, Check]:
    found = [d for d in named(docs, "Server", f"{name}-{port}") if d["metadata"]["namespace"] == ns]
    if len(found) != 1:
        return None, [f"Server {name}-{port} en {ns}: {len(found)}"]
    errors = []
    if found[0]["spec"]["podSelector"] != {"matchLabels": labels} or found[0]["spec"]["port"] != port:
        errors.append(f"Server {name}-{port}: selector o puerto")
    return found[0], errors


def mesh_authorization(docs: list[dict[str, Any]], ns: str, flow_id: str, name: str, port: int, identity: str) -> Check:
    """La `AuthorizationPolicy` del flujo sobre el `Server` del puerto, con la identidad del origen."""
    found = [d for d in docs if d["kind"] == "AuthorizationPolicy" and d["metadata"]["namespace"] == ns and d["metadata"]["name"] == f"{flow_id.lower()}-{name}-{port}"]
    if len(found) != 1:
        return [f"{flow_id}: sin AuthorizationPolicy sobre {name}-{port}"]
    ref = found[0]["spec"]["requiredAuthenticationRefs"][0]
    mtls = named(docs, "MeshTLSAuthentication", ref["name"])
    ok = found[0]["spec"]["targetRef"]["name"] == f"{name}-{port}" and ref["kind"] == "MeshTLSAuthentication" and mtls and identity in mtls[0]["spec"]["identities"]
    return [] if ok else [f"{flow_id}: la autorizacion de {name}-{port} no admite a {identity}"]


def network_authorization(docs: list[dict[str, Any]], ns: str, flow_id: str, name: str, port: int, cidr: str) -> Check:
    """T1: `NetworkAuthentication` con el `pod_cidr` del entorno y su `AuthorizationPolicy` sobre el `Server` del puerto."""
    found = [
        d for d in docs
        if d["kind"] == "AuthorizationPolicy" and d["metadata"]["namespace"] == ns and d["metadata"]["name"].startswith(f"{flow_id.lower()}-{name}-{port}-")
        and d["spec"]["targetRef"]["name"] == f"{name}-{port}" and d["spec"]["requiredAuthenticationRefs"][0]["kind"] == "NetworkAuthentication"
    ]  # fmt: skip
    if len(found) != 1:
        return [f"{flow_id}: {len(found)} autorizaciones por NetworkAuthentication sobre {name}-{port}"]
    auth = named(docs, "NetworkAuthentication", found[0]["spec"]["requiredAuthenticationRefs"][0]["name"])
    if len(auth) != 1 or auth[0]["metadata"]["namespace"] != ns or auth[0]["spec"]["networks"] != [{"cidr": cidr}]:
        return [f"{flow_id}: la NetworkAuthentication de {name}-{port} no es el pod_cidr {cidr}"]
    return []


def identity(name: str, data: dict[str, Any]) -> str:
    workload = data["workloads"][name]
    return f"{workload['sa']}.{workload['ns']}.serviceaccount.identity.linkerd.cluster.local"


# --- F90 -------------------------------------------------------------------------------------------------------------


def check_f90(env: str, data: dict[str, Any]) -> Check:
    """F90 abre el gRPC de `envoy-ratelimit` (INF-U2-03), no el 8083 de antes, hacia `envoy-gateway-system`."""
    docs = documents(env, data)
    grpc = design.ratelimit_ports()["grpc"]
    gateway = data["workloads"]["api-gateway"]
    return pair(
        docs, "F90", "api-gateway", "rate-limit", gateway["ns"], LIMITER_NS, labels_of(gateway), ratelimit.ratelimit_labels(),
        [peer("api-gateway", data)], {"namespaceSelector": {"matchLabels": {NS_KEY: LIMITER_NS}}, "podSelector": {"matchLabels": ratelimit.ratelimit_labels()}}, {grpc},
    )  # fmt: skip


# --- F91 y F61: origen sin malla (T1) -------------------------------------------------------------------------------


def limiter_source(env: str, data: dict[str, Any], flow_id: str, dest: str, port: int, others: list[dict[str, Any]], expected_ports: set[int]) -> Check:
    docs = documents(env, data)
    target = data["workloads"][dest]
    shown = target.get("name", dest)  # el generador nombra los documentos con `name` del trabajador si lo tiene (otel-collector: opentelemetry-collector)
    labels = ratelimit.ratelimit_labels()
    limiter = {"namespaceSelector": {"matchLabels": {NS_KEY: LIMITER_NS}}, "podSelector": {"matchLabels": labels}}
    found = pair(
        docs, flow_id, "rate-limit", shown, LIMITER_NS, target["ns"], labels, labels_of(target), [*others, limiter],
        {"namespaceSelector": {"matchLabels": {NS_KEY: target["ns"]}}, "podSelector": {"matchLabels": labels_of(target)}}, expected_ports,
    )  # fmt: skip
    _, errors = server(docs, target["ns"], shown, port, labels_of(target))
    found += errors
    for srv in named(docs, "Server", f"{shown}-{port}"):
        want = "opaque" if port in LINKERD_OPAQUE_PORTS else "unknown"
        if srv["spec"]["proxyProtocol"] != want:
            found.append(f"Server {shown}-{port}: proxyProtocol {srv['spec']['proxyProtocol']} y se esperaba {want}")
    found += network_authorization(docs, target["ns"], flow_id, shown, port, data["pod_cidr"][env])
    return found


def check_f91(env: str, data: dict[str, Any]) -> Check:
    ports = chart_ports(env)
    both = {ports["valkey"], ports["sentinel"]}
    found = limiter_source(env, data, "F91", "valkey", ports["valkey"], [], both) + limiter_source(env, data, "F91", "sentinel", ports["sentinel"], [], both)
    if LINKERD_INBOUND_PORT in {p for d in documents(env, data) if d["metadata"].get("labels", {}).get("vectra.io/flow") == "F91" for p in ports_of(d)}:
        found.append("F91: el origen no esta en la malla y no usa el 4143")
    return found


def check_f61(env: str, data: dict[str, Any]) -> Check:
    """F61: los namespaces de la malla siguen como estaban; `envoy-ratelimit` suma su origen sin malla en el mismo destino."""
    meshed = [peer_ns for item in data["flows"] if item["id"] == "F61" and item["to"] == ["otel-collector"] for peer_ns in item["from"] if peer_ns.startswith("ns:") and exists_in(endpoint(peer_ns, data), env)]
    others = [{"namespaceSelector": {"matchLabels": {NS_KEY: n.removeprefix("ns:")}}} for n in meshed]
    return limiter_source(env, data, "F61", "otel-collector", trace_port(), others, {trace_port()})


# --- F92 ------------------------------------------------------------------------------------------------------------


def check_f92(env: str, data: dict[str, Any]) -> Check:
    """T2: Valkey -> Valkey (6379, como estaba) y Valkey -> Sentinel (26379) bajo el mismo id."""
    docs, ports = documents(env, data), chart_ports(env)
    valkey, sentinel = data["workloads"]["valkey"], data["workloads"]["sentinel"]
    found = pair(
        docs, "F92", "valkey", "valkey", valkey["ns"], valkey["ns"], labels_of(valkey), labels_of(valkey),
        [peer("valkey", data)], peer("valkey", data), {ports["valkey"], LINKERD_INBOUND_PORT},
    )  # fmt: skip
    found += pair(
        docs, "F92", "valkey", "sentinel", valkey["ns"], sentinel["ns"], labels_of(valkey), labels_of(sentinel),
        [peer("valkey", data)], peer("sentinel", data), {ports["sentinel"]},
    )  # fmt: skip
    _, errors = server(docs, sentinel["ns"], "sentinel", ports["sentinel"], labels_of(sentinel))
    found += errors
    found += mesh_authorization(docs, sentinel["ns"], "F92", "sentinel", ports["sentinel"], identity("valkey", data))
    return found


# --- F60 ------------------------------------------------------------------------------------------------------------


def check_f60(env: str, data: dict[str, Any]) -> Check:
    """T3: el scrape de Envoy (data plane) y de `envoy-ratelimit` en su 19001, y del exportador de Valkey en el 9121."""
    docs, scrape = documents(env, data), design.scrape_ports()
    found: Check = []
    prometheus = data["workloads"]["prometheus"]
    for dest, port in (("api-gateway", scrape["envoy"]), ("rate-limit", scrape["ratelimit"]), ("valkey", scrape["exporter"])):
        target = data["workloads"][dest]
        labels = ratelimit.ratelimit_labels() if dest == "rate-limit" else labels_of(target)
        found += pair(
            docs, "F60", "prometheus", dest, prometheus["ns"], target["ns"], labels_of(prometheus), labels, [peer("prometheus", data)],
            {"namespaceSelector": {"matchLabels": {NS_KEY: target["ns"]}}, "podSelector": {"matchLabels": labels_of(target)}}, {port},
        )  # fmt: skip
        if target["ns"] in data["meshed_namespaces"]:
            _, errors = server(docs, target["ns"], dest, port, labels_of(target))
            found += errors + mesh_authorization(docs, target["ns"], "F60", dest, port, identity("prometheus", data))
        elif named(docs, "Server", f"{dest}-{port}"):
            found.append(f"F60: {dest} esta fuera de la malla y no lleva Server")
    if scrape["exporter"] != chart_ports(env)["exporter"]:
        found.append("F60: el puerto del exportador no es el del chart")
    return found


CHECKS = {"F90": check_f90, "F91": check_f91, "F61": check_f61, "F92": check_f92, "F60": check_f60}


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("flow_id", CHECKS)
def test_the_generated_edge_flows_follow_the_design(env, flow_id):
    assert CHECKS[flow_id](env, DATA) == []


# --- el cambio contrario, en una copia de flows.yaml, hace fallar cada comprobacion -----------------------------------


def without(data: dict[str, Any], flow_id: str, to: list[str] | None = None, port: int | None = None) -> None:
    data["flows"] = [f for f in data["flows"] if not (f["id"] == flow_id and (to is None or f["to"] == to) and (port is None or port in (f.get("ports") or [f.get("port")])))]


def edit(data: dict[str, Any], flow_id: str, match_to: list[str], **change: Any) -> None:
    for item in data["flows"]:
        if item["id"] == flow_id and item["to"] == match_to:
            item.update(change)
            for key, value in list(change.items()):
                if value is None:
                    del item[key]


def f61_without_limiter(data: dict[str, Any]) -> None:
    for item in data["flows"]:
        if item["id"] == "F61" and item["to"] == ["otel-collector"]:
            item["from"] = [s for s in item["from"] if s != "rate-limit"]


CONTRARY = {
    "F90 vuelve al 8083": ("F90", lambda d: edit(d, "F90", ["rate-limit"], port=8083)),
    "F90 sin el flujo": ("F90", lambda d: without(d, "F90")),
    "F90 con rate-limit en vectra-edge": ("F90", lambda d: d["workloads"]["rate-limit"].update(ns="vectra-edge")),
    "F91 sin unmeshed_source": ("F91", lambda d: edit(d, "F91", ["valkey", "sentinel"], unmeshed_source=None)),
    "F91 sin Sentinel": ("F91", lambda d: edit(d, "F91", ["valkey", "sentinel"], to=["valkey"])),
    "F91 con otro puerto": ("F91", lambda d: edit(d, "F91", ["valkey", "sentinel"], ports=[26380, 6379])),
    "F91 desde otro origen": ("F91", lambda d: edit(d, "F91", ["valkey", "sentinel"], **{"from": ["api-gateway"]})),
    "F61 sin rate-limit": ("F61", f61_without_limiter),
    "F61 sin unmeshed_source": ("F61", lambda d: edit(d, "F61", ["otel-collector"], unmeshed_source=None)),
    "F92 sin la linea de Sentinel": ("F92", lambda d: without(d, "F92", to=["sentinel"])),
    "F92 sin la linea de Valkey": ("F92", lambda d: without(d, "F92", to=["valkey"])),
    "F92 con otro puerto de Sentinel": ("F92", lambda d: edit(d, "F92", ["sentinel"], port=26380)),
    "F60 sin Envoy": ("F60", lambda d: without(d, "F60", to=["api-gateway"])),
    "F60 sin envoy-ratelimit": ("F60", lambda d: without(d, "F60", to=["rate-limit"])),
    "F60 sin el exportador": ("F60", lambda d: without(d, "F60", to=["valkey"])),
    "F60 con otro puerto del exportador": ("F60", lambda d: edit(d, "F60", ["valkey"], port=9122)),
}


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("case", CONTRARY)
def test_the_contrary_change_fails_its_check(env, case):
    flow_id, change = CONTRARY[case]
    data = copy.deepcopy(DATA)
    change(data)
    assert CHECKS[flow_id](env, data) != [], case


# --- F80 sigue generando lo mismo -------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_f80_keeps_its_network_authentication_on_5432_only(env):
    """Generalizar `unmeshed_source` a cualquier puerto no cambia F80: la NetworkAuthentication sigue solo en el 5432 de cada base."""
    docs = documents(env, DATA)
    dests = next(f for f in DATA["flows"] if f["id"] == "F80")["to"]
    mine = [d for d in docs if d["kind"] == "NetworkAuthentication" and d["metadata"]["name"].startswith("f80-")]
    assert sorted(d["metadata"]["name"] for d in mine) == sorted(f"f80-{db}-5432-operator-network" for db in dests)
    other = [d for d in docs if d["kind"] == "AuthorizationPolicy" and d["metadata"]["name"].startswith("f80-") and d["metadata"]["name"].endswith("-8000")]
    assert other and all(a["spec"]["requiredAuthenticationRefs"][0]["kind"] == "MeshTLSAuthentication" for a in other)
