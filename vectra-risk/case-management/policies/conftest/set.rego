# Lo que exige ver todos los documentos del render juntos: `conftest test --combine --namespace chart_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package chart_set

import rego.v1

# Un arreglo, no un conjunto: un documento repetido cuenta dos veces.
listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

app_names := ["case-service", "case-worker"]

# regla: documents-exact
# El render es esta lista de (tipo, nombre, namespace) y nada mas. El mock y la PrometheusRule van todos o ninguno (`coreMock.enabled`); el Job rt5-demo es opcional.
base_documents := {[kind, name, "vectra-app"] |
	some name in app_names
	some kind in ["Deployment", "Service", "HorizontalPodAutoscaler", "PodDisruptionBudget", "ServiceAccount", "ServiceMonitor"]
} | {["ExternalSecret", sprintf("%s-client", [name]), "vectra-app"] | some name in app_names} | {["ServiceAccount", "migration-case", "vectra-app"], ["Job", "case-migration", "vectra-app"]}

mock_documents := {[kind, "core-banking-mock", "vectra-mock"] | some kind in ["Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ServiceMonitor"]} | {["PrometheusRule", "case-management", "vectra-app"]}

actual_documents := [[d.kind, d.metadata.name, object.get(d.metadata, "namespace", "")] | some d in listed]

rt5_job(doc) if {
	doc[0] == "Job"
	startswith(doc[1], "rt5-demo-")
}

has_mock if ["Deployment", "core-banking-mock", "vectra-mock"] in actual_documents

expected_documents := base_documents | mock_documents if has_mock

expected_documents := base_documents if not has_mock

deny contains msg if {
	some doc in actual_documents
	not doc in expected_documents
	not rt5_job(doc)
	msg := sprintf("documents-exact: documento fuera de la lista: %s %s (%s)", doc)
}

deny contains msg if {
	some expected in expected_documents
	not expected in actual_documents
	msg := sprintf("documents-exact: falta %s %s (%s)", expected)
}

rt5_count := count([d | some d in actual_documents; rt5_job(d)])

deny contains msg if {
	count(actual_documents) != count(expected_documents) + rt5_count
	msg := sprintf("documents-exact: %d documentos, no %d (hay repetidos)", [count(actual_documents), count(expected_documents) + rt5_count])
}

deny contains msg if {
	rt5_count > 1
	msg := "documents-exact: un solo Job rt5-demo"
}

# regla: core-consistency
# `core.enabled = false` (produccion) no deja ningun recurso del mock ni la PrometheusRule `CoreWriteAttempt` (NFR-U8-44), ni el Job rt5-demo; con el core habilitado el mock existe.
deployments := [d | some d in listed; d.kind == "Deployment"]

service := [d | some d in deployments; d.metadata.name == "case-service"][0]

env_of(pod, name) := value if {
	some e in pod.containers[0].env
	e.name == name
	value := e.value
}

core_enabled := env_of(service.spec.template.spec, "CASE_CORE_ENABLED")

deny contains msg if {
	core_enabled != "true"
	has_mock
	msg := "core-consistency: con core.enabled = false no hay recursos del mock (NFR-U8-44)"
}

deny contains msg if {
	core_enabled != "true"
	rt5_count > 0
	msg := "core-consistency: con core.enabled = false no hay Job rt5-demo"
}

deny contains msg if {
	core_enabled != "true"
	some d in listed
	d.kind == "PrometheusRule"
	msg := "core-consistency: con core.enabled = false no hay PrometheusRule (CoreWriteAttempt vigila el mock)"
}

deny contains msg if {
	core_enabled == "true"
	not has_mock
	msg := "core-consistency: con core.enabled = true el mock (coreMock.enabled) existe en el render"
}

deny contains msg if {
	core_enabled != "true"
	env_of(service.spec.template.spec, "CASE_ALLOW_TEST_SCENARIOS") != "false"
	msg := "core-consistency: sin core (produccion) allowTestScenarios es false"
}

# regla: service-labels
# Las etiquetas del pod son las que espera `platform/network/flows.yaml` (`name:` de case-service, case-worker y core-banking-mock).
deny contains msg if {
	some d in deployments
	not d.spec.template.metadata.labels["app.kubernetes.io/name"] in {"case-service", "case-worker", "core-banking-mock"}
	msg := sprintf("service-labels: el pod de %s lleva app.kubernetes.io/name %v, que no esta en flows.yaml", [d.metadata.name, d.spec.template.metadata.labels["app.kubernetes.io/name"]])
}

# regla: service-account-exists
# Cada Deployment y cada Job usa una cuenta de servicio que el render declara.
accounts := {s.metadata.name | some s in listed; s.kind == "ServiceAccount"}

deny contains msg if {
	some d in listed
	d.kind in {"Deployment", "Job"}
	name := d.spec.template.spec.serviceAccountName
	not name in accounts
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [d.metadata.name, name])
}

# regla: identity
# Cada Deployment de vectra-app monta el Secret de SU ExternalSecret, de solo lectura, y la llave sale de `identity/clients/<VECTRA_CLIENT_ID>`.
secret_mount_path(pod, secret) := path if {
	some v in pod.volumes
	v.secret.secretName == secret
	some m in pod.containers[0].volumeMounts
	m.name == v.name
	m.readOnly == true
	path := concat("/", [trim_suffix(m.mountPath, "/"), "private-key"])
}

key_path_ok(pod, secret) if env_of(pod, "VECTRA_CLIENT_KEY_PATH") == secret_mount_path(pod, secret)

deny contains msg if {
	some d in deployments
	d.metadata.name in app_names
	secret := sprintf("%s-client", [d.metadata.name])
	not key_path_ok(d.spec.template.spec, secret)
	msg := sprintf("identity: %s no monta de solo lectura el Secret %s en VECTRA_CLIENT_KEY_PATH", [d.metadata.name, secret])
}

deny contains msg if {
	some es in listed
	es.kind == "ExternalSecret"
	not es.spec.target.name == es.metadata.name
	msg := sprintf("identity: el ExternalSecret %s crea el Secret %s", [es.metadata.name, es.spec.target.name])
}

deny contains msg if {
	some es in listed
	es.kind == "ExternalSecret"
	client := trim_suffix(es.metadata.name, "-client")
	es.spec.data[0].remoteRef.key != sprintf("identity/clients/%s", [client])
	msg := sprintf("identity: el ExternalSecret %s lee otra llave de la boveda", [es.metadata.name])
}

deny contains msg if {
	some d in deployments
	d.metadata.name in app_names
	some e in d.spec.template.spec.containers[0].env
	e.name in {"PGUSER", "PGPASSWORD"}
	e.valueFrom.secretKeyRef.name != db_secret[d.metadata.name]
	msg := sprintf("identity: %s usa el Secret %s de la base; el suyo es %s (ningun proceso recibe el de otro)", [d.metadata.name, e.valueFrom.secretKeyRef.name, db_secret[d.metadata.name]])
}

db_secret := {"case-service": "pg-role-case-app", "case-worker": "pg-role-case-worker"}

# regla: rt5-selector
# INF-U8-03: el selector del Service y del PDB de case-service NO coincide con las etiquetas del Job rt5-demo y SI con las de los pods del Deployment.
selects(selector, labels) if {
	every k, v in selector {
		labels[k] == v
	}
}

deny contains msg if {
	some job in listed
	job.kind == "Job"
	startswith(job.metadata.name, "rt5-demo-")
	some s in listed
	s.kind == "Service"
	s.metadata.name == "case-service"
	selects(s.spec.selector, job.spec.template.metadata.labels)
	msg := "rt5-selector: el selector del Service de case-service coincide con las etiquetas del Job rt5-demo"
}

deny contains msg if {
	some job in listed
	job.kind == "Job"
	startswith(job.metadata.name, "rt5-demo-")
	some s in listed
	s.kind == "PodDisruptionBudget"
	s.metadata.name == "case-service"
	selects(s.spec.selector.matchLabels, job.spec.template.metadata.labels)
	msg := "rt5-selector: el selector del PDB de case-service coincide con las etiquetas del Job rt5-demo"
}

deny contains msg if {
	some d in deployments
	d.metadata.name in app_names
	some s in listed
	s.kind == "Service"
	s.metadata.name == d.metadata.name
	not selects(s.spec.selector, d.spec.template.metadata.labels)
	msg := sprintf("rt5-selector: el Service %s no selecciona los pods de su Deployment", [d.metadata.name])
}

deny contains msg if {
	some d in deployments
	d.metadata.name in app_names
	some s in listed
	s.kind == "PodDisruptionBudget"
	s.metadata.name == d.metadata.name
	not selects(s.spec.selector.matchLabels, d.spec.template.metadata.labels)
	msg := sprintf("rt5-selector: el PDB %s no selecciona los pods de su Deployment", [d.metadata.name])
}

# regla: distinct-commands
# NFR-U8-10: case-service y case-worker usan la misma imagen por digest y ordenes distintas.
deny contains msg if {
	a := [d | some d in deployments; d.metadata.name == "case-service"][0]
	b := [d | some d in deployments; d.metadata.name == "case-worker"][0]
	a.spec.template.spec.containers[0].image != b.spec.template.spec.containers[0].image
	msg := "distinct-commands: case-service y case-worker usan la misma imagen (una imagen, tres ordenes; NFR-U8-10)"
}

deny contains msg if {
	a := [d | some d in deployments; d.metadata.name == "case-service"][0]
	b := [d | some d in deployments; d.metadata.name == "case-worker"][0]
	a.spec.template.spec.containers[0].command == b.spec.template.spec.containers[0].command
	msg := "distinct-commands: case-service y case-worker tienen la misma orden (NFR-U8-10)"
}
