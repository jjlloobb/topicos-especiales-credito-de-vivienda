# El Deployment `bias-monitoring-service` (INF-U9-01; NFR-U9-10 a 12). Mismo paquete que `common.rego`.
package main

import rego.v1

# regla: service-replicas
# 2 replicas fijas con la exencion de U1: no hay HPA (INF-U9-01; NFR-U9-11).
deny contains msg if {
	is_service
	input.spec.replicas != 2
	msg := sprintf("service-replicas: el servicio lleva 2 replicas fijas, no %v", [input.spec.replicas])
}

deny contains msg if {
	is_service
	object.get(input.metadata, ["annotations", "vectra.io/hpa-exempt"], "") == ""
	msg := "service-replicas: falta la anotacion vectra.io/hpa-exempt (la exencion de require-hpa-bounds)"
}

# regla: service-rollout
deny contains msg if {
	is_service
	input.spec.strategy != {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
	msg := "service-rollout: RollingUpdate con maxSurge 1 y maxUnavailable 0"
}

# regla: service-spread
deny contains msg if {
	is_service
	zones := [t | some t in object.get(service_pod, "topologySpreadConstraints", []); t.topologyKey == "topology.kubernetes.io/zone"]
	count(zones) == 0
	msg := "service-spread: reparto por zona (topology.kubernetes.io/zone)"
}

# regla: service-priority
deny contains msg if {
	is_service
	object.get(service_pod, "priorityClassName", "") != "vectra-normal"
	msg := sprintf("service-priority: el servicio es vectra-normal, no %s", [object.get(service_pod, "priorityClassName", "")])
}

# regla: service-criticality
deny contains msg if {
	is_service
	not object.get(input.metadata.labels, "vectra.io/criticality", "") in {"critical", "high", "medium"}
	msg := "service-criticality: falta la etiqueta vectra.io/criticality (require-criticality-label)"
}

# regla: service-prestop
# El `preStop` de 5 s es un campo del Deployment (U09-T03).
deny contains msg if {
	is_service
	object.get(service_container, ["lifecycle", "preStop", "sleep", "seconds"], 0) != 5
	msg := "service-prestop: lifecycle.preStop.sleep.seconds es 5"
}

# regla: service-probes
deny contains msg if {
	is_service
	object.get(service_container, ["readinessProbe", "httpGet", "path"], "") != "/readyz"
	msg := "service-probes: la readiness es /readyz (NFR-U9-12)"
}

deny contains msg if {
	is_service
	object.get(service_container, ["livenessProbe", "httpGet", "path"], "") != "/healthz"
	msg := "service-probes: la liveness es /healthz (NFR-U9-12)"
}

deny contains msg if {
	is_service
	some probe in ["readinessProbe", "livenessProbe"]
	object.get(service_container, [probe, "httpGet", "port"], "") != "metrics"
	msg := sprintf("service-probes: %s apunta al puerto de operacion (metrics, 8081)", [probe])
}

# regla: service-ports
deny contains msg if {
	is_service
	ports := {[p.name, p.containerPort] | some p in service_container.ports}
	ports != {["http", 8080], ["metrics", 8081]}
	msg := "service-ports: 8080 (http) y 8081 (metrics)"
}

# regla: service-command
deny contains msg if {
	is_service
	service_container.command != ["python", "-m", "vectra_bias.app"]
	msg := "service-command: el servicio ejecuta python -m vectra_bias.app"
}

# regla: service-env
# Solo las variables del codigo: ninguna constante (INF-U9-03) y ninguna del CronJob (el servicio no habla con governance ni con el Pushgateway).
deny contains msg if {
	is_service
	some e in service_container.env
	not e.name in service_env
	msg := sprintf("service-env: %s no es una variable del servicio; las constantes del codigo no son configuracion (INF-U9-03)", [e.name])
}

deny contains msg if {
	is_service
	names := {e.name | some e in service_container.env}
	missing := service_env - names
	count(missing) > 0
	msg := sprintf("service-env: faltan %v", [missing])
}

# regla: service-identity
deny contains msg if {
	is_service
	env_value("VECTRA_CLIENT_ID", service_container) != "bias-monitoring-service"
	msg := "service-identity: VECTRA_CLIENT_ID es bias-monitoring-service"
}

deny contains msg if {
	is_service
	service_pod.serviceAccountName != "bias-monitoring-service"
	msg := "service-identity: la cuenta de servicio es bias-monitoring-service"
}

env_value(name, container) := value if {
	some e in container.env
	e.name == name
	value := e.value
}

# regla: service-pdb-doc
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.spec.minAvailable != 1
	msg := "service-pdb-doc: minAvailable 1"
}

# regla: service-doc
# El Service se llama como lo busca governance (`biasUrl`, F25) y expone 8080 y 8081.
deny contains msg if {
	input.kind == "Service"
	input.metadata.name != "bias-monitoring-service"
	msg := sprintf("service-doc: el Service es bias-monitoring-service (biasUrl de governance), no %s", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	ports := {p.port | some p in input.spec.ports}
	ports != {8080, 8081}
	msg := "service-doc: el Service expone 8080 (F14, F25) y 8081 (F60)"
}
