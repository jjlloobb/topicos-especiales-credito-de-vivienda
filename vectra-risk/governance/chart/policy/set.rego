# Lo que exige ver todos los documentos del render juntos: `conftest test --combine --namespace chart_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package chart_set

import rego.v1

# Un arreglo, no un conjunto: un documento repetido cuenta dos veces.
listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

# regla: documents-exact
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas y nada de menos (Pasos 13 y 16 acotados a la demo).
expected_documents := {
	["Deployment", "governance-service", "vectra-app"],
	["Service", "governance-service", "vectra-app"],
	["HorizontalPodAutoscaler", "governance-service", "vectra-app"],
	["PodDisruptionBudget", "governance-service", "vectra-app"],
	["ServiceMonitor", "governance-service", "vectra-app"],
	["Job", "governance-migration", "vectra-app"],
	["ServiceAccount", "governance-service", "vectra-app"],
	["ServiceAccount", "migration-governance", "vectra-app"],
	["Role", "governance-validation-jobs", "vectra-staging"],
	["RoleBinding", "governance-validation-jobs", "vectra-staging"],
	["ServiceAccount", "model-validation-job", "vectra-staging"],
	["ExternalSecret", "model-validation-job-client", "vectra-staging"],
	["ExternalSecret", "governance-service-client", "vectra-app"],
}

actual_documents := [[d.kind, d.metadata.name, object.get(d.metadata, "namespace", "")] | some d in listed]

deny contains msg if {
	some doc in actual_documents
	not doc in expected_documents
	msg := sprintf("documents-exact: documento fuera de la lista: %s %s (%s)", doc)
}

deny contains msg if {
	some expected in expected_documents
	not expected in actual_documents
	msg := sprintf("documents-exact: falta %s %s (%s)", expected)
}

deny contains msg if {
	count(actual_documents) != count(expected_documents)
	msg := sprintf("documents-exact: %d documentos, no %d (hay repetidos)", [count(actual_documents), count(expected_documents)])
}

# regla: service-account-exists
# Cada CronJob, Deployment y Job usa una cuenta de servicio que el render declara.
pod_specs contains [d.metadata.name, d.metadata.namespace, d.spec.template.spec.serviceAccountName] if {
	some d in listed
	d.kind in {"Deployment", "Job"}
}

deny contains msg if {
	some [workload, namespace, name] in pod_specs
	not [name, namespace] in {[d.metadata.name, d.metadata.namespace] | some d in listed; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [workload, name])
}

# regla: no-plain-secret
# El chart no crea ningun Secret: las credenciales salen de los Secrets de U1 (`pg-role-gov-*`, `minio-governance`). Los unicos ExternalSecret son el de la
# llave del model-validation-job en vectra-staging (U04-T05) y el de la llave del propio servicio en vectra-app (U04-T08); el del S3 del banco esta diferido (T5).
deny contains msg if {
	some d in listed
	d.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el chart", [d.metadata.name])
}

deny contains msg if {
	some d in listed
	d.kind == "ExternalSecret"
	not [d.metadata.name, d.metadata.namespace] in {["model-validation-job-client", "vectra-staging"], ["governance-service-client", "vectra-app"]}
	msg := sprintf("no-plain-secret: el ExternalSecret %s no va en el chart (solo el del model-validation-job y el del governance-service)", [d.metadata.name])
}

# regla: servicemonitor-port
# El ServiceMonitor apunta al puerto del Service que es el de metricas (8081), no al del contrato (8080).
metrics_port_names := {p.name |
	some s in listed
	s.kind == "Service"
	s.metadata.name == "governance-service"
	some p in s.spec.ports
	p.port == 8081
}

deny contains msg if {
	some monitor in listed
	monitor.kind == "ServiceMonitor"
	some endpoint in monitor.spec.endpoints
	not object.get(endpoint, "port", "") in metrics_port_names
	msg := sprintf("servicemonitor-port: el endpoint apunta a %v; el puerto de metricas (8081) del Service se llama %v", [object.get(endpoint, "port", "ausente"), metrics_port_names])
}

# regla: service-port-names
# Los nombres de puerto del Service existen en el contenedor (el `targetPort` por nombre).
deny contains msg if {
	some s in listed
	s.kind == "Service"
	some p in s.spec.ports
	container_ports := {cp.name | some d in listed; d.kind == "Deployment"; some c in d.spec.template.spec.containers; some cp in c.ports}
	not p.targetPort in container_ports
	msg := sprintf("service-port-names: el targetPort %v del Service no existe en el contenedor", [p.targetPort])
}

# regla: service-pdb
# Cada Deployment tiene un PDB y un HPA en el render (NFR-U1-04, NFR-U1-12; `require-spread-and-pdb` y `require-hpa-bounds`).
deny contains msg if {
	some d in listed
	d.kind == "Deployment"
	name := d.spec.template.metadata.labels["app.kubernetes.io/name"]
	not name in {b.spec.selector.matchLabels["app.kubernetes.io/name"] | some b in listed; b.kind == "PodDisruptionBudget"}
	msg := sprintf("service-pdb: %s sin PodDisruptionBudget por app.kubernetes.io/name", [d.metadata.name])
}

deny contains msg if {
	some d in listed
	d.kind == "Deployment"
	not d.metadata.name in {h.spec.scaleTargetRef.name | some h in listed; h.kind == "HorizontalPodAutoscaler"}
	msg := sprintf("service-pdb: %s sin HorizontalPodAutoscaler", [d.metadata.name])
}
