"""Las metricas del proxy de Linkerd que lee una alerta tienen quien las raspe (U01-T09; hallazgo F-02 de la revision de U08-T05).

Mundo cerrado, sin cluster y sin Docker. Por entorno se descubren (no se listan) las `PrometheusRule` que Argo CD instalaria, y de cada
`expr` salen las metricas del proxy y sus selectores. Cada una necesita: un `PodMonitor` que alcance un pod inyectado del namespace que la
regla filtra, un puerto que ese pod declare, la etiqueta `namespace` intacta, la familia viva tras los `metricRelabelings`, un flujo de
`prometheus` a ese namespace por ese puerto con su `NetworkPolicy`, su `Server` y la autorizacion por identidad, y las sondas del proxy
(`/live`, `/ready`) sin quedar fuera de un `Server` con rutas.

El pod inyectado se modela desde las fuentes: el namespace (`linkerd.io/inject: enabled`), el workload (no lo desactiva) y lo que el
inyector anade, que se lee del chart de `linkerd-control-plane` fijado en `components.yaml` (su `PodMonitor` del proxy y `proxy.ports.admin`).
Lo que solo se ve en un cluster (la serie real, el raspado con mTLS) queda para U12 Paso 18 (cierre-demo.md, "Pendiente en U12").
"""

import importlib.util
import re
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from integration import CHARTS, CONFIG, ROOT, chart_renders, directory_docs, helm, is_chart, pod_spec

PLATFORM = ROOT / "platform"
ENVS = ("kind", "staging", "prod")
Doc = dict[str, Any]
World = dict[str, Any]

#: Fuente de las familias del proxy y de sus etiquetas: https://linkerd.io/2-edge/reference/proxy-metrics/ (pagina "Proxy Metrics",
#: consultada el 2026-11-13 para la version 2026.10.2 de `components.yaml`, chart edge `linkerd-control-plane`).
LINKERD_VERSION = "2026.10.2"
PROXY_FAMILIES = (
    "inbound_",
    "outbound_",
    "request_total",
    "response_total",
    "response_latency_ms",
    "route_",
    "tcp_",
    "identity_cert_",
    "control_",
)
#: Etiquetas que Prometheus pone al target (Prometheus Operator: `namespace`, `pod`, `container`, `job`, `instance`), no el proxy.
TARGET_LABELS = frozenset({"namespace", "pod", "container", "job", "instance"})
#: Etiquetas por metrica, segun la pagina de arriba. Las del proxy que esa pagina da para todas las metricas HTTP son `direction` y `tls`
#: (`authority` se omite en las entrantes). La pagina describe `route_group`, `route_kind`, `route_name` y `route_namespace` como etiquetas
#: comunes de las metricas `inbound_http_*` de ruta ("the route resource through which the proxy discovered the route binding"), pero NO lista
#: las de `inbound_http_authz_deny_total`: que esa serie traiga `route_name` esta POR CONFIRMAR EN U12 (Paso 18, con la serie real tras el 403).
FAMILY_LABELS: dict[str, frozenset[str]] = {
    "inbound_http_authz_deny_total": frozenset(
        {
            "direction",
            "tls",
            "route_group",
            "route_kind",
            "route_name",
            "route_namespace",
        }  # POR CONFIRMAR EN U12
    ),
    "inbound_http_authz_allow_total": frozenset({"direction", "tls", "authz_name"}),
    "inbound_http_route_not_found_total": frozenset({"direction", "tls"}),
}
#: Quien reescribe `namespace` rompe el filtro de la regla: el proxy no lo emite, lo pone Prometheus con el namespace del pod.
SAFE_ACTIONS = {"keep", "drop"}
INJECT = "linkerd.io/inject"
PROBES = ("/live", "/ready")

_TOKEN = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*")
_SELECTOR = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s*\{([^{}]*)\}")
_MATCHER = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(=~|!~|!=|=)\s*\"((?:[^\"\\]|\\.)*)\"")


def _network() -> Any:
    spec = importlib.util.spec_from_file_location("network_generate", PLATFORM / "network/generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_proxy_metric(name: str) -> bool:
    return any(
        name.startswith(p) if p.endswith("_") else name == p or name.startswith(p + "_")
        for p in PROXY_FAMILIES
    )


def metric_reads(expr: str) -> list[tuple[str, dict[str, tuple[str, str]]]]:
    """Cada lectura de una metrica del proxy en `expr`: su nombre y sus matchers `{etiqueta: (operador, valor)}`."""
    reads: list[tuple[str, dict[str, tuple[str, str]]]] = []
    selectors = {m.span(): m for m in _SELECTOR.finditer(expr)}
    for m in selectors.values():
        if is_proxy_metric(m.group(1)):
            reads.append((m.group(1), {k: (op, v) for k, op, v in _MATCHER.findall(m.group(2))}))
    bare = _SELECTOR.sub(" ", re.sub(r'"[^"]*"', '""', expr))
    for token in _TOKEN.findall(bare):
        if is_proxy_metric(token) and not any(token == name for name, _ in reads):
            reads.append((token, {}))
    return reads


def _fits(selector: dict[str, Any], labels: dict[str, str]) -> bool:
    for key, value in (selector.get("matchLabels") or {}).items():
        if labels.get(key) != value:
            return False
    for expr in selector.get("matchExpressions") or []:
        key, op, values = expr["key"], expr["operator"], expr.get("values", [])
        present = key in labels
        if (op == "In" and labels.get(key) not in values) or (op == "NotIn" and labels.get(key) in values):
            return False
        if (op == "Exists" and not present) or (op == "DoesNotExist" and present):
            return False
    return True


@cache
def linkerd_injection() -> dict[str, Any]:
    """Lo que el inyector anade a un pod, leido del chart fijado: no esta en los renders (lo pone la admision)."""
    component = next(c for c in CONFIG["components"] if c["name"] == "linkerd-control-plane")
    folder = CHARTS / "linkerd-control-plane" / component["chart"]
    if not (folder / "Chart.yaml").is_file():
        pytest.fail("falta platform/.charts/linkerd-control-plane: corre `make -C platform charts`")
    version = yaml.safe_load((folder / "Chart.yaml").read_text(encoding="utf-8"))["version"]
    assert version == component["version"] == LINKERD_VERSION, (
        f"el chart es {version}, components.yaml {component['version']} y esta prueba cita la documentacion de {LINKERD_VERSION}: "
        "revisa PROXY_FAMILIES y FAMILY_LABELS contra la pagina de metricas de esa version"
    )
    values = yaml.safe_load((folder / "values.yaml").read_text(encoding="utf-8"))
    rendered = helm(
        "linkerd-control-plane",
        folder,
        component["namespace"],
        [ROOT / f for f in component["values"]],
        "--set-string",
        "identityTrustAnchorsPEM=x",
        "--set",
        "podMonitor.enabled=true",
    )
    monitor = next(
        d for d in rendered if d["kind"] == "PodMonitor" and d["metadata"]["name"] == "linkerd-proxy"
    )
    keep = next(
        r for r in monitor["spec"]["podMetricsEndpoints"][0]["relabelings"] if r.get("action") == "keep"
    )
    container, port_name, control_plane = keep["regex"].strip("^$").split(";")
    (label,) = [k for k in monitor["metadata"]["labels"] if k.endswith("control-plane-ns")]
    return {
        "label": label,
        "label_value": control_plane,
        "container": container,
        "port_name": port_name,
        "port": values["proxy"]["ports"]["admin"],
    }


def _installed(env: str) -> list[Doc]:
    """Lo que Argo CD aplicaria de lo propio (directorios y charts del repositorio); los charts upstream no traen reglas de estas."""
    documents: list[Doc] = []
    for component in CONFIG["components"]:
        if env not in component.get("envs", ENVS) or "path" not in component:
            continue
        if (ROOT / component["path"] / "Chart.yaml").is_file():
            for name, rendered_env, namespace, values in chart_renders(
                component["path"], env, component["namespace"]
            ):
                if name == component["name"] and rendered_env == env:
                    documents += helm(name, ROOT / component["path"], namespace, values)
        elif not is_chart(component):
            documents += directory_docs(component, env)
    return documents


@cache
def build(env: str) -> World:
    network = _network()
    data = network.load()[0]
    documents = _installed(env)
    rules = [
        (d["metadata"]["name"], rule["alert"] if "alert" in rule else rule["record"], rule["expr"])
        for d in documents
        if d["kind"] == "PrometheusRule"
        for group in d["spec"]["groups"]
        for rule in group["rules"]
    ]
    workloads = []
    for d in documents:
        spec = pod_spec(d) if d.get("kind") else None
        if spec is None:
            continue
        template = (
            d["spec"]["template"] if d["kind"] != "CronJob" else d["spec"]["jobTemplate"]["spec"]["template"]
        )
        workloads.append(
            {
                "name": d["metadata"]["name"],
                "ns": d["metadata"]["namespace"],
                "labels": dict(template.get("metadata", {}).get("labels", {})),
                "annotations": dict(template.get("metadata", {}).get("annotations", {})),
                "ports": [
                    {"name": p.get("name"), "number": p["containerPort"]}
                    for c in [*spec.get("initContainers", []), *spec.get("containers", [])]
                    for p in c.get("ports", [])
                ],
            }
        )
    prometheus = data["workloads"]["prometheus"]
    return {
        "env": env,
        "rules": rules,
        "monitors": [d for d in documents if d["kind"] == "PodMonitor"],
        "namespaces": {d["metadata"]["name"]: d for d in documents if d["kind"] == "Namespace"},
        "workloads": workloads,
        "network": [
            d
            for d in documents
            if d["kind"]
            in {"NetworkPolicy", "Server", "HTTPRoute", "MeshTLSAuthentication", "AuthorizationPolicy"}
        ],
        "flows": [f for f in data["flows"] if network.active(f, env, data["env_disabled"][env])],
        "prometheus_identity": f"{prometheus['sa']}.{prometheus['ns']}.serviceaccount.identity.linkerd.cluster.local",
        "prometheus_ns": prometheus["ns"],
        "injection": linkerd_injection(),
    }


def injected_pods(world: World, ns: str) -> list[Doc]:
    """Los pods de `ns` con el proxy inyectado: etiqueta y puerto de `linkerd_injection()`, salvo que el workload lo desactive."""
    namespace = world["namespaces"].get(ns)
    if not namespace or namespace["metadata"].get("annotations", {}).get(INJECT) != "enabled":
        return []
    injection = world["injection"]
    pods = []
    for w in world["workloads"]:
        if w["ns"] != ns or w["annotations"].get(INJECT) == "disabled":
            continue
        pods.append(
            {
                "name": w["name"],
                "labels": {**w["labels"], injection["label"]: injection["label_value"]},
                "ports": [*w["ports"], {"name": injection["port_name"], "number": injection["port"]}],
            }
        )
    return pods


def _reaches(monitor: Doc, ns: str) -> bool:
    selector = monitor["spec"].get("namespaceSelector") or {}
    if selector.get("any"):
        return True
    return ns in (selector.get("matchNames") or [monitor["metadata"]["namespace"]])


def _port_of(endpoint: Doc, pod: Doc) -> int | None:
    for p in pod["ports"]:
        if endpoint.get("port") is not None and p["name"] == endpoint["port"]:
            return int(p["number"])
        if endpoint.get("portNumber") is not None and p["number"] == endpoint["portNumber"]:
            return int(p["number"])
    return None


def _survives(endpoint: Doc, metric: str) -> bool:
    for relabel in endpoint.get("metricRelabelings") or []:
        if (
            relabel.get("sourceLabels") != ["__name__"]
            or relabel.get("action", "replace") not in SAFE_ACTIONS
        ):
            continue
        matched = re.fullmatch(relabel.get("regex", "(.*)"), metric) is not None
        if (relabel["action"] == "keep") != matched:
            return False
    return True


def _rewrites_namespace(endpoint: Doc) -> bool:
    entries = [*(endpoint.get("relabelings") or []), *(endpoint.get("metricRelabelings") or [])]
    return bool(endpoint.get("honorLabels")) or any(
        r.get("targetLabel") == "namespace" and r.get("action", "replace") == "replace" for r in entries
    )


def _scrape_problems(world: World, who: str, metric: str, ns: str) -> tuple[list[str], int | None]:
    """El monitor, el puerto, `namespace` y el filtro de familias. Devuelve el puerto que alcanza el raspado."""
    env, pods = world["env"], injected_pods(world, ns)
    if not pods:
        return [f"{who}: {env} no tiene pods de {ns} con el proxy inyectado: {metric} no existe"], None
    notes: list[str] = []
    for monitor in world["monitors"]:
        if not _reaches(monitor, ns):
            continue
        for endpoint in monitor["spec"].get("podMetricsEndpoints", []):
            for pod in pods:
                if not _fits(monitor["spec"].get("selector") or {}, pod["labels"]):
                    continue
                port = _port_of(endpoint, pod)
                if port is None:
                    notes.append(
                        f"el PodMonitor {monitor['metadata']['name']} apunta a un puerto que el proxy no declara ({endpoint.get('port') or endpoint.get('portNumber')})"
                    )
                elif _rewrites_namespace(endpoint):
                    notes.append(
                        f"el PodMonitor {monitor['metadata']['name']} reescribe `namespace` o usa honorLabels"
                    )
                elif not _survives(endpoint, metric):
                    notes.append(f"los metricRelabelings de {monitor['metadata']['name']} tiran {metric}")
                else:
                    return [], port
    if notes:
        return [f"{who}: {metric} ({ns}, {env}): {'; '.join(notes)}"], None
    near = [m["metadata"]["name"] for m in world["monitors"] if _reaches(m, ns)]
    return [
        f"{who}: falta el monitor: ningun PodMonitor de {env} alcanza el proxy de los pods de {ns} para {metric}"
        f" (namespaceSelector y selector; los que alcanzan el namespace: {near or 'ninguno'})"
    ], None


def _flow_problems(world: World, who: str, metric: str, ns: str, port: int) -> list[str]:
    env, found = world["env"], []
    who = f"{who}: {metric} ({ns}, {env})"
    flows = [
        f
        for f in world["flows"]
        if "prometheus" in f["from"] and f"ns:{ns}" in f["to"] and port in f.get("ports", [f.get("port")])
    ]
    if not flows:
        return [
            f"{who}: falta el flujo de prometheus a ns:{ns} por el puerto {port} en {env} (F60) para {metric}"
        ]
    objects = [d for d in world["network"] if d["metadata"].get("namespace") == ns]
    if not any(
        d["kind"] == "NetworkPolicy"
        and "Ingress" in d["spec"].get("policyTypes", [])
        and any(p["port"] == port for rule in d["spec"].get("ingress", []) for p in rule.get("ports", []))
        for d in objects
    ):
        found.append(f"{who}: {env} no tiene NetworkPolicy de entrada en {ns} para el puerto {port}")
    servers = [d for d in objects if d["kind"] == "Server" and d["spec"].get("port") == port]
    if not servers:
        return [
            *found,
            f"{who}: {env} no tiene un Server de Linkerd en {ns} para el puerto {port}: la malla lo negaria por omision",
        ]
    server = servers[0]["metadata"]["name"]
    mtls = {d["metadata"]["name"]: d for d in objects if d["kind"] == "MeshTLSAuthentication"}
    authorized = False
    for d in objects:
        if d["kind"] != "AuthorizationPolicy" or d["spec"]["targetRef"] != {
            "group": "policy.linkerd.io",
            "kind": "Server",
            "name": server,
        }:
            continue
        for ref in d["spec"]["requiredAuthenticationRefs"]:
            if ref["kind"] == "MeshTLSAuthentication" and world["prometheus_identity"] in mtls.get(
                ref["name"], {}
            ).get("spec", {}).get("identities", []):
                authorized = True
    if not authorized:
        found.append(
            f"{who}: el Server {server} de {ns} ({env}) no autoriza la identidad {world['prometheus_identity']}"
        )
    routes = [
        d
        for d in objects
        if d["kind"] == "HTTPRoute"
        and any(r.get("kind") == "Server" and r["name"] == server for r in d["spec"].get("parentRefs", []))
    ]
    paths = {
        m["path"]["value"]
        for d in routes
        for rule in d["spec"].get("rules", [])
        for m in rule.get("matches", [])
        if "path" in m
    }
    if routes and not all(p in paths for p in PROBES):
        found.append(
            f"{who}: el Server {server} de {ns} ({env}) tiene rutas {sorted(paths)} y no las de las sondas {list(PROBES)}: "
            "Linkerd dejaria de autorizar /live y /ready del proxy"
        )
    return found


def problems(world: World) -> list[str]:
    """Cada defecto nombra el entorno, la regla, la metrica y el namespace."""
    found: list[str] = []
    for _, rule, expr in world["rules"]:
        who = f"{world['env']}/{rule}"
        for metric, matchers in metric_reads(expr):
            operator, ns = matchers.get("namespace", (None, None))
            if operator != "=" or ns is None:
                found.append(
                    f"{who}: lee {metric} sin filtrar por un `namespace` exacto: no se sabe que monitor la necesita"
                )
                continue
            if ns not in world["namespaces"]:
                continue  # el namespace no existe en este entorno (el mock no va a prod): no hay serie que raspar
            labels = TARGET_LABELS | FAMILY_LABELS.get(metric, frozenset())
            if metric not in FAMILY_LABELS:
                found.append(
                    f"{who}: {metric} no tiene sus etiquetas en FAMILY_LABELS (fuente: linkerd.io/2-edge/reference/proxy-metrics)"
                )
            found += [
                f"{who}: {metric} ({ns}, {world['env']}) filtra por la etiqueta `{label}`, que la familia no trae"
                for label in matchers
                if label not in labels
            ]
            scrape, port = _scrape_problems(world, who, metric, ns)
            found += scrape
            if port is not None:
                found += _flow_problems(world, who, metric, ns, port)
            else:
                # sin monitor tampoco se sabe el puerto: se pide el flujo del puerto del proxy, que es el que falta
                found += [
                    m
                    for m in _flow_problems(world, who, metric, ns, world["injection"]["port"])
                    if "falta el flujo" in m
                ]
    return list(dict.fromkeys(found))  # la expresion de CoreWriteAttempt lee la misma serie dos veces


def _reads(env: str) -> list[tuple[str, str]]:
    return [(rule, metric) for _, rule, expr in build(env)["rules"] for metric, _ in metric_reads(expr)]


@pytest.mark.parametrize("env", ENVS)
def test_the_rules_that_read_the_proxy_are_discovered(env: str) -> None:
    reads = _reads(env)
    if env == "kind":
        assert ("CoreWriteAttempt", "inbound_http_authz_deny_total") in reads, reads
    if env == "prod":
        assert "vectra-mock" not in build(env)["namespaces"], "el mock no va a prod"


@pytest.mark.parametrize("env", ENVS)
def test_every_proxy_metric_a_rule_reads_is_scraped_and_reachable(env: str) -> None:
    found = problems(build(env))
    assert not found, "\n" + "\n".join(found)


@pytest.mark.parametrize("env", ENVS)
def test_labels_a_rule_filters_by_belong_to_the_family(env: str) -> None:
    world = build(env)
    for _, rule, expr in world["rules"]:
        for metric, matchers in metric_reads(expr):
            allowed = TARGET_LABELS | FAMILY_LABELS[metric]
            assert set(matchers) <= allowed, (
                f"{env}/{rule}: {metric} filtra por {sorted(set(matchers) - allowed)}"
            )


def test_labels_cite_their_source() -> None:
    text = Path(__file__).read_text(encoding="utf-8")
    assert "https://linkerd.io/" in text and LINKERD_VERSION in text


def test_the_expression_parser_reads_the_alert() -> None:
    expr = (
        'increase(vectra_core_write_attempts_total[5m]) > 0 or sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})'
        ' - (sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"} offset 5m) or vector(0)) > 0'
    )
    found = metric_reads(expr)
    assert {name for name, _ in found} == {"inbound_http_authz_deny_total"}
    assert found[0][1] == {"namespace": ("=", "vectra-mock"), "route_name": ("=", "core-mock-catch-all")}


# --- Mutaciones: cada desajuste se detecta, sobre copias en memoria del mundo de kind ---------------------------------------------------


def _mutated(change: Any, env: str = "kind") -> list[str]:
    world = deepcopy(build(env))
    change(world)
    return problems(world)


def _monitor(world: World) -> Doc:
    return next(m for m in world["monitors"] if m["metadata"]["name"] == "linkerd-proxy")


def _expect(found: list[str], *texts: str) -> None:
    base = ("kind/CoreWriteAttempt", "inbound_http_authz_deny_total", "vectra-mock", "kind")
    assert any(all(t in m for t in (*base, *texts)) for m in found), found


def test_mutation_baseline_is_clean() -> None:
    assert problems(build("kind")) == []


def test_mutation_a_without_the_monitor() -> None:
    _expect(
        _mutated(
            lambda w: w.update(
                {"monitors": [m for m in w["monitors"] if m["metadata"]["name"] != "linkerd-proxy"]}
            )
        ),
        "falta el monitor",
    )


def test_mutation_b_namespace_selector_without_the_mock() -> None:
    _expect(
        _mutated(lambda w: _monitor(w)["spec"].update({"namespaceSelector": {"matchNames": ["vectra-app"]}})),
        "falta el monitor",
    )


def test_mutation_c_selector_with_a_label_the_pod_lacks() -> None:
    _expect(
        _mutated(
            lambda w: _monitor(w)["spec"]["selector"]["matchLabels"].update(
                {"app.kubernetes.io/name": "otro"}
            )
        ),
        "falta el monitor",
    )


@pytest.mark.parametrize("key, value", [("port", "admin-http"), ("portNumber", 4190)])
def test_mutation_d_port_the_proxy_does_not_declare(key: str, value: Any) -> None:
    def change(world: World) -> None:
        endpoint = _monitor(world)["spec"]["podMetricsEndpoints"][0]
        endpoint.pop("port", None)
        endpoint[key] = value

    _expect(_mutated(change), "no declara")


def test_mutation_e_keep_without_the_family() -> None:
    def change(world: World) -> None:
        _monitor(world)["spec"]["podMetricsEndpoints"][0]["metricRelabelings"] = [
            {"sourceLabels": ["__name__"], "action": "keep", "regex": "inbound_http_route_not_found_total"}
        ]

    _expect(_mutated(change), "tiran")


def test_mutation_e_drop_that_throws_the_family() -> None:
    def change(world: World) -> None:
        _monitor(world)["spec"]["podMetricsEndpoints"][0]["metricRelabelings"] = [
            {"sourceLabels": ["__name__"], "action": "drop", "regex": "inbound_http_authz_.+"}
        ]

    _expect(_mutated(change), "tiran")


def test_mutation_f_without_the_flow() -> None:
    def change(world: World) -> None:
        world["flows"] = [
            f
            for f in world["flows"]
            if not ("prometheus" in f["from"] and 4191 in f.get("ports", [f.get("port")]))
        ]

    _expect(_mutated(change), "falta el flujo")


def test_mutation_f_flow_disabled_in_kind() -> None:
    def change(world: World) -> None:
        network = _network()
        data = network.load()[0]
        for flow in data["flows"]:
            if flow["id"] == "F60":
                flow["envs"] = ["staging"]
        world["flows"] = [f for f in data["flows"] if network.active(f, "kind", [])]

    _expect(_mutated(change), "falta el flujo")


def test_mutation_f_without_the_server() -> None:
    _expect(
        _mutated(
            lambda w: w.update(
                {
                    "network": [
                        d
                        for d in w["network"]
                        if not (d["kind"] == "Server" and d["spec"].get("port") == 4191)
                    ]
                }
            )
        ),
        "Server",
    )


def test_mutation_f_without_the_network_policy() -> None:
    def change(world: World) -> None:
        for d in world["network"]:
            if d["kind"] == "NetworkPolicy" and d["metadata"].get("namespace") == "vectra-mock":
                for rule in d["spec"].get("ingress", []):
                    rule["ports"] = [p for p in rule.get("ports", []) if p["port"] != 4191]

    _expect(_mutated(change), "NetworkPolicy")


def test_mutation_f_authorization_for_another_identity() -> None:
    def change(world: World) -> None:
        world["prometheus_identity"] = (
            "otro.vectra-observability.serviceaccount.identity.linkerd.cluster.local"
        )

    _expect(_mutated(change), "no autoriza la identidad")


@pytest.mark.parametrize("where", ["relabelings", "metricRelabelings"])
def test_mutation_g_relabeling_that_sets_namespace(where: str) -> None:
    def change(world: World) -> None:
        endpoint = _monitor(world)["spec"]["podMetricsEndpoints"][0]
        endpoint.setdefault(where, []).append(
            {"targetLabel": "namespace", "replacement": "vectra-observability"}
        )

    _expect(_mutated(change), "reescribe `namespace`")


def test_mutation_g_honor_labels() -> None:
    _expect(
        _mutated(lambda w: _monitor(w)["spec"]["podMetricsEndpoints"][0].update({"honorLabels": True})),
        "reescribe `namespace`",
    )


def test_mutation_h_route_on_the_server_without_the_probes() -> None:
    def change(world: World) -> None:
        world["network"].append(
            {
                "kind": "HTTPRoute",
                "metadata": {"name": "metrics-4191", "namespace": "vectra-mock"},
                "spec": {
                    "parentRefs": [{"group": "policy.linkerd.io", "kind": "Server", "name": "metrics-4191"}],
                    "rules": [{"matches": [{"path": {"type": "Exact", "value": "/metrics"}}]}],
                },
            }
        )

    _expect(_mutated(change), "sondas")


def test_mutation_h_route_with_the_probes_is_fine() -> None:
    def change(world: World) -> None:
        world["network"].append(
            {
                "kind": "HTTPRoute",
                "metadata": {"name": "metrics-4191", "namespace": "vectra-mock"},
                "spec": {
                    "parentRefs": [{"group": "policy.linkerd.io", "kind": "Server", "name": "metrics-4191"}],
                    "rules": [
                        {"matches": [{"path": {"type": "Exact", "value": p}} for p in ("/metrics", *PROBES)]}
                    ],
                },
            }
        )

    assert _mutated(change) == []


def test_mutation_i_rule_filters_by_a_label_the_family_lacks() -> None:
    def change(world: World) -> None:
        world["rules"] = [(f, r, e.replace("route_name", "route")) for f, r, e in world["rules"]]

    _expect(_mutated(change), "`route`", "no trae")


def test_mutation_j_pod_without_the_proxy_injected() -> None:
    def change(world: World) -> None:
        for w in world["workloads"]:
            w["annotations"][INJECT] = "disabled"

    _expect(_mutated(change), "no tiene pods de vectra-mock")


def test_mutation_k_namespace_without_injection() -> None:
    def change(world: World) -> None:
        world["namespaces"]["vectra-mock"]["metadata"]["annotations"][INJECT] = "disabled"

    _expect(_mutated(change), "no tiene pods de vectra-mock")
