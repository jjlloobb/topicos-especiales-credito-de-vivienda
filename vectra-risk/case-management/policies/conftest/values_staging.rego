package values.staging

import rego.v1

# regla: staging-no-run-id
# INF-U8-03: el Job de la demostracion de RT-5 es solo de kind; ni la corrida ni el interruptor van en staging.
deny contains msg if {
	"runId" in object.keys(object.get(input, "probes", {}))
	msg := "staging-no-run-id: probes.runId no va en los values de staging (INF-U8-03, INF-U12-02)"
}

deny contains msg if {
	object.get(input, ["probes", "enabled"], false) != false
	msg := "staging-no-run-id: probes.enabled no va en los values de staging"
}
