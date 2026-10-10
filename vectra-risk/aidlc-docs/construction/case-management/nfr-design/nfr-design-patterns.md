# Patrones de NFR Design — U8 `case-management`

Decisiones del plan (`case-management-nfr-design-plan.md`, Q1–Q6 = A). Los IDs `P-U8-xx`
se referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind
las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás corren en CI.

---

## 1. Evaluación y cola

### P-U8-01 — Cola en tabla con arrendamiento corto (NFR-U8-04, 11, 13; BR-U8-07, 08)
- **Bucle del worker** (`case-worker`):
  - un semáforo de 16 limita los trabajos en vuelo por réplica;
  - con cupo libre y sin trabajos, sondea cada **400 ms ± 100 ms** de jitter (≤ 500 ms, NFR-U8-04); con trabajos, vuelve a tomar de inmediato.
- **Toma (transacción 1, corta)**:

  ```sql
  SELECT case_id, attempt FROM evaluation_jobs
   WHERE run_at <= now() AND (locked_until IS NULL OR locked_until < now())
   ORDER BY run_at
   LIMIT :cupo
   FOR UPDATE SKIP LOCKED;
  -- por cada fila tomada, según el attempt leído:
  --   attempt = 6 (el worker se perdió en el intento 6): escalamiento (BR-U8-09) en esta
  --     misma transacción, sin incrementar, sin llamar a scoring, y borrado del trabajo
  --   attempt < 6:
  UPDATE evaluation_jobs SET locked_until = now() + interval '30 s', attempt = attempt + 1
   WHERE case_id = :case_id RETURNING attempt;
  UPDATE cases SET attempts = :attempt, updated_at = now() WHERE case_id = :case_id;
  COMMIT;
  ```

  **Cada toma incrementa el número**, incluida la retoma tras un arrendamiento vencido, y lo copia a `cases.attempts`. Ese número es el que viaja en el `ScoringRequest` y el que usa la guarda de la transacción 2 (precisado el 2026-10-08, revisión del plan de tareas de U8). `case_worker` tiene `SELECT` y `UPDATE` sobre `evaluation_jobs`, así que el `RETURNING` de esta tabla sí está permitido. La decisión de escalar se toma con el valor **leído**, antes de escribir: así nunca se escribe un 7, que el `CHECK (attempt BETWEEN 0 AND 6)` rechazaría (precisado el 2026-10-08, segunda revisión del plan de tareas de U8).

  La conexión vuelve al pool antes de llamar a governance o a scoring.
- **Llamadas** (sin conexión ni transacción): `serving-config` → `feature_spec` → `derive` → scoring. El peor caso es 0,5 + 1 + 7 + 7 s (reintento por 401) = **15,5 s**, por debajo del arrendamiento de 30 s.
- **Aplicación del resultado (transacción 2, corta)**: `UPDATE cases … WHERE case_id = :id AND state IN ('en_evaluacion','en_sincronizacion') AND attempts = :attempt`, más la reprogramación o el borrado del trabajo, en la misma transacción (BR-U8-07, 08). Si no se actualiza ninguna fila, el resultado se descarta con el log `evaluation.result_discarded`.
- **Worker muerto o detenido**: otro worker retoma el trabajo cuando vence `locked_until`, con el número incrementado. Si el primero vuelve con su resultado, la condición `attempts = :attempt` (su número ya no es el vigente) o el cambio de estado lo descartan. El intento perdido cuenta como uno de los 6; si el trabajo retomado ya tiene `attempt = 6`, el caso escala sin incrementar, con `local_cause = scoring_unreachable`. Una `Recommendation` descartada queda en el registro como no entregada (P-U7-03).
- **Barridos y reconciliador** (`case-service`): corren en todas las réplicas con `FOR UPDATE SKIP LOCKED` y lotes de 100 (NFR-U8-13).
- **Verificación**:
  - Testcontainers: con el worker ocioso, un trabajo nuevo se toma en ≤ 600 ms (NFR-U8-04);
  - 16 trabajos en vuelo con un doble de scoring de 7 s y un pool de 5 conexiones → ninguna espera de conexión y `pg_stat_activity` sin transacciones abiertas durante la llamada (NFR-U8-11);
  - primer intento exitoso → `listo` con `attempts = 1`;
  - un worker detenido después de la toma → otro lo retoma tras 30 s con el número incrementado, y el resultado tardío del primero se descarta;
  - worker perdido en el intento 6 → la retoma escala sin llamar a scoring;
  - 2 réplicas de `case-service` → cada evidencia pendiente se reintenta una sola vez por ciclo (NFR-U8-13);
  - PBT-U8-01 (resultados tardíos).
- **Satisface**: NFR-U8-02, 04, 11, 13; RESILIENCY-08, 10; AUTONOMIA-06.

### P-U8-02 — Un cliente por dependencia, con límite, timeout y circuit breaker (Q6; NFR-U8-30..34)

| Proceso | Dependencia | Flujo | Conexiones máx. | Timeout | Abierto → |
|---|---|---|---|---|---|
| `case-worker` | scoring | F15 | 16 | 7 s | `scoring_unreachable` (el intento cuenta) |
| `case-worker` | governance (`serving-config`, `feature_spec`) | F104 | 4 | 500 ms / 1 s | `serving_config_unavailable` |
| `case-service` | registro | F16 | 10 | 2,5 s | 503 en la decisión; el reconciliador lo intenta en el ciclo siguiente |
| `case-service` | governance (barrido de BR-U8-10/14) | F104 | 2 | 500 ms | el barrido se salta el ciclo |
| `case-service` | core (solo kind y staging; en producción `core.enabled = false`, sin pool ni llamada, INF-U8-02) | F17 | 10 | 500 ms | `credit_status = no_disponible` |

- Cada cliente es un `httpx.AsyncClient` propio, creado con `vectra_common.deps`, con su propio circuit breaker. Los umbrales son los de U7: ≥ 50 % de fallos en las últimas 20 llamadas dentro de 30 s, y semiabierto a los 10 s.
- Esperar una conexión libre del pool **cuenta** dentro del timeout de la llamada. Una dependencia lenta agota solo su propio pool.
- **Consumidores de la misma dependencia** (hallazgo 6 de la revisión): en `case-service`, el reconciliador hace **como máximo 4 envíos simultáneos** al registro por réplica (semáforo propio). Así quedan al menos 6 de las 10 conexiones para la decisión síncrona (NFR-U8-01), aunque el registro esté lento pero vivo.
- Fallo del breaker = timeout, error de conexión o 5xx; un 4xx no cuenta (NFR-U8-32, U0 P-U0-07).
- Sin reintentos fuera de BR-U8-07 (backoff del caso), BR-U8-18 (reconciliador) y el reintento por 401 de BR-U8-08 (NFR-U8-33).
- **Verificación**:
  - prueba de integración: scoring doble de 7 s con 16 trabajos en vuelo → las lecturas de `serving-config` siguen respondiendo en < 50 ms;
  - 20 respuestas 422 de scoring → circuito cerrado (NFR-U8-32);
  - registro doble que tarda 2 s con 100 evidencias pendientes → nunca más de 4 envíos del reconciliador en vuelo, y una decisión concurrente obtiene conexión sin esperar al pool;
  - scoring caído → tras 20 llamadas, los intentos terminan en < 50 ms (NFR-U8-31);
  - import-linter: U8 no importa librerías de circuit breaking (NFR-U8-34).
- **Satisface**: NFR-U8-30..34; RESILIENCY-10.

### P-U8-03 — Degradación por dependencia (NFR-U8-21..25)

| Dependencia caída | Readiness | Ingesta y alta | Evaluación | Decisión | Consulta de la explicación | `get_case` |
|---|---|---|---|---|---|---|
| `case-db` sin escritura | No `Ready` si no hay conexión; con solo lectura, `Ready` | 503, sin efecto | Se detiene (sin toma) | 503, sin efecto | 503 | Sigue (lectura) |
| Registro | `Ready` | Sigue | `FailClosed(registry_unavailable)` de scoring → `en_sincronizacion` | 503 y `pendiente_registro` (P-U8-04) | Pendiente; 204 | Sigue |
| governance | `Ready` | Sigue | `serving_config_unavailable` → backoff | Sigue | Sigue | Sigue |
| scoring | `Ready` | Sigue | `scoring_unreachable` → backoff → `no_disponible` a los ~15,5 min | Sigue | Sigue | Sigue |
| Core (solo kind y staging; en producción está deshabilitado y `get_case` responde `no_disponible` sin llamar, INF-U8-02) | `Ready` | Sigue | Sigue | Sigue | Sigue | `credit_status = no_disponible` |

- **Ningún fallo produce un caso `listo` sin una `Recommendation` registrada** (AUTONOMIA-06).
- **Verificación**: una prueba de integración por fila (NFR-U8-21..25), con `default_transaction_read_only` para la base y dobles caídos para el resto.
- **Satisface**: NFR-U8-20..25; RESILIENCY-06, 10; SECURITY-15.

## 2. Evidencia

### P-U8-04 — Outbox, reconciliador y alertas de evidencia (Q1; BR-U8-18, 19)
- **Reconciliador** en `case-service`, cada 1 s:
  - toma las evidencias `pendiente_registro` con `next_attempt_at ≤ now()` (lotes de 100, `SKIP LOCKED`) y las envía con **como máximo 4 en vuelo** (P-U8-02);
  - reintenta con la misma `idempotency_key`, el payload y el `correlation_id` originales, y un `occurred_at` nuevo;
  - el backoff va de 1 s a 5 min, con jitter de ±20 %;
  - a las 24 h la evidencia pasa a `abandonada`.
- **Métricas** (calculadas cada 30 s, en todas las réplicas):
  - `vectra_case_evidence_pending_oldest_seconds{entry_type}` (gauge);
  - `vectra_case_evidence_abandoned_total{entry_type}` (contador, lo incrementa la réplica que abandona; sus tres series se crean en 0 al arrancar, P-U8-06).
- **Alertas**:

  | Alerta | Condición | Severidad |
  |---|---|---|
  | `CaseEvidencePending` | `max(vectra_case_evidence_pending_oldest_seconds{entry_type=~"human_decision\|fail_closed"}) > 1800` | SEV2 |
  | `CaseEvidencePending` | `max(vectra_case_evidence_pending_oldest_seconds{entry_type="explanation_view"}) > 7200` | SEV3 |
  | `CaseEvidenceAbandoned` | `sum(increase(vectra_case_evidence_abandoned_total{entry_type=~"human_decision\|fail_closed"}[15m])) > 0` | SEV2 |
  | `CaseEvidenceAbandoned` | `sum(increase(vectra_case_evidence_abandoned_total{entry_type="explanation_view"}[15m])) > 0` | SEV3 |

  Con 30 min quedan 23,5 h para actuar antes del abandono. Una `explanation_view` pendiente no bloquea el caso: solo puede subestimar `explanation_viewed_before` (BR-U8-17).
- **Verificación**:
  - PBT-U8-07;
  - `promtool test rules` de las cuatro reglas con series sintéticas (29 min → no dispara; 31 min → dispara);
  - prueba de integración: un abandono incrementa el contador con su `entry_type`.
- **Satisface**: BR-U8-18, 19; RESILIENCY-05, 07; SECURITY-13, 15.

## 3. Seguridad

### P-U8-05 — `retention_settings` y trigger `guard_vencido` (Q2; BR-U8-20, NFR-U8-41, 46(f))
- **Tabla `retention_settings`**:
  - una sola fila (`CHECK (id = 1)`) con `decided_years`, `undecided_years`, `intake_keys_days`, `created_at` (fecha de la primera migración, no cambia) y `updated_at`;
  - la escribe **solo** `case_migrator`, con el Job de migración (F44), a partir de los values de Helm (`retention.decided_years = 10`, `retention.undecided_years = 2`, `retention.intake_keys_days = 30`) mediante `INSERT … ON CONFLICT (id) DO UPDATE`, que actualiza los plazos y `updated_at` pero **nunca** `created_at`;
  - `case_retention` y `case_app` solo tienen `SELECT`.
- **Una sola fuente**: el job, el trigger y la métrica `vectra_case_retention_overdue_identifiers` leen los plazos de esa tabla, nunca de argumentos ni constantes. La CLI de retención no acepta plazos por argumento.
- **Trigger `guard_vencido`** (`BEFORE UPDATE OF state ON cases`, `SECURITY INVOKER`):

  | Si | Entonces |
  |---|---|
  | `NEW.state = 'vencido'` y `current_user <> 'case_retention'` | Excepción |
  | `NEW.state = 'vencido'` y `OLD.state` ∈ {`decidido`, `vencido`} | Excepción |
  | `NEW.state = 'vencido'` y `OLD.created_at + make_interval(years => s.undecided_years) >= now()` | Excepción (retención no vencida) |
  | `current_user = 'case_retention'` y `NEW.state <> 'vencido'` y `NEW.state <> OLD.state` | Excepción (ese rol no escribe otro estado) |

  `s` es la fila de `retention_settings`. Cuarta barrera, como P-U4-06: rol → dominio → trigger → prueba de migraciones.
- **Verificación** (Testcontainers):
  - `case_app` escribe `vencido` → excepción;
  - `case_retention` escribe `vencido` en un caso de 1 año → excepción; en uno de 2 años y 1 día → éxito;
  - `case_retention` escribe `listo` → excepción;
  - `case_retention` y `case_app` intentan escribir en `retention_settings` → error de permisos;
  - cambiar `retention.undecided_years` en los values y migrar → el job y el trigger aplican el valor nuevo;
  - migrar dos veces con valores distintos de `retention.*` → `created_at` queda igual, mientras `updated_at` y los plazos cambian (si el upsert lo pisara, cada migración reiniciaría el plazo de 2 días de `CaseRetentionMissing`);
  - PBT-U8-08, con los plazos leídos de la tabla.
- **Satisface**: BR-U8-20; NFR-U8-41, 46(f); SECURITY-06, 11; AUTONOMIA-04, 05.

### P-U8-06 — Telemetría sin datos del solicitante y eventos de seguridad (Q4; NFR-U8-42..45)
- **Etiquetas permitidas** en las métricas de U8: `result`, `cause`, `state`, `entry_type`, `dependency`, `code`, `route_template` y `attempt` (1..6). Nunca `case_id`, `principal_subject` ni datos del solicitante.
- **Contadores en 0 al arrancar** (hallazgo 5 de la revisión): cada contador con etiquetas de conjunto cerrado crea todas sus combinaciones en 0 al iniciar el proceso. Sin eso, `increase()` pierde el primer evento de una serie nueva, que es justo el que detectan `ScoringRequestRejected` y `CaseEvidenceAbandoned`. Aplica a `vectra_case_attempts_total{result, attempt}` (6 × 6), `vectra_case_evidence_abandoned_total{entry_type}` (3), `vectra_case_retries_total` y, en el mock, `vectra_core_write_attempts_total`.
- **Logs**, solo con campos de la allowlist de U0 (domain-entities §8), igual que `authz.denied` (BR-U0-73):
  - `case.viewed` lleva `principal_subject`, `principal_role` y `case_id`;
  - `case.retry_requested` lleva `principal_subject`, `principal_role` y `case_id`;
  - los dos van al almacenamiento tamper-evident con retención ≥ 90 días (NFR-SEC-14).
- **Eventos con alerta**:

  | Evento | Métrica | Alerta | Severidad |
  |---|---|---|---|
  | 401/403 de case-service | `vectra_authz_denied_total{code, route_template}` | `AuthDeniedBurst` (U2) | SEV2 |
  | `WriteAttempt` en el mock, o denegación del proxy de Linkerd del mock | `vectra_core_write_attempts_total` (puerto 8081 del mock, F60) o `inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}` | `CoreWriteAttempt`, con la expresión de INF-U8-03: `increase()` para el contador del mock y una resta contra `offset 5m` para la serie de Linkerd, que nace en 1 (precisado el 2026-10-08 por U8 INF-U8-03: X01 bloquea el `POST` antes de llegar al mock) | SEV2 |
  | Casos en `no_disponible` | `vectra_cases_failclosed_persistent` | `FailClosedPersistente` (U1) | SEV2 |
  | `retry` del CRO | `vectra_case_retries_total` | Sin alerta (auditoría por log) | — |

- `CoreWriteAttempt` solo existe donde existe el mock (kind, staging). En producción el core está deshabilitado para el MVP (`core.enabled = false`, INF-U8-02): no hay flujo hacia ningún core y la alerta no se despliega. La integración con el core real, con su propio equivalente de esta alerta, queda pendiente para Operations. Su runbook explica que en la demostración de RT-5 la alerta es la evidencia esperada y que, fuera de una demostración anunciada, es un incidente de seguridad.
- **Verificación**:
  - PBT-U0-07 (allowlist de logs);
  - PBT-U0-07 en modo strict sobre `case.viewed` y `case.retry_requested`: ningún campo se descarta y el actor (`principal_subject`) está presente;
  - prueba de que el registro de métricas de U8 no tiene etiquetas fuera de la lista;
  - prueba de arranque: `GET /metrics` recién iniciado ya muestra cada combinación de los contadores en 0;
  - `promtool test rules` de `CoreWriteAttempt`;
  - prueba de ejemplo **del mock aislado, sin proxy de Linkerd** (tercera capa de INF-U8-03): un `POST /v1/credits/{id}/status` con un token válido sin `core:write-credit` → 403, `WriteAttempt` y la métrica en 1. Con la malla, el `POST` no llega al mock y la evidencia es la del proxy (INF-U8-03).
- **Satisface**: NFR-U8-42..45; SECURITY-03, 14; AUTONOMIA-05.

### P-U8-07 — Job `case-retention` (Q4; NFR-U8-46, 47)
- **CronJob** con:
  - `schedule: "30 2 * * *"` y `timeZone: America/Bogota`, fuera del horario operativo; la hora es un value;
  - `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 3600`, `activeDeadlineSeconds: 7200` y `backoffLimit: 2`.
- **Corrida** (`python -m vectra_case.retention --dsn …`, la misma CLI para el `restore-drill` de U1):
  1. lee `retention_settings` (P-U8-05);
     - el plazo de 10 años se cuenta desde `decisions.decided_at` de la decisión `confirmada`, porque `cases` no guarda esa fecha. Los permisos `SELECT` por columna que necesita el rol `case_retention` están en `logical-components.md` §1 (hallazgo 1 de la revisión);
  2. procesa en lotes de ≤ 500 casos por transacción, con `FOR UPDATE SKIP LOCKED` y `SET LOCAL lock_timeout = '1s'`:
     - borra `case_identifiers` y `application.free_text`;
     - fija `anonymized_at`;
     - si el caso no estaba decidido, lo pasa a `vencido` y borra su trabajo;
  3. borra las `intake_keys` con más de `intake_keys_days`;
  4. cuenta `overdue_remaining` (las filas que la API tenía tomadas se procesan en la corrida siguiente);
  5. inserta su fila en `retention_runs` con `status = exitosa`, o `fallida` si algo falló.
- **Métricas** (las expone `case-service`, calculadas cada 60 s desde `case-db`, sin flujo nuevo):
  - `vectra_case_retention_overdue_identifiers`;
  - `vectra_case_retention_last_success_timestamp`: el `finished_at` de la última corrida exitosa o, si todavía no hay ninguna, `retention_settings.created_at`. La serie existe desde la primera migración, así que una instalación que nunca corre la retención dispara la alerta a los 2 días;
  - `vectra_case_retention_consecutive_overdue_runs` (corridas exitosas consecutivas más recientes con `overdue_remaining > 0`).
- **Alertas** (con `max()` entre réplicas):

  | Alerta | Condición | Severidad |
  |---|---|---|
  | `CaseRetentionMissing` | `time() - max(vectra_case_retention_last_success_timestamp) > 2 * 86400`, **o** `absent(vectra_case_retention_last_success_timestamp)` durante 1 h | SEV2 |
  | `CaseRetentionOverdue` | `max(vectra_case_retention_consecutive_overdue_runs) >= 2` | SEV2 |

  SEV2 y no SEV1: los identificadores siguen cifrados y con acceso restringido, y hay 1 h para responder.
- **NFR-U8-47**: el despliegue a producción exige `case-management/docs/retention.md` firmado por cumplimiento. Los tres [VERIFICAR] siguen abiertos.
- **Verificación**:
  - NFR-U8-46: 2 000 casos vencidos con la API escribiendo en paralelo → ninguna espera de bloqueo > 1 s y 0 vencidos tras dos corridas;
  - PBT-U8-08;
  - `promtool test rules` de las dos alertas (una corrida con pendientes → no dispara; dos → dispara; serie ausente durante 1 h → `CaseRetentionMissing` dispara);
  - prueba de migraciones con Testcontainers: la corrida completa se ejecuta con el rol `case_retention` real, sin superusuario, y no recibe ningún `permission denied`;
  - instalación nueva sin corridas → la métrica vale `retention_settings.created_at`.
- **Satisface**: NFR-U8-46, 47; BR-U8-02, 20; RESILIENCY-05; AUTONOMIA-05.

## 4. Observabilidad y operación

### P-U8-08 — Alertas operativas (Q3; NFR-U8-03, 12, 20; BR-U8-08)

| Alerta | Condición | Severidad |
|---|---|---|
| `CaseApiUnavailable` | `sum(up{job="case-service"}) == 0` **o** `absent(up{job="case-service"})` (el descubrimiento retira los targets cuando no queda ningún pod) durante 2 min, **o** la razón de 5xx de `case-service` > 5 % durante 5 min, sin contar los 503 de `dependency_unavailable` de la decisión con el registro caído (`route_template` de la decisión y `code = dependency_unavailable`) | SEV2 |
| `CaseJobsOverdue` | `max(vectra_case_jobs_overdue) > 0` durante 5 min | SEV2 |
| `CaseFirstAttemptFailureHigh` | `vectra_case_first_attempt_failure_ratio > 0.10` durante 15 min, con ≥ 20 casos con intento 1 en la ventana | SEV3 |
| `ScoringRequestRejected` | `sum(increase(vectra_case_attempts_total{result="scoring_rejected"}[5m])) > 0` | SEV2 |

- `vectra_case_jobs_overdue` es un gauge que calcula `case-service` cada 30 s: trabajos con `run_at < now() - 30 s` y sin tomar. `max()` evita sumar la misma cuenta de varias réplicas.
- `vectra_case_attempts_total{result}` usa `result` ∈ {`recommendation`, `failclosed`, `model_frozen`, `scoring_unreachable`, `serving_config_unavailable`, `scoring_rejected`}.
- `vectra_case_first_attempt_failure_ratio` es una regla de grabación sobre `vectra_case_attempts_total` filtrada por `attempt="1"` (la etiqueta `attempt` va de 1 a 6, cardinalidad acotada).
- Toda regla lleva `severity` y `runbook_url` (P-U1-10).
- Con todos los pods de `case-service` caídos, los gauges de la base desaparecen y `CaseJobsOverdue` no puede dispararse: en ese caso avisa `CaseApiUnavailable` por `absent()`.
- **Verificación**: `promtool test rules` de cada alerta con series sintéticas en los dos lados del umbral, más un caso **sin serie** para `CaseApiUnavailable` (sin `up{job="case-service"}` durante 2 min → dispara); y el test de U1 que exige `severity` y `runbook_url`.
- **Satisface**: NFR-U8-03, 12, 20; RESILIENCY-05, 07, 15.

### P-U8-09 — Escenarios de resiliencia de U8 (Q5; P-U0-08, decisión C)
Se documentan aquí y se ejecutan en Operations.

| # | Escenario | Resultado esperado |
|---|---|---|
| E1 | scoring caído | Casos en `en_sincronizacion`; circuito abierto tras 20 llamadas; `no_disponible` a los ~15,5 min; `FailClosedPersistente` |
| E2 | explainability caído (P-U0-08) | `FailClosed(explainer_unavailable)`; el caso sigue el backoff y queda `no_disponible` al agotar los intentos |
| E3 | Registro caído durante una decisión | 503; decisión `pendiente_registro`; `CaseEvidencePending` a los 30 min; el reconciliador confirma al volver el registro y el caso pasa a `decidido` |
| E4 | Failover de `case-db` | 503 en las escrituras durante el failover; ningún caso duplicado al reintentar el canal con la misma `Idempotency-Key` |
| E5 | Un pod de `case-worker` muere a mitad de una llamada | El trabajo se retoma al vencer `locked_until` (≤ 30 s); el resultado del intento anterior, si llega, se descarta (P-U8-01) |
| E6 | Core caído (solo kind y staging, donde existe el mock; en producción el core está deshabilitado, INF-U8-02) | `get_case` responde con `credit_status = no_disponible` dentro de su p99 |

- E1, E3, E5 y E6 tienen también una prueba de integración en CI (P-U8-01..04). E2 y E4 solo se ejecutan en Operations.
- **Verificación**:
  - en CI, las pruebas de integración de E1 (P-U8-02), E3 (P-U8-04), E5 (P-U8-01) y E6 (P-U8-03);
  - en Operations, los seis escenarios en kind o staging, con el resultado esperado de cada fila como criterio de aceptación y el reporte adjunto al runbook de la unidad.
- **Satisface**: RESILIENCY-14 (enfoque C).

### P-U8-10 — Procesos, escalado y conexiones (NFR-U8-10..15, 26)
- Una imagen y dos Deployments (`case-service` con la API, los barridos y el reconciliador; `case-worker` con la evaluación), más el CronJob `case-retention` y `core-banking-mock` en `vectra-mock` (solo kind y staging).
- `case-service` y `case-worker`: ≥ 2 réplicas repartidas por zona, PDB, HPA de 2 a 6 por CPU al 70 % y `PriorityClass` `vectra-high`. El mock: 2 réplicas, PDB, `vectra-low`.
- Pool de `case-db` ≤ 5 por réplica. Con los máximos: 12 × 5 = 60 conexiones, más el 20 %, `case-retention`, la migración y el operador (U1 Infrastructure Design).
- La cola atrasada no la detecta el HPA por CPU: la cubre `CaseJobsOverdue` (P-U8-08).
- **Verificación**: `helm template` + `conftest` + `kyverno test`; prueba de carga en kind (U12) sin `too many connections`.
- **Satisface**: NFR-U8-10..15, 26; RESILIENCY-08, 09.

## 5. Cumplimiento de extensiones (NFR Design U8)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | P-U8-10 (criticidad High, `vectra-high`); RPO y RTO de `case-db` heredados de U1 |
| RESILIENCY-05 / 07 / 15 | Cumple | P-U8-04, 06, 07, 08 (cada alerta con severidad, umbral y `runbook_url`) |
| RESILIENCY-06 | Cumple | P-U8-03 (readiness solo con `case-db`) |
| RESILIENCY-08 / 09 | Cumple | P-U8-01, 10 |
| RESILIENCY-10 | Cumple | P-U8-01, 02, 03 |
| RESILIENCY-11 / 12 / 13 | Cumple | Heredado de U1; P-U8-07 (la misma CLI de retención corre en el `restore-drill`) |
| RESILIENCY-14 | Cumple | P-U8-09 (enfoque C) |
| AUTONOMIA-02 | Cumple | Cada patrón, de P-U8-01 a P-U8-10, tiene su «Verificación» |
| AUTONOMIA-04 | Cumple | P-U8-05 (trigger como cuarta barrera) |
| AUTONOMIA-05 | Cumple | P-U8-05, 06, 07 |
| AUTONOMIA-06 | Cumple | P-U8-01, 03 (ningún caso `listo` sin recomendación registrada) |
| SECURITY-03 | Cumple | P-U8-06 |
| SECURITY-06 | Cumple | P-U8-05 (`retention_settings` solo la escribe `case_migrator`) |
| SECURITY-11 | Cumple | P-U8-05 (escrituras directas de `vencido` con otro rol o antes de plazo → excepción); P-U8-06 (`CoreWriteAttempt`, RT-5) |
| SECURITY-13 | Cumple | P-U8-04 |
| SECURITY-14 | Cumple | P-U8-06, 07 |
| SECURITY-15 | Cumple | P-U8-02, 03, 04 (fallos acotados y sin efecto) |
| PBT-06 | Cumple | PBT-U8-01 y 07 (stateful); PBT-U0-14 para el breaker |
| PBT-08 / 09 | Cumple | NFR-U8-52; PBT-U8-08 con los plazos de `retention_settings` |

## 6. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U8 business-rules BR-U8-20 y §8 | Plazos en `retention_settings`; el trigger los lee; fila del §8 «Pendiente para U8 NFR Design» marcada como resuelta | Q1, Q2, Q3 |
| U8 domain-entities §1.5 | Entidad `RetentionSettings` (tabla `retention_settings`) | Q2 |
| U8 NFR-U8-46(f) y §7 | Los plazos son values de Helm que la migración escribe en `retention_settings`; §7 resuelto | Q2, Q3, Q4 |
| `component-dependency.md` §4 | `SELECT` sobre `retention_settings` para `case_app` y `case_retention`; `case_migrator` la escribe | Q2 |
| `component-dependency.md` §4 (`case_retention`) | `SELECT` por columna sobre `case_identifiers.case_id`, `evaluation_jobs.case_id`, `intake_keys.created_at` y `decisions` (`case_id`, `decided_at`, `state`) | Revisión, hallazgo 1 |
| U8 domain-entities §1.5 | `created_at` en `retention_settings` (valor de la métrica antes de la primera corrida) | Revisión, hallazgo 2 |
| U8 NFR-U8-46(d) | `vectra_case_retention_last_success_timestamp` vale `retention_settings.created_at` mientras no haya una corrida exitosa | Segunda revisión, hallazgo 1 |
| U8 BR-U8-11, BR-U8-13b; NFR-U8-42, NFR-U8-45(d) | Los logs `case.viewed` y `case.retry_requested` llevan `principal_subject` y `principal_role` (allowlist de U0 §8), no `user_id` | Revisión, hallazgo 3 |
| U8 business-rules §8 | Celdas de las filas «Pendiente para U10» y «Pendiente para U9 y U11» corregidas | Revisión, cosméticos |
| U0 NFR Design P-U0-08 | Los escenarios de U8 están en P-U8-09 | Q5 |
