# Lo que exige ver todos los documentos del render juntos: `conftest test --combine --namespace chart_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package chart_set

import rego.v1

# Un arreglo, no un conjunto: un documento repetido cuenta dos veces.
listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

services := ["scoring-service", "explainability-service"]

# regla: documents-exact
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas (ni PrometheusRule, T2) y nada de menos.
expected_documents := {[kind, name, "vectra-app"] |
	some name in services
	some kind in ["Deployment", "Service", "HorizontalPodAutoscaler", "PodDisruptionBudget", "ServiceAccount", "ServiceMonitor"]
} | {["ExternalSecret", sprintf("%s-client", [name]), "vectra-app"] | some name in services}

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

# regla: service-labels
# Las etiquetas del pod son las que espera `platform/network/flows.yaml` (`name:` de scoring-service y explainability-service).
deployments := [d | some d in listed; d.kind == "Deployment"]

deny contains msg if {
	some d in deployments
	not d.spec.template.metadata.labels["app.kubernetes.io/name"] in services
	msg := sprintf("service-labels: el pod de %s lleva app.kubernetes.io/name %v, que no esta en flows.yaml", [d.metadata.name, d.spec.template.metadata.labels["app.kubernetes.io/name"]])
}

# regla: service-account-exists
# Cada Deployment usa una cuenta de servicio que el render declara.
deny contains msg if {
	some d in deployments
	name := d.spec.template.spec.serviceAccountName
	not name in {s.metadata.name | some s in listed; s.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [d.metadata.name, name])
}

# regla: identity
# Cada Deployment monta el Secret de SU ExternalSecret, de solo lectura, y la llave sale de `identity/clients/<VECTRA_CLIENT_ID>`.
secret_mount_path(pod, secret) := path if {
	some v in pod.volumes
	v.secret.secretName == secret
	some m in pod.containers[0].volumeMounts
	m.name == v.name
	m.readOnly == true
	path := concat("/", [trim_suffix(m.mountPath, "/"), "private-key"])
}

env_of(pod, name) := value if {
	some e in pod.containers[0].env
	e.name == name
	value := e.value
}

key_path_ok(pod, secret) if env_of(pod, "VECTRA_CLIENT_KEY_PATH") == secret_mount_path(pod, secret)

deny contains msg if {
	some d in deployments
	secret := sprintf("%s-client", [d.metadata.name])
	not key_path_ok(d.spec.template.spec, secret)
	msg := sprintf("identity: VECTRA_CLIENT_KEY_PATH de %s no es un archivo del Secret %s montado de solo lectura", [d.metadata.name, secret])
}

deny contains msg if {
	some d in deployments
	secret := sprintf("%s-client", [d.metadata.name])
	some es in listed
	es.kind == "ExternalSecret"
	es.metadata.name == secret
	not es.spec.data == [{"secretKey": "private-key", "remoteRef": {"key": concat("/", ["identity/clients", env_of(d.spec.template.spec, "VECTRA_CLIENT_ID")]), "property": "private-key"}}]
	msg := sprintf("identity: el ExternalSecret %s lee identity/clients/<VECTRA_CLIENT_ID>, propiedad private-key", [secret])
}

deny contains msg if {
	some es in listed
	es.kind == "ExternalSecret"
	es.spec.target.name != es.metadata.name
	msg := sprintf("identity: el ExternalSecret %s materializa un Secret con otro nombre", [es.metadata.name])
}

# regla: servicemonitor-port
# El ServiceMonitor apunta al puerto del Service que es el de metricas (8081), no al del contrato (8080).
metrics_port_names(service) := {p.name |
	some s in listed
	s.kind == "Service"
	s.metadata.name == service
	some p in s.spec.ports
	p.port == 8081
}

deny contains msg if {
	some monitor in listed
	monitor.kind == "ServiceMonitor"
	service := monitor.spec.selector.matchLabels["app.kubernetes.io/name"]
	some endpoint in monitor.spec.endpoints
	not object.get(endpoint, "port", "") in metrics_port_names(service)
	msg := sprintf("servicemonitor-port: el endpoint de %s apunta a %v; el puerto de metricas (8081) del Service se llama %v", [service, object.get(endpoint, "port", "ausente"), metrics_port_names(service)])
}

# regla: service-port-names
# Los nombres de puerto del Service existen en el contenedor (el `targetPort` por nombre).
deny contains msg if {
	some s in listed
	s.kind == "Service"
	some p in s.spec.ports
	container_ports := {cp.name | some d in listed; d.kind == "Deployment"; d.metadata.name == s.metadata.name; some c in d.spec.template.spec.containers; some cp in c.ports}
	not p.targetPort in container_ports
	msg := sprintf("service-port-names: el targetPort %v del Service %s no existe en el contenedor", [p.targetPort, s.metadata.name])
}

# regla: service-pdb
# Cada Deployment tiene un PDB y un HPA en el render (NFR-U1-04, NFR-U1-12; `require-spread-and-pdb` y `require-hpa-bounds`).
deny contains msg if {
	some d in deployments
	name := d.spec.template.metadata.labels["app.kubernetes.io/name"]
	not name in {b.spec.selector.matchLabels["app.kubernetes.io/name"] | some b in listed; b.kind == "PodDisruptionBudget"}
	msg := sprintf("service-pdb: %s sin PodDisruptionBudget por app.kubernetes.io/name", [d.metadata.name])
}

deny contains msg if {
	some d in deployments
	not d.metadata.name in {h.spec.scaleTargetRef.name | some h in listed; h.kind == "HorizontalPodAutoscaler"}
	msg := sprintf("service-pdb: %s sin HorizontalPodAutoscaler", [d.metadata.name])
}
