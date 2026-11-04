# Reglas de conftest sobre lo que `route_gen.py` genera (U02-T09, Paso 7 del plan de U2): una pasada por documento.
# Son listas blancas y comparaciones exactas contra el diseno (BR-U2-08, 10, 11, 13, 14; P-U2-02, 03, 06; INF-U2-10).
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_route_gen.py, y cada mensaje empieza por `x:`.
# Lo que exige ver varios documentos juntos esta en `set.rego` (`--combine --namespace gateway_set`).
package main

import rego.v1

edge_namespace := "vectra-edge"

app_headers := {"idempotency-key", "x-test-scenario"}

public_hostnames := {"vectra.localtest.me", "vectra.staging.banco.internal", "vectra.banco.internal"}

jwks_uri := "https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/certs"

problem_content_type := "application/problem+json"

internal_headers := {"x-vectra-sub", "x-vectra-azp"}

# domain-entities §4.1, perfiles `spa` y `api`: el texto exacto.
page_csp_text := "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types 'none'"

common_headers := {
	"Strict-Transport-Security": "max-age=31536000; includeSubDomains",
	"X-Content-Type-Options": "nosniff",
	"Referrer-Policy": "no-referrer",
	"Cross-Origin-Opener-Policy": "same-origin",
}

cookie_affinity := {
	"name": "vectra-spa-route",
	"ttl": "0s",
	"attributes": {"Secure": "", "HttpOnly": "", "SameSite": "Strict", "Path": "/"},
}

label(doc) := sprintf("%s %s", [doc.kind, doc.metadata.name])

# regla: no-app-headers
# `Idempotency-Key` y `X-Test-Scenario` pasan intactas (P-U2-06): ningun manifiesto las menciona.
deny contains msg if {
	walk(input, [_, value])
	is_string(value)
	lower(value) in app_headers
	msg := sprintf("no-app-headers: %s menciona %s", [label(input), value])
}

problem_responses contains response if {
	input.kind == "HTTPRouteFilter"
	direct := input.spec.directResponse
	response := {"status": direct.statusCode, "contentType": direct.contentType, "body": direct.body.inline}
}

problem_responses contains response if {
	input.kind == "BackendTrafficPolicy"
	some override in input.spec.responseOverride
	response := {
		"status": override.match.statusCodes[0].value,
		"contentType": override.response.contentType,
		"body": override.response.body.inline,
	}
}

valid_problem(response) if {
	body := json.unmarshal(response.body)
	object.keys(body) == {"type", "title", "status", "code", "correlation_id"}
	body.status == response.status
	body.correlation_id == "%TRACE_ID%"
	body.type == concat("", ["urn:vectra:problem:", body.code])
}

# regla: problem-body
# BR-U2-14: `Problem` generico con `correlation_id` (el trace-id) y sin mas campos.
deny contains msg if {
	some response in problem_responses
	response.contentType != problem_content_type
	msg := sprintf("problem-body: %s responde %d con content-type %s", [label(input), response.status, response.contentType])
}

deny contains msg if {
	some response in problem_responses
	not valid_problem(response)
	msg := sprintf("problem-body: %s responde %d con un cuerpo que no es un Problem con %%TRACE_ID%%", [label(input), response.status])
}

# regla: jwt-deny-by-default
# BR-U2-11: autorizacion con `defaultAction: Deny` y al menos una regla `Allow` de un proveedor declarado.
deny contains msg if {
	input.kind == "SecurityPolicy"
	input.spec.jwt
	not input.spec.authorization.defaultAction == "Deny"
	msg := sprintf("jwt-deny-by-default: %s no deniega por defecto", [label(input)])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	input.spec.jwt
	providers := {p.name | some p in input.spec.jwt.providers}
	allows := [r | some r in input.spec.authorization.rules; r.action == "Allow"; r.principal.jwt.provider in providers]
	count(allows) == 0
	msg := sprintf("jwt-deny-by-default: %s no tiene una regla Allow de un proveedor declarado", [label(input)])
}

# regla: jwks-internal
# P-U2-03, INF-U2-10: la JWKS por la URL interna de Keycloak, refresco de 5 min, y `sub`/`azp` copiados a cabeceras internas.
deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	provider.remoteJWKS.uri != jwks_uri
	msg := sprintf("jwks-internal: %s pide la JWKS a %s", [label(input), provider.remoteJWKS.uri])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	provider.remoteJWKS.backendRefs != [{"group": "", "kind": "Service", "name": "keycloak", "namespace": "vectra-identity", "port": 8443}]
	msg := sprintf("jwks-internal: %s no usa el Service keycloak:8443 de vectra-identity", [label(input)])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	provider.remoteJWKS.cacheDuration != "300s"
	msg := sprintf("jwks-internal: %s refresca la JWKS cada %s", [label(input), provider.remoteJWKS.cacheDuration])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	{[c.claim, c.header] | some c in provider.claimToHeaders} != {["sub", "x-vectra-sub"], ["azp", "x-vectra-azp"]}
	msg := sprintf("jwks-internal: %s no copia sub y azp a x-vectra-sub y x-vectra-azp", [label(input)])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	not endswith(provider.issuer, "/auth/realms/vectra")
	msg := sprintf("jwks-internal: %s con el issuer %s", [label(input), provider.issuer])
}

deny contains msg if {
	input.kind == "SecurityPolicy"
	some provider in input.spec.jwt.providers
	hostnames := {sprintf("https://%s/auth/realms/vectra", [h]) | some h in public_hostnames}
	not provider.issuer in hostnames
	msg := sprintf("jwks-internal: %s con el issuer %s, que no es el del hostname publico", [label(input), provider.issuer])
}

# regla: shared-rate-limits
# P-U2-06, NFR-U2-20: limites globales (con el servicio de rate limit), todos `shared` para que cuenten en un solo lugar.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	input.spec.rateLimit
	input.spec.rateLimit.type != "Global"
	msg := sprintf("shared-rate-limits: %s no es de tipo Global", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	some rule in input.spec.rateLimit.global.rules
	not rule.shared == true
	msg := sprintf("shared-rate-limits: %s tiene una regla que no es shared", [label(input)])
}

# regla: merge-with-gateway
# Las politicas por regla heredan los limites de la politica del Gateway (`mergeType`); sin eso los pierden.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	some ref in input.spec.targetRefs
	ref.kind == "HTTPRoute"
	not input.spec.mergeType == "StrategicMerge"
	msg := sprintf("merge-with-gateway: %s no hereda la politica del Gateway", [label(input)])
}

# regla: client-policy
# NFR-U2-23, P-U2-06, BR-U2-10, BR-U2-14.
deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.clientIPDetection.xForwardedFor == {"numTrustedHops": 1}
	msg := sprintf("client-policy: %s no confia en X-Forwarded-For de 1 salto", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.headers.earlyRequestHeaders == {"removeOnMatch": [{"type": "Prefix", "value": "x-vectra-"}]}
	msg := sprintf("client-policy: %s no quita x-vectra- de la request antes del filtro JWT", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.headers.lateResponseHeaders.remove == ["server"]
	msg := sprintf("client-policy: %s no quita server de la respuesta", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.headers.lateResponseHeaders.removeOnMatch == [{"type": "Prefix", "value": "x-envoy-"}, {"type": "Prefix", "value": "x-vectra-"}]
	msg := sprintf("client-policy: %s no quita x-envoy- ni x-vectra- de la respuesta", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	input.spec.headers.enableEnvoyHeaders
	msg := sprintf("client-policy: %s activa las cabeceras x-envoy-", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.path == {"escapedSlashesAction": "UnescapeAndRedirect", "disableMergeSlashes": false}
	msg := sprintf("client-policy: %s no fija UnescapeAndRedirect y la fusion de barras", [label(input)])
}

# regla: cookie-affinity
# V6: cookie de sesion `vectra-spa-route`.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	input.spec.loadBalancer
	not input.spec.loadBalancer.type == "ConsistentHash"
	msg := sprintf("cookie-affinity: %s no usa ConsistentHash", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	input.spec.loadBalancer
	not input.spec.loadBalancer.consistentHash == {"type": "Cookie", "cookie": cookie_affinity}
	msg := sprintf("cookie-affinity: %s no usa la cookie %s de sesion con Secure, HttpOnly, SameSite=Strict y Path=/", [label(input), cookie_affinity.name])
}

# regla: outlier
# P-U2-02: 5 errores 5xx consecutivos, expulsion de 30 s, hasta el 50 % de los pods.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	passive := input.spec.healthCheck.passive
	not passive.baseEjectionTime == "30s"
	msg := sprintf("outlier: %s expulsa por %s y debia ser 30s", [label(input), passive.baseEjectionTime])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	passive := input.spec.healthCheck.passive
	not passive.maxEjectionPercent == 50
	msg := sprintf("outlier: %s expulsa hasta el %v %% y debia ser 50", [label(input), passive.maxEjectionPercent])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	passive := input.spec.healthCheck.passive
	not is_console(input)
	not passive.consecutive5XxErrors == 5
	msg := sprintf("outlier: %s no expulsa tras 5 errores 5xx consecutivos", [label(input)])
}

is_console(btp) if btp.spec.targetRefs[0].name == "console"

# regla: console-no-5xx-ejection
# P-U2-02 (cuarta revision de coherencia): en `/api/console/**` cuentan solo los errores de conexion.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	is_console(input)
	not input.spec.healthCheck.passive
	msg := sprintf("console-no-5xx-ejection: %s no tiene outlier detection", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	is_console(input)
	passive := input.spec.healthCheck.passive
	not passive.consecutive5XxErrors == 0
	msg := sprintf("console-no-5xx-ejection: %s expulsa por errores 5xx", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	is_console(input)
	passive := input.spec.healthCheck.passive
	not passive.splitExternalLocalOriginErrors == true
	msg := sprintf("console-no-5xx-ejection: %s no separa los errores de origen local", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	is_console(input)
	passive := input.spec.healthCheck.passive
	not passive.consecutiveLocalOriginFailures == 5
	msg := sprintf("console-no-5xx-ejection: %s no expulsa tras 5 errores de conexion", [label(input)])
}

# regla: route-parent
# INF-U2-10 (V9): las HTTPRoute van en vectra-edge y cuelgan del listener `https` de `api-gateway`.
deny contains msg if {
	input.kind == "HTTPRoute"
	input.metadata.namespace != edge_namespace
	msg := sprintf("route-parent: %s esta en %s y debia estar en %s", [label(input), input.metadata.namespace, edge_namespace])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	not input.spec.parentRefs == [{"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": "api-gateway", "namespace": edge_namespace, "sectionName": "https"}]
	msg := sprintf("route-parent: %s no cuelga solo del listener https de api-gateway", [label(input)])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	count(input.spec.hostnames) != 1
	msg := sprintf("route-parent: %s debia tener un solo hostname", [label(input)])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some hostname in input.spec.hostnames
	not hostname in public_hostnames
	msg := sprintf("route-parent: %s con el hostname %s", [label(input), hostname])
}

# --- perfiles de cabeceras (BR-U2-13) -----------------------------------------------------------

response_modifiers(rule) := [f.responseHeaderModifier | some f in rule.filters; f.type == "ResponseHeaderModifier"]

header_values(rule, name) := [h.value |
	some modifier in response_modifiers(rule)
	some h in array.concat(object.get(modifier, "set", []), object.get(modifier, "add", []))
	h.name == name
]

profile_of(rule) := "grafana" if {
	path := rule.matches[0].path.value
	path_under(path, "/grafana")
}

profile_of(rule) := "auth" if {
	path := rule.matches[0].path.value
	path_under(path, "/auth")
}

profile_of(rule) := "page" if {
	path := rule.matches[0].path.value
	not path_under(path, "/grafana")
	not path_under(path, "/auth")
}

path_under(path, prefix) if path == prefix

path_under(path, prefix) if startswith(path, concat("", [prefix, "/"]))

# regla: profile-headers
# domain-entities §4.1: cada regla lleva su perfil, y todas el comun (con `Cross-Origin-Opener-Policy: same-origin`).
deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	count(response_modifiers(rule)) != 1
	msg := sprintf("profile-headers: %s, regla %s: debia tener un solo ResponseHeaderModifier", [label(input), rule.name])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	some name, value in common_headers
	not header_values(rule, name) == [value]
	msg := sprintf("profile-headers: %s, regla %s: %s debia ser %s", [label(input), rule.name, name, value])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "page"
	not header_values(rule, "X-Frame-Options") == ["DENY"]
	msg := sprintf("profile-headers: %s, regla %s: X-Frame-Options debia ser DENY", [label(input), rule.name])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "page"
	csp := header_values(rule, "Content-Security-Policy")
	not page_csp(csp)
	msg := sprintf("profile-headers: %s, regla %s: la CSP debia ser una sola y la de domain-entities §4.1", [label(input), rule.name])
}

page_csp(csp) if csp == [page_csp_text]

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "grafana"
	not header_values(rule, "X-Frame-Options") == ["SAMEORIGIN"]
	msg := sprintf("profile-headers: %s, regla %s: X-Frame-Options debia ser SAMEORIGIN", [label(input), rule.name])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "grafana"
	not header_values(rule, "Content-Security-Policy") == ["frame-ancestors 'self'"]
	msg := sprintf("profile-headers: %s, regla %s: la CSP de grafana debia ser frame-ancestors 'self'", [label(input), rule.name])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "auth"
	not header_values(rule, "Content-Security-Policy") == ["frame-ancestors 'self'"]
	msg := sprintf("profile-headers: %s, regla %s: auth debia agregar frame-ancestors 'self'", [label(input), rule.name])
}

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	profile_of(rule) == "auth"
	count(header_values(rule, "X-Frame-Options")) != 0
	msg := sprintf("profile-headers: %s, regla %s: auth conserva el X-Frame-Options de Keycloak", [label(input), rule.name])
}

# regla: internal-headers-removed
# P-U2-06: cada regla autenticada quita `x-vectra-sub` y `x-vectra-azp` antes de enviar al backend.
authenticated(rule) if {
	rule.backendRefs
	some match in rule.matches
	startswith(match.path.value, "/api/")
}

request_modifiers(rule) := [f.requestHeaderModifier | some f in rule.filters; f.type == "RequestHeaderModifier"]

deny contains msg if {
	input.kind == "HTTPRoute"
	some rule in input.spec.rules
	authenticated(rule)
	mods := request_modifiers(rule)
	not removes_internal(mods)
	msg := sprintf("internal-headers-removed: %s, regla %s: no quita x-vectra-sub y x-vectra-azp hacia el backend", [label(input), rule.name])
}

removes_internal(mods) if {
	count(mods) == 1
	{h | some h in mods[0].remove} == internal_headers
}

# regla: closed-no-rate-limit
# D-6 (BR-U2-10): en Envoy Gateway v1.9.3 el rate limit no se aplica a las rutas `directResponse`; la politica del cierre
# no declara 429 ni ningun `rateLimit`.
deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	input.metadata.name == "closed"
	input.spec.rateLimit
	msg := sprintf("closed-no-rate-limit: %s declara rateLimit", [label(input)])
}

deny contains msg if {
	input.kind == "BackendTrafficPolicy"
	input.metadata.name == "closed"
	some override in input.spec.responseOverride
	429 in {code | some code in [c | some m in override.match.statusCodes; c := m.value]}
	msg := sprintf("closed-no-rate-limit: %s declara un 429", [label(input)])
}
