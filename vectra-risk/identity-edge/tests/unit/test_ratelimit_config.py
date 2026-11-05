"""Descriptores del rate limit (U02-T11, CA-1): INF-U2-03, P-U2-06.

Envoy Gateway v1.9.3 arma los descriptores de `envoy-ratelimit` por xDS desde las `BackendTrafficPolicy` (`edge-rate-limits` y
`auth-rate-limits`); `route-gen` no genera configuracion del servicio. Esta prueba traduce `generated/<env>/` con `egctl x translate
--to ir` (sin cluster, con los mismos documentos de apoyo que `xds_gateway.py`) y compara las reglas `global` del IR con los limites
de `routes.yaml`, que se leen aqui por su cuenta (no se importa `route_gen`).
"""

import copy
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import xds_gateway as xds
import yaml

EDGE = xds.EDGE
ROUTES = EDGE / "gateway" / "routes.yaml"
VALUES = EDGE / "gateway" / "values"
ENVS = xds.ENVS
EDGE_POLICY = "edge-rate-limits"
AUTH_POLICY = "auth-rate-limits"
# egctl traduce `PathPrefix` a esta expresion regular de Envoy; `RegularExpression` queda igual.
PREFIX_SUFFIX = r"(/.*|\?.*|#.*|;.*|$)"

Rule = tuple[Any, ...]


def read_routes() -> dict[str, Any]:
    return yaml.safe_load(ROUTES.read_text(encoding="utf-8"))


def read_values(env: str) -> dict[str, Any]:
    return yaml.safe_load((VALUES / f"{env}.yaml").read_text(encoding="utf-8"))


def selector_path(path: dict[str, str]) -> str:
    if path["type"] == "PathPrefix":
        return f"^{path['value']}{PREFIX_SUFFIX}"
    assert path["type"] == "RegularExpression", f"tipo de path sin traduccion conocida: {path['type']}"
    return path["value"]


def expected_rule(item: dict[str, Any], values: dict[str, Any], cidr: str | None = None) -> Rule:
    header = item.get("header")
    if header:
        value = header.get("value") or (values.get(header["value_from"]) if header.get("value_from") else None)
        headers: tuple[Any, ...] = ((header["name"], value or "distinct"),)
    else:
        headers = ()
    path = selector_path(item["path"]) if item.get("path") else None
    return (headers, path, cidr, item["requests"], item["unit"], True)


def enabled(item: dict[str, Any], values: dict[str, Any]) -> bool:
    if item.get("requires") == "f09" and not values.get("f09", {}).get("enabled"):
        return False
    key = item.get("header", {}).get("value_from")
    return not key or bool(values.get(key))


def expected(routes: dict[str, Any], env: str) -> tuple[Counter[Rule], dict[str, Counter[Rule]]]:
    """Las reglas del Gateway (`edge-rate-limits`) y las de cada ruta (`auth-rate-limits`: `route: auth`), desde `routes.yaml`."""
    values = read_values(env)
    gateway: Counter[Rule] = Counter()
    by_route: dict[str, Counter[Rule]] = {}
    gateway[((), None, None, routes["global_limit"]["requests"], routes["global_limit"]["unit"], True)] += 1
    for item in routes["rate_limits"]:
        if not enabled(item, values):
            continue
        target = by_route.setdefault(item["route"], Counter()) if item.get("route") else gateway
        if item.get("source_ip"):
            for cidr in item["source_ip"]:
                target[expected_rule(item, values, cidr)] += 1
        else:
            target[expected_rule(item, values)] += 1
    return gateway, by_route


def observed_rule(rule: dict[str, Any]) -> Rule:
    headers = tuple((h["name"], "distinct" if h.get("distinct") else h["exact"]) for h in rule.get("headerMatches", []))
    path = rule.get("pathMatch", {}).get("safeRegex")
    cidr = rule.get("cidrMatch", {}).get("cidr")
    limit = rule["limit"]
    return (headers, path, cidr, limit["requests"], limit["unit"], rule["shared"])


def translate_ir(directory: Path) -> dict[str, Any]:
    docs = xds.load_dir(directory)
    text = yaml.safe_dump_all([*(d for d in docs if d["kind"] not in xds.OTHER_OPERATORS), *xds.stub_documents(docs)], sort_keys=False)
    run = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
        [str(xds.EGCTL), "x", "translate", "--from", "gateway-api", "--to", "ir", "--add-missing-resources", "-f", "-", "-o", "yaml"],
        input=text, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    return yaml.safe_load(run.stdout)


def ir_routes(ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """nombre de la ruta de Gateway API (`httproute/<ns>/<ruta>`) -> reglas `global` de cada ruta de Envoy que la expresa."""
    found: dict[str, list[dict[str, Any]]] = {}
    for gateway in ir["xdsIR"].values():
        for listener in gateway["http"]:
            for route in listener["routes"]:
                name = "/".join(route["name"].split("/")[:3])
                rules = ((route.get("traffic") or {}).get("rateLimit") or {}).get("global", {}).get("rules", [])
                found.setdefault(name, []).append(rules)  # type: ignore[arg-type]
    return found  # type: ignore[return-value]


def problems(ir: dict[str, Any], routes: dict[str, Any], env: str) -> list[str]:
    """Diferencias entre el IR y `routes.yaml`. Vacio si coinciden."""
    gateway, by_route = expected(routes, env)
    found: list[str] = []
    seen_routes = ir_routes(ir)
    if not seen_routes:
        return ["el IR no trae rutas"]
    for name, variants in sorted(seen_routes.items()):
        owner = name.split("/")[-1]
        for rules in variants:
            edge = Counter(observed_rule(r) for r in rules if f"/{EDGE_POLICY}/" in r["name"])
            auth = Counter(observed_rule(r) for r in rules if f"/{AUTH_POLICY}/" in r["name"])
            other = [r["name"] for r in rules if f"/{EDGE_POLICY}/" not in r["name"] and f"/{AUTH_POLICY}/" not in r["name"]]
            if edge != gateway:
                found.append(f"{name}: edge-rate-limits difiere: {sorted(map(str, edge - gateway))} sobran, {sorted(map(str, gateway - edge))} faltan")
            if auth != by_route.get(owner, Counter()):
                found.append(f"{name}: auth-rate-limits difiere")
            if other:
                found.append(f"{name}: reglas de otra politica: {other}")
    for owner in by_route:
        if not any(n.endswith(f"/{owner}") for n in seen_routes):
            found.append(f"la ruta {owner} no esta en el IR")
    return found


@pytest.fixture(scope="module", params=ENVS)
def case(request: pytest.FixtureRequest) -> tuple[str, dict[str, Any]]:
    return request.param, translate_ir(xds.GENERATED / request.param)


def test_the_ir_descriptors_match_routes_yaml(case: tuple[str, dict[str, Any]]) -> None:
    env, ir = case
    assert problems(ir, read_routes(), env) == []


def test_the_oracle_reads_the_expected_counters(case: tuple[str, dict[str, Any]]) -> None:
    """El oraculo no esta vacio: el Gateway lleva el contador global y los de consola, intake y promotion; `auth` los dos por IP."""
    env, _ = case
    gateway, by_route = expected(read_routes(), env)
    assert ((), None, None, 200, "Second", True) in gateway
    assert sum(1 for rule in gateway if rule[0] and rule[0][0][0] == "x-vectra-sub") == 2
    assert sum(1 for rule in gateway if rule[0] and rule[0][0][0] == "x-vectra-azp") == (2 if env != "prod" else 1)
    assert {rule[2] for rule in by_route["auth"]} == {"0.0.0.0/0", "::/0"}
    assert len(by_route["auth"]) == 4


def altered(routes: dict[str, Any], name: str, **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(routes)
    (item,) = [i for i in out["rate_limits"] if i["name"] == name]
    item.update(changes)
    return out


@pytest.mark.parametrize(
    ("name", "changes"),
    [
        ("console", {"requests": 21}),
        ("promotion", {"unit": "Minute"}),
        ("intake-channel", {"header": {"name": "x-vectra-azp", "value": "otro"}}),
        ("console", {"header": {"name": "x-vectra-other"}}),
        ("auth-login", {"source_ip": ["0.0.0.0/0"]}),
        ("auth-token", {"requests": 599}),
        ("auth-login", {"path": {"type": "RegularExpression", "value": "^/auth/otro$"}}),
    ],
    ids=["console-requests", "promotion-unit", "intake-azp", "console-header", "auth-ip", "auth-token-requests", "auth-path"],
)
def test_a_changed_limit_in_routes_yaml_makes_the_comparison_fail(case: tuple[str, dict[str, Any]], name: str, changes: dict[str, Any]) -> None:
    env, ir = case
    assert problems(ir, altered(read_routes(), name, **changes), env) != []


def test_a_changed_global_limit_makes_the_comparison_fail(case: tuple[str, dict[str, Any]]) -> None:
    env, ir = case
    routes = copy.deepcopy(read_routes())
    routes["global_limit"]["requests"] += 1
    assert problems(ir, routes, env) != []


def drop_rule(directory: Path, policy: str, index: int) -> None:
    path = directory / "backendtrafficpolicies.yaml"
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    (target,) = [d for d in docs if d and d["metadata"]["name"] == policy]
    target["spec"]["rateLimit"]["global"]["rules"].pop(index)
    path.write_text(yaml.safe_dump_all(docs, sort_keys=True), encoding="utf-8")


@pytest.mark.parametrize(("policy", "index"), [(EDGE_POLICY, 0), (EDGE_POLICY, 1), (AUTH_POLICY, 0), (AUTH_POLICY, 3)])
def test_a_rule_removed_from_a_copy_of_generated_makes_the_comparison_fail(tmp_path: Path, policy: str, index: int) -> None:
    copy_dir = tmp_path / "prod"
    shutil.copytree(xds.GENERATED / "prod", copy_dir)
    drop_rule(copy_dir, policy, index)
    assert problems(translate_ir(copy_dir), read_routes(), "prod") != []
