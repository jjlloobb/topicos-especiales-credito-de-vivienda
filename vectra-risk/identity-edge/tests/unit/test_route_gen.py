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


def _auth_counters(docs: gc.Docs) -> list[dict[str, Any]]:
    rules = gc.find(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    return [r for r in rules if any("sourceCIDR" in s for s in r.get("clientSelectors", []))]


def counters_violations(docs: gc.Docs) -> list[str]:
    bad = []
    counters = _auth_counters(docs)
    if len(counters) != 2:
        return [f"debia haber 2 contadores y hay {len(counters)}"]
    login = "/auth/realms/vectra/protocol/openid-connect/auth"
    token_path = "/auth/realms/vectra/protocol/openid-connect/token"
    same = ["/auth/realms/vectra/login-actions/authenticate", "/auth/realms/vectra/login-actions", login + "?client_id=x"]
    for counter in counters:
        (selector,) = counter["clientSelectors"]
        number = gd.rate_limit_numbers()["auth"]
        if (counter["limit"], counter.get("shared"), selector["sourceCIDR"]) != ({"requests": number, "unit": "Minute"}, True, {"type": "Distinct", "value": "0.0.0.0/0"}):
            bad.append(f"contador distinto: {counter}")
        regex = selector["path"]["value"]
        matches_login = all(re.fullmatch(regex, p) for p in [login, *same])
        matches_token = bool(re.fullmatch(regex, token_path)) or bool(re.fullmatch(regex, token_path + "?grant_type=x"))
        if matches_login == matches_token:
            bad.append(f"el contador no separa login y token: {regex}")
    others = ["/auth/realms/vectra/protocol/openid-connect/certs", "/auth/resources/x.css", "/auth/realms/vectra/account"]
    for counter in counters:
        regex = counter["clientSelectors"][0]["path"]["value"]
        if any(re.fullmatch(regex, p) for p in others):
            bad.append(f"el contador cuenta otros caminos: {regex}")
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
def test_auth_has_two_counters_of_600_per_minute_and_retry_after_60(env, docs_by_env):
    assert counters_violations(docs_by_env[env]) == []
    assert retry_after_violations(docs_by_env[env]) == []


def _set_counter(docs: gc.Docs, index: int, key: str, value: Any) -> None:
    counters = _auth_counters(docs)
    counters[index][key] = value


def _drop_counter(docs: gc.Docs) -> None:
    rules = gc.find(docs, "BackendTrafficPolicy", "edge-rate-limits")["spec"]["rateLimit"]["global"]["rules"]
    rules.remove(_auth_counters(docs)[1])


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: _set_counter(d, 0, "limit", {"requests": 10, "unit": "Minute"}),
        lambda d: _set_counter(d, 1, "shared", False),
        lambda d: _auth_counters(d)[0]["clientSelectors"][0].update(path={"type": "RegularExpression", "value": "^/auth/.*"}),
        _drop_counter,
    ],
    ids=["limit-10", "not-shared", "counts-everything", "one-counter"],
)
def test_counters_check_fails_on_altered_counters(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    alter(docs)
    assert counters_violations(docs)


def test_retry_after_check_fails_on_a_wrong_value():
    docs = copy.deepcopy(gc.load_env("prod"))
    entry = [e for e in gc.find(docs, "BackendTrafficPolicy", "auth-read")["spec"]["responseOverride"] if e["match"]["statusCodes"][0]["value"] == 429][0]
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
    rules = gc.find(docs, "HTTPRoute", "promotion")["spec"]["rules"]
    rules[0]["filters"] = [f for f in rules[0]["filters"] if f["type"] != "URLRewrite"]


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
    if ctp["earlyRequestHeaders"] != {"removeOnMatch": [{"type": "Prefix", "value": "x-vectra-"}]}:
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
        if grant["spec"]["from"] != [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "namespace": "vectra-edge"}]:
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


@pytest.mark.parametrize(
    "alter",
    [
        lambda d: gc.find(d, "ReferenceGrant", "edge-routes")["spec"]["to"].append({"group": "", "kind": "Service", "name": "other"}),
        lambda d: gc.find(d, "ReferenceGrant", "edge-routes")["spec"]["to"].pop(),
        lambda d: gc.find(d, "ReferenceGrant", "edge-routes")["spec"]["from"][0].update(kind="SecurityPolicy"),
        lambda d: d.remove(gc.find(d, "ReferenceGrant", "edge-routes")),
    ],
    ids=["extra-service", "missing-service", "other-kind", "no-grant"],
)
def test_grant_check_fails_on_altered_grants(alter):
    docs = copy.deepcopy(gc.load_env("prod"))
    # `find` exige un solo grant: se deja solo el de vectra-app.
    docs[:] = [d for d in docs if not (d["kind"] == "ReferenceGrant" and d["metadata"]["namespace"] != "vectra-app")]
    alter(docs)
    assert grant_violations(docs)


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
    assert gc.route(docs, "POST", "/federate").status == 404
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
    for rule in ("spa", "auth-read", "auth-write"):
        assert "requestBuffer" not in by_rule[rule]
    assert by_rule["console-read"]["timeout"]["http"]["requestTimeout"] == t["/api/console/**"]
    assert by_rule["auth-write"]["timeout"]["http"]["requestTimeout"] == t["/auth/**"]
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
    if retried != {"console-read", "promotion-models", "auth-read", "grafana-read"}:
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
    ("client-policy", "one-hop-two", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["clientIPDetection"]["xForwardedFor"].update(numTrustedHops=2)),
    ("client-policy", "no-early-removal", _no_early_removal),
    ("client-policy", "server-kept", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["headers"]["lateResponseHeaders"].pop("remove")),
    ("client-policy", "slashes-kept", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["path"].update(escapedSlashesAction="KeepUnchanged")),
    ("client-policy", "slashes-not-merged", lambda d: gc.find(d, "ClientTrafficPolicy", "edge-client")["spec"]["path"].update(disableMergeSlashes=True)),
    ("cookie-affinity", "ttl", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"].update(ttl="60s")),
    ("cookie-affinity", "samesite", lambda d: gc.find(d, "BackendTrafficPolicy", "spa")["spec"]["loadBalancer"]["consistentHash"]["cookie"]["attributes"].update(SameSite="None")),
    ("outlier", "ejection-time", lambda d: gc.find(d, "BackendTrafficPolicy", "intake-submit")["spec"]["healthCheck"]["passive"].update(baseEjectionTime="5s")),
    ("outlier", "max-percent", lambda d: gc.find(d, "BackendTrafficPolicy", "auth-read")["spec"]["healthCheck"]["passive"].update(maxEjectionPercent=100)),
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
    ("authenticated-has-security-policy", "new-authenticated-rule", lambda d: _rule(d, "intake", "intake-submit")["matches"].append({"path": {"type": "Exact", "value": "/api/other"}, "method": "POST"}) or gc.find(d, "HTTPRoute", "intake")["spec"]["rules"].append({"name": "other", "matches": [{"path": {"type": "Exact", "value": "/api/other"}}], "backendRefs": [{"group": "", "kind": "Service", "name": "other", "namespace": "vectra-app", "port": 8080}]})),
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
]


def test_every_rule_has_a_failing_case():
    assert {rule for rule, _, _ in MUTATIONS} == gc.policy_rules()


@pytest.mark.parametrize("env", ENVS)
def test_conftest_passes_on_the_generated_manifests(env, docs_by_env):
    code, output = gc.conftest(docs_by_env[env])
    assert code == 0, output


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
    crd_schemas.convert(gc.CHART, out)
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
