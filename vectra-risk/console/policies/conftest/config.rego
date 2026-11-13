# Las variables del BFF y el `config.json` de la SPA (INF-U10-01, 03; Paso 18). Mismo paquete que `common.rego`.
# `data.realm` (cliente y `redirectUris` del realm de U2 en el entorno) llega por `--data`: `conftest` no lee el realm.
package main

import rego.v1

# regla: bff-env
# Exactamente las variables del ConfigMap de `console_bff.app` (REQUIRED mas VECTRA_CA_BUNDLE) y la de telemetria (F61). Una constante de `console_bff/config.py` no es una variable.
bff_variables := {
	"VECTRA_CASE_URL", "VECTRA_GOVERNANCE_URL", "VECTRA_REGISTRY_URL", "VECTRA_EXPLAINABILITY_URL", "VECTRA_BIAS_URL",
	"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE", "VECTRA_OTLP_ENDPOINT",
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-bff-config"
	some name, _ in input.data
	not name in bff_variables
	msg := sprintf("bff-env: la variable %s no es de console_bff.app ni de U0", [name])
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-bff-config"
	some name in bff_variables
	not name in object.keys(input.data)
	msg := sprintf("bff-env: falta la variable %s", [name])
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-bff-config"
	some name in ["VECTRA_CASE_URL", "VECTRA_GOVERNANCE_URL", "VECTRA_REGISTRY_URL", "VECTRA_EXPLAINABILITY_URL", "VECTRA_BIAS_URL"]
	not endswith(input.data[name], ".svc.cluster.local:8080")
	msg := sprintf("bff-env: %s apunta al puerto 8080 de un Service del cluster (F10 a F14)", [name])
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-bff-config"
	some name in ["VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL"]
	not startswith(input.data[name], "https://")
	msg := sprintf("bff-env: %s va por https", [name])
}

# regla: config-json-keys
# `SCHEMA` de `console/spa/src/config/load.ts`: ni una clave mas ni una menos.
spa_config := json.unmarshal(input.data["config.json"]) if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not object.keys(input.data) == {"config.json"}
	msg := "config-json-keys: el ConfigMap lleva solo config.json"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not object.keys(spa_config) == {"oidc", "redirect_uri", "stepup_redirect_uri", "grafana"}
	msg := sprintf("config-json-keys: las claves son oidc, redirect_uri, stepup_redirect_uri y grafana, no %v", [object.keys(spa_config)])
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not object.keys(spa_config.oidc) == {"authority", "client_id"}
	msg := "config-json-keys: oidc lleva authority y client_id"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not object.keys(spa_config.grafana) == {"bias_dashboard_uid"}
	msg := "config-json-keys: grafana lleva bias_dashboard_uid"
}

# regla: config-json-no-secrets
# Ninguna clave con nombre de secreto ni valor con forma de llave (PEM o JWT): el cliente es publico (PKCE).
secret_words := ["secret", "password", "token", "key"]

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	some path, _ in walk_keys
	some word in secret_words
	contains(lower(path), word)
	msg := sprintf("config-json-no-secrets: la clave %s parece de un secreto (%s)", [path, word])
}

walk_keys[key] if {
	walk(spa_config, [path, _])
	count(path) > 0
	key := path[count(path) - 1]
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	some path, value in walked_strings
	regex.match(`-----BEGIN |^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$`, value)
	msg := sprintf("config-json-no-secrets: el valor de %s tiene forma de llave", [path])
}

walked_strings[key] := value if {
	walk(spa_config, [path, value])
	is_string(value)
	key := concat(".", [sprintf("%v", [p]) | some p in path])
}

# regla: config-json-realm
# El cliente y los dos `redirect_uri` son los del cliente publico de U2 en este entorno (BR-U10-06).
deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not data.realm
	msg := "config-json-realm: faltan los datos del realm (--data con realm.client_id y realm.redirect_uris)"
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	not spa_config.oidc.client_id == data.realm.client_id
	msg := sprintf("config-json-realm: client_id %v no es el del realm (%v)", [spa_config.oidc.client_id, data.realm.client_id])
}

deny contains msg if {
	input.kind == "ConfigMap"
	input.metadata.name == "console-spa-config"
	uris := {spa_config.redirect_uri, spa_config.stepup_redirect_uri}
	not uris == {u | some u in data.realm.redirect_uris}
	msg := sprintf("config-json-realm: los redirect_uri %v no son los del realm %v", [uris, data.realm.redirect_uris])
}
