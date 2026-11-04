"""Los manifiestos que `route-gen` debe generar, escritos aparte del generador y con los valores del diseno.

`expected(env, f09, simulator_azp)` devuelve `{archivo: [documentos]}` completos. Las pruebas comparan cada
documento generado entero contra esto (leccion de U02-T07). Todo valor que fija el diseno se lee de los documentos
de diseno por `gateway_design` (claims, scopes, `azp`, `cacheDuration`, outlier y reintentos, saltos de confianza,
caminos y reescrituras, destinos, cabeceras, cookie, F09, grants); aqui solo queda lo que fija el generador (nombres de
reglas y de politicas, etiquetas, orden) y la logica que arma cada documento.
"""

from typing import Any

import gateway_design as gd
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

GATEWAY_GROUP = "gateway.networking.k8s.io"
EG_GROUP = "gateway.envoyproxy.io"
EG_API = f"{EG_GROUP}/v1alpha1"
GW_API = f"{GATEWAY_GROUP}/v1"
LABELS = {"app.kubernetes.io/managed-by": "route-gen", "app.kubernetes.io/part-of": "identity-edge"}
TRACE_ID = "%TRACE_ID%"
QUERY_SUFFIX = r"(\?.*)?$"

FILES = (
    "backendtrafficpolicies.yaml",
    "clienttrafficpolicies.yaml",
    "httproutefilters.yaml",
    "httproutes.yaml",
    "referencegrants.yaml",
    "securitypolicies.yaml",
)
EXTERNAL_SECRETS_FILE = "externalsecrets.yaml"

# Fila de §4 y destino (Service) de cada ruta. Los puertos y namespaces salen de INF-U2-10.
ROW = {
    "spa": "/",
    "console": "/api/console/**",
    "intake": "/api/intake/**",
    "promotion": "/api/promotion/**",
    "auth": "/auth/realms/vectra/**",
    "grafana": "/grafana/**",
    "federate": "/federate",
}
SERVICE = {
    "spa": "console-spa",
    "console": "console-bff",
    "intake": "case-service",
    "promotion": "governance-service",
    "auth": "keycloak",
    "grafana": "kube-prometheus-stack-grafana",
    "federate": "kube-prometheus-stack-prometheus",
}
# La clave de P-U2-02 de cada ruta con reintentos, y su regla de solo lectura.
RETRY_KEY = {"console": "/api/console/**", "promotion": "/api/promotion/**", "auth": "/auth/**", "grafana": "/grafana/**"}
TIMEOUT_KEY = {"console": "/api/console/**", "intake": "/api/intake/**", "promotion": "/api/promotion/**", "auth": "/auth/**", "grafana": "/grafana/**"}
READ_RULE = {"console": "console-read", "promotion": "promotion-models", "auth": "auth-read", "grafana": "grafana-read"}

PROBLEM_ERRORS: dict[int, VectraError] = {
    401: Unauthenticated(),
    403: Forbidden(),
    404: NotFound(),
    413: PayloadTooLarge(),
    429: RateLimited(),
    503: DependencyUnavailable(),
}


def edge_namespace() -> str:
    return gd.gateway_ref()[1]


def dest(route: str) -> tuple[str, str, int]:
    namespace, port = gd.destinations()[SERVICE[route]]
    return (SERVICE[route], namespace, port)


def problem_json(status: int) -> str:
    assert status in gd.error_statuses()
    return problem_body(to_problem(PROBLEM_ERRORS[status], TRACE_ID)).decode("utf-8")


def meta(name: str, namespace: str | None = None) -> dict[str, Any]:
    return {"name": name, "namespace": namespace or edge_namespace(), "labels": dict(LABELS)}


def gateway_ref() -> dict[str, Any]:
    return {"group": GATEWAY_GROUP, "kind": "Gateway", "name": gd.gateway_ref()[0]}


def route_ref(route: str, rule: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"group": GATEWAY_GROUP, "kind": "HTTPRoute", "name": route}
    if rule:
        ref["sectionName"] = rule
    return ref


def backend_ref(d: tuple[str, str, int]) -> dict[str, Any]:
    name, namespace, port = d
    return {"group": "", "kind": "Service", "name": name, "namespace": namespace, "port": port}


def match(path_type: str, value: str, method: str | None = None, query: list[dict[str, str]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"path": {"type": path_type, "value": value}}
    if method:
        out["method"] = method
    if query:
        out["queryParams"] = query
    return out


def sorted_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(matches, key=lambda m: (m["path"]["value"], m["path"]["type"], m.get("method", "")))


def response_headers(profile: str) -> dict[str, Any]:
    profiles = gd.profiles()
    sets = {**profiles["common"].set, **profiles[profile].set}
    modifier: dict[str, Any] = {"set": [{"name": k, "value": sets[k]} for k in sorted(sets)]}
    if profiles[profile].add:
        modifier["add"] = [{"name": k, "value": v} for k, v in sorted(profiles[profile].add.items())]
    return {"type": "ResponseHeaderModifier", "responseHeaderModifier": modifier}


def request_headers() -> dict[str, Any]:
    return {"type": "RequestHeaderModifier", "requestHeaderModifier": {"remove": gd.internal_headers()}}


def extension_filter(name: str) -> dict[str, Any]:
    return {"type": "ExtensionRef", "extensionRef": {"group": EG_GROUP, "kind": "HTTPRouteFilter", "name": name}}


def rule(name: str, matches: list[dict[str, Any]], filters: list[dict[str, Any]], d: tuple[str, str, int] | None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "matches": sorted_matches(matches), "filters": filters}
    if d:
        out["backendRefs"] = [backend_ref(d)]
    return out


def httproute(name: str, hostname: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    gateway, namespace, section = gd.gateway_ref()
    return {
        "apiVersion": GW_API,
        "kind": "HTTPRoute",
        "metadata": meta(name),
        "spec": {
            "parentRefs": [{"group": GATEWAY_GROUP, "kind": "Gateway", "name": gateway, "namespace": namespace, "sectionName": section}],
            "hostnames": [hostname],
            "rules": sorted(rules, key=lambda r: r["name"]),
        },
    }


def with_methods(path_type: str, value: str, methods: list[str]) -> list[dict[str, Any]]:
    return [match(path_type, value, m) for m in methods]


def row_prefix(route: str) -> str:
    key = ROW[route]
    assert key.endswith("/**")
    return key[: -len("/**")]


def auth_matches(methods: list[str] | None) -> list[dict[str, Any]]:
    exact, prefix = gd.auth_entries()
    found = []
    for path_type, paths in (("Exact", exact), ("PathPrefix", prefix)):
        for path in paths:
            found += [match(path_type, path, m) for m in methods] if methods else [match(path_type, path)]
    return found


def read_methods() -> list[str]:
    return ["GET", "HEAD"]


def rewrite_filter(target: str) -> dict[str, Any]:
    return {"type": "URLRewrite", "urlRewrite": {"path": {"type": "ReplaceFullPath", "replaceFullPath": target}}}


def activation_pattern(source: str) -> str:
    return source.replace("{id}", "[^/]+")


def httproutes(hostname: str, f09: bool) -> list[dict[str, Any]]:
    intake, models, activation = gd.rewrites()
    state, approved = gd.promotion_query()
    get_method, post_method = gd.promotion_methods()
    closed_profile = {"api": "api", "auth": "auth", "federate": "api"}  # perfil de la fila de cada prefijo cerrado
    closed_rules = [
        rule(
            f"closed-{prefix.lstrip('/')}",
            [match("PathPrefix", prefix)],
            [extension_filter("problem-not-found"), response_headers(closed_profile[prefix.lstrip("/")])],
            None,
        )
        for prefix in gd.closed_prefixes()
    ]
    routes = [
        httproute("spa", hostname, [rule("spa", [match("PathPrefix", "/")], [response_headers("spa")], dest("spa"))]),
        httproute(
            "console",
            hostname,
            [
                rule("console-read", with_methods("PathPrefix", row_prefix("console"), read_methods()), [request_headers(), response_headers("api")], dest("console")),
                rule("console-write", [match("PathPrefix", row_prefix("console"))], [request_headers(), response_headers("api")], dest("console")),
            ],
        ),
        httproute(
            "intake",
            hostname,
            [rule("intake-submit", [match("Exact", intake.source, gd.intake_method())], [rewrite_filter(intake.target), request_headers(), response_headers("api")], dest("intake"))],
        ),
        httproute(
            "promotion",
            hostname,
            [
                rule(
                    "promotion-models",
                    [match("Exact", models.source, get_method, [{"type": "Exact", "name": state, "value": approved}])],
                    [rewrite_filter(models.target), request_headers(), response_headers("api")],
                    dest("promotion"),
                ),
                rule(
                    "promotion-activation",
                    [match("RegularExpression", activation_pattern(activation.source), post_method)],
                    [extension_filter("rewrite-promotion-activation"), request_headers(), response_headers("api")],
                    dest("promotion"),
                ),
            ],
        ),
        httproute(
            "auth",
            hostname,
            [
                rule("auth-read", auth_matches(read_methods()), [response_headers("auth")], dest("auth")),
                rule("auth-write", auth_matches(None), [response_headers("auth")], dest("auth")),
            ],
        ),
        httproute(
            "grafana",
            hostname,
            [
                rule("grafana-read", with_methods("PathPrefix", row_prefix("grafana"), read_methods()), [response_headers("grafana")], dest("grafana")),
                rule("grafana-write", [match("PathPrefix", row_prefix("grafana"))], [response_headers("grafana")], dest("grafana")),
            ],
        ),
        httproute("closed", hostname, closed_rules),
    ]
    if f09:
        routes.append(httproute("federate", hostname, [rule("federate", [match("Exact", "/federate", "GET")], [response_headers("api")], dest("federate"))]))
    return sorted(routes, key=lambda r: r["metadata"]["name"])


def httproutefilters() -> list[dict[str, Any]]:
    activation = gd.rewrites()[2]
    base = activation.source.split("/v1/")[0]  # `/api/promotion`
    return [
        {
            "apiVersion": EG_API,
            "kind": "HTTPRouteFilter",
            "metadata": meta("problem-not-found"),
            "spec": {
                "directResponse": {
                    "contentType": "application/problem+json",
                    "statusCode": 404,
                    "body": {"type": "Inline", "inline": problem_json(404)},
                }
            },
        },
        {
            "apiVersion": EG_API,
            "kind": "HTTPRouteFilter",
            "metadata": meta("rewrite-promotion-activation"),
            "spec": {
                "urlRewrite": {
                    "path": {
                        "type": "ReplaceRegexMatch",
                        "replaceRegexMatch": {"pattern": f"^{base}({activation_pattern(activation.source)[len(base):]})$", "substitution": "\\1"},
                    }
                }
            },
        },
    ]


# --- SecurityPolicy ---------------------------------------------------------------------------


def jwt_policy(name: str, hostname: str, claims: list[dict[str, Any]], scopes: list[str]) -> dict[str, Any]:
    principal: dict[str, Any] = {"provider": "keycloak", "claims": sorted(claims, key=lambda c: c["name"])}
    if scopes:
        principal["scopes"] = sorted(scopes)
    sub, azp = (f"{gd.internal_prefix()}{k}" for k in ("sub", "azp"))
    return {
        "apiVersion": EG_API,
        "kind": "SecurityPolicy",
        "metadata": meta(name),
        "spec": {
            "targetRefs": [route_ref(name)],
            "jwt": {
                "providers": [
                    {
                        "name": "keycloak",
                        "issuer": f"https://{hostname}{gd.jwt_issuer_path()}",
                        "remoteJWKS": {
                            "uri": gd.jwks_uri(),
                            "backendRefs": [backend_ref(dest("auth"))],
                            "cacheDuration": gd.jwks_cache_duration(),
                        },
                        "claimToHeaders": [{"claim": "azp", "header": azp}, {"claim": "sub", "header": sub}],
                    }
                ]
            },
            "authorization": {
                "defaultAction": "Deny",
                "rules": [{"name": f"{name}-allow", "action": "Allow", "principal": {"jwt": principal}}],
            },
        },
    }


def claim(name: str, values: list[str], array: bool = False) -> dict[str, Any]:
    return {"name": name, "valueType": "StringArray" if array else "String", "values": sorted(values)}


def securitypolicies(hostname: str, f09: bool, simulator_azp: str | None) -> list[dict[str, Any]]:
    console, intake, promotion = (gd.auth_row(ROW[r]) for r in ("console", "intake", "promotion"))
    assert [gd.authentication_kind(ROW[r]) for r in ("console", "intake", "promotion")] == ["jwt"] * 3
    intake_azp = [a for a in intake.azp if a not in intake.non_prod_azp] + ([simulator_azp] if simulator_azp else [])
    assert console.roles and promotion.roles and promotion.acr
    policies = [
        jwt_policy("console", hostname, [claim("azp", console.azp), claim("roles", console.roles, array=True)], console.scopes),
        jwt_policy("intake", hostname, [claim("azp", intake_azp)], intake.scopes),
        jwt_policy(
            "promotion",
            hostname,
            [claim("acr", [promotion.acr]), claim("azp", promotion.azp), claim("roles", promotion.roles, array=True)],
            promotion.scopes,
        ),
    ]
    if f09:
        assert gd.authentication_kind(ROW["federate"]) == "basic"
        policies.append(
            {
                "apiVersion": EG_API,
                "kind": "SecurityPolicy",
                "metadata": meta("federate"),
                "spec": {
                    "targetRefs": [route_ref("federate")],
                    "basicAuth": {"users": {"group": "", "kind": "Secret", "name": gd.federate().secret}},
                },
            }
        )
    return sorted(policies, key=lambda p: p["metadata"]["name"])


# --- BackendTrafficPolicy ---------------------------------------------------------------------


def override(status: int, retry_after: str | None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "contentType": "application/problem+json",
        "body": {"type": "Inline", "inline": problem_json(status)},
    }
    if status == 429 and retry_after:
        response["header"] = {"set": [{"name": "Retry-After", "value": retry_after}]}
    return {"match": {"statusCodes": [{"type": "Value", "value": status}]}, "source": "Local", "response": response}


def passive(console: bool) -> dict[str, Any]:
    o = gd.outlier()
    out: dict[str, Any] = {"baseEjectionTime": o.base_ejection_time, "maxEjectionPercent": o.max_ejection_percent}
    if console:  # en la consola cuentan solo los errores de conexion
        out |= {"consecutive5XxErrors": 0, "consecutiveLocalOriginFailures": o.local_origin_failures, "splitExternalLocalOriginErrors": True}
    else:
        out["consecutive5XxErrors"] = o.consecutive_5xx
    return out


def error_codes(route: str) -> list[int]:
    """Los estados `Problem` de una ruta: 429 siempre, 503 con backend, 401/403 si autentica, 413 si tiene tope de tamano."""
    kind = gd.authentication_kind(ROW[route])
    codes = {429, 503}
    if kind in ("jwt", "basic"):
        codes.add(401)
    if kind == "jwt":
        codes.add(403)
    if gd.body_limit(ROW[route]):
        codes.add(413)
    return sorted(codes)


def btp(route: str, rule_name: str, *, timeout: str | None, retry: bool, console: bool, limit: str | None, cookie: bool, retry_after: str) -> dict[str, Any]:
    spec: dict[str, Any] = {"mergeType": "StrategicMerge", "targetRefs": [route_ref(route, rule_name)]}
    if retry:
        r = gd.retry()
        spec["retry"] = {"numRetries": r.num_retries, "retryOn": {"triggers": [r.trigger]}}
        spec["circuitBreaker"] = {"retryBudget": {"percent": {"numerator": r.budget_percent, "denominator": 100}}}
    spec["healthCheck"] = {"passive": passive(console)}
    if cookie:
        c = gd.cookie()
        spec["loadBalancer"] = {
            "type": "ConsistentHash",
            "consistentHash": {"type": "Cookie", "cookie": {"name": c.name, "ttl": c.ttl, "attributes": dict(sorted(c.attributes.items()))}},
        }
    if limit:
        spec["requestBuffer"] = {"limit": limit}
    spec["responseOverride"] = [override(c, retry_after) for c in error_codes(route)]
    if timeout:
        spec["timeout"] = {"http": {"requestTimeout": timeout}}
    return {"apiVersion": EG_API, "kind": "BackendTrafficPolicy", "metadata": meta(rule_name), "spec": spec}


def counter_regex(paths: list[str]) -> str:
    """Los caminos de un contador de `/auth/**` (relativos al realm) como un patron que admite consulta."""
    parts = [p[: -len("/**")] + "(/[^?]*)?" if p.endswith("/**") else p for p in paths]
    body = parts[0] if len(parts) == 1 else "(" + "|".join(parts) + ")"
    return "^" + gd.AUTH_BASE + body + QUERY_SUFFIX


def rate_limit_rules(simulator_azp: str | None, f09: bool) -> list[dict[str, Any]]:
    n, u = gd.rate_limit_numbers(), gd.rate_limit_units()
    sub = f"{gd.internal_prefix()}sub"
    azp = f"{gd.internal_prefix()}azp"
    distinct_sub = {"name": sub, "type": "Distinct"}
    intake_path = {"type": "RegularExpression", "value": "^" + gd.rewrites()[0].source + QUERY_SUFFIX}
    counters = gd.auth_counters()

    def rl(key: str, selector: dict[str, Any] | None) -> dict[str, Any]:
        out: dict[str, Any] = {"limit": {"requests": n[key], "unit": u[key]}, "shared": True}
        if selector:
            out["clientSelectors"] = [selector]
        return out

    rules: dict[str, dict[str, Any]] = {
        "console": rl("console", {"headers": [distinct_sub], "path": {"type": "PathPrefix", "value": row_prefix("console")}}),
        "global": rl("global", None),
        "intake-channel": rl("intake-channel", {"headers": [{"name": azp, "type": "Exact", "value": "channel"}], "path": intake_path}),
        "promotion": rl("promotion", {"headers": [distinct_sub], "path": {"type": "PathPrefix", "value": row_prefix("promotion")}}),
    }
    for name, key in (("auth-login", "login"), ("auth-token", "token")):
        for cidr in ("0.0.0.0/0", "::/0"):  # un contador por IP de origen, IPv4 e IPv6
            rules[f"{name}@{cidr}"] = rl("auth", {"path": {"type": "RegularExpression", "value": counter_regex(counters[key])}, "sourceCIDR": {"type": "Distinct", "value": cidr}})
    if simulator_azp:
        rules["intake-channel-simulator"] = rl("intake-channel-simulator", {"headers": [{"name": azp, "type": "Exact", "value": simulator_azp}], "path": intake_path})
    if f09:
        rules["federate"] = rl("federate", {"path": {"type": "RegularExpression", "value": "^/federate" + QUERY_SUFFIX}})
    return [rules[k] for k in sorted(rules)]


def backendtrafficpolicies(simulator_azp: str | None, f09: bool) -> list[dict[str, Any]]:
    ra = gd.retry_after()
    timeouts = gd.timeouts()
    retried = set(gd.retry().routes)
    assert retried == set(RETRY_KEY.values())
    rules = {
        "spa": ["spa"],
        "console": ["console-read", "console-write"],
        "intake": ["intake-submit"],
        "promotion": ["promotion-models", "promotion-activation"],
        "auth": ["auth-read", "auth-write"],
        "grafana": ["grafana-read", "grafana-write"],
    }
    if f09:
        rules["federate"] = ["federate"]
    policies = [
        {
            "apiVersion": EG_API,
            "kind": "BackendTrafficPolicy",
            "metadata": meta("edge-rate-limits"),
            "spec": {
                "targetRefs": [gateway_ref()],
                "rateLimit": {"type": "Global", "global": {"rules": rate_limit_rules(simulator_azp, f09)}},
            },
        },
        {
            "apiVersion": EG_API,
            "kind": "BackendTrafficPolicy",
            "metadata": meta("closed"),
            "spec": {
                "mergeType": "StrategicMerge",
                "targetRefs": [route_ref("closed")],
                "responseOverride": [override(c, ra["second"]) for c in (404, 429)],
            },
        },
    ]
    for route, names in rules.items():
        for name in names:
            policies.append(
                btp(
                    route,
                    name,
                    timeout=timeouts.get(TIMEOUT_KEY.get(route, "")),
                    retry=name == READ_RULE.get(route),
                    console=route == "console",
                    limit=gd.body_limit(ROW[route]),
                    cookie=route == "spa",
                    retry_after=ra["auth"] if route == "auth" else ra["second"],
                )
            )
    return sorted(policies, key=lambda p: p["metadata"]["name"])


def clienttrafficpolicies() -> list[dict[str, Any]]:
    prefix = gd.internal_prefix()
    remove, remove_prefixes = gd.response_removals()
    return [
        {
            "apiVersion": EG_API,
            "kind": "ClientTrafficPolicy",
            "metadata": meta("edge-client"),
            "spec": {
                "targetRefs": [gateway_ref()],
                "clientIPDetection": {"xForwardedFor": {"numTrustedHops": gd.trusted_hops()}},
                "headers": {
                    "earlyRequestHeaders": {"removeOnMatch": [{"type": "Prefix", "value": prefix}]},
                    "lateResponseHeaders": {
                        "remove": remove,
                        "removeOnMatch": [{"type": "Prefix", "value": v} for v in sorted([*remove_prefixes, prefix])],
                    },
                },
                "path": {"escapedSlashesAction": gd.escaped_slashes_action(), "disableMergeSlashes": not gd.merge_slashes()},
            },
        }
    ]


def referencegrants(f09: bool) -> list[dict[str, Any]]:
    edge = edge_namespace()
    used: dict[str, set[str]] = {}
    for route in [r for r in SERVICE if r != "spa" and (f09 or r != "federate")]:
        namespace, _ = gd.destinations()[SERVICE[route]]
        used.setdefault(namespace, set()).add(SERVICE[route])
    assert set(used) <= set(gd.grant_namespaces())
    grant_ns, grant_group, grant_service = gd.securitypolicy_grant()
    out = []
    for namespace in gd.grant_namespaces():
        sources = [{"group": GATEWAY_GROUP, "kind": "HTTPRoute", "namespace": edge}]
        if namespace == grant_ns:
            assert used[namespace] == {grant_service}
            sources.append({"group": grant_group, "kind": "SecurityPolicy", "namespace": edge})
        out.append(
            {
                "apiVersion": GW_API,
                "kind": "ReferenceGrant",
                "metadata": meta("edge-routes", namespace),
                "spec": {"from": sources, "to": [{"group": "", "kind": "Service", "name": n} for n in sorted(used[namespace])]},
            }
        )
    return out


def externalsecrets() -> list[dict[str, Any]]:
    f = gd.federate()
    return [
        {
            "apiVersion": "external-secrets.io/v1",
            "kind": "ExternalSecret",
            "metadata": meta(f.secret, f.namespace),
            "spec": {
                "secretStoreRef": {"name": f.store_name, "kind": f.store_kind},
                "target": {"name": f.secret},
                "data": [{"secretKey": f.property, "remoteRef": {"key": f.key, "property": f.property}}],
            },
        }
    ]


def expected(env: str, f09: bool, simulator_azp: str | None) -> dict[str, list[dict[str, Any]]]:
    hostname = gd.hostnames()[env]
    files = {
        "backendtrafficpolicies.yaml": backendtrafficpolicies(simulator_azp, f09),
        "clienttrafficpolicies.yaml": clienttrafficpolicies(),
        "httproutefilters.yaml": httproutefilters(),
        "httproutes.yaml": httproutes(hostname, f09),
        "referencegrants.yaml": referencegrants(f09),
        "securitypolicies.yaml": securitypolicies(hostname, f09, simulator_azp),
    }
    if f09:
        files[EXTERNAL_SECRETS_FILE] = externalsecrets()
    return files
