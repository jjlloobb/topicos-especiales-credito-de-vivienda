# Reglas de negocio — U11 `product-metrics`

Decisiones del plan (`product-metrics-functional-design-plan.md`: Q1–Q5 y Q7–Q11 = A, con
las notas del usuario en Q3, Q5, Q8 y Q10; Q6 = A con dos ajustes). Los IDs `BR-U11-xx` se
referencian en los planes de tareas. U11 no guarda datos: lee el registro (F28) y las métricas
de U7, y publica series en `/metrics`.

---

## 1. Qué decisión cuenta (Q7; pendientes de U7 y U8)

**BR-U11-01 — Solo recomendaciones entregadas.**
- Una métrica de decisión parte de cada `human_decision` y de la `recommendation` que referencia por `recommendation_entry_id`. U11 lee **solo** entradas `human_decision` de la proyección `metrics` (filtro `entry_type`): la recomendación viene resuelta dentro de cada una, y la consulta de la explicación sale de `explanation_viewed_before`, así que no lee entradas `recommendation` ni `explanation_view` (revisión del FD de U11, 2026-10-10). U3 resuelve esa referencia en el servidor y la incluye en la propia entrada de la proyección `metrics` (§7, cambio a U3; ajuste 2 de Q6). Así una decisión sobre una recomendación vieja, fuera de la ventana de lectura, no queda como no atribuible.
- Las recomendaciones que ninguna decisión referencia no cuentan en la North Star, en la de ruido ni en la sostenida.
- Si la referencia no existe o no es una `recommendation`, la decisión es **no atribuible**: no entra en ningún cociente y se cuenta aparte (`vectra_product_unattributable_decisions`).

**BR-U11-02 — Momentos de negocio.** Las métricas de decisión se asignan al día UTC de
`decided_at`; el tiempo de originación, al día de `evaluated_at` de la recomendación entregada.
`recorded_at` solo sirve para leer (un reintento puede retrasarlo hasta 24 h, BR-U3-05). La
consulta previa de la explicación es `explanation_viewed_before`, que case-service calcula con
las `explanation_view` confirmadas antes de la decisión (BR-U8-19); U11 no la recalcula.

## 2. Métricas (Q1–Q5)

**BR-U11-03 — North Star** (Q1; FR-MET-01, US-503).
- **Numerador**: decisiones con `explanation_viewed_before = true` **y** `used_factors ≠ ["ninguno"]`, cualquiera sea la decisión.
- **Denominador**: todas las decisiones atribuibles del periodo (BR-U11-01).
- **Desglose** del numerador: «sustentada» (`sigue`), «cambiada» (`se_aparta`) y «revisión resuelta» (`resuelve_revision`).
- Si el denominador es 0, la tasa no se publica para ese periodo (no es 0).

**BR-U11-04 — Recomendaciones sostenidas, como aproximación** (Q2; FR-MET-05).
- `vectra_product_recommendation_sustained_ratio` = decisiones `sigue` / decisiones atribuibles.
- El panel muestra siempre la nota: «aproximación: mide si la decisión siguió la recomendación; la revisión del comité no está en el sistema».
- Target **[INTERNO]**: > 70 % al mes 6.
- **Pendiente para Operations**: la medición real exige un registro de la revisión del comité, que hoy no existe.

**BR-U11-05 — Tiempo de originación** (Q3; FR-MET-04).
- Inicio = `received_at` de la recomendación entregada (el `created_at` del caso en case-service; §7, cambio a U0, U7 y U8). Fin = `evaluated_at` de esa recomendación. Mide el sistema hasta la recomendación explicada, como dice FR-MET-04 («hasta recomendación explicada»), y no el proceso completo hasta la decisión.
- **Caso estándar**: `channel ≠ manual`, `outcome ≠ revision_requerida` y `first_evaluation = true`. `attempt = 1` no basta: BR-U8-10 (salida de `modelo_congelado`) y BR-U8-11 (`retry` del CRO) reinician `attempts`, así que un caso que ya falló o estuvo congelado volvería a tener `attempt = 1`. `first_evaluation` lo calcula U8: es `true` solo si el caso nunca pasó por `en_sincronizacion`, `no_disponible` ni `modelo_congelado` y el intento es el 1 (§7, cambio a U0, U7 y U8; revisión del FD de U11, 2026-10-10).
- Se publican p50, p80 y p95 por día y el porcentaje de casos estándar bajo 1 h. Target **[INTERNO]**: < 1 h en el 80 %.
- La nota de Q3 queda registrada: si el PRD §10 se interpretara como el proceso completo, la métrica cambia a la opción B (hasta `decided_at`). Hoy FR-MET-04 dice «hasta recomendación explicada», así que se mantiene A.

**BR-U11-06 — Respuesta completa y fail-closed** (Q4; FR-MET-03). Recording rules de U11 sobre
las métricas de U7, sin leer el registro:
- `vectra:product_complete_response_ratio:1h` y `:1d` = `recommendation` / (`recommendation` + `fail_closed`) de `vectra_recommendations_total`, por intento. Toda `recommendation` lleva su explicación (BR-U0-01..08), así que la razón mide cuántas solicitudes llegan a una respuesta completa. Target: 100 %.
- `vectra:product_desync_failclosed:rate1h` = tasa de `vectra_scoring_failclosed_total` con las causas de la categoría `desincronia` del catálogo de U0 (hoy `version_mismatch` y `feature_dictionary_incomplete`; §7, cambio a U0). La regla **no** se escribe a mano: `product-metrics/tools/gen_rules.py` la genera desde `vectra_contracts.catalog.FailClosedCause` y CI corre `gen_rules.py --check`, que falla si la regla versionada difiere de la generada. Así, si U0 agrega o recategoriza una causa, el build de U11 falla en lugar de desfasarse en silencio (revisión del FD de U11, 2026-10-10).

**BR-U11-07 — Métrica de ruido** (Q5; FR-MET-02, US-504).
- **Tasa** = decisiones atribuibles con `explanation_viewed_before = true` / decisiones atribuibles, en una ventana móvil de 7 días por `decided_at`.
- **Días consecutivos bajo el piso** (nota de Q5): el servicio publica `vectra_product_noise_days_below_floor`, el número de días UTC completos seguidos, hasta ayer, en los que la ventana que termina ese día tuvo una tasa < **F** con al menos **N** decisiones. Un día con menos de N decisiones no suma ni reinicia la cuenta. La serie sale de los datos, no del tiempo que lleva corriendo el proceso, así que un reinicio no la cambia.
- **`RuidoExplicacion`** (SEV3) dispara cuando `vectra_product_noise_days_below_floor ≥ S`, sin `for` (la persistencia ya está en la serie).
- Valores iniciales **[INTERNO]**, a acordar con el piloto: F = 0,6, S = 3 días, N = 50.

## 3. Cortes, parámetros y calidad (Q8, Q9, Q11)

**BR-U11-08 — Periodos y cortes** (Q8).
- Periodos (revisión del FD de U11, 2026-10-10), todos en días UTC **completos** y sin el día en curso, para que un valor publicado no cambie a lo largo del día:
  - `day`: ayer completo;
  - `30d`: los 30 días completos que terminan ayer;
  - `month_to_date`: el mes calendario en curso, desde el día 1 hasta ayer (el día 1 de cada mes no se publica);
  - `month`: los **6** meses calendario cerrados anteriores, cada uno con la etiqueta `month="AAAA-MM"`; se **republican** cada día, porque un mes cerrado puede cambiar durante los 7 días siguientes (BR-U0-37) (NFR Requirements de U11, 2026-10-10, NFR-U11-10, 11).

  El dashboard muestra la hora de Colombia y dice en cada panel qué periodo usa.
- Cortes: `channel` y `outcome` de la recomendación entregada; `model_version_id` solo en la North Star (§7, cambio a U3: la proyección los trae).
- **Nunca por persona**: la proyección no tiene `user_id` y ninguna serie lleva un identificador de usuario. `actor_role` solo valida (BR-U11-10), no corta.
- **Cortes agregables** (revisión del FD de U11, 2026-10-10): una razón por corte no se puede sumar entre cortes. Por eso, para la North Star, la sostenida y la tasa de consulta, el servicio publica los **conteos** (`numerador` y `denominador`) con todos los cortes, que sí se suman, y la razón solo en dos niveles: el total sin cortes (etiquetas con `all`) y por cada corte por separado. El dashboard calcula cualquier combinación como `sum(numerador) / sum(denominador)`, nunca como promedio de razones.

**BR-U11-09 — Parámetros y targets** (Q5, Q9).
- Un archivo `values-product-metrics-policy.yaml` del chart contiene F, S y N, y los targets del PRD §10: 100 % de respuesta completa, < 1 h en el 80 %, > 70 % sostenidas al mes 6 y la North Star «sin target acordado». Todos marcados **[INTERNO]**.
- `CODEOWNERS` del monorepo y de GitOps lo asignan a los equipos de producto y de riesgo, con la protección de rama de U4 (`branch-protection-check`).
- Rangos validados por `conftest`: 0 < F < 1, 1 ≤ S ≤ 14, N ≥ 30, targets entre 0 y 1 o en horas > 0.
- El dashboard dibuja los targets como líneas de referencia; un target sin definir se muestra como «sin target acordado».

**BR-U11-10 — Calidad de los datos** (Q11).
- Una entrada se **excluye** si tiene un valor fuera del catálogo de U0 (por ejemplo, un `decision` desconocido), si `actor_role ≠ analista` (solo el analista decide, C03), si `decided_at > recorded_at + 5 min` o si le falta un campo obligatorio.
- **Por qué 5 min** (revisión del FD de U11, 2026-10-10): BR-U0-37 exige `decided_at ≤ occurred_at`, y BR-U3-05 acepta `occurred_at` solo si `|occurred_at − now| ≤ 5 min`, con `recorded_at ≈ now`. Así `decided_at` puede superar a `recorded_at` en hasta 5 min por desfase de relojes, pero no más. Una entrada fuera de ese margen indica un defecto del registro, no un desfase normal, y se excluye.
- Cada exclusión suma en `vectra_product_invalid_entries`, y su `seq` va solo al log (nunca a la métrica).
- Si las excluidas superan el 1 % de la ventana de 30 días, las métricas se publican igual con `vectra_product_metrics_degraded = 1`, y el panel lo muestra.

## 4. Cálculo (Q6 con ajustes)

**BR-U11-11 — Ciclo del servicio.**
- **Al arrancar**: la **misma pasada completa** que la recomputación diaria (P-U11-01): desde el día 1 del sexto mes cerrado − 1 día hasta la cabeza, entre ~184 y ~215 días según el día del mes. Guarda en memoria las entradas de los últimos 35 días, los contadores de los 6 meses y el último `seq` leído. Así, después de un despliegue o un reinicio, el dashboard tiene los 6 meses desde la primera instantánea, y no 24 h después (revisión del NFR Design de U11, 2026-10-10; antes decía 36 días).
- **Cada 5 min (ajuste 1)**: lectura **incremental**, solo las entradas con `seq` mayor que el último leído, y recálculo en memoria. Así no repite 288 lecturas completas al día sobre el pool `projections` de U3.
- **Una vez al día** (02:30 UTC más un desfase aleatorio de 0 a 10 min por réplica, NFR-U11-04): recomputación completa de 35 días (pendientes consolidados, 2026-10-10; decía 36), que reemplaza el estado en memoria y corrige cualquier deriva, y lectura de los 6 meses cerrados en la **misma pasada** desde el día 1 del sexto mes: cada página se pliega en los contadores por mes y por corte, y solo las entradas con `decided_at` de los últimos 35 días se guardan además en el estado (NFR-U11-12; P-U11-01; NFR Design de U11, 2026-10-10). Una decisión tardía de un mes cerrado que llega por la lectura incremental entra en los contadores del mes en la recomputación del día siguiente. Una prueba de propiedad exige que el estado incremental y el completo coincidan (PBT-U11-02).
- Las entradas con `decided_at` de más de 35 días se descartan de la memoria en cada ciclo.
- **Si una lectura falla**: el servicio conserva los últimos valores y no actualiza `vectra_product_metrics_last_success_timestamp`. `ProductMetricsStale` (SEV3) dispara si pasan 30 min sin una lectura exitosa.
- El cálculo es una función pura `compute(entries, params, now) -> BusinessMetrics`. La lectura y la publicación son la única E/S.

## 5. Dashboard y acceso (Q10)

**BR-U11-12 — Dashboard de producto.**
- `product.json` en la carpeta `Vectra / Producto` de la organización `Vectra`, aprovisionado y de solo lectura.
- Paneles: North Star con su desglose, tasa de consulta con el piso y los días bajo el piso, recomendaciones sostenidas con su nota de aproximación, tiempo de originación con el target, respuesta completa y fail-closed por desincronía, no atribuibles, excluidas y el aviso de datos degradados.
- Ningún texto pasa `forbidden_phrases.py` (BR-U0-94). La consola no lo embebe: se abre en Grafana.

**BR-U11-13 — Permisos de la carpeta** (nota de Q10).
- `View` para los equipos `cro`, `cumplimiento` e `ingeniero_riesgo`. `analista` y `operacion` no la ven.
- La carpeta **no hereda** los permisos del rol de organización: Grafana da por omisión acceso a todas las carpetas a los roles `Viewer` y `Editor`, así que un `ingeniero_riesgo` (`Viewer`) o un `operacion` (`Editor`) verían cualquier carpeta.
- **Mecanismo, compartido con `Vectra / Sesgo` de U9** (§7, cambio a U1): un Job idempotente `grafana-folder-permissions` (hook `PostSync` de la Application de observabilidad de U1) aplica por la API de Grafana el archivo versionado `platform/observability/grafana/folder-permissions.yaml`: quita los permisos de rol de esas carpetas y deja solo los de equipo. Un CronJob horario en modo comprobación publica `vectra_grafana_folder_permissions_drift` (alerta SEV3 si vale 1).
- Pruebas en kind con los usuarios de U2:
  - `ingeniero-1` → `Vectra / Producto` 200 y `Vectra / Sesgo` 403;
  - `operacion-1` → las dos 403;
  - `analista-1` → las dos 403;
  - `cro-1` y `cumplimiento-1` → las dos 200.

## 6. Alertas

**BR-U11-14 — Alertas de U11.**

| Alerta | Condición | Severidad |
|---|---|---|
| `RuidoExplicacion` | `max without (instance, pod) (vectra_product_noise_days_below_floor) ≥ S` (deduplicada: hay 2 réplicas) | SEV3 |
| `ProductMetricsStale` | Por réplica, en dos reglas: **edad**, 30 min sin lectura exitosa (`for: 0`); **ausencia**, una réplica con `up = 1` sin la serie durante 30 min (`up{job="product-metrics"} == 1 unless on (pod) …`, `for: 30m`). Ninguna dispara mientras esa réplica tiene una pasada completa en curso (revisión del NFR Requirements de U11, 2026-10-10; dos reglas y exclusión de la pasada, pendientes posteriores al cierre, 2026-10-10) | SEV3 |
| `ProductMetricsDegraded` | `max without (instance, pod) (vectra_product_metrics_degraded) == 1` durante 1 h | SEV3 |
| `ProductMetricsFullRecomputeMissing` | Por réplica, en dos reglas: **edad**, 26 h sin recomputación completa exitosa, y la del arranque cuenta (`for: 0`); **ausencia**, una réplica con `up = 1` sin la serie durante 26 h (`for: 26h`). Ninguna dispara durante una pasada completa en curso (revisión del NFR Requirements de U11, 2026-10-10; pendientes posteriores al cierre, 2026-10-10) | SEV3 |

(Deduplicación, ausencia por réplica y la cuarta alerta agregadas en el NFR Requirements de U11, 2026-10-10, NFR-U11-06, 08, 42; la ausencia no usa `absent()`, que no ve una sola réplica. `GrafanaFolderPermissionsDrift` es de U1, no de U11; pendientes posteriores al cierre, 2026-10-10.)

Cada una con `runbook_url` (P-U1-10). El runbook de `RuidoExplicacion` dice que es una señal
de **producto** (revisar cómo se usa la explicación con el piloto), no una falla técnica.

## 7. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 §5.2 (`recommendation`) y §9.1 (`ScoringRequest`) | `ScoringRequest` agrega `received_at` (el `created_at` del caso) y `first_evaluation`; el payload de `recommendation` agrega `received_at`, `channel` (de `policy_inputs`), `attempt` y `first_evaluation` | Q3, Q8; revisión del FD de U11, 2026-10-10 |
| U0 BR-U0-37, `check_business_time` y plan (Paso 3); U3 plan (Paso 7) | `received_at` **no** es un momento de negocio de la entrada y queda fuera de la cota de 7 días: un caso congelado o no disponible más de 7 días tiene `received_at` viejo y su `recommendation` no debe rechazarse | revisión del FD de U11, 2026-10-10 |
| U0 `FailClosedCause` (catálogo) | Cada causa lleva `category` (`desincronia`, `congelamiento`, `dependencia`, `calidad`) | revisión del FD de U11, 2026-10-10 |
| U8 (domain-entities, BR-U8-06) | `first_evaluation = true` solo si el caso nunca pasó por `en_sincronizacion`, `no_disponible` ni `modelo_congelado` y el intento es el 1 | revisión del FD de U11, 2026-10-10 |
| U7 (construcción de la entrada `recommendation`) | Copia `received_at`, `channel`, `attempt` y `first_evaluation` de la solicitud al payload | Q3; revisión del FD de U11 |
| U8 (envío a scoring) | Envía `received_at = cases.created_at` y `first_evaluation` en cada intento | Q3; revisión del FD de U11 |
| U3 domain-entities §3 (proyección `metrics`) y plan (Paso 8) | `recommendation` con `model_version_id`, `channel`, `received_at`, `attempt` y `first_evaluation`; cada `human_decision` trae la recomendación referenciada resuelta en el servidor (`recommendation: {seq, outcome, model_version_id, evaluated_at, received_at, channel, attempt, first_evaluation} \| null`, `null` si no existe o no es `recommendation`); filtro por `recorded_at` y por `seq >` | Q6 (ajuste 2), Q8 |
| U1 (observabilidad, plan Paso 10) y `component-dependency.md` (F110 nuevo) | Job `grafana-folder-permissions` (`PostSync`) y CronJob de comprobación con `vectra_grafana_folder_permissions_drift`; `folder-permissions.yaml` con `Vectra / Sesgo` (U9) y `Vectra / Producto` (U11); flujo F110 hacia la API de Grafana; rango de flujos F01–F110 | Q10 |
| U9 INF-U9-05 | Los permisos de `Vectra / Sesgo` se aplican con el mismo Job de U1 y se prueban con `ingeniero-1` y `operacion-1` (403) | Q10 |
| U8 business-rules §8 y U7 NFR Design §9 | Pendientes para U11 resueltos (momentos de negocio; solo recomendaciones entregadas) | Q7 |
