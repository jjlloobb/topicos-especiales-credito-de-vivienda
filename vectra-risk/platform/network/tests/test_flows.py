"""P-U1-01, 02; plan de U1, Paso 3."""
import json
import re
from pathlib import Path

import pytest
import yaml
from generate import ENVS, build, load, main

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "aidlc-docs/inception/application-design/component-dependency.md"
DATA, FORBIDDEN = load()


def docs(env):
    return build(env, DATA, FORBIDDEN)[0]


def flow(flow_id):
    return next(f for f in DATA["flows"] if f["id"] == flow_id)


def all_docs(env):
    return [d for items in docs(env).values() for d in items]


def policies(env, ns):
    return [d for d in docs(env)[ns] if d["kind"] == "NetworkPolicy"]


def test_every_inventory_id_is_in_flows():
    ids = set(re.findall(r"^\| (F\d+) \|", INVENTORY.read_text(encoding="utf-8"), flags=re.M))
    system = {"F125", "F126", "F127"}  # los genera `system_internal`, no una entrada de `flows`
    assert ids and ids == {f["id"] for f in DATA["flows"]} | system


def test_inventory_x_ids_are_covered():
    ids = set(re.findall(r"^\| (X\d+) \|", INVENTORY.read_text(encoding="utf-8"), flags=re.M))
    covered = {c["id"] for c in FORBIDDEN["forbidden"]}
    assert {"X01", "X02", "X05", "X07", "X08", "X09"} <= covered
    assert ids - covered <= {"X03", "X04", "X06", "X10"} | covered


def test_endpoints_exist():
    for item in DATA["flows"]:
        for name in item["from"] + item["to"]:
            if ":" not in name:
                assert name in DATA["workloads"], (item["id"], name)


def test_every_namespace_denies_by_default():
    for env in ENVS:
        for ns, items in docs(env).items():
            names = {d["metadata"]["name"] for d in items}
            assert {"deny-all", "allow-dns"} <= names, ns
            deny = next(d for d in items if d["metadata"]["name"] == "deny-all")
            assert deny["spec"]["policyTypes"] == ["Ingress", "Egress"] and "ingress" not in deny["spec"]


def test_dns_is_the_only_common_exception():
    for env in ENVS:
        for _ns, items in docs(env).items():
            common = [d for d in items if d["kind"] == "NetworkPolicy" and d["spec"]["podSelector"] == {} and "vectra.io/flow" not in d["metadata"].get("labels", {})]
            assert {d["metadata"]["name"] for d in common} == {"deny-all", "allow-dns"}


def test_f27_only_from_the_cronjob_selector():
    assert flow("F27")["from"] == ["bias-monitoring-job"]
    egress = [p for p in policies("kind", "vectra-app") if p["metadata"]["name"].startswith("allow-f27-")and "egress" in p["spec"]]
    assert egress[0]["spec"]["podSelector"]["matchLabels"] == {"vectra.io/workload": "bias-monitoring-job"}


@pytest.mark.parametrize("flow_id", ["F01", "F07"])
def test_external_origin_has_no_egress_policy(flow_id):
    names = [d["metadata"]["name"] for d in all_docs("kind") if d["kind"] == "NetworkPolicy" and d["metadata"].get("labels", {}).get("vectra.io/flow") == flow_id]
    assert names and all(n.endswith("-ingress") for n in names)


def test_f09_disabled_everywhere():
    for env in ENVS:
        assert not [d for d in all_docs(env) if d["metadata"].get("labels", {}).get("vectra.io/flow") == "F09"]


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_f22_cannot_be_disabled_outside_kind(env):
    assert DATA["env_disabled"][env] == []


def test_f22_can_be_disabled_in_kind():
    changed = {**DATA, "env_disabled": {**DATA["env_disabled"], "kind": ["F22"]}}
    built = build("kind", changed, FORBIDDEN)[0]
    assert not [d for items in built.values() for d in items if d["metadata"].get("labels", {}).get("vectra.io/flow") == "F22"]


def test_restore_drill_has_exactly_its_flows():
    common = {"F61", "F80", "F83", "F87", "F114", "K12", "K18R"}
    expected = {"kind": common | {"F75", "F98", "F118"}, "staging": common | {"F75", "F99"}, "prod": common | {"F75", "F99"}}
    for env, wanted in expected.items():
        found = {d["metadata"]["labels"]["vectra.io/flow"] for d in policies(env, "vectra-restore-drill") if "vectra.io/flow" in d["metadata"].get("labels", {})}
        assert found == wanted, env


def api_policies(env):
    return {d["metadata"]["labels"]["vectra.io/flow"] for d in all_docs(env) if d["metadata"]["name"].startswith("allow-k8s-api-")}


def test_k_bindings_have_api_egress():
    assert api_policies("prod") == set(DATA["k_egress"])
    governance = next(d for d in docs("prod")["vectra-app"] if d["metadata"]["name"] == "allow-k8s-api-k01")
    assert governance["spec"]["podSelector"]["matchLabels"] == {"app.kubernetes.io/name": "governance-service"}


def test_k09_and_k16_have_no_api_egress():
    assert not {"K09", "K15", "K16"} & set(DATA["k_egress"])


def test_service_without_binding_does_not_reach_api():
    selectors = [d["spec"]["podSelector"].get("matchLabels", {}) for d in all_docs("prod") if d["metadata"]["name"].startswith("allow-k8s-api-")]
    for name in ("scoring-service", "explainability-service", "case-service", "bias-monitoring-service", "console-bff"):
        assert {"app.kubernetes.io/name": name} not in selectors


def test_x05_no_cross_database_access():
    for case in FORBIDDEN["forbidden"]:
        if case["id"] in {"X05", "U10", "U11", "X01", "X08"}:
            allowed = build("kind", DATA, FORBIDDEN)[1]["allowed"]
            assert not [a for a in allowed if a["from"] == case["from"] and a["to"] == case["to"]], case


def test_x02_no_external_egress_from_scoring():
    allowed = build("prod", DATA, FORBIDDEN)[1]["allowed"]
    externals = {a["from"] for a in allowed if flow(a["flow"])["to"][0].startswith("external:")}
    assert not {"scoring-service", "explainability-service", "bias-monitoring-service"} & externals


def test_observability_egress_is_only_f72_and_internal():
    allowed = build("prod", DATA, FORBIDDEN)[1]["allowed"]
    outside = {a["flow"] for a in allowed if a["from"] in {"prometheus", "grafana", "loki", "tempo", "otel-collector", "alloy", "pushgateway"} and flow(a["flow"])["to"][0].startswith("external:")}
    assert outside == {"F119"}, "F119 va al kubelet del nodo, dentro del cluster"


def test_mock_only_in_kind_and_staging():
    assert "vectra-mock" in docs("kind") and "vectra-mock" in docs("staging") and "vectra-mock" not in docs("prod")
    assert not [a for a in build("prod", DATA, FORBIDDEN)[1]["allowed"] if a["to"] == "core-banking-mock"]


def test_f111_only_in_kind():
    for env in ("staging", "prod"):
        assert not [a for a in build(env, DATA, FORBIDDEN)[1]["allowed"] if a["flow"] == "F111"]
    assert [a for a in build("kind", DATA, FORBIDDEN)[1]["allowed"] if a["flow"] == "F111"]


def test_linkerd_identity_is_source_serviceaccount():
    auth = [d for d in docs("prod")["vectra-app"] if d["kind"] == "MeshTLSAuthentication" and d["metadata"]["name"].startswith("f15-")]
    assert auth[0]["spec"]["identities"] == ["case-worker.vectra-app.serviceaccount.identity.linkerd.cluster.local"]


def test_f80_network_authentication_on_5432():
    names = {d["metadata"]["name"] for d in docs("prod")["vectra-data"] if d["kind"] == "NetworkAuthentication"}
    assert "f80-registry-db-5432-operator-network" in names


def test_target_port_used_by_network_policy_and_server():
    policy = next(p for p in policies("prod", "vectra-serving") if p["metadata"]["name"].startswith("allow-f19-"))
    assert policy["spec"]["ingress"][0]["ports"] == [{"protocol": "TCP", "port": 8080}]
    server = next(d for d in docs("prod")["vectra-serving"] if d["kind"] == "Server" and d["spec"]["port"] == 8080)
    assert server["spec"]["port"] == 8080


def test_generated_check_matches(monkeypatch):
    monkeypatch.setattr("sys.argv", ["generate.py", "--check"])
    assert main() == 0


def test_generated_documents_parse():
    for path in (Path(__file__).resolve().parents[1] / "generated").rglob("*.yaml"):
        assert list(yaml.safe_load_all(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_one_server_per_pod_and_port(env):
    for ns, items in docs(env).items():
        seen = [(json.dumps(d["spec"]["podSelector"], sort_keys=True), d["spec"]["port"]) for d in items if d["kind"] == "Server"]
        assert len(seen) == len(set(seen)), ns


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_every_authorization_targets_an_existing_object(env):
    for ns, items in docs(env).items():
        names = {(d["kind"], d["metadata"]["name"]) for d in items}
        for item in items:
            if item["kind"] == "AuthorizationPolicy":
                target = item["spec"]["targetRef"]
                assert (target["kind"], target["name"]) in names, (ns, item["metadata"]["name"])


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_all_flows_to_a_database_keep_their_authorization(env):
    policies_by_flow = {d["metadata"]["name"] for d in docs(env)["vectra-data"] if d["kind"] == "AuthorizationPolicy"}
    assert len([n for n in policies_by_flow if "registry-db-5432" in n]) > 1


def test_no_unresolved_templates_in_generated_manifests():
    for path in (Path(__file__).resolve().parents[1] / "generated").rglob("*.yaml"):
        assert "{{" not in path.read_text(encoding="utf-8"), path


def test_api_server_egress_fails_closed_until_the_bank_gives_the_range():
    egress = next(d for d in docs("prod")["vectra-app"] if d["metadata"]["name"] == "allow-k8s-api-k01")
    assert egress["spec"]["egress"][0]["to"] == [{"ipBlock": {"cidr": "0.0.0.0/32"}}]


def test_f80_network_authentication_fails_closed_until_the_bank_gives_the_range():
    network = next(d for d in docs("prod")["vectra-data"] if d["kind"] == "NetworkAuthentication")
    assert network["spec"]["networks"] == [{"cidr": "0.0.0.0/32"}]


def pushgateway_routes(env="prod"):
    return {d["metadata"]["name"]: d for d in docs(env)["vectra-observability"] if d["kind"] == "HTTPRoute"}


def test_pushgateway_routes_by_identity():
    routes = pushgateway_routes()
    drill = routes["prometheus-pushgateway-restore-drill"]["spec"]["rules"][0]["matches"]
    assert [m["method"] for m in drill] == ["PUT"], "restore-drill no borra grupos"
    assert re.fullmatch(drill[0]["path"]["value"], "/metrics/job/restore-drill/instance/x")
    assert not re.fullmatch(drill[0]["path"]["value"], "/metrics/job/bias-monitoring/x")
    assert not re.fullmatch(drill[0]["path"]["value"], "/metrics/job/restore-drill-evil")
    bias = routes["prometheus-pushgateway-bias-monitoring-job"]["spec"]["rules"][0]["matches"]
    assert {m["method"] for m in bias} == {"PUT", "DELETE", "GET"}
    assert [m["path"]["value"] for m in routes["prometheus-pushgateway-prometheus"]["spec"]["rules"][0]["matches"]] == ["/metrics"]


def test_pushgateway_has_no_server_wide_authorization():
    for item in docs("prod")["vectra-observability"]:
        if item["kind"] == "AuthorizationPolicy" and "pushgateway" in item["metadata"]["name"]:
            assert item["spec"]["targetRef"]["kind"] == "HTTPRoute"
    server = next(d for d in docs("prod")["vectra-observability"] if d["kind"] == "Server" and d["metadata"]["name"] == "prometheus-pushgateway-9091")
    assert server["spec"]["proxyProtocol"] == "HTTP/1"


def test_routes_exist_for_every_identity_of_the_pushgateway():
    routes = [name for name in pushgateway_routes() if not name.endswith("-probes")]
    assert len(routes) == 6, sorted(routes)


# --- Consistencia con U2-U12 (revision del 2026-11-01)


def suite(env):
    return build(env, DATA, FORBIDDEN)[1]


def named(env, ns, kind):
    return {d["metadata"]["name"]: d for d in docs(env)[ns] if d["kind"] == kind}


@pytest.mark.parametrize("ns", ["vectra-app", "vectra-edge", "vectra-serving"])
def test_prometheus_can_scrape_every_pod_of_the_namespace(ns):
    server = named("prod", ns, "Server")["metrics-8081"]
    assert server["spec"]["podSelector"] == {} and server["spec"]["port"] == 8081
    auth = next(d for name, d in named("prod", ns, "MeshTLSAuthentication").items() if name.startswith("f60-"))
    assert auth["spec"]["identities"] == ["prometheus.vectra-observability.serviceaccount.identity.linkerd.cluster.local"]


def test_promotion_tool_reaches_governance_through_the_gateway():
    assert any(a["flow"] == "F08" and a["from"] == "api-gateway" and a["to"] == "governance-service" for a in suite("prod")["allowed"])


def route_rules(env, ns, name):
    return named(env, ns, "HTTPRoute")[name]["spec"]["rules"][0]["matches"]


def governance_routes(env="prod"):
    routes = {}
    for name, route in named(env, "vectra-app", "HTTPRoute").items():
        if name.startswith("governance-service-"):
            routes[name.removeprefix("governance-service-")] = route["spec"]["rules"][0]["matches"]
    return routes


def route_matches(match, method, path):
    kind, value = match["path"]["type"], match["path"]["value"]
    found = path == value if kind == "Exact" else re.fullmatch(value, path) is not None
    return found and match.get("method") == method


def clients_of(route):
    auth = named("prod", "vectra-app", "MeshTLSAuthentication")[f"governance-service-{route}-mtls"]
    return {identity.split(".")[0] for identity in auth["spec"]["identities"]}


GOVERNANCE_CALLERS = {
    ("GET", "/v1/serving-config"): {"scoring-service", "case-service", "case-worker"},
    ("GET", "/v1/models"): {"console-bff", "api-gateway"},
    ("POST", "/v1/models/x/activation"): {"api-gateway"},
    ("POST", "/v1/models/x/freeze"): {"bias-monitoring-job"},
    ("GET", "/v1/models/x/feature-dictionary"): {"explainability-service"},
    ("GET", "/v1/models/x/feature-spec"): {"case-worker"},
    ("PUT", "/v1/validation-runs/x/source-counts"): {"model-validation-job"},
    ("PUT", "/v1/models/x/validation-report"): {"model-validation-job"},
    ("POST", "/v1/models/x/approval"): {"console-bff"},
    ("GET", "/v1/models/x"): {"console-bff"},
    ("POST", "/v1/policies/x/approval"): {"console-bff"},
    ("GET", "/v1/data-sources"): {"console-bff"},
}


@pytest.mark.parametrize(("request_line", "callers"), GOVERNANCE_CALLERS.items())
def test_each_governance_request_falls_in_one_route_with_all_its_callers(request_line, callers):
    """Linkerd elige una ruta y autoriza solo contra ella: un solape dejaria a alguien sin acceso."""
    method, path = request_line
    hits = [name for name, matches in governance_routes().items() if any(route_matches(m, method, path) for m in matches)]
    assert len(hits) == 1, (request_line, hits)
    assert clients_of(hits[0]) == callers


def test_every_contract_route_of_governance_has_its_place():
    """Cada ruta de U0 cae en exactamente una HTTPRoute."""
    spec = yaml.safe_load((ROOT / "contracts/openapi/governance-service.yaml").read_text(encoding="utf-8"))
    for path, operations in spec["paths"].items():
        concrete = re.sub(r"\{\w+\}", "x", path)
        for method in operations:
            hits = [n for n, matches in governance_routes().items() if any(route_matches(m, method.upper(), concrete) for m in matches)]
            assert len(hits) == 1, (method, path, hits)


def test_every_source_flow_to_governance_has_a_route():
    sources = {s for f in DATA["flows"] for pair in [(f["from"], f["to"])] if "governance-service" in pair[1] for s in pair[0]}
    declared = {s for r in DATA["http_routes"]["governance-service"]["_routes"].values() for s in r["sources"]}
    assert sources == declared


def test_the_rest_gets_a_proxy_403():
    routes = named("prod", "vectra-app", "HTTPRoute")
    assert "governance-catch-all" in routes
    targets = {d["spec"]["targetRef"]["name"] for d in docs("prod")["vectra-app"] if d["kind"] == "AuthorizationPolicy"}
    assert "governance-catch-all" not in targets
    assert named("prod", "vectra-app", "Server")["governance-service-8080"]["spec"]["proxyProtocol"] == "HTTP/1"


def test_core_mock_has_read_route_and_catch_all():
    routes = named("kind", "vectra-mock", "HTTPRoute")
    assert {"core-banking-mock-case-service", "core-mock-catch-all"} <= set(routes)
    assert route_rules("kind", "vectra-mock", "core-banking-mock-case-service")[0]["method"] == "GET"


def test_pushgateway_probes_are_authorized_for_kubelet_sources_only():
    """Nodos y red de pods: tras reiniciar un nodo, kubelet llego desde tunl0 y Linkerd respondio 403 (issue 7)."""
    assert {m["path"]["value"] for m in route_rules("prod", "vectra-observability", "prometheus-pushgateway-probes")} == {"/-/healthy", "/-/ready"}
    authn = named("kind", "vectra-observability", "NetworkAuthentication")["prometheus-pushgateway-probes-nodes"]
    assert authn["spec"]["networks"] == [{"cidr": "172.18.0.0/16"}, {"cidr": "192.168.0.0/16"}]


@pytest.mark.parametrize("ns", sorted(DATA["system_internal"]))
def test_system_namespaces_keep_their_operators_alive(ns):
    env = "kind" if ns == "vault" else "prod"
    names = {d["metadata"]["name"] for d in docs(env)[ns]}
    assert {"deny-all", "allow-dns", "allow-f125-same-namespace-ingress", "allow-f125-same-namespace-egress", "allow-f126-k8s-api"} <= names


def test_webhook_ports_are_open_where_they_exist():
    for ns, ports in (("kyverno", {9443}), ("external-secrets", {10250}), ("cert-manager", {10250}), ("linkerd", {8443, 9443})):
        rule = next(d for d in docs("prod")[ns] if d["metadata"]["name"] == "allow-f127-webhooks")
        assert {p["port"] for p in rule["spec"]["ingress"][0]["ports"]} == ports


def test_each_migration_only_reaches_its_database():
    pairs = {(a["from"], a["to"]) for a in suite("prod")["allowed"] if a["flow"] == "F44"}
    assert pairs == {("migration-case", "case-db"), ("migration-governance", "governance-db"), ("migration-registry", "registry-db")}


def test_backups_stay_in_cluster_only_in_kind():
    def targets(env):
        return {a["to"] for a in suite(env)["allowed"] if a["flow"] == "F70"}

    assert targets("kind") == {"minio"}
    assert targets("prod") == {"backups"}


def test_mock_reaches_keycloak_for_jwks_and_all_namespaces_export_traces():
    assert any(a["flow"] == "F50" and a["from"] == "core-banking-mock" for a in suite("kind")["allowed"])
    sources = {a["from"] for a in suite("kind")["allowed"] if a["flow"] == "F61"}
    assert {"vectra-mock", "vectra-staging", "vectra-identity"} <= sources


@pytest.mark.parametrize("env", ENVS)
def test_no_blocked_case_is_also_allowed(env):
    current = suite(env)
    allowed = {(a["from"], a["to"], port) for a in current["allowed"] for port in a["ports"]}
    for case in current["blocked"]:
        source = case["from"].removeprefix("external:")
        target = case["to"].removeprefix("external:")
        assert (source, target, case["port"]) not in allowed, case


def test_catalogue_has_the_cases_of_the_units():
    cases = {(c["id"], c["from"], c["to"]) for c in FORBIDDEN["forbidden"]}
    assert ("X04", "bias-monitoring-service", "governance-service") in cases
    assert ("X08", "predictor", "staging-isvc") in cases
    assert ("U9", "bias-monitoring-service", "pushgateway") in cases
    assert ("U8", "case-service", "scoring-service") in cases


def ports_in(policy):
    rules = policy["spec"].get("ingress") or policy["spec"].get("egress")
    return {p["port"] for rule in rules for p in rule["ports"]}


@pytest.mark.parametrize("env", ENVS)
def test_opaque_postgres_flows_open_the_proxy_port(env):
    """Linkerd envia el 5432 por el 4143 en cualquier modo: lo comprobo el Job `join` en kind (issue 7)."""
    named = {d["metadata"]["name"]: d for d in policies(env, "vectra-data")}
    assert ports_in(named["allow-f45-to-registry-db-ingress"]) == {5432, 4143}
    assert ports_in(named["allow-f45-registry-db-to-registry-db-egress"]) == {5432, 4143}


@pytest.mark.parametrize("env", ENVS)
def test_only_opaque_meshed_flows_open_the_proxy_port(env):
    """El resto sigue limitado a su puerto, y el operador sin malla llega directo al 5432."""
    named = {d["metadata"]["name"]: d for d in policies(env, "vectra-data")}
    assert 4143 not in ports_in(named["allow-f123-to-minio-ingress"])
    assert 4143 not in ports_in(named["allow-f80-to-registry-db-ingress"])


F130_TARGETS = {
    "alertmanager": 8080,
    "kube-prometheus-stack-prometheus-operator": 8080,
    "grafana": 3000,
}


def _f130_peers(rule):
    return {(e["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"], e["podSelector"]["matchLabels"]["app.kubernetes.io/name"]) for e in rule}


@pytest.mark.parametrize("env", ENVS)
def test_f130_prometheus_scrapes_the_observability_targets(env):
    """F130: cada destino recibe de prometheus SOLO su puerto (ingress y egress) y Linkerd lo autoriza con la identidad `prometheus`."""
    current = docs(env)["vectra-observability"]
    found = [p for p in current if p["kind"] == "NetworkPolicy" and p["metadata"].get("labels", {}).get("vectra.io/flow") == "F130"]
    assert len(found) == 2 * len(F130_TARGETS)
    for target, port in F130_TARGETS.items():
        label = target
        ingress = [p for p in found if p["spec"]["policyTypes"] == ["Ingress"] and p["spec"]["podSelector"]["matchLabels"] == {"app.kubernetes.io/name": label}]
        egress = [p for p in found if p["spec"]["policyTypes"] == ["Egress"] and p["spec"]["egress"][0]["to"] == [
            {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "vectra-observability"}}, "podSelector": {"matchLabels": {"app.kubernetes.io/name": label}}}]]
        assert len(ingress) == 1 and len(egress) == 1, target
        rule = ingress[0]["spec"]["ingress"]
        assert len(rule) == 1 and rule[0]["ports"] == [{"port": port, "protocol": "TCP"}], target
        assert _f130_peers(rule[0]["from"]) == {("vectra-observability", "prometheus")}, target
        out = egress[0]
        assert out["spec"]["podSelector"]["matchLabels"] == {"app.kubernetes.io/name": "prometheus"}, target
        assert len(out["spec"]["egress"]) == 1 and out["spec"]["egress"][0]["ports"] == [{"port": port, "protocol": "TCP"}], target
        auth = next(d for d in current if d["kind"] == "AuthorizationPolicy" and d["metadata"]["name"] == f"f130-{target}-{port}")
        assert auth["spec"]["targetRef"]["name"] == f"{target}-{port}"
        mtls = next(d for d in current if d["kind"] == "MeshTLSAuthentication" and d["metadata"]["name"] == f"f130-{target}-{port}-mtls")
        assert [r["name"] for r in auth["spec"]["requiredAuthenticationRefs"]] == [mtls["metadata"]["name"]], target
        assert mtls["spec"]["identities"] == ["prometheus.vectra-observability.serviceaccount.identity.linkerd.cluster.local"], target
        assert any(d["kind"] == "Server" and d["metadata"]["name"] == f"{target}-{port}" for d in current), target
    assert 4143 not in {pt["port"] for p in found for r in (p["spec"].get("ingress") or p["spec"].get("egress")) for pt in r["ports"]}
