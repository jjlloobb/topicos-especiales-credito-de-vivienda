# Reglas de conftest sobre `envoy-ratelimit` (U02-T11, Paso 9 del plan de U2): el `EnvoyGateway` del render de `gateway-helm` v1.9.3 con
# los values del controlador, y el `ExternalSecret` de `envoy-gateway-system` (INF-U2-03, 06; R1, R2, R5; NFR-U2-27).
# Kyverno no alcanza `envoy-gateway-system`: estas reglas exigen lo mismo que exigirian sus politicas (R2).
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_ratelimit_deployment.py, y cada mensaje empieza por `x:`.
# Lo que exige ver varios renders juntos esta en `set.rego` (`--combine --namespace ratelimit_set`).
package main

import rego.v1

registries := {"registro.banco.internal/vectra", "kind-registry:5000/vectra"}

digest := "sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681"

secret_name := "envoy-ratelimit-valkey"

# R1: `<master>,<sentinel-a-0>,<sentinel-b-0>,<sentinel-b-1>`, con los FQDN de los Services headless de `vectra-edge`.
redis_url := "ratelimit,sentinel-a-0.sentinel-a.vectra-edge.svc.cluster.local:26379,sentinel-b-0.sentinel-b.vectra-edge.svc.cluster.local:26379,sentinel-b-1.sentinel-b.vectra-edge.svc.cluster.local:26379"

# `rateLimitLabels()` de v1.9.3: lo que el controlador pone al template y al selector del Deployment.
ratelimit_labels := {
	"app.kubernetes.io/name": "envoy-ratelimit",
	"app.kubernetes.io/component": "ratelimit",
	"app.kubernetes.io/managed-by": "envoy-gateway",
}

# INF-U2-06: servicio de rate limit.
resources := {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "128Mi"}}

is_controller_config if {
	input.kind == "ConfigMap"
	input.metadata.name == "envoy-gateway-config"
}

config := yaml.unmarshal(input.data["envoy-gateway.yaml"]) if is_controller_config

kube := config.provider.kubernetes

deployment := kube.rateLimitDeployment

container := deployment.container

pod := deployment.pod

# regla: backend
deny contains msg if {
	is_controller_config
	not config.rateLimit.backend.type == "Redis"
	msg := "backend: rateLimit.backend.type distinto de Redis"
}

deny contains msg if {
	is_controller_config
	not config.rateLimit.backend.redis.url == redis_url
	msg := "backend: rateLimit.backend.redis.url no es el master y los tres Sentinel de R1"
}

deny contains msg if {
	is_controller_config
	not config.rateLimit.failClosed == false
	msg := "backend: rateLimit.failClosed debe ser false (el cierre de /auth/** es de la EnvoyPatchPolicy)"
}

# regla: telemetry
deny contains msg if {
	is_controller_config
	not config.rateLimit.telemetry.tracing.provider.type == "OpenTelemetry"
	msg := "telemetry: el tracing de envoy-ratelimit no es OpenTelemetry"
}

deny contains msg if {
	is_controller_config
	not config.rateLimit.telemetry.tracing.provider.url == "otel-collector.vectra-observability.svc:4317"
	msg := "telemetry: el tracing no va al otel-collector de vectra-observability"
}

deny contains msg if {
	is_controller_config
	not config.rateLimit.telemetry.tracing.samplingRate == 100
	msg := "telemetry: el muestreo del tracing no es 100"
}

deny contains msg if {
	is_controller_config
	config.rateLimit.telemetry.metrics.prometheus.disable == true
	msg := "telemetry: las metricas Prometheus de envoy-ratelimit estan deshabilitadas"
}

# regla: sentinel-env
env_of(name) := [e | some e in container.env; e.name == name]

deny contains msg if {
	is_controller_config
	not env_of("REDIS_TYPE") == [{"name": "REDIS_TYPE", "value": "SENTINEL"}]
	msg := "sentinel-env: REDIS_TYPE debe ser SENTINEL"
}

deny contains msg if {
	is_controller_config
	some name in ["REDIS_AUTH", "REDIS_SENTINEL_AUTH"]
	not env_of(name) == [{"name": name, "valueFrom": {"secretKeyRef": {"name": secret_name, "key": name}}}]
	msg := sprintf("sentinel-env: %s debe venir por secretKeyRef al Secret %s", [name, secret_name])
}

deny contains msg if {
	is_controller_config
	some e in container.env
	not e.name in {"REDIS_TYPE", "REDIS_AUTH", "REDIS_SENTINEL_AUTH"}
	msg := sprintf("sentinel-env: variable %s fuera del diseno", [e.name])
}

# regla: image
deny contains msg if {
	is_controller_config
	not container.image in {sprintf("%s/ratelimit@%s", [r, digest]) | some r in registries}
	msg := "image: la imagen de envoy-ratelimit no es ratelimit@sha256:b95206... de un registro permitido"
}

# regla: replicas
deny contains msg if {
	is_controller_config
	not deployment.replicas == 2
	msg := "replicas: rateLimitDeployment.replicas debe ser 2"
}

deny contains msg if {
	is_controller_config
	hpa := kube.rateLimitHpa
	not hpa.minReplicas == 2
	msg := "replicas: rateLimitHpa.minReplicas debe ser 2"
}

deny contains msg if {
	is_controller_config
	hpa := kube.rateLimitHpa
	not hpa.maxReplicas == 4
	msg := "replicas: rateLimitHpa.maxReplicas debe ser 4"
}

deny contains msg if {
	is_controller_config
	not kube.rateLimitHpa.metrics == [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}}]
	msg := "replicas: rateLimitHpa debe escalar por CPU al 70 %"
}

deny contains msg if {
	is_controller_config
	not kube.rateLimitPDB.minAvailable == 1
	msg := "replicas: rateLimitPDB.minAvailable debe ser 1"
}

# regla: resources
deny contains msg if {
	is_controller_config
	not container.resources == resources
	msg := "resources: los recursos de envoy-ratelimit difieren de INF-U2-06"
}

# regla: hardening
deny contains msg if {
	is_controller_config
	not pod.priorityClassName == "vectra-high"
	msg := "hardening: envoy-ratelimit sin priorityClassName vectra-high"
}

deny contains msg if {
	is_controller_config
	not pod.labels["vectra.io/criticality"] == "high"
	msg := "hardening: el pod de envoy-ratelimit sin vectra.io/criticality=high"
}

deny contains msg if {
	is_controller_config
	not deployment.patch.value.metadata.labels["vectra.io/criticality"] == "high"
	msg := "hardening: el Deployment de envoy-ratelimit sin vectra.io/criticality=high (patch)"
}

deny contains msg if {
	is_controller_config
	not deployment.patch.type == "StrategicMerge"
	msg := "hardening: el patch del Deployment de envoy-ratelimit no es StrategicMerge"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.runAsNonRoot == true
	msg := "hardening: el contenedor de envoy-ratelimit no corre como no root"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.allowPrivilegeEscalation == false
	msg := "hardening: el contenedor de envoy-ratelimit permite escalar privilegios"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.privileged == false
	msg := "hardening: el contenedor de envoy-ratelimit es privilegiado"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.readOnlyRootFilesystem == true
	msg := "hardening: el contenedor de envoy-ratelimit con raiz escribible"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.capabilities.drop == ["ALL"]
	msg := "hardening: el contenedor de envoy-ratelimit no suelta todas las capabilities"
}

deny contains msg if {
	is_controller_config
	not container.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: el contenedor de envoy-ratelimit sin seccompProfile RuntimeDefault"
}

deny contains msg if {
	is_controller_config
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod de envoy-ratelimit no corre como no root"
}

deny contains msg if {
	is_controller_config
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: el pod de envoy-ratelimit sin seccompProfile RuntimeDefault"
}

# regla: spread
deny contains msg if {
	is_controller_config
	not count(object.get(pod, "topologySpreadConstraints", [])) == 1
	msg := "spread: envoy-ratelimit debe repartirse con una sola restriccion por zona"
}

deny contains msg if {
	is_controller_config
	some c in pod.topologySpreadConstraints
	not c.topologyKey == "topology.kubernetes.io/zone"
	msg := "spread: la restriccion de envoy-ratelimit no es por topology.kubernetes.io/zone"
}

deny contains msg if {
	is_controller_config
	some c in pod.topologySpreadConstraints
	not c.whenUnsatisfiable == "DoNotSchedule"
	msg := "spread: la restriccion de envoy-ratelimit debe ser DoNotSchedule"
}

# El selector debe seleccionar los pods: no vacio y contenido en `rateLimitLabels()` (los pods llevan esas etiquetas mas las de pod.labels).
deny contains msg if {
	is_controller_config
	some c in pod.topologySpreadConstraints
	not c.labelSelector.matchLabels == ratelimit_labels
	msg := "spread: el selector del reparto de envoy-ratelimit no es rateLimitLabels()"
}

deny contains msg if {
	is_controller_config
	some c in pod.topologySpreadConstraints
	c.labelSelector.matchExpressions
	msg := "spread: el selector del reparto de envoy-ratelimit no admite matchExpressions"
}

# regla: external-secret
is_external_secret if {
	input.kind == "ExternalSecret"
	input.metadata.name == secret_name
}

deny contains msg if {
	is_external_secret
	not input.metadata.namespace == "envoy-gateway-system"
	msg := "external-secret: el ExternalSecret de envoy-ratelimit debe estar en envoy-gateway-system"
}

deny contains msg if {
	is_external_secret
	not input.spec.secretStoreRef == {"name": "vectra-store", "kind": "ClusterSecretStore"}
	msg := "external-secret: debe usar el ClusterSecretStore vectra-store"
}

deny contains msg if {
	is_external_secret
	not input.spec.target.name == secret_name
	msg := "external-secret: el Secret destino debe llamarse envoy-ratelimit-valkey"
}

deny contains msg if {
	is_external_secret
	not input.spec.target.template.data == {
		"REDIS_AUTH": "ratelimit:{{ .ratelimit }}",
		"REDIS_SENTINEL_AUTH": "ratelimit:{{ .sentinelRatelimit }}",
	}
	msg := "external-secret: la plantilla debe armar REDIS_AUTH y REDIS_SENTINEL_AUTH como ratelimit:<contrasena>"
}

deny contains msg if {
	is_external_secret
	not input.spec.data == [
		{"secretKey": "ratelimit", "remoteRef": {"key": "edge/valkey", "property": "ratelimit"}},
		{"secretKey": "sentinelRatelimit", "remoteRef": {"key": "edge/valkey", "property": "sentinel-ratelimit"}},
	]
	msg := "external-secret: debe tomar ratelimit y sentinel-ratelimit de edge/valkey"
}

# regla: no-plain-secret
deny contains msg if {
	input.kind == "Secret"
	input.metadata.name == secret_name
	msg := "no-plain-secret: el Secret de envoy-ratelimit lo materializa ESO, no se versiona"
}
