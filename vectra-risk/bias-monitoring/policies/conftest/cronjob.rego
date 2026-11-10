# El CronJob `bias-monitoring-job` y los parametros de cumplimiento (INF-U9-02 y 03; BR-U9-13). Mismo paquete que `common.rego`.
package main

import rego.v1

# regla: cronjob-shape
deny contains msg if {
	is_cronjob
	input.metadata.name != "bias-monitoring-job"
	msg := sprintf("cronjob-shape: el unico CronJob es bias-monitoring-job, no %s", [input.metadata.name])
}

deny contains msg if {
	is_cronjob
	not count(job_pod.containers) == 1
	msg := "cronjob-shape: el pod lleva un solo contenedor"
}

deny contains msg if {
	is_cronjob
	object.get(job_pod, "initContainers", []) != []
	msg := "cronjob-shape: el pod no lleva initContainers"
}

deny contains msg if {
	is_cronjob
	job_pod.restartPolicy != "Never"
	msg := "cronjob-shape: restartPolicy es Never"
}

deny contains msg if {
	is_cronjob
	job_container.command != ["python", "-m", "vectra_bias.run"]
	msg := "cronjob-shape: el CronJob ejecuta python -m vectra_bias.run"
}

# regla: concurrency
# Una sola corrida a la vez: Forbid y backoffLimit 0 (NFR-U9-13); nunca dos `freeze` en paralelo desde U9.
deny contains msg if {
	is_cronjob
	object.get(input.spec, "concurrencyPolicy", "") != "Forbid"
	msg := "concurrency: concurrencyPolicy es Forbid"
}

# regla: timezone
deny contains msg if {
	is_cronjob
	object.get(input.spec, "timeZone", "") != "Etc/UTC"
	msg := "timezone: timeZone es Etc/UTC"
}

# regla: deadlines
deny contains msg if {
	is_cronjob
	object.get(input.spec, "startingDeadlineSeconds", -1) != 300
	msg := sprintf("deadlines: startingDeadlineSeconds es 300, no %v", [object.get(input.spec, "startingDeadlineSeconds", "ausente")])
}

deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec, "activeDeadlineSeconds", -1) != 600
	msg := sprintf("deadlines: activeDeadlineSeconds es 600, no %v", [object.get(input.spec.jobTemplate.spec, "activeDeadlineSeconds", "ausente")])
}

deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec, "backoffLimit", -1) != 0
	msg := "deadlines: backoffLimit es 0"
}

# regla: history
deny contains msg if {
	is_cronjob
	object.get(input.spec, "successfulJobsHistoryLimit", -1) != 3
	msg := "history: successfulJobsHistoryLimit es 3"
}

deny contains msg if {
	is_cronjob
	object.get(input.spec, "failedJobsHistoryLimit", -1) != 3
	msg := "history: failedJobsHistoryLimit es 3"
}

# regla: cronjob-priority
deny contains msg if {
	is_cronjob
	object.get(job_pod, "priorityClassName", "") != "vectra-high"
	msg := sprintf("cronjob-priority: el CronJob es vectra-high, no %s", [object.get(job_pod, "priorityClassName", "")])
}

# regla: native-sidecar
deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec.template, ["metadata", "annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "") != "true"
	msg := "native-sidecar: bias-monitoring-job sin el sidecar nativo de Linkerd (P-U1-05)"
}

# regla: workload-label
# La etiqueta con la que `flows.yaml` selecciona al CronJob (F27, F50, F106).
deny contains msg if {
	is_cronjob
	object.get(input.spec.jobTemplate.spec.template.metadata.labels, "vectra.io/workload", "") != "bias-monitoring-job"
	msg := "workload-label: el pod lleva vectra.io/workload: bias-monitoring-job (F27, F50, F106)"
}

# regla: cronjob-identity
deny contains msg if {
	is_cronjob
	job_pod.serviceAccountName != "bias-monitoring-job"
	msg := "cronjob-identity: la cuenta de servicio es bias-monitoring-job"
}

deny contains msg if {
	is_cronjob
	env_value("VECTRA_CLIENT_ID", job_container) != "bias-monitoring-job"
	msg := "cronjob-identity: VECTRA_CLIENT_ID es bias-monitoring-job"
}

# regla: cronjob-env
deny contains msg if {
	is_cronjob
	some e in job_container.env
	not e.name in job_env
	msg := sprintf("cronjob-env: %s no es una variable del CronJob; las constantes del codigo no son configuracion (INF-U9-03)", [e.name])
}

deny contains msg if {
	is_cronjob
	names := {e.name | some e in job_container.env}
	missing := job_env - names
	count(missing) > 0
	msg := sprintf("cronjob-env: faltan %v", [missing])
}

# regla: cronjob-criticality
deny contains msg if {
	is_cronjob
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "high"
	msg := "cronjob-criticality: el CronJob lleva vectra.io/criticality: high"
}

# --- INF-U9-03: el horario y los rangos de los cinco parametros --------------------------------------------------------------------------

# El intervalo (5, 10 o 15 min) de un `schedule` valido: una lista de minutos en progresion aritmetica con desfase de 1 a 4 y el resto `*`.
interval_of(schedule) := interval if {
	fields := split(schedule, " ")
	count(fields) == 5
	array.slice(fields, 1, 5) == ["*", "*", "*", "*"]
	regex.match(`^\d{1,2}(,\d{1,2})*$`, fields[0])
	minutes := [to_number(m) | some m in split(fields[0], ",")]
	60 % count(minutes) == 0
	interval := 60 / count(minutes)
	interval in {5, 10, 15}
	every k, m in minutes {
		m == minutes[0] + k * interval
	}
	every m in minutes {
		m <= 59
		m % 5 in {1, 2, 3, 4}
	}
}

duration_seconds(value) := to_number(parts[1]) * {"s": 1, "m": 60, "h": 3600}[parts[2]] if {
	parts := regex.find_all_string_submatch_n(`^(\d+)([smh])$`, value, 1)[0]
}

policy := yaml.unmarshal(input.data["values-monitoring-policy.yaml"]) if is_policy

# Booleanos aparte por condicion: una llamada indefinida dentro de `not` deja indefinido el cuerpo y la regla no dispara; y el orden entre tipos
# de Rego hace que `"abc" >= 30` sea verdadero. Cada valor debe ser del tipo que `config.parse_policy` acepta, o la regla dispara.
number_in(value, low, high) if {
	is_number(value)
	value >= low
	value <= high
}

integer_in(value, low, high) if {
	number_in(value, low, high)
	value == floor(value)
}

# Una duracion valida de `config._DURATION`: `^\d+[smh]$`. Cualquier otra cosa ("1h30m", "90", "abc") no es una duracion.
valid_duration(value) if {
	is_string(value)
	regex.match(`^\d+[smh]$`, value)
}

stale_seconds_at_least(value, floor_s) if {
	valid_duration(value)
	duration_seconds(value) >= floor_s
}

# regla: policy-ranges
deny contains msg if {
	is_policy
	not number_in(policy.threshold_pp, 1, 20)
	msg := sprintf("policy-ranges: threshold_pp %v; debe ser un numero de 1 a 20 pp", [policy.threshold_pp])
}

deny contains msg if {
	is_policy
	not integer_in(policy.n_min, 30, 1000000000)
	msg := sprintf("policy-ranges: n_min %v; debe ser un entero y el piso es 30", [policy.n_min])
}

deny contains msg if {
	is_policy
	not integer_in(policy.window_days, 7, 90)
	msg := sprintf("policy-ranges: window_days %v; debe ser un entero de 7 a 90 dias", [policy.window_days])
}

# regla: policy-stale
# W es una duracion valida (`<n>s`, `<n>m` o `<n>h`), W >= 30 min y W >= 4 x el intervalo entre corridas.
deny contains msg if {
	is_policy
	not valid_duration(policy.stale_after)
	msg := sprintf("policy-stale: stale_after %v no es una duracion valida (<n>s, <n>m o <n>h)", [policy.stale_after])
}

deny contains msg if {
	is_policy
	valid_duration(policy.stale_after)
	not stale_seconds_at_least(policy.stale_after, 1800)
	msg := sprintf("policy-stale: stale_after %v; el piso es 30 min", [policy.stale_after])
}

stale_covers_interval(value, schedule) if {
	interval := interval_of(schedule)
	stale_seconds_at_least(value, 4 * interval * 60)
}

deny contains msg if {
	is_policy
	valid_duration(policy.stale_after)
	interval_of(policy.schedule)
	not stale_covers_interval(policy.stale_after, policy.schedule)
	msg := sprintf("policy-stale: stale_after %v es menos de 4 x el intervalo del horario", [policy.stale_after])
}

# regla: policy-schedule
deny contains msg if {
	is_policy
	not interval_of(policy.schedule)
	msg := sprintf("policy-schedule: el horario %q debe ser una lista de minutos con intervalo de 5, 10 o 15 min y desfase de 1 a 4 min", [policy.schedule])
}

# regla: schedule-vs-deadline
# Una corrida nunca pisa a la siguiente: activeDeadlineSeconds <= el intervalo en segundos.
deny contains msg if {
	is_cronjob
	interval := interval_of(input.spec.schedule)
	input.spec.jobTemplate.spec.activeDeadlineSeconds > interval * 60
	msg := sprintf("schedule-vs-deadline: activeDeadlineSeconds %v pasa del intervalo de %d min", [input.spec.jobTemplate.spec.activeDeadlineSeconds, interval])
}

deny contains msg if {
	is_cronjob
	not interval_of(input.spec.schedule)
	msg := sprintf("schedule-vs-deadline: el horario %q del CronJob no es valido", [input.spec.schedule])
}
