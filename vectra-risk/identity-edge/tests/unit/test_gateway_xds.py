"""Traduccion offline a xDS (U02-T10, Paso 8): P-U2-01, P-U2-07; W2, W3, W6; NFR-U2-23.

`egctl x translate` (v1.9.3, sin cluster) traduce `gateway/generated/<env>/` y estas pruebas inspeccionan el xDS: el filtro de rate
limit del dominio de `/auth/**` falla cerrado con 503 y ningun otro; el access log, el tracing y la IP real son los del diseno; y
ninguna politica queda sin aceptar. Cada comprobacion tiene su caso que falla sobre un `generated/` alterado.
"""

import copy
import shutil
from collections.abc import Callable
from typing import Any

import gateway_checks as gc
import gateway_design as gd
import gateway_expected as ge
import pytest
import xds_gateway as xg
import yaml

ENVS = gc.ENVS
BASE = "envoy.filters.http.ratelimit"
AUTH_FILTER = f"{BASE}/{ge.edge_namespace()}/{ge.AUTH_RULE}"
EDGE_FILTER = f"{BASE}/{ge.edge_namespace()}/edge-rate-limits"
LISTENER_FILTER = BASE  # el del dominio del listener: lo crea Envoy Gateway siempre
# `status_on_error: 503` en JSON de protobuf
STATUS = {500: "InternalServerError", 503: "ServiceUnavailable"}


def listener(result: dict[str, Any]) -> dict[str, Any]:
    gateway, namespace, section = gd.gateway_ref()
    (xds,) = result["xds"].values()
    for config in xds["configs"]:
        if config["@type"].endswith("ListenersConfigDump"):
            for dynamic in config["dynamicListeners"]:
                if dynamic["activeState"]["listener"]["name"] == f"{namespace}/{gateway}/{section}":
                    return dynamic["activeState"]["listener"]
    raise AssertionError("el xDS no tiene el listener https")


def hcm(result: dict[str, Any]) -> dict[str, Any]:
    (chain,) = listener(result)["filterChains"]
    (network_filter,) = chain["filters"]
    return network_filter["typedConfig"]


def ratelimit_filters(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["name"]: f["typedConfig"] for f in hcm(result)["httpFilters"] if f["name"].startswith(BASE)}


def problems(result: dict[str, Any]) -> list[str]:
    found = [f"sin aceptar: {line}" for line in xg.not_accepted(result)]
    filters = ratelimit_filters(result)
    if set(filters) != {LISTENER_FILTER, EDGE_FILTER, AUTH_FILTER}:
        found.append(f"filtros de rate limit: {sorted(filters)}")
    deny, status = gd.fail_closed()
    auth = filters.get(AUTH_FILTER, {})
    if auth.get("failureModeDeny", False) is not deny:
        found.append("el filtro de /auth/** no tiene failure_mode_deny")
    if auth.get("statusOnError") != {"code": STATUS[status]}:
        found.append(f"status_on_error de /auth/**: {auth.get('statusOnError')}")
    for name, config in filters.items():
        if name != AUTH_FILTER and config.get("failureModeDeny"):
            found.append(f"{name} tiene failure_mode_deny")
        if name != AUTH_FILTER and "statusOnError" in config:
            found.append(f"{name} tiene status_on_error")
    found += access_log_problems(result) + listener_access_log_problems(result) + tracing_problems(result) + client_ip_problems(result) + route_problems(result) + tls_problems(result)
    return found


TLS_VERSION = {"1.2": "TLSv1_2", "1.3": "TLSv1_3"}


def tls_problems(result: dict[str, Any]) -> list[str]:
    """NFR-U2-22 (Y4): TLS 1.2 como minimo y 1.3 como maximo en el borde."""
    (chain,) = listener(result)["filterChains"]
    params = chain["transportSocket"]["typedConfig"]["commonTlsContext"].get("tlsParams", {})
    low, high = gd.tls_versions()
    found = []
    if params.get("tlsMinimumProtocolVersion") != TLS_VERSION[low]:
        found.append(f"TLS minimo: {params.get('tlsMinimumProtocolVersion')}")
    if params.get("tlsMaximumProtocolVersion") != TLS_VERSION[high]:
        found.append(f"TLS maximo: {params.get('tlsMaximumProtocolVersion')}")
    return found


def access_log_problems(result: dict[str, Any]) -> list[str]:
    logs = hcm(result).get("accessLog", [])
    if len(logs) != 1:
        return [f"access logs: {len(logs)}"]
    config = logs[0]["typedConfig"]
    found = []
    if config.get("path") != "/dev/stdout":
        found.append(f"access log a {config.get('path')}")
    if config.get("logFormat", {}).get("jsonFormat") != ge.access_log_json():
        found.append(f"access log: {config.get('logFormat')}")
    return found


def listener_access_log_problems(result: dict[str, Any]) -> list[str]:
    """El access log del listener (conexiones que no llegan a una ruta, filtro `NR`) tiene los mismos campos."""
    entries = listener(result).get("accessLog", [])
    if not entries:
        return ["el listener no tiene access log"]
    return [f"access log del listener: {e['typedConfig'].get('logFormat')}" for e in entries if e["typedConfig"].get("logFormat", {}).get("jsonFormat") != ge.access_log_json()]


def tracing_problems(result: dict[str, Any]) -> list[str]:
    service, namespace, port, sampling = gd.tracing()
    tracing = hcm(result).get("tracing")
    if not tracing:
        return ["sin tracing"]
    found = []
    if tracing["provider"]["name"] != "envoy.tracers.opentelemetry":
        found.append(f"tracing con {tracing['provider']['name']}")
    if tracing.get("randomSampling", {}).get("value") != sampling or tracing.get("overallSampling", {}).get("value") != sampling:
        found.append(f"muestreo: {tracing.get('randomSampling')}")
    grpc = tracing["provider"]["typedConfig"]["grpcService"]["envoyGrpc"]
    if grpc["authority"] != f"{service}.{namespace}.svc":
        found.append(f"el tracing va a {grpc['authority']}")
    ports = _tracing_ports(result, grpc["clusterName"])
    if ports != {port}:
        found.append(f"el cluster de tracing apunta a los puertos {ports}")
    return found


def _tracing_ports(result: dict[str, Any], cluster: str) -> set[int]:
    (xds,) = result["xds"].values()
    ports: set[int] = set()
    for config in xds["configs"]:
        if config["@type"].endswith("EndpointsConfigDump"):
            for dynamic in config["dynamicEndpointConfigs"]:
                if dynamic["endpointConfig"]["clusterName"] == cluster:
                    ports |= {
                        lb["endpoint"]["address"]["socketAddress"]["portValue"]
                        for group in dynamic["endpointConfig"]["endpoints"]
                        for lb in group["lbEndpoints"]
                    }
    return ports


def client_ip_problems(result: dict[str, Any]) -> list[str]:
    """W2: Envoy toma la direccion remota. v1.9.3 resta 1 a `numTrustedHops`, asi que `xff_num_trusted_hops: 0` no basta."""
    config = hcm(result)
    found = []
    if config.get("useRemoteAddress") is not True:
        found.append("use_remote_address no es true")
    if config.get("originalIpDetectionExtensions"):
        found.append(f"original_ip_detection_extensions: {config['originalIpDetectionExtensions']}")
    if int(config.get("xffNumTrustedHops", 0)) > 0:
        found.append("xff_num_trusted_hops mayor que 0")
    return found


def route_problems(result: dict[str, Any]) -> list[str]:
    """Solo las rutas de `/auth/**` usan el filtro del dominio fail-closed."""
    (xds,) = result["xds"].values()
    found = []
    for config in xds["configs"]:
        if not config["@type"].endswith("RoutesConfigDump"):
            continue
        for dynamic in config["dynamicRouteConfigs"]:
            for host in dynamic["routeConfig"]["virtualHosts"]:
                for route in host["routes"]:
                    per_route = route.get("typedPerFilterConfig", {})
                    uses = AUTH_FILTER in per_route
                    is_auth = route["name"].startswith("httproute/vectra-edge/auth/")
                    if uses != is_auth:
                        found.append(f"{route['name']}: filtro de /auth/** = {uses}")
                    # la politica de la ruta de /auth/** se mezcla con edge-rate-limits: conserva el limite global
                    if is_auth and EDGE_FILTER not in per_route:
                        found.append(f"{route['name']}: sin el filtro de edge-rate-limits")
    return found


@pytest.fixture(scope="module")
def results() -> dict[str, dict[str, Any]]:
    """La salida de `make xds-gateway` (`xds_gateway.main`, que escribe `.tools/xds/<env>.yaml`), no una traduccion aparte."""
    assert xg.main([]) == 0
    return {env: yaml.safe_load((xg.OUT / f"{env}.yaml").read_text(encoding="utf-8")) for env in ENVS}


@pytest.fixture(scope="module")
def prod_docs() -> gc.Docs:
    return xg.load_dir(gc.GENERATED / "prod")


@pytest.mark.parametrize("env", ENVS)
def test_the_xds_of_every_environment_follows_the_design(env, results):
    assert problems(results[env]) == []


@pytest.mark.parametrize("env", ENVS)
def test_only_the_auth_domain_filter_fails_closed_with_503(env, results):
    filters = ratelimit_filters(results[env])
    assert filters[AUTH_FILTER]["failureModeDeny"] is True
    assert filters[AUTH_FILTER]["statusOnError"] == {"code": "ServiceUnavailable"}
    assert [n for n, c in filters.items() if c.get("failureModeDeny")] == [AUTH_FILTER]


@pytest.mark.parametrize("env", ENVS)
def test_every_policy_is_accepted(env, results):
    assert xg.not_accepted(results[env]) == []
    kinds = {who.split()[0] for who, _, _ in xg.conditions(results[env])}
    assert {"BackendTrafficPolicy", "ClientTrafficPolicy", "SecurityPolicy", "HTTPRoute", "Gateway"} <= kinds


@pytest.mark.parametrize("env", ENVS)
def test_the_translation_is_the_one_of_the_envoy_proxy_of_the_environment(env, results):
    # el EnvoyProxy tambien se acepta (GatewayClass.parametersRef)
    proxy = results[env]["envoyProxyForGatewayClass"]
    assert proxy["metadata"]["name"] == gd.gateway_ref()[0]
    assert all(c["status"] == "True" for a in proxy["status"]["ancestors"] for c in a["conditions"])


# --- cada comprobacion falla sobre un generated/ alterado ------------------------------------------


def _by_name(docs: gc.Docs, kind: str, name: str) -> dict[str, Any]:
    return gc.find(docs, kind, name)


def _counters_back_in_edge(docs: gc.Docs) -> None:
    edge = _by_name(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    auth = _by_name(docs, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"]
    edge.extend(auth.pop("rateLimit")["global"]["rules"])


def _second_gateway_policy(docs: gc.Docs) -> None:
    # una segunda BackendTrafficPolicy del Gateway queda `Conflicted` en v1.9.3
    extra = copy.deepcopy(_by_name(docs, "BackendTrafficPolicy", "edge-rate-limits"))
    extra["metadata"]["name"] = "zz-second"
    docs.append(extra)


def _patch_every_filter(docs: gc.Docs) -> None:
    for patch in _by_name(docs, "EnvoyPatchPolicy", "auth-fail-closed")["spec"]["jsonPatches"]:
        patch["operation"]["jsonPath"] = "..http_filters[?(@.name=~'envoy.filters.http.ratelimit.*')].typed_config"


def _patch_edge_filter(docs: gc.Docs) -> None:
    for patch in _by_name(docs, "EnvoyPatchPolicy", "auth-fail-closed")["spec"]["jsonPatches"]:
        patch["operation"]["jsonPath"] = patch["operation"]["jsonPath"].replace(ge.AUTH_RULE, "edge-rate-limits")


def _trust_one_hop(docs: gc.Docs) -> None:
    _by_name(docs, "ClientTrafficPolicy", "edge-client")["spec"]["clientIPDetection"] = {"xForwardedFor": {"numTrustedHops": 1}}


def _trust_zero_hops(docs: gc.Docs) -> None:
    _by_name(docs, "ClientTrafficPolicy", "edge-client")["spec"]["clientIPDetection"] = {"xForwardedFor": {"numTrustedHops": 0}}


def _proxy(docs: gc.Docs) -> dict[str, Any]:
    return _by_name(docs, "EnvoyProxy", "api-gateway")["spec"]


ALTERATIONS: list[tuple[str, Callable[[gc.Docs], None]]] = [
    ("counters-back-in-edge-rate-limits", _counters_back_in_edge),
    ("no-envoy-patch-policy", lambda d: d.remove(_by_name(d, "EnvoyPatchPolicy", "auth-fail-closed"))),
    ("patch-on-every-rate-limit-filter", _patch_every_filter),
    ("patch-on-the-edge-filter", _patch_edge_filter),
    ("patch-without-status-on-error", lambda d: _by_name(d, "EnvoyPatchPolicy", "auth-fail-closed")["spec"]["jsonPatches"].pop()),
    ("second-policy-on-the-gateway", _second_gateway_policy),
    ("trusts-one-hop", _trust_one_hop),
    ("trusts-zero-hops", _trust_zero_hops),
    ("tls-minimum-1.0", lambda d: _by_name(d, "ClientTrafficPolicy", "edge-client")["spec"]["tls"].update(minVersion="1.0")),
    ("tls-maximum-1.2", lambda d: _by_name(d, "ClientTrafficPolicy", "edge-client")["spec"]["tls"].update(maxVersion="1.2")),
    ("tracing-to-another-port", lambda d: _proxy(d)["telemetry"]["tracing"]["provider"]["backendRefs"][0].update(port=4318)),
    ("auth-policy-without-merge-type", lambda d: _by_name(d, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"].pop("mergeType")),
    ("no-tracing", lambda d: _proxy(d)["telemetry"].pop("tracing")),
    ("tracing-sampling-1", lambda d: _proxy(d)["telemetry"]["tracing"].update(samplingRate=1)),
    ("access-log-with-path", lambda d: _proxy(d)["telemetry"]["accessLog"]["settings"][0]["format"]["json"].update(path="%REQ(:PATH)%")),
    ("access-log-to-a-file", lambda d: _proxy(d)["telemetry"]["accessLog"]["settings"][0].update(sinks=[{"type": "File", "file": {"path": "/var/log/envoy/access.log"}}])),
    ("route-uses-a-missing-filter", lambda d: _by_name(d, "HTTPRoute", "closed")["spec"]["rules"][0]["filters"][0]["extensionRef"].update(name="ghost")),
]


@pytest.mark.parametrize(("case", "alter"), ALTERATIONS, ids=[c for c, _ in ALTERATIONS])
def test_the_xds_check_fails_on_an_altered_generated_tree(case, alter, prod_docs):
    docs = copy.deepcopy(prod_docs)
    alter(docs)
    result = xg.translate(docs)  # una excepcion de egctl hace fallar la prueba: no cuenta como acierto
    assert problems(result), f"{case}: la prueba no fallo"


def test_main_fails_when_a_policy_is_not_accepted(tmp_path, monkeypatch, capsys):
    generated = tmp_path / "generated"
    shutil.copytree(gc.GENERATED, generated)
    extra = copy.deepcopy(_by_name(xg.load_dir(gc.GENERATED / "prod"), "BackendTrafficPolicy", "edge-rate-limits"))
    extra["metadata"]["name"] = "zz-second"
    (generated / "prod" / "zz-second.yaml").write_text(yaml.safe_dump(extra), encoding="utf-8")
    monkeypatch.setattr(xg, "GENERATED", generated)
    assert xg.main(["--out", str(tmp_path / "out")]) == 1
    assert "Conflicted" in capsys.readouterr().err


def test_main_fails_when_egctl_rejects_the_input(tmp_path, monkeypatch, capsys):
    generated = tmp_path / "generated"
    shutil.copytree(gc.GENERATED, generated)
    (generated / "kind" / "gatewayclasses.yaml").unlink()
    monkeypatch.setattr(xg, "GENERATED", generated)
    assert xg.main(["--out", str(tmp_path / "out")]) == 1
    assert "GatewayClass" in capsys.readouterr().err


def test_the_inspection_reads_the_failure_mode_from_the_design(monkeypatch, results):
    monkeypatch.setattr(gd, "fail_closed", lambda: (True, 500))
    assert any("status_on_error" in line for line in problems(results["prod"]))


def test_main_passes_on_the_committed_manifests(tmp_path):
    assert xg.main(["--out", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{env}.yaml" for env in sorted(ENVS)]
