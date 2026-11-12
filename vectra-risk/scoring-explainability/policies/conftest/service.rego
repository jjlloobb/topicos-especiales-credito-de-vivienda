# Reglas de conftest sobre el render del chart de U7 (Paso 15 acotado a la demo; INF-U7-01, 03, 04, 05; P-U7-06; NFR-U7-20, 30), por documento
# (`conftest test`). Cada `# regla: x` tiene un caso que falla en scoring-explainability/tests/unit/test_chart.py, y cada mensaje empieza por `x:`.
# Lo que exige ver todo el render junto esta en `set.rego` (`--combine --namespace chart_set`).
package main

import rego.v1

namespace := "vectra-app"

services := {"scoring-service", "explainability-service"}

# El unico conjunto de variables de entorno de cada servicio (INF-U7-04): las de `REQUIRED_ENV` de su `app.py`, las de U0 (F50) y la telemetria.
common_env := {"VECTRA_CLIENT_ID", "VECTRA_CLIENT_KEY_PATH", "VECTRA_TOKEN_URL", "VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE", "VECTRA_OTLP_ENDPOINT"}

service_env := {
	"scoring-service": (common_env | {"SCORING_GOVERNANCE_URL", "SCORING_EXPLAINABILITY_URL", "SCORING_REGISTRY_URL", "SCORING_PREDICTOR_URL_TEMPLATE"}),
	"explainability-service": (common_env | {"EXPLAINABILITY_GOVERNANCE_URL", "EXPLAINABILITY_REGISTRY_URL", "EXPLAINABILITY_EXPLAINER_URL_TEMPLATE"}),
}

# Nombres de los presupuestos de `config.py` (INF-U7-04): ni estos ni nada con su forma pueden ser variables de entorno.
budget_words := `(?i)(BUDGET|TIMEOUT|DEADLINE|ATTEMPT|JITTER|POOL|BREAKER|MARGIN|CEILING|TTL|GRACE|RETRIES|WINDOW|OPEN_FOR|LRU)`

resources := {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}

is_service if {
	input.kind == "Deployment"
	input.metadata.name in services
}

service_pod := input.spec.template.spec if is_service

service_container := service_pod.containers[0] if is_service

all_containers contains c if {
	is_service
	some c in service_pod.containers
}

env_names(container) := {e.name | some e in container.env}

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
	msg := sprintf("no-plain-secret: %s sale de un Secret o ConfigMap por entorno; la llave se monta de solo lectura", [e.name])
}

# regla: budget-env
# INF-U7-04: el chart no define variables con los nombres de los presupuestos (`PRE_REGISTRY_BUDGET`, timeouts, pools, umbrales del breaker).
deny contains msg if {
	some c in all_containers
	some e in c.env
	regex.match(budget_words, e.name)
	msg := sprintf("budget-env: %s parece un presupuesto; son constantes de config.py, no configuracion (INF-U7-04)", [e.name])
}

# regla: service-env
# Solo URLs, la identidad ante Keycloak y la telemetria: las variables de `REQUIRED_ENV` de cada servicio y las de U0.
deny contains msg if {
	is_service
	some e in service_container.env
	not e.name in service_env[input.metadata.name]
	msg := sprintf("service-env: %s no es una variable de %s (INF-U7-04)", [e.name, input.metadata.name])
}

deny contains msg if {
	is_service
	missing := service_env[input.metadata.name] - env_names(service_container)
	count(missing) > 0
	msg := sprintf("service-env: a %s le faltan %v", [input.metadata.name, missing])
}

# regla: service-shape
deny contains msg if {
	is_service
	not count(service_pod.containers) == 1
	msg := "service-shape: el pod lleva un solo contenedor"
}

deny contains msg if {
	is_service
	object.get(input.spec, "replicas", 1) < 2
	msg := "service-shape: 2 replicas o mas (NFR-U7-20; test_kind_profile.py cuenta spec.replicas)"
}

deny contains msg if {
	is_service
	object.get(service_pod, "serviceAccountName", "") != input.metadata.name
	msg := sprintf("service-shape: la cuenta de servicio es %s (flows.yaml)", [input.metadata.name])
}

deny contains msg if {
	is_service
	object.get(input.spec.template.metadata.labels, "app.kubernetes.io/name", "") != input.metadata.name
	msg := sprintf("service-shape: el pod lleva app.kubernetes.io/name: %s (flows.yaml, PDB)", [input.metadata.name])
}

deny contains msg if {
	is_service
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "high"
	msg := "service-shape: vectra.io/criticality: high"
}

# regla: service-rollout
deny contains msg if {
	is_service
	input.spec.strategy != {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
	msg := "service-rollout: RollingUpdate con maxSurge 1 y maxUnavailable 0 (INF-U7-02)"
}

# regla: service-priority
deny contains msg if {
	is_service
	object.get(service_pod, "priorityClassName", "") != "vectra-high"
	msg := sprintf("service-priority: la prioridad es vectra-high, no %s (INF-U7-01)", [object.get(service_pod, "priorityClassName", "")])
}

# regla: service-spread
deny contains msg if {
	is_service
	zones := [t | some t in object.get(service_pod, "topologySpreadConstraints", []); t.topologyKey == "topology.kubernetes.io/zone"]
	count(zones) == 0
	msg := "service-spread: topologySpreadConstraints por topology.kubernetes.io/zone (NFR-U1-04)"
}

# regla: service-resources
deny contains msg if {
	is_service
	service_container.resources != resources
	msg := "service-resources: requests de 250m / 256Mi y limits de 1 CPU / 512Mi (INF-U7-01)"
}

# regla: service-prestop
# INF-U7-03: `preStop.sleep` de 5 s.
deny contains msg if {
	is_service
	object.get(service_container, ["lifecycle", "preStop", "sleep", "seconds"], 0) != 5
	msg := "service-prestop: lifecycle.preStop.sleep.seconds es 5 (INF-U7-03)"
}

# regla: service-grace
# INF-U7-03: 20 s cubren 5 + 10 + margen y superan el peor caso de 6,1 s (P-U7-02).
deny contains msg if {
	is_service
	object.get(service_pod, "terminationGracePeriodSeconds", 30) < 20
	msg := sprintf("service-grace: terminationGracePeriodSeconds es de al menos 20, no %v (INF-U7-03)", [object.get(service_pod, "terminationGracePeriodSeconds", 30)])
}

deny contains msg if {
	is_service
	not "terminationGracePeriodSeconds" in object.keys(service_pod)
	msg := "service-grace: terminationGracePeriodSeconds esta declarado (INF-U7-03)"
}

# regla: service-probes
# INF-U7-01: readiness `/readyz` cada 5 s y liveness cada 10 s, las dos en 8081; sin `startupProbe` (NFR-U7-21). La liveness es `/healthz`:
# es la ruta que sirve `vectra_common.ops_server` (U0); INF-U7-01 la llama `/livez`.
deny contains msg if {
	is_service
	object.get(service_container, ["readinessProbe", "httpGet", "path"], "") != "/readyz"
	msg := "service-probes: la readiness es /readyz"
}

deny contains msg if {
	is_service
	object.get(service_container, ["livenessProbe", "httpGet", "path"], "") != "/healthz"
	msg := "service-probes: la liveness es /healthz (la ruta que sirve ops_server)"
}

deny contains msg if {
	is_service
	some probe in ["readinessProbe", "livenessProbe"]
	object.get(service_container, [probe, "httpGet", "port"], "") != "metrics"
	msg := sprintf("service-probes: %s apunta al puerto de operacion (metrics, 8081)", [probe])
}

deny contains msg if {
	is_service
	object.get(service_container, ["readinessProbe", "periodSeconds"], 0) != 5
	msg := "service-probes: readinessProbe cada 5 s (INF-U7-01)"
}

deny contains msg if {
	is_service
	object.get(service_container, ["livenessProbe", "periodSeconds"], 0) != 10
	msg := "service-probes: livenessProbe cada 10 s (INF-U7-01)"
}

deny contains msg if {
	is_service
	service_container.startupProbe
	msg := "service-probes: sin startupProbe; la precarga del diccionario no bloquea el arranque (NFR-U7-21)"
}

# regla: service-ports
deny contains msg if {
	is_service
	ports := {[p.name, p.containerPort] | some p in service_container.ports}
	ports != {["http", 8080], ["metrics", 8081]}
	msg := "service-ports: 8080 (http) y 8081 (metrics)"
}

# regla: service-sidecar
# P-U7-06: sidecar nativo de Linkerd, para que el proxy termine despues de la app (INF-U7-03).
deny contains msg if {
	is_service
	object.get(input.spec.template.metadata, ["annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "") != "true"
	msg := "service-sidecar: el pod lleva config.alpha.linkerd.io/proxy-enable-native-sidecar: \"true\" (P-U7-06)"
}

# regla: service-identity
deny contains msg if {
	is_service
	e := [e | some e in service_container.env; e.name == "VECTRA_CLIENT_ID"][0]
	e.value != input.metadata.name
	msg := sprintf("service-identity: VECTRA_CLIENT_ID es %s", [input.metadata.name])
}

# regla: workload-image
# Por digest y del repositorio del servicio.
deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	not count(parts) == 2
	msg := sprintf("workload-image: la imagen %s va por digest", [c.image])
}

deny contains msg if {
	is_service
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not endswith(parts[0], concat("/", ["/vectra", input.metadata.name]))
	msg := sprintf("workload-image: el repositorio %s no es el de %s", [parts[0], input.metadata.name])
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("workload-image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: hardening
deny contains msg if {
	is_service
	not service_pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	is_service
	not service_pod.securityContext.runAsUser == 65532
	msg := "hardening: runAsUser 65532, el de la imagen"
}

deny contains msg if {
	is_service
	not service_pod.securityContext.runAsGroup == 65532
	msg := "hardening: runAsGroup 65532, el de la imagen"
}

deny contains msg if {
	is_service
	not service_pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	some c in all_containers
	c.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

deny contains msg if {
	is_service
	some v in object.get(service_pod, "volumes", [])
	not v.emptyDir
	not v.name in {"keycloak-ca", "service-identity"}
	msg := sprintf("hardening: el volumen %s no es un emptyDir (sin hostPath; solo la CA de Keycloak y la llave del servicio)", [v.name])
}

deny contains msg if {
	is_service
	some v in object.get(service_pod, "volumes", [])
	v.hostPath
	msg := sprintf("hardening: el volumen %s es hostPath", [v.name])
}

# regla: read-only-mounts
# La llave `private_key_jwt` y la CA se montan de solo lectura.
deny contains msg if {
	some c in all_containers
	some m in c.volumeMounts
	not m.readOnly == true
	msg := sprintf("read-only-mounts: el montaje %s (%s) va de solo lectura", [m.name, m.mountPath])
}

# regla: namespace
deny contains msg if {
	input.kind in {"Deployment", "Service", "HorizontalPodAutoscaler", "PodDisruptionBudget", "ServiceAccount", "ExternalSecret", "ServiceMonitor"}
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

# regla: service-doc
# Cada Service se llama como su Deployment y expone 8080 y 8081.
deny contains msg if {
	input.kind == "Service"
	not input.metadata.name in services
	msg := sprintf("service-doc: el Service %s no es de U7", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	ports := {p.port | some p in input.spec.ports}
	ports != {8080, 8081}
	msg := "service-doc: el Service expone 8080 y 8081"
}

# regla: hpa-doc
# INF-U7-01: de 2 a 6 replicas por CPU al 70 %, con estabilizacion de 60 s hacia arriba y 300 s hacia abajo.
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.scaleTargetRef.name in services
	msg := "hpa-doc: el HPA escala un Deployment de U7"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.minReplicas != 2
	msg := sprintf("hpa-doc: minReplicas es 2, no %v", [input.spec.minReplicas])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.maxReplicas != 6
	msg := sprintf("hpa-doc: maxReplicas es 6, no %v", [input.spec.maxReplicas])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	metrics := [m | some m in input.spec.metrics; m.type == "Resource"; m.resource.name == "cpu"; m.resource.target.type == "Utilization"; m.resource.target.averageUtilization == 70]
	count(metrics) != 1
	msg := "hpa-doc: una sola metrica, CPU al 70 % de utilizacion"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	object.get(input.spec, ["behavior", "scaleUp", "stabilizationWindowSeconds"], -1) != 60
	msg := "hpa-doc: estabilizacion de 60 s hacia arriba"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	object.get(input.spec, ["behavior", "scaleDown", "stabilizationWindowSeconds"], -1) != 300
	msg := "hpa-doc: estabilizacion de 300 s hacia abajo"
}

# regla: pdb-doc
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	not object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") in services
	msg := "pdb-doc: el PDB selecciona por app.kubernetes.io/name uno de los dos servicios"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	object.get(input.spec, "minAvailable", 0) != 1
	msg := "pdb-doc: minAvailable es 1"
}

# regla: servicemonitor-doc
deny contains msg if {
	input.kind == "ServiceMonitor"
	not object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") in services
	msg := "servicemonitor-doc: selecciona el Service de uno de los dos servicios"
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	some endpoint in input.spec.endpoints
	object.get(endpoint, "honorLabels", false) != true
	msg := "servicemonitor-doc: honorLabels: true (shared-infrastructure.md §1)"
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	count(input.spec.endpoints) != 1
	msg := "servicemonitor-doc: un solo endpoint, el de metricas"
}
