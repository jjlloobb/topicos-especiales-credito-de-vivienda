"""`routes.yaml` y `route-gen` (U02-T09, Paso 7): BR-U2-08, 10, 11, 13, 14; P-U2-02, 03, 06, 07; INF-U2-01, 10.

Cada documento generado se compara completo con `gateway_expected` (escrito aparte, con los valores del diseno de
`gateway_design`). Cada regla de identity-edge/gateway/policy/ tiene un caso que falla sobre un documento alterado, y
cada punto de las precisiones tiene un caso que pasa y otro que falla.
"""

import copy
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import crd_schemas
import design_values
import gateway_checks as gc
import gateway_design as gd
import gateway_expected as ge
import pytest
import route_gen
import yaml
from vectra_contracts.models.api import Problem

ENVS = gc.ENVS
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


def simulator_azp(env: str) -> str | None:
    """`channel-simulator` existe en kind y staging y no en produccion (domain-entities §2.2)."""
    (client,) = [c for c in design_values.service_clients() if c.client_id == "channel-simulator"]
    assert client.non_prod_only
    return None if env == "prod" else client.client_id


def expected(env: str, f09: bool = False) -> dict[str, list[dict[str, Any]]]:
    return ge.expected(env, f09, simulator_azp(env))


def values_for(env: str, f09: bool = False) -> dict[str, Any]:
    values = copy.deepcopy(route_gen.load_values(env))
    values["f09"]["enabled"] = f09
    return values


def generated_docs(env: str, f09: bool = False) -> gc.Docs:
    files = route_gen.generate(route_gen.load_routes(), values_for(env, f09))
    return gc.flat({name: [d for d in yaml.safe_load_all(text) if d] for name, text in files.items()})


@pytest.fixture(scope="module")
def docs_by_env() -> dict[str, gc.Docs]:
    return {env: gc.load_env(env) for env in ENVS}


def token(**claims: Any) -> dict[str, Any]:
    return claims


# --- los manifiestos generados son los del diseno --------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_exact_set_of_files_and_documents_per_environment(env):
    on_disk = gc.load_dir(gc.GENERATED / env)
    want = expected(env)
    assert set(on_disk) == set(want) == set(ge.FILES)
    assert gc.identities(gc.flat(on_disk)) == gc.identities(gc.flat(want))


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("name", ge.FILES)
def test_every_generated_document_equals_the_design(env, name):
    on_disk = gc.load_dir(gc.GENERATED / env)[name]
    want = expected(env)[name]
    assert len(on_disk) == len(want)
    for got, exp in zip(on_disk, want, strict=True):
        assert got == exp, f"{name}: {got['kind']} {got['metadata']['name']}"


@pytest.mark.parametrize("env", ENVS)
def test_the_committed_manifests_are_what_the_generator_writes(env):
    fresh = route_gen.generate(route_gen.load_routes(), route_gen.load_values(env))
    on_disk = {p.name: p.read_text(encoding="utf-8") for p in (gc.GENERATED / env).glob("*.yaml")}
    assert on_disk == fresh


def test_the_values_of_each_environment_hold_the_hostname_of_the_design():
    for env, hostname in gd.hostnames().items():
        assert route_gen.load_values(env)["hostname"] == hostname


@pytest.mark.parametrize("env", ENVS)
def test_the_issuer_uses_the_public_hostname_and_the_jwks_the_internal_url(env):
    (provider,) = gc.find(gc.load_env(env), "SecurityPolicy", "console")["spec"]["jwt"]["providers"]
    assert provider["issuer"] == f"https://{gd.hostnames()[env]}/auth/realms/vectra"
    assert provider["remoteJWKS"]["uri"] == gd.jwks_uri()


# --- --check ------------------------------------------------------------------------------------


def test_check_passes_on_the_committed_manifests():
    assert route_gen.main(["--check"]) == 0


def _copy_generated(tmp_path: Path) -> Path:
    out = tmp_path / "generated"
    shutil.copytree(gc.GENERATED, out)
    return out


def test_check_succeeds_on_a_fresh_write(tmp_path):
    out = tmp_path / "generated"
    assert route_gen.main(["--out", str(out)]) == 0
    assert route_gen.main(["--check", "--out", str(out)]) == 0


@pytest.mark.parametrize(
    "alter",
    [
        lambda out: (out / "kind" / "httproutes.yaml").write_text("# alterado\n", encoding="utf-8"),
        lambda out: (out / "prod" / "securitypolicies.yaml").unlink(),
        lambda out: (out / "staging" / "extra.yaml").write_text("kind: Extra\n", encoding="utf-8"),
        lambda out: shutil.rmtree(out / "staging"),
    ],
    ids=["content-changed", "file-missing", "file-extra", "environment-missing"],
)
def test_check_fails_on_an_altered_generated_tree_and_does_not_write(alter, tmp_path):
    out = _copy_generated(tmp_path)
    alter(out)
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert route_gen.main(["--check", "--out", str(out)]) != 0
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before


# --- /api/intake/** por entorno (CA-4) ------------------------------------------------------------


def _intake_token(azp: str, scope: str = "intake:submit") -> dict[str, Any]:
    return token(azp=azp, scope=scope)


@pytest.mark.parametrize("env", ENVS)
def test_intake_authorization_admits_channel_and_the_simulator_only_outside_production(env, docs_by_env):
    policy = gc.find(docs_by_env[env], "SecurityPolicy", "intake")
    assert gc.authorizes(policy, _intake_token("channel"))
    assert gc.authorizes(policy, _intake_token("channel-simulator")) == (env != "prod")
    assert not gc.authorizes(policy, _intake_token("vectra-console"))
    assert not gc.authorizes(policy, _intake_token("channel", scope="other:scope"))
    assert not gc.authorizes(policy, {"azp": "channel"})


def test_intake_production_policy_has_no_simulator_azp(docs_by_env):
    (claim,) = gc.find(docs_by_env["prod"], "SecurityPolicy", "intake")["spec"]["authorization"]["rules"][0]["principal"]["jwt"]["claims"]
    assert claim["values"] == ["channel"]


def _azp_limits(docs: gc.Docs) -> dict[str, tuple[int, str]]:
    rules = gc.find(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    found = {}
    for rule in rules:
        for selector in rule.get("clientSelectors", []):
            for header in selector.get("headers", []):
                if header["name"] == "x-vectra-azp":
                    found[header["value"]] = (rule["limit"]["requests"], rule["limit"]["unit"])
    return found


@pytest.mark.parametrize("env", ENVS)
def test_intake_rate_limits_are_separate_per_azp_and_the_simulator_has_none_in_production(env, docs_by_env):
    n = gd.rate_limit_numbers()
    want = {"channel": (n["intake-channel"], "Second")}
    if env != "prod":
        want["channel-simulator"] = (n["intake-channel-simulator"], "Second")
    assert _azp_limits(docs_by_env[env]) == want
    assert (n["intake-channel"], n["intake-channel-simulator"]) == (10, 30)


@pytest.mark.parametrize("env", ENVS)
def test_intake_post_is_rewritten_and_anything_else_under_the_prefix_is_404(env, docs_by_env):
    docs = docs_by_env[env]
    ok = gc.route(docs, "POST", "/api/intake/v1/intake/applications")
    assert (ok.kind, ok.backend, ok.upstream_path) == ("backend", ("case-service", "vectra-app", 8080), "/v1/intake/applications")
    for method, path in [
        ("GET", "/api/intake/v1/intake/applications"),
        ("PUT", "/api/intake/v1/intake/applications"),
        ("POST", "/api/intake/v1/intake/applications/1"),
        ("POST", "/api/intake/v1/intake/applications/"),
        ("POST", "/api/intake/other"),
        ("POST", "/api/intake"),
        ("GET", "/api/intake/"),
    ]:
        out = gc.route(docs, method, path)
        assert (out.kind, out.status) == ("direct", 404), (method, path)


# --- CA-5: /auth/** ---------------------------------------------------------------------------------


def auth_violations(docs: gc.Docs) -> list[str]:
    """Que la lista exacta de V1 y solo ella llegue a Keycloak, y sus dos contadores."""
    bad = []
    exact, prefix = gd.auth_entries()
    for path in exact:
        if gc.route(docs, "GET", path).backend != ("keycloak", "vectra-identity", 8443):
            bad.append(f"exacto fuera: {path}")
        if gc.route(docs, "GET", path + "x").kind != "direct":
            bad.append(f"exacto con sufijo: {path}x")
    for path in prefix:
        for suffix in ("", "/a", "/a/b"):
            if gc.route(docs, "POST", path + suffix).backend != ("keycloak", "vectra-identity", 8443):
                bad.append(f"prefijo fuera: {path}{suffix}")
        if gc.route(docs, "GET", path + "x").kind == "backend" and gc.route(docs, "GET", path + "x").backend[0] == "keycloak":
            bad.append(f"prefijo partido: {path}x")
    for path in (
        "/auth/admin",
        "/auth/admin/realms/vectra",
        "/auth/realms/master/protocol/openid-connect/token",
        "/auth/realms/vectra/protocol/openid-connect/userinfo",
        "/auth/realms/vectra/protocol/openid-connect/token/introspect",
        "/auth/realms/vectra/protocol/openid-connect/revoke",
        "/auth/realms/vectra/broker/x/endpoint",
        "/auth/realms/vectra/clients-registrations/openid-connect",
        "/auth/realms/vectra",
        "/auth",
        "/auth/",
    ):
        out = gc.route(docs, "GET", path)
        if (out.kind, out.status) != ("direct", 404):
            bad.append(f"debia dar 404: {path}")
    return bad


def _drop_auth_match(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "auth")["spec"]["rules"]:
        rule["matches"] = [m for m in rule["matches"] if not m["path"]["value"].endswith("/account")]


def _add_auth_match(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "auth")["spec"]["rules"]:
        rule["matches"].append({"path": {"type": "Exact", "value": "/auth/realms/vectra/protocol/openid-connect/userinfo"}})


def _widen_auth_prefix(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "auth")["spec"]["rules"]:
        rule["matches"].append({"path": {"type": "PathPrefix", "value": "/auth/realms"}})


@pytest.mark.parametrize("env", ENVS)
def test_auth_routes_exactly_the_list_of_v1(env, docs_by_env):
    assert auth_violations(docs_by_env[env]) == []


@pytest.mark.parametrize("alter", [_drop_auth_match, _add_auth_match, _widen_auth_prefix], ids=["entry-removed", "userinfo-added", "realms-opened"])
def test_auth_list_check_fails_when_the_list_changes(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert auth_violations(docs)


AUTH_POLICY = ge.AUTH_RULE  # X1: la politica de la unica regla de `/auth/**`


def _auth_rules(docs: gc.Docs) -> list[dict[str, Any]]:
    return gc.find(docs, "BackendTrafficPolicy", AUTH_POLICY)["spec"]["rateLimit"]["global"]["rules"]


def _auth_counters(docs: gc.Docs) -> list[dict[str, Any]]:
    return [r for r in _auth_rules(docs) if any("sourceCIDR" in s for s in r.get("clientSelectors", []))]


CIDRS = {"0.0.0.0/0", "::/0"}  # un contador por IP de origen, de IPv4 y de IPv6


def counters_violations(docs: gc.Docs) -> list[str]:
    counters = _auth_counters(docs)
    if len(counters) != 4:
        return [f"debia haber 2 contadores por familia de direcciones y hay {len(counters)} reglas"]
    bad = []
    login = "/auth/realms/vectra/protocol/openid-connect/auth"
    token_url = "/auth/realms/vectra/protocol/openid-connect/token"  # noqa: S105
    same = ["/auth/realms/vectra/login-actions/authenticate", "/auth/realms/vectra/login-actions", login + "?client_id=x"]
    others = ["/auth/realms/vectra/protocol/openid-connect/certs", "/auth/resources/x.css", "/auth/realms/vectra/account"]
    number, unit = gd.rate_limit_numbers()["auth"], gd.rate_limit_units()["auth"]
    by_regex: dict[str, set[str]] = {}
    for counter in counters:
        (selector,) = counter["clientSelectors"]
        if counter["limit"] != {"requests": number, "unit": unit} or counter.get("shared") is not True:
            bad.append(f"contador distinto: {counter}")
        if selector["sourceCIDR"]["type"] != "Distinct" or selector["sourceCIDR"]["value"] not in CIDRS:
            bad.append(f"sourceCIDR distinto: {selector['sourceCIDR']}")
        regex = selector["path"]["value"]
        by_regex.setdefault(regex, set()).add(selector["sourceCIDR"]["value"])
        matches_login = all(re.fullmatch(regex, p) for p in [login, *same])
        matches_token = bool(re.fullmatch(regex, token_url)) or bool(re.fullmatch(regex, token_url + "?grant_type=x"))
        if matches_login == matches_token:
            bad.append(f"el contador no separa login y token: {regex}")
        if any(re.fullmatch(regex, p) for p in others):
            bad.append(f"el contador cuenta otros caminos: {regex}")
    if len(by_regex) != 2 or any(cidrs != CIDRS for cidrs in by_regex.values()):
        bad.append(f"cada contador debia estar con las dos familias de direcciones: {by_regex}")
    return bad


def retry_after_violations(docs: gc.Docs) -> list[str]:
    want = gd.retry_after()
    bad = []
    for btp in of_btp(docs):
        name = btp["metadata"]["name"]
        for entry in btp["spec"].get("responseOverride", []):
            if entry["match"]["statusCodes"][0]["value"] != 429:
                continue
            (header,) = entry["response"]["header"]["set"]
            exp = want["auth"] if name.startswith("auth-") else want["second"]
            if (header["name"], header["value"]) != ("Retry-After", exp):
                bad.append(f"{name}: Retry-After {header['value']} y debia ser {exp}")
    return bad


def of_btp(docs: gc.Docs) -> gc.Docs:
    return [b for b in gc.of_kind(docs, "BackendTrafficPolicy") if b["metadata"]["name"] != "edge-rate-limits" and b["metadata"]["name"] != "closed"]


@pytest.mark.parametrize("env", ENVS)
def test_auth_has_two_counters_per_ip_family_of_600_per_minute_and_retry_after_60(env, docs_by_env):
    assert counters_violations(docs_by_env[env]) == []
    assert retry_after_violations(docs_by_env[env]) == []


def _set_counter(docs: gc.Docs, index: int, key: str, value: Any) -> None:
    counters = _auth_counters(docs)
    counters[index][key] = value


def _drop_counter(docs: gc.Docs) -> None:
    _auth_rules(docs).remove(_auth_counters(docs)[1])


def _drop_ipv6(docs: gc.Docs) -> None:
    rules = _auth_rules(docs)
    for counter in _auth_counters(docs):
        if counter["clientSelectors"][0]["sourceCIDR"]["value"] == "::/0":
            rules.remove(counter)


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: _set_counter(d, 0, "limit", {"requests": 10, "unit": "Minute"}),
        lambda d: _set_counter(d, 1, "shared", False),
        lambda d: _auth_counters(d)[0]["clientSelectors"][0].update(path={"type": "RegularExpression", "value": "^/auth/.*"}),
        _drop_counter,
        _drop_ipv6,
    ],
    ids=["limit-10", "not-shared", "counts-everything", "one-counter", "no-ipv6"],
)
def test_counters_check_fails_on_altered_counters(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert counters_violations(docs)


def test_retry_after_check_fails_on_a_wrong_value():
    docs = copy.deepcopy(gc.load_env("prod"))
    entry = [e for e in gc.find(docs, "BackendTrafficPolicy", AUTH_POLICY)["spec"]["responseOverride"] if e["match"]["statusCodes"][0]["value"] == 429][0]
    entry["response"]["header"]["set"][0]["value"] = "1"
    assert retry_after_violations(docs)
    other = copy.deepcopy(gc.load_env("prod"))
    entry = [e for e in gc.find(other, "BackendTrafficPolicy", "console-read")["spec"]["responseOverride"] if e["match"]["statusCodes"][0]["value"] == 429][0]
    entry["response"]["header"]["set"][0]["value"] = "60"
    assert retry_after_violations(other)


# --- CA-5: promocion ---------------------------------------------------------------------------------


def promotion_violations(docs: gc.Docs) -> list[str]:
    bad = []
    backend = ("governance-service", "vectra-app", 8080)
    ok = gc.route(docs, "GET", "/api/promotion/v1/models", {"state": "aprobado"})
    if (ok.backend, ok.upstream_path) != (backend, "/v1/models"):
        bad.append("GET state=aprobado no se reescribe a /v1/models")
    ok = gc.route(docs, "POST", "/api/promotion/v1/models/abc-1/activation")
    if (ok.backend, ok.upstream_path) != (backend, "/v1/models/abc-1/activation"):
        bad.append("POST de activacion no se reescribe")
    for method, path, query in [
        ("GET", "/api/promotion/v1/models", {}),
        ("GET", "/api/promotion/v1/models", {"state": "borrador"}),
        ("POST", "/api/promotion/v1/models", {"state": "aprobado"}),
        ("GET", "/api/promotion/v1/models/abc/activation", {}),
        ("POST", "/api/promotion/v1/models/a/b/activation", {}),
        ("POST", "/api/promotion/v1/models//activation", {}),
        ("PUT", "/api/promotion/v1/models/abc/activation", {}),
        ("POST", "/api/promotion/v1/other", {}),
        ("GET", "/api/promotion/v1/models/abc", {"state": "aprobado"}),
    ]:
        out = gc.route(docs, method, path, query)
        if (out.kind, out.status) != ("direct", 404):
            bad.append(f"debia dar 404: {method} {path} {query}")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_promotion_allows_only_get_models_approved_and_post_activation(env, docs_by_env):
    assert promotion_violations(docs_by_env[env]) == []


def _drop_query(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "promotion")["spec"]["rules"]:
        for m in rule["matches"]:
            m.pop("queryParams", None)


def _drop_rewrite(docs: gc.Docs) -> None:
    rule = _rule(docs, "promotion", "promotion-models")
    rule["filters"] = [f for f in rule["filters"] if f["type"] != "URLRewrite"]


def _id_with_slash(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "promotion")["spec"]["rules"]:
        for m in rule["matches"]:
            m["path"]["value"] = m["path"]["value"].replace("[^/]+", ".+")


def _open_method(docs: gc.Docs) -> None:
    for rule in gc.find(docs, "HTTPRoute", "promotion")["spec"]["rules"]:
        for m in rule["matches"]:
            m.pop("method", None)


@pytest.mark.parametrize("alter", [_drop_query, _drop_rewrite, _id_with_slash, _open_method], ids=["no-state", "no-rewrite", "id-with-slash", "any-method"])
def test_promotion_check_fails_on_altered_routes(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert promotion_violations(docs)


# --- CA-5: cabeceras internas ---------------------------------------------------------------------


def internal_header_violations(docs: gc.Docs) -> list[str]:
    bad = []
    ctp = gc.find(docs, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]
    if ctp.get("earlyRequestHeaders") != {"removeOnMatch": [{"type": "Prefix", "value": "x-vectra-"}]}:
        bad.append("la entrada no quita el prefijo x-vectra-")
    authenticated = {"console-read", "console-write", "intake-submit", "promotion-models", "promotion-activation"}
    seen = set()
    for route in gc.of_kind(docs, "HTTPRoute"):
        for rule in route["spec"]["rules"]:
            mods = [f for f in rule.get("filters", []) if f["type"] == "RequestHeaderModifier"]
            if rule["name"] in authenticated:
                seen.add(rule["name"])
                if len(mods) != 1 or sorted(mods[0]["requestHeaderModifier"].get("remove", [])) != ["x-vectra-azp", "x-vectra-sub"]:
                    bad.append(f"{rule['name']}: no quita x-vectra-sub y x-vectra-azp hacia el backend")
            elif mods:
                bad.append(f"{rule['name']}: filtro de cabeceras de peticion inesperado")
    if seen != authenticated:
        bad.append(f"reglas autenticadas que faltan: {authenticated - seen}")
    names = json.dumps(docs).lower()
    for header in ("idempotency-key", "x-test-scenario"):
        if header in names:
            bad.append(f"{header} aparece en un manifiesto")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_internal_headers_are_removed_on_entry_and_towards_the_backend_and_app_headers_untouched(env, docs_by_env):
    assert internal_header_violations(docs_by_env[env]) == []


def _no_early_removal(docs: gc.Docs) -> None:
    del gc.find(docs, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["earlyRequestHeaders"]


def _only_sub_removed(docs: gc.Docs) -> None:
    gc.find(docs, "HTTPRoute", "intake")["spec"]["rules"][0]["filters"][1]["requestHeaderModifier"]["remove"] = ["x-vectra-sub"]


def _touch_idempotency_key(docs: gc.Docs) -> None:
    gc.find(docs, "HTTPRoute", "intake")["spec"]["rules"][0]["filters"][1]["requestHeaderModifier"]["remove"].append("Idempotency-Key")


def _touch_test_scenario(docs: gc.Docs) -> None:
    gc.find(docs, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["earlyRequestHeaders"]["removeOnMatch"].append({"type": "Exact", "value": "X-Test-Scenario"})


@pytest.mark.parametrize("alter", [_no_early_removal, _only_sub_removed, _touch_idempotency_key, _touch_test_scenario], ids=["no-early", "one-header", "idempotency-key", "test-scenario"])
def test_internal_headers_check_fails_on_altered_documents(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert internal_header_violations(docs)


# --- CA-5: server, x-envoy-, x-vectra- fuera de la respuesta ----------------------------------------


def response_removal_violations(docs: gc.Docs) -> list[str]:
    late = gc.find(docs, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"]
    bad = []
    if late.get("remove") != ["server"]:
        bad.append("la respuesta conserva server")
    if late.get("removeOnMatch") != [{"type": "Prefix", "value": "x-envoy-"}, {"type": "Prefix", "value": "x-vectra-"}]:
        bad.append("la respuesta conserva x-envoy- o x-vectra-")
    if gc.find(docs, "ClientTrafficPolicy", "edge-client")["spec"]["headers"].get("enableEnvoyHeaders"):
        bad.append("enableEnvoyHeaders activo")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_server_and_envoy_headers_are_removed_from_responses(env, docs_by_env):
    assert response_removal_violations(docs_by_env[env]) == []


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"].pop("remove"),
        lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"]["removeOnMatch"].pop(0),
        lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"].update(enableEnvoyHeaders=True),
    ],
    ids=["server-kept", "x-envoy-kept", "envoy-headers-on"],
)
def test_response_removal_check_fails_on_altered_documents(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert response_removal_violations(docs)


# --- CA-5: cuerpos Problem --------------------------------------------------------------------------


def problem_bodies(docs: gc.Docs) -> list[tuple[str, int, str]]:
    """(donde, estado HTTP, cuerpo) de cada Problem que genera el gateway."""
    found = []
    for hrf in gc.of_kind(docs, "HTTPRouteFilter"):
        direct = hrf["spec"].get("directResponse")
        if direct:
            found.append((f"HTTPRouteFilter/{hrf['metadata']['name']}", direct["statusCode"], direct["body"]["inline"]))
    for btp in gc.of_kind(docs, "BackendTrafficPolicy"):
        for entry in btp["spec"].get("responseOverride", []):
            found.append((f"BackendTrafficPolicy/{btp['metadata']['name']}", entry["match"]["statusCodes"][0]["value"], entry["response"]["body"]["inline"]))
    return found


def problem_violations(docs: gc.Docs) -> list[str]:
    bad = []
    seen = set()
    for where, status, body in problem_bodies(docs):
        seen.add(status)
        try:
            problem = Problem.model_validate_json(body.replace("%TRACE_ID%", TRACE))
        except ValueError as exc:
            bad.append(f"{where}: {status}: {str(exc).splitlines()[0]}")
            continue
        if problem.status != status or problem.correlation_id != TRACE or "%TRACE_ID%" not in body:
            bad.append(f"{where}: {status}: estado o correlation_id")
        if problem.type != f"urn:vectra:problem:{problem.code.value}":
            bad.append(f"{where}: {status}: type")
    if not {401, 403, 404, 413, 429, 503} <= seen:
        bad.append(f"faltan codigos: {sorted({401, 403, 404, 413, 429, 503} - seen)}")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_every_problem_body_validates_with_the_model_of_u0(env, docs_by_env):
    assert problem_violations(docs_by_env[env]) == []


def test_problem_bodies_are_the_ones_u0_produces():
    for _, status, body in problem_bodies(gc.load_env("prod")):
        assert body == ge.problem_json(status)


def _body_with_extra_field(docs: gc.Docs) -> None:
    hrf = gc.find(docs, "HTTPRouteFilter", "problem-not-found")["spec"]["directResponse"]["body"]
    hrf["inline"] = hrf["inline"].replace("}", ', "detail": "/api/x"}')


def _body_without_trace_id(docs: gc.Docs) -> None:
    btp = gc.find(docs, "BackendTrafficPolicy", "intake-submit")["spec"]["responseOverride"][0]["response"]["body"]
    btp["inline"] = btp["inline"].replace("%TRACE_ID%", "-")


def _body_wrong_status(docs: gc.Docs) -> None:
    btp = gc.find(docs, "BackendTrafficPolicy", "intake-submit")["spec"]["responseOverride"][0]
    btp["match"]["statusCodes"][0]["value"] = 402


def _drop_413(docs: gc.Docs) -> None:
    for name in ("console-read", "console-write", "intake-submit", "promotion-models", "promotion-activation", "grafana-read", "grafana-write"):
        spec = gc.find(docs, "BackendTrafficPolicy", name)["spec"]
        spec["responseOverride"] = [e for e in spec["responseOverride"] if e["match"]["statusCodes"][0]["value"] != 413]


@pytest.mark.parametrize("alter", [_body_with_extra_field, _body_without_trace_id, _body_wrong_status, _drop_413], ids=["extra-field", "no-trace-id", "wrong-status", "no-413"])
def test_problem_check_fails_on_altered_bodies(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert problem_violations(docs)


# --- CA-5: cookie de afinidad -----------------------------------------------------------------------


def cookie_violations(docs: gc.Docs) -> list[str]:
    spec = gc.find(docs, "BackendTrafficPolicy", "spa")["spec"]
    lb = spec.get("loadBalancer", {})
    want = {"name": "vectra-spa-route", "ttl": "0s", "attributes": {"Secure": "", "HttpOnly": "", "SameSite": "Strict", "Path": "/"}}
    if lb.get("type") != "ConsistentHash" or lb.get("consistentHash", {}).get("type") != "Cookie":
        return ["la ruta / no usa ConsistentHash de tipo Cookie"]
    return [] if lb["consistentHash"]["cookie"] == want else [f"cookie distinta: {lb['consistentHash']['cookie']}"]


@pytest.mark.parametrize("env", ENVS)
def test_the_spa_route_has_the_session_cookie_affinity(env, docs_by_env):
    assert cookie_violations(docs_by_env[env]) == []
    others = [b["metadata"]["name"] for b in gc.of_kind(docs_by_env[env], "BackendTrafficPolicy") if "loadBalancer" in b["spec"]]
    assert others == ["spa"]


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"].update(ttl="3600s"),
        lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"]["attributes"].pop("HttpOnly"),
        lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"]["attributes"].update(SameSite="Lax"),
        lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"].pop("loadBalancer"),
    ],
    ids=["ttl", "no-httponly", "samesite-lax", "no-affinity"],
)
def test_cookie_check_fails_on_altered_policy(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert cookie_violations(docs)


# --- CA-5: ReferenceGrant ---------------------------------------------------------------------------


def used_services(docs: gc.Docs) -> dict[str, set[str]]:
    used: dict[str, set[str]] = {}
    for route in gc.of_kind(docs, "HTTPRoute"):
        for rule in route["spec"]["rules"]:
            for ref in rule.get("backendRefs", []):
                if ref["namespace"] != route["metadata"]["namespace"]:
                    used.setdefault(ref["namespace"], set()).add(ref["name"])
    return used


def grant_violations(docs: gc.Docs) -> list[str]:
    bad = []
    grants = {g["metadata"]["namespace"]: g for g in gc.of_kind(docs, "ReferenceGrant")}
    used = used_services(docs)
    if set(grants) != set(used):
        bad.append(f"namespaces con grant {sorted(grants)} y usados {sorted(used)}")
    for namespace, grant in grants.items():
        grant_ns, grant_group, grant_service = gd.securitypolicy_grant()
        want_from = [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "namespace": "vectra-edge"}]
        if namespace == grant_ns:  # D-1: la JWKS de la SecurityPolicy, solo hacia el Service de Keycloak
            want_from.append({"group": grant_group, "kind": "SecurityPolicy", "namespace": "vectra-edge"})
            if [t["name"] for t in grant["spec"]["to"]] != [grant_service]:
                bad.append(f"{namespace}: el grant de la SecurityPolicy debia ser solo hacia {grant_service}")
        if grant["spec"]["from"] != want_from:
            bad.append(f"{namespace}: from")
        names = [t["name"] for t in grant["spec"]["to"]]
        if any(t != {"group": "", "kind": "Service", "name": t["name"]} for t in grant["spec"]["to"]):
            bad.append(f"{namespace}: to con algo que no es un Service por nombre")
        if set(names) != used.get(namespace, set()) or len(names) != len(set(names)):
            bad.append(f"{namespace}: {sorted(names)} y los usados son {sorted(used.get(namespace, set()))}")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_reference_grants_admit_exactly_the_services_used(env, docs_by_env):
    assert grant_violations(docs_by_env[env]) == []
    assert used_services(docs_by_env[env]) == {
        "vectra-app": {"console-bff", "case-service", "governance-service"},
        "vectra-identity": {"keycloak"},
        "vectra-observability": {"kube-prometheus-stack-grafana"},
    }


def _set_header(rule: dict[str, Any], name: str, value: str) -> None:
    for entry in rule["filters"][-1]["responseHeaderModifier"]["set"]:
        if entry["name"] == name:
            entry["value"] = value
            return
    raise AssertionError(name)


def _f09(alter: Callable[[gc.Docs], None]) -> Callable[[gc.Docs], None]:
    """Parte de los manifiestos de produccion con F09 habilitada (generados) y los altera."""

    def mutate(docs: gc.Docs) -> None:
        docs[:] = generated_docs("prod", f09=True)
        alter(docs)

    return mutate


def _grant(docs: gc.Docs, namespace: str) -> dict[str, Any]:
    (found,) = [g for g in gc.of_kind(docs, "ReferenceGrant") if g["metadata"]["namespace"] == namespace]
    return found


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: _grant(d, "vectra-app")["spec"]["to"].append({"group": "", "kind": "Service", "name": "other"}),
        lambda d: _grant(d, "vectra-app")["spec"]["to"].pop(),
        lambda d: _grant(d, "vectra-app")["spec"]["from"][0].update(kind="SecurityPolicy"),
        lambda d: d.remove(_grant(d, "vectra-app")),
        lambda d: _grant(d, "vectra-identity")["spec"]["from"].pop(),
        lambda d: _grant(d, "vectra-identity")["spec"]["to"].append({"group": "", "kind": "Service", "name": "other"}),
        lambda d: _grant(d, "vectra-app")["spec"]["from"].append({"group": "gateway.envoyproxy.io", "kind": "SecurityPolicy", "namespace": "vectra-edge"}),
        lambda d: _grant(d, "vectra-observability")["spec"]["to"][0].update(kind="Secret"),
    ],
    ids=["extra-service", "missing-service", "other-kind", "no-grant", "no-policy-source", "extra-service-for-policy", "policy-source-in-app", "not-a-service"],
)
def test_grant_check_fails_on_altered_grants(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    assert grant_violations(docs) == []
    alter(docs)
    assert grant_violations(docs)


def test_the_identity_grant_admits_the_security_policy_only_towards_keycloak():
    grant = _grant(gc.load_env("prod"), "vectra-identity")["spec"]
    assert [f["kind"] for f in grant["from"]] == ["HTTPRoute", "SecurityPolicy"]
    assert [t["name"] for t in grant["to"]] == ["keycloak"]


# --- CA-5: F09 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_f09_is_disabled_in_every_environment_and_generates_nothing(env, docs_by_env):
    assert route_gen.load_values(env)["f09"]["enabled"] is False
    text = json.dumps(docs_by_env[env])
    for word in ("kube-prometheus-stack-prometheus", "federate-basic-auth", "basicAuth", "ExternalSecret", "identity/federate"):
        assert word not in text
    assert "externalsecrets.yaml" not in gc.load_dir(gc.GENERATED / env)
    out = gc.route(docs_by_env[env], "GET", "/federate")
    assert (out.kind, out.status) == ("direct", 404)


@pytest.mark.parametrize("env", ENVS)
def test_f09_enabled_generates_the_route_the_basic_auth_and_the_external_secret(env):
    files = route_gen.generate(route_gen.load_routes(), values_for(env, f09=True))
    assert set(files) == set(ge.FILES) | {ge.EXTERNAL_SECRETS_FILE}
    want = expected(env, f09=True)
    for name, text in files.items():
        assert [d for d in yaml.safe_load_all(text) if d] == want[name], name
    docs = gc.flat(want)
    out = gc.route(docs, "GET", "/federate")
    assert (out.kind, out.backend) == ("backend", ("kube-prometheus-stack-prometheus", "vectra-observability", 9090))
    assert gc.route(docs, "GET", "/federate/x").status == 404
    assert gc.find(docs, "SecurityPolicy", "federate")["spec"]["basicAuth"]["users"]["name"] == "federate-basic-auth"
    secret = gc.find(docs, "ExternalSecret", "federate-basic-auth")["spec"]
    assert secret["secretStoreRef"] == {"name": "vectra-store", "kind": "ClusterSecretStore"}
    assert secret["data"] == [{"secretKey": ".htpasswd", "remoteRef": {"key": "identity/federate", "property": ".htpasswd"}}]
    assert grant_violations(docs) == []


def test_f09_enabled_conftest_passes_and_the_disabled_set_with_the_route_fails():
    docs = generated_docs("prod", f09=True)
    code, output = gc.conftest(docs)
    assert code == 0, output
    base = generated_docs("prod", f09=False)
    base.append(next(d for d in docs if d["kind"] == "ExternalSecret"))
    code, output = gc.conftest(base)
    assert code != 0 and "federate-coherence: " in output


# --- tamano, tiempos, perfil por ruta (del diseno) ---------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_sizes_timeouts_and_profiles_come_from_the_design(env, docs_by_env):
    docs = docs_by_env[env]
    sizes = {k: gd.body_limit(k) for k in gd.route_rows()}
    t = gd.timeouts()
    by_rule = {b["metadata"]["name"]: b["spec"] for b in gc.of_kind(docs, "BackendTrafficPolicy")}
    for rule, key in [("console-read", "/api/console/**"), ("intake-submit", "/api/intake/**"), ("promotion-models", "/api/promotion/**"), ("grafana-write", "/grafana/**")]:
        assert by_rule[rule]["requestBuffer"] == {"limit": sizes[key]}
    for rule in ("spa", AUTH_POLICY):
        assert "requestBuffer" not in by_rule[rule]
    assert by_rule["console-read"]["timeout"]["http"]["requestTimeout"] == t["/api/console/**"]
    assert by_rule[AUTH_POLICY]["timeout"]["http"]["requestTimeout"] == t["/auth/**"]
    assert "timeout" not in by_rule["spa"]


# --- retry y outlier detection (P-U2-02) -------------------------------------------------------------


def retry_violations(docs: gc.Docs) -> list[str]:
    bad = []
    for btp in gc.of_kind(docs, "BackendTrafficPolicy"):
        if "retry" not in btp["spec"]:
            continue
        (ref,) = btp["spec"]["targetRefs"]
        route = gc.find(docs, "HTTPRoute", ref["name"])
        (rule,) = [r for r in route["spec"]["rules"] if r["name"] == ref.get("sectionName")]
        if not all(m.get("method") in ("GET", "HEAD") for m in rule["matches"]):
            bad.append(f"{rule['name']}: reintenta una regla que admite otros metodos")
    retried = {b["metadata"]["name"] for b in gc.of_kind(docs, "BackendTrafficPolicy") if "retry" in b["spec"]}
    if retried != {"console-read", "promotion-models", "grafana-read"}:  # X1: `/auth/**` no reintenta
        bad.append(f"reglas con reintento: {sorted(retried)}")
    return bad


@pytest.mark.parametrize("env", ENVS)
def test_only_idempotent_rules_are_retried(env, docs_by_env):
    assert retry_violations(docs_by_env[env]) == []
    spec = gc.find(docs_by_env[env], "BackendTrafficPolicy", "console-read")["spec"]
    assert spec["retry"] == {"numRetries": 1, "retryOn": {"triggers": ["connect-failure"]}}
    assert spec["circuitBreaker"]["retryBudget"]["percent"] == {"numerator": 20, "denominator": 100}


def test_retry_check_fails_when_a_unsafe_rule_is_retried():
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "BackendTrafficPolicy", "console-write")["spec"]["retry"] = {"numRetries": 1}
    assert retry_violations(docs)
    docs = copy.deepcopy(gc.load_env("prod"))
    gc.find(docs, "BackendTrafficPolicy", "intake-submit")["spec"]["retry"] = {"numRetries": 1}
    assert retry_violations(docs)


@pytest.mark.parametrize("env", ENVS)
def test_outlier_detection_ejects_by_5xx_except_in_the_console(env, docs_by_env):
    for btp in gc.of_kind(docs_by_env[env], "BackendTrafficPolicy"):
        passive = btp["spec"].get("healthCheck", {}).get("passive")
        name = btp["metadata"]["name"]
        if name.startswith("console-"):
            assert passive == {"baseEjectionTime": "30s", "maxEjectionPercent": 50, "consecutive5XxErrors": 0, "consecutiveLocalOriginFailures": 5, "splitExternalLocalOriginErrors": True}
        elif passive is not None:
            assert passive == {"baseEjectionTime": "30s", "maxEjectionPercent": 50, "consecutive5XxErrors": 5}


# --- conftest: cada regla falla sobre un documento alterado -----------------------------------------


def _doc(kind: str, name: str) -> Callable[[gc.Docs], dict[str, Any]]:
    return lambda docs: gc.find(docs, kind, name)


def _remove(kind: str, name: str) -> Callable[[gc.Docs], None]:
    return lambda docs: docs.remove(gc.find(docs, kind, name))


def _rule(docs: gc.Docs, route: str, rule: str) -> dict[str, Any]:
    (found,) = [r for r in gc.find(docs, "HTTPRoute", route)["spec"]["rules"] if r["name"] == rule]
    return found


def _federate_route(docs: gc.Docs) -> None:
    docs.append(
        {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {"name": "federate", "namespace": "vectra-edge"},
            "spec": {"rules": []},
        }
    )


def _new_api_route(docs: gc.Docs) -> None:
    docs.append(
        {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {"name": "other", "namespace": "vectra-edge"},
            "spec": {
                "rules": [
                    {
                        "name": "other",
                        "matches": [{"path": {"type": "Exact", "value": "/api/other"}}],
                        "backendRefs": [{"group": "", "kind": "Service", "name": "other", "namespace": "vectra-app", "port": 8080}],
                    }
                ]
            },
        }
    )



# --- Paso 8 (U02-T10): helpers de las alteraciones ---------------------------------------------------


def _kube(docs: gc.Docs) -> dict[str, Any]:
    return gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["provider"]["kubernetes"]


def _container(docs: gc.Docs) -> dict[str, Any]:
    return _kube(docs)["envoyDeployment"]["container"]


def _pod(docs: gc.Docs) -> dict[str, Any]:
    return _kube(docs)["envoyDeployment"]["pod"]


def _sidecar(docs: gc.Docs) -> dict[str, Any]:
    (found,) = [c for c in _kube(docs)["envoyDeployment"]["patch"]["value"]["spec"]["template"]["spec"]["containers"] if c["name"] == "shutdown-manager"]
    return found


def _telemetry(docs: gc.Docs) -> dict[str, Any]:
    return gc.find(docs, "EnvoyProxy", "api-gateway")["spec"]["telemetry"]


def _listener(docs: gc.Docs) -> dict[str, Any]:
    return gc.find(docs, "Gateway", "api-gateway")["spec"]["listeners"][0]


def _patches(docs: gc.Docs) -> list[dict[str, Any]]:
    return gc.find(docs, "EnvoyPatchPolicy", "auth-fail-closed")["spec"]["jsonPatches"]


def _move_counters_to_edge(docs: gc.Docs) -> None:
    edge = gc.find(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    auth = gc.find(docs, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"]
    edge.extend(auth["rateLimit"]["global"]["rules"])
    del auth["rateLimit"]


def _cert_for(docs: gc.Docs) -> dict[str, Any]:
    return gc.find(docs, "Certificate", "api-gateway")["spec"]



# (regla, caso, alteracion). Cada regla de la politica aparece al menos una vez; la salida debe nombrarla.
MUTATIONS: list[tuple[str, str, Callable[[gc.Docs], None]]] = [
    ("no-app-headers", "idempotency-key-filtered", lambda d: _rule(d, "intake", "intake-submit")["filters"][1]["requestHeaderModifier"]["remove"].append("Idempotency-Key")),
    ("no-app-headers", "test-scenario-in-client-policy", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["earlyRequestHeaders"].update(remove=["x-test-scenario"])),
    ("problem-body", "extra-field", _body_with_extra_field),
    ("problem-body", "no-trace-id", _body_without_trace_id),
    ("problem-body", "wrong-content-type", lambda d: gc.find(d, "HTTPRouteFilter", "problem-not-found")["spec"]["directResponse"].update(contentType="text/plain")),
    ("jwt-deny-by-default", "default-allow", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["authorization"].update(defaultAction="Allow")),
    ("jwt-deny-by-default", "no-authorization", lambda d: gc.find(d, "SecurityPolicy", "intake")["spec"].pop("authorization")),
    ("jwks-internal", "public-jwks-uri", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["jwt"]["providers"][0]["remoteJWKS"].update(uri="https://vectra.banco.internal/auth/realms/vectra/protocol/openid-connect/certs")),
    ("jwks-internal", "cache-duration", lambda d: gc.find(d, "SecurityPolicy", "promotion")["spec"]["jwt"]["providers"][0]["remoteJWKS"].update(cacheDuration="3600s")),
    ("jwks-internal", "claim-to-headers", lambda d: gc.find(d, "SecurityPolicy", "intake")["spec"]["jwt"]["providers"][0].update(claimToHeaders=[{"claim": "sub", "header": "x-vectra-sub"}])),
    ("shared-rate-limits", "not-shared", lambda d: gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"][0].update(shared=False)),
    ("shared-rate-limits", "local", lambda d: gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"].update(type="Local")),
    ("merge-with-gateway", "no-merge-type", lambda d: gc.find(d, "BackendTrafficPolicy", "console-read")["spec"].pop("mergeType")),
    ("client-policy", "trusts-one-hop", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"].update(clientIPDetection={"xForwardedFor": {"numTrustedHops": 1}})),
    ("client-policy", "trusts-zero-hops", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"].update(clientIPDetection={"xForwardedFor": {"numTrustedHops": 0}})),
    ("client-policy", "no-early-removal", _no_early_removal),
    ("client-policy", "server-kept", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"].pop("remove")),
    ("client-policy", "slashes-kept", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["path"].update(escapedSlashesAction="KeepUnchanged")),
    ("client-policy", "slashes-not-merged", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["path"].update(disableMergeSlashes=True)),
    ("cookie-affinity", "ttl", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"].update(ttl="60s")),
    ("cookie-affinity", "samesite", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"]["attributes"].update(SameSite="None")),
    ("outlier", "ejection-time", lambda d: gc.find(d, "BackendTrafficPolicy", "intake-submit")["spec"]["healthCheck"]["passive"].update(baseEjectionTime="5s")),
    ("outlier", "max-percent", lambda d: gc.find(d, "BackendTrafficPolicy", AUTH_POLICY)["spec"]["healthCheck"]["passive"].update(maxEjectionPercent=100)),
    ("console-no-5xx-ejection", "ejects-by-5xx", lambda d: gc.find(d, "BackendTrafficPolicy", "console-read")["spec"]["healthCheck"]["passive"].update(consecutive5XxErrors=5)),
    ("console-no-5xx-ejection", "no-split", lambda d: gc.find(d, "BackendTrafficPolicy", "console-write")["spec"]["healthCheck"]["passive"].update(splitExternalLocalOriginErrors=False)),
    ("console-no-5xx-ejection", "no-passive", lambda d: gc.find(d, "BackendTrafficPolicy", "console-write")["spec"].pop("healthCheck")),
    ("route-parent", "other-gateway", lambda d: gc.find(d, "HTTPRoute", "console")["spec"]["parentRefs"][0].update(name="other")),
    ("route-parent", "no-section", lambda d: gc.find(d, "HTTPRoute", "console")["spec"]["parentRefs"][0].pop("sectionName")),
    ("route-parent", "other-namespace", lambda d: gc.find(d, "HTTPRoute", "console")["metadata"].update(namespace="vectra-app")),
    ("profile-headers", "no-coop", lambda d: _rule(d, "console", "console-read")["filters"][1]["responseHeaderModifier"].update(set=[h for h in _rule(d, "console", "console-read")["filters"][1]["responseHeaderModifier"]["set"] if h["name"] != "Cross-Origin-Opener-Policy"])),
    ("profile-headers", "grafana-frames-api", lambda d: _rule(d, "console", "console-read")["filters"][1]["responseHeaderModifier"]["set"].append({"name": "X-Frame-Options", "value": "SAMEORIGIN"})),
    ("profile-headers", "no-profile-on-spa", lambda d: _rule(d, "spa", "spa").update(filters=[])),
    ("profile-headers", "api-with-self-ancestors", lambda d: _rule(d, "intake", "intake-submit")["filters"][2]["responseHeaderModifier"].update(add=[{"name": "Content-Security-Policy", "value": "frame-ancestors 'self'"}])),
    ("internal-headers-removed", "no-request-modifier", lambda d: _rule(d, "promotion", "promotion-models").update(filters=[f for f in _rule(d, "promotion", "promotion-models")["filters"] if f["type"] != "RequestHeaderModifier"])),
    ("internal-headers-removed", "only-sub", lambda d: _rule(d, "intake", "intake-submit")["filters"][1]["requestHeaderModifier"].update(remove=["x-vectra-sub"])),
    ("routes-complete", "no-closed-route", _remove("HTTPRoute", "closed")),
    ("routes-complete", "no-client-policy", _remove("ClientTrafficPolicy", "edge-client")),
    ("unexpected-document", "extra-route", lambda d: d.append({"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute", "metadata": {"name": "extra", "namespace": "vectra-edge"}, "spec": {"rules": []}})),
    ("no-retry-unsafe", "retry-on-write", lambda d: gc.find(d, "BackendTrafficPolicy", "console-write")["spec"].update(retry={"numRetries": 1})),
    ("no-retry-unsafe", "retry-on-post-only-rule", lambda d: gc.find(d, "BackendTrafficPolicy", "promotion-activation")["spec"].update(retry={"numRetries": 1})),
    ("no-retry-unsafe", "retry-on-whole-route", lambda d: gc.find(d, "BackendTrafficPolicy", "console-read")["spec"]["targetRefs"][0].pop("sectionName")),
    ("authenticated-has-security-policy", "no-policy-for-intake", _remove("SecurityPolicy", "intake")),
    ("authenticated-has-security-policy", "policy-without-jwt", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"].pop("jwt")),
    ("authenticated-has-security-policy", "new-authenticated-route", _new_api_route),
    ("every-rule-has-policy", "rule-without-traffic-policy", _remove("BackendTrafficPolicy", "grafana-write")),
    ("closed-prefixes", "api-not-closed", lambda d: gc.find(d, "HTTPRoute", "closed")["spec"]["rules"].remove(_rule(d, "closed", "closed-api"))),
    ("closed-prefixes", "auth-with-backend", lambda d: _rule(d, "closed", "closed-auth").update(backendRefs=[{"group": "", "kind": "Service", "name": "keycloak", "namespace": "vectra-identity", "port": 8443}])),
    ("closed-prefixes", "federate-open", lambda d: _rule(d, "closed", "closed-federate").update(filters=[])),
    ("reference-grants-exact", "extra-service", lambda d: [g for g in gc.of_kind(d, "ReferenceGrant") if g["metadata"]["namespace"] == "vectra-app"][0]["spec"]["to"].append({"group": "", "kind": "Service", "name": "other"})),
    ("reference-grants-exact", "wrong-from", lambda d: gc.of_kind(d, "ReferenceGrant")[0]["spec"]["from"][0].update(namespace="vectra-app")),
    ("rate-limit-global", "no-global-rule", lambda d: gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"].remove([r for r in gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"] if "clientSelectors" not in r][0])),
    ("rate-limit-global", "global-100", lambda d: [r for r in gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"] if "clientSelectors" not in r][0].update(limit={"requests": 100, "unit": "Second"})),
    ("federate-coherence", "route-without-policy", lambda d: _federate_route(d)),
    ("security-policy-target", "policy-for-no-route", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["targetRefs"][0].update(name="ghost")),
    # --- ramas de las reglas que antes no tenian caso ---
    ("jwks-internal", "backend-ref", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["jwt"]["providers"][0]["remoteJWKS"]["backendRefs"][0].update(name="other")),
    ("jwks-internal", "issuer-realm", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["jwt"]["providers"][0].update(issuer="https://vectra.banco.internal/auth/realms/other")),
    ("jwks-internal", "issuer-host", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["jwt"]["providers"][0].update(issuer="https://otro.example/auth/realms/vectra")),
    ("client-policy", "late-prefix", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"]["removeOnMatch"].pop()),
    ("client-policy", "envoy-headers", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"].update(enableEnvoyHeaders=True)),
    ("cookie-affinity", "type", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"].update(type="Random")),
    ("cookie-affinity", "hash-type", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"].update(type="Header")),
    ("outlier", "5xx-threshold", lambda d: gc.find(d, "BackendTrafficPolicy", "intake-submit")["spec"]["healthCheck"]["passive"].update(consecutive5XxErrors=10)),
    ("console-no-5xx-ejection", "local-origin-threshold", lambda d: gc.find(d, "BackendTrafficPolicy", "console-read")["spec"]["healthCheck"]["passive"].update(consecutiveLocalOriginFailures=1)),
    ("route-parent", "two-hostnames", lambda d: gc.find(d, "HTTPRoute", "console")["spec"]["hostnames"].append("vectra.localtest.me")),
    ("route-parent", "unknown-hostname", lambda d: gc.find(d, "HTTPRoute", "console")["spec"].update(hostnames=["otro.example"])),
    ("profile-headers", "grafana-csp", lambda d: _rule(d, "grafana", "grafana-read")["filters"][0]["responseHeaderModifier"]["set"].append({"name": "Content-Security-Policy", "value": "frame-ancestors 'none'"})),
    ("profile-headers", "grafana-xfo", lambda d: _set_header(_rule(d, "grafana", "grafana-write"), "X-Frame-Options", "DENY")),
    ("profile-headers", "auth-csp", lambda d: _rule(d, "auth", AUTH_POLICY)["filters"][0]["responseHeaderModifier"].pop("add")),
    ("profile-headers", "auth-xfo", lambda d: _rule(d, "auth", AUTH_POLICY)["filters"][0]["responseHeaderModifier"]["set"].append({"name": "X-Frame-Options", "value": "SAMEORIGIN"})),
    ("profile-headers", "page-csp-text", lambda d: _set_header(_rule(d, "console", "console-write"), "Content-Security-Policy", "default-src *; frame-ancestors 'none'; require-trusted-types-for 'script'; trusted-types 'none'")),
    ("profile-headers", "hsts", lambda d: _set_header(_rule(d, "spa", "spa"), "Strict-Transport-Security", "max-age=0")),
    ("profile-headers", "two-modifiers", lambda d: _rule(d, "spa", "spa")["filters"].append(copy.deepcopy(_rule(d, "spa", "spa")["filters"][0]))),
    ("reference-grants-exact", "missing-grant", lambda d: d.remove(_grant(d, "vectra-app"))),
    ("reference-grants-exact", "not-a-service", lambda d: _grant(d, "vectra-observability")["spec"]["to"][0].update(kind="Secret")),
    ("reference-grants-exact", "no-policy-source", lambda d: _grant(d, "vectra-identity")["spec"]["from"].pop()),
    ("reference-grants-exact", "policy-source-in-app", lambda d: _grant(d, "vectra-app")["spec"]["from"].append({"group": "gateway.envoyproxy.io", "kind": "SecurityPolicy", "namespace": "vectra-edge"})),
    ("federate-coherence", "no-external-secret", _f09(lambda d: d.remove(gc.find(d, "ExternalSecret", "federate-basic-auth")))),
    ("federate-coherence", "no-policy", _f09(lambda d: d.remove(gc.find(d, "SecurityPolicy", "federate")))),
    ("federate-coherence", "external-secret-without-route", lambda d: d.append(ge.externalsecrets()[0])),
    ("federate-coherence", "wrong-secret", _f09(lambda d: gc.find(d, "SecurityPolicy", "federate")["spec"]["basicAuth"]["users"].update(name="otro"))),
    ("federate-coherence", "wrong-vault-key", _f09(lambda d: gc.find(d, "ExternalSecret", "federate-basic-auth")["spec"]["data"][0]["remoteRef"].update(key="identity/otro"))),
    ("closed-prefixes", "no-404-override", lambda d: gc.find(d, "BackendTrafficPolicy", "closed")["spec"].update(responseOverride=[e for e in gc.find(d, "BackendTrafficPolicy", "closed")["spec"]["responseOverride"] if e["match"]["statusCodes"][0]["value"] != 404])),
    ("closed-no-rate-limit", "declares-429", lambda d: gc.find(d, "BackendTrafficPolicy", "closed")["spec"]["responseOverride"].append(ge.override(429, "1"))),
    ("closed-no-rate-limit", "declares-rate-limit", lambda d: gc.find(d, "BackendTrafficPolicy", "closed")["spec"].update(rateLimit={"type": "Global", "global": {"rules": []}})),
    ("closed-prefixes", "override-from-backend", lambda d: [e.update(source="Backend") for e in gc.find(d, "BackendTrafficPolicy", "closed")["spec"]["responseOverride"]]),
    ("environment-values", "prod-with-simulator", lambda d: gc.find(d, "SecurityPolicy", "intake")["spec"]["authorization"]["rules"][0]["principal"]["jwt"]["claims"][0]["values"].append("channel-simulator")),
    ("environment-values", "prod-simulator-limit", lambda d: gc.find(d, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"].append({"limit": {"requests": 30, "unit": "Second"}, "shared": True, "clientSelectors": [{"headers": [{"name": "x-vectra-azp", "type": "Exact", "value": "channel-simulator"}]}]})),
    ("environment-values", "staging-hostname", lambda d: gc.find(d, "HTTPRoute", "console")["spec"].update(hostnames=["vectra.staging.banco.internal"])),
    ("environment-values", "staging-issuer", lambda d: gc.find(d, "SecurityPolicy", "console")["spec"]["jwt"]["providers"][0].update(issuer="https://vectra.staging.banco.internal/auth/realms/vectra")),
    # --- Paso 8 (U02-T10) ---
    ("gateway-class", "controller", lambda d: gc.find(d, "GatewayClass", "envoy-gateway")["spec"].update(controllerName="example.com/other")),
    ("gateway-class", "parameters-ref", lambda d: gc.find(d, "GatewayClass", "envoy-gateway")["spec"]["parametersRef"].update(name="other")),
    ("gateway-class", "name", lambda d: gc.find(d, "GatewayClass", "envoy-gateway")["metadata"].update(name="otra")),
    ("gateway-listener", "name", lambda d: gc.find(d, "Gateway", "api-gateway")["metadata"].update(name="otro")),
    ("gateway-listener", "namespace", lambda d: gc.find(d, "Gateway", "api-gateway")["metadata"].update(namespace="vectra-app")),
    ("gateway-listener", "class", lambda d: gc.find(d, "Gateway", "api-gateway")["spec"].update(gatewayClassName="otra")),
    ("gateway-listener", "two-listeners", lambda d: gc.find(d, "Gateway", "api-gateway")["spec"]["listeners"].append(copy.deepcopy(_listener(d)))),
    ("gateway-listener", "listener-name", lambda d: _listener(d).update(name="web")),
    ("gateway-listener", "port", lambda d: _listener(d).update(port=8443)),
    ("gateway-listener", "protocol", lambda d: _listener(d).update(protocol="HTTP")),
    ("gateway-listener", "hostname", lambda d: _listener(d).update(hostname="otro.example")),
    ("gateway-listener", "tls-passthrough", lambda d: _listener(d)["tls"].update(mode="Passthrough")),
    ("gateway-listener", "tls-secret", lambda d: _listener(d)["tls"]["certificateRefs"][0].update(name="otro-secret")),
    ("certificate-issuer", "namespace", lambda d: gc.find(d, "Certificate", "api-gateway")["metadata"].update(namespace="vectra-app")),
    ("certificate-issuer", "secret", lambda d: _cert_for(d).update(secretName="otro")),
    ("certificate-issuer", "two-dns-names", lambda d: _cert_for(d)["dnsNames"].append("vectra.localtest.me")),
    ("certificate-issuer", "dns-name", lambda d: _cert_for(d).update(dnsNames=["otro.example"])),
    ("certificate-issuer", "namespaced-issuer", lambda d: _cert_for(d)["issuerRef"].update(kind="Issuer")),
    ("certificate-issuer", "unknown-issuer", lambda d: _cert_for(d)["issuerRef"].update(name="letsencrypt")),
    ("envoy-identity", "service-account", lambda d: _kube(d).update(envoyServiceAccount={"name": "envoy"})),
    ("envoy-identity", "pod-label", lambda d: _pod(d)["labels"].update({"app.kubernetes.io/name": "envoy"})),
    ("envoy-image", "registry", lambda d: _container(d).update(image="docker.io/envoyproxy/envoy@" + "sha256:" + "9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0")),
    ("envoy-image", "no-digest", lambda d: _container(d).update(image="registro.banco.internal/vectra/envoy:distroless-v1.39.5")),
    ("envoy-image", "other-digest", lambda d: _container(d).update(image="registro.banco.internal/vectra/envoy@sha256:" + "0" * 64)),
    ("envoy-image", "registry-only", lambda d: _container(d).update(image="otro.io/vectra/envoy@sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0")),
    ("envoy-image", "other-mirror", lambda d: _container(d).update(image="registro.banco.internal/vectra/otro@sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0")),
    ("envoy-non-root", "pod", lambda d: _pod(d)["securityContext"].update(runAsNonRoot=False)),
    ("envoy-non-root", "container", lambda d: _container(d)["securityContext"].pop("runAsNonRoot")),
    ("envoy-no-privileged", "privileged", lambda d: _container(d)["securityContext"].update(privileged=True)),
    ("envoy-no-privileged", "escalation", lambda d: _container(d)["securityContext"].update(allowPrivilegeEscalation=True)),
    ("envoy-readonly-rootfs", "writable", lambda d: _container(d)["securityContext"].update(readOnlyRootFilesystem=False)),
    ("envoy-readonly-rootfs", "missing", lambda d: _container(d).pop("securityContext")),
    ("envoy-hardening", "pod-seccomp", lambda d: _pod(d)["securityContext"].pop("seccompProfile")),
    ("envoy-hardening", "container-seccomp", lambda d: _container(d)["securityContext"].update(seccompProfile={"type": "Unconfined"})),
    ("envoy-hardening", "capabilities", lambda d: _container(d)["securityContext"].update(capabilities={"add": ["NET_ADMIN"]})),
    ("envoy-resources", "no-limits", lambda d: _container(d)["resources"].pop("limits")),
    ("envoy-resources", "sidecar-without-patch", lambda d: _kube(d)["envoyDeployment"].pop("patch")),
    ("envoy-resources", "sidecar-patch-type", lambda d: _kube(d)["envoyDeployment"]["patch"].update(type="JSONMerge")),
    ("envoy-resources", "sidecar-no-limits", lambda d: _sidecar(d)["resources"].pop("limits")),
    ("envoy-resources", "sidecar-limits", lambda d: _sidecar(d)["resources"]["limits"].update(memory="1Gi")),
    ("envoy-resources", "sidecar-missing", lambda d: _kube(d)["envoyDeployment"]["patch"]["value"]["spec"]["template"]["spec"].update(containers=[])),
    ("envoy-resources", "patches-envoy", lambda d: _kube(d)["envoyDeployment"]["patch"]["value"]["spec"]["template"]["spec"]["containers"].append({"name": "envoy", "resources": {}})),
    ("client-tls", "min-1.0", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["tls"].update(minVersion="1.0")),
    ("client-tls", "max-auto", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["tls"].update(maxVersion="Auto")),
    ("client-tls", "missing", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"].pop("tls")),
    ("envoy-resources", "memory", lambda d: _container(d)["resources"]["requests"].update(memory="1Gi")),
    ("envoy-priority", "class", lambda d: _pod(d).update(priorityClassName="system-cluster-critical")),
    ("envoy-priority", "missing", lambda d: _pod(d).pop("priorityClassName")),
    ("envoy-criticality", "pod-label", lambda d: _pod(d)["labels"].pop("vectra.io/criticality")),
    ("envoy-criticality", "deployment-label", lambda d: gc.find(d, "Gateway", "api-gateway")["spec"].pop("infrastructure")),
    ("envoy-service", "type", lambda d: _kube(d)["envoyService"].update(type="ClusterIP")),
    ("envoy-service", "cluster-policy", lambda d: _kube(d)["envoyService"].update(externalTrafficPolicy="Cluster")),
    ("envoy-service", "label", lambda d: _kube(d)["envoyService"].update(labels={"app.kubernetes.io/name": "envoy"})),
    ("envoy-scaling", "replicas", lambda d: _kube(d)["envoyDeployment"].update(replicas=1)),
    ("envoy-scaling", "hpa-range", lambda d: _kube(d)["envoyHpa"].update(maxReplicas=10)),
    ("envoy-scaling", "hpa-target", lambda d: _kube(d)["envoyHpa"]["metrics"][0]["resource"]["target"].update(averageUtilization=90)),
    ("envoy-scaling", "pdb", lambda d: _kube(d)["envoyPDB"].update(minAvailable=0)),
    ("envoy-scaling", "spread", lambda d: _pod(d)["topologySpreadConstraints"][0].update(topologyKey="kubernetes.io/hostname")),
    ("access-log-allowlist", "extra-field", lambda d: _telemetry(d)["accessLog"]["settings"][0]["format"]["json"].update(path="%REQ(:PATH)%")),
    ("access-log-allowlist", "authorization", lambda d: _telemetry(d)["accessLog"]["settings"][0]["format"]["json"].update(method="%REQ(AUTHORIZATION)%")),
    ("access-log-allowlist", "missing-field", lambda d: _telemetry(d)["accessLog"]["settings"][0]["format"]["json"].pop("client_ip")),
    ("access-log-allowlist", "text-format", lambda d: _telemetry(d)["accessLog"]["settings"][0].update(format={"type": "Text", "text": "%REQ(:PATH)%"})),
    ("access-log-allowlist", "two-settings", lambda d: _telemetry(d)["accessLog"]["settings"].append(copy.deepcopy(_telemetry(d)["accessLog"]["settings"][0]))),
    ("access-log-allowlist", "other-sink", lambda d: _telemetry(d)["accessLog"]["settings"][0].update(sinks=[{"type": "File", "file": {"path": "/var/log/envoy.log"}}])),
    ("access-log-allowlist", "disabled", lambda d: _telemetry(d)["accessLog"].update(disable=True)),
    ("tracing", "sampling", lambda d: _telemetry(d)["tracing"].update(samplingRate=1)),
    ("tracing", "collector", lambda d: _telemetry(d)["tracing"]["provider"]["backendRefs"][0].update(port=4318)),
    ("tracing", "host-and-port", lambda d: _telemetry(d)["tracing"].update(provider={"type": "OpenTelemetry", "host": "otel-collector.vectra-observability.svc", "port": 4317})),
    ("fail-closed-patch", "type", lambda d: gc.find(d, "EnvoyPatchPolicy", "auth-fail-closed")["spec"].update(type="Other")),
    ("fail-closed-patch", "target", lambda d: gc.find(d, "EnvoyPatchPolicy", "auth-fail-closed")["spec"]["targetRef"].update(name="other")),
    ("fail-closed-patch", "one-patch", lambda d: _patches(d).pop()),
    ("fail-closed-patch", "not-a-listener", lambda d: _patches(d)[0].update(type="type.googleapis.com/envoy.config.cluster.v3.Cluster")),
    ("fail-closed-patch", "other-listener", lambda d: _patches(d)[0].update(name="vectra-edge/api-gateway/web")),
    ("fail-closed-patch", "all-rate-limit-filters", lambda d: _patches(d)[0]["operation"].update(jsonPath="..http_filters[?(@.name=~'envoy.filters.http.ratelimit.*')].typed_config")),
    ("fail-closed-patch", "three-patches", lambda d: _patches(d).append(copy.deepcopy(_patches(d)[0]))),
    ("fail-closed-patch", "fail-open", lambda d: _patches(d)[0]["operation"].update(value=False)),
    ("fail-closed-patch", "status-500", lambda d: _patches(d)[1]["operation"].update(value={"code": 500})),
    ("environment-issuer", "kind-issuer-in-prod", lambda d: _cert_for(d)["issuerRef"].update(name="vectra-internal-ca")),
    ("environment-issuer", "dns-name", lambda d: _cert_for(d).update(dnsNames=["vectra.staging.banco.internal"])),
    ("environment-issuer", "listener-hostname", lambda d: _listener(d).update(hostname="vectra.staging.banco.internal")),
    ("environment-issuer", "kind-image-in-prod", lambda d: _container(d).update(image="kind-registry:5000/vectra/envoy@sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0")),
    ("gateway-wiring", "gateway-without-class", _remove("GatewayClass", "envoy-gateway")),
    ("gateway-wiring", "class-without-proxy", _remove("EnvoyProxy", "api-gateway")),
    ("gateway-wiring", "listener-secret", lambda d: _cert_for(d).update(secretName="otro")),
    ("gateway-wiring", "route-without-gateway", _remove("Gateway", "api-gateway")),
    ("auth-rate-limit-isolated", "counters-back-in-edge", _move_counters_to_edge),
    ("auth-rate-limit-isolated", "counters-elsewhere", lambda d: gc.find(d, "BackendTrafficPolicy", "console-read")["spec"].update(rateLimit={"type": "Global", "global": {"rules": []}})),
    ("auth-rate-limit-isolated", "target", lambda d: gc.find(d, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"]["targetRefs"][0].pop("sectionName")),
    ("auth-rate-limit-isolated", "one-counter", lambda d: gc.find(d, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"]["rateLimit"]["global"]["rules"].pop()),
    ("auth-rate-limit-isolated", "retry", lambda d: gc.find(d, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"].update(retry={"numRetries": 1})),
    ("auth-rate-limit-isolated", "two-rules", lambda d: _rule(d, "auth", ge.AUTH_RULE) and gc.find(d, "HTTPRoute", "auth")["spec"]["rules"].append({**copy.deepcopy(_rule(d, "auth", ge.AUTH_RULE)), "name": "otra"})),
    ("fail-closed-domain", "patch-on-edge-domain", lambda d: [_patches(d)[i]["operation"].update(jsonPath=_patches(d)[i]["operation"]["jsonPath"].replace("auth-rate-limits", "edge-rate-limits")) for i in (0, 1)]),
]


def test_every_rule_has_a_failing_case():
    assert {rule for rule, _, _ in MUTATIONS} == gc.policy_rules()


@pytest.mark.parametrize("env", ENVS)
def test_conftest_passes_on_the_generated_manifests(env, docs_by_env):
    code, output = gc.conftest(docs_by_env[env], env)
    assert code == 0, output


@pytest.mark.parametrize(("docs_env", "dir_env"), [("kind", "prod"), ("prod", "kind"), ("staging", "kind"), ("kind", "staging"), ("prod", "elsewhere")])
def test_conftest_tells_the_environments_apart(docs_env, dir_env, docs_by_env):
    code, output = gc.conftest(docs_by_env[docs_env], dir_env)
    assert code != 0 and "environment-values: " in output, output


@pytest.mark.parametrize(("rule", "case", "mutate"), MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in MUTATIONS])
def test_rule_fails_on_an_altered_document(rule, case, mutate, docs_by_env):
    docs = copy.deepcopy(docs_by_env["prod"])
    mutate(docs)
    code, output = gc.conftest(docs)
    assert code != 0, f"{rule}/{case}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{case}: la salida no nombra la regla\n{output}"


# --- esquemas y kubeconform (CA-2) -------------------------------------------------------------------


@pytest.fixture(scope="module")
def schemas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("schemas")
    crd_schemas.convert(gc.CHART, out, gc.ESO_CHART, cert_manager_chart=gc.CERT_MANAGER_CHART)
    return out


@pytest.mark.parametrize("env", ENVS)
def test_kubeconform_validates_every_document_with_no_missing_schema(env, schemas):
    code, output = gc.kubeconform(gc.GENERATED / env, schemas)
    assert code == 0, output
    count = sum(len(v) for v in gc.load_dir(gc.GENERATED / env).values())
    assert f"Valid: {count}, Invalid: 0, Errors: 0, Skipped: 0" in output, output


def test_kubeconform_fails_on_an_unknown_field(schemas, tmp_path):
    for kind, name, path in [
        ("BackendTrafficPolicy", "console-read", ["spec", "retriez"]),
        ("HTTPRoute", "console", ["spec", "rules", 0, "mtches"]),
        ("SecurityPolicy", "console", ["spec", "jwt", "providers", 0, "issuerr"]),
        ("ClientTrafficPolicy", "edge-client", ["spec", "headers", "lateResponseHeaders", "removeOnMatch", 0, "valu"]),
    ]:
        docs = copy.deepcopy(gc.load_env("prod"))
        node: Any = gc.find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = "x"
        target = tmp_path / kind
        target.mkdir()
        (target / "all.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        code, output = gc.kubeconform(target, schemas)
        assert code != 0 and "Invalid: 0" not in output, (kind, output)


def test_kubeconform_fails_on_a_kind_without_schema(schemas, tmp_path):
    (tmp_path / "x.yaml").write_text("apiVersion: gateway.envoyproxy.io/v1alpha1\nkind: Unknown\nmetadata: {name: x}\n", encoding="utf-8")
    code, _ = gc.kubeconform(tmp_path, schemas)
    assert code != 0


@pytest.mark.parametrize("env", ENVS)
def test_kubeconform_validates_the_external_secret_when_f09_is_enabled(env, schemas, tmp_path):
    files = route_gen.generate(route_gen.load_routes(), values_for(env, f09=True))
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    code, output = gc.kubeconform(tmp_path, schemas)
    assert code == 0, output
    count = sum(len([d for d in yaml.safe_load_all(t) if d]) for t in files.values())
    assert f"Valid: {count}, Invalid: 0, Errors: 0, Skipped: 0" in output, output
    assert ge.EXTERNAL_SECRETS_FILE in files


def test_kubeconform_fails_on_an_external_secret_with_an_unknown_field(schemas, tmp_path):
    docs = generated_docs("prod", f09=True)
    gc.find(docs, "ExternalSecret", "federate-basic-auth")["spec"]["datta"] = []
    (tmp_path / "all.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
    code, output = gc.kubeconform(tmp_path, schemas)
    assert code != 0 and "Invalid: 0" not in output, output


# --- el oraculo lee el diseno (F-02) ----------------------------------------------------------


def _alter(attribute: str, old: str, new: str) -> tuple[str, str, str]:
    return (attribute, old, new)


# (documento de diseno, texto, texto alterado). Cada alteracion cambia un valor que fija el diseno; el oraculo lo lee
# alterado, asi que deja de coincidir con los manifiestos generados. Si un valor estuviera escrito a mano en el
# oraculo, la alteracion no lo movería y la prueba fallaria.
DESIGN_ALTERATIONS = [
    ("INFRASTRUCTURE", "`console-bff` 8080", "`console-bff` 8081"),
    ("INFRASTRUCTURE", "`keycloak` 8443 (`vectra-identity`)", "`keycloak` 9443 (`vectra-identity`)"),
    ("INFRASTRUCTURE", "`kube-prometheus-stack-grafana` 80", "`kube-prometheus-stack-grafana` 3000"),
    ("INFRASTRUCTURE", "`cacheDuration` de 5 min", "`cacheDuration` de 10 min"),
    ("INFRASTRUCTURE", "`api-gateway` en `vectra-edge`, con el listener `https`", "`api-gateway` en `vectra-edge`, con el listener `web`"),
    ("INFRASTRUCTURE", "solo hacia el Service `keycloak`", "solo hacia el Service `otro`"),
    ("INFRASTRUCTURE", "https://<hostname público>/auth/realms/vectra", "https://<hostname público>/auth/realms/otro"),
    ("INFRASTRUCTURE", "| kind | `vectra.localtest.me` |", "| kind | `vectra.otro.me` |"),
    ("NFR_PATTERNS", "5 errores 5xx consecutivos sacan un pod del balanceo por 30 s", "5 errores 5xx consecutivos sacan un pod del balanceo por 45 s"),
    ("NFR_PATTERNS", "hasta el 50 % de los pods", "hasta el 40 % de los pods"),
    ("NFR_PATTERNS", "5 errores 5xx consecutivos", "7 errores 5xx consecutivos"),
    ("NFR_PATTERNS", "1 reintento ante `connect-failure`", "2 reintento ante `connect-failure`"),
    ("NFR_PATTERNS", "presupuesto del 20 %", "presupuesto del 25 %"),
    ("NFR_PATTERNS", "| `/auth/**` | 10 s |", "| `/auth/**` | 12 s |"),
    ("NFR_PATTERNS", "prefijo reservado `x-vectra-`", "prefijo reservado `x-mio-`"),
    ("NFR_PATTERNS", "`x-vectra-azp`", "`x-vectra-azq`"),
    ("NFR_REQUIREMENTS", "no confía en ningún salto", "confía en un salto"),
    ("BUSINESS_RULES", "se tratan con `UnescapeAndRedirect`", "se tratan con `RejectRequest`"),
    ("BUSINESS_RULES", "las barras dobles se fusionan", "las barras dobles se mantienen"),
    ("BUSINESS_RULES", "Se ocultan las cabeceras `server` y `x-envoy-*`", "Se ocultan las cabeceras `via` y `x-envoy-*`"),
    ("BUSINESS_RULES", "Se ocultan las cabeceras `server` y `x-envoy-*`", "Se ocultan las cabeceras `server` y `x-mio-*`"),
    ("BUSINESS_RULES", "`/api/` y `/auth/` son prefijos cerrados", "`/api/` y `/grafana/` son prefijos cerrados"),
    ("BUSINESS_RULES", "su política no declara 429", "su política declara 429"),
    ("NFR_PATTERNS", "Solo `GET`/`HEAD`: 1 reintento", "Solo `GET`: 1 reintento"),
    ("NFR_PATTERNS", "- `/auth/**` no reintenta", "- `/auth/**` reintenta"),
    ("DOMAIN_ENTITIES", "JWT válido de `vectra-console`", "JWT válido de `vectra-consola`"),
    ("DOMAIN_ENTITIES", "JWT con `intake:submit`", "JWT con `intake:send`"),
    ("DOMAIN_ENTITIES", "`azp` = `channel` (F04)", "`azp` = `canal` (F04)"),
    ("DOMAIN_ENTITIES", "JWT de `promotion-tool`", "JWT de `promotion-cli`"),
    ("DOMAIN_ENTITIES", "`governance:promotion`, `acr = mfa`", "`governance:promote`, `acr = mfa`"),
    ("DOMAIN_ENTITIES", "`governance:promotion`, `acr = mfa`", "`governance:promotion`, `acr = pwd`"),
    ("DOMAIN_ENTITIES", "rol `ingeniero_riesgo`, `governance", "rol `cro`, `governance"),
    ("DOMAIN_ENTITIES", "llega como `/v1/intake/applications`", "llega como `/v2/intake/applications`"),
    ("DOMAIN_ENTITIES", "llega como `/v1/models`, y", "llega como `/v2/models`, y"),
    ("DOMAIN_ENTITIES", "`/api/promotion/v1/models/{id}/activation` (solo `POST`)", "`/api/promotion/v1/models/{id}/activate` (solo `POST`)"),
    ("DOMAIN_ENTITIES", "con `state=aprobado`", "con `state=borrador`"),
    ("DOMAIN_ENTITIES", "(solo `POST /v1/intake/applications`)", "(solo `PUT /v1/intake/applications`)"),
    ("DOMAIN_ENTITIES", "`SameSite=Strict`;", "`SameSite=Lax`;"),
    ("DOMAIN_ENTITIES", "cookie de sesión (TTL 0 s)", "cookie de sesión (TTL 60 s)"),
    ("DOMAIN_ENTITIES", "`path=/`", "`path=/spa`"),
    ("DOMAIN_ENTITIES", "cookie** `vectra-spa-route`", "cookie** `vectra-otra-ruta`"),
    ("DOMAIN_ENTITIES", "Secret `federate-basic-auth`", "Secret `federate-otro`"),
    ("DOMAIN_ENTITIES", "clave de bóveda `identity/federate`", "clave de bóveda `identity/otro`"),
    ("DOMAIN_ENTITIES", "20 req/s por `sub`", "25 req/s por `sub`"),
    ("DOMAIN_ENTITIES", "600 req/min por IP en login", "600 req/s por IP en login"),
    ("DOMAIN_ENTITIES", "Límite global: 200 req/s", "Límite global: 150 req/s"),
    ("DOMAIN_ENTITIES", "`protocol/openid-connect/token`)", "`protocol/openid-connect/certs`)"),
    ("DOMAIN_ENTITIES", "`X-Frame-Options: DENY`", "`X-Frame-Options: SAMEORIGIN`"),
    ("DOMAIN_ENTITIES", "| 64 KiB | Perfil `api` |", "| 48 KiB | Perfil `api` |"),
    # --- Paso 8 (U02-T10): cada valor nuevo que fija el diseno ---
    ("INFRASTRUCTURE", "`vectra-internal-ca` en kind", "`vectra-interna` en kind"),
    ("INFRASTRUCTURE", "el ejemplo es `banco-ca`", "el ejemplo es `ca-banco`"),
    ("INFRASTRUCTURE", "listener HTTPS (443)", "listener HTTPS (8443)"),
    ("INFRASTRUCTURE", "`registro.banco.internal/vectra/envoy` (`kind-registry:5000/vectra/envoy` en kind)", "`registro.banco.internal/vectra/proxy` (`kind-registry:5000/vectra/envoy` en kind)"),
    ("INFRASTRUCTURE", "`registro.banco.internal/vectra/envoy` (`kind-registry:5000/vectra/envoy` en kind)", "`registro.banco.internal/vectra/envoy` (`kind-registry:5000/vectra/proxy` en kind)"),
    ("INFRASTRUCTURE", "sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0", "sha256:" + "1" * 64),
    ("INFRASTRUCTURE", "`vectra.io/criticality: high` va en", "`vectra.io/criticality: medium` va en"),
    ("INFRASTRUCTURE", "`externalTrafficPolicy: Local` y la etiqueta `app.kubernetes.io/name: api-gateway`", "`externalTrafficPolicy: Cluster` y la etiqueta `app.kubernetes.io/name: api-gateway`"),
    ("INFRASTRUCTURE", "`envoyHpa` de 2 a 6 réplicas", "`envoyHpa` de 3 a 6 réplicas"),
    ("INFRASTRUCTURE", "`envoyHpa` de 2 a 6 réplicas", "`envoyHpa` de 2 a 8 réplicas"),
    ("INFRASTRUCTURE", "objetivo de CPU del 70 %", "objetivo de CPU del 80 %"),
    ("INFRASTRUCTURE", "`envoyPDB` con `minAvailable: 1`", "`envoyPDB` con `minAvailable: 2`"),
    ("INFRASTRUCTURE", "| Envoy (data plane) | 250m / 256 MiB | 1 CPU / 512 MiB |", "| Envoy (data plane) | 300m / 256 MiB | 1 CPU / 512 MiB |"),
    ("INFRASTRUCTURE", "| Envoy (data plane) | 250m / 256 MiB | 1 CPU / 512 MiB |", "| Envoy (data plane) | 250m / 256 MiB | 2 CPU / 512 MiB |"),
    ("INFRASTRUCTURE", "`otel-collector.vectra-observability.svc:4317` (F61) con muestreo del 100 %", "`otel-collector.vectra-observability.svc:4318` (F61) con muestreo del 100 %"),
    ("INFRASTRUCTURE", "`otel-collector.vectra-observability.svc:4317` (F61) con muestreo del 100 %", "`otel-collector.vectra-observability.svc:4317` (F61) con muestreo del 50 %"),
    ("INFRASTRUCTURE", "spread por zona", "spread por nodo"),
    ("NFR_PATTERNS", "- Campos: `timestamp`, `route_name`,", "- Campos: `timestamp`, `route`,"),
    ("NFR_PATTERNS", "`failure_mode_deny: true` y `status_on_error: 503`", "`failure_mode_deny: true` y `status_on_error: 500`"),
    ("NFR_PATTERNS", "`failure_mode_deny: true` y `status_on_error: 503`", "`failure_mode_deny: false` y `status_on_error: 503`"),
    ("KEYCLOAK_VALUES", "maxSkew: 1", "maxSkew: 2"),
    ("KEYCLOAK_VALUES", "whenUnsatisfiable: DoNotSchedule", "whenUnsatisfiable: ScheduleAnyway"),
    ("INFRASTRUCTURE", "en JSON a stdout", "en JSON a stderr"),
    ("INFRASTRUCTURE", "en JSON a stdout", "en Text a stdout"),
    ("INFRASTRUCTURE", "tracing OpenTelemetry hacia", "tracing Zipkin hacia"),
    ("INFRASTRUCTURE", "objetivo de CPU del", "objetivo de memoria del"),
    ("INFRASTRUCTURE", "listener HTTPS (443)", "listener HTTP (443)"),
    ("INFRASTRUCTURE", "| 10m / 32 MiB | 50m / 64 MiB |", "| 20m / 32 MiB | 50m / 64 MiB |"),
    ("INFRASTRUCTURE", "| 10m / 32 MiB | 50m / 64 MiB |", "| 10m / 32 MiB | 100m / 64 MiB |"),
    ("INFRASTRUCTURE", "`shutdown-manager` (sidecar de cada pod de Envoy)", "`shutdown-agent` (sidecar de cada pod de Envoy)"),
    ("INFRASTRUCTURE", "fija TLS 1.2 como mínimo y 1.3 como máximo", "fija TLS 1.3 como mínimo y 1.3 como máximo"),
    ("INFRASTRUCTURE", "fija TLS 1.2 como mínimo y 1.3 como máximo", "fija TLS 1.2 como mínimo y 1.2 como máximo"),
    ("LOGICAL_COMPONENTS", "| Envoy (data plane) | `vectra-edge` | TLS, rutas, JWT, rate limit, cabeceras, access log | P-U2-01..03, 06, 07 | `vectra-high` |", "| Envoy (data plane) | `vectra-edge` | TLS, rutas, JWT, rate limit, cabeceras, access log | P-U2-01..03, 06, 07 | `vectra-medium` |"),
]


@pytest.mark.parametrize(("attribute", "old", "new"), DESIGN_ALTERATIONS, ids=[f"{i}-{a}" for i, (a, _, _) in enumerate(DESIGN_ALTERATIONS)])
def test_a_value_changed_in_the_design_but_not_in_the_oracle_is_caught(attribute, old, new, monkeypatch):
    import gateway_design

    text = getattr(gateway_design, attribute)
    assert old in text, f"el diseno ya no dice {old!r}: actualiza la alteracion"
    reference = {env: gc.flat(expected(env, f09=True)) for env in ENVS}
    monkeypatch.setattr(gateway_design, attribute, text.replace(old, new))
    changed = []
    for env in ENVS:
        altered = gc.flat(expected(env, f09=True))  # una excepcion del lector hace fallar la prueba: debe leer el valor alterado
        if altered != reference[env]:
            changed.append(env)
            assert altered != generated_docs(env, f09=True), env
    assert changed, f"el oraculo no lee {old!r} del diseno"


def test_the_design_texts_are_the_ones_the_oracle_reads():
    import gateway_design

    assert gateway_design.INFRASTRUCTURE is design_values.INFRASTRUCTURE
    assert gateway_design.DOMAIN_ENTITIES is design_values.DOMAIN_ENTITIES


# --- Paso 8 (U02-T10): lo que no es una sola regla ---------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_auth_counters_live_only_in_the_route_policy(env, docs_by_env):
    docs = docs_by_env[env]
    edge = gc.find(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    assert not [r for r in edge if any("sourceCIDR" in s for s in r.get("clientSelectors", []))]
    others = [b["metadata"]["name"] for b in gc.of_kind(docs, "BackendTrafficPolicy") if "rateLimit" in b["spec"]]
    assert sorted(others) == sorted(["edge-rate-limits", ge.AUTH_RULE])
    assert "retry" not in gc.find(docs, "BackendTrafficPolicy", ge.AUTH_RULE)["spec"]  # X1


@pytest.mark.parametrize("env", ENVS)
def test_the_client_policy_takes_the_remote_address(env, docs_by_env):
    spec = gc.find(docs_by_env[env], "ClientTrafficPolicy", "edge-client")["spec"]
    assert "clientIPDetection" not in spec  # v1.9.3 resta 1 a numTrustedHops y configura la extension xff aun con 0
    assert gd.trusted_hops() == 0


@pytest.mark.parametrize("env", ENVS)
def test_the_issuer_is_the_one_of_the_environment_and_staging_and_prod_never_use_the_one_of_kind(env, docs_by_env):
    issuer = gc.find(docs_by_env[env], "Certificate", "api-gateway")["spec"]["issuerRef"]["name"]
    assert issuer == gd.issuers()[env]
    assert (issuer == "vectra-internal-ca") == (env == "kind")


@pytest.mark.parametrize("env", ENVS)
def test_the_envoy_image_is_the_mirror_of_the_environment_with_the_digest_of_the_design(env, docs_by_env):
    repos, digest, _, _ = gd.envoy_images()
    image = _container(docs_by_env[env])["image"]
    assert image == f"{repos[env]}@{digest}"
    values = route_gen.load_values(env)["envoy_image"]
    assert (values["repository"], values["digest"]) == (repos[env], digest)


@pytest.mark.parametrize("env", ENVS)
def test_the_access_log_has_exactly_the_fields_of_the_design(env, docs_by_env):
    (setting,) = _telemetry(docs_by_env[env])["accessLog"]["settings"]
    assert sorted(setting["format"]["json"]) == sorted(gd.access_log_fields())
    assert setting["format"]["json"]["correlation_id"] == "%TRACE_ID%"
    assert all("REQ(" not in v or v == "%REQ(:METHOD)%" for v in setting["format"]["json"].values())


@pytest.mark.parametrize("remove", ["digest", "repository", "block"])
def test_the_generator_fails_without_the_digest_of_the_envoy_image(remove):
    values = copy.deepcopy(route_gen.load_values("prod"))
    if remove == "block":
        values.pop("envoy_image")
    else:
        values["envoy_image"].pop(remove)
    with pytest.raises(route_gen.RoutesError):
        route_gen.generate(route_gen.load_routes(), values)


def test_the_generator_rejects_a_digest_that_is_not_a_sha256():
    values = copy.deepcopy(route_gen.load_values("prod"))
    values["envoy_image"]["digest"] = "latest"
    with pytest.raises(route_gen.RoutesError):
        route_gen.generate(route_gen.load_routes(), values)


def test_the_generator_fails_without_an_issuer():
    values = copy.deepcopy(route_gen.load_values("prod"))
    values.pop("issuer")
    with pytest.raises(route_gen.RoutesError):
        route_gen.generate(route_gen.load_routes(), values)


@pytest.mark.parametrize("env", ENVS)
def test_the_gateway_carries_the_criticality_label_the_deployment_gets(env, docs_by_env):
    assert gc.find(docs_by_env[env], "Gateway", "api-gateway")["spec"]["infrastructure"]["labels"] == gd.infrastructure_labels()
