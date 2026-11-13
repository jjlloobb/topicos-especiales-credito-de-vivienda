# Lo que exige ver todos los documentos del render juntos: `conftest test --combine --namespace console_set`.
# Con --combine, `input` es [{path, contents}], y `contents` es un documento o, si el archivo tiene varios, una lista.
package console_set

import rego.v1

listed := array.concat(
	[d | some file in input; is_array(file.contents); some d in file.contents; is_object(d)],
	[file.contents | some file in input; is_object(file.contents)],
)

deployments := [d | some d in listed; d.kind == "Deployment"]

kinds := [d.kind | some d in listed]

# regla: inventory
# Un render es de una sola pieza. BFF: Deployment, Service, HPA, PDB, ServiceAccount, ConfigMap y ServiceMonitor. SPA: Deployment, Service, PDB, ServiceAccount y ConfigMap (sin HPA ni ServiceMonitor).
expected := {
	"console-bff": {"Deployment", "Service", "HorizontalPodAutoscaler", "PodDisruptionBudget", "ServiceAccount", "ConfigMap", "ServiceMonitor"},
	"console-spa": {"Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ConfigMap"},
}

deny contains msg if {
	count(deployments) != 1
	msg := sprintf("inventory: un render tiene un solo Deployment, tiene %d", [count(deployments)])
}

deny contains msg if {
	count(deployments) == 1
	name := deployments[0].metadata.name
	some kind in expected[name]
	not kind in kinds
	msg := sprintf("inventory: %s sin %s", [name, kind])
}

deny contains msg if {
	count(deployments) == 1
	name := deployments[0].metadata.name
	count(kinds) != count(expected[name])
	msg := sprintf("inventory: %s rinde %d documentos, no %d (un tipo repetido o de mas)", [name, count(kinds), count(expected[name])])
}

deny contains msg if {
	count(deployments) == 1
	name := deployments[0].metadata.name
	some doc in listed
	not doc.kind in expected[name]
	msg := sprintf("inventory: %s no lleva %s %s", [name, doc.kind, doc.metadata.name])
}

# regla: checksum-spa
# `checksum/config` es el sha256 del `config.json` rendido: un cambio de `config.json` reinicia los pods.
deny contains msg if {
	some d in deployments
	d.metadata.name == "console-spa"
	some c in listed
	c.kind == "ConfigMap"
	c.metadata.name == "console-spa-config"
	annotation := d.spec.template.metadata.annotations["checksum/config"]
	not annotation == crypto.sha256(c.data["config.json"])
	msg := sprintf("checksum-spa: checksum/config %s no es el sha256 del config.json rendido", [annotation])
}

# regla: config-mounted
# El volumen de `config.json` es el ConfigMap del chart, en el directorio que `nginx.conf` usa (`alias`), sin `subPath` y de solo lectura.
deny contains msg if {
	some d in deployments
	d.metadata.name == "console-spa"
	mounts := [m | some m in d.spec.template.spec.containers[0].volumeMounts; m.name == "config"]
	count(mounts) != 1
	msg := "config-mounted: la SPA monta el volumen config una vez"
}

deny contains msg if {
	some d in deployments
	d.metadata.name == "console-spa"
	vols := [v | some v in d.spec.template.spec.volumes; v.name == "config"; v.configMap.name == "console-spa-config"]
	count(vols) != 1
	msg := "config-mounted: el volumen config es el ConfigMap console-spa-config"
}

# regla: hpa-presence
deny contains msg if {
	some d in deployments
	d.metadata.name == "console-bff"
	not "HorizontalPodAutoscaler" in kinds
	msg := "hpa-presence: el BFF lleva HPA (en kind tambien: INF-U10-06)"
}

deny contains msg if {
	some d in deployments
	d.metadata.name == "console-spa"
	"HorizontalPodAutoscaler" in kinds
	msg := "hpa-presence: la SPA no lleva HPA (2 replicas fijas con la exencion de U1)"
}

deny contains msg if {
	some doc in listed
	doc.kind in {"Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ConfigMap", "ServiceMonitor", "HorizontalPodAutoscaler"}
	not doc.metadata.namespace in {"vectra-app", "vectra-edge"}
	msg := sprintf("inventory: %s %s esta fuera de vectra-app y vectra-edge", [doc.kind, doc.metadata.name])
}
