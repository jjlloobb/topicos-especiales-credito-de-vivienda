# Lo que exige ver todos los documentos de un entorno juntos: `conftest test --combine --namespace keycloak_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package keycloak_set

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

present(kind, name) if {
	some document in documents
	document.kind == kind
	document.metadata.name == name
}

required := [
	["StatefulSet", "keycloak"],
	["HorizontalPodAutoscaler", "keycloak"],
	["PodDisruptionBudget", "keycloak"],
	["Service", "keycloak"],
	["Service", "keycloak-admin"],
	["Certificate", "keycloak-tls"],
	["BackendTLSPolicy", "keycloak"],
	["ExternalSecret", "identity-ca"],
	["ExternalSecret", "keycloak-config-cli-client"],
	["ExternalSecret", "keycloak-reader-client"],
]

# regla: present
deny contains msg if {
	some pair in required
	not present(pair[0], pair[1])
	msg := sprintf("present: falta %s %s en el render", pair)
}

# regla: hpa-targets-statefulset
deny contains msg if {
	some document in documents
	document.kind == "HorizontalPodAutoscaler"
	not present(document.spec.scaleTargetRef.kind, document.spec.scaleTargetRef.name)
	msg := sprintf("hpa-targets-statefulset: %s apunta a algo que no esta en el render", [document.metadata.name])
}
