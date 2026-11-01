# Reglas de conftest sobre lo renderizado. Equivalen a las de `platform/tests/test_platform.py`,
# y ademas cubren los manifiestos de `platform/rendered/`.
# Cada `# regla: x` tiene sus casos en `tests/x/{pass,fail}.yaml` (platform/tests/rego_fixtures.py lo exige).
package main

import rego.v1

# regla: zone-spread
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.namespace in {"vectra-app", "vectra-edge", "vectra-identity", "vectra-serving", "vectra-mock"}
	not zone_spread(input)
	msg := sprintf("%s sin topologySpreadConstraints por zona", [input.metadata.name])
}

zone_spread(obj) if {
	some constraint in obj.spec.template.spec.topologySpreadConstraints
	constraint.topologyKey == "topology.kubernetes.io/zone"
}

# regla: native-sidecar
# Con `object.get` y una ruta: sin `metadata` en la plantilla la regla falla, no se salta.
deny contains msg if {
	input.kind in {"CronJob", "Job"}
	object.get(pod_annotations(input), "config.alpha.linkerd.io/proxy-enable-native-sidecar", "") != "true"
	msg := sprintf("%s sin el sidecar nativo explicito", [input.metadata.name])
}

pod_annotations(obj) := object.get(obj, ["spec", "jobTemplate", "spec", "template", "metadata", "annotations"], {}) if obj.kind == "CronJob"

pod_annotations(obj) := object.get(obj, ["spec", "template", "metadata", "annotations"], {}) if obj.kind == "Job"

# regla: rbac-wildcards
# Cada campo por separado: una regla sin `resources` (solo `nonResourceURLs`) tambien se revisa.
deny contains msg if {
	input.kind in {"Role", "ClusterRole"}
	some rule in input.rules
	some field in ["verbs", "resources", "apiGroups", "nonResourceURLs"]
	some value in object.get(rule, field, [])
	value in {"*", "/*"}
	msg := sprintf("%s con comodines en %s", [input.metadata.name, field])
}

# regla: k16-verbs
# K16: verbos permitidos del operador de verificacion.
deny contains msg if {
	input.kind in {"Role", "ClusterRole"}
	startswith(input.metadata.name, "vectra-verification-operator")
	some rule in input.rules
	some verb in rule.verbs
	not verb in {"get", "list", "watch", "create"}
	msg := sprintf("K16 con el verbo %s", [verb])
}

# regla: k16-create
deny contains msg if {
	input.kind in {"Role", "ClusterRole"}
	startswith(input.metadata.name, "vectra-verification-operator")
	some rule in input.rules
	"create" in rule.verbs
	not rule.resources == ["pods/portforward"]
	msg := "K16 solo crea pods/portforward"
}

# regla: application-project
deny contains msg if {
	input.kind == "Application"
	input.spec.project == "default"
	msg := sprintf("%s usa el proyecto default", [input.metadata.name])
}

# regla: appproject-wildcard
deny contains msg if {
	input.kind == "AppProject"
	"*" in input.spec.sourceRepos
	msg := "AppProject con comodin en repositorios"
}
