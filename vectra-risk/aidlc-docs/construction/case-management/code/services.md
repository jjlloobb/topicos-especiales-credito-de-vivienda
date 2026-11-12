# U8 `case-management`: resumen de los servicios (Bloque D, U08-T03)

Este archivo lo completa el Paso 18 (U08-T04) con los Bloques E y F. Aquí está la sección del **Bloque D** (`case-service`: Pasos 9 a 13).

## Módulos

| Módulo | Paso | Qué hace |
|---|---|---|
| `intake` | 9 | `submit` (ingesta y alta manual), idempotencia, `X-Test-Scenario`, `body_sha256`. |
| `retention` | 9 (P-5) | Solo `purge_intake_keys` (ver «Purga adelantada»). La CLI es del Paso 16. |
| `evidence` | 10 | `Evidence` (decisión, consulta), `Reconciler`, `RegistryClient`. |
| `sweeps` | 11 | `Sweeper`: `modelo_congelado` y la marca `model_frozen_after_recommendation`. |
| `db_gauges` | 11 | `DbGauges`: `vectra_case_jobs_overdue`, `vectra_cases_failclosed_persistent`, evidencia pendiente. |
| `governance_client` | 11 | `ServingConfigClient` (solo `serving-config`). |
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
