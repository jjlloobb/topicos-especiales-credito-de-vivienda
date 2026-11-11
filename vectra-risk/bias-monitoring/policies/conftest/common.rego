# Reglas de conftest sobre el render del chart de U9 (Paso 12 acotado a la demo; INF-U9-01 a 04; BR-U9-13; P-U9-05; NFR-U9-10 a 13, 30, 34).
# Cada `# regla: x` tiene un caso que falla en bias-monitoring/tests/unit/test_chart.py, y cada mensaje empieza por `x:`.
# Por documento (`conftest test`): este paquete. Lo que exige ver todo el render junto esta en `set.rego` (`--combine --namespace chart_set`).
package main

import rego.v1

namespace := "vectra-app"

image_repository_suffix := "/vectra/bias-monitoring"

# El unico conjunto de variables de entorno de cada proceso (INF-U9-03): las del codigo (`vectra_bias.app.REQUIRED` y las opcionales que se
# usan; `vectra_bias.run.build_deps`). Ninguna constante del codigo (CACHE_TTL_SECONDS, timeouts, reintentos) es una variable.
service_env := {"VECTRA_REGISTRY_URL", "VECTRA_TOKEN_URL", "VECTRA_CLIENT_ID", "VECTRA_CLIENT_KEY_PATH", "VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE", "VECTRA_POLICY_PATH"}

job_env := {"VECTRA_REGISTRY_URL", "VECTRA_GOVERNANCE_URL", "VECTRA_PUSHGATEWAY_URL", "VECTRA_POLICY_PATH", "VECTRA_TOKEN_URL", "VECTRA_CLIENT_ID", "VECTRA_CLIENT_KEY_PATH", "VECTRA_CA_BUNDLE"}

resources := {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}

is_service if {
	input.kind == "Deployment"
	input.metadata.name == "bias-monitoring-service"
}

is_cronjob if input.kind == "CronJob"

is_policy if {
	input.kind == "ConfigMap"
	input.metadata.name == "bias-monitoring-policy"
}

service_pod := input.spec.template.spec if is_service

service_container := service_pod.containers[0] if is_service

job_pod := input.spec.jobTemplate.spec.template.spec if is_cronjob

job_container := job_pod.containers[0] if is_cronjob

# Lo que ambos procesos comparten.
workloads contains service_pod if is_service

workloads contains job_pod if is_cronjob

# regla: no-plain-secret
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el render; lo crea ESO desde el ExternalSecret", [input.metadata.name])
}

deny contains msg if {
	some c in all_containers
	some e in c.env
	contains(object.get(e, "value", ""), "@")
	msg := sprintf("no-plain-secret: %s lleva credenciales en la URL", [e.name])
}

deny contains msg if {
	some c in all_containers
	some e in c.env
	e.valueFrom
	msg := sprintf("no-plain-secret: %s sale de un Secret o ConfigMap por entorno; las llaves se montan de solo lectura", [e.name])
}

all_containers contains c if {
	is_service
	some c in service_pod.containers
}

all_containers contains c if {
	is_cronjob
	some c in job_pod.containers
}

# regla: no-probe
# El Job `x04-probe-<runId>` esta diferido (T5): ningun Job en el render.
deny contains msg if {
	input.kind == "Job"
	msg := sprintf("no-probe: el Job %s no va; x04-probe esta diferido por la demo (T5)", [input.metadata.name])
}

# regla: hardening
deny contains msg if {
	some pod in workloads
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	some pod in workloads
	not pod.securityContext.runAsUser == 65532
	msg := "hardening: runAsUser 65532, el de la imagen"
}

deny contains msg if {
	some pod in workloads
	not pod.securityContext.runAsGroup == 65532
	msg := "hardening: runAsGroup 65532, el de la imagen"
}

deny contains msg if {
	some pod in workloads
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	some c in all_containers
	c.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

# regla: read-only-mounts
# La llave `private_key_jwt`, la CA y la politica se montan de solo lectura.
deny contains msg if {
	some c in all_containers
	some m in c.volumeMounts
	not m.readOnly == true
	msg := sprintf("read-only-mounts: el montaje %s (%s) va de solo lectura", [m.name, m.mountPath])
}

# regla: resources
deny contains msg if {
	some c in all_containers
	c.resources != resources
	msg := "resources: requests 100m/128Mi y limits 500m/256Mi (INF-U9-01)"
}

# regla: image
deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	not count(parts) == 2
	msg := sprintf("image: la imagen %s va por digest", [c.image])
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not endswith(parts[0], image_repository_suffix)
	msg := sprintf("image: el repositorio %s no es el de bias-monitoring", [parts[0]])
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: namespace
deny contains msg if {
	input.kind in {"Deployment", "CronJob", "Service", "PodDisruptionBudget", "ServiceAccount", "ExternalSecret", "ServiceMonitor", "ConfigMap"}
	input.metadata.namespace != namespace
	msg := sprintf("namespace: %s %s va en %s, no en %s", [input.kind, input.metadata.name, input.metadata.namespace, namespace])
}

# regla: service-account-doc
deny contains msg if {
	input.kind == "ServiceAccount"
	object.get(input, "secrets", []) != []
	msg := "service-account-doc: sin secretos en la cuenta de servicio"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	object.get(input, "automountServiceAccountToken", true) != true
	msg := "service-account-doc: Linkerd necesita el token de la cuenta de servicio"
}
