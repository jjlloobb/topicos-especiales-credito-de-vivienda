# El Deployment `product-metrics` (INF-U11-01, 03; NFR-U11-05, 20, 21). Mismo paquete que `common.rego`.
package main

import rego.v1

# regla: replicas
# 2 replicas fijas con la exencion de U1: no hay HPA (NFR-U11-05).
deny contains msg if {
	is_deployment
	input.spec.replicas != 2
	msg := sprintf("replicas: 2 replicas fijas, no %v", [input.spec.replicas])
}

deny contains msg if {
	is_deployment
	trim_space(object.get(input.metadata, ["annotations", "vectra.io/hpa-exempt"], "")) == ""
	msg := "replicas: falta la anotacion vectra.io/hpa-exempt con su justificacion (la exencion de require-hpa-bounds)"
}

# regla: rollout
deny contains msg if {
	is_deployment
	input.spec.strategy != {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
	msg := "rollout: RollingUpdate con maxSurge 1 y maxUnavailable 0"
}

# regla: deadlines
deny contains msg if {
	is_deployment
	object.get(input.spec, "progressDeadlineSeconds", 0) != 4800
	msg := "deadlines: progressDeadlineSeconds 4800 (la pasada completa y el reintento de U3 caido)"
}

deny contains msg if {
	is_deployment
	object.get(pod, "terminationGracePeriodSeconds", 0) != 10
	msg := "deadlines: terminationGracePeriodSeconds 10 (INF-U11-01)"
}

# regla: spread
deny contains msg if {
	is_deployment
	zones := [t | some t in object.get(pod, "topologySpreadConstraints", []); t.topologyKey == "topology.kubernetes.io/zone"]
	count(zones) == 0
	msg := "spread: reparto por zona (topology.kubernetes.io/zone)"
}

# regla: priority
deny contains msg if {
	is_deployment
	object.get(pod, "priorityClassName", "") != "vectra-normal"
	msg := sprintf("priority: product-metrics es vectra-normal, no %s", [object.get(pod, "priorityClassName", "")])
}

# regla: criticality
deny contains msg if {
	is_deployment
	not object.get(input.metadata.labels, "vectra.io/criticality", "") in {"critical", "high", "medium"}
	msg := "criticality: falta la etiqueta vectra.io/criticality (require-criticality-label)"
}

# regla: probes
deny contains msg if {
	is_deployment
	object.get(container, ["readinessProbe", "httpGet", "path"], "") != "/readyz"
	msg := "probes: la readiness es /readyz (NFR-U11-07)"
}

deny contains msg if {
	is_deployment
	object.get(container, ["livenessProbe", "httpGet", "path"], "") != "/healthz"
	msg := "probes: la liveness es /healthz (INF-U11-01)"
}

deny contains msg if {
	is_deployment
	some probe in ["readinessProbe", "livenessProbe"]
	object.get(container, [probe, "httpGet", "port"], "") != "metrics"
	msg := sprintf("probes: %s apunta al puerto de operacion (metrics, 8081)", [probe])
}

deny contains msg if {
	is_deployment
	container.startupProbe
	msg := "probes: sin startupProbe larga (INF-U11-01): el arranque no espera a U3"
}

# regla: ports
deny contains msg if {
	is_deployment
	ports := {[p.name, p.containerPort] | some p in container.ports}
	ports != {["metrics", 8081]}
	msg := "ports: solo 8081 (metrics); sin 8080"
}

# regla: command
deny contains msg if {
	is_deployment
	container.command != ["python", "-m", "vectra_product.main"]
	msg := "command: el contenedor ejecuta python -m vectra_product.main"
}

# regla: env
# Solo las variables de cableado: ninguna constante del codigo es configuracion (INF-U11-02).
deny contains msg if {
	is_deployment
	some e in container.env
	not e.name in container_env
	msg := sprintf("env: %s no es una variable del proceso; las constantes del codigo no son configuracion", [e.name])
}

deny contains msg if {
	is_deployment
	names := {e.name | some e in container.env}
	missing := container_env - names
	count(missing) > 0
	msg := sprintf("env: faltan %v", [missing])
}

# regla: identity-doc
deny contains msg if {
	is_deployment
	env_value("VECTRA_CLIENT_ID", container) != "product-metrics"
	msg := "identity-doc: VECTRA_CLIENT_ID es product-metrics"
}

deny contains msg if {
	is_deployment
	pod.serviceAccountName != "product-metrics"
	msg := "identity-doc: la cuenta de servicio es product-metrics (el sa de flows.yaml)"
}

env_value(name, c) := value if {
	some e in c.env
	e.name == name
	value := e.value
}

# regla: pdb-doc
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.spec.minAvailable != 1
	msg := "pdb-doc: minAvailable 1"
}

# regla: service-doc
# El Service se llama `product-metrics` (el `job` de las alertas) y expone solo 8081, tambien para pods aun no listos (INF-U11-04).
deny contains msg if {
	input.kind == "Service"
	input.metadata.name != "product-metrics"
	msg := sprintf("service-doc: el Service es product-metrics (el job de las alertas), no %s", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	ports := {p.port | some p in input.spec.ports}
	ports != {8081}
	msg := "service-doc: el Service expone solo 8081 (F60), sin 8080"
}

deny contains msg if {
	input.kind == "Service"
	not input.spec.publishNotReadyAddresses == true
	msg := "service-doc: publishNotReadyAddresses true (Prometheus raspa replicas aun no listas)"
}
