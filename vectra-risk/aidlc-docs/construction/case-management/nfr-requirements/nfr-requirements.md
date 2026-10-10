# Requisitos no funcionales — U8 `case-management`

Decisiones del plan (`case-management-nfr-requirements-plan.md`, Q1–Q9 = A, con los ajustes
del usuario). Las verificaciones «en kind» las ejecuta el operador después de un PR aprobado
(AUTONOMIA-01); las demás corren en CI.

Los IDs `NFR-U8-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Rendimiento (Q1, Q2; NFR-PER-01)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U8-01 | Latencia de la API de case-service, a 10 solicitudes/s de ingesta con la consola en paralelo: ingesta y alta manual (validación + caso + trabajo en una transacción) **p95 ≤ 200 ms**; `GET /v1/cases` (página ≤ 100) **p95 ≤ 300 ms**; `GET /v1/cases/{id}` **p95 ≤ 300 ms y p99 ≤ 800 ms** (incluye el core, con timeout de 500 ms, en casos `decidido`); decisión (con el append síncrono al registro) **p95 ≤ 300 ms**; consulta de la explicación **p95 ≤ 200 ms**. Ninguna operación síncrona espera a scoring | Prueba de carga k6 en kind (U12, operador), con el reporte adjunto al PR |
| NFR-U8-02 | **Tiempo hasta `listo`**: desde la ingesta hasta `listo`, cuando scoring responde con una `Recommendation` al primer intento, **p95 ≤ 5 s** a 10 solicitudes/s. Fija el objetivo de NFR-PER-01 («recomendación disponible al abrir el caso»). Se mide con el histograma `vectra_case_time_to_ready_seconds` (de `created_at` a `listo`), que excluye los casos que pasaron por `en_sincronizacion`, porque esos dependen del backoff | Misma prueba; consulta del histograma en Prometheus |
| NFR-U8-03 | **Fallos al primer intento visibles**: como el histograma de NFR-U8-02 excluye los casos que no llegan a `listo` al primer intento, la métrica `vectra_case_first_attempt_failure_ratio` (casos cuyo intento 1 no terminó en `Recommendation` / casos con intento 1, en ventana de 5 min) los hace visibles. Su umbral de alerta se fija en NFR Design | Prueba de integración con un doble de scoring que falla el 30 % de los primeros intentos → la razón es 0,3 ± 0,05 |
| NFR-U8-04 | **Sondeo de la cola**: cada réplica de `case-worker` consulta `evaluation_jobs` con un intervalo **≤ 500 ms** cuando no tiene trabajos, para que la espera en la cola no consuma el presupuesto de NFR-U8-02 | Prueba de integración: un trabajo nuevo se toma en ≤ 600 ms con el worker ocioso |

## 2. Escalabilidad (Q3, Q4, Q8)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U8-10 | **Dos Deployments con la misma imagen**: `case-service` (API, barridos de BR-U8-10/14 y reconciliador de evidencia) y `case-worker` (evaluación). Una carga de evaluaciones no compite con la consola | `helm template`: dos Deployments, misma imagen por digest, distinto comando |
| NFR-U8-11 | **Worker asíncrono, 16 trabajos en vuelo por réplica**. Toma el trabajo en una **transacción corta** que fija `locked_until = ahora + 30 s` y la confirma; **no retiene conexión ni transacción** mientras espera a governance o a scoring (hasta 7 s). La toma también incrementa `evaluation_jobs.attempt` y lo copia a `cases.attempts` (BR-U8-07; precisado el 2026-10-08, revisión del plan de tareas de U8). El resultado se aplica en otra transacción corta (BR-U8-08, `UPDATE … WHERE state IN (…) AND attempts = :attempt`, con el número de esa toma). Con 2 réplicas son 32 en vuelo, unas 80 evaluaciones/s a 400 ms cada una: **4× el pico de prueba** (NFR-U1-11) | Prueba de integración: 16 trabajos en vuelo con un doble de scoring que tarda 7 s y un pool de 5 conexiones → ninguna espera de conexión, y `pg_stat_activity` no muestra transacciones abiertas durante la llamada |
| NFR-U8-12 | Los dos Deployments: **≥ 2 réplicas** repartidas por zona, PDB y **HPA de 2 a 6 por CPU al 70 %** (NFR-U1-12). El HPA por CPU **no reacciona** a una cola atrasada, porque el worker espera E/S: la protección real es el margen de NFR-U8-11 y la alerta sobre `vectra_case_jobs_overdue` (trabajos con `run_at` vencido hace más de 30 s y sin tomar), con umbral en NFR Design | `helm template` + `conftest`; prueba de la métrica con trabajos vencidos sembrados |
| NFR-U8-13 | Barridos y reconciliador en **todas** las réplicas de `case-service`; `FOR UPDATE SKIP LOCKED` evita el trabajo duplicado | Prueba de integración con 2 réplicas: cada evidencia pendiente se reintenta una sola vez por ciclo |
| NFR-U8-14 | **Conexiones a `case-db`**: pool ≤ 5 por réplica (P-U1-08). Con los máximos del HPA, 6 réplicas de `case-service` y 6 de `case-worker` son **12 clientes × 5 = 60 conexiones**, más el 20 % de margen, el CronJob `case-retention` (1 conexión), el Job de migración (1) y las del operador y los backups. `max_connections` de `case-db` (U1 Infrastructure Design) debe cubrir esa suma | Revisión del valor en los values de `case-db`; prueba de carga (NFR-U1-11) sin `too many connections` |
| NFR-U8-15 | **Carga sobre governance**: cada réplica de `case-worker` lee `serving-config` con caché ≤ 5 s y el `feature_spec` con caché sin expiración por versión (LRU de 4). Con los máximos, governance recibe **12 clientes cada 5 s** (6 de scoring y 6 de `case-worker`, ≈ 2,4 req/s, casi todas 304). NFR-U4-10 queda ampliado a esa carga con el mismo p95 ≤ 20 ms; NFR-U4-11 no cambia (case-service no hace transiciones) | Script k6 de U4 (plan de U4, Paso 19) con 12 clientes y una lectura de `feature_spec` por cliente al cambiar de versión |

## 3. Disponibilidad y modos de fallo (Q5)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U8-20 | Criticidad **High** para `case-service` y `case-worker`, como `case-db` (NFR-U1-01). La API de casos queda **fuera** del SLO de 99,5 % de la ruta de recomendación (NFR-RES-02), pero tiene su propia alarma de indisponibilidad (nombre y umbral en NFR Design). Si la API no responde, el canal reintenta con la misma `Idempotency-Key` (BR-U8-02) | Etiqueta `vectra.io/criticality: high` (política de U1); `promtool test rules` de la alarma |
| NFR-U8-21 | Readiness solo con `case-db` (P-U1-04); governance, scoring, el registro y el core **no** entran en la readiness | Prueba de arranque: con governance caído, los pods quedan `Ready` |
| NFR-U8-22 | **`case-db` sin escritura** (NFR-U1-03 o caída): la ingesta, el alta manual, la decisión y la consulta de la explicación responden **503** y no se crea ni se cambia nada; las lecturas siguen si queda una instancia. El canal reintenta con la misma llave | Prueba de integración con la base en solo lectura (`default_transaction_read_only`) |
| NFR-U8-23 | **Registro caído**: la decisión responde 503 y queda `pendiente_registro` (BR-U8-18). Scoring también responde `FailClosed(registry_unavailable)`, porque escribe la recomendación de forma síncrona (BR-U0-08): los casos pasan a `en_sincronizacion` y escalan a los 15,5 min. **Las evaluaciones no siguen** | Prueba de integración con un doble del registro caído y otro de scoring que responde `registry_unavailable` |
| NFR-U8-24 | **governance o scoring caídos**: los casos pasan a `en_sincronizacion` con `serving_config_unavailable` o `scoring_unreachable` y escalan a los 15,5 min (BR-U8-07, 09) | PBT-U8-01 y la prueba de ejemplo de US-112 |
| NFR-U8-25 | **Core caído**: `get_case` responde con `credit_status = no_disponible` (BR-U8-21) y nunca falla por el core. **Core deshabilitado** (`core.enabled = false`, producción en el MVP): `no_integrado` (precisado el 2026-10-10 por U10 FD, Q3) sin llamar y sin contar para el breaker (precisado el 2026-10-08 por U8 INF-U8-02) | Prueba de integración con el mock detenido; prueba con `core.enabled = false`: `no_integrado`, cero llamadas al doble y breaker sin fallos registrados |
| NFR-U8-26 | `core-banking-mock` (solo kind y staging; precisado el 2026-10-08 por INF-U8-02): 2 réplicas y PDB, como cualquier Deployment de Vectra (NFR-U1-04), criticidad **Low**, sin base de datos (datos sembrados desde un archivo de fixtures versionado) | `helm template` + `kyverno test` (sin excepción a `require-spread-and-pdb`) |

## 4. Resiliencia (Q6; RESILIENCY-10, NFR-RES-11)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U8-30 | Timeouts por llamada, todos con `vectra_common.deps.call`: `case-worker` → `serving-config` **500 ms**; → `feature_spec` **1 s**; → scoring **7 s** (BR-U8-07); case-service → registro **2,5 s** (U3); → core **500 ms** (BR-U8-21) | `contracts`: `call` sin timeout no compila; prueba de integración por dependencia con un doble lento |
| NFR-U8-31 | **Circuit breaker por dependencia** (governance, scoring, registro, core), con los umbrales de U7: se abre con ≥ 50 % de fallos en las últimas 20 llamadas dentro de 30 s y pasa a semiabierto a los 10 s. Abierto → sin llamar: governance → `serving_config_unavailable`; scoring → `scoring_unreachable` (el intento **cuenta**); registro → 503 en la decisión; core → `no_disponible`. Con `core.enabled = false` no hay llamada y el breaker del core no registra nada (precisado el 2026-10-08 por U8 INF-U8-02) | PBT-U0-14 (propiedad stateful del breaker); prueba de integración: con scoring caído, tras 20 llamadas el circuito se abre y los intentos terminan en < 50 ms |
| NFR-U8-32 | **Qué cuenta como fallo del breaker**: solo timeouts, errores de conexión y 5xx. Un 4xx (incluidos los de `scoring_rejected`) es una respuesta de una dependencia sana y **no** cuenta, para que una solicitud defectuosa no abra el circuito de todos los casos. El criterio vive en `vectra_common.deps` (NFR-U0-23, precisado por esta unidad) | PBT-U0-14 con el comando `call_4xx`; prueba de integración: 20 respuestas 422 de scoring → el circuito sigue cerrado |
| NFR-U8-33 | Sin reintentos fuera de los ya definidos: el backoff del caso (BR-U8-07), el reconciliador de evidencia (BR-U8-18) y el reintento por 401 de scoring dentro del mismo intento (BR-U8-08) | Revisión de código + prueba: un 503 de governance produce una sola llamada por intento |
| NFR-U8-34 | El circuit breaker es el de `vectra_common.deps` (U0, NFR-U0-23), no uno propio de U8 | Contrato de import-linter: U8 no importa librerías de circuit breaking |

## 5. Seguridad (Q7)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U8-40 | **Identificadores en `case-db`**: cifrado del volumen (StorageClass cifrada de U1) y de los backups (F70); TLS en toda conexión. **Sin cifrado por columna**: el crypto-shredding se descartó en U0 Q7, y la eliminación por retención es un `DELETE` de una fila (BR-U8-20) | SECURITY-01, NFR-SEC-01 | Políticas de U1 sobre la StorageClass y el `Cluster`; `sslmode=verify-full` en la cadena de conexión |
| NFR-U8-41 | **Mínimo privilegio en la base**: `case_app` lee y escribe `case_identifiers` pero no puede borrarla y no borra en ninguna tabla; `case_worker` (precisado el 2026-10-08 por U8 INF-U8-01) consume la cola y actualiza solo las columnas de evaluación de `cases`; `case_retention` es el único que borra identificadores y el único que escribe `state = vencido` (trigger `guard_vencido`); `case_migrator` solo DDL. Además (precisado el 2026-10-08 por U8 INF-U8-01): `case_app` actualiza en `cases` solo `(state, attempts, model_frozen_after_recommendation, updated_at)`; `case_worker` solo inserta entradas `fail_closed` en `evidence_outbox` (política RLS `worker_fail_closed_only`); y toda transición de `state` pasa por el trigger `guard_transition`, que la comprueba por par de estados y rol contra `case_transitions`. Solo los procesos de U8 tienen credenciales de `case-db`, cada uno con su rol: `case-service` (`case_app`), `case-worker` (`case_worker`), `case-retention` (`case_retention`) y la migración (`case_migrator`) (precisado el 2026-10-08 por U8 INF-U8-01) | SECURITY-06, AUTONOMIA-03 | Prueba de migraciones con Testcontainers: cada rol intenta lo que no le corresponde → error (incluidos un `entry_type` distinto de `fail_closed` desde `case_worker` y una transición fuera de `case_transitions`) |
| NFR-U8-42 | Ningún log, métrica ni traza lleva identificadores, `free_text` ni `test_scenario_id` (BR-U0-50..53). Las métricas usan etiquetas de cardinalidad acotada (`result`, `cause`, `state`), nunca `case_id`. El log `case.viewed` solo lleva `principal_subject`, `principal_role` y `case_id`, campos de la allowlist de U0 §8 (precisado el 2026-10-08 por U8 NFR Design) | SECURITY-03, AUTONOMIA-05 | PBT-U0-07 (allowlist) + prueba de las etiquetas de las métricas |
| NFR-U8-43 | Sin egress (X02); hacia el core, solo `GET /v1/credits/{id}` (X01 en dos capas: NetworkPolicy + Linkerd L7), en kind y staging; en producción no hay flujo hacia el core (`core.enabled = false`, INF-U8-02) | AUTONOMIA-03, 05 | Suite de conectividad de U1; prueba estática: ningún método de escritura en el cliente del core |
| NFR-U8-44 | `allow_test_scenarios = false` en los values de producción, verificado por política; `X-Test-Scenario` en producción → 400 (BR-U8-03) | SECURITY-11 | `conftest` sobre los values de producción + prueba de ejemplo |
| NFR-U8-45 | **Eventos de seguridad con alerta** (umbrales y severidades en NFR Design): (a) cada 401/403 de case-service emite `authz.denied` y `vectra_authz_denied_total{code, route_template}` (BR-U0-73), que alimenta `AuthDeniedBurst` (U2, SEV2); (b) solo en kind y staging, donde existe el mock (precisado el 2026-10-08 por INF-U8-02): cada `WriteAttempt` del mock incrementa `vectra_core_write_attempts_total` y dispara `CoreWriteAttempt`; como X01 bloquea el `POST` en Linkerd, la alerta también se dispara con la denegación del proxy en la ruta de captura del mock (precisado el 2026-10-08 por U8 INF-U8-03) (cualquier intento es un caso de abuso, RT-5; en la demostración la alerta es la evidencia esperada); (c) el gauge `vectra_cases_failclosed_persistent` alimenta `FailClosedPersistente` (U1, NFR-U1-32); (d) `case.retry_requested` y `case.viewed` (con `principal_subject` y `principal_role`; precisado el 2026-10-08) quedan en el almacenamiento de logs tamper-evident con retención ≥ 90 días (NFR-SEC-14), y `retry` incrementa `vectra_case_retries_total` | SECURITY-14 | `promtool test rules` de cada alerta; prueba de que cada evento emite su log y su métrica sin datos del solicitante |

## 5b. Retención de identificadores (BR-U8-20; NFR-U3-03)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U8-46 | **`case-retention`**: (a) CronJob **diario** fuera del horario operativo, con `concurrencyPolicy: Forbid`; (b) procesa en **lotes** de a lo sumo 500 casos por transacción, tomados con `FOR UPDATE SKIP LOCKED`, para no bloquear la API ni el worker (una fila tomada por la API se procesa en la corrida siguiente); (c) **idempotente**: correr dos veces da el mismo resultado (PBT-U8-08); (d) case-service expone, sin un flujo nuevo, `vectra_case_retention_overdue_identifiers` (casos con la retención vencida que aún conservan identificadores o `free_text`) y `vectra_case_retention_last_success_timestamp` (de la última corrida exitosa o, si todavía no hay ninguna, `retention_settings.created_at`, para que una instalación que nunca corre la retención también dispare la alerta; precisado el 2026-10-08 por U8 NFR Design, P-U8-07. La corrida la registra el job en la tabla `retention_runs`, domain-entities §1.4; `case_retention` solo inserta y `case_app` solo lee); (e) alertas: `CaseRetentionMissing` si la última corrida exitosa tiene más de **2 días**, y `CaseRetentionOverdue` solo si **dos corridas exitosas consecutivas** terminan con `overdue_remaining > 0`: una fila tomada por la API en una corrida se procesa en la siguiente (b), así que una sola corrida con pendientes no es una falla (severidades en NFR Design); (f) los plazos son **parámetros** (`retention.decided_years = 10`, `retention.undecided_years = 2`), no constantes: la migración los escribe desde los values en la tabla `retention_settings`, y el job y el trigger `guard_vencido` los leen de ella (precisado el 2026-10-08 por U8 NFR Design, Q2; P-U8-05) | AUTONOMIA-05, NFR-U3-03, RESILIENCY-05 | Prueba de integración con Testcontainers: 2 000 casos vencidos y la API escribiendo en paralelo → ninguna espera de bloqueo > 1 s y 0 identificadores vencidos tras dos corridas; `promtool test rules` de las dos alertas |
| NFR-U8-47 | **Plazos por confirmar con cumplimiento** antes de producción (Ley 1581 y Superintendencia Financiera): 10 años desde la decisión **[VERIFICAR]**, 2 años desde la creación para los casos nunca decididos **[VERIFICAR]** y el riesgo aceptado de que los backups mensuales (12 meses, NFR-U1-06) conserven identificadores ya vencidos hasta que expiran **[VERIFICAR]**. La confirmación queda en `case-management/docs/retention.md`, firmada por cumplimiento, y es condición del despliegue a producción | NFR-U3-01, NFR-U1-06 | Lista de verificación previa a producción (Operations): `retention.md` con la confirmación de cumplimiento |

## 6. Calidad de pruebas (Q9)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U8-50 | Cobertura de ramas **≥ 95 %** en case-service y **100 %** en `case_fsm`, `backoff`, `decision`, `views`, `intake`, `evidence`, `evaluation`, `sweeps` y `retention` (este último borra identificadores) | `pytest --cov --cov-branch` + umbral por módulo |
| NFR-U8-51 | Mutation testing con `mutmut` en `case_fsm`, `validate_decision`, `views` y `backoff`: 0 sobrevivientes sin justificar | `mutmut run` en el job nocturno y en los PR que tocan esos módulos |
| NFR-U8-52 | PBT-U8-01..08 con el perfil `ci` (500 ejemplos, semilla impresa) | `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property` |
| NFR-U8-53 | El doble del registro de PBT-U8-07 implementa BR-U3-05/06 y BR-U0-37 y se valida con las pruebas de ejemplo de append de U3 (plan de U3, Paso 7) | Ejecución de esas pruebas contra el doble en CI |

## 7. Pendientes para NFR Design (del FD y de este documento)

**Resueltos el 2026-10-08 por U8 NFR Design**: P-U8-04 (evidencia), P-U8-05 (`guard_vencido`), P-U8-06 y 07 (severidades de seguridad y retención), P-U8-08 (umbrales operativos) y P-U8-09 (escenarios de resiliencia).

- Alerta de evidencia pendiente (umbral antes de las 24 h) y alerta al abandonar; trigger `guard_vencido`.
- Alerta `ScoringRequestRejected` y métrica `vectra_case_attempts_total{result}`.
- Umbrales de `vectra_case_first_attempt_failure_ratio` (NFR-U8-03), `vectra_case_jobs_overdue` (NFR-U8-12) y de la alarma de indisponibilidad de la API (NFR-U8-20).
- Escenarios de resiliencia de U8 (P-U0-08, decisión del proyecto C).
- Severidades de `CoreWriteAttempt` (NFR-U8-45), `CaseRetentionMissing` y `CaseRetentionOverdue` (NFR-U8-46; umbral de dos corridas consecutivas ya fijado). La tabla `retention_runs` ya está en domain-entities §1.4 y los permisos en `component-dependency.md`.

## 8. Cumplimiento de extensiones (NFR Requirements U8)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | NFR-U8-20 (criticidad High; RPO y RTO de `case-db` heredados de U1, NFR-U1-02..07) |
| RESILIENCY-05 / 07 | Cumple | NFR-U8-03, 12, 20, 45, 46 (métricas y alarmas; umbrales en NFR Design) |
| RESILIENCY-06 | Cumple | NFR-U8-21 |
| RESILIENCY-08 / 09 | Cumple | NFR-U8-10..14 |
| RESILIENCY-10 | Cumple | NFR-U8-22..25, 30..34 |
| RESILIENCY-11 / 12 / 13 | Cumple | Heredado de U1 (backups de `case-db`, F70; `restore-drill` con `case-retention`, P-U1-05) |
| RESILIENCY-14 | Cumple | Decisión del proyecto C; escenarios de U8 en NFR Design (§7) |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |
| AUTONOMIA-03 | Cumple | NFR-U8-41, 43 |
| AUTONOMIA-05 | Cumple | NFR-U8-42, 43, 46 (los identificadores no sobreviven a su retención) |
| AUTONOMIA-06 | Cumple | NFR-U8-23, 24, 31 (ningún fallo produce un caso `listo` sin recomendación registrada) |
| SECURITY-01 | Cumple | NFR-U8-40 |
| SECURITY-03 | Cumple | NFR-U8-42 |
| SECURITY-06 | Cumple | NFR-U8-41 |
| SECURITY-11 | Cumple | NFR-U8-44 |
| SECURITY-14 | Cumple | NFR-U8-45 (`AuthDeniedBurst`, `CoreWriteAttempt`, `FailClosedPersistente`, logs de `retry` y `case.viewed` retenidos ≥ 90 días) y NFR-U8-46 (alertas de retención) |
| SECURITY-15 | Cumple | NFR-U8-22..25, 31 (fail-closed acotado en tiempo; 503 sin efecto) |
| PBT-06 | Cumple | PBT-U8-01 y 07 (stateful); PBT-U0-14 para el breaker que usa NFR-U8-31 |
| PBT-08 / 09 | Cumple | NFR-U8-52 |

## 9. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Motivo |
|---|---|---|
| U4 NFR-U4-10 y plan de tareas, Paso 19 (script k6) | 12 clientes de `serving-config` cada 5 s (6 de scoring y 6 de `case-worker`) y una lectura de `feature_spec` por cliente al cambiar de versión | Q4; pendiente del FD de U8 |
| U0 NFR-U0-23, NFR Design P-U0-07, business-logic-model PBT-U0-14, plan de tareas Paso 10 (`deps.py`) | Solo timeouts, errores de conexión y 5xx cuentan como fallo del circuit breaker; un 4xx no cuenta. Comando `call_4xx` en la propiedad stateful | Q6 (ajuste) |
| U1 Infrastructure Design (`max_connections`) | `case-db` tiene dos Deployments clientes (12 réplicas × 5 conexiones con los máximos), más `case-retention` y la migración | Q8 (ajuste) |
| `requirements.md` NFR-PER-01 | El tiempo hasta `listo` queda fijado en NFR-U8-02 | Q2 |
| U8 domain-entities §1.4; `component-dependency.md` (roles `case_retention` y `case_app`, X01) | Tabla `retention_runs` (solo `INSERT` de `case_retention`, solo `SELECT` de `case_app`); X01 rige el puerto de datos del mock y el de métricas (8081) admite a Prometheus (F60) | NFR-U8-45, 46 (revisión) |
