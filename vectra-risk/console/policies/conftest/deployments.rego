# Los dos Deployment de U10 (INF-U10-01; NFR-U10-10, 12, 20, 22). Mismo paquete que `common.rego`.
package main

import rego.v1

# regla: replicas
# Las dos piezas rinden 2 replicas; el BFF las escala el HPA y la SPA es fija, con la exencion de U1 y su justificacion.
deny contains msg if {
	is_deployment
	not input.spec.replicas == 2
	msg := sprintf("replicas: %s tiene 2 replicas, no %v", [input.metadata.name, object.get(input.spec, "replicas", "ninguna")])
}

# regla: exempt
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	trim_space(object.get(input.metadata, ["annotations", "vectra.io/hpa-exempt"], "")) == ""
	msg := "exempt: falta la anotacion vectra.io/hpa-exempt con su justificacion (la exencion de require-hpa-bounds; NFR-U10-12)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	object.get(input.metadata, ["annotations", "vectra.io/hpa-exempt"], "") != ""
	msg := "exempt: el BFF escala con HPA y no lleva la exencion"
}

# regla: rollout
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not input.spec.strategy == {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
	msg := "rollout: console-bff usa RollingUpdate con maxSurge 1 y maxUnavailable 0"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	not input.spec.strategy == {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": "100%", "maxUnavailable": 0}}
	msg := "rollout: console-spa usa RollingUpdate con maxSurge 100% y maxUnavailable 0"
}

# regla: resources-bff
# INF-U10-01: 250m / 256 MiB y 1 CPU / 512 MiB. kind pide 128 MiB de memoria (P-1 = b): lo decide `data.env`.
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.resources.limits == {"cpu": "1", "memory": "512Mi"}
	msg := "resources-bff: limits 1 CPU / 512Mi (INF-U10-01)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.resources.requests.cpu == "250m"
	msg := "resources-bff: request de CPU 250m (INF-U10-01)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	expected := bff_memory_request
	not container.resources.requests.memory == expected
	msg := sprintf("resources-bff: request de memoria %s en %s (INF-U10-01; 128Mi solo en kind, P-1), no %v", [expected, data.env, object.get(container.resources.requests, "memory", "ausente")])
}

bff_memory_request := "128Mi" if data.env == "kind"

bff_memory_request := "256Mi" if {
	data.env != "kind"
}

# regla: resources-spa
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	not container.resources == {"requests": {"cpu": "50m", "memory": "32Mi"}, "limits": {"cpu": "200m", "memory": "64Mi"}}
	msg := "resources-spa: 50m / 32Mi y 200m / 64Mi (INF-U10-01)"
}

# regla: probes
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.readinessProbe.httpGet == {"path": "/readyz", "port": "metrics"}
	msg := "probes: readiness del BFF es /readyz en el puerto metrics (8081)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.livenessProbe.httpGet == {"path": "/healthz", "port": "metrics"}
	msg := "probes: liveness del BFF es /healthz en el puerto metrics (8081)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	some probe in ["readinessProbe", "livenessProbe"]
	not container[probe].httpGet == {"path": "/healthz", "port": "http"}
	msg := sprintf("probes: %s de la SPA es GET /healthz en el puerto http (8080)", [probe])
}

deny contains msg if {
	is_deployment
	container.startupProbe
	msg := "probes: sin startupProbe (INF-U10-01)"
}

# regla: shutdown
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.lifecycle.preStop.sleep.seconds == 5
	msg := "shutdown: preStop.sleep de 5 s (P-5 (a) de U10-T02)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	object.get(pod, "terminationGracePeriodSeconds", 0) < 20
	msg := "shutdown: terminationGracePeriodSeconds de al menos 20 (preStop 5 s + el apagado de U0, hasta 10 s)"
}

# regla: checksum-present
deny contains msg if {
	is_deployment
	not regex.match(`^[0-9a-f]{64}$`, object.get(input.spec.template.metadata.annotations, "checksum/config", ""))
	msg := sprintf("checksum-present: %s lleva checksum/config del ConfigMap en el pod template", [input.metadata.name])
}

# regla: spa-volumes
# `/tmp` (el `pid` y los temporales de nginx) es un `emptyDir`; `config.json` es un volumen completo en su directorio, nunca sobre la raiz de nginx.
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	not tmp_is_empty_dir
	msg := "spa-volumes: /tmp es un emptyDir (nginx corre con el sistema de archivos de solo lectura)"
}

tmp_is_empty_dir if {
	some m in container.volumeMounts
	m.mountPath == "/tmp"
	some v in pod.volumes
	v.name == m.name
	v.emptyDir
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	some m in container.volumeMounts
	startswith(m.mountPath, "/usr/share/nginx")
	msg := sprintf("spa-volumes: el montaje %s esta en %s: taparia index.html", [m.name, m.mountPath])
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-spa"
	count(pod.volumes) != 2
	msg := "spa-volumes: solo el emptyDir de /tmp y el ConfigMap de config.json"
}

# regla: bff-ca
# El JWKS va por `https`: sin `VECTRA_CA_BUNDLE` el proceso sale con codigo 2. La CA se monta de solo lectura del ConfigMap `vectra-internal-ca`.
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	count([v | some v in pod.volumes; v.configMap.name == "vectra-internal-ca"]) != 1
	msg := "bff-ca: el volumen de la CA es el ConfigMap vectra-internal-ca"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "console-bff"
	not container.envFrom == [{"configMapRef": {"name": "console-bff-config"}}]
	msg := "bff-ca: las variables salen solo del ConfigMap console-bff-config (envFrom)"
}
