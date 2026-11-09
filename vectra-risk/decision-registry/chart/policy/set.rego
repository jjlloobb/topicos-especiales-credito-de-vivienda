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
# El render es exactamente esta lista de (tipo, nombre, namespace): nada de mas y nada de menos. El Paso 13 la amplia.
expected_documents := {
	["CronJob", "registry-aggregator", "vectra-app"],
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
# El CronJob usa una cuenta de servicio que el render declara.
deny contains msg if {
	some job in listed
	job.kind == "CronJob"
	name := job.spec.jobTemplate.spec.template.spec.serviceAccountName
	not [name, job.metadata.namespace] in {[d.metadata.name, d.metadata.namespace] | some d in listed; d.kind == "ServiceAccount"}
	msg := sprintf("service-account-exists: %s usa la cuenta de servicio %s, que no esta en el render", [job.metadata.name, name])
}

# regla: no-external-secret
# El agregador usa el Secret de U1; el chart no crea ninguno para el (el ExternalSecret de lo propio es del Paso 13).
deny contains msg if {
	some d in listed
	d.kind in {"ExternalSecret", "Secret"}
	msg := sprintf("no-external-secret: %s %s no va en el chart minimo", [d.kind, d.metadata.name])
}
