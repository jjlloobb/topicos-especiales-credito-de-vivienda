# Reglas de conftest sobre el render del chart minimo de U3 (Paso 12 acotado a la demo; BR-U3-17; INF-U3-03; P-U3-08; NFR-U3-42).
# Cada `# regla: x` tiene un caso que falla en decision-registry/tests/unit/test_chart.py, y cada mensaje empieza por `x:`.
# Lo que exige ver todos los documentos juntos esta en `set.rego` (`--combine --namespace chart_set`).
package main

import rego.v1

namespace := "vectra-app"

image_repositories := {"registro.banco.internal/vectra/decision-registry", "kind-registry:5000/vectra/decision-registry"}

secret_name := "pg-role-registry-aggregator"

is_cronjob if input.kind == "CronJob"

pod := input.spec.jobTemplate.spec.template.spec if is_cronjob

container := pod.containers[0] if is_cronjob

# regla: cronjob-shape
deny contains msg if {
	is_cronjob
	input.metadata.name != "registry-aggregator"
	msg := sprintf("cronjob-shape: el unico CronJob del chart minimo es registry-aggregator, no %s", [input.metadata.name])
}

deny contains msg if {
	is_cronjob
	input.metadata.namespace != namespace
	msg := sprintf("cronjob-shape: el namespace es %s, no %s", [input.metadata.namespace, namespace])
}

deny contains msg if {
	is_cronjob
	not count(pod.containers) == 1
	msg := "cronjob-shape: el pod lleva un solo contenedor"
}

deny contains msg if {
	is_cronjob
	object.get(pod, "initContainers", []) != []
	msg := "cronjob-shape: el pod no lleva initContainers"
}

deny contains msg if {
	is_cronjob
	pod.restartPolicy != "Never"
	msg := "cronjob-shape: restartPolicy es Never"
}

# regla: schedule
deny contains msg if {
	is_cronjob
	input.spec.schedule != "*/5 * * * *"
	msg := sprintf("schedule: el agregador corre cada 5 min, no %s", [input.spec.schedule])
}

# regla: concurrency
deny contains msg if {
	is_cronjob
	object.get(input.spec, "concurrencyPolicy", "") != "Forbid"
	msg := "concurrency: concurrencyPolicy es Forbid"
}

# regla: deadline
# 240 s de lotes + margen: 280 s, menos que el periodo de 300 s (una corrida nunca pisa a la siguiente). Sin reintentos.
deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec, "activeDeadlineSeconds", "ausente") != 280
	msg := sprintf("deadline: activeDeadlineSeconds es 280, no %v", [object.get(input.spec.jobTemplate.spec, "activeDeadlineSeconds", "ausente")])
}

deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec, "backoffLimit", -1) != 0
	msg := "deadline: backoffLimit es 0"
}

# regla: priority
deny contains msg if {
	is_cronjob
	object.get(pod, "priorityClassName", "") != "vectra-high"
	msg := "priority: la prioridad del agregador es vectra-high"
}

# regla: native-sidecar
deny contains msg if {
	is_cronjob
	object.get(object.get(input.spec.jobTemplate.spec.template, "metadata", {}), ["annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "") != "true"
	msg := "native-sidecar: registry-aggregator sin el sidecar nativo de Linkerd"
}

# regla: service-account
deny contains msg if {
	is_cronjob
	object.get(pod, "serviceAccountName", "") != "registry-aggregator"
	msg := sprintf("service-account: la cuenta de servicio es registry-aggregator, no %s", [object.get(pod, "serviceAccountName", "")])
}

# regla: workload-label
# La etiqueta con la que `flows.yaml` (F107) selecciona al agregador.
deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec.template.metadata.labels, "vectra.io/workload", "") != "registry-aggregator"
	msg := "workload-label: el pod lleva vectra.io/workload: registry-aggregator (F107)"
}

# regla: image
deny contains msg if {
	is_cronjob
	parts := split(container.image, "@")
	not count(parts) == 2
	msg := sprintf("image: la imagen %s va por digest", [container.image])
}

deny contains msg if {
	is_cronjob
	parts := split(container.image, "@")
	count(parts) == 2
	not parts[0] in image_repositories
	msg := sprintf("image: el repositorio %s no es el de decision-registry", [parts[0]])
}

deny contains msg if {
	is_cronjob
	parts := split(container.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: command
deny contains msg if {
	is_cronjob
	container.command != ["vectra-registry", "aggregator", "run"]
	msg := "command: registry-aggregator ejecuta vectra-registry aggregator run (sin --until-head: el tope de 240 s)"
}

# regla: no-plain-secret
# Las credenciales de la base salen del Secret de U1 por `secretKeyRef`; nada literal ni en la URL.
deny contains msg if {
	is_cronjob
	some e in container.env
	e.name in {"PGUSER", "PGPASSWORD"}
	not e.valueFrom.secretKeyRef.name == secret_name
	msg := sprintf("no-plain-secret: %s sale del Secret %s por secretKeyRef", [e.name, secret_name])
}

deny contains msg if {
	is_cronjob
	names := {e.name | some e in container.env}
	missing := {"PGUSER", "PGPASSWORD"} - names
	count(missing) > 0
	msg := sprintf("no-plain-secret: faltan %v (secretKeyRef de %s)", [missing, secret_name])
}

deny contains msg if {
	is_cronjob
	some e in container.env
	contains(object.get(e, "value", ""), "@")
	msg := sprintf("no-plain-secret: %s lleva credenciales en la URL", [e.name])
}

deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el render; lo crea U1 (ExternalSecret)", [input.metadata.name])
}

# regla: resources
deny contains msg if {
	is_cronjob
	not container.resources.requests.cpu
	msg := "resources: requests y limits de CPU y memoria (INF-U3-03)"
}

deny contains msg if {
	is_cronjob
	not container.resources.limits.memory
	msg := "resources: requests y limits de CPU y memoria (INF-U3-03)"
}

# regla: hardening
deny contains msg if {
	is_cronjob
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	is_cronjob
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	is_cronjob
	container.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

# regla: service-account-doc
deny contains msg if {
	input.kind == "ServiceAccount"
	input.metadata.namespace != namespace
	msg := sprintf("service-account-doc: el namespace es %s", [namespace])
}

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
