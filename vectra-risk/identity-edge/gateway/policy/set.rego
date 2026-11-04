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
	["BackendTrafficPolicy", "auth-read"], ["BackendTrafficPolicy", "auth-write"],
	["BackendTrafficPolicy", "grafana-read"], ["BackendTrafficPolicy", "grafana-write"],
	["ClientTrafficPolicy", "edge-client"],
	["ReferenceGrant", "edge-routes"],
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

deny contains msg if {
	some g in of_kind("ReferenceGrant")
	not g.spec.from == [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "namespace": edge_namespace}]
	msg := sprintf("reference-grants-exact: el ReferenceGrant de %s admite algo mas que HTTPRoute de vectra-edge", [g.metadata.namespace])
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
