"""Los manifiestos que `route-gen` debe generar, escritos aparte del generador y con los valores del diseno.

`expected(env, f09, simulator_azp)` devuelve `{archivo: [documentos]}` completos. Las pruebas comparan cada
documento generado entero contra esto (leccion de U02-T07): los valores que fija el diseno se leen de los
documentos de diseno (`gateway_design`); los que solo fija el generador (nombres, etiquetas, orden) se escriben aqui.
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

EDGE_NS = "vectra-edge"
GATEWAY = "api-gateway"
GATEWAY_GROUP = "gateway.networking.k8s.io"
EG_GROUP = "gateway.envoyproxy.io"
EG_API = f"{EG_GROUP}/v1alpha1"
GW_API = f"{GATEWAY_GROUP}/v1"
LABELS = {"app.kubernetes.io/managed-by": "route-gen", "app.kubernetes.io/part-of": "identity-edge"}
TRACE_ID = "%TRACE_ID%"
INTERNAL_PREFIX = "x-vectra-"
INTERNAL_HEADERS = ["x-vectra-azp", "x-vectra-sub"]
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

SPA = ("console-spa", EDGE_NS, 8080)
CONSOLE = ("console-bff", "vectra-app", 8080)
INTAKE = ("case-service", "vectra-app", 8080)
PROMOTION = ("governance-service", "vectra-app", 8080)
KEYCLOAK = ("keycloak", "vectra-identity", 8443)
GRAFANA = ("kube-prometheus-stack-grafana", "vectra-observability", 80)
PROMETHEUS = ("kube-prometheus-stack-prometheus", "vectra-observability", 9090)

PROBLEM_ERRORS: dict[int, VectraError] = {
    401: Unauthenticated(),
    403: Forbidden(),
    404: NotFound(),
    413: PayloadTooLarge(),
    429: RateLimited(),
    503: DependencyUnavailable(),
}


def problem_json(status: int) -> str:
    return problem_body(to_problem(PROBLEM_ERRORS[status], TRACE_ID)).decode("utf-8")


def meta(name: str, namespace: str = EDGE_NS) -> dict[str, Any]:
    return {"name": name, "namespace": namespace, "labels": dict(LABELS)}


def gateway_ref() -> dict[str, Any]:
    return {"group": GATEWAY_GROUP, "kind": "Gateway", "name": GATEWAY}


def route_ref(route: str, rule: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"group": GATEWAY_GROUP, "kind": "HTTPRoute", "name": route}
    if rule:
        ref["sectionName"] = rule
    return ref


def backend_ref(dest: tuple[str, str, int]) -> dict[str, Any]:
    name, namespace, port = dest
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
    return {"type": "RequestHeaderModifier", "requestHeaderModifier": {"remove": list(INTERNAL_HEADERS)}}


def extension_filter(name: str) -> dict[str, Any]:
    return {"type": "ExtensionRef", "extensionRef": {"group": EG_GROUP, "kind": "HTTPRouteFilter", "name": name}}


def rule(name: str, matches: list[dict[str, Any]], filters: list[dict[str, Any]], dest: tuple[str, str, int] | None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "matches": sorted_matches(matches), "filters": filters}
    if dest:
        out["backendRefs"] = [backend_ref(dest)]
    return out


def httproute(name: str, hostname: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "apiVersion": GW_API,
        "kind": "HTTPRoute",
        "metadata": meta(name),
        "spec": {
            "parentRefs": [{"group": GATEWAY_GROUP, "kind": "Gateway", "name": GATEWAY, "namespace": EDGE_NS, "sectionName": "https"}],
            "hostnames": [hostname],
            "rules": sorted(rules, key=lambda r: r["name"]),
        },
    }


def with_methods(path_type: str, value: str, methods: list[str]) -> list[dict[str, Any]]:
    return [match(path_type, value, m) for m in methods]


def auth_matches(methods: list[str] | None) -> list[dict[str, Any]]:
    exact, prefix = gd.auth_entries()
    found = []
    for path_type, paths in (("Exact", exact), ("PathPrefix", prefix)):
        for path in paths:
            found += [match(path_type, path, m) for m in methods] if methods else [match(path_type, path)]
    return found


def httproutes(hostname: str, f09: bool) -> list[dict[str, Any]]:
    read = ["GET", "HEAD"]
    intake_path = "/api/intake/v1/intake/applications"
    routes = [
        httproute("spa", hostname, [rule("spa", [match("PathPrefix", "/")], [response_headers("spa")], SPA)]),
        httproute(
            "console",
            hostname,
            [
                rule("console-read", with_methods("PathPrefix", "/api/console", read), [request_headers(), response_headers("api")], CONSOLE),
                rule("console-write", [match("PathPrefix", "/api/console")], [request_headers(), response_headers("api")], CONSOLE),
            ],
        ),
        httproute(
            "intake",
            hostname,
            [
                rule(
                    "intake-submit",
                    [match("Exact", intake_path, "POST")],
                    [
                        {"type": "URLRewrite", "urlRewrite": {"path": {"type": "ReplaceFullPath", "replaceFullPath": "/v1/intake/applications"}}},
                        request_headers(),
                        response_headers("api"),
                    ],
                    INTAKE,
                )
            ],
        ),
        httproute(
            "promotion",
            hostname,
            [
                rule(
                    "promotion-models",
                    [match("Exact", "/api/promotion/v1/models", "GET", [{"type": "Exact", "name": "state", "value": "aprobado"}])],
                    [
                        {"type": "URLRewrite", "urlRewrite": {"path": {"type": "ReplaceFullPath", "replaceFullPath": "/v1/models"}}},
                        request_headers(),
                        response_headers("api"),
                    ],
                    PROMOTION,
                ),
                rule(
                    "promotion-activation",
                    [match("RegularExpression", "/api/promotion/v1/models/[^/]+/activation", "POST")],
                    [extension_filter("rewrite-promotion-activation"), request_headers(), response_headers("api")],
                    PROMOTION,
                ),
            ],
        ),
        httproute(
            "auth",
            hostname,
            [
                rule("auth-read", auth_matches(read), [response_headers("auth")], KEYCLOAK),
                rule("auth-write", auth_matches(None), [response_headers("auth")], KEYCLOAK),
            ],
        ),
        httproute(
            "grafana",
            hostname,
            [
                rule("grafana-read", with_methods("PathPrefix", "/grafana", read), [response_headers("grafana")], GRAFANA),
                rule("grafana-write", [match("PathPrefix", "/grafana")], [response_headers("grafana")], GRAFANA),
            ],
        ),
        httproute(
            "closed",
            hostname,
            [
                rule("closed-api", [match("PathPrefix", "/api")], [extension_filter("problem-not-found"), response_headers("api")], None),
                rule("closed-auth", [match("PathPrefix", "/auth")], [extension_filter("problem-not-found"), response_headers("auth")], None),
                rule("closed-federate", [match("PathPrefix", "/federate")], [extension_filter("problem-not-found"), response_headers("api")], None),
            ],
        ),
    ]
    if f09:
        routes.append(
            httproute(
                "federate",
                hostname,
                [rule("federate", [match("Exact", "/federate", "GET")], [response_headers("api")], PROMETHEUS)],
            )
        )
    return sorted(routes, key=lambda r: r["metadata"]["name"])


def httproutefilters() -> list[dict[str, Any]]:
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
                        "replaceRegexMatch": {"pattern": "^/api/promotion(/v1/models/[^/]+/activation)$", "substitution": "\\1"},
                    }
                }
            },
        },
    ]


# --- SecurityPolicy ---------------------------------------------------------------------------


def jwt_policy(name: str, hostname: str, claims: list[dict[str, Any]], scopes: list[str] | None) -> dict[str, Any]:
    principal: dict[str, Any] = {"provider": "keycloak", "claims": claims}
    if scopes:
        principal["scopes"] = scopes
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
                        "issuer": f"https://{hostname}/auth/realms/vectra",
                        "remoteJWKS": {
                            "uri": gd.jwks_uri(),
                            "backendRefs": [backend_ref(KEYCLOAK)],
                            "cacheDuration": "300s",
                        },
                        "claimToHeaders": [{"claim": "azp", "header": "x-vectra-azp"}, {"claim": "sub", "header": "x-vectra-sub"}],
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
    return {"name": name, "valueType": "StringArray" if array else "String", "values": values}


def securitypolicies(hostname: str, f09: bool, simulator_azp: str | None) -> list[dict[str, Any]]:
    intake_azp = sorted(["channel"] + ([simulator_azp] if simulator_azp else []))
    policies = [
        jwt_policy(
            "console",
            hostname,
            [claim("azp", ["vectra-console"]), claim("roles", sorted(gd.business_roles()), array=True)],
            None,
        ),
        jwt_policy("intake", hostname, [claim("azp", intake_azp)], ["intake:submit"]),
        jwt_policy(
            "promotion",
            hostname,
            [claim("acr", ["mfa"]), claim("azp", ["promotion-tool"]), claim("roles", ["ingeniero_riesgo"], array=True)],
            ["governance:promotion"],
        ),
    ]
    if f09:
        policies.append(
            {
                "apiVersion": EG_API,
                "kind": "SecurityPolicy",
                "metadata": meta("federate"),
                "spec": {
                    "targetRefs": [route_ref("federate")],
                    "basicAuth": {"users": {"group": "", "kind": "Secret", "name": "federate-basic-auth"}},
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


def overrides(codes: list[int], retry_after: str) -> list[dict[str, Any]]:
    return [override(c, retry_after) for c in sorted(codes)]


def passive(console: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"baseEjectionTime": "30s", "maxEjectionPercent": 50}
    if console:
        out |= {"consecutive5XxErrors": 0, "consecutiveLocalOriginFailures": 5, "splitExternalLocalOriginErrors": True}
    else:
        out["consecutive5XxErrors"] = 5
    return out


def btp(
    route: str,
    rule_name: str | None,
    *,
    timeout: str | None = None,
    retry: bool = False,
    console: bool = False,
    limit: str | None = None,
    codes: list[int],
    retry_after: str,
    outlier: bool = True,
    cookie: bool = False,
) -> dict[str, Any]:
    spec: dict[str, Any] = {"mergeType": "StrategicMerge", "targetRefs": [route_ref(route, rule_name)]}
    if retry:
        spec["retry"] = {"numRetries": 1, "retryOn": {"triggers": ["connect-failure"]}}
        spec["circuitBreaker"] = {"retryBudget": {"percent": {"numerator": 20, "denominator": 100}}}
    if outlier:
        spec["healthCheck"] = {"passive": passive(console)}
    if cookie:
        spec["loadBalancer"] = {
            "type": "ConsistentHash",
            "consistentHash": {
                "type": "Cookie",
                "cookie": {
                    "name": "vectra-spa-route",
                    "ttl": "0s",
                    "attributes": {"HttpOnly": "", "Path": "/", "SameSite": "Strict", "Secure": ""},
                },
            },
        }
    if limit:
        spec["requestBuffer"] = {"limit": limit}
    spec["responseOverride"] = overrides(codes, retry_after)
    if timeout:
        spec["timeout"] = {"http": {"requestTimeout": timeout}}
    return {
        "apiVersion": EG_API,
        "kind": "BackendTrafficPolicy",
        "metadata": meta(rule_name or route),
        "spec": spec,
    }


def rate_limit_rules(simulator_azp: str | None, f09: bool) -> list[dict[str, Any]]:
    n = gd.rate_limit_numbers()
    distinct_sub = {"name": "x-vectra-sub", "type": "Distinct"}
    per_ip = {"type": "Distinct", "value": "0.0.0.0/0"}

    def rl(requests: int, unit: str, selector: dict[str, Any] | None) -> dict[str, Any]:
        out: dict[str, Any] = {"limit": {"requests": requests, "unit": unit}, "shared": True}
        if selector:
            out["clientSelectors"] = [selector]
        return out

    intake_path = {"type": "RegularExpression", "value": "^/api/intake/v1/intake/applications" + QUERY_SUFFIX}
    rules = {
        "auth-login": rl(
            n["auth"],
            "Minute",
            {
                "path": {
                    "type": "RegularExpression",
                    "value": "^/auth/realms/vectra/(protocol/openid-connect/auth|login-actions(/[^?]*)?)" + QUERY_SUFFIX,
                },
                "sourceCIDR": per_ip,
            },
        ),
        "auth-token": rl(
            n["auth"],
            "Minute",
            {
                "path": {"type": "RegularExpression", "value": "^/auth/realms/vectra/protocol/openid-connect/token" + QUERY_SUFFIX},
                "sourceCIDR": per_ip,
            },
        ),
        "console": rl(n["console"], "Second", {"headers": [distinct_sub], "path": {"type": "PathPrefix", "value": "/api/console"}}),
        "global": rl(n["global"], "Second", None),
        "intake-channel": rl(
            n["intake-channel"], "Second", {"headers": [{"name": "x-vectra-azp", "type": "Exact", "value": "channel"}], "path": intake_path}
        ),
        "promotion": rl(n["promotion"], "Second", {"headers": [distinct_sub], "path": {"type": "PathPrefix", "value": "/api/promotion"}}),
    }
    if simulator_azp:
        rules["intake-channel-simulator"] = rl(
            n["intake-channel-simulator"],
            "Second",
            {"headers": [{"name": "x-vectra-azp", "type": "Exact", "value": simulator_azp}], "path": intake_path},
        )
    if f09:
        rules["federate"] = rl(n["federate"], "Second", {"path": {"type": "RegularExpression", "value": "^/federate" + QUERY_SUFFIX}})
    return [rules[k] for k in sorted(rules)]


def backendtrafficpolicies(simulator_azp: str | None, f09: bool) -> list[dict[str, Any]]:
    one, minute = gd.retry_after()["second"], gd.retry_after()["auth"]
    t = gd.timeouts()
    sizes = {k: gd.body_limit(k) for k in gd.route_rows()}
    common = [401, 403, 413, 429, 503]
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
        btp("spa", "spa", cookie=True, codes=[429, 503], retry_after=one),
        btp("console", "console-read", timeout=t["/api/console/**"], retry=True, console=True, limit=sizes["/api/console/**"], codes=common, retry_after=one),
        btp("console", "console-write", timeout=t["/api/console/**"], console=True, limit=sizes["/api/console/**"], codes=common, retry_after=one),
        btp("intake", "intake-submit", timeout=t["/api/intake/**"], limit=sizes["/api/intake/**"], codes=common, retry_after=one),
        btp("promotion", "promotion-models", timeout=t["/api/promotion/**"], retry=True, limit=sizes["/api/promotion/**"], codes=common, retry_after=one),
        btp("promotion", "promotion-activation", timeout=t["/api/promotion/**"], limit=sizes["/api/promotion/**"], codes=common, retry_after=one),
        btp("auth", "auth-read", timeout=t["/auth/**"], retry=True, codes=[429, 503], retry_after=minute),
        btp("auth", "auth-write", timeout=t["/auth/**"], codes=[429, 503], retry_after=minute),
        btp("grafana", "grafana-read", timeout=t["/grafana/**"], retry=True, limit=sizes["/grafana/**"], codes=[413, 429, 503], retry_after=one),
        btp("grafana", "grafana-write", timeout=t["/grafana/**"], limit=sizes["/grafana/**"], codes=[413, 429, 503], retry_after=one),
        btp("closed", None, codes=[429], retry_after=one, outlier=False),
    ]
    if f09:
        policies.append(btp("federate", "federate", codes=[401, 429, 503], retry_after=one))
    return sorted(policies, key=lambda p: p["metadata"]["name"])


def clienttrafficpolicies() -> list[dict[str, Any]]:
    return [
        {
            "apiVersion": EG_API,
            "kind": "ClientTrafficPolicy",
            "metadata": meta("edge-client"),
            "spec": {
                "targetRefs": [gateway_ref()],
                "clientIPDetection": {"xForwardedFor": {"numTrustedHops": 1}},
                "headers": {
                    "earlyRequestHeaders": {"removeOnMatch": [{"type": "Prefix", "value": INTERNAL_PREFIX}]},
                    "lateResponseHeaders": {
                        "remove": ["server"],
                        "removeOnMatch": [{"type": "Prefix", "value": "x-envoy-"}, {"type": "Prefix", "value": INTERNAL_PREFIX}],
                    },
                },
                "path": {"escapedSlashesAction": "UnescapeAndRedirect", "disableMergeSlashes": False},
            },
        }
    ]


def referencegrants(f09: bool) -> list[dict[str, Any]]:
    targets = {"vectra-app": [CONSOLE[0], INTAKE[0], PROMOTION[0]], "vectra-identity": [KEYCLOAK[0]], "vectra-observability": [GRAFANA[0]]}
    if f09:
        targets["vectra-observability"].append(PROMETHEUS[0])
    return [
        {
            "apiVersion": GW_API,
            "kind": "ReferenceGrant",
            "metadata": meta("edge-routes", namespace),
            "spec": {
                "from": [{"group": GATEWAY_GROUP, "kind": "HTTPRoute", "namespace": EDGE_NS}],
                "to": [{"group": "", "kind": "Service", "name": n} for n in sorted(names)],
            },
        }
        for namespace, names in sorted(targets.items())
    ]


def externalsecrets() -> list[dict[str, Any]]:
    return [
        {
            "apiVersion": "external-secrets.io/v1",
            "kind": "ExternalSecret",
            "metadata": meta("federate-basic-auth"),
            "spec": {
                "secretStoreRef": {"name": "vectra-store", "kind": "ClusterSecretStore"},
                "target": {"name": "federate-basic-auth"},
                "data": [{"secretKey": ".htpasswd", "remoteRef": {"key": "identity/federate", "property": ".htpasswd"}}],
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
