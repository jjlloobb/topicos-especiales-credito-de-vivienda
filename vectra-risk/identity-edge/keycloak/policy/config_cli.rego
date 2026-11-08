# Reglas de conftest sobre el Job de `keycloak-config-cli` y sus piezas, solo en kind (U02-T19, B-1; INF-U2-05a, «Excepción solo en kind»).
# `keycloak-config-cli` v6.5.1 corre como hook `PostSync` de la Application `keycloak`, con el administrador de arranque de `master`
# (contraseña, no `private_key_jwt`: ningun release lo admite, INF-U2-05a). Que el Job exista en kind y no en staging ni en prod lo exigen
# `set.rego` (`config-cli-only-kind`) y la regla `bootstrap-admin` de `keycloak.rego`.
# Cada `# regla: x` tiene un caso que falla en identity-edge/tests/unit/test_config_cli.py, y cada mensaje empieza por `x:`.
package main

import rego.v1

config_cli_name := "keycloak-config-cli"

# La imagen de `keycloak-config-cli` 6.5.1 (la etiqueta 6.5.1-26.5.5, la de la linea 26 de Keycloak), espejada en el registro de kind.
config_cli_repository := "kind-registry:5000/vectra/keycloak-config-cli"

# ExternalSecret de la excepcion de kind: nombre -> clave de la boveda (las propiedades las comprueba `config-cli-external-secrets`).
config_cli_external_secrets := {"keycloak-bootstrap-admin", "keycloak-realm-clients-jwks", "keycloak-realm-synthetic-users"}

is_config_cli_job if {
	input.kind == "Job"
	input.metadata.name == config_cli_name
}

job_pod := input.spec.template.spec if is_config_cli_job

job_container := job_pod.containers[0] if is_config_cli_job

job_containers contains c if {
	is_config_cli_job
	some c in job_pod.containers
}

job_containers contains c if {
	is_config_cli_job
	some c in object.get(job_pod, "initContainers", [])
}

# El valor en claro de la variable, o "" si falta o viene de un Secret (una variable ausente tambien incumple la regla).
job_env(name) := object.get({e.name: e.value | some e in job_container.env; "value" in object.keys(e)}, name, "")

# regla: config-cli-hook
# Hook `PostSync` de Argo CD, que corre cuando la wave 3 ya esta sana, y `BeforeHookCreation`: el Job anterior se borra antes de crear el nuevo.
deny contains msg if {
	is_config_cli_job
	object.get(input.metadata, "annotations", {}) != {
		"argocd.argoproj.io/hook": "PostSync",
		"argocd.argoproj.io/hook-delete-policy": "BeforeHookCreation",
	}
	msg := "config-cli-hook: el Job lleva exactamente argocd.argoproj.io/hook: PostSync y hook-delete-policy: BeforeHookCreation"
}

# regla: config-cli-image
# Imagen fijada por digest (el digest del indice multi-arquitectura de la etiqueta 6.5.1-26.5.5), en el mirror de kind. Sin etiqueta.
deny contains msg if {
	is_config_cli_job
	some c in job_containers
	not regex.match(sprintf("^%s@sha256:[0-9a-f]{64}$", [config_cli_repository]), c.image)
	msg := sprintf("config-cli-image: %s debe ser %s@sha256:<digest>: %s", [c.name, config_cli_repository, c.image])
}

deny contains msg if {
	is_config_cli_job
	some c in job_containers
	endswith(c.image, "0000000000000000000000000000000000000000000000000000000000000000")
	msg := sprintf("config-cli-image: %s lleva un digest de marcador", [c.name])
}

# regla: config-cli-varsubst
# El realm usa `$(env:NOMBRE)`: sin la sustitucion, el realm se importaria con el texto literal. Una variable sin valor es un error.
deny contains msg if {
	is_config_cli_job
	job_env("IMPORT_VARSUBSTITUTION_ENABLED") != "true"
	msg := "config-cli-varsubst: IMPORT_VARSUBSTITUTION_ENABLED debe ser true"
}

deny contains msg if {
	is_config_cli_job
	job_env("IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR") != "true"
	msg := "config-cli-varsubst: IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR debe ser true"
}

# regla: config-cli-connection
# A la Admin API por `hostname-admin` (F94), con la CA del Secret `identity-ca`, sin saltar la verificacion; el realm de kind, del ConfigMap propio.
deny contains msg if {
	is_config_cli_job
	job_env("KEYCLOAK_URL") != admin_hostname
	msg := sprintf("config-cli-connection: KEYCLOAK_URL debe ser %s", [admin_hostname])
}

deny contains msg if {
	is_config_cli_job
	job_env("KEYCLOAK_SSLVERIFY") != "true"
	msg := "config-cli-connection: KEYCLOAK_SSLVERIFY debe ser true"
}

deny contains msg if {
	is_config_cli_job
	job_env("IMPORT_FILES_LOCATIONS") != "file:/config/realm.kind.yaml"
	msg := "config-cli-connection: IMPORT_FILES_LOCATIONS debe ser file:/config/realm.kind.yaml"
}

deny contains msg if {
	is_config_cli_job
	not volume_secret("identity-ca")
	msg := "config-cli-connection: falta el volumen del Secret identity-ca"
}

deny contains msg if {
	is_config_cli_job
	not volume_configmap("keycloak-config-cli-realm")
	msg := "config-cli-connection: falta el volumen del ConfigMap keycloak-config-cli-realm"
}

volume_secret(name) if {
	some v in job_pod.volumes
	v.secret.secretName == name
}

volume_configmap(name) if {
	some v in job_pod.volumes
	v.configMap.name == name
}

# regla: config-cli-credentials
# La credencial del administrador de arranque sale de `keycloak-bootstrap-admin` por secretKeyRef; las variables del realm, de dos Secret
# de ExternalSecret por envFrom. Ninguna credencial en claro.
deny contains msg if {
	is_config_cli_job
	some name, key in {"KEYCLOAK_USER": "username", "KEYCLOAK_PASSWORD": "password"}
	not job_secret_env(name, key)
	msg := sprintf("config-cli-credentials: %s debe salir de secretKeyRef keycloak-bootstrap-admin/%s", [name, key])
}

job_secret_env(name, key) if {
	some e in job_container.env
	e.name == name
	e.valueFrom == {"secretKeyRef": {"name": "keycloak-bootstrap-admin", "key": key}}
}

deny contains msg if {
	is_config_cli_job
	refs := [r.secretRef.name | some r in object.get(job_container, "envFrom", [])]
	sort(refs) != ["keycloak-realm-clients-jwks", "keycloak-realm-synthetic-users"]
	msg := "config-cli-credentials: envFrom exacto: keycloak-realm-clients-jwks y keycloak-realm-synthetic-users"
}

deny contains msg if {
	is_config_cli_job
	some e in job_container.env
	e.name in {"KEYCLOAK_PASSWORD", "KEYCLOAK_USER", "KEYCLOAK_CLIENTSECRET"}
	"value" in object.keys(e)
	msg := sprintf("config-cli-credentials: %s no puede ir en claro", [e.name])
}

# regla: config-cli-security
# Lo que exigirian las politicas de U1: no root, raiz de solo lectura, sin privilegios, recursos, prioridad y sin token de la API.
deny contains msg if {
	is_config_cli_job
	job_pod.securityContext.runAsNonRoot != true
	msg := "config-cli-security: el pod debe correr con runAsNonRoot"
}

deny contains msg if {
	is_config_cli_job
	job_pod.securityContext.seccompProfile != {"type": "RuntimeDefault"}
	msg := "config-cli-security: seccompProfile RuntimeDefault"
}

deny contains msg if {
	is_config_cli_job
	some c in job_containers
	not container_secure(c)
	msg := sprintf("config-cli-security: %s: allowPrivilegeEscalation false, readOnlyRootFilesystem, capabilities drop ALL", [c.name])
}

container_secure(c) if {
	c.securityContext.allowPrivilegeEscalation == false
	c.securityContext.readOnlyRootFilesystem == true
	c.securityContext.capabilities.drop == ["ALL"]
}

deny contains msg if {
	is_config_cli_job
	some c in job_containers
	not container_resources(c)
	msg := sprintf("config-cli-security: %s: requests y limits de cpu y memoria", [c.name])
}

container_resources(c) if {
	every section in ["requests", "limits"] {
		every resource in ["cpu", "memory"] {
			c.resources[section][resource]
		}
	}
}

deny contains msg if {
	is_config_cli_job
	job_pod.priorityClassName != "vectra-low"
	msg := "config-cli-security: priorityClassName vectra-low"
}

deny contains msg if {
	is_config_cli_job
	job_pod.serviceAccountName != config_cli_name
	msg := sprintf("config-cli-security: serviceAccountName %s (la identidad de F94 en flows.yaml)", [config_cli_name])
}

deny contains msg if {
	is_config_cli_job
	object.get(object.get(input.spec.template.metadata, "labels", {}), "app.kubernetes.io/name", "") != config_cli_name
	msg := sprintf("config-cli-security: la etiqueta app.kubernetes.io/name del pod debe ser %s (el selector de F94)", [config_cli_name])
}

deny contains msg if {
	is_config_cli_job
	object.get(object.get(input.spec.template.metadata, "annotations", {}), "config.alpha.linkerd.io/proxy-enable-native-sidecar", "") != "true"
	msg := "config-cli-security: sidecar nativo de Linkerd (config.alpha.linkerd.io/proxy-enable-native-sidecar: \"true\"), para que el Job termine"
}

deny contains msg if {
	is_config_cli_job
	object.get(object.get(input.metadata, "labels", {}), "vectra.io/criticality", "") != "medium"
	msg := "config-cli-security: vectra.io/criticality medium"
}

deny contains msg if {
	is_config_cli_job
	job_pod.restartPolicy != "Never"
	msg := "config-cli-security: restartPolicy Never"
}

# regla: config-cli-external-secrets
# Las tres ExternalSecret de la excepcion de kind leen solo las claves de la boveda de INF-U2-01.
deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name == "keycloak-bootstrap-admin"
	not bootstrap_admin_ok(input)
	msg := "config-cli-external-secrets: keycloak-bootstrap-admin lee exactamente identity/keycloak-admin (username y password)"
}

bootstrap_admin_ok(doc) if {
	doc.spec.secretStoreRef == {"name": "vectra-store", "kind": "ClusterSecretStore"}
	doc.spec.target == {"name": "keycloak-bootstrap-admin"}
	doc.spec.data == [
		{"secretKey": "username", "remoteRef": {"key": "identity/keycloak-admin", "property": "username"}},
		{"secretKey": "password", "remoteRef": {"key": "identity/keycloak-admin", "property": "password"}},
	]
	object.keys(doc.spec) == {"secretStoreRef", "target", "data"}
	doc.metadata.namespace == namespace
}

# Una entrada por cliente: `identity/clients/<id>`, propiedad `jwks`, como `<id con guiones bajos>`. El Secret lleva `CLIENT_<ID>_JWKS` con el
# JWKS entre comillas JSON (`toJson`): keycloak-config-cli sustituye el texto en el YAML del realm (`jwks.string: $(env:...)`), y un JWKS sin
# comillas se leeria como un mapa YAML, no como la cadena que exige el atributo (probado con la imagen 6.5.1-26.5.5).
deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name == "keycloak-realm-clients-jwks"
	some item in input.spec.data
	not jwks_item_ok(item)
	msg := sprintf("config-cli-external-secrets: %s: debe leer identity/clients/<id>, propiedad jwks, con <id> en guiones bajos", [item.secretKey])
}

jwks_item_ok(item) if {
	regex.match(`^[a-z0-9]+(_[a-z0-9]+)*$`, item.secretKey)
	item.remoteRef == {"key": sprintf("identity/clients/%s", [replace(item.secretKey, "_", "-")]), "property": "jwks"}
}

deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name == "keycloak-realm-clients-jwks"
	keys := {k | some item in input.spec.data; k := sprintf("CLIENT_%s_JWKS", [upper(item.secretKey)])}
	input.spec.target.template.data != {k: sprintf("{{ .%s | toJson }}", [lower(replace(replace(k, "CLIENT_", ""), "_JWKS", ""))]) | some k in keys}
	msg := "config-cli-external-secrets: keycloak-realm-clients-jwks: el template lleva CLIENT_<ID>_JWKS = {{ .<id> | toJson }} por cada cliente"
}

# Una entrada por variable `SYNTH_<USUARIO>_*`, con la propiedad del mismo nombre (regla de INF-U2-01).
deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name == "keycloak-realm-synthetic-users"
	some item in input.spec.data
	not synth_item_ok(item)
	msg := sprintf("config-cli-external-secrets: %s: SYNTH_* debe leer identity/synthetic-users con la propiedad del mismo nombre", [item.secretKey])
}

synth_item_ok(item) if {
	regex.match(`^SYNTH_[A-Z0-9_]+_(PASSWORD|TOTP_SEED)$`, item.secretKey)
	item.remoteRef == {"key": "identity/synthetic-users", "property": item.secretKey}
}

deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name in {"keycloak-realm-clients-jwks", "keycloak-realm-synthetic-users"}
	not external_secret_shape_ok(input)
	msg := sprintf("config-cli-external-secrets: %s: store vectra-store, target con su nombre, sin dataFrom, en vectra-identity", [input.metadata.name])
}

external_secret_shape_ok(doc) if {
	doc.spec.secretStoreRef == {"name": "vectra-store", "kind": "ClusterSecretStore"}
	doc.spec.target.name == doc.metadata.name
	object.keys(doc.spec) == {"secretStoreRef", "target", "data"}
	doc.metadata.namespace == namespace
}

# Solo el de los clientes lleva template; el de los usuarios sinteticos entrega las propiedades tal cual.
deny contains msg if {
	input.kind == "ExternalSecret"
	input.metadata.name == "keycloak-realm-synthetic-users"
	object.keys(input.spec.target) != {"name"}
	msg := "config-cli-external-secrets: keycloak-realm-synthetic-users: el target lleva solo el nombre"
}

# regla: config-cli-realm
# El realm de kind va en su ConfigMap, con la clave `realm.kind.yaml` y el texto del realm de Git sin tocar (se verifica en las pruebas).
deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "keycloak-config-cli-realm"
	object.keys(input.data) != {"realm.kind.yaml"}
	msg := "config-cli-realm: el ConfigMap lleva exactamente la clave realm.kind.yaml"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "keycloak-config-cli-realm"
	not startswith(input.data["realm.kind.yaml"], "#")
	msg := "config-cli-realm: realm.kind.yaml debe ser el realm de Git, sin tocar"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "keycloak-config-cli-realm"
	input.metadata.namespace != namespace
	msg := sprintf("config-cli-realm: ConfigMap %s fuera de %s", [input.metadata.name, namespace])
}
