# Lo que exige ver todos los documentos de un entorno juntos: `conftest test --combine --namespace jobs_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package jobs_set

import rego.v1

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

# regla: documents-exact
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas y nada de menos.
expected_documents := {
	["ConfigMap", "realm-drift-realm", "vectra-identity"],
	["CronJob", "realm-drift", "vectra-identity"],
	["CronJob", "signing-key-age", "vectra-identity"],
	["ServiceAccount", "realm-drift", "vectra-identity"],
	["ServiceAccount", "signing-key-age", "vectra-identity"],
}

# Un arreglo, no un conjunto: un documento repetido cuenta dos veces.
listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

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
# Cada CronJob usa la cuenta de servicio que el render declara (el mismo nombre).
deny contains msg if {
	some job in documents
	job.kind == "CronJob"
	name := job.spec.jobTemplate.spec.template.spec.serviceAccountName
	not [name, job.metadata.namespace] in {[d.metadata.name, d.metadata.namespace] | some d in documents; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [job.metadata.name, name])
}

# regla: configmap-mounted
# El ConfigMap que monta realm-drift esta en el render.
deny contains msg if {
	some job in documents
	job.kind == "CronJob"
	some v in job.spec.jobTemplate.spec.template.spec.volumes
	v.configMap
	not [v.configMap.name, job.metadata.namespace] in {[d.metadata.name, d.metadata.namespace] | some d in documents; d.kind == "ConfigMap"}
	msg := sprintf("configmap-mounted: %s monta el ConfigMap %s, que no esta en el render", [job.metadata.name, v.configMap.name])
}
