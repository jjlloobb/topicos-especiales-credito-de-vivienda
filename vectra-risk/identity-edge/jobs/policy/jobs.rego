# Reglas de conftest sobre lo que `render-jobs` produce (U02-T08, Paso 6 del plan de U2).
# Son listas blancas y comparaciones exactas contra el diseno (INF-U2-05a, 06, 09; BR-U2-12; P-U2-05).
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_identity_jobs.py, y cada mensaje empieza por `x:`.
# Lo que exige ver todos los documentos juntos esta en `set.rego` (`--combine --namespace jobs_set`).
package main

import rego.v1

namespace := "vectra-identity"

pushgateway_url := "http://pushgateway.vectra-observability.svc:9091"

admin_url := "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/admin/realms/vectra"

token_url := "https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token"

image_repositories := {"registro.banco.internal/vectra/identity-jobs", "kind-registry:5000/vectra/identity-jobs"}

priority_class := "vectra-low"

resources := {
	"requests": {"cpu": "100m", "memory": "256Mi"},
	"limits": {"cpu": "500m", "memory": "512Mi"},
}

# Por CronJob: horario (UTC), ejecutable, el realm montado y el nombre de la cuenta de servicio (el mismo que el CronJob).
jobs := {
	"realm-drift": {"schedule": "0 3 * * *", "script": "/app/realm_drift.py", "realm": true},
	"signing-key-age": {"schedule": "0 * * * *", "script": "/app/signing_key_age.py", "realm": false},
}

common_env := {
	"VECTRA_CLIENT_ID": "keycloak-reader",
	"VECTRA_TOKEN_URL": token_url,
	"VECTRA_CLIENT_KEY_PATH": "/etc/vectra/reader/private-key",
	"VECTRA_CA_BUNDLE": "/etc/vectra/ca/ca.crt",
	"KEYCLOAK_ADMIN_URL": admin_url,
	"PUSHGATEWAY_URL": pushgateway_url,
	"PYTHONDONTWRITEBYTECODE": "1",
}

is_cronjob if input.kind == "CronJob"

pod := input.spec.jobTemplate.spec.template.spec if is_cronjob

# El unico contenedor de la plantilla.
container := pod.containers[0] if is_cronjob

expected_env := object.union(common_env, {"REALM_FILE": "/etc/vectra/realm/realm.yaml"}) if jobs[input.metadata.name].realm

expected_env := common_env if not jobs[input.metadata.name].realm

# regla: cronjob-shape
deny contains msg if {
	is_cronjob
	not input.metadata.name in object.keys(jobs)
	msg := sprintf("cronjob-shape: el CronJob %s no es de la lista", [input.metadata.name])
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
	input.spec.schedule != jobs[input.metadata.name].schedule
	msg := sprintf("schedule: %s corre a las %s, no a las %s (UTC)", [input.metadata.name, input.spec.schedule, jobs[input.metadata.name].schedule])
}

deny contains msg if {
	is_cronjob
	object.get(input.spec, "timeZone", "UTC") != "UTC"
	msg := "schedule: el horario es UTC"
}

# regla: concurrency
deny contains msg if {
	is_cronjob
	object.get(input.spec, "concurrencyPolicy", "") != "Forbid"
	msg := "concurrency: concurrencyPolicy es Forbid"
}

# regla: service-account
deny contains msg if {
	is_cronjob
	object.get(pod, "serviceAccountName", "") != input.metadata.name
	msg := sprintf("service-account: %s usa la cuenta de servicio %s", [input.metadata.name, object.get(pod, "serviceAccountName", "")])
}

# regla: priority
deny contains msg if {
	is_cronjob
	object.get(pod, "priorityClassName", "") != priority_class
	msg := sprintf("priority: la prioridad es %s", [priority_class])
}

# regla: resources
deny contains msg if {
	is_cronjob
	object.get(container, "resources", {}) != resources
	msg := "resources: los recursos son los de INF-U2-06"
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
	msg := sprintf("image: el repositorio %s no es el de identity-jobs", [parts[0]])
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
	container.command != ["python", jobs[input.metadata.name].script]
	msg := sprintf("command: %s ejecuta python %s", [input.metadata.name, jobs[input.metadata.name].script])
}

# regla: env
deny contains msg if {
	is_cronjob
	actual := {e.name: e.value | some e in container.env}
	actual != expected_env
	msg := sprintf("env: las variables de %s no son las del diseno (INF-U2-09)", [input.metadata.name])
}

deny contains msg if {
	is_cronjob
	some e in container.env
	not is_string(object.get(e, "value", null))
	msg := sprintf("env: %s sale de un valor literal, no de otra fuente", [e.name])
}

# regla: volumes
# Los Secrets que crea U02-T07 (`keycloak-reader-client`, `identity-ca`) y, solo en realm-drift, el ConfigMap del realm.
deny contains msg if {
	is_cronjob
	not secret_volume("reader-key", "keycloak-reader-client", "private-key")
	msg := "volumes: la llave sale del Secret keycloak-reader-client, propiedad private-key"
}

deny contains msg if {
	is_cronjob
	not secret_volume("identity-ca", "identity-ca", "ca.crt")
	msg := "volumes: la CA sale del Secret identity-ca, propiedad ca.crt"
}

secret_volume(name, secret, key) if {
	some v in pod.volumes
	v.name == name
	v.secret.secretName == secret
	v.secret.items == [{"key": key, "path": key}]
}

deny contains msg if {
	is_cronjob
	jobs[input.metadata.name].realm
	not realm_volume
	msg := "volumes: realm-drift monta el ConfigMap realm-drift-realm, propiedad realm.yaml"
}

realm_volume if {
	some v in pod.volumes
	v.name == "realm"
	v.configMap.name == "realm-drift-realm"
	v.configMap.items == [{"key": "realm.yaml", "path": "realm.yaml"}]
}

deny contains msg if {
	is_cronjob
	not jobs[input.metadata.name].realm
	some v in pod.volumes
	v.name == "realm"
	msg := "volumes: signing-key-age no monta el realm de Git"
}

deny contains msg if {
	is_cronjob
	allowed := {"reader-key", "identity-ca", "realm"}
	some v in pod.volumes
	not v.name in allowed
	msg := sprintf("volumes: el volumen %s no esta en la lista", [v.name])
}

deny contains msg if {
	is_cronjob
	some m in container.volumeMounts
	object.get(m, "readOnly", false) != true
	msg := sprintf("volumes: el montaje %s es de solo lectura", [m.name])
}

deny contains msg if {
	is_cronjob
	mounted := {m.name | some m in container.volumeMounts}
	declared := {v.name | some v in pod.volumes}
	mounted != declared
	msg := "volumes: los montajes son los volumenes del pod"
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

deny contains msg if {
	is_cronjob
	object.get(pod, "hostNetwork", false)
	msg := "hardening: sin hostNetwork"
}

# regla: native-sidecar
deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec.template.metadata.annotations, "config.alpha.linkerd.io/proxy-enable-native-sidecar", "") != "true"
	msg := sprintf("native-sidecar: %s sin el sidecar nativo de Linkerd", [input.metadata.name])
}

# regla: realm-configmap
deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name != "realm-drift-realm"
	msg := sprintf("realm-configmap: el ConfigMap %s no es el del realm", [input.metadata.name])
}

deny contains msg if {
	input.kind == "ConfigMap"
	object.keys(input.data) != {"realm.yaml"}
	msg := "realm-configmap: el ConfigMap lleva solo realm.yaml"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.namespace != namespace
	msg := sprintf("realm-configmap: el namespace es %s", [namespace])
}

# regla: no-plain-secret
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el render; lo crea el ExternalSecret de U02-T07", [input.metadata.name])
}

# regla: service-account-doc
deny contains msg if {
	input.kind == "ServiceAccount"
	not input.metadata.name in object.keys(jobs)
	msg := sprintf("service-account-doc: la cuenta de servicio %s no es de la lista", [input.metadata.name])
}

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
