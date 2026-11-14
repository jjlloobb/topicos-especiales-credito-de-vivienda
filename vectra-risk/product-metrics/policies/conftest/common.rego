# Reglas de conftest sobre el render del chart de U11 (Paso 11; INF-U11-01 a 04; BR-U11-09; NFR-U11-05, 13, 20, 21).
# Cada `# regla: x` tiene un caso que falla en product-metrics/tests/unit/test_chart.py, y cada mensaje empieza por `x:`.
# Por documento (`conftest test`): este paquete. Lo que exige ver todo el render junto esta en `set.rego` (`--combine --namespace chart_set`).
package main

import rego.v1

namespace := "vectra-app"

image_repository_suffix := "/vectra/product-metrics"

# El unico conjunto de variables del contenedor (`process.md`, «Entorno y arranque»): las de cableado que pone el chart. `VECTRA_POLICY_PATH` es opcional y no
# se pone (el ConfigMap se monta en `params.POLICY_PATH`). Ninguna constante de `config.py` (CYCLE_SECONDS, FULL_PASS_DEADLINE_SECONDS...) es una variable.
container_env := {"VECTRA_REGISTRY_URL", "VECTRA_CLIENT_ID", "VECTRA_TOKEN_URL", "VECTRA_ASSERTION_AUDIENCE", "VECTRA_CLIENT_KEY_PATH", "VECTRA_CA_BUNDLE"}

# INF-U11-01 / NFR-U11-13: 100m de CPU; limits 500m / 512Mi. El request de memoria es de 256Mi en staging y prod y de 128Mi en kind (P-1 = b).
memory_requests := {"256Mi", "128Mi"}

limits := {"cpu": "500m", "memory": "512Mi"}

is_deployment if {
	input.kind == "Deployment"
	input.metadata.name == "product-metrics"
}

is_policy if {
	input.kind == "ConfigMap"
	input.metadata.name == "product-metrics-policy"
}

pod := input.spec.template.spec if is_deployment

container := pod.containers[0] if is_deployment

# regla: no-plain-secret
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el render; lo crea ESO desde el ExternalSecret", [input.metadata.name])
}

deny contains msg if {
	is_deployment
	some e in container.env
	contains(object.get(e, "value", ""), "@")
	msg := sprintf("no-plain-secret: %s lleva credenciales en la URL", [e.name])
}

deny contains msg if {
	is_deployment
	some e in container.env
	e.valueFrom
	msg := sprintf("no-plain-secret: %s sale de un Secret o ConfigMap por entorno; las llaves se montan de solo lectura", [e.name])
}

# regla: no-linkerd-policy
# El 8081 lo cubre el `Server` `metrics-8081` que U1 genera desde F60 (P-3): el chart no declara ni `Server` ni `AuthorizationPolicy`.
deny contains msg if {
	input.kind in {"Server", "AuthorizationPolicy"}
	msg := sprintf("no-linkerd-policy: el chart no declara %s %s; el 8081 lo cubre el Server metrics-8081 de U1 (P-3)", [input.kind, input.metadata.name])
}

# regla: no-hpa
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	msg := "no-hpa: 2 replicas fijas, sin HorizontalPodAutoscaler (INF-U11-01)"
}

# regla: hardening
deny contains msg if {
	is_deployment
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	is_deployment
	not pod.securityContext.runAsUser == 65532
	msg := "hardening: runAsUser 65532, el de la imagen"
}

deny contains msg if {
	is_deployment
	not pod.securityContext.runAsGroup == 65532
	msg := "hardening: runAsGroup 65532, el de la imagen"
}

deny contains msg if {
	is_deployment
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	is_deployment
	container.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

deny contains msg if {
	is_deployment
	some v in object.get(pod, "volumes", [])
	v.hostPath
	msg := sprintf("hardening: el volumen %s es hostPath", [v.name])
}

# regla: read-only-mounts
# La llave `private_key_jwt`, la CA y los parametros se montan de solo lectura.
deny contains msg if {
	is_deployment
	some m in container.volumeMounts
	not m.readOnly == true
	msg := sprintf("read-only-mounts: el montaje %s (%s) va de solo lectura", [m.name, m.mountPath])
}

# regla: no-subpath
# El ConfigMap de parametros se monta como directorio (INF-U11-02): con `subPath` el kubelet no lo actualiza.
deny contains msg if {
	is_deployment
	some m in container.volumeMounts
	m.subPath
	msg := sprintf("no-subpath: el montaje %s usa subPath", [m.name])
}

# regla: resources
deny contains msg if {
	is_deployment
	container.resources.limits != limits
	msg := "resources: limits 500m / 512Mi (INF-U11-01)"
}

deny contains msg if {
	is_deployment
	not container.resources.requests.cpu == "100m"
	msg := "resources: request de CPU 100m (INF-U11-01)"
}

deny contains msg if {
	is_deployment
	not container.resources.requests.memory in memory_requests
	msg := sprintf("resources: request de memoria 256Mi (128Mi solo en kind, P-1), no %v", [object.get(container.resources.requests, "memory", "ausente")])
}

# regla: image
deny contains msg if {
	is_deployment
	parts := split(container.image, "@")
	not count(parts) == 2
	msg := sprintf("image: la imagen %s va por digest", [container.image])
}

deny contains msg if {
	is_deployment
	parts := split(container.image, "@")
	count(parts) == 2
	not endswith(parts[0], image_repository_suffix)
	msg := sprintf("image: el repositorio %s no es el de product-metrics", [parts[0]])
}

deny contains msg if {
	is_deployment
	parts := split(container.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: namespace
deny contains msg if {
	input.kind in {"Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ExternalSecret", "ServiceMonitor", "PrometheusRule", "ConfigMap"}
	input.metadata.namespace != namespace
	msg := sprintf("namespace: %s %s va en %s, no en %s", [input.kind, input.metadata.name, input.metadata.namespace, namespace])
}

# regla: service-account-doc
# Sin token montado (INF-U11-03): el proceso no habla con la API de Kubernetes. Linkerd identifica al pod por su cuenta de servicio, no por ese token.
deny contains msg if {
	input.kind == "ServiceAccount"
	object.get(input, "secrets", []) != []
	msg := "service-account-doc: sin secretos en la cuenta de servicio"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	not input.automountServiceAccountToken == false
	msg := "service-account-doc: automountServiceAccountToken false en la cuenta de servicio"
}

# regla: pod-token
deny contains msg if {
	is_deployment
	not pod.automountServiceAccountToken == false
	msg := "pod-token: automountServiceAccountToken false en el pod"
}
