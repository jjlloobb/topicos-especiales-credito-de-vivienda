# U8 `case-management`: resumen de los servicios (Bloques D, E y F)

El Paso 18 (U08-T04) completa este archivo con los Bloques E y F: la sección «Bloques E y F (U08-T04)» está al final. Primero va la sección del **Bloque D** (`case-service`: Pasos 9 a 13, U08-T03). El resumen de la base está en `database.md`.

## Módulos

| Módulo | Paso | Qué hace |
|---|---|---|
| `intake` | 9 | `submit` (ingesta y alta manual), idempotencia, `X-Test-Scenario`, `body_sha256`. |
| `retention` | 9 (P-5) | Solo `purge_intake_keys` (ver «Purga adelantada»). La CLI es del Paso 16. |
| `evidence` | 10 | `Evidence` (decisión, consulta), `Reconciler`, `RegistryClient`. |
| `sweeps` | 11 | `Sweeper`: `modelo_congelado` y la marca `model_frozen_after_recommendation`. |
| `db_gauges` | 11 | `DbGauges`: `vectra_case_jobs_overdue`, `vectra_cases_failclosed_persistent`, evidencia pendiente. |
| `governance_client` | 11, 14 | `ServingConfigClient`: `serving-config` (Paso 11) y `feature_spec` (Paso 14). |
| `credit` | 12 | `CreditReader` (solo `GET`). |
| `api`, `app`, `db`, `metrics` | 13 | Las 9 rutas, arranque (`python -m vectra_case.app`), pool de `case-db`, métricas. |

## Decisiones tomadas (sin respuesta del usuario: rige la recomendación (a))

- **P-1 (a). Cliente de `serving-config` en `case-service`.** `governance_client.py` trae solo la lectura de `serving-config`: `deps.call` con 500 ms, el breaker de NFR-U8-31, token `service_token.provider_from_env`, caché ≤ 5 s con `If-None-Match` (304 renueva la caché). U08-T04 le añade `feature_spec` y el cliente de scoring, en el mismo módulo. Una respuesta con la forma vieja (sin `cutoff`, `low_confidence_threshold` ni `channel_rules`) falla la validación estricta de `ServingConfig` (`ServingConfigInvalid`) y el barrido se salta el ciclo: falla cerrado. Esto cierra para U8, en el código, la candidata «orden de despliegue» de U04-T09; el despliegue conjunto es de U08-T05 y U12.
- **P-2 (a). Fila de `evaluation_jobs`.** El escalamiento a `no_disponible` y a `modelo_congelado` **borra** el trabajo (lo hace el worker, U08-T04); `case_app` no tiene `UPDATE` ni `DELETE` sobre `evaluation_jobs`. `retry` y el barrido hacen un `INSERT` simple con `attempt = 0`. Si choca con una fila viva (índice único sobre `case_id`), esa operación se revierte: `retry` responde `409 conflict_state` sin cambiar el estado, y el barrido deja ese caso en `modelo_congelado` y sigue con los demás (un `SAVEPOINT` por caso). Hay una prueba de cada una. Falta precisarlo en `domain-entities` §2.1 (lo hace U08-T04 con el worker).
- **P-3 (a). Rechazos de `validate_decision`.** La respuesta lleva solo el `code` (422 `validation_error` o 409 `conflict_state`), sin `reason`. Las razones internas (`used_factors_not_in_shap_vector`, `decision_incoherent_with_outcome`) no salen a la red ni a los logs de negocio. Es el valor distinto de `decision_already_recorded`, que sí es un `ProblemReason` de U0 y sí sale en el 409 del conflicto tras un abandono. No cambia U0.
- **P-4 (a). `PersistentFailure.since`.** Sale de `cases.updated_at`. Cada `UPDATE` de `case-service` sobre `cases` fija `updated_at` (barrido, `retry`, confirmación de la decisión, marca de congelamiento). Hay una prueba de integración (`test_persistent_failure_since_is_the_time_of_the_state_change`). La candidata F-05 de U08-T02 (`persistent_failure` con `since` ausente) deja de ocurrir en la práctica, porque `updated_at` es `NOT NULL`; sigue habiendo un `ValueError` en `views` solo como defensa.

## Purga adelantada (P-5 de la enmienda)

`retention.purge_intake_keys(conn)` borra las filas de `intake_keys` con más de `retention_settings.intake_keys_days` días (30 por omisión, BR-U8-02); el plazo sale de la tabla, nunca de un argumento. Corre con el rol `case_retention`, el único con `DELETE` sobre `intake_keys`. PBT-U8-06 (`tests/property/test_intake.py`) la llama para comprobar que la llave queda libre. La CLI `case-retention` y PBT-U8-08 son del Paso 16.

## Contrato entre `case-service` y `case-worker` sobre el outbox

`evidence_outbox.payload` es la entrada completa del registro en JSON (`RegistryEntryIn`: `actor`, `correlation_id`, `payload`, `model_version_id`, `policy_version_id`, y los demás campos del sobre). El reconciliador le impone `entry_type`, `case_id` e `idempotency_key` desde las columnas, y un `occurred_at` nuevo en cada intento; el resto va tal como se construyó. El worker (U08-T04) debe insertar así sus `fail_closed` (rol `case_worker`, `INSERT` simple dentro de un `SAVEPOINT`).

## Reconciliador (P-U8-04)

- Cada 1 s, lotes de 100 con `FOR UPDATE SKIP LOCKED`, como máximo 4 envíos en vuelo (`RECONCILER_CONCURRENCY`).
- **Arrendamiento** (`config.RECONCILER_LEASE`, 125 s): al reclamar, `next_attempt_at` pasa a `ahora + 125 s`. No es el del worker (`config.LEASE`, 30 s): cubre el peor lote (100 filas / 4 en vuelo × 2,5 s × 2 por el reintento por 401), no un envío. Así dos réplicas no reintentan la misma evidencia en un ciclo, aunque la segunda arranque a mitad del lote; si una réplica muere, sus filas vuelven a ser elegibles a los 125 s. El envío inmediato de la decisión y de la consulta inserta ya con `next_attempt_at = ahora + 125 s`, para que el reconciliador no lo envíe en paralelo. Las demás constantes de `case-service` (`RECONCILER_*`, `SWEEP_INTERVAL`, `GAUGE_INTERVAL`, `JOBS_OVERDUE_AFTER`, `SERVING_CONFIG_CACHE_TTL`, `DB_*`) viven en `config.py`.
- Backoff de 1 s a 5 min con jitter de ±20 %, a partir de `attempts`; a las 24 h (`created_at`) la evidencia y su decisión pasan a `abandonada` y suben `vectra_case_evidence_abandoned_total{entry_type}`.
- Una `explanation_view` abandonada que el analista abre de nuevo vuelve a `pendiente_registro` con `created_at = ahora` (plazo de 24 h nuevo), el mismo payload y la misma llave.
- Todos los tiempos salen del reloj inyectado (`Evidence.clock`), no de `now()` de la base, para que las pruebas simulen horas y días.
- **Conflicto tras un abandono** (BR-U8-18): se reenvía cada decisión abandonada del caso (la más nueva primero) hasta obtener el ack original; en una transacción, la nueva pasa a `abandonada` y después la anterior a `confirmada` y el caso a `decidido`.

## `first_evaluation` (línea del Paso 10 que pasa a U08-T04)

Ninguna entrada que escribe `case-service` (`human_decision`, `explanation_view`, `fail_closed`) lleva `first_evaluation`: ese campo viaja solo en la `recommendation` que escribe scoring, con el valor que calcula `evaluation` (U08-T04) a partir de `cases.ever_degraded` y el intento. `case_app` además no puede escribir `ever_degraded`. Por eso la prueba de «caso nuevo → `true` en el intento 1 y `false` en el 2, descongelado → `false`, reintentado por el CRO → `false`» pasa a U08-T04. Lo que sí prueba esta tarea es que `retry` y el barrido dejan `attempts = 0`, un trabajo `attempt = 0` y no tocan `ever_degraded`.

## Degradación (P-U8-03)

La base se traduce a `503 dependency_unavailable`: conexión perdida, pool agotado (2 s) y `default_transaction_read_only` (`ReadOnlySqlTransaction`). Con solo lectura, `get_case` y `list_cases` siguen respondiendo y `/readyz` sigue en 200. `/readyz` (8081) hace una conexión corta (`SELECT 1`, 1 s) con `case-db` y nada más; governance, registro y core caídos no lo afectan. `get_case` nunca falla por el core.

## Arranque y apagado

`python -m vectra_case.app` → `Settings.from_env()` (variables obligatorias: `CASE_DB_DSN`, `CASE_GOVERNANCE_URL`, `CASE_REGISTRY_URL`, `CASE_CORE_ENABLED`, `CASE_CORE_URL` si el core está habilitado, `CASE_ALLOW_TEST_SCENARIOS`, y las de U0: `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH`) → `ops_server.run_service`. `build_app()` sin argumentos no lee el entorno ni abre conexiones (lo usa CA-6); los servicios y los tres bucles (reconciliador, barrido, gauges) arrancan en el `lifespan`. Con `SIGTERM`, los tres bucles dejan de tomar trabajo, terminan el lote en curso y se cierran los clientes; uvicorn vuelve a emitir la señal, así que el proceso termina con 0 o con `-SIGTERM`. El `preStop` es del chart (U08-T05).

## Diferidos por la demo (recortes E*F)

- La alerta `CaseEvidenceDiscarded` y su prueba de `promtool` (Paso 21, U08-T05). La métrica `vectra_case_evidence_discarded_total` sí existe, creada en 0 y con su prueba.
- Las métricas de retención `vectra_case_retention_overdue_identifiers`, `vectra_case_retention_last_success_timestamp` y `vectra_case_retention_consecutive_overdue_runs` y NFR-U8-46.
- La CLI `case-retention` y PBT-U8-08 (Paso 16).

---

# Bloques E y F (U08-T04)

`case-worker` (Pasos 14 y 15) y `core-banking-mock` (Paso 17). El Paso 16 (CLI `case-retention`) está diferido por la demo.

## Módulos

| Módulo | Paso | Qué hace |
|---|---|---|
| `governance_client` | 14 | `ServingConfigClient` gana `feature_spec(model_version_id)`: `GET /v1/models/{id}/feature-spec`, 1 s, validado con `FeatureSpec` de U0, caché sin expiración por versión y LRU de 4 (`FEATURE_SPEC_CACHE_SIZE`, `OrderedDict`). Un solo `DependencyClient` por proceso (un pool y un breaker, P-U8-02); el pool es un parámetro: 2 en `case-service`, 4 en `case-worker` (`GOVERNANCE_WORKER_POOL`). Cada llamada lleva un tope duro con `asyncio.timeout` además del `httpx.Timeout` de `deps`. |
| `evaluation` | 14, 15 | `ScoringClient` (F15: 16 conexiones, 7 s, `POST /v1/recommendations`, validado con `RecommendResult`; vive aquí y no en `governance_client` porque solo lo usa la evaluación, así que no se crea un módulo que §1 no nombra), `build_request` (sin E/S, PBT-U8-05), `Evaluator` (el intento y la aplicación del resultado, BR-U8-08), `escalate` (BR-U8-09) y `Taken`. |
| `job_queue` | 15 | `JobQueue.take`: `FOR UPDATE SKIP LOCKED`, arrendamiento de 30 s, `attempt` leído (no `attempt + 1` en SQL), escalamiento en la toma con `attempt = 6`. |
| `worker` | 15 | `Worker` (semáforo de 16, sondeo de 400 ms ± 100 ms, drenaje de 20 s), `WorkerSettings.from_env` y `python -m vectra_case.worker` (sondas en 8081; no expone 8080). |
| `metrics` | 15 | Se añade `vectra_case_time_to_ready_seconds` (sin etiquetas; buckets 0,5, 1, 2, 3, 5, 10, 30 y 60 s; solo casos `listo` al primer intento y `ever_degraded = false`). |
| `case_fsm` | 15 | P-1 (a): la fila (`en_evaluacion`, `attempt_6_failed`) → `no_disponible`. |
| `core_banking_mock` | 17 | `app.py` (`build_app`, 2 rutas, `credits.json`), `auth.py` (autenticador perezoso del entorno y `WriteAttemptMiddleware`), `metrics.py` (`vectra_core_write_attempts_total`). No importa `vectra_case` ni `httpx`. |

## Decisiones tomadas (el usuario fusionó la tarea sin cambiar ninguna: rige la recomendación (a) en las cinco)

- **U08-T04 P-1 (a). Escalar desde `en_evaluacion`.** `case_fsm.TRANSITIONS` admite (`en_evaluacion`, `attempt_6_failed`) → `no_disponible`; la prueba unitaria y BR-U8-12 (y el diagrama de `business-logic-model.md`) lo dicen. La prueba que compara `case_fsm` con `case_transitions` sigue en verde (el par de estados ya existía en la migración). PBT-U8-01 lo recorre con seis `worker_lost` seguidos.
- **U08-T04 P-2 (a). El `SIGTERM` con un scoring «que responde a los 10 s».** `SCORING_TIMEOUT` es de 7 s, así que una respuesta a los 10 s nunca llega. `test_worker_shutdown.py` prueba la línea del plan con un doble que responde a los 5 s (el intento termina y el caso queda `listo`) y añade un caso con 10 s: el intento termina a los 7 s como `scoring_unreachable`, el trabajo queda reprogramado y sin arrendamiento y el proceso sale antes de los 20 s. **Propuesta:** corregir INF-U8-06 («responde a los 10 s») en el diseño; queda como candidata.
- **U08-T04 P-3 (a). `vectra_case_first_attempt_failure_ratio`.** La prueba la calcula desde los contadores del proceso con la definición de NFR-U8-03 (intentos 1 que no terminaron en `recommendation` / intentos 1), sobre 300 casos y con semilla fija. La regla de grabación es del Paso 21 (U08-T05); la expresión PromQL equivalente para copiar y probar con `promtool`:

  ```promql
  sum(rate(vectra_case_attempts_total{attempt="1", result!="recommendation"}[5m]))
  /
  sum(rate(vectra_case_attempts_total{attempt="1"}[5m]))
  ```

  El doble falla con `FailClosed` (200) y no con 5xx: una racha de 5xx abriría el breaker de scoring (≥ 50 % en 20 llamadas) y el doble ya no decidiría la razón.
- **U08-T04 P-4 (a). El `WriteAttempt` del mock.** Es el registro `authz.denied` que U0 ya emite en el 403 de `POST /v1/credits/{id}/status` (`route_template`, `error_code`, `principal_subject`) más el incremento de `vectra_core_write_attempts_total`, que cuelga de la denegación de esa ruta (`WriteAttemptMiddleware`, el más externo: un `POST` a esa ruta que termina en 403) y no del handler. El handler, si llegara a ejecutarse (un token que traiga `core:write-credit`), también responde 403 y se cuenta igual. Un 401 (sin token o con firma inválida) no cuenta. No cambia U0. **Diferencia con el texto de P-4:** el registro `authz.denied` de U0 no lleva `http_method` (`ProblemHandlerMiddleware._record_denied` solo emite `route_template`, `error_code` y `principal_subject`); la ruta identifica el método porque solo hay un `POST` con esa plantilla. Si se quiere `http_method = POST` en el registro, es un cambio de U0 (candidata).
- **U08-T04 P-5 (a). Vencimiento en PBT-U8-01.** `tests/doubles/worker_support.expire_case` aplica el vencimiento con el rol `case_retention` real: envejece `created_at` con el superusuario (`guard_vencido` lee la fecha), pasa el caso a `vencido` y borra su trabajo. `guard_transition` y `guard_vencido` siguen activos. No hay código de producción nuevo en `retention.py`. **Dependencia de PBT-U8-01 sobre el Paso 16:** cuando exista la corrida de `case-retention`, el apoyo debería llamarla.

## `evaluation` y `job_queue`: lo que fija el código

- **Toma** (`JobQueue.take`, una transacción corta): elige el trabajo debido (`run_at <= ahora` y sin arrendamiento vigente), lee `attempt`, fija `locked_until = ahora + 30 s`, escribe `attempt = leído + 1` en `evaluation_jobs` y lo copia a `cases.attempts` (con `updated_at`). Con `attempt = 6` escala en esa transacción (`local_cause = scoring_unreachable`, sin incrementar y sin llamar). Si el caso ya salió del bucle (`listo`, `decidido`, `vencido`…) el trabajo se borra y no se evalúa. La conexión vuelve al pool antes de la llamada a scoring.
- **Intento** (BR-U8-05): `serving-config` → `feature_spec` → `derive` → `ScoringRequest` → scoring. Una falla al leer `serving-config` o `feature_spec`, una respuesta inválida (la forma vieja de U04-T09) o un `FeatureSpec` que `derive` no puede usar termina el intento como `serving_config_unavailable`, sin llamar a scoring (falla cerrado).
- **Resultado** (BR-U8-08): `Recommendation` → `listo` y borra el trabajo; `FailClosed(model_frozen)` → `modelo_congelado` con `attempts = 0`, `last_cause = model_frozen` y sin trabajo; los demás `FailClosed` y los fallos de transporte, 5xx, circuito abierto y respuestas que no son un `RecommendResult` → `en_sincronizacion` y reprogramación (`run_at` por el backoff y `locked_until = NULL` en `evaluation_jobs`; `last_cause` en `cases`); un 4xx (el 401 ya se reintentó dentro de `deps.call`) → `scoring_rejected`, escala de inmediato. Los tres estados degradados ponen `ever_degraded = true` en la misma transacción.
- **Guarda** (BR-U8-08): cada `UPDATE` lleva `WHERE state IN (en_evaluacion, en_sincronizacion) AND attempts = :attempt` y `EXISTS (trabajo vivo del caso con locked_until = el que fijó esta toma)`. La toma entrega ese `locked_until` en `Taken.leased_until`; la guarda identifica **la toma**, no el número, porque `attempts` vuelve a 0 al congelar y con el `retry` del CRO (ronda 2 de U08-T04, F-01 de la ronda 1: un resultado tardío del intento 1 de un ciclo anterior se aplicaba al intento 1 del ciclo siguiente). Sin migración: usa `evaluation_jobs.locked_until`, que ya existe y que `case_worker` ya lee al tomar. El escalamiento de la propia toma (`attempt = 6` sin llamar a scoring) no la comprueba (`leased_until = None`): tiene la fila bloqueada. Sin fila cambiada, el resultado se descarta con `evaluation.result_discarded` (con `case_id` y `attempt`) y no se tocan el trabajo, la métrica ni el caso. `vectra_case_attempts_total` solo cuenta los resultados aplicados.
- **Escalamiento** (BR-U8-09): `no_disponible`, `escalation_count + 1` y la entrada `fail_closed` con la forma del contrato de arriba (`payload` = `RegistryEntryIn` con un `FailClosedPayload`, `actor` = `case-worker`), llave `uuid5(case_id, "fail_closed:<ciclo>")`, `INSERT` simple en un `SAVEPOINT`, `unique_violation` = éxito. `retryable = false` solo con `scoring_rejected` (o `model_frozen`, que no escala).
- **Reloj inyectado**: `run_at`, `locked_until`, `escalated_at` y el backoff salen del reloj del `Evaluator`/`JobQueue`, no de `now()` de la base.
- **`ever_degraded` y `first_evaluation`**: `first_evaluation = not cases.ever_degraded and attempt = 1`, `received_at = cases.created_at` en todos los intentos. `retry` del CRO y el barrido de `case-service` dejan `ever_degraded` como está.

## Variables de entorno

Todas obligatorias, sin valores por omisión: si falta una, el proceso no arranca (`KeyError`).

| Proceso | Variables |
|---|---|
| `case-worker` (`python -m vectra_case.worker`) | `CASE_DB_DSN` (con el rol `case_worker`), `CASE_GOVERNANCE_URL`, `CASE_SCORING_URL`; las de U0 para el token de servicio: `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` (y `VECTRA_CLIENT_KEY_ID` opcional) y `VECTRA_CA_BUNDLE` si las URL son `https`. Un `provider_from_env` por audiencia: `scoring-service` (`case:recommend`) y `governance-service` (`governance:read-serving`, `governance:read-feature-spec`). |
| `core-banking-mock` (`python -m core_banking_mock.app`) | `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL` (y `VECTRA_CA_BUNDLE` con `https`) para validar los tokens. Los créditos salen de `/app/fixtures/credits.json` (INF-U8-02); copiarlo a la imagen es del Paso 19. |

Ninguna constante de `config.py` se lee del entorno.

## Arranque y apagado del worker

`python -m vectra_case.worker`: sirve las sondas y `/metrics` en 8081 con `ops_server.create_ops_app` (readiness: solo `case-db`) y corre el bucle; no expone 8080. `ops_server.serve` exige una app en 8080, así que el worker levanta `uvicorn` solo para la app de sondas y maneja `SIGTERM` y `SIGINT` él mismo (se anula `capture_signals`, que vuelve a emitir la señal al salir y mataría el drenaje). Con la señal: deja de sondear, espera las llamadas en vuelo hasta 20 s y cierra clientes y base; sale con 0. **La gracia de 20 s empieza en el `SIGTERM`**, aunque los 16 huecos estén ocupados (el bucle espera un hueco o el `stop()`, el que llegue primero; ronda 2 de U08-T04, F-04). **Peor caso real del apagado (para `terminationGracePeriodSeconds`, U08-T05):** una toma que ya estaba en curso al llegar la señal (acotada por `DB_ACQUIRE_TIMEOUT` 2 s + `DB_CONNECT_TIMEOUT` 2 s, normalmente milisegundos) + 20 s de drenaje + hasta `GRACEFUL_SHUTDOWN` = 10 s de uvicorn de sondas, que solo se consume si una conexión de sondas sigue abierta (las dos esperas son seriales: `ops.should_exit` se pone al terminar el drenaje) + el cierre de clientes y base (milisegundos) = **≈ 34 s en el peor caso**. El caso normal termina cuando terminan las llamadas en vuelo: segundos con un scoring sano (el drenaje de 20 s es un tope, no una espera). `WORKER_TERMINATION_GRACE = 30 s` no cubre el peor caso: el chart debe usar 40 s, o bien U0 bajar `GRACEFUL_SHUTDOWN` (candidata). Lo que no termine en 20 s queda arrendado y otro worker lo retoma a los 30 s (BR-U8-07). **Candidata de U0:** un `ops_server.serve_ops_only(readiness)` y una opción para no capturar señales.

## `core-banking-mock`

`create_app("core-banking-mock", handlers=…)` con las 2 rutas de `REGISTRY` y `authenticator_from_env`; arranque con `ops_server.run_service` (8080 y 8081). `GET /v1/credits/{id}` (`core:read-credit`, `aud = core-banking-mock`) responde un `CreditStatusView` o 404; el fixture trae un crédito por cada estado del core. `POST /v1/credits/{id}/status` exige `core:write-credit`, que nadie tiene: la autorización de U0 lo deniega antes del cuerpo (403, no 422). `vectra_core_write_attempts_total` no lleva etiquetas y nace en 0 al importar `core_banking_mock.metrics`.

## Cobertura (Paso 18)

- `make -C case-management check` exige 95 % de ramas en `vectra_case` y 100 % en los ocho módulos de NFR-U8-50 que entran: `case_fsm`, `backoff`, `decision`, `views`, `intake`, `evidence`, `evaluation` y `sweeps`. `retention` sigue sin umbral propio (diferido por la demo).
- `worker.py` y `app.py` corren su `main()` en un subproceso: la cobertura de subprocesos se mide con `patch = subprocess` en `coveragerc` y `COVERAGE_PROCESS_START`. No se usa `omit` ni se excluyen archivos de `source`.
- Ramas inalcanzables: se quitó la de `Evidence.record_view` (`if to_send is not None`, siempre verdadera: toda salida del `async with` que no es `return` deja una fila que enviar) y la de `worker.run` que esperaba a las sondas (si `uvicorn` no puede abrir 8081 sale del proceso con 1). El comportamiento no cambia. Las pruebas nuevas de `evidence`, `sweeps` e `intake` están en `tests/integration/test_evidence_edges.py`.
- `case-management/conftest.py` importa `core_banking_mock` primero: con `--import-mode=importlib`, `core_banking_mock/tests/test_x.py` se llamaría `core_banking_mock.tests.test_x` y pytest crearía un `core_banking_mock` vacío que tapa el paquete.
- La semilla de Hypothesis se fija y se imprime en el encabezado de pytest también en verde (`tests/conftest.py`, NFR-U8-52).

## Notas que pidió el revisor de U08-T03 (solo texto: `evidence.py` no cambia por ellas)

- **Qué cubre la cifra de `RECONCILER_LEASE`** (125 s, F-01 de la ronda 2): `BATCH_SIZE // RECONCILER_CONCURRENCY * REGISTRY_TIMEOUT * 2`, es decir, 25 turnos de hasta 2,5 s con el reintento por 401. No cuenta el tiempo del token (`TOKEN_TIMEOUT`, 2 s), las transacciones de `_confirm` y `_fail`, ni los envíos extra de `_resolve_conflict`; y `httpx.Timeout` limita cada fase, no la llamada entera, así que el peor caso real de un lote es de ≈ 225 s. Si un lote lo excede, el efecto es un reenvío idempotente (misma llave, mismo contenido), no una pérdida. U08-T05 alinea `terminationGracePeriodSeconds` con esta cifra.
- **Envío inmediato interrumpido** (F-02 de la ronda 2): `decision` y `explanation-views` insertan la evidencia ya arrendada (`next_attempt_at = ahora + 125 s`) y la envían. Si el proceso muere después del `INSERT`, o `settle` lanza algo que no es `VectraError`, la fila queda arrendada 125 s y el reconciliador no la reclama hasta que venza: igual que el caso de una réplica muerta. Es aceptable: la alerta `CaseEvidencePending` salta a 1800 s y el abandono es a las 24 h.

## Pragmas

Ninguno: ni `# pragma: no cover` ni `omit`. El 100 % de los ocho módulos y el 95 % de `vectra_case` se miden con las pruebas (la cifra está en `bitacoras/U08-T04.md`).

## Diferidos por la demo (E*F)

- **Paso 16**: la CLI `case-retention`, PBT-U8-08, la corrida de P-U8-07 y las tres métricas de retención (ya listadas arriba). `retention.py` sigue con la purga de `intake_keys` de U08-T03.
- El umbral de cobertura de `retention`.
- `mutmut` (NFR-U8-51; T3).
- Bloque G (U08-T05): Dockerfiles y copia del fixture a la imagen, chart, reglas (`ScoringRequestRejected`, `CaseFirstAttemptFailureHigh` con su regla de grabación, `CaseJobsOverdue`, `CoreWriteAttempt`), runbooks, `docs/api.md`, `tools/check_openapi.py`, Applications y k6.
- El Paso 24 (kind) está consolidado en U12 Paso 18.
