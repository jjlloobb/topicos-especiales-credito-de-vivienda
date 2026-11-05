#!/usr/bin/env python3
"""Genera NetworkPolicies, politicas de Linkerd y la suite de conectividad (P-U1-01, 02).

Uso: `generate.py` escribe `generated/`; `generate.py --check` falla si difiere.
"""

import argparse
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ENVS = ("kind", "staging", "prod")
ANY_CIDR = "0.0.0.0/0"
NS_ENVS = {"vectra-mock": ("kind", "staging"), "vault": ("kind",)}


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    flows = yaml.safe_load((HERE / "flows.yaml").read_text(encoding="utf-8"))
    forbidden = yaml.safe_load((HERE / "forbidden.yaml").read_text(encoding="utf-8"))
    return flows, forbidden


def labels_of(workload: dict[str, Any]) -> dict[str, str]:
    """Selector de pods. Solo se usan etiquetas que el chart de cada unidad fija."""
    if "labels" in workload:
        return dict(workload["labels"])
    if "workload" in workload:
        return {"vectra.io/workload": workload["workload"]}
    if "component" in workload:
        return {"vectra.io/component": workload["component"]}
    if "cnpg" in workload:
        return {"cnpg.io/cluster": workload["cnpg"]}
    if workload.get("cnpg_any"):
        return {"cnpg.io/podRole": "instance"}
    if "part" in workload:
        return {"linkerd.io/control-plane-ns": workload["part"]}
    return {"app.kubernetes.io/name": workload["name"]}


def active(flow: dict[str, Any], env: str, disabled: list[str]) -> bool:
    return flow.get("enabled", True) and env in flow.get("envs", ENVS) and flow["id"] not in disabled


def ports_of(flow: dict[str, Any]) -> list[int]:
    if "target_port" in flow:
        return [flow["target_port"]]
    return flow.get("ports", [flow.get("port")])


def endpoint(name: str, data: dict[str, Any]) -> dict[str, Any]:
    if name.startswith("external:"):
        return {"kind": "external", "name": name.removeprefix("external:")}
    if name.startswith("ns:"):
        return {"kind": "ns", "ns": name.removeprefix("ns:")}
    return {"kind": "workload", "name": name, **data["workloads"][name]}


def exists_in(ep: dict[str, Any], env: str) -> bool:
    """`vectra-mock` y `vault` no existen en todos los entornos, ni como `ns:` ni como workload."""
    if ep["kind"] == "ns" and ep["ns"] in NS_ENVS:
        return env in NS_ENVS[ep["ns"]]
    return env in ep.get("envs", ENVS)


def peer(ep: dict[str, Any]) -> dict[str, Any]:
    selector: dict[str, Any] = {
        "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ep["ns"]}}
    }
    if ep["kind"] == "workload":
        selector["podSelector"] = {"matchLabels": labels_of(ep)}
    return selector


# Puertos opacos por omision de Linkerd (`proxy.opaquePorts`). Su trafico entre proxies no usa el puerto de la
# aplicacion: va siempre al 4143, tambien con `outboundTransportMode: transparent`. El `Server` sigue autorizando
# por identidad y puerto de destino.
LINKERD_OPAQUE_PORTS = {25, 587, 3306, 4444, 5432, 6379, 9300, 11211}
LINKERD_INBOUND_PORT = 4143


def network_ports(flow: dict[str, Any], ports: list[int]) -> list[int]:
    """Los puertos que la NetworkPolicy debe abrir para que el flujo funcione a traves de la malla."""
    if flow.get("unmeshed_source") is True or not LINKERD_OPAQUE_PORTS.intersection(ports):
        return ports
    return [*ports, LINKERD_INBOUND_PORT]


def pod_selector(ep: dict[str, Any]) -> dict[str, Any]:
    return {"matchLabels": labels_of(ep)} if ep["kind"] == "workload" else {}


def network_policy(
    name: str, ns: str, selector: dict[str, Any], rule_key: str, rule: dict[str, Any], flow_id: str
) -> dict[str, Any]:
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": ns, "labels": {"vectra.io/flow": flow_id}},
        "spec": {
            "podSelector": selector,
            "policyTypes": ["Ingress" if rule_key == "ingress" else "Egress"],
            rule_key: [rule],
        },
    }


def deny_all(ns: str) -> list[dict[str, Any]]:
    base = {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": {"namespace": ns}}
    deny = {
        **base,
        "metadata": {**base["metadata"], "name": "deny-all"},
        "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
    }
    dns = {
        **base,
        "metadata": {**base["metadata"], "name": "allow-dns"},
        "spec": {
            "podSelector": {},
            "policyTypes": ["Egress"],
            "egress": [
                {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                            },
                            "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                        }
                    ],
                    "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                }
            ],
        },
    }
    return [deny, dns]


def system_policies(ns: str, webhooks: list[int], api_cidr: str) -> list[dict[str, Any]]:
    """F125, F126 y F127: lo que un operador necesita dentro de su namespace, sin datos de negocio."""
    own = {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ns}}}
    api = {
        "to": [{"ipBlock": {"cidr": api_cidr}}],
        "ports": [{"protocol": "TCP", "port": 443}, {"protocol": "TCP", "port": 6443}],
    }
    documents = [
        network_policy("allow-f125-same-namespace-ingress", ns, {}, "ingress", {"from": [own]}, "F125"),
        network_policy("allow-f125-same-namespace-egress", ns, {}, "egress", {"to": [own]}, "F125"),
        network_policy("allow-f126-k8s-api", ns, {}, "egress", api, "F126"),
    ]
    if webhooks:
        rule = {"ports": [{"protocol": "TCP", "port": p} for p in webhooks]}
        documents.append(network_policy("allow-f127-webhooks", ns, {}, "ingress", rule, "F127"))
    return documents


def identity_of(source: dict[str, Any]) -> str:
    who = source["sa"] if source["kind"] == "workload" else "*"
    return f"{who}.{source['ns']}.serviceaccount.identity.linkerd.cluster.local"


def server_of(dest: dict[str, Any], port: int, protocol: str | None = None) -> dict[str, Any]:
    """Un solo `Server` por pod y puerto: Linkerd ignora los demas que seleccionen lo mismo."""
    return {
        "apiVersion": "policy.linkerd.io/v1beta3",
        "kind": "Server",
        "metadata": {"name": f"{dest['name']}-{port}", "namespace": dest["ns"]},
        "spec": {
            "podSelector": pod_selector(dest),
            "port": port,
            "proxyProtocol": protocol or ("opaque" if port in LINKERD_OPAQUE_PORTS else "unknown"),
        },
    }


def has_unmeshed_source(flow: dict[str, Any], sources: list[dict[str, Any]], port: int) -> bool:
    """Un origen fuera de la malla no presenta identidad de Linkerd: se autoriza por red (`pod_cidr`) en el `Server` del puerto.

    `unmeshed_source: true` vale para todos los origenes del flujo (F80, F91); una lista nombra los que estan fuera de la malla dentro
    de un flujo que tambien tiene origenes mallados (F61). `unmeshed_ports` limita los puertos (F80 solo lo necesita en el 5432).
    """
    unmeshed = flow.get("unmeshed_source")
    if not unmeshed or port not in flow.get("unmeshed_ports", [port]):
        return False
    return unmeshed is True or any(s.get("name") in unmeshed for s in sources)


def check_unmeshed_sources(flow: dict[str, Any], data: dict[str, Any]) -> None:
    """Una lista `unmeshed_source` solo nombra origenes del flujo: una errata dejaria el origen sin autorizacion por red y sin error."""
    unmeshed = flow.get("unmeshed_source")
    if unmeshed is None or isinstance(unmeshed, bool):
        return
    origins = {endpoint(s, data).get("name") for s in flow["from"] if not s.startswith("external:")}
    unknown = [n for n in unmeshed if n not in origins]
    if unknown:
        raise SystemExit(
            f"{flow['id']}: unmeshed_source nombra {unknown}, que no son origen del flujo ({sorted(o for o in origins if o)})"
        )


def linkerd_policy(
    flow: dict[str, Any], dest: dict[str, Any], sources: list[dict[str, Any]], port: int, pod_cidr: str
) -> list[dict[str, Any]]:
    """`AuthorizationPolicy` por flujo sobre el `Server` del puerto (P-U1-02)."""
    server_name = f"{dest['name']}-{port}"
    name = f"{flow['id'].lower()}-{dest['name']}-{port}"
    identities = [identity_of(s) for s in sources if s["kind"] in ("workload", "ns")]
    documents = [server_of(dest, port)]
    if identities:
        auth_name = f"{name}-mtls"
        documents.append(mesh_authentication(auth_name, dest["ns"], identities))
        documents.append(
            authorization(name, dest["ns"], "MeshTLSAuthentication", auth_name, server=server_name)
        )
    if has_unmeshed_source(flow, sources, port):
        auth_name = f"{name}-operator-network"
        documents.append(
            {
                "apiVersion": "policy.linkerd.io/v1alpha1",
                "kind": "NetworkAuthentication",
                "metadata": {"name": auth_name, "namespace": dest["ns"]},
                "spec": {"networks": [{"cidr": pod_cidr}]},
            }
        )
        documents.append(
            authorization(
                f"{name}-operator", dest["ns"], "NetworkAuthentication", auth_name, server=server_name
            )
        )
    return documents


def mesh_authentication(name: str, ns: str, identities: list[str]) -> dict[str, Any]:
    return {
        "apiVersion": "policy.linkerd.io/v1alpha1",
        "kind": "MeshTLSAuthentication",
        "metadata": {"name": name, "namespace": ns},
        "spec": {"identities": sorted(set(identities))},
    }


def route_policy(
    source_name: str, source: dict[str, Any], dest: dict[str, Any], port: int, routes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rutas por identidad y metodo (P-U1-13). Lo que ninguna ruta admite no se autoriza."""
    return named_route_policy(f"{dest['name']}-{source_name}", [source], dest, port, routes)


def named_route_policy(
    name: str, sources: list[dict[str, Any]], dest: dict[str, Any], port: int, routes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Una `HTTPRoute`, y su autorizacion para todos los que pueden usarla."""
    matches = []
    for route in routes:
        if "exact" in route:
            path = {"type": "Exact", "value": route["exact"]}
        elif "regex" in route:
            path = {"type": "RegularExpression", "value": route["regex"]}
        else:
            path = {"type": "RegularExpression", "value": f"{route['group']}(/.*)?"}
        matches.extend({"path": path, "method": method} for method in route["methods"])
    return [
        server_of(dest, port, protocol="HTTP/1"),
        {
            "apiVersion": "policy.linkerd.io/v1beta3",
            "kind": "HTTPRoute",
            "metadata": {"name": name, "namespace": dest["ns"]},
            "spec": {
                "parentRefs": [
                    {"group": "policy.linkerd.io", "kind": "Server", "name": f"{dest['name']}-{port}"}
                ],
                "rules": [{"matches": matches}],
            },
        },
        mesh_authentication(f"{name}-mtls", dest["ns"], [identity_of(s) for s in sources]),
        {
            "apiVersion": "policy.linkerd.io/v1alpha1",
            "kind": "AuthorizationPolicy",
            "metadata": {"name": name, "namespace": dest["ns"]},
            "spec": {
                "targetRef": {"group": "policy.linkerd.io", "kind": "HTTPRoute", "name": name},
                "requiredAuthenticationRefs": [
                    {"group": "policy.linkerd.io", "kind": "MeshTLSAuthentication", "name": f"{name}-mtls"}
                ],
            },
        },
    ]


def http_route(name: str, dest: dict[str, Any], port: int, matches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "apiVersion": "policy.linkerd.io/v1beta3",
        "kind": "HTTPRoute",
        "metadata": {"name": name, "namespace": dest["ns"]},
        "spec": {
            "parentRefs": [
                {"group": "policy.linkerd.io", "kind": "Server", "name": f"{dest['name']}-{port}"}
            ],
            "rules": [{"matches": matches}],
        },
    }


def catch_all_route(name: str, dest: dict[str, Any], port: int) -> list[dict[str, Any]]:
    """Ruta sin `AuthorizationPolicy`: lo que no admite otra da 403 medido, no 404 (INF-U8-03)."""
    return [http_route(name, dest, port, [{"path": {"type": "PathPrefix", "value": "/"}}])]


def probe_routes(
    dest: dict[str, Any], port: int, paths: list[str], node_cidr: str, pod_cidr: str
) -> list[dict[str, Any]]:
    """En un `Server` con rutas, Linkerd deja de autorizar solo las sondas del kubelet."""
    name = f"{dest['name']}-probes"
    matches = [{"path": {"type": "Exact", "value": p}, "method": "GET"} for p in paths]
    return [
        http_route(name, dest, port, matches),
        {
            "apiVersion": "policy.linkerd.io/v1alpha1",
            "kind": "NetworkAuthentication",
            "metadata": {"name": f"{name}-nodes", "namespace": dest["ns"]},
            # kubelet puede salir con la IP de tunl0 de Calico, dentro de la red de pods.
            "spec": {"networks": [{"cidr": node_cidr}, {"cidr": pod_cidr}]},
        },
        {
            "apiVersion": "policy.linkerd.io/v1alpha1",
            "kind": "AuthorizationPolicy",
            "metadata": {"name": name, "namespace": dest["ns"]},
            "spec": {
                "targetRef": {"group": "policy.linkerd.io", "kind": "HTTPRoute", "name": name},
                "requiredAuthenticationRefs": [
                    {"group": "policy.linkerd.io", "kind": "NetworkAuthentication", "name": f"{name}-nodes"}
                ],
            },
        },
    ]


def namespace_metrics_policy(
    flow: dict[str, Any], dest: dict[str, Any], sources: list[dict[str, Any]], port: int, pod_cidr: str
) -> list[dict[str, Any]]:
    """Un `Server` para todo el namespace en el puerto de metricas: F60 no nombra a cada servicio."""
    named = {**dest, "name": "metrics"}
    return linkerd_policy(flow, named, sources, port, pod_cidr)


def merged(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Quita los repetidos por tipo y nombre; une las identidades de una misma autenticacion."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for document in documents:
        key = (document["kind"], document["metadata"]["name"])
        if key not in seen:
            seen[key] = document
        elif document["kind"] == "MeshTLSAuthentication":
            seen[key]["spec"]["identities"] = sorted(
                {*seen[key]["spec"]["identities"], *document["spec"]["identities"]}
            )
    return list(seen.values())


def authorization(name: str, ns: str, kind: str, auth: str, server: str | None = None) -> dict[str, Any]:
    return {
        "apiVersion": "policy.linkerd.io/v1alpha1",
        "kind": "AuthorizationPolicy",
        "metadata": {"name": name, "namespace": ns},
        "spec": {
            "targetRef": {"group": "policy.linkerd.io", "kind": "Server", "name": server or name},
            "requiredAuthenticationRefs": [{"group": "policy.linkerd.io", "kind": kind, "name": auth}],
        },
    }


def build(
    env: str, data: dict[str, Any], forbidden: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meshed = set(data["meshed_namespaces"])
    for ns in [*data["meshed_namespaces"], *data["system_namespaces"]]:
        if env not in NS_ENVS.get(ns, ENVS):
            continue
        docs[ns].extend(deny_all(ns))
        if ns in data["system_internal"]:
            docs[ns].extend(
                system_policies(ns, data["system_internal"][ns]["webhooks"], data["api_server_cidr"][env])
            )
    allowed: list[dict[str, Any]] = []
    disabled = data["env_disabled"][env]
    for flow in data["flows"]:
        if not active(flow, env, disabled):
            continue
        check_unmeshed_sources(flow, data)
        pairs = [(flow["from"], flow["to"])] + [([a], [b]) for a, b in flow.get("also", [])]
        for sources_raw, dests_raw in pairs:
            sources = [endpoint(s, data) for s in sources_raw]
            dests = [endpoint(d, data) for d in dests_raw]
            sources = [s for s in sources if exists_in(s, env)]
            dests = [d for d in dests if exists_in(d, env)]
            ports = ports_of(flow)
            port_rules = [{"protocol": "TCP", "port": p} for p in network_ports(flow, ports)]
            for dest in dests:
                for src in sources:
                    allowed.append(
                        {
                            "flow": flow["id"],
                            "from": src.get("name") or src.get("ns"),
                            "to": dest.get("name") or dest.get("ns"),
                            "ports": ports,
                        }
                    )
                    if src["kind"] != "external":
                        target = {"ipBlock": {"cidr": ANY_CIDR}} if dest["kind"] == "external" else peer(dest)
                        src_label = src.get("name") or src["ns"]
                        dest_label = dest.get("name") or dest.get("ns")
                        docs[src["ns"]].append(
                            network_policy(
                                f"allow-{flow['id'].lower()}-{src_label}-to-{dest_label}-egress"[:63].rstrip(
                                    "-"
                                ),
                                src["ns"],
                                pod_selector(src),
                                "egress",
                                {"to": [target], "ports": port_rules},
                                flow["id"],
                            )
                        )
                if dest["kind"] == "external":
                    continue
                internal = [s for s in sources if s["kind"] != "external"]
                dest_label = dest.get("name") or dest["ns"]
                source_peers = [peer(s) for s in internal]
                rule: dict[str, Any] = {"ports": port_rules}
                if len(source_peers) == len(sources):
                    rule = {"from": source_peers, "ports": port_rules}
                docs[dest["ns"]].append(
                    network_policy(
                        f"allow-{flow['id'].lower()}-to-{dest_label}-ingress"[:63].rstrip("-"),
                        dest["ns"],
                        pod_selector(dest),
                        "ingress",
                        rule,
                        flow["id"],
                    )
                )
                if dest["kind"] == "ns" and dest["ns"] in meshed and internal:
                    for port in ports:
                        docs[dest["ns"]].extend(
                            namespace_metrics_policy(flow, dest, internal, port, data["pod_cidr"][env])
                        )
                if dest["kind"] == "workload" and dest["ns"] in meshed and internal:
                    routed = data["http_routes"].get(dest["name"])
                    for port in ports:
                        if not routed:
                            docs[dest["ns"]].extend(
                                linkerd_policy(flow, dest, internal, port, data["pod_cidr"][env])
                            )
                            continue
                        for route_name, route in routed.get("_routes", {}).items():
                            clients = [endpoint(s, data) for s in route["sources"]]
                            docs[dest["ns"]].extend(
                                named_route_policy(
                                    f"{dest['name']}-{route_name}",
                                    [c for c in clients if exists_in(c, env)],
                                    dest,
                                    port,
                                    route["matches"],
                                )
                            )
                        for source_name in [
                            s
                            for s in sources_raw
                            if "_routes" not in routed and exists_in(endpoint(s, data), env)
                        ]:
                            source = endpoint(source_name, data)
                            docs[dest["ns"]].extend(
                                route_policy(source_name, source, dest, port, routed[source_name])
                            )
                        if "_catch_all" in routed:
                            docs[dest["ns"]].extend(catch_all_route(routed["_catch_all"], dest, port))
                        if "_probes" in routed:
                            docs[dest["ns"]].extend(
                                probe_routes(
                                    dest,
                                    port,
                                    routed["_probes"],
                                    data["node_cidr"][env],
                                    data["pod_cidr"][env],
                                )
                            )
    for key, subject in sorted(data["k_egress"].items()):
        workload = data["workloads"][subject] if isinstance(subject, str) else subject
        docs[workload["ns"]].append(
            network_policy(
                f"allow-k8s-api-{key.lower()}",
                workload["ns"],
                {"matchLabels": labels_of(workload)},
                "egress",
                {
                    "to": [{"ipBlock": {"cidr": data["api_server_cidr"][env]}}],
                    "ports": [{"protocol": "TCP", "port": 443}, {"protocol": "TCP", "port": 6443}],
                },
                key,
            )
        )
    blocked = [c for c in forbidden["forbidden"] if env in c.get("envs", ENVS)]
    return {ns: merged(items) for ns, items in docs.items()}, {
        "env": env,
        "allowed": allowed,
        "blocked": blocked,
    }


def write(out: Path, data: dict[str, Any], forbidden: dict[str, Any]) -> None:
    for env in ENVS:
        docs, suite = build(env, data, forbidden)
        folder = out / env
        folder.mkdir(parents=True, exist_ok=True)
        for ns, items in sorted(docs.items()):
            text = "---\n".join(yaml.safe_dump(item, sort_keys=True) for item in items)
            (folder / f"{ns}.yaml").write_text(text, encoding="utf-8")
        (folder / "connectivity-suite.yaml").write_text(
            yaml.safe_dump(suite, sort_keys=True), encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data, forbidden = load()
    target = HERE / "generated"
    if not args.check:
        shutil.rmtree(target, ignore_errors=True)
        write(target, data, forbidden)
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "generated"
        write(fresh, data, forbidden)
        old = (
            {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            if target.exists()
            else {}
        )
        new = {p.relative_to(fresh): p.read_bytes() for p in fresh.rglob("*") if p.is_file()}
    if old != new:
        print("platform/network/generated difiere: corre generate.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
