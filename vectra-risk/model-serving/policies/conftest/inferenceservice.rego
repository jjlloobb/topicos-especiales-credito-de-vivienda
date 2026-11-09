# Reglas por documento sobre el render del chart de U6 (Paso 6): `conftest test --policy model-serving/policies/conftest <render>`.
# Cada `# regla: <id>` tiene en `tests/unit/test_chart.py` un caso que falla con una mutacion del render. Los mensajes empiezan por el id.
# Diseño que cubren: NFR-U6-02, NFR-U6-11, NFR-U6-20, NFR-U6-22 y NFR-U6-32; P-U6-02 y P-U6-04; INF-U6-01 y INF-U6-02.
# El perfil se deduce del namespace y de la etiqueta `vectra.io/serving-state`, no de la anotacion `vectra.io/profile` (que informa).
package main

import rego.v1

is_isvc if input.kind == "InferenceService"

staging if input.metadata.namespace == "vectra-staging"

inactive if input.metadata.labels["vectra.io/serving-state"] == "inactivo"

active if {
	input.metadata.namespace == "vectra-serving"
	not inactive
}

# Los componentes que declara la plantilla: el predictor siempre y el explicador salvo en staging.
components := {c | some c in {"predictor", "explainer"}; input.spec[c]}

container(c) := input.spec[c].containers[0]

env_value(c, name) := value if {
	some e in container(c).env
	e.name == name
	value := e.value
} else := ""

source_uri(c) := object.get(input.spec[c].annotations, "internal.serving.kserve.io/storage-initializer-sourceuri", "")

version := input.metadata.annotations["vectra.io/model-version-id"]

# regla: name-from-version
deny contains msg if {
	is_isvc
	expected := sprintf("isvc-%s", [substring(version, count(version) - 8, 8)])
	input.metadata.name != expected
	msg := sprintf("name-from-version: %s no sale del model_version_id %s (esperado %s)", [input.metadata.name, version, expected])
}

# regla: name-from-version
deny contains msg if {
	is_isvc
	not regex.match(`^isvc-[0-9a-f]{8}$`, input.metadata.name)
	msg := sprintf("name-from-version: %s no es isvc-<8 hex>", [input.metadata.name])
}

# regla: version-annotation-equal
deny contains msg if {
	is_isvc
	some c in components
	object.get(input.spec[c].annotations, "vectra.io/model-version-id", "") != version
	msg := sprintf("version-annotation-equal: %s lleva otra anotacion vectra.io/model-version-id que el InferenceService", [c])
}

# regla: storage-uri-equal
deny contains msg if {
	is_isvc
	some c in components
	env_value(c, "STORAGE_URI") != source_uri(c)
	msg := sprintf("storage-uri-equal: %s: STORAGE_URI y la anotacion del storage initializer difieren", [c])
}

# regla: storage-uri-equal
deny contains msg if {
	is_isvc
	count(components) == 2
	source_uri("predictor") != source_uri("explainer")
	msg := "storage-uri-equal: predictor y explicador con distinto storageUri"
}

# regla: no-adversarial-in-serving
deny contains msg if {
	is_isvc
	input.metadata.namespace == "vectra-serving"
	some c in components
	regex.match(`(^|/)adversarial(/|$)`, source_uri(c))
	msg := sprintf("no-adversarial-in-serving: %s sirve una ruta adversarial/ en vectra-serving", [c])
}

# regla: active-min-replicas
deny contains msg if {
	is_isvc
	active
	some c in components
	object.get(input.spec[c], "minReplicas", 0) < 2
	msg := sprintf("active-min-replicas: el activo con %s por debajo de 2 replicas (NFR-U1-04)", [c])
}

# regla: active-scaling
deny contains msg if {
	is_isvc
	active
	bounds := {"predictor": [2, 4], "explainer": [2, 6]}
	some c, limits in bounds
	not [input.spec[c].minReplicas, input.spec[c].maxReplicas] == limits
	msg := sprintf("active-scaling: %s debe escalar de %d a %d replicas", [c, limits[0], limits[1]])
}

# regla: active-scaling
deny contains msg if {
	is_isvc
	active
	some c in components
	metric := object.get(input.spec[c], ["autoScaling", "metrics", 0, "resource"], {})
	not metric.name == "cpu"
	msg := sprintf("active-scaling: %s sin HPA por CPU", [c])
}

# regla: active-scaling
deny contains msg if {
	is_isvc
	active
	some c in components
	metric := object.get(input.spec[c], ["autoScaling", "metrics", 0, "resource"], {})
	metric.name == "cpu"
	not metric.target.averageUtilization == 60
	msg := sprintf("active-scaling: %s con la CPU en otro valor que el 60 %%", [c])
}

# regla: active-scaling
deny contains msg if {
	is_isvc
	active
	some c in components
	behavior := object.get(input.spec[c], ["autoScaling", "behavior"], {})
	not [behavior.scaleUp.stabilizationWindowSeconds, behavior.scaleDown.stabilizationWindowSeconds] == [60, 300]
	msg := sprintf("active-scaling: %s sin estabilizacion de 60 s hacia arriba y 300 s hacia abajo", [c])
}

# regla: active-spread
deny contains msg if {
	is_isvc
	active
	some c in components
	not zone_spread(input.spec[c])
	msg := sprintf("active-spread: %s sin topologySpreadConstraints por topology.kubernetes.io/zone", [c])
}

zone_spread(component) if {
	some t in component.topologySpreadConstraints
	t.topologyKey == "topology.kubernetes.io/zone"
}

# regla: priority-by-profile
deny contains msg if {
	is_isvc
	expected := expected_priority
	some c in components
	object.get(input.spec[c], "priorityClassName", "") != expected
	msg := sprintf("priority-by-profile: %s con %s, no %s", [c, object.get(input.spec[c], "priorityClassName", ""), expected])
}

expected_priority := "vectra-high" if active

expected_priority := "vectra-normal" if inactive

expected_priority := "vectra-low" if staging

# regla: inactive-contract
deny contains msg if {
	is_isvc
	inactive
	some c in components
	not [input.spec[c].minReplicas, input.spec[c].maxReplicas] == [1, 1]
	msg := sprintf("inactive-contract: el inactivo con %s fuera de 1 replica fija", [c])
}

# regla: inactive-contract
deny contains msg if {
	is_isvc
	inactive
	not input.metadata.annotations["vectra.io/hpa-exempt"]
	msg := "inactive-contract: el inactivo sin la anotacion vectra.io/hpa-exempt"
}

# regla: inactive-contract
deny contains msg if {
	is_isvc
	inactive
	some c in components
	input.spec[c].autoScaling
	msg := sprintf("inactive-contract: el inactivo con HPA en %s", [c])
}

# regla: inactive-contract
deny contains msg if {
	is_isvc
	inactive
	some c in components
	object.get(input.spec[c].labels, "vectra.io/serving-state", "") != "inactivo"
	msg := sprintf("inactive-contract: el pod de %s sin la etiqueta vectra.io/serving-state: inactivo", [c])
}

# regla: inactive-contract
deny contains msg if {
	is_isvc
	not active
	not input.metadata.annotations["serving.kserve.io/autoscalerClass"] == "none"
	msg := "inactive-contract: una version de 1 replica fija debe declarar serving.kserve.io/autoscalerClass: none (sin HPA)"
}

# regla: active-no-exemption
deny contains msg if {
	is_isvc
	active
	input.metadata.annotations["vectra.io/hpa-exempt"]
	msg := "active-no-exemption: el activo no lleva vectra.io/hpa-exempt (el rollback la quita)"
}

# regla: staging-contract
deny contains msg if {
	is_isvc
	staging
	input.spec.explainer
	msg := "staging-contract: staging solo tiene predictor (INF-U4-05; F30 y F46)"
}

# regla: staging-contract
deny contains msg if {
	is_isvc
	staging
	not [input.spec.predictor.minReplicas, input.spec.predictor.maxReplicas] == [1, 1]
	msg := "staging-contract: staging con 1 replica fija"
}

# regla: resources-by-profile
deny contains msg if {
	is_isvc
	some c in components
	expected := expected_resources[c]
	not container(c).resources == expected
	msg := sprintf("resources-by-profile: %s con recursos distintos de INF-U6-01", [c])
}

expected_resources := {
	"predictor": {"requests": {"cpu": "500m", "memory": "512Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
	"explainer": {"requests": {"cpu": "500m", "memory": "512Mi"}, "limits": {"cpu": "2", "memory": "1Gi"}},
} if {
	not staging
}

expected_resources := {"predictor": {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}} if staging

# regla: component-identity
deny contains msg if {
	is_isvc
	some c in components
	object.get(input.spec[c].labels, "vectra.io/component", "") != c
	msg := sprintf("component-identity: el pod de %s sin vectra.io/component=%s (flows.yaml)", [c, c])
}

# regla: component-identity
deny contains msg if {
	is_isvc
	some c in components
	object.get(input.spec[c], "serviceAccountName", "") != "kserve-model"
	msg := sprintf("component-identity: %s sin la ServiceAccount kserve-model", [c])
}

# regla: component-identity
deny contains msg if {
	is_isvc
	some c in components
	object.get(input.spec[c].labels, "app.kubernetes.io/name", "") != sprintf("%s-%s", [input.metadata.name, c])
	msg := sprintf("component-identity: %s sin app.kubernetes.io/name=<isvc>-%s (el PDB lo usa)", [c, c])
}

# regla: probes-and-volume
deny contains msg if {
	is_isvc
	some c in components
	k := container(c)
	not probes_ok(k)
	msg := sprintf("probes-and-volume: %s fuera de las sondas de INF-U6-01 (startup 5 s x 30, readiness 5 s, liveness 10 s)", [c])
}

probes_ok(k) if {
	k.startupProbe.periodSeconds == 5
	k.startupProbe.failureThreshold == 30
	k.readinessProbe.periodSeconds == 5
	k.livenessProbe.periodSeconds == 10
}

# regla: probes-and-volume
deny contains msg if {
	is_isvc
	some c in components
	not package_volume(c)
	msg := sprintf("probes-and-volume: %s sin emptyDir de 1 GiB para el paquete", [c])
}

package_volume(c) if {
	some v in input.spec[c].volumes
	v.emptyDir.sizeLimit == "1Gi"
}

# regla: container-security
deny contains msg if {
	is_isvc
	some c in components
	not regex.match(`@sha256:[0-9a-f]{64}$`, object.get(container(c), "image", ""))
	msg := sprintf("container-security: %s con una imagen sin digest", [c])
}

# regla: container-security
deny contains msg if {
	is_isvc
	some c in components
	s := object.get(container(c), "securityContext", {})
	not secure(s)
	msg := sprintf("container-security: %s sin runAsNonRoot, readOnlyRootFilesystem o con privilegios", [c])
}

secure(s) if {
	s.runAsNonRoot == true
	s.readOnlyRootFilesystem == true
	s.allowPrivilegeEscalation == false
	not s.privileged
}
