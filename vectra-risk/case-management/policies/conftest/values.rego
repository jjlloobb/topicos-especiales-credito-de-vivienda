# Reglas sobre los ARCHIVOS de values por entorno (NFR-U8-44; INF-U12-02), no sobre el render: `conftest test --namespace values.prod <archivo>` y
# `--namespace values.staging <archivo>`. Cada `# regla: x` tiene un caso en case-management/tests/unit/test_chart.py. Quedan fuera (enmienda §3 U8, fila 22)
# la regla de la firma de `retention.md` (diferida).
package values.prod

import rego.v1

# regla: prod-no-run-id
# INF-U8-03: el Job de la demostracion de RT-5 es solo de kind; ni la corrida ni el interruptor van en produccion.
deny contains msg if {
	"runId" in object.keys(object.get(input, "probes", {}))
	msg := "prod-no-run-id: probes.runId no va en los values de produccion (INF-U8-03, INF-U12-02)"
}

deny contains msg if {
	object.get(input, ["probes", "enabled"], false) != false
	msg := "prod-no-run-id: probes.enabled no va en los values de produccion"
}

# regla: prod-switches
# NFR-U8-44: en produccion `core.enabled`, `coreMock.enabled` y `allowTestScenarios` son `false`, y estan escritos.
deny contains msg if {
	object.get(input, ["core", "enabled"], null) != false
	msg := "prod-switches: core.enabled es false y esta escrito (NFR-U8-44)"
}

deny contains msg if {
	object.get(input, ["coreMock", "enabled"], null) != false
	msg := "prod-switches: coreMock.enabled es false y esta escrito (NFR-U8-44)"
}

deny contains msg if {
	object.get(input, "allowTestScenarios", null) != false
	msg := "prod-switches: allowTestScenarios es false y esta escrito (NFR-U8-44)"
}
