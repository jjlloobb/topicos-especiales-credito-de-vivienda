# El Service y el HPA (INF-U10-01, 06; NFR-U10-10). Mismo paquete que `common.rego`.
package main

import rego.v1

# regla: service-ports
# BFF: 8080 (F03) y 8081 (F60). SPA: 8080 (F02) y nada mas. Sin afinidad de sesion (BR-U10-02): la de la SPA es la cookie del gateway de U2.
deny contains msg if {
	input.kind == "Service"
	input.metadata.name == "console-bff"
	ports := {[p.name, p.port] | some p in input.spec.ports}
	not ports == {["http", 8080], ["metrics", 8081]}
	msg := "service-ports: el Service del BFF expone 8080 (http) y 8081 (metrics)"
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name == "console-spa"
	ports := {[p.name, p.port] | some p in input.spec.ports}
	not ports == {["http", 8080]}
	msg := "service-ports: el Service de la SPA expone solo el 8080"
}

deny contains msg if {
	input.kind == "Service"
	input.spec.sessionAffinity
	not input.spec.sessionAffinity == "None"
	msg := "service-ports: sin afinidad de sesion en el Service (BR-U10-02)"
}

deny contains msg if {
	input.kind == "Service"
	not input.spec.selector == {"app.kubernetes.io/name": input.metadata.name}
	msg := "service-ports: el selector es por app.kubernetes.io/name"
}

# regla: hpa-bff
# NFR-U10-10: de 2 a 6 por CPU al 70 %, con estabilizacion de 60 s hacia arriba y 300 s hacia abajo. INF-U10-06: en kind el maximo es 2 (de 2 a 2) y el HPA sigue presente.
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.minReplicas == 2
	msg := sprintf("hpa-bff: el minimo es 2, no %v", [object.get(input.spec, "minReplicas", "ninguno")])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	expected := hpa_max
	not input.spec.maxReplicas == expected
	msg := sprintf("hpa-bff: el maximo es %d en %s, no %v", [expected, data.env, object.get(input.spec, "maxReplicas", "ninguno")])
}

hpa_max := 2 if data.env == "kind"

hpa_max := 6 if {
	data.env != "kind"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.scaleTargetRef == {"apiVersion": "apps/v1", "kind": "Deployment", "name": "console-bff"}
	msg := "hpa-bff: el HPA apunta al Deployment console-bff"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.metrics == [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}}]
	msg := "hpa-bff: CPU al 70 % (NFR-U10-10)"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.behavior == {"scaleUp": {"stabilizationWindowSeconds": 60}, "scaleDown": {"stabilizationWindowSeconds": 300}}
	msg := "hpa-bff: estabilizacion de 60 s hacia arriba y 300 s hacia abajo"
}

# regla: monitor
deny contains msg if {
	input.kind == "ServiceMonitor"
	not input.spec.endpoints == [{"port": "metrics", "path": "/metrics", "interval": "30s", "honorLabels": true}]
	msg := "monitor: el ServiceMonitor raspa /metrics del puerto metrics (8081) con honorLabels"
}
