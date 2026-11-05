# Lo que exige ver los renders juntos: `conftest test --combine --namespace ratelimit_set` sobre el del banco y el de kind.
# Con --combine, `input` es [{path, contents}]. El nombre del directorio del render (`bank` o `kind`) dice cual es cual.
package ratelimit_set

import rego.v1

# Con --combine, un archivo de varios documentos llega como una entrada `{path, contents}` por documento.
images[env] := image if {
	some env in {"bank", "kind"}
	some entry in input
	endswith(entry.path, sprintf("/%s/render.yaml", [env]))
	entry.contents.kind == "ConfigMap"
	entry.contents.metadata.name == "envoy-gateway-config"
	image := yaml.unmarshal(entry.contents.data["envoy-gateway.yaml"]).provider.kubernetes.rateLimitDeployment.container.image
}

expected := {
	"bank": "registro.banco.internal/vectra/ratelimit@sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681",
	"kind": "kind-registry:5000/vectra/ratelimit@sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681",
}

# regla: registry-per-env
deny contains msg if {
	some env, want in expected
	not object.get(images, env, "") == want
	msg := sprintf("registry-per-env: la imagen de envoy-ratelimit en %s debe ser %s", [env, want])
}
