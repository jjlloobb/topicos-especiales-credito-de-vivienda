# Reglas de negocio — U9 `bias-monitoring`

Decisiones del plan (`bias-monitoring-functional-design-plan.md`, Q1–Q12) y de sus
aclaraciones (`bias-monitoring-functional-design-clarification-questions.md`, CQ1–CQ4).
Los IDs `BR-U9-xx` se referencian en los planes de tareas. Las etiquetas de monitoreo son
las de U0 §2.2; esta unidad **mide y alerta, no certifica** (FR-BIA-08).

---

## 1. Métrica (Q1, Q3; US-301, FR-BIA-01)

**BR-U9-01 — Tasa favorable.** Para un conjunto de recomendaciones, la tasa de un grupo es
`favorable / total` del grupo. `revision_requerida` cuenta como **no** favorable.

**BR-U9-02 — Celdas y muestra mínima.**
- Una **celda** es (atributo, grupo, banda de capacidad de pago). Los atributos son `sexo`, `rango_edad`, `region` y `estrato`; las bandas, `lt_20`, `20_30` y `gt_30`.
- Una celda con menos de `n_min = 30` casos es **insuficiente**: se reporta con su tamaño y la marca «muestra insuficiente», y **no** entra en ningún cálculo.
- Una banda con menos de 2 grupos suficientes no tiene diferencia y no entra en la agregada.
- El grupo `no_informado` se reporta, pero **no** entra en el máximo ni en el mínimo.

**BR-U9-03 — Diferencia por banda.** Para cada atributo y banda: `max(tasa) − min(tasa)`
entre los grupos suficientes (diferencia de paridad demográfica, la métrica de Fairlearn).
Se publica con el **par extremo** (los dos grupos) y el intervalo de confianza del 95 % de
Newcombe (método 10, híbrido de Wilson) para la diferencia de esas dos proporciones. Ese
intervalo es **contexto**: no decide.

**BR-U9-04 — Agregada del atributo** (Q3, regla precisada por el usuario).
- `D_a = Σ_b w_b · d_b`, con `d_b` la diferencia de la banda `b` y `w_b = n_b / Σ n_b`.
- `n_b` es el tamaño de la banda **contando solo sus celdas suficientes** del atributo y **sin** `no_informado`. La suma `Σ n_b` es solo sobre las bandas **con diferencia** (BR-U9-02); una banda sin diferencia no pesa. El valor y el intervalo usan los mismos pesos (revisión del FD de U9, 2026-10-08, H8).
- **Intervalo de la agregada** (aproximación normal): `Var(D_a) = Σ_b w_b² · v_b`, donde `v_b = ((U_b − L_b) / (2 · 1,96))²` sale del intervalo de Newcombe de la banda; el intervalo es `D_a ± 1,96 · √Var(D_a)`.
- Si ninguna banda tiene diferencia, la agregada del atributo es «muestra insuficiente».

**BR-U9-05 — Agregada del modelo.** Es la **mayor** de las cuatro agregadas por atributo
con valor. El atributo que la produce es el **atributo disparador**, y el paquete de contexto
lo indica.

**BR-U9-06 — Contexto sin bandas.** También se publica la diferencia sobre toda la población
del atributo, sin bandas. No decide nada: sirve para comparar con la agregada por bandas.
**Sin inferencia por resta** (precisado el 2026-10-10 por U9 NFR Requirements, Q7): si un grupo del atributo tiene al menos una celda
insuficiente en alguna banda, su tasa sin bandas **no** se publica (permitiría deducir la tasa
de la celda chica restando las de las celdas suficientes), y `population_difference` se calcula
solo con las celdas suficientes y se marca `population_difference_partial = true` (en la métrica, la etiqueta `partial="true"`). El total de una banda (`n_band`)
ya suma solo celdas suficientes, así que no filtra nada.

## 2. Qué se lee (Q4, Q5, Q12; CQ1, CQ2, CQ4)

**BR-U9-07 — Conteos agregados, no filas.**
- bias lee del registro (F26) la proyección `monitoring_daily` de U3: conteos **marginales por atributo** (versión, día, atributo, grupo, banda, resultado y, en decisiones, `decision`), hasta 198 filas por día y versión en `modelo` y hasta 396 en `humana` (cuarta revisión del FD de U9, 2026-10-10). **No** guarda ni recibe la combinación de las cuatro etiquetas, que podría reidentificar a una persona y no cabría en el límite de la proyección (revisión del FD de U9, 2026-10-08, H2). Nunca lee filas de recomendaciones ni decisiones.
- La métrica solo necesita marginales: cada atributo se mide por separado (BR-U9-03..06).
- **Una recomendación por caso** (Q5, CQ2): el agregador de U3 cuenta, por caso, la recomendación que referencia su `human_decision` o, si no hay decisión, la más reciente por `evaluated_at` (en empate, el mayor `seq`). Si la que cuenta cambia, el agregador resta la anterior y suma la nueva. Es una aproximación aceptada para los casos sin decisión: el error posible es contar una recomendación descartada del mismo caso y del mismo modelo.
- Las **decisiones humanas** se cuentan con las etiquetas de la recomendación que referencian (`recommendation_entry_id` → `seq`), por `decided_at`, con `final_outcome` y `decision`.
- Todo se mide con el **momento de negocio** (`evaluated_at`, `decided_at`), no con `recorded_at`.

**BR-U9-08 — Ventana y versión medida** (Q4).
- Ventana: **30 días UTC**: el día actual (parcial) y los 29 anteriores, por día de `evaluated_at` (o `decided_at`). U3 suma los días de cada rango en el servidor (segunda revisión del FD de U9, 2026-10-08). El día de `t − 30 d` no entra (revisión del FD de U9, 2026-10-08).
- Cada versión se mide por separado; las versiones nunca se mezclan.
- **Inicio de la ventana de una versión** = el más tardío entre: el primer día con datos de la versión, y el **día siguiente (fecha UTC) al `recorded_at` de su última reactivación** (tercera revisión del FD de U9, 2026-10-10) (`frozen_resolution` con acción `reactivar`, leída de `monitoring_freezes`). Sin esto, tras una reactivación la ventana conservaría los datos que provocaron el congelamiento y la corrida siguiente volvería a congelar, y los casos de U8 oscilarían entre `modelo_congelado` y `en_evaluacion` (revisión del FD de U9, 2026-10-08, H1).
- Tras una reactivación, la versión vuelve a reunir muestra: hasta entonces su resultado es «muestra insuficiente» y no se congela. Cumplimiento reactivó con justificación y el dashboard lo muestra.
- **Versiones evaluadas para congelar**: las que tienen recomendaciones el día actual o el anterior (en la práctica, la activa y, durante una promoción, la saliente). Las demás solo aparecen en el dashboard.

**BR-U9-09 — Entradas inválidas** (Q12 = X, CQ4).
- El agregador de U3 no suma en las celdas una entrada cuyas etiquetas no pertenecen al catálogo de U0 §2.2: la cuenta como inválida y guarda su `seq`.
- La proyección devuelve, con los conteos, el **total** de entradas `recommendation` y `human_decision` de la versión en la ventana (válidas más inválidas, una por entrada del registro, no por caso), el total de inválidas y como máximo los **100 `seq`** más recientes de las inválidas.
- bias excluye las inválidas, publica `vectra_bias_invalid_entries`, registra los `seq` recibidos en el log (sin datos del solicitante) y dispara `BiasInvalidEntries` (SEV2, a ingeniería de datos) si hay al menos una en la ventana.
- **Razón de inválidas de una corrida** (quinta revisión del FD de U9, 2026-10-10): numerador = las `invalid_entries` de los rangos «después» (de `modelo` **y** de `humana`) de todas las versiones evaluadas, más `unattributable_invalid`, que se toma **una sola vez**: bias envía `unattributable_range` = la ventana de la corrida (hoy − 29 a hoy) solo en la **primera** solicitud, y la respuesta lo devuelve como un único valor por solicitud (séptima revisión del FD de U9, 2026-10-10); denominador = las `total_entries` de esos mismos rangos más el mismo `unattributable_invalid` (sexta revisión del FD de U9, 2026-10-10) (las no atribuibles cuentan en los dos lados, porque son entradas de la ventana que no pertenecen a ninguna versión). `BiasInvalidEntries` salta si el numerador es > 0.
- La corrida **falla** solo si esa razón supera el **1 %**. Motivo: U3 valida las etiquetas al escribir, así que una inválida es un defecto; si un solo registro detuviera el monitoreo, el modelo dejaría de vigilarse hasta 30 días.

## 3. Corrida y congelamiento (Q3, Q4, Q6; US-303, FR-BIA-03, AUTONOMIA-04)

**BR-U9-10 — Corrida.**
- CronJob cada **15 min**. Una corrida lee los conteos, calcula el modelo y las decisiones humanas de cada versión, evalúa el congelamiento, llama a `freeze` si corresponde y publica las métricas.
- **Todo o nada**: si falla la lectura del registro, la librería o el cálculo, las inválidas superan el 1 % o el agregador de U3 está **atrasado** (BR-U3-17: hay entradas con `seq` mayor que la marca de agua y la más antigua de ellas tiene `recorded_at` de hace más de 30 min; con la marca igual a la cabeza el atraso es 0, aunque el registro no tenga tráfico; revisión del FD de U9, 2026-10-08, H5), la corrida falla, **no** congela con datos parciales y **no** actualiza `vectra_bias_last_success_timestamp`. Igual publica las métricas de la corrida (BR-U9-20).
- Una corrida es **completa** cuando terminó el cálculo y, si correspondía, el `freeze` respondió con éxito o con 409.

**BR-U9-11 — Regla de congelamiento** (Q3, precisada por el usuario). Una versión evaluada
(BR-U9-08) se congela si y solo si:
- su agregada del modelo (BR-U9-05) es **> 5 pp**, **y**
- el **límite inferior** del intervalo de la agregada ponderada de ese atributo (BR-U9-04) es **> 0**.

Si todas las agregadas son «muestra insuficiente», no se congela. Una versión recién activada
sirve hasta reunir muestra, y el dashboard lo muestra. La disparidad de las decisiones humanas
**nunca** congela (BR-U9-14).

**BR-U9-12 — Llamada a `freeze`** (Q6).
- bias llama a `POST /v1/models/{id}/freeze` (F27) con el paquete de contexto (BR-U9-15). Es la **única** llamada de bias a governance (X04, BR-U4-04).
- **Identidad** (revisión del FD de U9, 2026-10-08, H4): la llamada la hace **solo el CronJob**, con su propio cliente de Keycloak `bias-monitoring-job` (scopes `governance:freeze` y `registry:read:monitoring`). El servicio HTTP `bias-monitoring-service` tiene solo `registry:read:monitoring`: no puede congelar. El actor del evento `freeze` es `{kind: system, id: bias-monitoring-job}` (BR-U3-16), y es la identidad que admiten BR-U4-01, BR-U4-04 y `guard_freeze`.
- Governance responde 409 si la versión ya está `congelado` o no es la `activo`: la corrida lo registra y sigue; no es un error.
- Timeout, 5xx o error de conexión: **3 reintentos** en la misma corrida (1, 2 y 4 s). Si persiste, la corrida falla y salta `BiasFreezeFailed` (SEV1). La corrida siguiente vuelve a evaluar y a intentar.
- **Varias versiones** (precisado el 2026-10-10 por U9 NFR Design, Q4): la corrida intenta `freeze` en **todas** las versiones que cumplan la regla aunque falle en una; al final queda fallida si alguna falló, con `vectra_bias_freeze_failed` = 1 solo para esa versión (P-U9-01). El CronJob no usa circuit breaker (P-U9-02).
- bias **nunca** reactiva ni pide reactivar. Una medición posterior bajo el umbral no hace nada sobre un modelo congelado (US-303, FR-BIA-05).

**BR-U9-13 — Parámetros.** Umbral (5 pp), `n_min` (30), ventana (30 días), frecuencia
(15 min) y W (1 h) son values de Helm versionados en Git. Cambiarlos exige un PR revisado
por cumplimiento. Sus valores viajan en cada paquete y en cada respuesta del dashboard.

## 4. Decisiones humanas (Q2; US-302, FR-BIA-02)

**BR-U9-14 — Disparidad de las decisiones humanas.**
- Misma métrica (BR-U9-01..05), con `final_outcome = favorable` como resultado, por versión del modelo de la recomendación, en la misma ventana por `decided_at`.
- Se reporta **aparte** de la del modelo.
- Si cumple la regla de BR-U9-11 → alerta `DisparidadDecisionHumana` (SEV2, a cumplimiento). **Nunca** llama a `freeze`.
- Además se reporta, por grupo y banda, la **tasa de apartamiento**: `se_aparta / (sigue + se_aparta)`. `resuelve_revision` no entra, porque no hay recomendación favorable o desfavorable de la que apartarse (BR-U0-35).

## 5. Paquete de contexto (Q7; CQ3; US-304, FR-BIA-04)

**BR-U9-15 — Contenido que arma bias.**
- `model_version_id`, `computed_at`, umbral, `n_min` y versión de la librería.
- Tres mediciones de la versión, cada una con las cuatro agregadas por atributo, sus intervalos y, por banda, tasas, diferencias y tamaños:
  - **antes**: los 30 días UTC que terminan 7 días antes (de hoy − 36 a hoy − 7);
  - **después**: la ventana de la corrida (de hoy − 29 a hoy);
  - **últimos 7 días**: de hoy − 6 a hoy, porque la ventana desplazada comparte 23 días con la actual y diluiría un cambio reciente.
- Las tres respetan el inicio de la ventana de la versión (BR-U9-08).
- Si la versión tiene menos de 7 días con datos, el «antes» es «sin datos» y el paquete lo dice.
- Atributo disparador, grupos y bandas implicados (los de las bandas cuya diferencia supera el umbral) y volumen afectado: recomendaciones de la versión en la ventana y cuántas fueron `favorable`.
- **Sin datos de ningún solicitante**: solo conteos y tasas; una celda insuficiente lleva solo su tamaño.
- **Tamaño** (revisión del FD de U9, 2026-10-08, H10): el paquete canónico (JCS) no supera **48 KiB**, para que el evento `freeze` quepa en los 64 KiB del registro (BR-U3-07) con lo que agrega governance. Si los supera, bias quita, en este orden, las celdas de `before`, las de `last_7_days` y las de `after`, y conserva siempre las agregadas, las bandas y el atributo disparador; el paquete indica `truncated = true`. El congelamiento **nunca** espera ni se omite por el tamaño del paquete.

**BR-U9-16 — Lo que agrega governance.** Al recibir el `freeze`, governance agrega al paquete
las `data_sources` de la versión y su `initial_disparity` de la validación, y lo escribe en el
evento `freeze` del registro (BR-U4-15). Si el evento superara 60 KiB, governance reemplaza
`initial_disparity` por sus agregadas (sin celdas); si aún superara 64 KiB, reduce
`data_sources` a sus ids (revisión del FD de U9, 2026-10-08, H10; tercera revisión del FD de U9, 2026-10-10).

## 6. Fuente nueva (Q10; US-306, FR-BIA-06)

**BR-U9-17 — `compare_source(source_id, pre, post)`** (F25, scope `bias:compare`).
- `pre` y `post` son listas de `CountTable` (U0 §9.4), una por atributo: por (grupo, banda), `favorable` y `total`. El Job cuenta por resultado y reduce a esas dos cifras (`revision_requerida` cuenta como no favorable, BR-U9-01) (cuarta revisión del FD de U9, 2026-10-10). `pre` viene de la versión activa y `post` de la versión candidata que declara la fuente, las dos puntuadas por el `model-validation-job` sobre el mismo dataset de validación (U4).
- Nunca llegan combinaciones de etiquetas por registro, que podrían reidentificar a una persona.
- bias devuelve `PrePostReport`: las métricas de BR-U9-01..06 para cada tabla y la diferencia post − pre de cada agregada. No guarda nada.
- Tablas con conteos negativos, grupos o bandas fuera del catálogo, o atributos faltantes → `422 validation_error`, sin cálculo parcial.
- **Tamaño** (tercera revisión del FD de U9, 2026-10-10): el `PrePostReport` canónico no supera **48 KiB**, porque viaja en el evento `data_source_event` (U4 BR-U4-13; registro ≤ 64 KiB). Si los supera, bias quita las celdas de `pre` y después las de `post`, conserva siempre las agregadas, las bandas y `delta`, y marca `truncated = true`.

## 7. Consulta (Q8, Q11; US-304, US-307, FR-UI-05)

**BR-U9-18 — `get_disparity(filter)`** (F14; `cumplimiento` y `cro`).
- Filtros: versión, atributo y ventana (7, 30 o 90 días). Por omisión, **la servible** (la versión `activo` o, tras un congelamiento, la `congelado`; cuarta revisión del FD de U9, 2026-10-10): el BFF la consulta en governance con `list_models(state=activo,congelado)` (F11; sexta revisión del FD de U9, 2026-10-10) y la envía; bias no lee governance (X04). Si no llega, bias usa la versión con las recomendaciones más recientes (tercera revisión del FD de U9, 2026-10-10).
- Se recalcula a pedido desde `monitoring_daily`, con una caché de 15 min por filtro.
- La respuesta lleva, por atributo y banda, tasas, diferencias, intervalos, tamaños y las celdas insuficientes; la agregada del modelo y la de las decisiones humanas **separadas**; la tasa de apartamiento; umbral, `n_min` y `computed_at`.
- Aplica la regla sin inferencia por resta de BR-U9-06 (precisado el 2026-10-10 por U9 NFR Requirements).
- Cada consulta emite el log `disparity.viewed` con `principal_subject`, `principal_role`, `model_version_id` y la ventana (sin datos del solicitante), retenido ≥ 90 días (NFR-U9-32; evento del catálogo de U0 §8.1; revisión del NFR Requirements de U9, 2026-10-10 (segunda)).
- Siempre lleva `disclaimer = "mide y alerta, no certifica"`. Ningún texto de la API contiene «sin sesgo», «libre de discriminación» ni las frases de la lista de U10.

**BR-U9-19 — Congelamientos** (`list_freezes` para `cumplimiento` y `cro`; `get_context_package` solo para `cumplimiento`).
- Se leen de las entradas `freeze` y `frozen_resolution` del registro, en la proyección `monitoring_freezes` de U3: `freeze_id`, `model_version_id`, `frozen_at`, el paquete completo (BR-U9-15, 16) y, si existe, la resolución (`reactivar`, `descartar` o `investigar`) con su `recorded_at` (revisión del FD de U9, 2026-10-08, H1). `list_freezes` devuelve `FreezeSummary` con `resolution?` (cuarta revisión del FD de U9, 2026-10-10).
- `get_context_package` emite el log `freeze_context.viewed` con `principal_subject`, `principal_role` y `model_version_id` (NFR-U9-32; U0 §8.1; revisión del NFR Requirements de U9, 2026-10-10 (segunda)).
- Un `freeze_id` inexistente → 404.

## 8. Monitoreo detenido y métricas (Q8, Q9; US-308, NFR-RES-11)

**BR-U9-20 — Métricas publicadas.**
- Al terminar **cada** corrida, completa o fallida, el CronJob empuja al Pushgateway de U1 (flujo nuevo F106). Todas son **gauges**: un proceso que termina en cada corrida no puede acumular un contador (revisión del FD de U9, 2026-10-08, H3).
- Dos **grupos** de Pushgateway, con `PUT` (reemplaza todo el grupo):
  - `job="bias-monitoring", group="success"`: solo `vectra_bias_last_success_timestamp`. Se empuja **solo** si la corrida fue completa, así que una corrida fallida nunca lo borra ni dispara `absent()`;
  - `job="bias-monitoring", group="run"`: las métricas de la corrida. Se empuja siempre; el `PUT` reemplaza el grupo, así que las series de versiones que ya no se evalúan desaparecen en la corrida siguiente.
- Métricas del grupo `run`:
  - `vectra_bias_last_run_timestamp` y `vectra_bias_last_run_ok` (1 o 0), con `vectra_bias_last_run_failure{reason}` = 1 para el motivo de la falla (`lectura`, `libreria`, `invalidas`, `agregador_atrasado`, `token` (Keycloak no entrega token al cliente `bias-monitoring-job`, E7), `freeze`; `token` agregado en la revisión del NFR Requirements de U9, 2026-10-10 (segunda));
  - `vectra_bias_disparity{model_version_id, population, attribute, band, partial}` (`partial` ∈ {`true`, `false`}; solo `true` en `band = sin_bandas` con `population_difference_partial`) (`population` ∈ {`modelo`, `humana`}; `band` incluye `agregada` y `sin_bandas`) y `vectra_bias_aggregate_lower{model_version_id, population, attribute}`;
  - `vectra_bias_rule_met{model_version_id, population}` (1 si se cumple BR-U9-11), que alimenta `DisparidadDecisionHumana`;
  - `vectra_bias_cell_size{model_version_id, population, attribute, group, band}`;
  - `vectra_bias_invalid_entries` y `vectra_bias_total_entries`.
- **Grupo propio por versión para el `freeze` fallido** (revisión del Infrastructure Design de U9, 2026-10-10): `vectra_bias_freeze_failed{model_version_id}` va en el grupo `job="bias-monitoring", group="freeze-<model_version_id>"`, no en `run`. Se empuja con 1 cuando el `freeze` de esa versión falla tras los reintentos, y el grupo **se borra** (`DELETE`) cuando un `freeze` posterior de esa versión responde con éxito o con 409, o en una corrida **completa** en la que esa versión ya no cumple la regla de BR-U9-11 o ya no se evalúa (BR-U9-08) (revisión del plan de tareas de U9, 2026-10-10). Una corrida que falla antes del cálculo no lo toca, así que la alerta sigue activa mientras la versión siga sin congelar.
- Una celda insuficiente publica **solo** su tamaño, nunca su tasa; la serie `band = sin_bandas` sigue BR-U9-06 (sin la tasa de un grupo con celdas insuficientes; la diferencia, solo con celdas suficientes y con `partial="true"`; precisado el 2026-10-10 por U9 NFR Requirements).
- **Pushgateway caído** (tercera revisión del FD de U9, 2026-10-10): el CronJob registra el error en el log, termina con código distinto de cero y no reintenta; el congelamiento **no** depende de la publicación (ya se aplicó antes). Si el grupo `success` no se pudo empujar, `MonitoreoSesgoDetenido` avisa a W, y `PushgatewayDown` (U1) avisa antes.
- La historia queda en Prometheus (30 días, INF-U1-07). Las ventanas de 90 días del dashboard se recalculan (BR-U9-18).

**BR-U9-21 — `MonitoreoSesgoDetenido`** (sustituye a `bias_monitoring_age_s`, Q9).
- `time() − max(vectra_bias_last_success_timestamp) > W` (1 h) → SEV2; `> 2W` (2 h) → SEV1.
- `absent(vectra_bias_last_success_timestamp)` durante W → SEV2.
- El modelo **sigue sirviendo** (BR-U4-16, que cita esta regla). Governance no recibe la edad del cálculo: bias solo puede llamar a `freeze`.

**BR-U9-22 — Alertas de la unidad.**

| Alerta | Condición | Severidad |
|---|---|---|
| `MonitoreoSesgoDetenido` | BR-U9-21, con W y 2W tomados de `stale_after` | SEV2 / SEV1 |
| `BiasFreezeFailed` | `freeze` de una versión falló tras los reintentos (BR-U9-12), por versión | SEV1 |
| `DisparidadDecisionHumana` | Las decisiones humanas cumplen la regla de BR-U9-11 en dos corridas seguidas (BR-U9-14), por versión | SEV2 |
| `BiasInvalidEntries` | Al menos una entrada inválida en la ventana (BR-U9-09) | SEV2 |

Las expresiones exactas (con `max by (model_version_id)` donde aplica), los `for` y los `runbook_url` son los de NFR Design P-U9-06. `DisparidadDecisionHumana` y `BiasInvalidEntries` se alimentan del grupo `run`, que se empuja también en las corridas fallidas; `BiasFreezeFailed`, de los grupos por versión de BR-U9-20 (revisión del Infrastructure Design de U9, 2026-10-10).

`ModeloCongelado` es de U4 (BR-U4-15).

## 8b. Riesgos aceptados y pendientes para etapas siguientes (cuarta revisión del FD de U9, 2026-10-10)

| Tema | Riesgo o pendiente | Mitigación |
|---|---|---|
| `BiasInvalidEntries` | Una sola entrada inválida mantiene la alerta hasta 30 días, mientras siga en la ventana | El runbook pide investigar el `seq` (U3) y silenciar la alerta con su `seq` y fecha de vencimiento; la corrida sigue mientras las inválidas no superen el 1 % |
| Periodo ciego tras reactivar | La ventana empieza al día siguiente de la reactivación; hasta reunir `n_min` por celda, la versión es «muestra insuficiente» y no se congela | Es la decisión de cumplimiento al reactivar (con justificación); el dashboard muestra la muestra acumulada; el runbook de reactivación pide revisar el dashboard a diario hasta que haya muestra |
| Pushgateway sin persistencia | Tras un reinicio del Pushgateway, `vectra_bias_last_success_timestamp` falta hasta la siguiente corrida completa (≤ 15 min); `absent()` solo alerta a W (1 h), así que no hay falsa alarma, pero el valor queda ciego unos minutos | `PushgatewayDown` (U1) avisa del reinicio |
| **Infrastructure Design de U9** (pendiente) | El CronJob debe llevar `backoffLimit: 0` (una corrida fallida no se repite: la siguiente llega a los 15 min y nunca hay dos `freeze` en paralelo), `concurrencyPolicy: Forbid`, `vectra-high` y el sidecar nativo; un `ExternalSecret` con la llave privada (`private_key_jwt`) del cliente `bias-monitoring-job`, distinto del del servicio | Se fija en el Infrastructure Design de U9 |
| **Para U10** | Solo lo propio de U9: la consola muestra el `disclaimer` del dashboard, aplica el lint de frases prohibidas (FR-BIA-08) y obtiene la versión servible con `list_models(state=activo,congelado)` (BR-U9-18). Los pendientes de U8 para U10 viven en U8 business-rules §8 y no se repiten aquí | revisión del NFR Requirements de U9, 2026-10-10 |
| **Para U11** | Ninguno propio de U9. El pendiente de medir con los momentos de negocio y solo las recomendaciones entregadas vive en U7 NFR Design §9 y U8 business-rules §8 | revisión del NFR Requirements de U9, 2026-10-10 |
| **Para U12** | Solo lo propio de U9: la demostración de RT-2 necesita ≥ 30 casos por celda en `region` y `estrato` (unas 36 celdas) y mide la latencia de detección (p95 ≤ 30 min, ≈ 27 min; NFR-U9-01). La demostración de RT-5 y la medición de `case-db` viven en U8 | revisión del NFR Requirements de U9, 2026-10-10 |

## 9. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U3 business-rules (nueva BR-U3-17), domain-entities §1.2 y §3, business-logic-model §1 y §3 (PBT-U3-09), plan de tareas | Agregador incremental `registry-aggregator` con rol propio `registry_aggregator`: lee entradas por `seq` desde una marca de agua y mantiene las cinco tablas derivadas (`monitoring_daily`, `monitoring_entry_totals`, `monitoring_case_index`, `monitoring_invalid` y `monitoring_watermark`; U3 domain-entities §1.3); restar y sumar van en la misma transacción que avanza la marca de agua. Los triggers de solo-anexar siguen aplicando a `registry_entries`, no a las tablas derivadas. Proyecciones nuevas `monitoring_daily` y `monitoring_freezes` | Q4, Q8; CQ1, CQ2, CQ4 |
| U0 domain-entities §9.3 `ServingConfig` | Se quita `bias_monitoring_age_s` | Q9 |
| U0 §5.2 `freeze` | `context_package` = `FreezeContext` de U9 (domain-entities §3) más lo que agrega governance | Q7 |
| U4 BR-U4-13, domain-entities (`source_candidate_for`), business-logic-model, plan de tareas (Pasos 10 y 13) | `compare_source` va por **F25** (decía F27) con tablas de conteo por atributo de la versión activa y de una **versión candidata** que declara la fuente `en_evaluacion` (se registra, pero no puede aprobarse ni activarse hasta que la fuente se apruebe); el `model-validation-job` produce las tablas en modo `source_comparison` | Q10 |
| U4 BR-U4-15, BR-U4-16, domain-entities §5, PBT-U4-05, tabla de alertas, plan de tareas (Pasos 5 y 13) | governance agrega `data_sources` e `initial_disparity` al paquete; BR-U4-16 cita BR-U9-21; sin `bias_monitoring_age_s`; `MonitoreoSesgoDetenido` pasa a U9 | Q7, Q9 |
| `component-dependency.md` | F25 con conteos; F26 con `monitoring_daily` y `monitoring_freezes`, también desde el CronJob; F27 desde el CronJob; flujos nuevos **F106** (CronJob de bias → Pushgateway) y **F107** (`registry-aggregator` → `registry-db-rw`) | Q8, Q10; CQ1 |
| `component-methods.md` C11 | Firmas con conteos (`disparity_by_band(counts, attribute, n_min)`, `counts_from_records`), `compare_source(source_id, pre, post)`, `list_freezes` | Q4, Q10 |
| `services.md` S4 y S5 | Lectura de conteos agregados; regla de congelamiento; origen del «después» | Q3, Q4, Q10 |
| U7 NFR Design §9 | «Contar solo las recomendaciones entregadas»: resuelto para U9 por BR-U9-07 | Q5 |
| U8 business-rules §8 | «Medir con el momento de negocio»: resuelto para U9 por BR-U9-07 | Q4 |
| U5 | La variante proxy y el modelo base se miden con `counts_from_records` + `disparity_by_band` | Q4 |
| U3 BR-U3-16, 17, domain-entities §1.3 (esquema de las tablas derivadas) y §3, business-logic-model §2.5 y §3, plan de tareas | Marginales por atributo en lugar de la combinación de etiquetas; esquema, llaves, `CHECK (count >= 0)`, retención de 180 días y reconstrucción; definición del atraso; `SELECT … FOR UPDATE` de la marca de agua; `monitoring_freezes` con las `frozen_resolution`; actor `bias-monitoring-job` | revisión del FD de U9, 2026-10-08: H1, H2, H4, H5, H6, H12 |
| U2 domain-entities §2.2, plan de tareas (Pasos 2 y 14); U0 §7.2 (catálogo de scopes) | Cliente nuevo `bias-monitoring-job` con `governance:freeze` y `registry:read:monitoring`; `bias-monitoring-service` sin `governance:freeze` | revisión del FD de U9, 2026-10-08: H4 |
| U4 BR-U4-01, BR-U4-04, P-U4-06 (`guard_freeze`) | La identidad que congela es `bias-monitoring-job` | revisión del FD de U9, 2026-10-08: H4 |
| U0 §9 (nueva §9.4) | Contratos de U9: `MonitoringMarginalCount`, `MonitoringWindow`, `FreezeRecord`, `CountTable`, `AttributeResult`, `DisparityResult`, `FreezeContext`, `CompareSourceRequest`, `PrePostReport`, `DisparityView`, `FreezeSummary` (BR-U0-93: los contratos viven en U0) | revisión del FD de U9, 2026-10-08: H4 |
| U1 (Pushgateway: `NetworkPolicy` y P-U1-05) | El Pushgateway admite también a F106 (CronJob de bias, `vectra-app`), además de F87 | revisión del FD de U9, 2026-10-08: H4 |
| U4 BR-U4-05, BR-U4-13, domain-entities §2.1, §2.2 y §4, business-logic-model §2.5 y §3, P-U4-07, plan de tareas; `component-dependency.md` F32; `component-methods.md` C10 | Modo `source_comparison` cerrado: la versión activa se despliega también en KServe de staging (X08); `ValidationRun` con `mode` y `source_id`; el vencimiento en ese modo no toca la versión; F32 con el endpoint de conteos; `DataSource.pre_post_report` guardado; `initial_disparity` con el formato de la librería de U9 | revisión del FD de U9, 2026-10-08: H7, H11 |
| U3 (BR-U3-17, domain-entities §1.2, §1.3 y §3, NFR-U3-24, 35, NFR e infraestructura, plan); U4 (INF-U4-05, BR-U4-01, 05, 13, 15, P-U4-02, NFR-U4-12, plan); U0 §5.2 y §9.4; `component-methods` | Segunda revisión: agregación por rango en el servidor; iteración de lotes; índice por caso sin etiquetas; gauge del atraso; lecturas de `registry_verifier`; comparación de fuentes con su endpoint, barrido por modo y versión activa en staging; escalera de tamaño del evento `freeze`; `pre_post_report` en U0 | Segunda revisión del FD de U9, 2026-10-08 |
| U9 (esta unidad); U0 §5.2 y §9.4; U1 (P-U1-01, P-U1-09, tech-stack, alerta `PushgatewayDown`, sidecar en CronJobs); U2 (BR-U2 §8, `realm-lint`, PBT-U2-03); U3 y U4 (planes); `component-methods` C09 | Tercera revisión: `recorded_at` en UTC para la reactivación; 4 rangos por versión y varias solicitudes; recorte del `PrePostReport`; falla del Pushgateway; versión activa por omisión vía el BFF; `governance:freeze` solo para `bias-monitoring-job` | tercera revisión del FD de U9, 2026-10-10 |
| U1 (P-U1-05, plan Pasos 5 y 20); U3 (BR-U3-17, BLM, NFR-U3-24, 35, INF-U3-04, plan); U0 §5.2 y §9.4; U9 (§3.2, §3.4, BR-U9-17..19, §8b) | Cuarta revisión: política de sidecar como mutación (no bloquea a CloudNativePG); 181 días con la justificación corregida; decisión sin recomendación como fila no atribuible; filas de `humana` y tamaños; versión servible por omisión; `FreezeSummary.resolution`; `CompareSourceRequest` como lista; riesgos aceptados | cuarta revisión del FD de U9, 2026-10-10 |
| U3 (BR-U3-17, BLM, domain-entities, NFR-U3-24, deployment-architecture, plan); U0 §9.4 y plan Paso 3; U9 (BR-U9-09, §1.2, BLM); U1 (P-U1-05, P-U1-09, NFR-U1-25, 32, plan, diagramas); U4 y U2 (planes); `component-methods`; inventario | Quinta revisión: fila no atribuible proyectada; tipo `MonitoringQuery`; orden del agregador; memoria y lote; índice por `recorded_at`; `aggregator run`; escenarios del agregador; sidecar sin deriva en Argo CD; US-306 en U4; pruebas de `governance:freeze` en U2 | Quinta revisión del FD de U9, 2026-10-10 |
| U0 §9.4 (`unattributable_range`, `POST`); U3 (BR-U3-17: referenciada que no es `recommendation`, decisión sobre una inválida, reconstrucción con Job a demanda; NFR-U3 §7; plan Pasos 8, 12, 13, 17, 18); U9 BR-U9-09; U4 C09 `list_models` y plan Paso 10; U1 (sidecar en todo namespace mallado, Paso 16); inventario (§1, X04, F11, U10) | Sexta revisión | sexta revisión del FD de U9, 2026-10-10 |
| U1 (P-U1-05: etiqueta `vectra.io/mesh`; plan Pasos 5 y 6); U0 (P-U0-12 `read_only`, plan Pasos 3, 9 y 15); U3 (Jobs a demanda en INF-U3-03/04, identidad del reset, `Forbid`, validación de rangos, fila nueva del índice, buckets, tech-stack, historial; plan Pasos 8 y 12); U9 (§1.2, BLM, BR-U9-09: `unattributable_range` en la primera solicitud) | Séptima revisión | séptima revisión del FD de U9, 2026-10-10 |
| Inventario (F107 con el rebuild, F108 nuevo para el reset, §4 y §1), unit-of-work (U3 y `archive_job/`); U3 (BR-U3-17, NFR-U3-24, 42, §8, logical-components, deployment-architecture, INF-U3-03/06, plan Pasos 12 y 13); U0 BR-U0-71 (`read_only`); U1 (chart de namespaces, Paso 5, rangos F01–F108); U9 (BLM §2.3, ejemplos, §8b con pendientes de U10, U11 y U12) | Octava revisión | octava revisión del FD de U9, 2026-10-10 |
| U9 (BR-U9-06, 18, 20, §8b); U0 §9.4 (`AttributeResult.population_difference_partial`); `components.md` y `application-design.md` (criticidad de C11); U1 NFR-U1-12 y plan Paso 5 (exención de HPA) | Sin inferencia por resta en la diferencia sin bandas; criticidad por proceso; latencia de detección ≈ 27 min | precisado el 2026-10-10 por U9 NFR Requirements |
| U9 (BR-U9-06, 18..20, BLM); U0 (§8.1 catálogo de eventos, BR-U0-71); U3 (lanzamiento de los Jobs a demanda; ver la fila siguiente); U1 (Paso 16) | Marca `population_difference_partial` y etiqueta `partial`; motivo `token` (E7); eventos `disparity.viewed` y `freeze_context.viewed` | revisión del NFR Requirements de U9, 2026-10-10 (segunda) |
| U3 (BR-U3-17, INF-U3-03/04, deployment-architecture, plan); inventario; U1 (plan, NFR-U1-27, application-design) | Reconstrucción con Jobs normales en Git por `runId` y *advisory lock*; se retiran K15 y `restrict-manual-jobs` | aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10 |
| U9 (BR-U9-20, 22; P-U9-01, 06; INF-U9-03, 05); U3 (Application aparte de reconstrucción); U0 (NFR-U0-23, plan Pasos 3, 9 y 10) | Métrica de `freeze` fallido en un grupo por versión que se borra solo con un `freeze` exitoso; alertas generadas con W y 2W; rango del horario | revisión del Infrastructure Design de U9, 2026-10-10 |
