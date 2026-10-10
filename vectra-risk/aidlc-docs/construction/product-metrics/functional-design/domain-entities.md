# Entidades de dominio — U11 `product-metrics`

U11 no tiene datos persistentes. Los tipos de entrada son los de la proyección `metrics` de U3
(con los cambios de business-rules §7); aquí se describen el estado en memoria, el resultado
del cálculo y las series publicadas.

---

## 1. Entradas leídas (proyección `metrics`, F28; reducidas en la revisión del FD de U11, 2026-10-10)

U11 lee solo entradas `human_decision`. Campos que usa, y para qué:

| Campo | Uso |
|---|---|
| `seq` | Lectura incremental y deduplicación |
| `decision`, `used_factors`, `explanation_viewed_before` | North Star, sostenida y tasa de consulta (BR-U11-03, 04, 07) |
| `actor_role` | Validación: debe ser `analista` (BR-U11-10) |
| `decided_at`, `recorded_at` | Día de la métrica; ventana de lectura y margen de 5 min (BR-U11-02, 10) |
| `recommendation_entry_id` | Solo para el log de las no atribuibles |
| `recommendation: {seq, outcome, model_version_id, evaluated_at, received_at, channel, attempt, first_evaluation} \| null` | Atribución, cortes y tiempo de originación (BR-U11-01, 05, 08) |

U11 no usa `case_id`, `final_outcome` ni las entradas `recommendation` y `explanation_view`, así
que no los guarda; la proyección `metrics` de U3 los sigue teniendo para otros usos.

## 2. Estado en memoria

| Estado | Contenido | Regla |
|---|---|---|
| `last_seq` | Último `seq` leído | BR-U11-11 |
| `decisions` | Las `human_decision` de §1 con `decided_at` de los últimos 35 días | BR-U11-11 |
| `last_full_recompute_at`, `last_success_at` | Momentos de la última recomputación completa y de la última lectura exitosa | BR-U11-11 |

Se pierde con un reinicio: el arranque hace una lectura completa.

## 3. Resultado del cálculo

`BusinessMetrics` (salida de `compute(entries, params, now)`):

| Campo | Contenido |
|---|---|
| `north_star` | Por periodo (`day`, `30d`, `month_to_date`, `month`; BR-U11-08): `numerator`, `denominator`, `rate?` (ausente si el denominador es 0), desglose `sustentada`, `cambiada`, `revision_resuelta`; por `model_version_id` |
| `explanation_view_rate` | Ventana móvil de 7 días por día: `viewed`, `decisions`, `rate?` |
| `noise_days_below_floor` | Entero (BR-U11-07) |
| `sustained_ratio` | Como `north_star` (BR-U11-04) |
| `origination` | Por día: p50, p80, p95 en segundos y `standard_under_1h_ratio` (BR-U11-05) |
| `unattributable_decisions` | Conteo por día |
| `invalid_entries` | Conteo en la ventana de 30 días |
| `degraded` | `bool` (> 1 % excluidas) |

Cortes: `channel` y `outcome` en todas las métricas de decisión; `model_version_id` solo en
`north_star`. Nunca un identificador de usuario.

## 4. Parámetros (`values-product-metrics-policy.yaml`)

| Parámetro | Valor inicial | Rango |
|---|---|---|
| `noise_floor` (F) | 0,6 **[INTERNO]** | 0 < F < 1 |
| `noise_sustain_days` (S) | 3 **[INTERNO]** | 1..14 |
| `noise_min_decisions` (N) | 50 **[INTERNO]** | ≥ 30 |
| `target_complete_response` | 1,0 | 0..1 |
| `target_origination_hours` / `target_origination_ratio` | 1 h / 0,8 **[INTERNO]** | > 0 / 0..1 |
| `target_sustained_ratio_month6` | 0,7 **[INTERNO]** | 0..1 |
| `target_north_star` | `null` («sin target acordado») | `null` o 0..1 |

## 5. Series publicadas (`/metrics`)

| Serie | Etiquetas |
|---|---|
| `vectra_product_north_star_decisions` (conteo) | `period` (`day`, `30d`, `month_to_date`, `month`), `month` (`AAAA-MM`, solo con `period="month"`; NFR Requirements de U11, 2026-10-10), `part` (`numerator`, `denominator`), `channel`, `outcome`, `model_version_id` |
| `vectra_product_north_star_ratio` | `period`, y **una sola** de `channel`, `outcome` o `model_version_id` con su valor, las otras en `all`; o las tres en `all` (total) |
| `vectra_product_north_star_breakdown` (conteo) | `period`, `kind` (`sustentada`, `cambiada`, `revision_resuelta`), `channel`, `outcome` |
| `vectra_product_explanation_view_decisions` (conteo) | `period` (`7d`), `part`, `channel` |
| `vectra_product_explanation_view_ratio` | `period` (`7d`), `channel` (un valor o `all`) |
| `vectra_product_noise_days_below_floor` | — |
| `vectra_product_sustained_decisions` (conteo) | `period`, `part`, `channel`, `outcome` |
| `vectra_product_recommendation_sustained_ratio` | `period`, y `channel` u `outcome` con su valor y el otro en `all`; o los dos en `all` |
| `vectra_product_origination_seconds` | `quantile` (`0.5`, `0.8`, `0.95`), `standard` (`true`) |
| `vectra_product_origination_standard_under_target_ratio` | — |
| `vectra_product_unattributable_decisions` | `period` |
| `vectra_product_invalid_entries` | — |
| `vectra_product_metrics_degraded` | — |
| `vectra_product_metrics_last_success_timestamp` | — |
| `vectra_product_target` | `metric` (los targets de §4, para las líneas de referencia) |

**Series de operación del ciclo** (NFR-U11-40; agregadas a la allowlist en la revisión del NFR Requirements de U11, 2026-10-10):

| Serie | Etiquetas |
|---|---|
| `vectra_product_cycle_duration_seconds` (histograma) | `kind` (`incremental`, `full`) |
| `vectra_product_entries_read_total` (contador) | `kind` (`incremental`, `full`) |
| `vectra_product_last_full_recompute_timestamp` | — |
| `vectra_product_full_pass_in_progress` | — (revisión del NFR Design de U11, 2026-10-10) |
| `vectra_product_cycles_skipped_total` (contador) | — (revisión del NFR Design de U11, 2026-10-10) |
| `vectra_circuit_state` (de U0) | `dependency` (`decision-registry`) |

Además, las series estándar de `vectra_common.ops_server` (proceso de Python y `up`, que no
publica el servicio sino Prometheus) quedan fuera de la allowlist de U11 y las controla la
allowlist de U0.

Recording rules (BR-U11-06): `vectra:product_complete_response_ratio:1h`, `:1d` y
`vectra:product_desync_failclosed:rate1h`.

Allowlist: exactamente las series y etiquetas de las dos tablas de esta sección (producto y operación del ciclo), más las estándar de U0; una prueba falla si aparece otra. Las
razones con más de un corte a la vez no se publican: se calculan sumando los conteos (revisión del FD de U11, 2026-10-10).
