# Entidades de dominio — U9 `bias-monitoring`

U9 no tiene base de datos propia. Lee conteos agregados del registro (U3) y publica
métricas. Las etiquetas (`MonitoringLabels`) y los resultados (`outcome`, `final_outcome`,
`decision`) son los de U0.

---

## 1. Lo que lee del registro (U3, F26)

### 1.1 `MonitoringMarginalCount` (proyección `monitoring_daily`, agregada en el servidor por rango; segunda revisión del FD de U9, 2026-10-08)

| Campo | Notas |
|---|---|
| `population` | `modelo` (recomendaciones, por día de `evaluated_at`) \| `humana` (decisiones, por día de `decided_at`) |
| `model_version_id` | De la recomendación (en `humana`, de la recomendación que referencia la decisión) |
| `range_id` | El rango pedido al que pertenece la suma (§1.2); el día no viaja: U3 suma los días del rango en el servidor |
| `attribute` | `sexo \| rango_edad \| region \| estrato` |
| `group` | El valor del atributo (U0 §2.2). **Marginal por atributo**: nunca la combinación de las cuatro etiquetas (revisión del FD de U9, 2026-10-08, H2) |
| `band` | `banda_capacidad_pago` |
| `result` | `modelo`: `outcome`; `humana`: `final_outcome` |
| `decision` | Solo en `humana`: `sigue \| se_aparta \| resuelve_revision` |
| `count` | Entero ≥ 0 |

Ya aplica la regla de una recomendación por caso (BR-U9-07): bias nunca ve casos. Cada
entrada suma una vez en cada uno de los cuatro atributos. Por rango, versión y población son
hasta 198 filas en `modelo` y 396 en `humana`, sea cual sea la cantidad de días (cuarta revisión del FD de U9, 2026-10-10).

### 1.2 `MonitoringWindow` (respuesta de la proyección)

Solicitud (`MonitoringQuery` de U0 §9.4): hasta **12 rangos** `{range_id, model_version_id?, population, from_day, to_day}`
(**4 por versión evaluada**: antes, después y últimos 7 días de `modelo`, y después de `humana`; con 12 caben 3 versiones). Si hay más versiones, bias hace **varias solicitudes** de ≤ 12 rangos y nunca omite una versión (tercera revisión del FD de U9, 2026-10-10). La **primera** solicitud lleva además `unattributable_range` = la ventana de la corrida (hoy − 29 a hoy); las siguientes no lo llevan, y su `unattributable_invalid` es 0. La respuesta trae `unattributable_invalid` como un **único valor por solicitud**, no por rango (séptima revisión del FD de U9, 2026-10-10). Antes de pedirlos, bias consulta
`versions`: por versión y población, el primer y el último día con datos (segunda revisión del FD de U9, 2026-10-08).

| Campo | Notas |
|---|---|
| `versions` | Por versión y población: `first_day`, `last_day` (para elegir las versiones evaluadas y el inicio de la ventana, BR-U9-08) |
| `counts` | `list[MonitoringMarginalCount]`, sumados por rango |
| `total_entries` | Por rango: entradas `recommendation` y `human_decision` de la versión, válidas más inválidas (una por entrada del registro) |
| `invalid_entries` | Por rango: total de inválidas de la versión |
| `unattributable_invalid` | Un **solo** valor por solicitud, sobre el `unattributable_range` que pide bias (hoy − 29 a hoy): decisiones de `humana` sin recomendación atribuible (fila `'-'` de U3). No va en `totals`, así que no se repite por rango (sexta revisión del FD de U9, 2026-10-10) |
| `invalid_seqs` | Como máximo los 100 `seq` más recientes de las inválidas (BR-U9-09) |
| `watermark_seq` | Hasta qué `seq` está al día el agregador |
| `lag_seconds` | Atraso del agregador: 0 si la marca de agua es la cabeza; si no, `now() − recorded_at` de la entrada más antigua con `seq` mayor que la marca (BR-U3-17). Con más de 30 min, la corrida falla (BR-U9-10) |

### 1.3 `FreezeRecord` (proyección `monitoring_freezes`)
`freeze_id`, `model_version_id`, `frozen_at`, `context_package` (§3.1 más lo que agrega
governance: `data_sources`, `initial_disparity`) y `resolution?`: `{action: reactivar |
descartar | investigar, recorded_at}` de la `frozen_resolution` posterior, si existe (`recorded_at` del registro, como en U0 §9.4 y U3; la reactivación tiene efecto al confirmarse; tercera revisión del FD de U9, 2026-10-10). La última
`reactivar` de una versión fija el inicio de su ventana (BR-U9-08; revisión del FD de U9, 2026-10-08, H1).

## 2. Cálculo (librería compartida)

### 2.1 `CountTable`
Por atributo: (grupo, banda) → (`favorable`, `total`). Es la entrada de la librería. Se
arma con los `MonitoringMarginalCount` de un rango (CronJob y servicio), o con `counts_from_records` a partir de
filas etiquetadas (U4 `model-validation-job`, U5).

### 2.2 `CellResult`

| Campo | Notas |
|---|---|
| `group`, `band` | — |
| `n` | Tamaño de la celda |
| `rate` | `favorable / n`; **ausente** si `n < n_min` |
| `status` | `suficiente \| muestra_insuficiente` |

### 2.3 `BandResult`

| Campo | Notas |
|---|---|
| `band` | `lt_20 \| 20_30 \| gt_30` |
| `difference` | `max − min` entre los grupos suficientes, sin `no_informado`; ausente con menos de 2 grupos suficientes |
| `extreme_pair` | Los dos grupos del máximo y del mínimo |
| `ci_95` | Intervalo de Newcombe de la diferencia del par extremo (contexto) |
| `n_band` | Suma de las celdas suficientes del atributo en la banda (peso) |

### 2.4 `AttributeResult`

| Campo | Notas |
|---|---|
| `attribute` | `sexo \| rango_edad \| region \| estrato` |
| `cells` | `list[CellResult]` |
| `bands` | `list[BandResult]` |
| `aggregate` | `Σ w_b · d_b` (BR-U9-04); ausente si ninguna banda tiene diferencia |
| `aggregate_ci_95` | `aggregate ± 1,96 · √(Σ w_b² · v_b)` |
| `population_difference` | Diferencia sin bandas (contexto, BR-U9-06), solo con celdas suficientes; sin la tasa de un grupo que tenga alguna celda insuficiente |
| `population_difference_partial` | `true` si se excluyó alguna celda insuficiente (precisado el 2026-10-10 por U9 NFR Requirements) |

### 2.5 `DisparityResult`

| Campo | Notas |
|---|---|
| `population` | `modelo \| humana` |
| `model_version_id`, `window_from`, `window_to` | — |
| `attributes` | Los cuatro `AttributeResult` |
| `model_aggregate` | La mayor agregada con valor; ausente si todas son insuficientes |
| `trigger_attribute` | El atributo de `model_aggregate` |
| `departure_rates` | Solo en `humana`: por grupo y banda, `se_aparta / (sigue + se_aparta)` (BR-U9-14) |

### 2.6 `FreezeDecision`
`freeze: bool` y `reason`: `supera_umbral`, `bajo_umbral`, `intervalo_incluye_cero` o
`muestra_insuficiente` (BR-U9-11).

### 2.7 `RunReport` (una corrida)
`run_id`, `started_at`, `finished_at`, `status` (`completa \| fallida`), `failure_reason?`,
por versión evaluada: el `DisparityResult` del modelo y el de las decisiones humanas, la
`FreezeDecision` y el resultado de la llamada a `freeze` (`congelado`, `409`, `fallido`);
`invalid_entries`, `total_entries`. No se guarda: se publica como métricas (BR-U9-20) y en
el log de la corrida (sin datos del solicitante).

## 3. Contratos hacia afuera

### 3.1 `FreezeContext` (paquete que envía bias a `freeze`, BR-U9-15)

| Campo | Notas |
|---|---|
| `model_version_id`, `computed_at` | — |
| `threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s`, `library_version` | Los cinco parámetros de BR-U9-13 y la versión de la librería (los tres nuevos, revisión del FD de U10, 2026-10-10, A7) |
| `before` | `DisparityResult` de hoy − 36 a hoy − 7 (días UTC), o `sin_datos` |
| `after` | `DisparityResult` de hoy − 29 a hoy |
| `last_7_days` | `DisparityResult` de hoy − 6 a hoy |
| `window_start` | Inicio de la ventana de la versión (BR-U9-08) |
| `truncated` | `true` si se quitaron celdas para no superar 48 KiB (BR-U9-15) |
| `trigger_attribute` | — |
| `implicated` | Grupos y bandas cuya diferencia supera el umbral |
| `affected_volume` | Recomendaciones de la versión en la ventana y cuántas fueron `favorable` |

Solo agregados: una celda insuficiente lleva solo su tamaño. Governance agrega
`data_sources` e `initial_disparity` (BR-U9-16).

### 3.2 `CompareSourceRequest` y `PrePostReport` (F25, BR-U9-17)
- Solicitud: `source_id`, `pre: list[CountTable]`, `post: list[CountTable]`, con los cuatro atributos en cada lista y sin atributos repetidos (como U0 §9.4; cuarta revisión del FD de U9, 2026-10-10).
- Respuesta: `source_id`, `pre: DisparityResult`, `post: DisparityResult`, `delta` (post − pre de cada agregada y de `model_aggregate`), `threshold_pp`, `n_min`, `truncated: bool`, `disclaimer`. JCS ≤ 48 KiB (BR-U9-17).

### 3.3 `DisparityView` (F14, BR-U9-18)
`model_version_id`, `window`, `computed_at`, `model: DisparityResult`, `human:
DisparityResult`, `threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s`, `invalid_entries`, `disclaimer` («mide y alerta,
no certifica»).

### 3.4 `FreezeSummary`
`freeze_id`, `model_version_id`, `frozen_at`, `trigger_attribute`, `model_aggregate`, `resolution?` (`{action, recorded_at}`, como U0 §9.4; cuarta revisión del FD de U9, 2026-10-10).

## 4. Configuración (values de Helm, BR-U9-13)

| Parámetro | Valor |
|---|---|
| `threshold_pp` | 5 **[INTERNO]** |
| `n_min` | 30 |
| `window_days` | 30 |
| `schedule` | cada 15 min |
| `stale_after` (W) | 1 h (SEV2); 2W = 2 h (SEV1) |
| `invalid_fail_ratio` | 0,01 |
| `freeze_retries` | 3 (1, 2 y 4 s) |
| `dashboard_cache` | 15 min |

## 5. Errores

| Situación | Respuesta |
|---|---|
| `get_context_package` de un `freeze_id` inexistente | 404 `not_found` |
| `compare_source` con tablas inválidas | 422 `validation_error` |
| Rol no permitido en F14 o scope ausente en F25 | 403, con `authz.denied` (BR-U0-73) |
| Registro no disponible en una consulta del dashboard | 503 `dependency_unavailable` (sin datos parciales) |
