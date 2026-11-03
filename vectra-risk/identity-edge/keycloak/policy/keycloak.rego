# Reglas de conftest sobre lo que `render-keycloak` produce (U02-T07, Paso 5 del plan de U2).
# Son listas blancas y comparaciones exactas contra el diseno (INF-U2-01, 05a, 05b, 06, 08; NFR-U2-02, 26).
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_keycloak_deploy.py, y cada mensaje empieza por `x:`.
# Lo que exige ver varios documentos juntos esta en `set.rego` (`--combine --namespace keycloak_set`).
package main

import rego.v1

namespace := "vectra-identity"

public_hostnames := {
	"https://vectra.localtest.me/auth",
	"https://vectra.staging.banco.internal/auth",
	"https://vectra.banco.internal/auth",
}

admin_hostname := "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth"

image_repositories := {"registro.banco.internal/vectra/keycloak", "kind-registry:5000/vectra/keycloak"}

# Variables con valor fijo. Las demas (KC_HOSTNAME y las que vienen de un Secret) se comprueban aparte.
fixed_env := {
	"KC_HTTP_RELATIVE_PATH": "/auth",
	"KC_CACHE": "ispn",
	"KC_CACHE_STACK": "jdbc-ping",
	"KC_PROXY_HEADERS": "xforwarded",
	"KC_DB": "postgres",
	"KC_DB_URL_HOST": "keycloak-db-rw.vectra-data.svc",
	"KC_DB_URL_PORT": "5432",
	"KC_DB_URL_DATABASE": "keycloak",
	"KC_DB_URL_PROPERTIES": "?sslmode=verify-full&sslrootcert=/etc/vectra/ca/ca.crt",
	"KC_DB_POOL_MAX_SIZE": "20",
	"KC_METRICS_ENABLED": "true",
	"KC_HEALTH_ENABLED": "true",
	"KC_HOSTNAME_ADMIN": admin_hostname,
	"KC_HTTPS_CERTIFICATE_FILE": "/etc/x509/https/tls.crt",
	"KC_HTTPS_CERTIFICATE_KEY_FILE": "/etc/x509/https/tls.key",
	"JAVA_OPTS_APPEND": "-XX:MaxRAMPercentage=70",
}

secret_env := {
	"KC_DB_USERNAME": {"name": "pg-role-keycloak", "key": "username"},
	"KC_DB_PASSWORD": {"name": "pg-role-keycloak", "key": "password"},
}

env_names := (({"KC_HOSTNAME"} | {n | some n, _ in fixed_env}) | {n | some n, _ in secret_env})

# Cada ExternalSecret de U2 con la clave de la boveda que lee (INF-U2-01, enmienda Q4).
vault_entries := {
	"identity-ca": {"key": "identity/ca", "property": "ca.crt", "secretKey": "ca.crt"},
	"keycloak-config-cli-client": {"key": "identity/clients/keycloak-config-cli", "property": "private-key", "secretKey": "private-key"},
	"keycloak-reader-client": {"key": "identity/clients/keycloak-reader", "property": "private-key", "secretKey": "private-key"},
}

is_keycloak_statefulset if {
	input.kind == "StatefulSet"
	input.metadata.name == "keycloak"
}

# El unico contenedor de la plantilla.
container := input.spec.template.spec.containers[0] if is_keycloak_statefulset

env_of(name) := value if {
	some e in container.env
	e.name == name
	value := e.value
}

# regla: statefulset-shape
deny contains msg if {
	is_keycloak_statefulset
	not count(input.spec.template.spec.containers) == 1
	msg := "statefulset-shape: Keycloak lleva un solo contenedor"
}

deny contains msg if {
	is_keycloak_statefulset
	input.metadata.namespace != namespace
	msg := sprintf("statefulset-shape: el namespace es %s, no %s", [input.metadata.namespace, namespace])
}

# regla: replicas
# Con HPA el StatefulSet no fija `replicas`; si lo fija, son 2 (NFR-U2-01).
deny contains msg if {
	is_keycloak_statefulset
	"replicas" in object.keys(input.spec)
	input.spec.replicas != 2
	msg := sprintf("replicas: %v replicas, no 2", [input.spec.replicas])
}

# regla: hpa
deny contains msg if {
	some problem in hpa_problem
	msg := sprintf("hpa: %s", [problem])
}

is_keycloak_hpa if {
	input.kind == "HorizontalPodAutoscaler"
	input.metadata.name == "keycloak"
}

hpa_problem contains "minReplicas distinto de 2" if {
	is_keycloak_hpa
	object.get(input.spec, "minReplicas", 0) != 2
}

hpa_problem contains "maxReplicas distinto de 4" if {
	is_keycloak_hpa
	object.get(input.spec, "maxReplicas", 0) != 4
}

hpa_problem contains "no apunta al StatefulSet keycloak" if {
	is_keycloak_hpa
	object.get(input.spec, "scaleTargetRef", {}) != {"apiVersion": "apps/v1", "kind": "StatefulSet", "name": "keycloak"}
}

hpa_problem contains "las metricas son exactamente una: CPU, utilizacion del 70 %" if {
	is_keycloak_hpa
	not hpa_cpu_only
}

hpa_cpu_only if {
	count(input.spec.metrics) == 1
	input.spec.metrics[0].type == "Resource"
	input.spec.metrics[0].resource.name == "cpu"
	input.spec.metrics[0].resource.target.type == "Utilization"
	input.spec.metrics[0].resource.target.averageUtilization == 70
}

# regla: zone-spread
deny contains msg if {
	is_keycloak_statefulset
	not zone_spread
	msg := "zone-spread: una restriccion de reparto por topology.kubernetes.io/zone, maxSkew 1, DoNotSchedule, sobre los pods de Keycloak"
}

zone_spread if {
	constraints := input.spec.template.spec.topologySpreadConstraints
	count(constraints) == 1
	constraints[0].topologyKey == "topology.kubernetes.io/zone"
	constraints[0].maxSkew == 1
	constraints[0].whenUnsatisfiable == "DoNotSchedule"
	constraints[0].labelSelector.matchLabels == input.spec.selector.matchLabels
}

# regla: pdb
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.metadata.name == "keycloak"
	not pdb_ok
	msg := "pdb: minAvailable 1 (sin maxUnavailable) sobre los pods de Keycloak"
}

pdb_ok if {
	input.spec.minAvailable == 1
	object.keys(input.spec) == {"minAvailable", "selector"}
	input.spec.selector.matchLabels["app.kubernetes.io/name"] == "keycloak"
	input.spec.selector.matchLabels["app.kubernetes.io/instance"] == "keycloak"
	count(input.spec.selector.matchLabels) == 2
}

# regla: start-optimized
deny contains msg if {
	is_keycloak_statefulset
	object.get(container, "args", []) != ["start", "--optimized"]
	msg := "start-optimized: args debe ser exactamente [start, --optimized] (NFR-U2-26)"
}

deny contains msg if {
	is_keycloak_statefulset
	"command" in object.keys(container)
	msg := "start-optimized: sin command: el ENTRYPOINT de la imagen es kc.sh"
}

# regla: env-whitelist
deny contains msg if {
	is_keycloak_statefulset
	names := {e.name | some e in container.env}
	extra := names - env_names
	count(extra) > 0
	msg := sprintf("env-whitelist: variables fuera de la lista blanca: %v", [sort(extra)])
}

deny contains msg if {
	is_keycloak_statefulset
	names := {e.name | some e in container.env}
	missing := env_names - names
	count(missing) > 0
	msg := sprintf("env-whitelist: faltan variables: %v", [sort(missing)])
}

deny contains msg if {
	is_keycloak_statefulset
	count(container.env) != count({e.name | some e in container.env})
	msg := "env-whitelist: variable repetida"
}

deny contains msg if {
	is_keycloak_statefulset
	envfrom := object.get(container, "envFrom", null)
	envfrom != null
	envfrom != []
	msg := "env-whitelist: sin envFrom"
}

deny contains msg if {
	is_keycloak_statefulset
	some name, expected in fixed_env
	env_of(name) != expected
	msg := sprintf("env-whitelist: %s debe valer %s", [name, expected])
}

# Cada variable es exactamente {name, value}; las que el diseno lleva a un Secret, exactamente {name, valueFrom}.
deny contains msg if {
	is_keycloak_statefulset
	some e in container.env
	not env_shape_ok(e)
	msg := sprintf("env-whitelist: %s debe ser exactamente {name, value} (o {name, valueFrom} si viene de un Secret)", [e.name])
}

env_shape_ok(e) if {
	not e.name in object.keys(secret_env)
	object.keys(e) == {"name", "value"}
	is_string(e.value)
}

env_shape_ok(e) if {
	e.name in object.keys(secret_env)
	object.keys(e) == {"name", "valueFrom"}
}

# regla: cache-stack
deny contains msg if {
	is_keycloak_statefulset
	env_of("KC_CACHE_STACK") != "jdbc-ping"
	msg := "cache-stack: KC_CACHE_STACK debe ser jdbc-ping"
}

deny contains msg if {
	is_keycloak_statefulset
	not "KC_CACHE_STACK" in {e.name | some e in container.env}
	msg := "cache-stack: falta KC_CACHE_STACK"
}

# regla: proxy-headers
deny contains msg if {
	is_keycloak_statefulset
	env_of("KC_PROXY_HEADERS") != "xforwarded"
	msg := "proxy-headers: KC_PROXY_HEADERS debe ser xforwarded"
}

deny contains msg if {
	is_keycloak_statefulset
	not "KC_PROXY_HEADERS" in {e.name | some e in container.env}
	msg := "proxy-headers: falta KC_PROXY_HEADERS"
}

# regla: hostname
deny contains msg if {
	is_keycloak_statefulset
	not env_of("KC_HOSTNAME") in public_hostnames
	msg := "hostname: KC_HOSTNAME debe ser el hostname publico de INF-U2-01 con el path /auth"
}

# regla: hostname-admin
deny contains msg if {
	is_keycloak_statefulset
	env_of("KC_HOSTNAME_ADMIN") != admin_hostname
	msg := sprintf("hostname-admin: KC_HOSTNAME_ADMIN debe ser %s (interno, fuera del gateway)", [admin_hostname])
}

deny contains msg if {
	is_keycloak_statefulset
	env_of("KC_HOSTNAME_ADMIN") == env_of("KC_HOSTNAME")
	msg := "hostname-admin: no puede ser el publico"
}

# regla: persistent-sessions
# NFR-U2-02: `persistent-user-sessions` esta activa por defecto en 26.8.1 y no se toca.
deny contains msg if {
	is_keycloak_statefulset
	some e in container.env
	e.name in {"KC_FEATURES", "KC_FEATURES_DISABLED"}
	msg := sprintf("persistent-sessions: %s no puede definirse", [e.name])
}

deny contains msg if {
	is_keycloak_statefulset
	some arg in object.get(container, "args", [])
	startswith(arg, "--features")
	msg := sprintf("persistent-sessions: el argumento %s no puede pasarse", [arg])
}

# regla: probes
deny contains msg if {
	is_keycloak_statefulset
	some probe in ["livenessProbe", "readinessProbe"]
	not probe_on_management_port(probe)
	msg := sprintf("probes: %s debe ser un httpGet al puerto de gestion 9000", [probe])
}

probe_on_management_port(probe) if {
	port := container[probe].httpGet.port
	some declared in container.ports
	declared.name == port
	declared.containerPort == 9000
}

probe_on_management_port(probe) if {
	container[probe].httpGet.port == 9000
}

# regla: resources
deny contains msg if {
	is_keycloak_statefulset
	container.resources != {"requests": {"cpu": "500m", "memory": "1Gi"}, "limits": {"cpu": "2", "memory": "2Gi"}}
	msg := "resources: INF-U2-06 fija 500m / 1 GiB de requests y 2 CPU / 2 GiB de limits"
}

# regla: priority
deny contains msg if {
	is_keycloak_statefulset
	object.get(input.spec.template.spec, "priorityClassName", "") != "vectra-high"
	msg := "priority: priorityClassName debe ser vectra-high"
}

# regla: criticality
deny contains msg if {
	is_keycloak_statefulset
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "high"
	msg := "criticality: vectra.io/criticality debe ser high (NFR-U1-01)"
}

# regla: image
deny contains msg if {
	is_keycloak_statefulset
	not count(split(container.image, "@")) == 2
	msg := sprintf("image: %s sin digest", [container.image])
}

deny contains msg if {
	is_keycloak_statefulset
	parts := split(container.image, "@")
	count(parts) == 2
	not parts[0] in image_repositories
	msg := sprintf("image: el repositorio %s no es el de INF-U2-08", [parts[0]])
}

deny contains msg if {
	is_keycloak_statefulset
	parts := split(container.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("image: el digest %s no es sha256 de 64 hex", [parts[1]])
}

# regla: db-credentials
# La contrasena de la base y el usuario llegan del Secret `pg-role-keycloak` que entrega U1.
deny contains msg if {
	is_keycloak_statefulset
	some name, expected in secret_env
	not env_from_secret(name, expected)
	msg := sprintf("db-credentials: %s debe salir de secretKeyRef %s/%s", [name, expected.name, expected.key])
}

env_from_secret(name, expected) if {
	some e in container.env
	e.name == name
	e.valueFrom == {"secretKeyRef": {"name": expected.name, "key": expected.key}}
}

# regla: tls-mount
# El certificado `keycloak-tls` se monta; sin el, 8443 no arranca (INF-U2-05b).
deny contains msg if {
	is_keycloak_statefulset
	not tls_volume
	msg := "tls-mount: falta el volumen con el Secret keycloak-tls"
}

tls_volume if {
	some volume in input.spec.template.spec.volumes
	volume.secret.secretName == "keycloak-tls"
}

# regla: no-plain-secret
# Ningun Secret en el render: toda credencial llega por ExternalSecret o por el `pg-role-keycloak` de U1.
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: Secret %s en el render", [input.metadata.name])
}

# regla: external-secret
deny contains msg if {
	input.kind == "ExternalSecret"
	not input.metadata.name in object.keys(vault_entries)
	msg := sprintf("external-secret: %s no es un ExternalSecret de U2", [input.metadata.name])
}

deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name in object.keys(vault_entries)
	not external_secret_ok(input, vault_entries[input.metadata.name])
	msg := sprintf("external-secret: %s no lee exactamente la clave de la boveda de INF-U2-01", [input.metadata.name])
}

external_secret_ok(doc, entry) if {
	doc.spec.secretStoreRef == {"name": "vectra-store", "kind": "ClusterSecretStore"}
	doc.spec.target == {"name": doc.metadata.name}
	doc.spec.data == [{"secretKey": entry.secretKey, "remoteRef": {"key": entry.key, "property": entry.property}}]
	object.keys(doc.spec) == {"secretStoreRef", "target", "data"}
	doc.metadata.namespace == namespace
}

# regla: keycloak-tls
deny contains msg if {
	input.kind == "Certificate"
	not input.metadata.name == "keycloak-tls"
	msg := sprintf("keycloak-tls: Certificate %s no es de U2", [input.metadata.name])
}

deny contains msg if {
	some problem in certificate_problem
	msg := sprintf("keycloak-tls: %s", [problem])
}

is_keycloak_tls if {
	input.kind == "Certificate"
	input.metadata.name == "keycloak-tls"
}

certificate_problem contains "secretName distinto de keycloak-tls" if {
	is_keycloak_tls
	input.spec.secretName != "keycloak-tls"
}

certificate_problem contains "los SAN deben ser exactamente los dos de INF-U2-05b" if {
	is_keycloak_tls
	input.spec.dnsNames != ["keycloak.vectra-identity.svc", "keycloak-admin.vectra-identity.svc.cluster.local"]
}

certificate_problem contains "duration debe ser 2160h (90 dias)" if {
	is_keycloak_tls
	input.spec.duration != "2160h"
}

certificate_problem contains "renewBefore debe ser 720h (renueva a los 60)" if {
	is_keycloak_tls
	input.spec.renewBefore != "720h"
}

certificate_problem contains "issuerRef debe ser un ClusterIssuer con nombre" if {
	is_keycloak_tls
	not issuer_ok
}

issuer_ok if {
	input.spec.issuerRef.kind == "ClusterIssuer"
	is_string(input.spec.issuerRef.name)
	input.spec.issuerRef.name != ""
}

certificate_problem contains "namespace distinto de vectra-identity" if {
	is_keycloak_tls
	input.metadata.namespace != namespace
}

# regla: backend-tls-policy
deny contains msg if {
	some problem in backend_tls_problem
	msg := sprintf("backend-tls-policy: %s", [problem])
}

is_backend_tls if input.kind == "BackendTLSPolicy"

backend_tls_problem contains "apiVersion distinta de gateway.networking.k8s.io/v1" if {
	is_backend_tls
	input.apiVersion != "gateway.networking.k8s.io/v1"
}

backend_tls_problem contains "debe apuntar al puerto https (8443) del Service keycloak" if {
	is_backend_tls
	input.spec.targetRefs != [{"group": "", "kind": "Service", "name": "keycloak", "sectionName": "https"}]
}

backend_tls_problem contains "la CA debe ser el Secret identity-ca" if {
	is_backend_tls
	input.spec.validation.caCertificateRefs != [{"group": "", "kind": "Secret", "name": "identity-ca"}]
}

backend_tls_problem contains "hostname de validacion distinto del SAN de keycloak-tls" if {
	is_backend_tls
	input.spec.validation.hostname != "keycloak.vectra-identity.svc"
}

backend_tls_problem contains "namespace distinto de vectra-identity" if {
	is_backend_tls
	input.metadata.namespace != namespace
}

# regla: service-whitelist
# Solo los cuatro Service que hay hoy, ClusterIP, con el selector exacto de los pods de Keycloak.
pod_selector := {"app.kubernetes.io/name": "keycloak", "app.kubernetes.io/instance": "keycloak"}

services := {
	"keycloak": {"keys": {"type", "selector", "ports"}, "ports": {
		{"name": "https", "port": 8443, "targetPort": "https", "protocol": "TCP"},
		{"name": "jgroups", "port": 7800, "targetPort": "jgroups", "protocol": "TCP"},
		{"name": "http-internal", "port": 9000, "targetPort": "http-internal", "protocol": "TCP"},
	}},
	"keycloak-admin": {"keys": {"type", "selector", "ports"}, "ports": {
		{"name": "https", "port": 8443, "targetPort": "https", "protocol": "TCP"},
	}},
	"keycloak-http": {"keys": {"type", "selector", "ports"}, "ports": {
		{"name": "http-internal", "port": 9000, "targetPort": "http-internal", "protocol": "TCP"},
		{"name": "http", "port": 80, "targetPort": "http", "protocol": "TCP"},
		{"name": "https", "port": 8443, "targetPort": "https", "protocol": "TCP"},
	}},
	"keycloak-headless": {"keys": {"type", "clusterIP", "selector", "ports"}, "ports": {
		{"name": "http", "port": 80, "targetPort": "http", "protocol": "TCP"},
	}},
}

deny contains msg if {
	input.kind == "Service"
	not input.metadata.name in object.keys(services)
	msg := sprintf("service-whitelist: el Service %s no esta en la lista blanca", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name in object.keys(services)
	object.keys(input.spec) != services[input.metadata.name].keys
	msg := sprintf("service-whitelist: %s tiene campos de spec fuera de la lista blanca", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name in object.keys(services)
	input.spec.type != "ClusterIP"
	msg := sprintf("service-whitelist: %s debe ser ClusterIP", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name == "keycloak-headless"
	input.spec.clusterIP != "None"
	msg := "service-whitelist: keycloak-headless debe ser headless (clusterIP None)"
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name in object.keys(services)
	input.spec.selector != pod_selector
	msg := sprintf("service-whitelist: %s debe seleccionar exactamente los pods de Keycloak", [input.metadata.name])
}

# regla: service-ports
deny contains msg if {
	input.kind == "Service"
	input.metadata.name in object.keys(services)
	ports := {p | some p in input.spec.ports}
	ports != services[input.metadata.name].ports
	msg := sprintf("service-ports: %s no expone exactamente sus puertos (keycloak: 8443, 7800, 9000; keycloak-admin: 8443)", [input.metadata.name])
}

# regla: no-gateway-route
# `hostname-admin` no esta en el gateway (INF-U2-01).
deny contains msg if {
	input.kind in {"HTTPRoute", "Ingress", "GRPCRoute", "TLSRoute"}
	msg := sprintf("no-gateway-route: %s %s: el chart de Keycloak no publica rutas", [input.kind, input.metadata.name])
}
