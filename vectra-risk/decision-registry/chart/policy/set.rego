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
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas y nada de menos (Pasos 12, 13 y 15 acotados a la demo).
expected_documents := {
	["CronJob", "registry-aggregator", "vectra-app"],
	["Deployment", "decision-registry-service", "vectra-app"],
	["Service", "decision-registry-service", "vectra-app"],
	["HorizontalPodAutoscaler", "decision-registry-service", "vectra-app"],
	["PodDisruptionBudget", "decision-registry-service", "vectra-app"],
	["ServiceMonitor", "decision-registry-service", "vectra-app"],
	["Job", "registry-migration", "vectra-app"],
	["ConfigMap", "decision-registry-checkpoint", "vectra-app"],
	["ServiceAccount", "migration-registry", "vectra-app"],
	["ServiceAccount", "decision-registry-service", "vectra-app"],
	["ServiceAccount", "registry-checkpoint", "vectra-app"],
	["ServiceAccount", "registry-archive", "vectra-app"],
	["ServiceAccount", "registry-verify", "vectra-app"],
	["ServiceAccount", "registry-aggregator", "vectra-app"],
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
pod_specs contains [d.metadata.name, d.metadata.namespace, d.spec.jobTemplate.spec.template.spec.serviceAccountName] if {
	some d in listed
	d.kind == "CronJob"
}

pod_specs contains [d.metadata.name, d.metadata.namespace, d.spec.template.spec.serviceAccountName] if {
	some d in listed
	d.kind in {"Deployment", "Job"}
}

deny contains msg if {
	some [workload, namespace, name] in pod_specs
	not [name, namespace] in {[d.metadata.name, d.metadata.namespace] | some d in listed; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [workload, name])
}

# regla: no-external-secret
# Las credenciales de la base salen de los Secrets de U1; el chart no crea ninguno ni un ExternalSecret (el del S3 del banco esta diferido).
deny contains msg if {
	some d in listed
	d.kind in {"ExternalSecret", "Secret"}
	msg := sprintf("no-external-secret: %s %s no va en el chart", [d.kind, d.metadata.name])
}

# regla: servicemonitor-port
# El ServiceMonitor apunta al puerto del Service que es el de metricas (8081), no al del contrato (8080).
metrics_port_names := {p.name |
	some s in listed
	s.kind == "Service"
	s.metadata.name == "decision-registry-service"
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
