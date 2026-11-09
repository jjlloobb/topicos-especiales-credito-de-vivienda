# Lo que exige ver todos los documentos del render juntos: `conftest test --combine --namespace chart_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package chart_set

import rego.v1

# Un arreglo, no un conjunto: un documento repetido cuenta dos veces.
listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

# regla: no-secrets
# La credencial minio-kserve es de U1: el chart no declara Secret ni ExternalSecret (Paso 7).
deny contains msg if {
	some d in listed
	d.kind in {"Secret", "ExternalSecret"}
	msg := sprintf("no-secrets: %s %s: la credencial minio-kserve es de U1", [d.kind, d.metadata.name])
}

# regla: no-repeated-documents
deny contains msg if {
	keys := [sprintf("%s/%s/%s", [d.kind, object.get(d.metadata, "namespace", ""), d.metadata.name]) | some d in listed]
	count(keys) != count({k | some k in keys})
	msg := "no-repeated-documents: documentos repetidos en el render"
}

# regla: service-account-credential
deny contains msg if {
	some ns in {"vectra-serving", "vectra-staging"}
	not credential_in(ns)
	msg := sprintf("service-account-credential: falta la ServiceAccount kserve-model con el Secret minio-kserve en %s (F46)", [ns])
}

credential_in(ns) if {
	some d in listed
	d.kind == "ServiceAccount"
	d.metadata.name == "kserve-model"
	d.metadata.namespace == ns
	{"name": "minio-kserve"} in d.secrets
}

# Los InferenceService del render, con su namespace.
isvcs := [d | some d in listed; d.kind == "InferenceService"]

# regla: active-pdb
# Cada componente del activo (Kyverno `require-pdb` mira el Deployment que genera KServe) tiene su PDB por app.kubernetes.io/name.
deny contains msg if {
	some d in isvcs
	d.metadata.namespace == "vectra-serving"
	not d.metadata.labels["vectra.io/serving-state"]
	some c in {"predictor", "explainer"}
	name := d.spec[c].labels["app.kubernetes.io/name"]
	not budget_for(d.metadata.namespace, name)
	msg := sprintf("active-pdb: %s/%s sin PodDisruptionBudget por app.kubernetes.io/name=%s", [d.metadata.name, c, name])
}

budget_for(ns, name) if {
	some b in listed
	b.kind == "PodDisruptionBudget"
	b.metadata.namespace == ns
	b.spec.selector.matchLabels["app.kubernetes.io/name"] == name
	b.spec.minAvailable == 1
}

# regla: inactive-no-pdb
# El inactivo (1 replica) con un PDB de minAvailable 1 no se podria drenar.
deny contains msg if {
	some d in isvcs
	d.metadata.labels["vectra.io/serving-state"] == "inactivo"
	some b in listed
	b.kind == "PodDisruptionBudget"
	startswith(b.metadata.name, d.metadata.name)
	msg := sprintf("inactive-no-pdb: PodDisruptionBudget %s sobre el inactivo %s", [b.metadata.name, d.metadata.name])
}
