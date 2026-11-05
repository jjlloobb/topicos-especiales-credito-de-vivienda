# Reglas de conftest sobre lo que `render-valkey` produce (U02-T11, Paso 9 del plan de U2).
# Son listas blancas y comparaciones exactas contra el diseno (INF-U2-04, 06, R2 a R5; NFR-U2-20, 27, 30).
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_valkey_chart.py, y cada mensaje empieza por `x:`.
# Lo que exige ver varios documentos juntos esta en `set.rego` (`--combine --namespace valkey_set`).
package main

import rego.v1

namespace := "vectra-edge"

registries := {"registro.banco.internal/vectra", "kind-registry:5000/vectra"}

valkey_digest := "sha256:2602ace2be6569bc2bbb06f873776516ab9089821525be34f4305c67eb9db02a"

exporter_digest := "sha256:19bb5c732f5812d5b60b2e0af3c6d82c5b3e418cd020068d65f588a56df4a118"

images := {
	"valkey": {sprintf("%s/valkey@%s", [r, valkey_digest]) | some r in registries},
	"sentinel": {sprintf("%s/valkey@%s", [r, valkey_digest]) | some r in registries},
	"exporter": {sprintf("%s/redis-exporter@%s", [r, exporter_digest]) | some r in registries},
}

# INF-U2-06: Valkey (cada nodo), exportador y Sentinel (cada uno).
resources := {
	"valkey": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
	"exporter": {"requests": {"cpu": "50m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
	"sentinel": {"requests": {"cpu": "50m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
}

# R5 («ACL definitivas»): las lineas exactas. Las contrasenas son marcas de la plantilla de ESO.
users_acl := [
	"user default off",
	"user ratelimit on >{{ .ratelimit }} ~* +@read +@write +@connection -@dangerous",
	"user replication on >{{ .replication }} +psync +replconf +ping",
	"user sentinel on >{{ .sentinel }} +auth +client|setname +client|kill +config|rewrite +exec +info +multi +ping +publish +script|kill +slaveof +subscribe &__sentinel__:hello",
	"user exporter on >{{ .exporter }} +info +ping +client|setname +config|get +slowlog|get +slowlog|len +latency|latest +latency|histogram +command|info +commandlog|len",
]

valkey_secret_conf := ["masteruser replication", "masterauth {{ .replication }}"]

sentinel_users_conf := [
	"user default off",
	"user ratelimit on >{{ .sentinelRatelimit }} +auth +hello +ping +subscribe +sentinel|master +sentinel|slaves +sentinel|sentinels &switch-master",
	"user sentinel-peer on >{{ .sentinelPeer }} +auth +ping +publish +client|setname +sentinel|is-master-down-by-addr &__sentinel__:hello",
	"sentinel sentinel-user sentinel-peer",
	"sentinel sentinel-pass {{ .sentinelPeer }}",
]

sentinel_auth_conf := ["sentinel auth-user ratelimit sentinel", "sentinel auth-pass ratelimit {{ .sentinel }}"]

valkey_conf := [
	"port 6379",
	"bind 0.0.0.0",
	"protected-mode no",
	"dir /data",
	"save \"\"",
	"appendonly no",
	"maxmemory 128mb",
	"maxmemory-policy volatile-ttl",
	"replica-read-only yes",
	"aclfile /etc/valkey-secret/users.acl",
	"include /etc/valkey-secret/valkey-secret.conf",
]

sentinel_head_conf := [
	"port 26379",
	"dir /data",
	"protected-mode no",
	"sentinel resolve-hostnames yes",
	"sentinel announce-hostnames yes",
]

# Directivas que llevan una contrasena: no pueden estar en un ConfigMap.
password_directives := {"masterauth", "primaryauth", "requirepass", "auth-pass", "sentinel-pass", "user"}

password_env_names := {"REDIS_PASSWORD", "REDISCLI_AUTH", "REDIS_AUTH", "REDIS_SENTINEL_AUTH"}

statefulset_names := {"valkey-a", "valkey-b", "sentinel-a", "sentinel-b"}

is_statefulset if input.kind == "StatefulSet"

is_valkey_node if {
	is_statefulset
	startswith(input.metadata.name, "valkey-")
}

is_sentinel_group if {
	is_statefulset
	startswith(input.metadata.name, "sentinel-")
}

pod := input.spec.template.spec

lines(text) := [line | some line in split(text, "\n"); line != ""]

container(name) := c if {
	some c in pod.containers
	c.name == name
}

env_map(c) := {e.name: e | some e in c.env}

config_map(name) if {
	input.kind == "ConfigMap"
	input.metadata.name == name
}

external_secret if {
	input.kind == "ExternalSecret"
	input.metadata.name == "valkey-acl"
}

template_lines(key) := lines(input.spec.target.template.data[key])

# regla: namespace
deny contains msg if {
	input.metadata.namespace != namespace
	msg := sprintf("namespace: %s %s esta en %v y debe estar en %s", [input.kind, input.metadata.name, input.metadata.namespace, namespace])
}

# regla: images
deny contains msg if {
	is_statefulset
	some c in pod.containers
	not c.image in images[c.name]
	msg := sprintf("images: %s/%s usa %s: se exige el espejo de un registro permitido con el digest del diseno (R2)", [input.metadata.name, c.name, c.image])
}

# regla: no-persistence
deny contains msg if {
	is_statefulset
	input.spec.volumeClaimTemplates
	msg := sprintf("no-persistence: %s tiene volumeClaimTemplates (sin persistencia, INF-U2-04)", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	some v in pod.volumes
	v.name == "data"
	not v.emptyDir
	msg := sprintf("no-persistence: %s monta `data` fuera de un emptyDir", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	some v in pod.volumes
	v.persistentVolumeClaim
	msg := sprintf("no-persistence: %s usa un PersistentVolumeClaim", [input.metadata.name])
}

deny contains msg if {
	config_map("valkey-config")
	lines(input.data["valkey.conf"]) != valkey_conf
	msg := "no-persistence: valkey.conf difiere del diseno (save \"\", appendonly no, aclfile, maxmemory 128mb, volatile-ttl)"
}

# regla: acl-file
deny contains msg if {
	is_valkey_node
	c := container("valkey")
	not {"name": "acl", "mountPath": "/etc/valkey-secret", "readOnly": true} in c.volumeMounts
	msg := sprintf("acl-file: %s no monta el aclfile de solo lectura en /etc/valkey-secret", [input.metadata.name])
}

deny contains msg if {
	is_valkey_node
	some v in pod.volumes
	v.name == "acl"
	v.secret.secretName != "valkey-acl"
	msg := sprintf("acl-file: %s toma el aclfile de %s y no del Secret valkey-acl", [input.metadata.name, v.secret.secretName])
}

deny contains msg if {
	is_valkey_node
	not [v | some v in pod.volumes; v.name == "acl"]
	msg := sprintf("acl-file: %s sin el volumen `acl`", [input.metadata.name])
}

# regla: acl-users
deny contains msg if {
	external_secret
	template_lines("users.acl") != users_acl
	msg := "acl-users: users.acl difiere de las lineas de R5 (default off, ratelimit, replication, sentinel, exporter)"
}

# regla: master-auth
deny contains msg if {
	external_secret
	template_lines("valkey-secret.conf") != valkey_secret_conf
	msg := "master-auth: valkey-secret.conf debe fijar masteruser replication y masterauth de la plantilla"
}

# regla: sentinel-acl
deny contains msg if {
	external_secret
	template_lines("sentinel-users.conf") != sentinel_users_conf
	msg := "sentinel-acl: sentinel-users.conf difiere de R5 (default off, ratelimit, sentinel-peer, sentinel-user y sentinel-pass)"
}

deny contains msg if {
	external_secret
	template_lines("sentinel-auth.conf") != sentinel_auth_conf
	msg := "sentinel-acl: sentinel-auth.conf difiere de R5 (auth-user sentinel y auth-pass)"
}

# regla: sentinel-hostnames
deny contains msg if {
	config_map("sentinel-config")
	lines(input.data["sentinel-head.conf"]) != sentinel_head_conf
	msg := "sentinel-hostnames: sentinel-head.conf debe fijar resolve-hostnames yes y announce-hostnames yes (R3)"
}

# regla: maxmemory
deny contains msg if {
	config_map("valkey-config")
	not "maxmemory 128mb" in lines(input.data["valkey.conf"])
	msg := "maxmemory: falta `maxmemory 128mb`"
}

deny contains msg if {
	config_map("valkey-config")
	not "maxmemory-policy volatile-ttl" in lines(input.data["valkey.conf"])
	msg := "maxmemory: falta `maxmemory-policy volatile-ttl`"
}

# regla: zones
deny contains msg if {
	is_statefulset
	terms := pod.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms
	not count(terms) == 1
	msg := sprintf("zones: %s necesita una sola nodeSelectorTerm", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	not pod.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution
	msg := sprintf("zones: %s sin nodeAffinity obligatoria a su zona (R3)", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	some term in pod.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms
	exprs := [e | some e in term.matchExpressions]
	count(exprs) != 1
	msg := sprintf("zones: %s necesita una sola expresion de zona", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	some term in pod.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms
	some e in term.matchExpressions
	not zone_expression(e)
	msg := sprintf("zones: %s debe fijar topology.kubernetes.io/zone In [<una zona>]", [input.metadata.name])
}

zone_expression(e) if {
	e.key == "topology.kubernetes.io/zone"
	e.operator == "In"
	count(e.values) == 1
	e.values[0] in {"zone-a", "zone-b"}
}

# R6 (INF-U2-04): A va a zone-a y B a zone-b en kind, staging y prod.
node_zone := {"valkey-a": "zone-a", "sentinel-a": "zone-a", "valkey-b": "zone-b", "sentinel-b": "zone-b"}

deny contains msg if {
	is_statefulset
	some term in pod.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms
	some e in term.matchExpressions
	zone_expression(e)
	not e.values[0] == node_zone[input.metadata.name]
	msg := sprintf("zones: %s debe ir a la zona %s (R6)", [input.metadata.name, node_zone[input.metadata.name]])
}

# regla: sentinel-timing
sentinel_master_conf := [
	"sentinel down-after-milliseconds ratelimit 5000",
	"sentinel failover-timeout ratelimit 60000",
	"sentinel parallel-syncs ratelimit 1",
]

deny contains msg if {
	config_map("sentinel-config")
	some want in sentinel_master_conf
	directive := split(want, " ")[1]
	not want in lines(input.data["sentinel-master.conf"])
	msg := sprintf("sentinel-timing: %s debe ser `%s` (R7)", [directive, want])
}

deny contains msg if {
	config_map("sentinel-config")
	lines(input.data["sentinel-master.conf"]) != sentinel_master_conf
	msg := "sentinel-timing: sentinel-master.conf difiere de R7 (down-after-milliseconds, failover-timeout y parallel-syncs)"
}

# regla: replica-priority
deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "valkey-a"
	env_map(container("valkey"))["REPLICA_PRIORITY"].value != "10"
	msg := "replica-priority: valkey-a debe tener replica-priority 10 (R3)"
}

deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "valkey-b"
	env_map(container("valkey"))["REPLICA_PRIORITY"].value != "100"
	msg := "replica-priority: valkey-b debe tener replica-priority 100 (R3)"
}

# regla: initial-primary
deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "valkey-a"
	env_map(container("valkey"))["INITIAL_PRIMARY"].value != ""
	msg := "initial-primary: valkey-a arranca como primaria (R3)"
}

deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "valkey-b"
	env_map(container("valkey"))["INITIAL_PRIMARY"].value != sprintf("valkey-a-0.valkey-a.%s.svc.cluster.local", [namespace])
	msg := "initial-primary: valkey-b arranca como replica de valkey-a (R3)"
}

# regla: replicas
deny contains msg if {
	is_valkey_node
	input.spec.replicas != 1
	msg := sprintf("replicas: %s debe tener 1 replica (R3)", [input.metadata.name])
}

deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "sentinel-a"
	input.spec.replicas != 1
	msg := "replicas: sentinel-a debe tener 1 replica (R3)"
}

deny contains msg if {
	input.kind == "StatefulSet"
	input.metadata.name == "sentinel-b"
	input.spec.replicas != 2
	msg := "replicas: sentinel-b debe tener 2 replicas (R3)"
}

# regla: quorum
deny contains msg if {
	is_sentinel_group
	env_map(container("sentinel"))["SENTINEL_QUORUM"].value != "2"
	msg := sprintf("quorum: %s debe fijar quorum 2 (R3)", [input.metadata.name])
}

# regla: pdb
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.metadata.name == "valkey"
	not input.spec == {"minAvailable": 1, "selector": {"matchLabels": {"app.kubernetes.io/name": "valkey"}}}
	msg := "pdb: el PDB de Valkey es minAvailable 1 sobre app.kubernetes.io/name=valkey (INF-U2-04)"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.metadata.name == "sentinel"
	not input.spec == {"minAvailable": 2, "selector": {"matchLabels": {"app.kubernetes.io/name": "sentinel"}}}
	msg := "pdb: el PDB de Sentinel es minAvailable 2 sobre app.kubernetes.io/name=sentinel (INF-U2-04)"
}

# regla: exporter-sidecar
deny contains msg if {
	is_valkey_node
	not container("exporter")
	msg := sprintf("exporter-sidecar: %s sin el sidecar `exporter`", [input.metadata.name])
}

deny contains msg if {
	is_valkey_node
	c := container("exporter")
	not {"name": "metrics", "containerPort": 9121} in c.ports
	msg := sprintf("exporter-sidecar: el exportador de %s debe exponer metrics en el 9121", [input.metadata.name])
}

deny contains msg if {
	is_valkey_node
	c := container("exporter")
	env := env_map(c)
	not env["REDIS_USER"].value == "exporter"
	msg := sprintf("exporter-sidecar: el exportador de %s debe entrar con el usuario `exporter` (R5)", [input.metadata.name])
}

deny contains msg if {
	is_valkey_node
	c := container("exporter")
	env := env_map(c)
	not env["REDIS_PASSWORD"].valueFrom.secretKeyRef == {"name": "valkey-acl", "key": "exporter-password"}
	msg := sprintf("exporter-sidecar: la contrasena del exportador de %s sale del Secret valkey-acl", [input.metadata.name])
}

deny contains msg if {
	is_valkey_node
	not count(pod.containers) == 2
	msg := sprintf("exporter-sidecar: %s lleva Valkey y el exportador, y nada mas", [input.metadata.name])
}

# regla: no-plain-password
deny contains msg if {
	input.kind == "ConfigMap"
	some key, text in input.data
	some line in lines(text)
	first := split(line, " ")[0]
	first in password_directives
	msg := sprintf("no-plain-password: %s/%s lleva la directiva `%s`: las contrasenas van en el Secret de ESO (NFR-U2-27)", [input.metadata.name, key, first])
}

deny contains msg if {
	input.kind == "ConfigMap"
	some key, text in input.data
	some line in lines(text)
	contains(line, "{{")
	msg := sprintf("no-plain-password: %s/%s lleva una marca de plantilla de contrasena", [input.metadata.name, key])
}

deny contains msg if {
	is_statefulset
	some c in pod.containers
	some e in c.env
	e.name in password_env_names
	e.value
	msg := sprintf("no-plain-password: %s/%s lleva %s como valor y no desde un Secret", [input.metadata.name, c.name, e.name])
}

deny contains msg if {
	is_statefulset
	some c in pod.containers
	some e in c.env
	e.name in password_env_names
	not e.valueFrom.secretKeyRef.name == "valkey-acl"
	msg := sprintf("no-plain-password: %s/%s toma %s de otro Secret", [input.metadata.name, c.name, e.name])
}

# regla: resources
deny contains msg if {
	is_statefulset
	some c in pod.containers
	c.resources != resources[c.name]
	msg := sprintf("resources: %s/%s difiere de INF-U2-06", [input.metadata.name, c.name])
}

# regla: hardening
deny contains msg if {
	is_statefulset
	pod.priorityClassName != "vectra-high"
	msg := sprintf("hardening: %s sin priorityClassName vectra-high", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	not input.spec.template.metadata.labels["vectra.io/criticality"] == "high"
	msg := sprintf("hardening: la plantilla de %s sin vectra.io/criticality=high", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	not input.metadata.labels["vectra.io/criticality"] == "high"
	msg := sprintf("hardening: %s sin vectra.io/criticality=high", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	not pod.securityContext.runAsNonRoot == true
	msg := sprintf("hardening: %s no corre como no root", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := sprintf("hardening: %s sin seccompProfile RuntimeDefault", [input.metadata.name])
}

deny contains msg if {
	is_statefulset
	some c in pod.containers
	not hardened(c.securityContext)
	msg := sprintf("hardening: %s/%s sin securityContext endurecido", [input.metadata.name, c.name])
}

hardened(sc) if {
	sc.allowPrivilegeEscalation == false
	sc.privileged == false
	sc.readOnlyRootFilesystem == true
	sc.runAsNonRoot == true
	sc.capabilities.drop == ["ALL"]
	sc.seccompProfile.type == "RuntimeDefault"
}

deny contains msg if {
	is_statefulset
	pod.automountServiceAccountToken != false
	msg := sprintf("hardening: %s monta el token de la cuenta de servicio", [input.metadata.name])
}

deny contains msg if {
	input.kind == "ServiceAccount"
	input.automountServiceAccountToken != false
	msg := sprintf("hardening: la cuenta de servicio %s monta el token", [input.metadata.name])
}

# regla: headless-service
deny contains msg if {
	input.kind == "Service"
	input.spec.clusterIP != "None"
	msg := sprintf("headless-service: %s debe ser headless (R3)", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	not input.spec.publishNotReadyAddresses == true
	msg := sprintf("headless-service: %s debe publicar tambien las direcciones no listas", [input.metadata.name])
}

# regla: external-secret
deny contains msg if {
	external_secret
	not input.spec.secretStoreRef == {"name": "vectra-store", "kind": "ClusterSecretStore"}
	msg := "external-secret: el ExternalSecret usa el ClusterSecretStore vectra-store"
}

deny contains msg if {
	external_secret
	refs := {sprintf("%s=%s/%s", [d.secretKey, d.remoteRef.key, d.remoteRef.property]) | some d in input.spec.data}
	refs != {
		"ratelimit=edge/valkey/ratelimit",
		"replication=edge/valkey/replication",
		"sentinel=edge/valkey/sentinel",
		"sentinelPeer=edge/valkey/sentinel-peer",
		"exporter=edge/valkey/exporter",
		"sentinelRatelimit=edge/valkey/sentinel-ratelimit",
	}
	msg := "external-secret: las propiedades de la clave edge/valkey son ratelimit, replication, sentinel, sentinel-peer, exporter y sentinel-ratelimit (R5)"
}

deny contains msg if {
	external_secret
	input.spec.target.name != "valkey-acl"
	msg := "external-secret: el Secret se llama valkey-acl"
}

# regla: plain-secret
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("plain-secret: %s es un Secret en claro: lo materializa ESO", [input.metadata.name])
}
