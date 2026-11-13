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
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas (ni `Server`, ni `AuthorizationPolicy`, ni `Secret`) y nada de menos.
expected_documents := {
	["Deployment", "product-metrics", "vectra-app"],
	["Service", "product-metrics", "vectra-app"],
	["PodDisruptionBudget", "product-metrics", "vectra-app"],
	["ServiceMonitor", "product-metrics", "vectra-app"],
	["PrometheusRule", "product-metrics", "vectra-app"],
	["ServiceAccount", "product-metrics", "vectra-app"],
	["ExternalSecret", "product-metrics-client", "vectra-app"],
	["ConfigMap", "product-metrics-policy", "vectra-app"],
	["ConfigMap", "product-metrics-dashboard", "vectra-app"],
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

deployment := [d | some d in listed; d.kind == "Deployment"; d.metadata.name == "product-metrics"][0]

pod := deployment.spec.template.spec

env_of(name) := value if {
	some e in pod.containers[0].env
	e.name == name
	value := e.value
}

config_map(name) := d if {
	some d in listed
	d.kind == "ConfigMap"
	d.metadata.name == name
}

# regla: checksum-config
# `checksum/config` del pod es el sha256 del `data` del ConfigMap de parametros (el archivo tal cual): un cambio de parametros reinicia las replicas.
policy_text := config_map("product-metrics-policy").data["values-product-metrics-policy.yaml"]

deny contains msg if {
	not deployment.spec.template.metadata.annotations["checksum/config"]
	msg := "checksum-config: el pod no lleva la anotacion checksum/config"
}

deny contains msg if {
	deployment.spec.template.metadata.annotations["checksum/config"] != crypto.sha256(policy_text)
	msg := "checksum-config: checksum/config no es el sha256 del data del ConfigMap de parametros"
}

# regla: policy-mounted
# El ConfigMap de parametros se monta (de solo lectura, como directorio) en la carpeta de `vectra_product.params.POLICY_PATH`; sin `VECTRA_POLICY_PATH`.
policy_mount_dir := "/etc/vectra/product-metrics-policy"

mounted_policy_dirs := {trim_suffix(m.mountPath, "/") |
	some v in pod.volumes
	v.configMap.name == "product-metrics-policy"
	some m in pod.containers[0].volumeMounts
	m.name == v.name
}

deny contains msg if {
	not policy_mount_dir in mounted_policy_dirs
	msg := sprintf("policy-mounted: el ConfigMap product-metrics-policy debe montarse en %s; se monta en %v", [policy_mount_dir, mounted_policy_dirs])
}

# regla: identity
# El pod monta el Secret de su ExternalSecret, de solo lectura, y la llave sale de `identity/clients/<VECTRA_CLIENT_ID>` (propiedad `private-key`).
external_secret(name) := d if {
	some d in listed
	d.kind == "ExternalSecret"
	d.metadata.name == name
}

mounted_secret_path(secret) := path if {
	some v in pod.volumes
	v.secret.secretName == secret
	some m in pod.containers[0].volumeMounts
	m.name == v.name
	m.readOnly == true
	path := concat("/", [trim_suffix(m.mountPath, "/"), "private-key"])
}

key_path_ok(secret) if env_of("VECTRA_CLIENT_KEY_PATH") == mounted_secret_path(secret)

deny contains msg if {
	not key_path_ok("product-metrics-client")
	msg := "identity: VECTRA_CLIENT_KEY_PATH no es un archivo del Secret product-metrics-client montado de solo lectura"
}

deny contains msg if {
	es := external_secret("product-metrics-client")
	client := env_of("VECTRA_CLIENT_ID")
	not es.spec.data == [{"secretKey": "private-key", "remoteRef": {"key": concat("/", ["identity/clients", client]), "property": "private-key"}}]
	msg := sprintf("identity: el ExternalSecret product-metrics-client lee identity/clients/%s, propiedad private-key", [client])
}

deny contains msg if {
	es := external_secret("product-metrics-client")
	es.spec.target.name != "product-metrics-client"
	msg := "identity: el ExternalSecret materializa un Secret con otro nombre"
}

# regla: service-account-exists
deny contains msg if {
	not pod.serviceAccountName in {d.metadata.name | some d in listed; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: la cuenta de servicio %s no esta en el render", [pod.serviceAccountName])
}

# regla: servicemonitor-port
# El ServiceMonitor apunta al puerto del Service que es el de metricas (8081).
metrics_port_names := {p.name |
	some s in listed
	s.kind == "Service"
	s.metadata.name == "product-metrics"
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

deny contains msg if {
	some monitor in listed
	monitor.kind == "ServiceMonitor"
	object.get(monitor.spec, "jobLabel", "") != ""
	msg := "servicemonitor-port: el ServiceMonitor no fija jobLabel: `job` es el nombre del Service (lo usan las alertas)"
}

# regla: service-port-names
deny contains msg if {
	some s in listed
	s.kind == "Service"
	some p in s.spec.ports
	container_ports := {cp.name | some c in pod.containers; some cp in c.ports}
	not p.targetPort in container_ports
	msg := sprintf("service-port-names: el targetPort %v del Service no existe en el contenedor", [p.targetPort])
}

# regla: service-pdb
# El PDB selecciona por `app.kubernetes.io/name` el mismo valor que lleva el pod (require-spread-and-pdb).
deny contains msg if {
	name := deployment.spec.template.metadata.labels["app.kubernetes.io/name"]
	not name in {b.spec.selector.matchLabels["app.kubernetes.io/name"] | some b in listed; b.kind == "PodDisruptionBudget"}
	msg := sprintf("service-pdb: %s sin PodDisruptionBudget por app.kubernetes.io/name", [deployment.metadata.name])
}

# regla: alerts-exact
# La PrometheusRule tiene exactamente cuatro `alertname` (P-U11-06); cada regla de alerta con `severity: SEV3` y `runbook_url`.
alerts := [r | some d in listed; d.kind == "PrometheusRule"; some g in d.spec.groups; some r in g.rules; r.alert]

expected_alerts := {"RuidoExplicacion", "ProductMetricsDegraded", "ProductMetricsStale", "ProductMetricsFullRecomputeMissing"}

deny contains msg if {
	names := {a.alert | some a in alerts}
	names != expected_alerts
	msg := sprintf("alerts-exact: las alertas son exactamente %v; sobran %v y faltan %v", [expected_alerts, names - expected_alerts, expected_alerts - names])
}

deny contains msg if {
	some a in alerts
	not a.labels.severity == "SEV3"
	msg := sprintf("alerts-exact: %s lleva severity SEV3", [a.alert])
}

deny contains msg if {
	some a in alerts
	not a.annotations.runbook_url
	msg := sprintf("alerts-exact: %s lleva runbook_url", [a.alert])
}

# regla: alert-job
# Las ramas de ausencia usan `up{job="..."}`: el `job` es el nombre del Service.
deny contains msg if {
	some a in alerts
	found := regex.find_all_string_submatch_n(`up\{job="([^"]+)"\}`, a.expr, -1)
	some match in found
	match[1] != "product-metrics"
	msg := sprintf("alert-job: %s lee up{job=%q}; el job es product-metrics (nombre del Service)", [a.alert, match[1]])
}

# regla: noise-sustain
# S de `RuidoExplicacion` es `noise_sustain_days` del ConfigMap de parametros renderizado.
deny contains msg if {
	policy := yaml.unmarshal(policy_text)
	some a in alerts
	a.alert == "RuidoExplicacion"
	not endswith(a.expr, sprintf(">= %v", [policy.noise_sustain_days]))
	msg := sprintf("noise-sustain: RuidoExplicacion no usa S = %v del ConfigMap de parametros", [policy.noise_sustain_days])
}

# regla: dashboard-labels
# El ConfigMap del dashboard lleva la etiqueta y la anotacion que lee el sidecar de Grafana de U1.
deny contains msg if {
	cm := config_map("product-metrics-dashboard")
	not cm.metadata.labels["vectra.io/dashboard"]
	msg := "dashboard-labels: el ConfigMap del dashboard lleva la etiqueta vectra.io/dashboard"
}

deny contains msg if {
	cm := config_map("product-metrics-dashboard")
	object.get(cm.metadata, ["annotations", "grafana_folder"], "") != "Vectra / Producto"
	msg := "dashboard-labels: la anotacion grafana_folder es «Vectra / Producto»"
}
