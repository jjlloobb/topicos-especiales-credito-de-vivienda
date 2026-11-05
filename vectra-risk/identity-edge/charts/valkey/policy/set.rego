# Lo que exige ver todos los documentos de un entorno juntos: `conftest test --combine --namespace valkey_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package valkey_set

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
	["StatefulSet", "valkey-a"],
	["StatefulSet", "valkey-b"],
	["StatefulSet", "sentinel-a"],
	["StatefulSet", "sentinel-b"],
	["Service", "valkey-a"],
	["Service", "valkey-b"],
	["Service", "sentinel-a"],
	["Service", "sentinel-b"],
	["ConfigMap", "valkey-config"],
	["ConfigMap", "sentinel-config"],
	["ConfigMap", "valkey-scripts"],
	["ServiceAccount", "valkey"],
	["ServiceAccount", "sentinel"],
	["PodDisruptionBudget", "valkey"],
	["PodDisruptionBudget", "sentinel"],
	["ExternalSecret", "valkey-acl"],
]

# regla: required-documents
deny contains msg if {
	some pair in required
	not present(pair[0], pair[1])
	msg := sprintf("required-documents: falta %s %s", pair)
}

# regla: zone-layout
deny contains msg if {
	zone("valkey-a") == zone("valkey-b")
	msg := "zone-layout: valkey-a y valkey-b deben estar en zonas distintas (R3)"
}

deny contains msg if {
	zone("sentinel-a") != zone("valkey-a")
	msg := "zone-layout: sentinel-a va en la zona de valkey-a (R3)"
}

deny contains msg if {
	zone("sentinel-b") != zone("valkey-b")
	msg := "zone-layout: sentinel-b va en la zona de valkey-b (R3)"
}

zone(name) := z if {
	some document in documents
	document.kind == "StatefulSet"
	document.metadata.name == name
	z := document.spec.template.spec.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].values[0]
}

# regla: sentinel-total
deny contains msg if {
	total := sum([d.spec.replicas | some d in documents; d.kind == "StatefulSet"; startswith(d.metadata.name, "sentinel-")])
	total != 3
	msg := sprintf("sentinel-total: debe haber 3 Sentinel y hay %d (INF-U2-04)", [total])
}

# regla: selectors
# Cada StatefulSet selecciona su template, cada Service sus pods y cada PDB todos los pods de su grupo.
deny contains msg if {
	some d in documents
	d.kind == "StatefulSet"
	not selects(d.spec.selector.matchLabels, d.spec.template.metadata.labels)
	msg := sprintf("selectors: el selector de %s no selecciona su template", [d.metadata.name])
}

deny contains msg if {
	some d in documents
	d.kind == "Service"
	not service_selects_its_statefulset(d)
	msg := sprintf("selectors: el Service %s no selecciona los pods de su StatefulSet", [d.metadata.name])
}

service_selects_its_statefulset(service) if {
	some d in documents
	d.kind == "StatefulSet"
	d.metadata.name == service.metadata.name
	d.spec.serviceName == service.metadata.name
	selects(service.spec.selector, d.spec.template.metadata.labels)
}

deny contains msg if {
	some pdb in documents
	pdb.kind == "PodDisruptionBudget"
	some d in documents
	d.kind == "StatefulSet"
	d.spec.template.metadata.labels["app.kubernetes.io/name"] == pdb.metadata.name
	not selects(pdb.spec.selector.matchLabels, d.spec.template.metadata.labels)
	msg := sprintf("selectors: el PDB %s no selecciona los pods de %s", [pdb.metadata.name, d.metadata.name])
}

deny contains msg if {
	some pdb in documents
	pdb.kind == "PodDisruptionBudget"
	not pdb_selects_something(pdb)
	msg := sprintf("selectors: el PDB %s no selecciona ningun pod", [pdb.metadata.name])
}

pdb_selects_something(pdb) if {
	some d in documents
	d.kind == "StatefulSet"
	selects(pdb.spec.selector.matchLabels, d.spec.template.metadata.labels)
}

selects(selector, labels) if {
	every key, value in selector {
		labels[key] == value
	}
}
