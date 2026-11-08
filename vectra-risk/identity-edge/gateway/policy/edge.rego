# Reglas de conftest sobre el Gateway, el Certificate, el EnvoyProxy y la EnvoyPatchPolicy que `route_gen.py` genera
# (U02-T10, Paso 8 del plan de U2): una pasada por documento. INF-U2-01, 02, 06; NFR-U2-03, 22, 23; P-U2-01, 07.
# Los campos del EnvoyProxy son los que piden las politicas estaticas de U1 (`STATIC_POLICIES`) al data plane en `vectra-edge`:
# `EnvoyProxy` no genera un Deployment en el render, asi que se exigen aqui. Cada `# regla: x` tiene un caso que falla en
# identity-edge/tests/unit/test_route_gen.py y cada mensaje empieza por `x:`.
package main

import rego.v1

class_name := "envoy-gateway"

controller_name := "gateway.envoyproxy.io/gatewayclass-controller"

tls_secret := "api-gateway-tls"

criticality := {"vectra.io/criticality": "high"}

gateway_label := {"app.kubernetes.io/name": "api-gateway"}

# restrict-registries (U1): registro permitido; disallow-latest: digest.
allowed_registries := {"registro.vectra.internal/", "registro.banco.internal/vectra/", "kind-registry:5000/"}

envoy_digest := "sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0"

# regla: gateway-class
deny contains msg if {
	input.kind == "GatewayClass"
	not input.spec.controllerName == controller_name
	msg := sprintf("gateway-class: %s con el controlador %s", [label(input), input.spec.controllerName])
}

deny contains msg if {
	input.kind == "GatewayClass"
	not input.spec.parametersRef == {"group": "gateway.envoyproxy.io", "kind": "EnvoyProxy", "name": "api-gateway", "namespace": edge_namespace}
	msg := sprintf("gateway-class: %s no apunta al EnvoyProxy api-gateway de vectra-edge", [label(input)])
}

deny contains msg if {
	input.kind == "GatewayClass"
	not input.metadata.name == class_name
	msg := sprintf("gateway-class: %s debia llamarse %s", [label(input), class_name])
}

# regla: gateway-listener
# INF-U2-02, INF-U2-10: un `Gateway` `api-gateway` en vectra-edge con un solo listener HTTPS (443) `https` y el Secret del Certificate.
deny contains msg if {
	input.kind == "Gateway"
	not input.metadata.name == "api-gateway"
	msg := sprintf("gateway-listener: %s debia llamarse api-gateway", [label(input)])
}

deny contains msg if {
	input.kind == "Gateway"
	not input.metadata.namespace == edge_namespace
	msg := sprintf("gateway-listener: %s no esta en %s", [label(input), edge_namespace])
}

deny contains msg if {
	input.kind == "Gateway"
	not input.spec.gatewayClassName == class_name
	msg := sprintf("gateway-listener: %s no usa la GatewayClass %s", [label(input), class_name])
}

deny contains msg if {
	input.kind == "Gateway"
	count(input.spec.listeners) != 1
	msg := sprintf("gateway-listener: %s debia tener un solo listener", [label(input)])
}

deny contains msg if {
	input.kind == "Gateway"
	some listener in input.spec.listeners
	not listener.name == "https"
	msg := sprintf("gateway-listener: %s con el listener %s y debia ser https", [label(input), listener.name])
}

deny contains msg if {
	input.kind == "Gateway"
	some listener in input.spec.listeners
	not listener.port == 443
	msg := sprintf("gateway-listener: %s escucha en el puerto %v y debia ser 443", [label(input), listener.port])
}

deny contains msg if {
	input.kind == "Gateway"
	some listener in input.spec.listeners
	not listener.protocol == "HTTPS"
	msg := sprintf("gateway-listener: %s con el protocolo %s", [label(input), listener.protocol])
}

deny contains msg if {
	input.kind == "Gateway"
	some listener in input.spec.listeners
	not listener.hostname in public_hostnames
	msg := sprintf("gateway-listener: %s con el hostname %v", [label(input), object.get(listener, "hostname", "")])
}

deny contains msg if {
	input.kind == "Gateway"
	some listener in input.spec.listeners
	not listener.tls == {"mode": "Terminate", "certificateRefs": [{"group": "", "kind": "Secret", "name": tls_secret}]}
	msg := sprintf("gateway-listener: %s no termina TLS con el Secret %s", [label(input), tls_secret])
}

# regla: certificate-issuer
# INF-U2-01, NFR-U2-22: Certificate en vectra-edge para el hostname publico, emitido por un ClusterIssuer. Cual ClusterIssuer
# toca a cada entorno lo comprueba `environment-values`.
deny contains msg if {
	input.kind == "Certificate"
	not input.metadata.namespace == edge_namespace
	msg := sprintf("certificate-issuer: %s no esta en %s", [label(input), edge_namespace])
}

deny contains msg if {
	input.kind == "Certificate"
	not input.spec.secretName == tls_secret
	msg := sprintf("certificate-issuer: %s no escribe el Secret %s", [label(input), tls_secret])
}

deny contains msg if {
	input.kind == "Certificate"
	count(input.spec.dnsNames) != 1
	msg := sprintf("certificate-issuer: %s debia tener un solo dnsName", [label(input)])
}

deny contains msg if {
	input.kind == "Certificate"
	some name in input.spec.dnsNames
	not name in public_hostnames
	msg := sprintf("certificate-issuer: %s con el dnsName %s", [label(input), name])
}

deny contains msg if {
	input.kind == "Certificate"
	not input.spec.issuerRef.kind == "ClusterIssuer"
	msg := sprintf("certificate-issuer: %s no usa un ClusterIssuer", [label(input)])
}

deny contains msg if {
	input.kind == "Certificate"
	not input.spec.issuerRef.name in {"vectra-internal-ca", "banco-ca"}
	msg := sprintf("certificate-issuer: %s con el issuer %s", [label(input), input.spec.issuerRef.name])
}

# regla: envoy-identity
# Paso 8 (Z1): la identidad: ServiceAccount `api-gateway` (Linkerd) y el pod sin sobrescribir las etiquetas de Envoy Gateway; el Paso 10
# selecciona el data plane por `gateway.envoyproxy.io/owning-gateway-name`.
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyServiceAccount == {"name": "api-gateway"}
	msg := sprintf("envoy-identity: %s no usa el ServiceAccount api-gateway", [label(input)])
}

# Z1: `pod.labels` se copia encima de las etiquetas del template pero no del selector del Deployment (`stableSelector`), que usa las de
# `EnvoyAppLabel` (v1.9.3): sobrescribir una deja un selector que no selecciona su template, y el apiserver rechaza el Deployment.
envoy_app_label_keys := {"app.kubernetes.io/name", "app.kubernetes.io/component", "app.kubernetes.io/managed-by"}

deny contains msg if {
	input.kind == "EnvoyProxy"
	some key in object.keys(input.spec.provider.kubernetes.envoyDeployment.pod.labels)
	key in envoy_app_label_keys
	msg := sprintf("envoy-identity: %s sobrescribe %s en pod.labels y el selector del Deployment dejaria de seleccionar sus pods", [label(input), key])
}

# regla: envoy-image
# restrict-registries y disallow-latest (U1), W4: registro permitido (el espejo de Envoy) y el digest del diseno.
envoy_image := input.spec.provider.kubernetes.envoyDeployment.container.image

deny contains msg if {
	input.kind == "EnvoyProxy"
	not image_registry_allowed(envoy_image)
	msg := sprintf("envoy-image: %s usa la imagen %s, de un registro no permitido", [label(input), envoy_image])
}

image_registry_allowed(image) if {
	some prefix in allowed_registries
	startswith(image, prefix)
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not endswith(envoy_image, concat("", ["@", envoy_digest]))
	msg := sprintf("envoy-image: %s usa la imagen %s, sin el digest del espejo", [label(input), envoy_image])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not contains(envoy_image, "/vectra/envoy@")
	msg := sprintf("envoy-image: %s usa la imagen %s y debia ser el espejo vectra/envoy", [label(input), envoy_image])
}

# regla: envoy-non-root
# require-run-as-non-root (U1): el pod y el contenedor (y con el, el sidecar shutdown-manager de v1.9.3).
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.pod.securityContext.runAsNonRoot == true
	msg := sprintf("envoy-non-root: %s no fija runAsNonRoot en el pod", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.runAsNonRoot == true
	msg := sprintf("envoy-non-root: %s no fija runAsNonRoot en el contenedor", [label(input)])
}

# regla: envoy-no-privileged
# disallow-privileged (U1).
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.privileged == false
	msg := sprintf("envoy-no-privileged: %s no fija privileged: false", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("envoy-no-privileged: %s permite la escalada de privilegios", [label(input)])
}

# regla: envoy-readonly-rootfs
# require-ro-rootfs (U1). v1.9.3 deja la raiz escribible por defecto; el contexto del contenedor la fija tambien en el sidecar.
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.readOnlyRootFilesystem == true
	msg := sprintf("envoy-readonly-rootfs: %s no fija readOnlyRootFilesystem", [label(input)])
}

# regla: envoy-hardening
# Pod Security: seccomp RuntimeDefault y sin capacidades.
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.pod.securityContext.seccompProfile == {"type": "RuntimeDefault"}
	msg := sprintf("envoy-hardening: %s no fija seccompProfile RuntimeDefault en el pod", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.seccompProfile == {"type": "RuntimeDefault"}
	msg := sprintf("envoy-hardening: %s no fija seccompProfile RuntimeDefault en el contenedor", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.securityContext.capabilities == {"drop": ["ALL"]}
	msg := sprintf("envoy-hardening: %s no quita todas las capacidades", [label(input)])
}

# regla: envoy-resources
# require-resources (U1) vale para todos los contenedores del pod, INF-U2-06: Envoy 250m / 256 MiB de requests y 1 CPU / 512 MiB
# de limits; el sidecar `shutdown-manager` 10m / 32 MiB y 50m / 64 MiB (Y1), que v1.9.3 solo deja fijar por `envoyDeployment.patch`.
sidecar_containers := [c |
	some c in input.spec.provider.kubernetes.envoyDeployment.patch.value.spec.template.spec.containers
	c.name == "shutdown-manager"
]

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.container.resources == {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}
	msg := sprintf("envoy-resources: %s no fija los recursos de INF-U2-06 en Envoy", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.patch.type == "StrategicMerge"
	msg := sprintf("envoy-resources: %s no fija los recursos del shutdown-manager por un patch StrategicMerge", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	count(sidecar_containers) != 1
	msg := sprintf("envoy-resources: %s debia fijar los recursos del contenedor shutdown-manager", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	some c in sidecar_containers
	not c.resources == {"requests": {"cpu": "10m", "memory": "32Mi"}, "limits": {"cpu": "50m", "memory": "64Mi"}}
	msg := sprintf("envoy-resources: %s no fija los recursos del shutdown-manager de INF-U2-06", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	some c in input.spec.provider.kubernetes.envoyDeployment.patch.value.spec.template.spec.containers
	not c.name == "shutdown-manager"
	msg := sprintf("envoy-resources: %s parcha el contenedor %s y solo debia parchar el shutdown-manager", [label(input), c.name])
}

# regla: client-tls
# NFR-U2-22 (Y4): TLS 1.2 como minimo y 1.3 como maximo en el borde.
deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.tls.minVersion == "1.2"
	msg := sprintf("client-tls: %s no fija TLS 1.2 como minimo", [label(input)])
}

deny contains msg if {
	input.kind == "ClientTrafficPolicy"
	not input.spec.tls.maxVersion == "1.3"
	msg := sprintf("client-tls: %s no fija TLS 1.3 como maximo", [label(input)])
}

# regla: envoy-priority
# require-priority-class (U1).
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyDeployment.pod.priorityClassName == "vectra-high"
	msg := sprintf("envoy-priority: %s no usa la prioridad vectra-high", [label(input)])
}

# regla: envoy-criticality
# require-criticality-label (U1) valida el Deployment, cuyas etiquetas salen de `Gateway.spec.infrastructure.labels` (X3); el pod tambien la lleva.
deny contains msg if {
	input.kind == "EnvoyProxy"
	not object.get(input.spec.provider.kubernetes.envoyDeployment.pod.labels, "vectra.io/criticality", "") == "high"
	msg := sprintf("envoy-criticality: %s no etiqueta el pod con vectra.io/criticality: high", [label(input)])
}

deny contains msg if {
	input.kind == "Gateway"
	not input.spec.infrastructure.labels == criticality
	msg := sprintf("envoy-criticality: %s no pone vectra.io/criticality: high en infrastructure.labels", [label(input)])
}

# regla: envoy-service
# restrict-loadbalancer (U1), W2: unico LoadBalancer, con la etiqueta de api-gateway y la IP real del cliente (`Local`).
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyService.type == "LoadBalancer"
	msg := sprintf("envoy-service: %s no es LoadBalancer", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyService.externalTrafficPolicy == "Local"
	msg := sprintf("envoy-service: %s no usa externalTrafficPolicy: Local", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyService.labels == gateway_label
	msg := sprintf("envoy-service: %s no etiqueta el Service con app.kubernetes.io/name: api-gateway", [label(input)])
}

# regla: envoy-scaling
# NFR-U2-03, W5: al menos 2 replicas, HPA de 2 a 6 con CPU al 70 %, PDB `minAvailable: 1` y reparto por zona.
deny contains msg if {
	input.kind == "EnvoyProxy"
	input.spec.provider.kubernetes.envoyDeployment.replicas < 2
	msg := sprintf("envoy-scaling: %s tiene menos de 2 replicas", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	hpa := input.spec.provider.kubernetes.envoyHpa
	not {hpa.minReplicas, hpa.maxReplicas} == {2, 6}
	msg := sprintf("envoy-scaling: %s no escala de 2 a 6 replicas", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyHpa.metrics == [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}}]
	msg := sprintf("envoy-scaling: %s no escala por CPU al 70 %%", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.provider.kubernetes.envoyPDB == {"minAvailable": 1}
	msg := sprintf("envoy-scaling: %s no tiene el PDB minAvailable: 1", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	constraints := input.spec.provider.kubernetes.envoyDeployment.pod.topologySpreadConstraints
	not [c.topologyKey | some c in constraints] == ["topology.kubernetes.io/zone"]
	msg := sprintf("envoy-scaling: %s no reparte por zona", [label(input)])
}

# El reparto selecciona los pods del data plane por la etiqueta del owning gateway que v1.9.3 pone a todos.
deny contains msg if {
	input.kind == "EnvoyProxy"
	some c in input.spec.provider.kubernetes.envoyDeployment.pod.topologySpreadConstraints
	not c.labelSelector.matchLabels == {"gateway.envoyproxy.io/owning-gateway-name": "api-gateway"}
	msg := sprintf("envoy-scaling: %s reparte pods que no son los del data plane", [label(input)])
}

# regla: access-log-allowlist
# P-U2-07: JSON a stdout con exactamente los campos del diseno; ni query string, ni cuerpo, ni cabeceras. `route_name` y
# `method` usan operadores que no llevan la query.
access_log_fields := {
	"timestamp": "%START_TIME%",
	"route_name": "%ROUTE_NAME%",
	"method": "%REQ(:METHOD)%",
	"status": "%RESPONSE_CODE%",
	"duration_ms": "%DURATION%",
	"upstream_cluster": "%UPSTREAM_CLUSTER%",
	"correlation_id": "%TRACE_ID%",
	"client_ip": "%DOWNSTREAM_REMOTE_ADDRESS_WITHOUT_PORT%",
	"response_flags": "%RESPONSE_FLAGS%",
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	count(input.spec.telemetry.accessLog.settings) != 1
	msg := sprintf("access-log-allowlist: %s debia tener un solo access log", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	some setting in input.spec.telemetry.accessLog.settings
	not setting.format == {"type": "JSON", "json": access_log_fields}
	msg := sprintf("access-log-allowlist: %s no registra exactamente los campos de P-U2-07", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	some setting in input.spec.telemetry.accessLog.settings
	not setting.sinks == [{"type": "File", "file": {"path": "/dev/stdout"}}]
	msg := sprintf("access-log-allowlist: %s no escribe solo a stdout", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	input.spec.telemetry.accessLog.disable
	msg := sprintf("access-log-allowlist: %s desactiva el access log", [label(input)])
}

# regla: tracing
# W6, F61: OpenTelemetry hacia el colector, con muestreo del 100 %.
deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.telemetry.tracing.samplingRate == 100
	msg := sprintf("tracing: %s no muestrea el 100 %%", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyProxy"
	not input.spec.telemetry.tracing.provider == {"type": "OpenTelemetry", "backendRefs": [{"name": "otel-collector", "namespace": "vectra-observability", "port": 4317}]}
	msg := sprintf("tracing: %s no envia las trazas a otel-collector.vectra-observability.svc:4317", [label(input)])
}

# regla: fail-closed-patch
# P-U2-01, NFR-U2-21, alternativa 2: la EnvoyPatchPolicy fija `failure_mode_deny: true` y `status_on_error: 503` solo en el filtro de rate
# limit del dominio de `/auth/**` del listener https.
auth_filter := "envoy.filters.http.ratelimit/vectra-edge/auth-rate-limits"

auth_selector := "..http_filters[?(@.name=='envoy.filters.http.ratelimit/vectra-edge/auth-rate-limits')].typed_config"

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	not input.spec.type == "JSONPatch"
	msg := sprintf("fail-closed-patch: %s no es JSONPatch", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	not input.spec.targetRef == {"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": "api-gateway"}
	msg := sprintf("fail-closed-patch: %s no apunta al Gateway api-gateway", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	count(input.spec.jsonPatches) != 2
	msg := sprintf("fail-closed-patch: %s debia tener dos parches", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	some patch in input.spec.jsonPatches
	not patch.type == "type.googleapis.com/envoy.config.listener.v3.Listener"
	msg := sprintf("fail-closed-patch: %s parcha algo que no es un Listener", [label(input)])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	some patch in input.spec.jsonPatches
	not patch.name == "vectra-edge/api-gateway/https"
	msg := sprintf("fail-closed-patch: %s parcha el listener %s y debia ser vectra-edge/api-gateway/https", [label(input), patch.name])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	some patch in input.spec.jsonPatches
	not patch.operation.jsonPath == auth_selector
	msg := sprintf("fail-closed-patch: %s no acota el parche al filtro %s", [label(input), auth_filter])
}

deny contains msg if {
	input.kind == "EnvoyPatchPolicy"
	patches := {[p.operation.op, p.operation.path, json.marshal(p.operation.value)] | some p in input.spec.jsonPatches}
	patches != {["add", "failure_mode_deny", "true"], ["add", "status_on_error", "{\"code\":503}"]}
	msg := sprintf("fail-closed-patch: %s no fija failure_mode_deny: true y status_on_error: 503", [label(input)])
}
