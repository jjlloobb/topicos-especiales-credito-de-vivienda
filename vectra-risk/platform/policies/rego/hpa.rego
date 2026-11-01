# Reglas entre documentos de un mismo render: `conftest test --combine --namespace hpa`.
# Reemplaza la comprobacion de `require-hpa-bounds` al admitir, que depende del orden en que llegan los recursos.
package hpa

import rego.v1

# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
documents contains document if {
	some file in input
	is_array(file.contents)
	some document in file.contents
	is_object(document)
}

documents contains document if {
	some file in input
	is_object(file.contents)
	document := file.contents
}

# regla: deployment-hpa
deny contains msg if {
	some deployment in documents
	deployment.kind == "Deployment"
	not exempt(deployment)
	not has_hpa(deployment)
	msg := sprintf("%s sin HPA en el render ni la anotacion vectra.io/hpa-exempt (NFR-U1-12)", [deployment.metadata.name])
}

exempt(deployment) if object.get(deployment, ["metadata", "annotations", "vectra.io/hpa-exempt"], "") != ""

has_hpa(deployment) if {
	some autoscaler in documents
	autoscaler.kind == "HorizontalPodAutoscaler"
	autoscaler.spec.scaleTargetRef.kind == "Deployment"
	autoscaler.spec.scaleTargetRef.name == deployment.metadata.name
	object.get(autoscaler.metadata, "namespace", "") == object.get(deployment.metadata, "namespace", "")
}

# Lo que `require-spread-and-pdb` exige al admitir, para que falle en el PR y no en el clúster.
# regla: deployment-replicas
deny contains msg if {
	some deployment in documents
	needs_availability(deployment)
	object.get(deployment.spec, "replicas", 1) < 2
	msg := sprintf("%s con menos de 2 replicas (NFR-U1-04)", [deployment.metadata.name])
}

# regla: deployment-pdb
deny contains msg if {
	some deployment in documents
	needs_availability(deployment)
	not has_pdb(deployment)
	msg := sprintf("%s sin PodDisruptionBudget por app.kubernetes.io/name (NFR-U1-04)", [deployment.metadata.name])
}

needs_availability(deployment) if {
	deployment.kind == "Deployment"
	deployment.metadata.namespace in {"vectra-app", "vectra-edge", "vectra-identity", "vectra-serving", "vectra-mock"}
	not inactive(deployment)
}

inactive(deployment) if {
	deployment.metadata.labels["vectra.io/serving-state"] == "inactivo"
	exempt(deployment)
}

has_pdb(deployment) if {
	some budget in documents
	budget.kind == "PodDisruptionBudget"
	object.get(budget.metadata, "namespace", "") == deployment.metadata.namespace
	name := deployment.spec.template.metadata.labels["app.kubernetes.io/name"]
	budget.spec.selector.matchLabels["app.kubernetes.io/name"] == name
}
