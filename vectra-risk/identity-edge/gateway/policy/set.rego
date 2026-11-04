# Lo que exige ver todos los documentos de un entorno juntos: `conftest test --combine --namespace gateway_set` (U02-T09).
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package gateway_set

import rego.v1

documents contains document if {
	some file in input
	is_array(file.contents)
	some document in file.contents
	is_object(document)
}

documents contains document if {
	some file in input
	is_object(file.contents)
	document := file.contents
}

of_kind(kind) := {d | some d in documents; d.kind == kind}

present(kind, name) if {
	some d in documents
	d.kind == kind
	d.metadata.name == name
}

edge_namespace := "vectra-edge"

# Siempre presentes.
required := [
	["HTTPRoute", "spa"], ["HTTPRoute", "console"], ["HTTPRoute", "intake"], ["HTTPRoute", "promotion"],
	["HTTPRoute", "auth"], ["HTTPRoute", "grafana"], ["HTTPRoute", "closed"],
	["HTTPRouteFilter", "problem-not-found"], ["HTTPRouteFilter", "rewrite-promotion-activation"],
	["SecurityPolicy", "console"], ["SecurityPolicy", "intake"], ["SecurityPolicy", "promotion"],
	["BackendTrafficPolicy", "edge-rate-limits"], ["BackendTrafficPolicy", "closed"], ["BackendTrafficPolicy", "spa"],
	["BackendTrafficPolicy", "console-read"], ["BackendTrafficPolicy", "console-write"], ["BackendTrafficPolicy", "intake-submit"],
	["BackendTrafficPolicy", "promotion-models"], ["BackendTrafficPolicy", "promotion-activation"],
	["BackendTrafficPolicy", "auth-rate-limits"],
	["BackendTrafficPolicy", "grafana-read"], ["BackendTrafficPolicy", "grafana-write"],
	["ClientTrafficPolicy", "edge-client"],
	["ReferenceGrant", "edge-routes"],
	["GatewayClass", "envoy-gateway"], ["Gateway", "api-gateway"], ["Certificate", "api-gateway"],
	["EnvoyProxy", "api-gateway"], ["EnvoyPatchPolicy", "auth-fail-closed"],
]  # fmt: skip

# Solo con F09 habilitada.
federate := [
	["HTTPRoute", "federate"], ["SecurityPolicy", "federate"], ["BackendTrafficPolicy", "federate"],
	["ExternalSecret", "federate-basic-auth"],
]  # fmt: skip

allowed := {pair | some pair in array.concat(required, federate)}

# regla: routes-complete
deny contains msg if {
	some pair in required
	not present(pair[0], pair[1])
	msg := sprintf("routes-complete: falta %s %s", pair)
}

# regla: unexpected-document
deny contains msg if {
	some d in documents
	not [d.kind, d.metadata.name] in allowed
	msg := sprintf("unexpected-document: %s %s no es un manifiesto de route-gen", [d.kind, d.metadata.name])
}

# regla: no-retry-unsafe
# P-U2-02: nunca se reintentan POST, PUT ni PATCH; solo las reglas que admiten unicamente GET o HEAD llevan `retry`.
deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.spec.retry
	some ref in btp.spec.targetRefs
	not ref.sectionName
	msg := sprintf("no-retry-unsafe: BackendTrafficPolicy %s reintenta toda la ruta %s", [btp.metadata.name, ref.name])
}

deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.spec.retry
	some ref in btp.spec.targetRefs
	some route in of_kind("HTTPRoute")
	route.metadata.name == ref.name
	some rule in route.spec.rules
	rule.name == ref.sectionName
	some match in rule.matches
	not object.get(match, "method", "") in {"GET", "HEAD"}
	msg := sprintf("no-retry-unsafe: BackendTrafficPolicy %s reintenta la regla %s, que admite otros metodos", [btp.metadata.name, rule.name])
}

# regla: authenticated-has-security-policy
# BR-U2-11: toda ruta autenticada tiene una SecurityPolicy con JWT y autorizacion `Deny` por defecto (o la basic auth de F09).
authenticated(rule) if {
	rule.backendRefs
	some match in rule.matches
	startswith(match.path.value, "/api/")
}

authenticated(rule) if {
	rule.backendRefs
	some match in rule.matches
	match.path.value == "/federate"
}

protected(route_name) if {
	some sp in of_kind("SecurityPolicy")
	some ref in sp.spec.targetRefs
	ref.kind == "HTTPRoute"
	ref.name == route_name
	not ref.sectionName
	count(sp.spec.jwt.providers) > 0
	sp.spec.authorization.defaultAction == "Deny"
}

protected(route_name) if {
	some sp in of_kind("SecurityPolicy")
	some ref in sp.spec.targetRefs
	ref.kind == "HTTPRoute"
	ref.name == route_name
	not ref.sectionName
	sp.spec.basicAuth.users.name
}

deny contains msg if {
	some route in of_kind("HTTPRoute")
	some rule in route.spec.rules
	authenticated(rule)
	not protected(route.metadata.name)
	msg := sprintf("authenticated-has-security-policy: la regla %s de la ruta %s no tiene SecurityPolicy con JWT y Deny por defecto", [rule.name, route.metadata.name])
}

# regla: security-policy-target
deny contains msg if {
	some sp in of_kind("SecurityPolicy")
	some ref in sp.spec.targetRefs
	not present("HTTPRoute", ref.name)
	msg := sprintf("security-policy-target: SecurityPolicy %s apunta a la HTTPRoute %s, que no existe", [sp.metadata.name, ref.name])
}

# regla: every-rule-has-policy
# Cada regla de cada ruta tiene su BackendTrafficPolicy (timeouts, errores `Problem`, y los limites heredados).
covered(route, rule) if {
	some btp in of_kind("BackendTrafficPolicy")
	some ref in btp.spec.targetRefs
	ref.kind == "HTTPRoute"
	ref.name == route.metadata.name
	object.get(ref, "sectionName", rule.name) == rule.name
}

deny contains msg if {
	some route in of_kind("HTTPRoute")
	some rule in route.spec.rules
	not covered(route, rule)
	msg := sprintf("every-rule-has-policy: la regla %s de la ruta %s no tiene BackendTrafficPolicy", [rule.name, route.metadata.name])
}

# regla: closed-prefixes
# BR-U2-10 (V10): `/api`, `/auth` y `/federate` son prefijos cerrados con 404 `Problem` por `directResponse`.
closed_rule(prefix) if {
	some route in of_kind("HTTPRoute")
	route.metadata.name == "closed"
	some rule in route.spec.rules
	not rule.backendRefs
	{[m.path.type, m.path.value] | some m in rule.matches} == {["PathPrefix", prefix]}
	[f | some f in rule.filters; f.type == "ExtensionRef"; f.extensionRef == {"group": "gateway.envoyproxy.io", "kind": "HTTPRouteFilter", "name": "problem-not-found"}] != []
}

deny contains msg if {
	some prefix in ["/api", "/auth", "/federate"]
	not closed_rule(prefix)
	msg := sprintf("closed-prefixes: el prefijo %s no esta cerrado con el 404 Problem", [prefix])
}

deny contains msg if {
	not closed_not_found_override
	msg := "closed-prefixes: la politica closed no reescribe el 404 como Problem con source Local (D-2)"
}

closed_not_found_override if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "closed"
	some o in btp.spec.responseOverride
	o.match.statusCodes == [{"type": "Value", "value": 404}]
	o.source == "Local"
	contains(o.response.body.inline, "%TRACE_ID%")
}

# regla: reference-grants-exact
# INF-U2-10: un ReferenceGrant por namespace de destino, solo para HTTPRoute de vectra-edge y solo hacia los Services usados.
used_services(namespace) := {ref.name |
	some route in of_kind("HTTPRoute")
	some rule in route.spec.rules
	some ref in rule.backendRefs
	ref.namespace == namespace
}

foreign_namespaces := {ref.namespace |
	some route in of_kind("HTTPRoute")
	some rule in route.spec.rules
	some ref in rule.backendRefs
	ref.namespace != edge_namespace
}

deny contains msg if {
	some namespace in foreign_namespaces
	not granted(namespace)
	msg := sprintf("reference-grants-exact: falta el ReferenceGrant de %s", [namespace])
}

granted(namespace) if {
	some g in of_kind("ReferenceGrant")
	g.metadata.namespace == namespace
}

# D-1: el grant de `vectra-identity` admite ademas la SecurityPolicy de vectra-edge (la JWKS), solo hacia `keycloak`.
route_source := {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "namespace": edge_namespace}

policy_source := {"group": "gateway.envoyproxy.io", "kind": "SecurityPolicy", "namespace": edge_namespace}

allowed_sources(namespace) := [route_source, policy_source] if namespace == "vectra-identity"

allowed_sources(namespace) := [route_source] if namespace != "vectra-identity"

deny contains msg if {
	some g in of_kind("ReferenceGrant")
	not g.spec.from == allowed_sources(g.metadata.namespace)
	msg := sprintf("reference-grants-exact: el ReferenceGrant de %s admite %v", [g.metadata.namespace, g.spec.from])
}

deny contains msg if {
	some g in of_kind("ReferenceGrant")
	some target in g.spec.to
	not target == {"group": "", "kind": "Service", "name": target.name}
	msg := sprintf("reference-grants-exact: el ReferenceGrant de %s admite algo que no es un Service por nombre", [g.metadata.namespace])
}

deny contains msg if {
	some g in of_kind("ReferenceGrant")
	names := {t.name | some t in g.spec.to}
	names != used_services(g.metadata.namespace)
	msg := sprintf("reference-grants-exact: el ReferenceGrant de %s admite %v y las rutas usan %v", [g.metadata.namespace, names, used_services(g.metadata.namespace)])
}

# regla: rate-limit-global
# domain-entities §4: limite global de 200 req/s, en un solo contador compartido por todas las rutas.
global_rules := [r |
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "edge-rate-limits"
	some r in btp.spec.rateLimit.global.rules
	not r.clientSelectors
]

deny contains msg if {
	count(global_rules) != 1
	msg := sprintf("rate-limit-global: debia haber una regla global sin selectores y hay %d", [count(global_rules)])
}

deny contains msg if {
	some r in global_rules
	not r.limit == {"requests": 200, "unit": "Second"}
	msg := "rate-limit-global: el limite global debia ser 200 por segundo"
}

# regla: federate-coherence
# V7: con F09 se generan juntas la ruta, su SecurityPolicy con basic auth, su BackendTrafficPolicy y el ExternalSecret.
deny contains msg if {
	present("HTTPRoute", "federate")
	some pair in federate
	not present(pair[0], pair[1])
	msg := sprintf("federate-coherence: F09 tiene la ruta pero falta %s %s", pair)
}

deny contains msg if {
	not present("HTTPRoute", "federate")
	some pair in federate
	present(pair[0], pair[1])
	msg := sprintf("federate-coherence: F09 no tiene la ruta pero hay %s %s", pair)
}

deny contains msg if {
	some sp in of_kind("SecurityPolicy")
	sp.metadata.name == "federate"
	not sp.spec.basicAuth.users == {"group": "", "kind": "Secret", "name": "federate-basic-auth"}
	msg := "federate-coherence: la basic auth de F09 debia leer el Secret federate-basic-auth"
}

deny contains msg if {
	some secret in of_kind("ExternalSecret")
	secret.metadata.name == "federate-basic-auth"
	not secret.spec.data == [{"secretKey": ".htpasswd", "remoteRef": {"key": "identity/federate", "property": ".htpasswd"}}]
	msg := "federate-coherence: el ExternalSecret de F09 debia leer identity/federate, propiedad .htpasswd"
}

# regla: environment-values
# INF-U2-01: el entorno sale del directorio de los archivos (`generated/<env>/`); hostname, issuer y `azp` de intake son los suyos.
hostnames := {"kind": "vectra.localtest.me", "staging": "vectra.staging.banco.internal", "prod": "vectra.banco.internal"}

envs := {parts[count(parts) - 2] |
	some file in input
	parts := split(file.path, "/")
}

deny contains msg if {
	count(envs) != 1
	msg := sprintf("environment-values: los archivos deben estar en un solo directorio de entorno y estan en %v", [envs])
}

deny contains msg if {
	some env in envs
	not hostnames[env]
	msg := sprintf("environment-values: %s no es un entorno conocido", [env])
}

deny contains msg if {
	some env in envs
	some route in of_kind("HTTPRoute")
	not route.spec.hostnames == [hostnames[env]]
	msg := sprintf("environment-values: la ruta %s de %s debia tener el hostname %s", [route.metadata.name, env, hostnames[env]])
}

deny contains msg if {
	some env in envs
	some sp in of_kind("SecurityPolicy")
	some provider in sp.spec.jwt.providers
	not provider.issuer == sprintf("https://%s/auth/realms/vectra", [hostnames[env]])
	msg := sprintf("environment-values: la SecurityPolicy %s de %s tiene el issuer %s", [sp.metadata.name, env, provider.issuer])
}

simulator_in_intake if {
	some sp in of_kind("SecurityPolicy")
	sp.metadata.name == "intake"
	some claim in sp.spec.authorization.rules[_].principal.jwt.claims
	claim.name == "azp"
	"channel-simulator" in claim.values
}

simulator_rule if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "edge-rate-limits"
	some r in btp.spec.rateLimit.global.rules
	some s in r.clientSelectors
	some h in s.headers
	h.value == "channel-simulator"
}

deny contains msg if {
	"prod" in envs
	simulator_in_intake
	msg := "environment-values: produccion autoriza el azp channel-simulator"
}

deny contains msg if {
	"prod" in envs
	simulator_rule
	msg := "environment-values: produccion tiene el limite de channel-simulator"
}

deny contains msg if {
	some env in envs
	env != "prod"
	not simulator_in_intake
	msg := sprintf("environment-values: %s no autoriza el azp channel-simulator", [env])
}

deny contains msg if {
	some env in envs
	env != "prod"
	not simulator_rule
	msg := sprintf("environment-values: %s no tiene el limite de channel-simulator", [env])
}

# regla: environment-issuer
# INF-U2-01, NFR-U2-22: el ClusterIssuer del Certificate y el hostname del Gateway y del Certificate son los del entorno;
# staging y prod nunca usan el de kind. La imagen de Envoy es el espejo del entorno (W4).
issuers := {"kind": "vectra-internal-ca", "staging": "banco-ca", "prod": "banco-ca"}

images := {
	"kind": "kind-registry:5000/vectra/envoy",
	"staging": "registro.banco.internal/vectra/envoy",
	"prod": "registro.banco.internal/vectra/envoy",
}

deny contains msg if {
	some env in envs
	some cert in of_kind("Certificate")
	not cert.spec.issuerRef.name == issuers[env]
	msg := sprintf("environment-issuer: el Certificate de %s usa el issuer %s y debia ser %s", [env, cert.spec.issuerRef.name, issuers[env]])
}

deny contains msg if {
	some env in envs
	some cert in of_kind("Certificate")
	not cert.spec.dnsNames == [hostnames[env]]
	msg := sprintf("environment-issuer: el Certificate de %s debia emitirse para %s", [env, hostnames[env]])
}

deny contains msg if {
	some env in envs
	some gateway in of_kind("Gateway")
	some listener in gateway.spec.listeners
	not listener.hostname == hostnames[env]
	msg := sprintf("environment-issuer: el listener del Gateway de %s debia tener el hostname %s", [env, hostnames[env]])
}

deny contains msg if {
	some env in envs
	some proxy in of_kind("EnvoyProxy")
	image := proxy.spec.provider.kubernetes.envoyDeployment.container.image
	not image == sprintf("%s@%s", [images[env], data.main.envoy_digest])
	msg := sprintf("environment-issuer: el EnvoyProxy de %s usa la imagen %s", [env, image])
}

# regla: gateway-wiring
# El Gateway usa la GatewayClass que existe, la GatewayClass apunta al EnvoyProxy que existe, y el listener lee el Secret que escribe el Certificate.
deny contains msg if {
	some gateway in of_kind("Gateway")
	not present("GatewayClass", gateway.spec.gatewayClassName)
	msg := sprintf("gateway-wiring: el Gateway %s usa la GatewayClass %s, que no existe", [gateway.metadata.name, gateway.spec.gatewayClassName])
}

deny contains msg if {
	some class in of_kind("GatewayClass")
	not present("EnvoyProxy", class.spec.parametersRef.name)
	msg := sprintf("gateway-wiring: la GatewayClass %s apunta al EnvoyProxy %s, que no existe", [class.metadata.name, class.spec.parametersRef.name])
}

deny contains msg if {
	some gateway in of_kind("Gateway")
	some listener in gateway.spec.listeners
	some ref in listener.tls.certificateRefs
	secrets := {c.spec.secretName | some c in of_kind("Certificate")}
	not ref.name in secrets
	msg := sprintf("gateway-wiring: el listener %s lee el Secret %s, que ningun Certificate escribe", [listener.name, ref.name])
}

deny contains msg if {
	some route in of_kind("HTTPRoute")
	some parent in route.spec.parentRefs
	not present("Gateway", parent.name)
	msg := sprintf("gateway-wiring: la HTTPRoute %s cuelga del Gateway %s, que no existe", [route.metadata.name, parent.name])
}

# regla: auth-rate-limit-isolated
# P-U2-01 (X1): los dos contadores por IP de `/auth/**` van solos en la politica de ruta de la unica regla de `/auth/**`, sin
# reintentos; ninguna otra politica los lleva, y `edge-rate-limits` conserva el resto (el limite global falla abierto).
has_ip_counter(rule) if {
	some s in rule.clientSelectors
	s.sourceCIDR
}

policies_with_ip_counters := {btp.metadata.name |
	some btp in of_kind("BackendTrafficPolicy")
	some rule in btp.spec.rateLimit.global.rules
	has_ip_counter(rule)
}

deny contains msg if {
	policies_with_ip_counters != {"auth-rate-limits"}
	msg := sprintf("auth-rate-limit-isolated: los contadores por IP deben estar solo en auth-rate-limits y estan en %v", [policies_with_ip_counters])
}

deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "auth-rate-limits"
	not btp.spec.targetRefs == [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "auth", "sectionName": "auth-rate-limits"}]
	msg := "auth-rate-limit-isolated: auth-rate-limits debia apuntar a la unica regla de la ruta auth"
}

deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "auth-rate-limits"
	count(btp.spec.rateLimit.global.rules) != 4
	msg := "auth-rate-limit-isolated: auth-rate-limits debia tener los dos contadores por familia de direcciones"
}

deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name == "auth-rate-limits"
	btp.spec.retry
	msg := "auth-rate-limit-isolated: /auth/** no reintenta"
}

deny contains msg if {
	some route in of_kind("HTTPRoute")
	route.metadata.name == "auth"
	count(route.spec.rules) != 1
	msg := "auth-rate-limit-isolated: la ruta auth debia tener una sola regla"
}

deny contains msg if {
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name != "edge-rate-limits"
	btp.metadata.name != "auth-rate-limits"
	btp.spec.rateLimit
	msg := sprintf("auth-rate-limit-isolated: %s declara un rateLimit y solo edge-rate-limits y auth-rate-limits lo hacen", [btp.metadata.name])
}

# regla: fail-closed-domain
# El filtro que la EnvoyPatchPolicy pone en fail-closed es el del dominio `<namespace>/<politica>` de la politica con los contadores
# de `/auth/**`, y ningun otro.
deny contains msg if {
	some patch_policy in of_kind("EnvoyPatchPolicy")
	some patch in patch_policy.spec.jsonPatches
	some btp in of_kind("BackendTrafficPolicy")
	btp.metadata.name in policies_with_ip_counters
	want := sprintf("..http_filters[?(@.name=='envoy.filters.http.ratelimit/%s/%s')].typed_config", [btp.metadata.namespace, btp.metadata.name])
	not patch.operation.jsonPath == want
	msg := sprintf("fail-closed-domain: el parche apunta a %s y el dominio de los contadores de /auth/** es %s", [patch.operation.jsonPath, want])
}
