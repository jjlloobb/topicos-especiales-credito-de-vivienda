"""U01-T14: la malla admite lo que no trae identidad de Linkerd: el trafico externo al gateway y las sondas del kubelet.

Con `default-inbound-policy: deny`, un puerto sin autorizacion rechaza al origen. Dos clases de trafico legitimo quedaban fuera:
- los flujos con origen `external:` hacia un workload mallado (F01, F07, F08 al 10443 del gateway), que solo tenian NetworkPolicy;
- las sondas del kubelet por HTTPS o TCP (Keycloak sonda `/auth/health` por HTTPS en el 9000), que el proxy no ve como HTTP.

Las pruebas no llaman a ningun binario: leen `flows.yaml`, lo generado y los manifiestos versionados. Cada comprobacion tiene su cambio
contrario: aplicado en una copia de los datos o de lo generado, falla.
"""

import copy
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from generate import ENVS, active, build, endpoint, exists_in, labels_of, load, ports_of

ROOT = Path(__file__).resolve().parents[3]
DATA, FORBIDDEN = load()
Check = list[str]
Doc = dict[str, Any]
POD_TEMPLATES = ("Deployment", "StatefulSet", "DaemonSet", "Job")
PROBES = ("startupProbe", "livenessProbe", "readinessProbe")
#: Manifiestos versionados con pods: se leen tal cual, sin helm (la CI no tiene `platform/.tools`).
RENDERED = (
    "identity-edge/keycloak/rendered",
    "identity-edge/charts/valkey/rendered",
    "identity-edge/jobs/rendered",
    "platform/rendered",
)
TEMPLATE_DIRS = (
    "*/chart/templates",
    "*/chart/*/templates",
    "identity-edge/charts/*/templates",
    "platform/*/chart/templates",
)


def generated(env: str, data: dict[str, Any] = DATA) -> dict[str, list[Doc]]:
    return build(env, data, FORBIDDEN)[0]


def networks_of(docs: list[Doc], ns: str, target_kind: str, target_name: str) -> set[str]:
    """Los rangos de red que alguna `AuthorizationPolicy` admite sobre el `Server` o la `HTTPRoute`."""
    auths = {d["metadata"]["name"]: d for d in docs if d["kind"] == "NetworkAuthentication"}
    found: set[str] = set()
    for policy in (d for d in docs if d["kind"] == "AuthorizationPolicy"):
        target = policy["spec"]["targetRef"]
        if target["kind"] != target_kind or target["name"] != target_name:
            continue
        for ref in policy["spec"]["requiredAuthenticationRefs"]:
            if ref["kind"] == "NetworkAuthentication" and ref["name"] in auths:
                found |= {n["cidr"] for n in auths[ref["name"]]["spec"]["networks"]}
    return found


def servers_of(docs: list[Doc], workload: dict[str, Any], port: int) -> list[Doc]:
    selector = {"matchLabels": labels_of(workload)}
    return [
        d
        for d in docs
        if d["kind"] == "Server" and d["spec"]["port"] == port and d["spec"]["podSelector"] == selector
    ]


def external_gaps(env: str, data: dict[str, Any], docs: dict[str, list[Doc]]) -> Check:
    """Cada flujo activo con origen `external:` hacia un pod mallado: el `Server` del puerto admite el rango externo del entorno."""
    gaps: Check = []
    disabled = data["env_disabled"][env]
    for flow in (f for f in data["flows"] if active(f, env, disabled)):
        pairs = [(flow["from"], flow["to"])] + [([a], [b]) for a, b in flow.get("also", [])]
        for sources_raw, dests_raw in pairs:
            if not any(s.startswith("external:") for s in sources_raw):
                continue
            for dest in (e for e in (endpoint(d, data) for d in dests_raw) if exists_in(e, env)):
                if dest["kind"] == "external" or dest["ns"] not in data["meshed_namespaces"]:
                    continue
                if dest["kind"] != "workload":
                    gaps.append(
                        f"{flow['id']}: destino {dest} es un namespace entero; el generador no lo autoriza"
                    )
                    continue
                for port in ports_of(flow):
                    found = servers_of(docs.get(dest["ns"], []), dest, port)
                    if len(found) != 1:
                        gaps.append(f"{env} {flow['id']}: {len(found)} Server para {dest['name']}:{port}")
                        continue
                    cidrs = networks_of(docs[dest["ns"]], dest["ns"], "Server", found[0]["metadata"]["name"])
                    if data["external_cidr"][env] not in cidrs:
                        gaps.append(
                            f"{env} {flow['id']}: {dest['name']}:{port} no admite el rango externo ({sorted(cidrs)})"
                        )
    return gaps


def external_flows(env: str) -> list[str]:
    disabled = DATA["env_disabled"][env]
    return [
        f["id"]
        for f in DATA["flows"]
        if active(f, env, disabled)
        and any(s.startswith("external:") for s in f["from"])
        and any(
            endpoint(d, DATA)["kind"] == "workload" and endpoint(d, DATA)["ns"] in DATA["meshed_namespaces"]
            for d in f["to"]
        )
    ]


@pytest.mark.parametrize("env", ENVS)
def test_external_flows_are_authorized_in_the_mesh(env: str) -> None:
    ids = external_flows(env)
    expected = {"kind": {"F01", "F07", "F08"}, "staging": {"F01", "F07", "F08"}, "prod": {"F01", "F08"}}[env]
    assert expected <= set(ids), ids
    assert external_gaps(env, DATA, generated(env)) == []


def test_external_range_is_the_documented_one() -> None:
    """kind: la red de Docker (el balanceador de `cloud-provider-kind` es 172.18.0.x); el banco aun no entrega el rango de los demas."""
    assert DATA["external_cidr"] == {"kind": "172.18.0.0/16", "staging": "0.0.0.0/32", "prod": "0.0.0.0/32"}


def test_external_gateway_server_is_opaque_and_named_by_port() -> None:
    """El 10443 lleva TLS de Envoy: el proxy no lo interpreta. Los nombres son los que sustituyen a los `tmp-*` de kind."""
    docs = generated("kind")["vectra-edge"]
    by_kind = {(d["kind"], d["metadata"]["name"]): d for d in docs}
    assert by_kind[("Server", "api-gateway-10443")]["spec"]["proxyProtocol"] == "opaque"
    assert by_kind[("NetworkAuthentication", "api-gateway-10443-external")]["spec"]["networks"] == [
        {"cidr": "172.18.0.0/16"}
    ]
    assert (
        by_kind[("AuthorizationPolicy", "api-gateway-10443-external")]["spec"]["targetRef"]["name"]
        == "api-gateway-10443"
    )


@pytest.mark.parametrize("env", ENVS)
def test_external_gap_is_detected_when_the_authorization_is_removed(env: str) -> None:
    """Cambio contrario: sin la autorizacion del origen externo, el barrido la echa en falta."""
    docs = {
        ns: [d for d in items if not d["metadata"]["name"].endswith("-external")]
        for ns, items in generated(env).items()
    }
    assert any("no admite el rango externo" in g for g in external_gaps(env, DATA, docs))


# ---- sondas del kubelet -----------------------------------------------------------------------------------------------------------


def pods(path: Path) -> Iterator[tuple[str, Doc]]:
    """Cada plantilla de pod de un YAML versionado: (namespace, plantilla)."""
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not isinstance(doc, dict) or "kind" not in doc:
            continue
        spec = doc.get("spec") or {}
        if doc["kind"] in POD_TEMPLATES:
            yield doc["metadata"].get("namespace", ""), spec["template"]
        elif doc["kind"] == "CronJob":
            yield doc["metadata"].get("namespace", ""), spec["jobTemplate"]["spec"]["template"]


def probes_of(template: Doc) -> Iterator[tuple[str, str | None, int | str | None, str | None]]:
    """(tipo, ruta, puerto, esquema) de cada sonda con red; `exec` no pasa por la malla."""
    for container in template["spec"].get("containers", []):
        ports = {p.get("name"): p["containerPort"] for p in container.get("ports", [])}
        for key in PROBES:
            probe = container.get(key)
            if not probe:
                continue
            if "httpGet" in probe:
                get = probe["httpGet"]
                port = ports.get(get["port"], get["port"])
                yield "http", get.get("path"), port, get.get("scheme", "HTTP")
            elif "tcpSocket" in probe:
                port = probe["tcpSocket"]["port"]
                yield "tcp", None, ports.get(port, port), None
            elif "grpc" in probe:
                yield "grpc", None, probe["grpc"]["port"], None


def owner(ns: str, template: Doc, data: dict[str, Any]) -> dict[str, Any] | None:
    labels = template.get("metadata", {}).get("labels", {})
    for name, workload in data["workloads"].items():
        if workload["ns"] == ns and labels_of(workload).items() <= labels.items():
            return {"name": name, **workload}
    return None


def probe_gaps(env: str, data: dict[str, Any], docs: dict[str, list[Doc]]) -> Check:
    """Toda sonda de un pod mallado llega al proceso: HTTP en claro en un `Server` sin rutas la autoriza Linkerd; en un `Server` con
    rutas, por la ruta de sondas; HTTPS o TCP necesitan un `Server` con el origen del kubelet (`node_cidr` y `pod_cidr`)."""
    gaps: Check = []
    kubelet = {data["node_cidr"][env], data["pod_cidr"][env]}
    for base in RENDERED:
        for path in sorted((ROOT / base / env).glob("*.yaml")):
            for ns, template in pods(path):
                if ns not in data["meshed_namespaces"]:
                    continue
                workload = owner(ns, template, data)
                for kind, route, port, scheme in probes_of(template):
                    label = f"{env} {path.relative_to(ROOT)} {ns}:{port}"
                    plain = kind == "http" and scheme == "HTTP"
                    if workload is None:
                        if not plain:
                            gaps.append(
                                f"{label}: sonda {kind}/{scheme} de un pod que no es un workload de flows.yaml"
                            )
                        continue
                    found = servers_of(docs.get(ns, []), workload, int(port))  # type: ignore[arg-type]
                    if not found:
                        if not plain:
                            gaps.append(
                                f"{label} ({workload['name']}): sonda {kind}/{scheme} sin Server: Linkerd la rechaza"
                            )
                        continue
                    name = found[0]["metadata"]["name"]
                    routes = [
                        d
                        for d in docs[ns]
                        if d["kind"] == "HTTPRoute" and d["spec"]["parentRefs"][0]["name"] == name
                    ]
                    if plain and not routes:
                        continue
                    if plain:
                        probe_routes = [
                            r
                            for r in routes
                            if any(
                                m.get("path", {}).get("value") == route and m.get("method") == "GET"
                                for rule in r["spec"]["rules"]
                                for m in rule["matches"]
                            )
                            and kubelet <= networks_of(docs[ns], ns, "HTTPRoute", r["metadata"]["name"])
                        ]
                        if not probe_routes:
                            gaps.append(
                                f"{label} ({workload['name']}): el Server {name} tiene rutas y ninguna admite la sonda {route}"
                            )
                    elif not kubelet <= networks_of(docs[ns], ns, "Server", name):
                        gaps.append(
                            f"{label} ({workload['name']}): el Server {name} no admite al kubelet {sorted(kubelet)}"
                        )
    return gaps


def template_probe_classes(root: Path = ROOT) -> list[str]:
    """Las sondas HTTPS, TCP o gRPC de las plantillas de los charts propios, que no se pueden leer sin helm."""
    found: list[str] = []
    for pattern in TEMPLATE_DIRS:
        for path in sorted(root.glob(f"{pattern}/*.yaml")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                match = re.match(r"^(\s*)(startup|liveness|readiness)Probe:", line)
                if not match:
                    continue
                block = []
                for nxt in lines[i + 1 :]:
                    if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= len(match.group(1)):
                        break
                    block.append(nxt)
                text = "\n".join(block)
                if re.search(r"tcpSocket|grpc:|scheme:\s*['\"]?HTTPS", text):
                    found.append(f"{path.relative_to(root)}:{i + 1}")
    return found


@pytest.mark.parametrize("env", ENVS)
def test_probe_ports_are_authorized_in_the_mesh(env: str) -> None:
    assert probe_gaps(env, DATA, generated(env)) == []


def test_probe_keycloak_9000_authorizes_the_kubelet_and_keeps_prometheus() -> None:
    """El `Server` `keycloak-9000` admite las sondas por HTTPS (node_cidr y pod_cidr) y sigue admitiendo a Prometheus (F60, mTLS)."""
    docs = generated("kind")["vectra-identity"]
    by_kind = {(d["kind"], d["metadata"]["name"]): d for d in docs}
    assert by_kind[("NetworkAuthentication", "keycloak-9000-probes-nodes")]["spec"]["networks"] == [
        {"cidr": DATA["node_cidr"]["kind"]},
        {"cidr": DATA["pod_cidr"]["kind"]},
    ]
    assert (
        by_kind[("AuthorizationPolicy", "keycloak-9000-probes")]["spec"]["targetRef"]["name"]
        == "keycloak-9000"
    )
    mtls = [
        d
        for d in docs
        if d["kind"] == "AuthorizationPolicy" and d["spec"]["targetRef"]["name"] == "keycloak-9000"
    ]
    assert any(
        r["kind"] == "MeshTLSAuthentication" for d in mtls for r in d["spec"]["requiredAuthenticationRefs"]
    )


@pytest.mark.parametrize("env", ENVS)
def test_probe_gap_is_detected_when_the_kubelet_is_not_authorized(env: str) -> None:
    """Cambio contrario: sin la autorizacion de las sondas, el barrido echa en falta a Keycloak."""
    docs = {
        ns: [d for d in items if "-probes" not in d["metadata"]["name"]]
        for ns, items in generated(env).items()
    }
    assert any("keycloak" in g and "kubelet" in g for g in probe_gaps(env, DATA, docs))


def test_probe_gap_is_detected_for_a_workload_without_a_server() -> None:
    """Cambio contrario: una sonda HTTPS en un puerto sin `Server` queda sin autorizar."""
    data = copy.deepcopy(DATA)
    docs = {
        ns: [d for d in items if d["kind"] != "Server" or d["spec"]["port"] != 9000]
        for ns, items in generated("kind").items()
    }
    assert any("sin Server" in g for g in probe_gaps("kind", data, docs))


def test_probe_chart_templates_use_plain_http_or_exec() -> None:
    """Los charts propios sondean por HTTP en claro o `exec`; una sonda HTTPS, TCP o gRPC nueva exige autorizar al kubelet."""
    assert template_probe_classes() == []


def test_probe_template_scan_sees_an_https_probe(tmp_path: Path) -> None:
    """Cambio contrario: el escaner encuentra una sonda HTTPS de verdad."""
    chart = tmp_path / "x" / "chart" / "templates"
    chart.mkdir(parents=True)
    (chart / "d.yaml").write_text(
        "spec:\n  containers:\n    - name: a\n      readinessProbe:\n        httpGet: { path: /r, port: 9000, scheme: HTTPS }\n",
        encoding="utf-8",
    )
    assert template_probe_classes(tmp_path) == ["x/chart/templates/d.yaml:4"]


def test_probe_ports_config_lists_every_tls_or_tcp_probe_of_the_renders() -> None:
    """`probed_ports` de flows.yaml no se desvia de los manifiestos: lo que se sonda por HTTPS o TCP esta, y lo que esta se sonda."""
    seen: dict[str, set[int]] = {}
    for base in RENDERED:
        for env in ENVS:
            for path in (ROOT / base / env).glob("*.yaml"):
                for ns, template in pods(path):
                    workload = owner(ns, template, DATA)
                    for kind, _, port, scheme in probes_of(template):
                        if workload and not (kind == "http" and scheme == "HTTP"):
                            seen.setdefault(workload["name"], set()).add(int(port))  # type: ignore[arg-type]
    assert seen == {n: set(p) for n, p in DATA["probed_ports"].items()}
