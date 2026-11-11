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
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas (ningun `x04-probe`, T5) y nada de menos.
expected_documents := {
	["Deployment", "bias-monitoring-service", "vectra-app"],
	["Service", "bias-monitoring-service", "vectra-app"],
	["PodDisruptionBudget", "bias-monitoring-service", "vectra-app"],
	["ServiceMonitor", "bias-monitoring-service", "vectra-app"],
	["CronJob", "bias-monitoring-job", "vectra-app"],
	["ConfigMap", "bias-monitoring-policy", "vectra-app"],
	["ServiceAccount", "bias-monitoring-service", "vectra-app"],
	["ServiceAccount", "bias-monitoring-job", "vectra-app"],
	["ExternalSecret", "bias-monitoring-service-client", "vectra-app"],
	["ExternalSecret", "bias-monitoring-job-client", "vectra-app"],
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

service := [d | some d in listed; d.kind == "Deployment"; d.metadata.name == "bias-monitoring-service"][0]

cronjob := [d | some d in listed; d.kind == "CronJob"; d.metadata.name == "bias-monitoring-job"][0]

service_pod := service.spec.template.spec

job_pod := cronjob.spec.jobTemplate.spec.template.spec

# regla: schedule-from-policy
# El `schedule` del CronJob es el de `values-monitoring-policy.yaml` (el del ConfigMap), nunca uno escrito en la plantilla.
policy := yaml.unmarshal([d | some d in listed; d.kind == "ConfigMap"; d.metadata.name == "bias-monitoring-policy"][0].data["values-monitoring-policy.yaml"])

deny contains msg if {
	cronjob.spec.schedule != policy.schedule
	msg := sprintf("schedule-from-policy: el CronJob corre con %q y la politica dice %q", [cronjob.spec.schedule, policy.schedule])
}

# regla: policy-mounted
# `VECTRA_POLICY_PATH` apunta al ConfigMap de la politica, montado en los dos procesos.
policy_file := "values-monitoring-policy.yaml"

mounted_policy_path(pod) := path if {
	some v in pod.volumes
	v.configMap.name == "bias-monitoring-policy"
	some m in pod.containers[0].volumeMounts
	m.name == v.name
	path := concat("/", [trim_suffix(m.mountPath, "/"), policy_file])
}

env_of(pod, name) := value if {
	some e in pod.containers[0].env
	e.name == name
	value := e.value
}

# Un booleano aparte: una llamada dentro de `not` se eleva fuera de el y, si queda indefinida, el cuerpo entero lo queda y la regla no dispara.
policy_path_ok(pod) if env_of(pod, "VECTRA_POLICY_PATH") == mounted_policy_path(pod)

deny contains msg if {
	some [who, pod] in [["bias-monitoring-service", service_pod], ["bias-monitoring-job", job_pod]]
	not policy_path_ok(pod)
	msg := sprintf("policy-mounted: VECTRA_POLICY_PATH de %s no apunta al ConfigMap bias-monitoring-policy montado", [who])
}

# regla: identity
# Cada proceso monta el Secret de SU ExternalSecret, de solo lectura, y la llave sale de `identity/clients/<VECTRA_CLIENT_ID>` (propiedad
# `private-key`). Un ExternalSecret por proceso; ninguno comparte la llave del otro.
external_secret(name) := d if {
	some d in listed
	d.kind == "ExternalSecret"
	d.metadata.name == name
}

mounted_secret_path(pod, secret) := path if {
	some v in pod.volumes
	v.secret.secretName == secret
	some m in pod.containers[0].volumeMounts
	m.name == v.name
	m.readOnly == true
	path := concat("/", [trim_suffix(m.mountPath, "/"), "private-key"])
}

identities := [
	["bias-monitoring-service", service_pod, "bias-monitoring-service-client"],
	["bias-monitoring-job", job_pod, "bias-monitoring-job-client"],
]

client_id_ok(pod, client) if env_of(pod, "VECTRA_CLIENT_ID") == client

deny contains msg if {
	some [client, pod, secret] in identities
	not client_id_ok(pod, client)
	msg := sprintf("identity: el pod de %s lleva otro VECTRA_CLIENT_ID; debe ser %s", [client, client])
}

key_path_ok(pod, secret) if env_of(pod, "VECTRA_CLIENT_KEY_PATH") == mounted_secret_path(pod, secret)

deny contains msg if {
	some [client, pod, secret] in identities
	not key_path_ok(pod, secret)
	msg := sprintf("identity: VECTRA_CLIENT_KEY_PATH de %s no es un archivo del Secret %s montado de solo lectura", [client, secret])
}

deny contains msg if {
	some [client, pod, secret] in identities
	es := external_secret(secret)
	not es.spec.data == [{"secretKey": "private-key", "remoteRef": {"key": concat("/", ["identity/clients", client]), "property": "private-key"}}]
	msg := sprintf("identity: el ExternalSecret %s lee identity/clients/%s, propiedad private-key", [secret, client])
}

deny contains msg if {
	some [client, pod, secret] in identities
	es := external_secret(secret)
	es.spec.target.name != secret
	msg := sprintf("identity: el ExternalSecret %s materializa un Secret con otro nombre", [secret])
}

# regla: service-account-exists
# Cada CronJob y Deployment usa una cuenta de servicio que el render declara, con el nombre de su cliente.
deny contains msg if {
	some sa in {service_pod.serviceAccountName, job_pod.serviceAccountName}
	not sa in {d.metadata.name | some d in listed; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: la cuenta de servicio %s no esta en el render", [sa])
}

# regla: servicemonitor-port
# El ServiceMonitor apunta al puerto del Service que es el de metricas (8081), no al del contrato (8080).
metrics_port_names := {p.name |
	some s in listed
	s.kind == "Service"
	s.metadata.name == "bias-monitoring-service"
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
deny contains msg if {
	some s in listed
	s.kind == "Service"
	some p in s.spec.ports
	container_ports := {cp.name | some c in service_pod.containers; some cp in c.ports}
	not p.targetPort in container_ports
	msg := sprintf("service-port-names: el targetPort %v del Service no existe en el contenedor", [p.targetPort])
}

# regla: service-pdb
# El PDB selecciona por `app.kubernetes.io/name` el mismo valor que lleva el pod (require-spread-and-pdb); sin HPA el Deployment lleva la exencion.
deny contains msg if {
	name := service.spec.template.metadata.labels["app.kubernetes.io/name"]
	not name in {b.spec.selector.matchLabels["app.kubernetes.io/name"] | some b in listed; b.kind == "PodDisruptionBudget"}
	msg := sprintf("service-pdb: %s sin PodDisruptionBudget por app.kubernetes.io/name", [service.metadata.name])
}

deny contains msg if {
	some h in listed
	h.kind == "HorizontalPodAutoscaler"
	msg := "service-pdb: el servicio lleva 2 replicas fijas, sin HorizontalPodAutoscaler"
}
