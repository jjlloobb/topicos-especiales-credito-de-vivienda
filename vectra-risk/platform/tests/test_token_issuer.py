"""El emisor (`iss`) de los tokens, entre unidades (U02-T21): lo que valida cada servicio es lo que Keycloak firma.

Mundo cerrado, sin clúster y sin Docker. Por entorno se leen (no se copian): el `KC_HOSTNAME` y los Services y el `Certificate` del
render de Keycloak, los proveedores JWT del gateway, los flujos de `flows.yaml` y los workloads que Argo CD rendiría (charts de
`components.yaml` con `chart_renders`, más `identity-edge/jobs/rendered/`). Los workloads se descubren: ninguno está listado aquí.

Lo medido con un Keycloak real (`identity-edge/docs/emisor-de-tokens.md`, R2): con `KC_HOSTNAME` como URL completa todo token sale con
`iss` = `<KC_HOSTNAME>/realms/vectra`, pidan por el host que pidan. Por eso todo `VECTRA_OIDC_ISSUER` debe ser ese emisor. El JWKS y la URL
de token siguen por un Service de Keycloak que F50/F94 permiten (el gateway no es alcanzable desde `vectra-app`).

U00-T04: la `aud` de la aserción `private_key_jwt` identifica al servidor de autorización, no la URL a la que se envía (Keycloak
responde 400 `Invalid token audience` a la URL interna). Todo workload que pide token rinde `VECTRA_ASSERTION_AUDIENCE`, y vale
exactamente el emisor del entorno. Y una variable vigilada que llega sin `value` literal (`valueFrom`) es un fallo: no se puede leer.
"""

import importlib.util
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml
from integration import ROOT, chart_renders, helm, pod_labels, pod_spec

PLATFORM = ROOT / "platform"
ENVS = ("kind", "staging", "prod")
REALM = "/realms/vectra"
ISSUER_VAR, JWKS_VAR = "VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL"
AUDIENCE_VAR = "VECTRA_ASSERTION_AUDIENCE"
TOKEN_VARS = ("VECTRA_TOKEN_URL", "GOVERNANCE_JOB_TOKEN_URL")
URL_VARS = {
    JWKS_VAR: "/protocol/openid-connect/certs",
    "VECTRA_TOKEN_URL": "/protocol/openid-connect/token",
    "GOVERNANCE_JOB_TOKEN_URL": "/protocol/openid-connect/token",
}
#: Quien pide el token de `GOVERNANCE_JOB_TOKEN_URL` no es el pod que lo lleva, sino el Job que `governance-service` lanza.
URL_ORIGIN = {"GOVERNANCE_JOB_TOKEN_URL": "model-validation-job"}
WATCHED = (ISSUER_VAR, JWKS_VAR, AUDIENCE_VAR, *TOKEN_VARS)
#: Marca de una variable vigilada que llega por `valueFrom`: no tiene `value` literal que comparar.
NO_LITERAL = "<sin value literal>"
#: Los workloads que CA-5 exige ver en cada entorno: sin ellos la prueba pasaria en vacio.
VALIDATORS = {
    "decision-registry-service",
    "governance-service",
    "scoring-service",
    "explainability-service",
    "bias-monitoring-service",
}
REQUESTERS = {
    "governance-service",
    "scoring-service",
    "explainability-service",
    "bias-monitoring-service",
    "bias-monitoring-job",
    "product-metrics",
    "realm-drift",
    "signing-key-age",
}

World = dict[str, Any]


def _network() -> Any:
    spec = importlib.util.spec_from_file_location("network_generate", PLATFORM / "network/generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _docs(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _env_of(spec: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for container in [*spec.get("initContainers", []), *spec.get("containers", [])]:
        values.update(
            {e["name"]: e.get("value", NO_LITERAL) for e in container.get("env", []) if e["name"] in WATCHED}
        )
    return values


def _pods(documents: list[dict[str, Any]], default_ns: str) -> list[dict[str, Any]]:
    pods = []
    for document in documents:
        spec = pod_spec(document) if document.get("kind") else None
        if spec is None:
            continue
        found = _env_of(spec)
        if found:
            pods.append(
                {
                    "name": document["metadata"]["name"],
                    "ns": document["metadata"].get("namespace", default_ns),
                    "sa": spec.get("serviceAccountName", "default"),
                    "env": found,
                }
            )
    return pods


@cache
def build(env: str) -> World:
    keycloak = _docs(ROOT / f"identity-edge/keycloak/rendered/{env}/keycloak.yaml")
    sts = next(d for d in keycloak if d["kind"] == "StatefulSet")
    hostname = next(
        e["value"]
        for e in sts["spec"]["template"]["spec"]["containers"][0]["env"]
        if e["name"] == "KC_HOSTNAME"
    )
    certificate = next(
        d for d in keycloak if d["kind"] == "Certificate" and d["metadata"]["name"] == "keycloak-tls"
    )
    policies = [
        d
        for d in _docs(ROOT / f"identity-edge/gateway/generated/{env}/securitypolicies.yaml")
        if d["kind"] == "SecurityPolicy"
    ]
    gateway = sorted({p["issuer"] for d in policies for p in d["spec"].get("jwt", {}).get("providers", [])})
    network = _network()
    flows = network.load()[0]
    pods = []
    components = yaml.safe_load((ROOT / "vectra-risk-gitops/components.yaml").read_text(encoding="utf-8"))[
        "components"
    ]
    for component in components:
        path = component.get("path")
        chart = ROOT / path if path else None
        if not chart or not (chart / "Chart.yaml").is_file() or env not in component.get("envs", ENVS):
            continue
        if not any(
            f.is_file() and any(v in f.read_text(encoding="utf-8") for v in WATCHED)
            for f in chart.rglob("*")
            if f.suffix in {".yaml", ".tpl"}
        ):
            continue
        for name, rendered_env, namespace, values in chart_renders(path, env, component["namespace"]):
            if name == component["name"] and rendered_env == env:
                pods += _pods(helm(name, chart, namespace, values), namespace)
    pods += _pods(_docs(ROOT / f"identity-edge/jobs/rendered/{env}/identity-jobs.yaml"), "vectra-identity")
    return {
        "env": env,
        "issuer": hostname.rstrip("/") + REALM,
        "gateway_issuers": gateway,
        "services": [
            {
                "name": d["metadata"]["name"],
                "ns": d["metadata"]["namespace"],
                "selector": d["spec"]["selector"],
                "ports": [p["port"] for p in d["spec"]["ports"]],
            }
            for d in keycloak
            if d["kind"] == "Service"
        ],
        "keycloak_labels": pod_labels(sts),
        "sans": list(certificate["spec"]["dnsNames"]),
        "workloads": flows["workloads"],
        "flows": [f for f in flows["flows"] if network.active(f, env, flows["env_disabled"][env])],
        "pods": pods,
    }


def _origins(world: World, ns: str, sa: str) -> set[str]:
    return {
        name
        for name, w in world["workloads"].items()
        if w.get("ns") == ns and w.get("sa") == sa and world["env"] in w.get("envs", ENVS)
    }


def _reaches_keycloak(world: World, origins: set[str], port: int) -> bool:
    for flow in world["flows"]:
        if (
            "keycloak" in flow["to"]
            and origins & set(flow["from"])
            and port in flow.get("ports", [flow.get("port")])
        ):
            return True
    return False


def problems(world: World, only: str | None = None) -> list[str]:
    """Cada defecto nombra el entorno y el workload."""
    env, found = world["env"], []
    if len(world["gateway_issuers"]) != 1 or world["gateway_issuers"][0] != world["issuer"]:
        found.append(
            f"{env}/gateway: los proveedores JWT validan {world['gateway_issuers']}, Keycloak firma {world['issuer']}"
        )
    for pod in world["pods"]:
        if only and pod["name"] != only:
            continue
        who, values = f"{env}/{pod['name']}", pod["env"]
        found += [
            f"{who}: {var} llega sin `value` literal (valueFrom): no se puede comprobar"
            for var in values
            if values[var] == NO_LITERAL
        ]
        values = {var: value for var, value in values.items() if value != NO_LITERAL}
        if ISSUER_VAR in values and values[ISSUER_VAR] != world["issuer"]:
            found.append(f"{who}: {ISSUER_VAR} = {values[ISSUER_VAR]}, y Keycloak firma {world['issuer']}")
        if ISSUER_VAR in values and JWKS_VAR not in values:
            found.append(f"{who}: tiene {ISSUER_VAR} y no {JWKS_VAR}")
        for var in (v for v in URL_VARS if v in values):
            found += _url_problems(world, pod, var, urlsplit(values[var]), who)
        found += _audience_problems(world, values, who)
    return found


def _audience_problems(world: World, values: dict[str, str], who: str) -> list[str]:
    found = []
    asks = any(v in values for v in TOKEN_VARS)
    if asks and AUDIENCE_VAR not in values:
        found.append(
            f"{who}: pide token (VECTRA_TOKEN_URL) y no rinde {AUDIENCE_VAR}: Keycloak rechazaria la aserción"
        )
    if AUDIENCE_VAR in values and not asks:
        found.append(f"{who}: rinde {AUDIENCE_VAR} sin URL de token")
    if AUDIENCE_VAR in values and values[AUDIENCE_VAR] != world["issuer"]:
        found.append(
            f"{who}: {AUDIENCE_VAR} = {values[AUDIENCE_VAR]}, y la aud que Keycloak acepta (su emisor) es {world['issuer']}"
        )
    return found


def _url_problems(world: World, pod: dict[str, Any], var: str, url: Any, who: str) -> list[str]:
    found = []
    base = urlsplit(world["issuer"]).path + URL_VARS[var]
    if url.scheme != "https":
        found.append(f"{who}: {var} no es https ({url.scheme})")
    if url.path != base:
        found.append(f"{who}: la ruta de {var} es {url.path}, la del realm es {base}")
    port = url.port or 443
    services = [
        s
        for s in world["services"]
        if url.hostname in {f"{s['name']}.{s['ns']}.svc", f"{s['name']}.{s['ns']}.svc.cluster.local"}
    ]
    if not services:
        found.append(f"{who}: el host de {var} ({url.hostname}) no es un Service de Keycloak")
    elif not any(
        port in s["ports"] and s["selector"].items() <= world["keycloak_labels"].items() for s in services
    ):
        found.append(
            f"{who}: ningun Service {url.hostname} abre el puerto {port} sobre los pods de Keycloak ({var})"
        )
    if url.hostname not in world["sans"]:
        found.append(f"{who}: el host de {var} ({url.hostname}) no es SAN de keycloak-tls")
    origin_name = URL_ORIGIN.get(var)
    origins = {origin_name} if origin_name else _origins(world, pod["ns"], pod["sa"])
    if not origins:
        found.append(f"{who}: su ServiceAccount {pod['ns']}/{pod['sa']} no es un workload de flows.yaml")
    elif not _reaches_keycloak(world, origins, port):
        found.append(
            f"{who}: {sorted(origins)} no es origen de un flujo habilitado hacia keycloak por el puerto {port} ({var})"
        )
    return found


CASES = [(env, pod["name"]) for env in ENVS for pod in build(env)["pods"]]
IDS = [f"{env}-{name}" for env, name in CASES]


@pytest.mark.parametrize("env", ENVS)
def test_the_workloads_are_discovered(env: str) -> None:
    world = build(env)
    validators = {p["name"] for p in world["pods"] if ISSUER_VAR in p["env"]}
    requesters = {p["name"] for p in world["pods"] if any(v in p["env"] for v in TOKEN_VARS)}
    audience = {p["name"] for p in world["pods"] if AUDIENCE_VAR in p["env"]}
    assert VALIDATORS <= validators, f"{env}: faltan validadores {sorted(VALIDATORS - validators)}"
    assert REQUESTERS <= requesters, (
        f"{env}: faltan workloads que piden token {sorted(REQUESTERS - requesters)}"
    )
    assert REQUESTERS <= audience, (
        f"{env}: faltan workloads sin {AUDIENCE_VAR} {sorted(REQUESTERS - audience)}"
    )


@pytest.mark.parametrize("env", ENVS)
def test_the_gateway_and_keycloak_share_the_issuer(env: str) -> None:
    world = build(env)
    assert world["issuer"].endswith("/auth" + REALM)
    assert world["gateway_issuers"] == [world["issuer"]]


@pytest.mark.parametrize(("env", "name"), CASES, ids=IDS)
def test_the_workload_trusts_what_keycloak_signs(env: str, name: str) -> None:
    assert problems(build(env), name) == []


def _mutated(env: str, change: Any) -> list[str]:
    world = deepcopy(build(env))
    change(world)
    return problems(world)


def _pod(world: World, name: str) -> dict[str, Any]:
    return next(p for p in world["pods"] if p["name"] == name)


def _expect(found: list[str], env: str, name: str, text: str) -> None:
    assert any(m.startswith(f"{env}/{name}:") and text in m for m in found), found


@pytest.mark.parametrize("env", ENVS)
def test_mutation_a_issuer_with_keycloak_admin(env: str) -> None:
    def change(world: World) -> None:
        _pod(world, "scoring-service")["env"][ISSUER_VAR] = (
            "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth" + REALM
        )

    _expect(_mutated(env, change), env, "scoring-service", ISSUER_VAR)


def test_mutation_b_issuer_of_staging_in_kind() -> None:
    other = build("staging")["issuer"]
    assert other != build("kind")["issuer"]
    _expect(
        _mutated("kind", lambda w: _pod(w, "governance-service")["env"].update({ISSUER_VAR: other})),
        "kind",
        "governance-service",
        ISSUER_VAR,
    )


@pytest.mark.parametrize("env", ENVS)
@pytest.mark.parametrize("bad", ["", "/realms/otro"])
def test_mutation_c_issuer_without_the_vectra_realm(env: str, bad: str) -> None:
    def change(world: World) -> None:
        _pod(world, "decision-registry-service")["env"][ISSUER_VAR] = (
            world["issuer"].removesuffix(REALM) + bad
        )

    _expect(_mutated(env, change), env, "decision-registry-service", ISSUER_VAR)


@pytest.mark.parametrize("env", ENVS)
def test_mutation_d_jwks_by_the_public_hostname(env: str) -> None:
    def change(world: World) -> None:
        host = urlsplit(world["issuer"]).hostname
        _pod(world, "explainability-service")["env"][JWKS_VAR] = (
            f"https://{host}{urlsplit(world['issuer']).path}{URL_VARS[JWKS_VAR]}"
        )

    _expect(_mutated(env, change), env, "explainability-service", "no es un Service de Keycloak")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_e_token_url_on_port_443(env: str) -> None:
    def change(world: World) -> None:
        values = _pod(world, "bias-monitoring-job")["env"]
        values["VECTRA_TOKEN_URL"] = values["VECTRA_TOKEN_URL"].replace(":8443", "")

    _expect(_mutated(env, change), env, "bias-monitoring-job", "puerto 443")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_f_requester_without_a_flow_to_keycloak(env: str) -> None:
    def change(world: World) -> None:
        for flow in world["flows"]:
            if "keycloak" in flow["to"]:
                flow["from"] = [w for w in flow["from"] if w != "product-metrics"]

    _expect(_mutated(env, change), env, "product-metrics", "no es origen de un flujo")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_f_job_of_governance_without_a_flow(env: str) -> None:
    def change(world: World) -> None:
        for flow in world["flows"]:
            flow["from"] = [w for w in flow["from"] if w != "model-validation-job"]

    _expect(_mutated(env, change), env, "governance-service", "model-validation-job")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_g_host_that_is_not_a_san(env: str) -> None:
    def change(world: World) -> None:
        world["sans"] = [s for s in world["sans"] if not s.startswith("keycloak-admin")]

    found = _mutated(env, change)
    _expect(found, env, "decision-registry-service", "no es SAN de keycloak-tls")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_h_gateway_issuer_differs_from_keycloak(env: str) -> None:
    found = _mutated(env, lambda w: w.update({"gateway_issuers": [w["issuer"] + "x"]}))
    assert any(m.startswith(f"{env}/gateway:") for m in found), found


# --- U00-T04: la audiencia de la aserción ---


@pytest.mark.parametrize("env", ENVS)
def test_mutation_i_audience_is_the_internal_token_url(env: str) -> None:
    def change(world: World) -> None:
        values = _pod(world, "scoring-service")["env"]
        values[AUDIENCE_VAR] = values["VECTRA_TOKEN_URL"]

    _expect(_mutated(env, change), env, "scoring-service", AUDIENCE_VAR)


@pytest.mark.parametrize("env", ENVS)
def test_mutation_j_audience_is_the_internal_issuer(env: str) -> None:
    def change(world: World) -> None:
        internal = "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth" + REALM
        _pod(world, "product-metrics")["env"][AUDIENCE_VAR] = internal

    _expect(_mutated(env, change), env, "product-metrics", AUDIENCE_VAR)


def test_mutation_k_audience_of_staging_in_kind() -> None:
    other = build("staging")["issuer"]
    assert other != build("kind")["issuer"]
    _expect(
        _mutated("kind", lambda w: _pod(w, "governance-service")["env"].update({AUDIENCE_VAR: other})),
        "kind",
        "governance-service",
        AUDIENCE_VAR,
    )


@pytest.mark.parametrize("env", ENVS)
def test_mutation_l_token_url_without_audience(env: str) -> None:
    for name in sorted(REQUESTERS):
        found = _mutated(env, lambda w, n=name: _pod(w, n)["env"].pop(AUDIENCE_VAR, None))
        _expect(found, env, name, "no rinde " + AUDIENCE_VAR)


@pytest.mark.parametrize("env", ENVS)
def test_mutation_m_audience_is_the_public_token_url(env: str) -> None:
    def change(world: World) -> None:
        _pod(world, "realm-drift")["env"][AUDIENCE_VAR] = world["issuer"] + URL_VARS["VECTRA_TOKEN_URL"]

    _expect(_mutated(env, change), env, "realm-drift", AUDIENCE_VAR)


@pytest.mark.parametrize("env", ENVS)
def test_mutation_n_audience_of_another_realm(env: str) -> None:
    def change(world: World) -> None:
        _pod(world, "bias-monitoring-job")["env"][AUDIENCE_VAR] = (
            world["issuer"].removesuffix(REALM) + "/realms/otro"
        )

    _expect(_mutated(env, change), env, "bias-monitoring-job", AUDIENCE_VAR)


@pytest.mark.parametrize("env", ENVS)
def test_mutation_o_audience_without_a_token_url(env: str) -> None:
    def change(world: World) -> None:
        values = _pod(world, "decision-registry-service")["env"]
        values[AUDIENCE_VAR] = world["issuer"]

    _expect(_mutated(env, change), env, "decision-registry-service", "sin URL de token")


@pytest.mark.parametrize("env", ENVS)
def test_mutation_p_a_watched_variable_without_a_literal_value(env: str) -> None:
    def change(world: World) -> None:
        _pod(world, "signing-key-age")["env"][AUDIENCE_VAR] = NO_LITERAL

    _expect(_mutated(env, change), env, "signing-key-age", "sin `value` literal")
