"""`route-gen` (U02-T09, Paso 7 de U2): `routes.yaml` + `values/<env>.yaml` -> manifiestos de Envoy Gateway.

Genera por entorno, en `identity-edge/gateway/generated/<env>/`: HTTPRoute (cerradas, con 404 `Problem` para el resto),
HTTPRouteFilter, SecurityPolicy (JWT con JWKS interna y autorizacion `Deny` por defecto), BackendTrafficPolicy
(reintentos solo idempotentes, outlier detection, tamano por ruta, afinidad, errores `Problem`, y los descriptores de
rate limit en una politica del Gateway), ClientTrafficPolicy, ReferenceGrant y, con F09 habilitada, un ExternalSecret.

Sin `--check` escribe; con `--check` compara sin escribir y termina distinto de 0 si algo difiere. La salida es una
funcion pura de las entradas: toda lista de `routes.yaml` es un conjunto y se ordena, y las claves van ordenadas.
Diseno: domain-entities §4 y §4.1; BR-U2-08, 10, 11, 13, 14; P-U2-02, 03, 06, 07; INF-U2-01, 10.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from vectra_common.errors import (
    DependencyUnavailable,
    Forbidden,
    NotFound,
    PayloadTooLarge,
    RateLimited,
    Unauthenticated,
    VectraError,
    problem_body,
    to_problem,
)

EDGE = Path(__file__).resolve().parents[1]
GATEWAY_DIR = EDGE / "gateway"
ROUTES_YAML = GATEWAY_DIR / "routes.yaml"
VALUES_DIR = GATEWAY_DIR / "values"
GENERATED = GATEWAY_DIR / "generated"
ENVS = ("kind", "staging", "prod")

GW_GROUP = "gateway.networking.k8s.io"
GW_API = f"{GW_GROUP}/v1"
EG_GROUP = "gateway.envoyproxy.io"
EG_API = f"{EG_GROUP}/v1alpha1"
LABELS = {"app.kubernetes.io/managed-by": "route-gen", "app.kubernetes.io/part-of": "identity-edge"}
HEADER = "# Generado por identity-edge/tools/route_gen.py desde identity-edge/gateway/routes.yaml. No editar a mano.\n"
TRACE_ID = "%TRACE_ID%"  # operador de formato de Envoy: el trace-id de `traceparent` (P-U2-07)
PROBLEM_CONTENT_TYPE = "application/problem+json"
NOT_FOUND_FILTER = "problem-not-found"
EDGE_RATE_LIMITS = "edge-rate-limits"
CLIENT_POLICY = "edge-client"

PROBLEM_ERRORS: dict[int, VectraError] = {
    401: Unauthenticated(),
    403: Forbidden(),
    404: NotFound(),
    413: PayloadTooLarge(),
    429: RateLimited(),
    503: DependencyUnavailable(),
}


class RoutesError(ValueError):
    """`routes.yaml` o los values no son validos."""


def load_routes(path: Path = ROUTES_YAML) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RoutesError(f"{path}: se esperaba un mapa")
    return data


def load_values(env: str, directory: Path = VALUES_DIR) -> dict[str, Any]:
    data = yaml.safe_load((directory / f"{env}.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RoutesError(f"values/{env}.yaml: se esperaba un mapa")
    return data


# --- bloques comunes ---------------------------------------------------------------------------


def problem_json(status: int) -> str:
    return problem_body(to_problem(PROBLEM_ERRORS[status], TRACE_ID)).decode("utf-8")


def meta(ctx: "Ctx", name: str, namespace: str | None = None) -> dict[str, Any]:
    return {"name": name, "namespace": namespace or ctx.namespace, "labels": dict(LABELS)}


class Ctx:
    """Entradas ya validadas: las rutas activas (F09 segun los values) y el entorno."""

    def __init__(self, routes: dict[str, Any], values: dict[str, Any]) -> None:
        self.routes = routes
        self.values = values
        self.namespace: str = routes["namespace"]
        self.gateway: str = routes["gateway"]["name"]
        self.section: str = routes["gateway"]["section"]
        self.hostname: str = values["hostname"]
        f09 = bool(values.get("f09", {}).get("enabled", False))
        self.active = sorted((r for r in routes["routes"] if r.get("requires") != "f09" or f09), key=lambda r: r["name"])
        self.f09 = f09
        names = [rule["name"] for r in self.active for rule in r["rules"]] + [c["rule"] for c in routes["closed"]]
        if len(names) != len(set(names)):
            raise RoutesError("nombres de regla repetidos")
        unknown = {r["profile"] for r in self.active} | {c["profile"] for c in routes["closed"]}
        if not unknown <= set(routes["profiles"]):
            raise RoutesError(f"perfiles desconocidos: {sorted(unknown - set(routes['profiles']))}")

    def enabled(self, item: dict[str, Any]) -> bool:
        if item.get("requires") == "f09" and not self.f09:
            return False
        key = item.get("header", {}).get("value_from")
        return not key or bool(self.values.get(key))


def gateway_ref(ctx: Ctx) -> dict[str, Any]:
    return {"group": GW_GROUP, "kind": "Gateway", "name": ctx.gateway}


def route_ref(name: str, rule: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"group": GW_GROUP, "kind": "HTTPRoute", "name": name}
    if rule:
        ref["sectionName"] = rule
    return ref


def backend_ref(backend: dict[str, Any]) -> dict[str, Any]:
    return {"group": "", "kind": "Service", "name": backend["service"], "namespace": backend["namespace"], "port": backend["port"]}


# --- HTTPRoute ---------------------------------------------------------------------------------


def build_match(match: dict[str, Any], method: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {"path": {"type": match["type"], "value": match["path"]}}
    if method:
        out["method"] = method
    if match.get("query"):
        out["queryParams"] = [{"type": "Exact", "name": k, "value": v} for k, v in sorted(match["query"].items())]
    return out


def match_key(match: dict[str, Any]) -> tuple[str, str, str]:
    return (match["path"]["value"], match["path"]["type"], match.get("method", ""))


def rule_matches(route: dict[str, Any], rule: dict[str, Any]) -> list[dict[str, Any]]:
    bases = rule.get("matches", route.get("matches"))
    if not bases:
        raise RoutesError(f"regla {rule['name']} sin matches")
    methods = sorted(rule.get("methods") or [None], key=lambda m: m or "")
    return sorted((build_match(m, method) for m in bases for method in methods), key=match_key)


def response_headers(ctx: Ctx, profile: str) -> dict[str, Any]:
    profiles = ctx.routes["profiles"]
    sets = {**profiles["common"].get("set", {}), **profiles[profile].get("set", {})}
    adds = {**profiles["common"].get("add", {}), **profiles[profile].get("add", {})}
    modifier: dict[str, Any] = {"set": [{"name": k, "value": sets[k]} for k in sorted(sets)]}
    if adds:
        modifier["add"] = [{"name": k, "value": adds[k]} for k in sorted(adds)]
    return {"type": "ResponseHeaderModifier", "responseHeaderModifier": modifier}


def extension_ref(name: str) -> dict[str, Any]:
    return {"type": "ExtensionRef", "extensionRef": {"group": EG_GROUP, "kind": "HTTPRouteFilter", "name": name}}


def route_rule(ctx: Ctx, route: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    rewrite = rule.get("rewrite")
    if rewrite and "full_path" in rewrite:
        filters.append({"type": "URLRewrite", "urlRewrite": {"path": {"type": "ReplaceFullPath", "replaceFullPath": rewrite["full_path"]}}})
    elif rewrite:
        filters.append(extension_ref(rewrite["filter"]))
    if route.get("auth", {}).get("kind") == "jwt":
        filters.append({"type": "RequestHeaderModifier", "requestHeaderModifier": {"remove": sorted(ctx.routes["internal_headers"])}})
    filters.append(response_headers(ctx, route["profile"]))
    return {
        "name": rule["name"],
        "matches": rule_matches(route, rule),
        "filters": filters,
        "backendRefs": [backend_ref(route["backend"])],
    }


def http_route(ctx: Ctx, name: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "apiVersion": GW_API,
        "kind": "HTTPRoute",
        "metadata": meta(ctx, name),
        "spec": {
            "parentRefs": [{"group": GW_GROUP, "kind": "Gateway", "name": ctx.gateway, "namespace": ctx.namespace, "sectionName": ctx.section}],
            "hostnames": [ctx.hostname],
            "rules": sorted(rules, key=lambda r: r["name"]),
        },
    }


def closed_route(ctx: Ctx) -> dict[str, Any]:
    rules = [
        {
            "name": c["rule"],
            "matches": [{"path": {"type": "PathPrefix", "value": c["path"]}}],
            "filters": [extension_ref(NOT_FOUND_FILTER), response_headers(ctx, c["profile"])],
        }
        for c in ctx.routes["closed"]
    ]
    return http_route(ctx, "closed", rules)


def http_routes(ctx: Ctx) -> list[dict[str, Any]]:
    routes = [http_route(ctx, r["name"], [route_rule(ctx, r, rule) for rule in r["rules"]]) for r in ctx.active]
    routes.append(closed_route(ctx))
    return sorted(routes, key=lambda d: d["metadata"]["name"])


def http_route_filters(ctx: Ctx) -> list[dict[str, Any]]:
    filters = [
        {
            "apiVersion": EG_API,
            "kind": "HTTPRouteFilter",
            "metadata": meta(ctx, NOT_FOUND_FILTER),
            "spec": {
                "directResponse": {
                    "contentType": PROBLEM_CONTENT_TYPE,
                    "statusCode": 404,
                    "body": {"type": "Inline", "inline": problem_json(404)},
                }
            },
        }
    ]
    for route in ctx.active:
        for rule in route["rules"]:
            rewrite = rule.get("rewrite", {})
            if "filter" in rewrite:
                filters.append(
                    {
                        "apiVersion": EG_API,
                        "kind": "HTTPRouteFilter",
                        "metadata": meta(ctx, rewrite["filter"]),
                        "spec": {
                            "urlRewrite": {
                                "path": {
                                    "type": "ReplaceRegexMatch",
                                    "replaceRegexMatch": {"pattern": rewrite["pattern"], "substitution": rewrite["substitution"]},
                                }
                            }
                        },
                    }
                )
    return sorted(filters, key=lambda d: d["metadata"]["name"])


# --- SecurityPolicy ----------------------------------------------------------------------------


def build_claim(ctx: Ctx, claim: dict[str, Any]) -> dict[str, Any]:
    values = set(claim["values"])
    extra = ctx.values.get(claim["extra_values_from"]) if claim.get("extra_values_from") else None
    if extra:
        values.add(extra)
    return {"name": claim["name"], "valueType": "StringArray" if claim.get("array") else "String", "values": sorted(values)}


def security_policy(ctx: Ctx, route: dict[str, Any]) -> dict[str, Any]:
    auth = route["auth"]
    spec: dict[str, Any] = {"targetRefs": [route_ref(route["name"])]}
    if auth["kind"] == "basic":
        spec["basicAuth"] = {"users": {"group": "", "kind": "Secret", "name": auth["secret"]}}
    else:
        jwt = ctx.routes["jwt"]
        principal: dict[str, Any] = {
            "provider": jwt["provider"],
            "claims": sorted((build_claim(ctx, c) for c in auth["claims"]), key=lambda c: c["name"]),
        }
        if auth.get("scopes"):
            principal["scopes"] = sorted(auth["scopes"])
        spec["jwt"] = {
            "providers": [
                {
                    "name": jwt["provider"],
                    "issuer": f"https://{ctx.hostname}{jwt['issuer_path']}",
                    "remoteJWKS": {
                        "uri": jwt["jwks_uri"],
                        "backendRefs": [backend_ref(jwt["jwks_backend"])],
                        "cacheDuration": jwt["cache_duration"],
                    },
                    "claimToHeaders": sorted(jwt["claim_to_headers"], key=lambda c: c["claim"]),
                }
            ]
        }
        spec["authorization"] = {
            "defaultAction": "Deny",
            "rules": [{"name": f"{route['name']}-allow", "action": "Allow", "principal": {"jwt": principal}}],
        }
    return {"apiVersion": EG_API, "kind": "SecurityPolicy", "metadata": meta(ctx, route["name"]), "spec": spec}


def security_policies(ctx: Ctx) -> list[dict[str, Any]]:
    return [security_policy(ctx, r) for r in ctx.active if r.get("auth")]


# --- BackendTrafficPolicy ----------------------------------------------------------------------


def override(status: int, retry_after: str) -> dict[str, Any]:
    response: dict[str, Any] = {
        "contentType": PROBLEM_CONTENT_TYPE,
        "body": {"type": "Inline", "inline": problem_json(status)},
    }
    if status == 429:
        response["header"] = {"set": [{"name": "Retry-After", "value": retry_after}]}
    return {"match": {"statusCodes": [{"type": "Value", "value": status}]}, "source": "Local", "response": response}


def passive(ctx: Ctx, route: dict[str, Any]) -> dict[str, Any]:
    base = ctx.routes["outlier"]
    out: dict[str, Any] = {"baseEjectionTime": base["base_ejection_time"], "maxEjectionPercent": base["max_ejection_percent"]}
    local = route.get("outlier", {})
    if local.get("local_origin_only"):
        out |= {
            "consecutive5XxErrors": 0,  # Envoy no expulsa por 5xx con umbral 0 (el contador nunca coincide)
            "consecutiveLocalOriginFailures": local["consecutive_local_origin_failures"],
            "splitExternalLocalOriginErrors": True,
        }
    else:
        out["consecutive5XxErrors"] = base["consecutive_5xx"]
    return out


def rule_traffic_policy(ctx: Ctx, route: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    spec: dict[str, Any] = {"mergeType": "StrategicMerge", "targetRefs": [route_ref(route["name"], rule["name"])]}
    if rule.get("retry"):
        retry = ctx.routes["retry"]
        spec["retry"] = {"numRetries": retry["num_retries"], "retryOn": {"triggers": sorted(retry["triggers"])}}
        spec["circuitBreaker"] = {"retryBudget": {"percent": {"numerator": retry["budget_percent"], "denominator": 100}}}
    spec["healthCheck"] = {"passive": passive(ctx, route)}
    if route.get("affinity"):
        a = route["affinity"]
        spec["loadBalancer"] = {
            "type": "ConsistentHash",
            "consistentHash": {"type": "Cookie", "cookie": {"name": a["cookie"], "ttl": a["ttl"], "attributes": dict(sorted(a["attributes"].items()))}},
        }
    if route.get("max_body"):
        spec["requestBuffer"] = {"limit": route["max_body"]}
    spec["responseOverride"] = [override(c, route["retry_after"]) for c in sorted(route["errors"])]
    if route.get("timeout"):
        spec["timeout"] = {"http": {"requestTimeout": route["timeout"]}}
    return {"apiVersion": EG_API, "kind": "BackendTrafficPolicy", "metadata": meta(ctx, rule["name"]), "spec": spec}


def closed_traffic_policy(ctx: Ctx) -> dict[str, Any]:
    policy = ctx.routes["closed_policy"]
    spec = {
        "mergeType": "StrategicMerge",
        "targetRefs": [route_ref("closed")],
        "responseOverride": [override(c, policy["retry_after"]) for c in sorted(policy["errors"])],
    }
    return {"apiVersion": EG_API, "kind": "BackendTrafficPolicy", "metadata": meta(ctx, "closed"), "spec": spec}


def rate_limit_rule(ctx: Ctx, item: dict[str, Any], cidr: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"limit": {"requests": item["requests"], "unit": item["unit"]}, "shared": True}
    selector: dict[str, Any] = {}
    if item.get("header"):
        header = item["header"]
        value = header.get("value") or (ctx.values[header["value_from"]] if header.get("value_from") else None)
        selector["headers"] = [{"name": header["name"], "type": "Exact", "value": value} if value else {"name": header["name"], "type": "Distinct"}]
    if item.get("path"):
        selector["path"] = dict(item["path"])
    if cidr:
        selector["sourceCIDR"] = {"type": "Distinct", "value": cidr}
    if selector:
        out["clientSelectors"] = [selector]
    return out


def edge_rate_limits(ctx: Ctx) -> dict[str, Any]:
    """Todos los contadores en una sola politica del Gateway: `shared` solo comparte dentro de una politica.

    Las politicas por regla la heredan con `mergeType` (Envoy Gateway v1.9.3, `translateBackendTrafficPolicyForRouteWithMerge`
    conserva los nombres de las reglas de la politica del Gateway, asi que `global` es un solo contador).
    """
    limits = {"global": rate_limit_rule(ctx, ctx.routes["global_limit"])}
    for item in ctx.routes["rate_limits"]:
        if not ctx.enabled(item):
            continue
        if item.get("source_ip"):  # un contador por IP de origen, uno por familia de direcciones
            for cidr in item["source_ip"]:
                limits[f"{item['name']}@{cidr}"] = rate_limit_rule(ctx, item, cidr)
        else:
            limits[item["name"]] = rate_limit_rule(ctx, item)
    return {
        "apiVersion": EG_API,
        "kind": "BackendTrafficPolicy",
        "metadata": meta(ctx, EDGE_RATE_LIMITS),
        "spec": {
            "targetRefs": [gateway_ref(ctx)],
            "rateLimit": {"type": "Global", "global": {"rules": [limits[k] for k in sorted(limits)]}},
        },
    }


def backend_traffic_policies(ctx: Ctx) -> list[dict[str, Any]]:
    policies = [edge_rate_limits(ctx), closed_traffic_policy(ctx)]
    policies += [rule_traffic_policy(ctx, r, rule) for r in ctx.active for rule in r["rules"]]
    return sorted(policies, key=lambda d: d["metadata"]["name"])


# --- ClientTrafficPolicy, ReferenceGrant, ExternalSecret ---------------------------------------


def client_traffic_policies(ctx: Ctx) -> list[dict[str, Any]]:
    c = ctx.routes["client"]
    prefix = ctx.routes["internal_header_prefix"]
    return [
        {
            "apiVersion": EG_API,
            "kind": "ClientTrafficPolicy",
            "metadata": meta(ctx, CLIENT_POLICY),
            "spec": {
                "targetRefs": [gateway_ref(ctx)],
                "clientIPDetection": {"xForwardedFor": {"numTrustedHops": c["trusted_hops"]}},
                "headers": {
                    "earlyRequestHeaders": {"removeOnMatch": [{"type": "Prefix", "value": prefix}]},
                    "lateResponseHeaders": {
                        "remove": sorted(c["response_remove"]),
                        "removeOnMatch": [{"type": "Prefix", "value": v} for v in sorted([*c["response_remove_prefixes"], prefix])],
                    },
                },
                "path": {"escapedSlashesAction": c["escaped_slashes_action"], "disableMergeSlashes": not c["merge_slashes"]},
            },
        }
    ]


def reference_grants(ctx: Ctx) -> list[dict[str, Any]]:
    used: dict[str, set[str]] = {}
    for route in ctx.active:
        backend = route["backend"]
        if backend["namespace"] != ctx.namespace:
            used.setdefault(backend["namespace"], set()).add(backend["service"])
    jwks_namespace = ctx.routes["jwt"]["jwks_backend"]["namespace"]

    def sources(namespace: str) -> list[dict[str, Any]]:
        found = [{"group": GW_GROUP, "kind": "HTTPRoute", "namespace": ctx.namespace}]
        if namespace == jwks_namespace:  # D-1: v1.9.3 exige el grant para el `backendRefs` de la JWKS (SecurityPolicy)
            found.append({"group": EG_GROUP, "kind": "SecurityPolicy", "namespace": ctx.namespace})
        return found

    return [
        {
            "apiVersion": GW_API,
            "kind": "ReferenceGrant",
            "metadata": meta(ctx, "edge-routes", namespace),
            "spec": {
                "from": sources(namespace),
                "to": [{"group": "", "kind": "Service", "name": name} for name in sorted(names)],
            },
        }
        for namespace, names in sorted(used.items())
    ]


def external_secrets(ctx: Ctx) -> list[dict[str, Any]]:
    found = []
    for route in ctx.active:
        auth = route.get("auth", {})
        if auth.get("kind") == "basic":
            ext = auth["external_secret"]
            found.append(
                {
                    "apiVersion": "external-secrets.io/v1",
                    "kind": "ExternalSecret",
                    "metadata": meta(ctx, auth["secret"]),
                    "spec": {
                        "secretStoreRef": {"name": ext["store"], "kind": "ClusterSecretStore"},
                        "target": {"name": auth["secret"]},
                        "data": [{"secretKey": ext["property"], "remoteRef": {"key": ext["key"], "property": ext["property"]}}],
                    },
                }
            )
    return found


# --- salida ------------------------------------------------------------------------------------


def dump(docs: list[dict[str, Any]]) -> str:
    body = "---\n".join(yaml.safe_dump(d, sort_keys=True, default_flow_style=False, width=100_000, allow_unicode=True) for d in docs)
    return HEADER + "---\n" + body


def generate(routes: dict[str, Any], values: dict[str, Any]) -> dict[str, str]:
    """`{archivo: texto}` de un entorno. No modifica sus argumentos."""
    ctx = Ctx(routes, values)
    files = {
        "backendtrafficpolicies.yaml": backend_traffic_policies(ctx),
        "clienttrafficpolicies.yaml": client_traffic_policies(ctx),
        "httproutefilters.yaml": http_route_filters(ctx),
        "httproutes.yaml": http_routes(ctx),
        "referencegrants.yaml": reference_grants(ctx),
        "securitypolicies.yaml": security_policies(ctx),
    }
    secrets = external_secrets(ctx)
    if secrets:
        files["externalsecrets.yaml"] = secrets
    return {name: dump(docs) for name, docs in sorted(files.items())}


def differences(out: Path, routes: dict[str, Any]) -> list[str]:
    """Lo que difiere entre `out/<env>/` y lo que se generaria ahora."""
    found = []
    for env in ENVS:
        want = generate(routes, load_values(env))
        directory = out / env
        have = {p.name: p.read_text(encoding="utf-8") for p in directory.glob("*") if p.is_file()} if directory.is_dir() else {}
        for name in sorted(set(want) | set(have)):
            if name not in have:
                found.append(f"{env}/{name}: falta")
            elif name not in want:
                found.append(f"{env}/{name}: sobra")
            elif have[name] != want[name]:
                found.append(f"{env}/{name}: difiere")
    return found


def write(out: Path, routes: dict[str, Any]) -> None:
    for env in ENVS:
        files = generate(routes, load_values(env))
        directory = out / env
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("*"):
            if stale.is_file() and stale.name not in files:
                stale.unlink()
        for name, text in files.items():
            (directory / name).write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="compara sin escribir; termina distinto de 0 si algo difiere")
    parser.add_argument("--out", type=Path, default=GENERATED, help="directorio de salida (por defecto, gateway/generated)")
    args = parser.parse_args(argv)
    routes = load_routes()
    if args.check:
        found = differences(args.out, routes)
        for line in found:
            print(f"route_gen: {line}", file=sys.stderr)  # noqa: T201
        if found:
            print("route_gen: lo versionado difiere de lo generado: corre `uv run python identity-edge/tools/route_gen.py`", file=sys.stderr)  # noqa: T201
        return 1 if found else 0
    write(args.out, routes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
