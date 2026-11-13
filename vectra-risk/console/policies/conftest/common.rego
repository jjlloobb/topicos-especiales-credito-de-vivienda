# Reglas de conftest sobre el render de los dos charts de U10 (Paso 18; INF-U10-01, 03, 04, 06; NFR-U10-10, 12, 20, 22, 45). Se corren sobre el render de cada entorno y de cada chart.
# Cada `# regla: x` tiene un caso que falla en console/bff/tests/unit/test_chart.py, y cada mensaje empieza por `x:`.
# Por documento (`conftest test`): los paquetes `main` de este directorio (`common`, `bff`, `spa`, `config`). Lo que exige ver todo el render junto esta en `set.rego`
# (`--combine --namespace console_set`). Los datos del entorno y del realm de U2 llegan por `--data` (`console/bff/tools/chart_data.py`): `data.env` y `data.realm`.
package main

import rego.v1

pieces := {
	"console-bff": {"namespace": "vectra-app", "user": 65532, "priority": "vectra-high", "criticality": "high"},
	"console-spa": {"namespace": "vectra-edge", "user": 101, "priority": "vectra-normal", "criticality": "medium"},
}

is_deployment if {
	input.kind == "Deployment"
	input.metadata.name in object.keys(pieces)
}

piece := pieces[input.metadata.name] if is_deployment

pod := input.spec.template.spec if is_deployment

container := pod.containers[0] if is_deployment

# regla: forbidden-kinds
# Ninguno de los dos charts crea un `Secret` (el BFF usa el token del usuario; la SPA es publica), ni la politica de red o de enrutado (son de U1 y de U2), ni reglas de alerta (Paso 19, T2).
deny contains msg if {
	input.kind in {"Secret", "ExternalSecret", "PrometheusRule", "Server", "HTTPRoute", "AuthorizationPolicy", "NetworkPolicy"}
	msg := sprintf("forbidden-kinds: el chart de U10 no declara %s %s", [input.kind, input.metadata.name])
}

# regla: hardening
deny contains msg if {
	is_deployment
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	is_deployment
	not pod.securityContext.runAsUser == piece.user
	msg := sprintf("hardening: runAsUser %d, el de la imagen de %s", [piece.user, input.metadata.name])
}

deny contains msg if {
	is_deployment
	not pod.securityContext.runAsGroup == piece.user
	msg := sprintf("hardening: runAsGroup %d, el de la imagen de %s", [piece.user, input.metadata.name])
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

# regla: pod-token
deny contains msg if {
	is_deployment
	not pod.automountServiceAccountToken == false
	msg := "pod-token: automountServiceAccountToken false en el pod"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	not input.automountServiceAccountToken == false
	msg := "pod-token: automountServiceAccountToken false en la cuenta de servicio"
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
	not endswith(parts[0], concat("", ["/vectra/", input.metadata.name]))
	msg := sprintf("image: el repositorio %s no es el de %s", [parts[0], input.metadata.name])
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
	input.kind in {"Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ConfigMap", "ServiceMonitor", "HorizontalPodAutoscaler"}
	expected := pieces[trim_suffix(input.metadata.labels["app.kubernetes.io/name"], "-config")].namespace
	not input.metadata.namespace == expected
	msg := sprintf("namespace: %s %s va en %s, no en %s", [input.kind, input.metadata.name, input.metadata.namespace, expected])
}

# regla: priority
deny contains msg if {
	is_deployment
	not object.get(pod, "priorityClassName", "") == piece.priority
	msg := sprintf("priority: %s es %s, no %s (NFR-U10-20)", [input.metadata.name, piece.priority, object.get(pod, "priorityClassName", "")])
}

# regla: criticality
deny contains msg if {
	is_deployment
	not input.metadata.labels["vectra.io/criticality"] == piece.criticality
	msg := sprintf("criticality: vectra.io/criticality %s en %s (NFR-U10-20)", [piece.criticality, input.metadata.name])
}

# regla: spread
deny contains msg if {
	is_deployment
	zones := [t | some t in object.get(pod, "topologySpreadConstraints", []); t.topologyKey == "topology.kubernetes.io/zone"]
	count(zones) == 0
	msg := "spread: reparto por zona (topology.kubernetes.io/zone) (NFR-U10-22)"
}

# regla: pdb
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	not input.spec.minAvailable == 1
	msg := sprintf("pdb: minAvailable 1 en %s (NFR-U10-22)", [input.metadata.name])
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	not input.spec.selector.matchLabels == {"app.kubernetes.io/name": input.metadata.name}
	msg := sprintf("pdb: el selector de %s es por app.kubernetes.io/name", [input.metadata.name])
}

# regla: no-subpath
# Los dos ConfigMap se montan como directorio: con `subPath` el kubelet no los actualiza.
deny contains msg if {
	is_deployment
	some m in container.volumeMounts
	m.subPath
	msg := sprintf("no-subpath: el montaje %s usa subPath", [m.name])
}

# regla: read-only-mounts
deny contains msg if {
	is_deployment
	some m in container.volumeMounts
	not m.name == "tmp"
	not m.readOnly == true
	msg := sprintf("read-only-mounts: el montaje %s (%s) va de solo lectura", [m.name, m.mountPath])
}

# regla: no-inline-env
# Las variables del BFF llegan del ConfigMap (`envFrom`), y las constantes del codigo no son variables (INF-U10-01).
deny contains msg if {
	is_deployment
	container.env
	msg := "no-inline-env: ninguna variable en el Deployment; salen del ConfigMap"
}

# regla: service-account-name
deny contains msg if {
	is_deployment
	not pod.serviceAccountName == input.metadata.name
	msg := sprintf("service-account-name: la cuenta de servicio de %s es la de flows.yaml", [input.metadata.name])
}

# regla: data-env
# Los datos del entorno llegan por `--data` (`console/bff/tools/chart_data.py`): sin ellos, las reglas que dependen del entorno no dirian nada.
known_env if data.env in {"kind", "staging", "prod"}

deny contains msg if {
	input.kind == "Deployment"
	not known_env
	msg := "data-env: faltan los datos del entorno (--data con env kind, staging o prod)"
}
