# `values-product-metrics-policy.yaml` renderizado (INF-U11-02; BR-U11-09): la regla evalua **el `data` del ConfigMap de parametros**, no el archivo suelto.
# Mismo paquete que `common.rego`. Los rangos son los de `vectra_product.config` (NOISE_*, TARGET_*): `tests/unit/test_chart.py` compara cada constante de
# abajo con la de `config.py`, y pasa la misma tabla de filas por `vectra_product.params.parse` y por esta regla, con el mismo veredicto en cada una.
package main

import rego.v1

policy_file := "values-product-metrics-policy.yaml"

policy_keys := {
	"noise_floor", "noise_sustain_days", "noise_min_decisions", "target_complete_response",
	"target_origination_hours", "target_origination_ratio", "target_sustained_ratio_month6", "target_north_star",
}

# --- los rangos (con el nombre de la constante de config.py que cada una sigue) ---
noise_floor_min_exclusive := 0 # NOISE_FLOOR_MIN_EXCLUSIVE

noise_floor_max_exclusive := 1 # NOISE_FLOOR_MAX_EXCLUSIVE

noise_sustain_days_min := 1 # NOISE_SUSTAIN_DAYS_MIN

noise_sustain_days_max := 14 # NOISE_SUSTAIN_DAYS_MAX

noise_min_decisions_min := 30 # NOISE_MIN_DECISIONS_MIN

target_ratio_min := 0 # TARGET_RATIO_MIN

target_ratio_max := 1 # TARGET_RATIO_MAX

target_origination_hours_min_exclusive := 0 # TARGET_ORIGINATION_HOURS_MIN_EXCLUSIVE

policy_data := yaml.unmarshal(input.data[policy_file]) if {
	is_policy
	input.data[policy_file]
}

# Un entero: `is_number` y sin parte fraccionaria (un booleano no es numero). `3.0` es el mismo numero que `3` para una regla que lee JSON; el render de
# helm normaliza `3.0` a `3`, de modo que el proceso lee lo mismo que la regla.
is_integer(v) if {
	is_number(v)
	v == round(v)
}

unit_closed(v) if {
	is_number(v)
	v >= target_ratio_min
	v <= target_ratio_max
}

# regla: policy-ranges
deny contains msg if {
	is_policy
	not input.data[policy_file]
	msg := sprintf("policy-ranges: el ConfigMap no trae %s", [policy_file])
}

deny contains msg if {
	is_policy
	not is_object(policy_data)
	msg := "policy-ranges: el archivo de parametros no es un mapa"
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	keys := {k | some k, _ in policy_data}
	keys != policy_keys
	msg := sprintf("policy-ranges: las claves deben ser exactamente las ocho de BR-U11-09; faltan %v y sobran %v", [policy_keys - keys, keys - policy_keys])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_floor
	not is_number(v)
	msg := "policy-ranges: noise_floor no es un numero"
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_floor
	is_number(v)
	not v > noise_floor_min_exclusive
	msg := sprintf("policy-ranges: noise_floor %v fuera de 0 < F < 1", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_floor
	is_number(v)
	not v < noise_floor_max_exclusive
	msg := sprintf("policy-ranges: noise_floor %v fuera de 0 < F < 1", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_sustain_days
	not is_integer(v)
	msg := "policy-ranges: noise_sustain_days no es un entero"
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_sustain_days
	is_integer(v)
	not v >= noise_sustain_days_min
	msg := sprintf("policy-ranges: noise_sustain_days %v fuera de 1..14", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_sustain_days
	is_integer(v)
	not v <= noise_sustain_days_max
	msg := sprintf("policy-ranges: noise_sustain_days %v fuera de 1..14", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_min_decisions
	not is_integer(v)
	msg := "policy-ranges: noise_min_decisions no es un entero"
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.noise_min_decisions
	is_integer(v)
	not v >= noise_min_decisions_min
	msg := sprintf("policy-ranges: noise_min_decisions %v menor que 30", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.target_origination_hours
	not is_number(v)
	msg := "policy-ranges: target_origination_hours no es un numero"
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.target_origination_hours
	is_number(v)
	not v > target_origination_hours_min_exclusive
	msg := sprintf("policy-ranges: target_origination_hours %v no es mayor que 0", [v])
}

deny contains msg if {
	is_policy
	is_object(policy_data)
	some key in {"target_complete_response", "target_origination_ratio", "target_sustained_ratio_month6"}
	v := policy_data[key]
	not unit_closed(v)
	msg := sprintf("policy-ranges: %s %v no es un numero entre 0 y 1", [key, v])
}

# `target_north_star` puede ser null: «sin target acordado».
deny contains msg if {
	is_policy
	is_object(policy_data)
	v := policy_data.target_north_star
	v != null
	not unit_closed(v)
	msg := sprintf("policy-ranges: target_north_star %v no es null ni un numero entre 0 y 1", [v])
}
