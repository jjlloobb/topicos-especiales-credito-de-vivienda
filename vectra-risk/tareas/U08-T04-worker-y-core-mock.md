# U08-T04 — `case-worker` (clientes, cola, evaluación), `core-banking-mock` y resumen de los servicios

**Unidad:** U8 `case-management`
**Historias que implementa:**
- US-112: backoff, recuperación y escalamiento a `no_disponible` con su entrada `fail_closed` (Paso 15);
- US-109: `free_text` nunca sale hacia scoring (Paso 15, PBT-U8-05);
- US-603: la escritura al core es imposible; el mock la rechaza y la cuenta (Paso 17).

Los Pasos 14 y 18 no tienen historia propia en la trazabilidad del plan (§3).

**Depende de:**
- U08-T01, U08-T02 y U08-T03 en `main` (ya están: los Pasos 1 a 13 del plan figuran `[x]`). De ellas se usan las migraciones y los grants de `case_worker`, `case_fsm`, `backoff`, `config.py`, `metrics.py`, `db.py`, `governance_client.py` (solo `serving-config`), el reconciliador de `evidence.py` y los dobles de `tests/doubles/`.
- U0 en `main`: `ScoringRequest`, `RecommendResult`, `FeatureSpec`, `derive`, `derive_monitoring_labels`, `FailClosedPayload`, `LocalCause`, `LogEvent.EVALUATION_RESULT_DISCARDED`, `deps` (con el reintento por 401 ya dentro de `deps.call`), `service_token.provider_from_env`, `ops_server`, `create_app` y las 2 rutas de `REGISTRY["core-banking-mock"]`.

Sin clúster (AUTONOMIA-01). Las pruebas de integración usan Testcontainers (Docker local) y dobles HTTP de governance, scoring y registro.
**Rama:** `tarea/U08-T04`, desde `origin/main`.

Son los Bloques E y F del plan de U8 (`aidlc-docs/construction/plans/case-management-code-generation-plan.md`), fusionados: **Pasos 14, 15, 17 y 18**. En `demo-recorte-funcional.md` §4 y §8 es la tarea «E+F (14, 15, 17, 18)». El Paso 16 (CLI `case-retention`) está en D (§3, U8, fila «16»). Los Pasos 14, 15 y 17 entran **completos** (E); el Paso 18 entra como **E\*F**, «Sin el umbral de `retention`» (§3, U8, fila «18 Resumen»). Las PBT del bloque (PBT-U8-01 y PBT-U8-05) no se recortan. Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): como máximo 2 rondas, y solo un ROJO bloquea.

Lo que sostiene en las demos (enmienda §1): el flujo base (ingesta → `case-worker` → governance y scoring → `listo`), D1 (`en_sincronizacion` con backoff hasta `no_disponible` en el intento 6, con su `fail_closed` en el outbox), D2 (`modelo_congelado` por `FailClosed(model_frozen)`) y D3 (`vectra_core_write_attempts_total` en 0 desde el arranque del mock).

Tarea que sigue en U8: **U08-T05**, Bloque G más el cierre (Pasos 19 a 23, 25 y 26). El Paso 24 queda consolidado en U12 Paso 18 (enmienda §8).

---

## Alcance

**Dentro:** los Pasos 14, 15, 17 y 18 del plan. Texto del plan, sin recortes salvo los dos del Paso 18, que se marcan con ~~tachado~~ y aparecen también en «Fuera».

### Bloque E — `case-worker`

- [ ] **Paso 14 — Clientes y caché de gobierno** (E)
  - Un `httpx.AsyncClient` por dependencia con `deps.call` (P-U8-02): scoring 16 conexiones y 7 s; governance 4 conexiones, 500 ms (`serving-config`) y 1 s (`feature_spec`).
  - `governance_client`: `serving-config` con caché ≤ 5 s e `If-None-Match`; `feature_spec` por versión, sin expiración, LRU de 4.
  - Fallo del breaker = timeout, conexión o 5xx; un 4xx no cuenta (NFR-U8-32). NFR-U8-31 se escribe `BreakerConfig(open_for=10, window_size=20, failure_ratio=0.5, window_seconds=30)`, y el token de servicio es `service_token.provider_from_env(audience, scopes)`, pasado como `token_source` (revisión de consistencia entre unidades, 2026-11-01).
  - Diseño: BR-U8-05; P-U8-02, 09; NFR-U8-15, 24, 30, 31, 32, 33.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_worker_clients.py`:
    - scoring doble de 7 s con 16 trabajos en vuelo → las lecturas de `serving-config` siguen respondiendo en < 50 ms;
    - 20 respuestas 422 de scoring → circuito cerrado;
    - scoring caído → tras 20 llamadas, los intentos terminan en < 50 ms (E1 de P-U8-09);
    - 5 versiones de `feature_spec` → se descarta la menos usada;
    - (de esta tarea) un 503 de governance produce **una sola** llamada por intento (NFR-U8-33);
    - (de esta tarea) `serving-config` con la forma vieja, sin `cutoff`, `low_confidence_threshold` ni `channel_rules` → el intento termina como `serving_config_unavailable`, sin llamar a scoring (falla cerrado; candidata «orden de despliegue» de U04-T09);
    - (de esta tarea) lo que sirven los dobles de governance y de scoring valida contra `ServingConfig`, `FeatureSpec` y `RecommendResult` de U0.

- [ ] **Paso 15 — `job_queue`, `evaluation` y `worker`** (E)
  - `job_queue` (P-U8-01): semáforo de 16; sondeo 400 ms ± 100 ms; toma en una transacción corta con `FOR UPDATE SKIP LOCKED`, `locked_until = now() + 30 s` y **`attempt = attempt + 1` copiado a `cases.attempts`**, también en la retoma tras un arrendamiento vencido; la decisión se toma con el `attempt` **leído**: si ya vale 6, escala en esa transacción con `local_cause = scoring_unreachable`, sin incrementar (nunca se escribe 7, que el `CHECK` rechaza) y sin llamar a scoring (BR-U8-07); la conexión vuelve al pool antes de las llamadas.
  - `evaluation` (BR-U8-05..09): `serving-config` → `feature_spec` → `derive` → `ScoringRequest` (sin identificadores, `free_text` ni `test_scenario_id`; con `received_at = cases.created_at` y `first_evaluation = not cases.ever_degraded and attempt = 1`, BR-U8-06; pendientes posteriores al cierre, 2026-10-10) → scoring; al entrar en `en_sincronizacion`, `no_disponible` o `modelo_congelado`, la misma transacción pone `cases.ever_degraded = true`; tabla de resultados de BR-U8-08, con el reintento por 401 dentro del mismo intento; aplicación del resultado con `UPDATE … WHERE state IN (…) AND attempts = :attempt`, con el número que devolvió esa toma, o `evaluation.result_discarded`; la reprogramación solo fija `run_at`, `last_cause` y `locked_until = NULL`.
  - Escalamiento: `no_disponible`, `escalation_count + 1` y la entrada `fail_closed` en `evidence_outbox` con `UUIDv5(case_id, "fail_closed", ciclo)`, exactamente uno de `cause` o `local_cause`, `retryable`, `attempt` y `escalated_at`, con un `INSERT` simple en un `SAVEPOINT` (sin `RETURNING` ni `ON CONFLICT`; `unique_violation` de la llave = éxito) en la misma transacción que el cambio de estado (BR-U8-09); la envía el reconciliador del Paso 10.
  - Métricas `vectra_case_attempts_total{result, attempt}` (creadas en 0) y `vectra_case_time_to_ready_seconds` (solo casos `listo` al primer intento; buckets 0,5, 1, 2, 3, 5, 10, 30 y 60 s; seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - Apagado: al recibir `SIGTERM` deja de sondear y espera las llamadas en vuelo hasta 20 s.
  - Diseño: BR-U8-05, 06, 07, 08, 09, 12; P-U8-01, 08, 09; INF-U8-06; NFR-U8-02, 03, 04, 11, 24. Historias: US-109, US-112.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evaluation.py case-management/tests/property/test_case_machine.py case-management/tests/integration/test_worker.py case-management/tests/integration/test_worker_shutdown.py` (Testcontainers y dobles). Las líneas son las del plan, todas:
    - PBT-U8-05 (ningún dato prohibido en el `ScoringRequest`; dos solicitudes que solo difieren en `free_text` producen el mismo `ScoringRequest`);
    - `received_at` es el `created_at` del caso en todos los intentos; `first_evaluation`: `true` solo en el intento 1 de un caso que nunca se degradó, y `false` después de pasar por `en_sincronizacion`, `no_disponible` o `modelo_congelado`, también tras un descongelamiento o un `retry` del CRO; `ever_degraded` nunca vuelve a `false` (pendientes posteriores al cierre, 2026-10-10);
    - PBT-U8-01 (stateful, sobre `case_fsm` y `evaluation`, contra el modelo de referencia, con los comandos `worker_lost` y `late_result`);
    - con reloj simulado: recuperación en el intento 3 → `listo`; 6 fallos → `no_disponible`, gauge = 1 y una entrada `fail_closed` (US-112);
    - versión pedida distinta de la de scoring → `FailClosed(version_mismatch)` y el caso reintenta;
    - scoring responde 403 → `scoring_rejected`, escala de inmediato y `vectra_case_attempts_total{result="scoring_rejected"}` sube; 401 una vez → reintento con token nuevo dentro del mismo intento;
    - resultado que llega con el caso `vencido` → el caso no cambia y queda `evaluation.result_discarded`;
    - con el worker ocioso, un trabajo nuevo se toma en ≤ 600 ms;
    - 16 trabajos en vuelo con un scoring de 7 s y un pool de 5 → ninguna espera de conexión y `pg_stat_activity` sin transacciones abiertas durante la llamada;
    - **primer intento exitoso → `listo` con `attempts = 1`** (la guarda no descarta el primer resultado);
    - un worker detenido después de la toma → otro lo retoma tras 30 s con `attempt` incrementado, y el resultado tardío del primero se descarta con `evaluation.result_discarded` (E5 de P-U8-09);
    - worker perdido en el intento 6 → la retoma escala a `no_disponible` con `local_cause = scoring_unreachable`, `attempts = 6` y una entrada `fail_closed`, sin llamar a scoring y sin violar el `CHECK`;
    - escalamiento con un `fail_closed` de la misma llave ya presente → el caso queda `no_disponible` y la transacción confirma;
    - doble de scoring que falla el 30 % de los primeros intentos → `vectra_case_first_attempt_failure_ratio` = 0,3 ± 0,05 (ver P-3);
    - `SIGTERM` al worker a los 0,5 s con un scoring que responde a los 10 s → el intento termina y el caso queda `listo` (ver P-2);
    - (línea del Paso 10 que U08-T03 pasó a esta tarea, `code/services.md`, «`first_evaluation`») caso nuevo → `true` en el intento 1 y `false` en el 2. Caso descongelado con `attempts = 0`, intento 1 → `false`. Caso reintentado por el CRO desde `no_disponible` → `false`. Se comprueba sobre el `ScoringRequest` que recibe el doble de scoring;
    - (de esta tarea) `FailClosed(model_frozen)` → `modelo_congelado`, `attempts = 0`, sin trabajo y `ever_degraded = true`; después del barrido de U08-T03, el intento 1 lleva `first_evaluation = false`;
    - (de esta tarea) la entrada `fail_closed` que inserta el worker (rol `case_worker`) la confirma el reconciliador de U08-T03 contra el doble del registro: una sola entrada, con exactamente uno de `cause` o `local_cause`, y `retryable = false` solo con `scoring_rejected`;
    - (de esta tarea) `GET /metrics` del worker recién iniciado muestra las 36 series de `vectra_case_attempts_total` en 0 y ninguna etiqueta fuera de la allowlist de P-U8-06;
    - (de esta tarea) `python -m vectra_case.worker` arranca de verdad, como proceso, con las variables obligatorias, y `/readyz` (8081) responde 200 con `case-db` arriba.

### Bloque F — `case-retention` y `core-banking-mock`

- ~~**Paso 16 — CLI `case-retention`**~~ **(diferido por la demo: enmienda §3, U8, fila «16 `case-retention`»: «D · D · Con PBT-U8-08»; ver «Fuera»).**

- [ ] **Paso 17 — `core-banking-mock`** (E)
  - FastAPI sin base, con los fixtures dentro de la imagen (`/app/fixtures/credits.json`).
  - `GET /v1/credits/{id}` con validación de firma por JWKS (F50), `aud = core-banking-mock` y scope `core:read-credit` con `vectra_common`.
  - `POST /v1/credits/{id}/status`: exige `core:write-credit`, que nadie tiene → 403, `WriteAttempt` en el log y `vectra_core_write_attempts_total` (creada en 0 al arrancar).
  - Métricas en 8081.
  - Diseño: BR-U8-22; INF-U8-02, 03; P-U8-06; NFR-U8-26, 45. Historia: US-603.
  - **Aceptación**: `uv run pytest case-management/core_banking_mock/tests`:
    - token sin `core:read-credit` → 403;
    - prueba **del mock aislado, sin proxy de Linkerd**: `POST` con cualquier token válido → 403, un `WriteAttempt` y la métrica en 1 (US-603);
    - `GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0;
    - (de esta tarea) `GET` con `core:read-credit` y un `id` del fixture → 200 con un `CreditStatusView` válido; un `id` que no está → 404; token con otra audiencia → 401;
    - (de esta tarea) `POST` con un token que **sí** trae `core:write-credit` (fabricado en la prueba) → también 403, `WriteAttempt` y la métrica sube: la escritura del mock se rechaza siempre (plan §4, AUTONOMIA-03);
    - (de esta tarea) `POST` con un cuerpo inválido o vacío y un token válido → 403, no 422: la autorización va antes que la validación del cuerpo;
    - (de esta tarea) `CreditReader` de U08-T03 (`vectra_case.credit`) contra la app real del mock, en proceso → `aprobado` para un `id` del fixture y `sin_credito` para uno ausente.

- [ ] **Paso 18 — Resumen de los servicios** (E\*F)
  - Cobertura de ramas ≥ 95 % en `vectra_case` y **100 %** en `case_fsm`, `backoff`, `decision`, `views`, `intake`, `evidence`, `evaluation`, `sweeps` ~~y `retention`~~ **(umbral de `retention` diferido por la demo: enmienda §3, U8, fila «18 Resumen»: «Sin el umbral de `retention`»)**.
  - PBT-U8-01..~~08~~07 con el perfil `ci` (500 ejemplos, semilla impresa). ~~PBT-U8-08~~ **(diferida con su código: enmienda §3, U8, fila «16», y §5.2: «Se difieren con su código: … PBT-U8-08»)**.
  - Resúmenes en `aidlc-docs/construction/case-management/code/services.md` y `code/database.md`.
  - Diseño: NFR-U8-50, 52.
  - **Aceptación**: `uv run pytest case-management/tests --cov=vectra_case --cov-branch --cov-fail-under=95` y el umbral por módulo (100 % en los ~~nueve~~ ocho de NFR-U8-50 que entran).

### Precisiones

- **Estructura de §1 que toca esta tarea.** Todo existe ya como esqueleto de U08-T01; se llena en su sitio:
  - `case-management/src/vectra_case/governance_client.py` (se amplía), `job_queue.py`, `evaluation.py` y `worker.py` (hoy son una línea de docstring cada uno);
  - `case-management/core_banking_mock/src/core_banking_mock/app.py`, `auth.py` y `metrics.py` (hoy vacíos);
  - `case-management/core_banking_mock/fixtures/credits.json` (hoy solo hay `.gitkeep`);
  - `case-management/core_banking_mock/tests/` (hoy solo `.gitkeep`);
  - `case-management/tests/integration/test_worker_clients.py`, `test_worker.py` y `test_worker_shutdown.py`; `case-management/tests/property/test_evaluation.py` y `test_case_machine.py`; los dobles nuevos en `case-management/tests/doubles/`;
  - `aidlc-docs/construction/case-management/code/database.md` (**no existe**; ninguna tarea anterior lo creó) y `code/services.md` (se completa).

  Los docstrings de los esqueletos dicen «Paso 14» para `evaluation` y `job_queue`; el plan los pone en el Paso 15. Se corrigen al llenarlos. **No** se crean `Dockerfile`, plantillas del chart, reglas, runbooks, `docs/` ni `tools/check_openapi.py` (U08-T05).
- **Rutas de la aceptación.** El plan escribe algunas rutas relativas a `case-management/`. Los comandos de esta tarea usan la ruta completa desde `vectra-risk/`.
- **Roles de base.** El worker corre con `case_worker`, nunca con superusuario; el reconciliador de las pruebas, con `case_app`. Los grants de U08-T01 no cambian: `case_worker` tiene `SELECT` sobre `cases` y `case_identifiers`; `UPDATE (state, attempts, last_cause, recommendation, recommendation_entry_id, escalation_count, ever_degraded, updated_at)` sobre `cases`; `SELECT, UPDATE, DELETE` sobre `evaluation_jobs`; e `INSERT` sin `SELECT` sobre `evidence_outbox`, solo `fail_closed` (RLS). Si una prueba necesita un permiso que la migración no da, se reporta como hallazgo; no se cambia la migración.
- **`last_cause` en la reprogramación.** `evaluation_jobs` no tiene columna `last_cause` (domain-entities §2.1; migración 0001). La frase del plan «la reprogramación solo fija `run_at`, `last_cause` y `locked_until = NULL`» se lee así: `run_at` y `locked_until = NULL` en `evaluation_jobs`, y `last_cause` en `cases`, en la misma transacción que el cambio de estado. `attempt` no se toca: sube en la toma siguiente (BR-U8-07).
- **El trabajo se borra al terminar** (candidata F-02 de U08-T01, `CANDIDATAS.md`; P-2 (a) de U08-T03). El worker borra la fila de `evaluation_jobs` al pasar a `listo`, a `modelo_congelado` y a `no_disponible`, en la misma transacción. Así el `INSERT` simple de `retry` y del barrido no choca con el índice único. Se precisa en `functional-design/domain-entities.md` §2.1 (una fila: «la fila se borra al salir de `en_evaluacion`/`en_sincronizacion`») y se cierra la candidata.
- **Reloj inyectado.** `run_at`, `locked_until`, `escalated_at` y el backoff salen de un reloj inyectado y viajan como parámetros de las consultas, no de `now()` de la base, igual que en `evidence.py` (U08-T03). Así «con reloj simulado» y «tras 30 s» no esperan tiempo real, y PBT-U8-01 puede saltar horas y años. Las líneas que miden tiempo de pared siguen con reloj real: toma en ≤ 600 ms, < 50 ms con el circuito abierto, `serving-config` < 50 ms con scoring lento, 16 trabajos con un pool de 5 y el `SIGTERM`.
- **Clientes (Paso 14).**
  - `ServingConfigClient` hoy fija el pool en `GOVERNANCE_SERVICE_POOL` (2). El worker usa `GOVERNANCE_WORKER_POOL` (4): el pool pasa a ser un parámetro, sin duplicar la clase. `case-service` sigue con 2.
  - `feature_spec`: `GET /v1/models/{id}/feature-spec`, `FEATURE_SPEC_TIMEOUT` (1 s), validado con `FeatureSpec` de U0; caché sin expiración por `model_version_id`, LRU de 4. Comparte el `DependencyClient` de governance (un pool y un breaker por dependencia, P-U8-02).
  - Scoring: `POST /v1/recommendations`, `SCORING_POOL` (16), `SCORING_TIMEOUT` (7 s), respuesta validada con `RecommendResult`. Vive en el módulo que el codificador elija entre `evaluation.py` y `governance_client.py`; si crea un módulo nuevo, lo justifica en `services.md`, porque §1 no lo nombra.
  - Tokens del cliente `case-worker` (`identity-edge/keycloak/realm/realm.*.yaml`): audiencia `scoring-service` con `case:recommend`; audiencia `governance-service` con `governance:read-serving` y `governance:read-feature-spec`. Un `provider_from_env` por audiencia.
  - El reintento por 401 ya lo hace `deps.call` (invalida el token y repite una vez). `evaluation` no añade otro. Un segundo 401 llega como respuesta 401 y se trata como «otro 4xx»: `scoring_rejected`.
  - `httpx.Timeout` de `deps` limita cada fase, no la llamada entera (`CANDIDATAS.md`, «U0, `deps._send`»). Cada llamada del worker lleva además un tope duro con `asyncio.timeout`, como `credit.py`, para que `WORKER_WORST_CASE` (15,5 s) < `LEASE` (30 s) sea cierto.
  - «Scoring doble de 7 s»: el doble retiene la respuesta hasta `SCORING_TIMEOUT`. Lo que miden esas dos líneas es el aislamiento de pools y de conexiones, no el resultado del intento, que puede ser un timeout.
- **`evaluation` (Paso 15).**
  - La construcción del `ScoringRequest` es una función sin E/S dentro de `evaluation` (recibe la fila del caso, los identificadores, el `FeatureSpec`, el intento y la versión). PBT-U8-05 la prueba sin base. `derive` necesita la solicitud completa: `cases.application` más `case_identifiers`.
  - `ScoringRequest` de U0 exige `received_at` y `first_evaluation`. El diagrama de business-logic-model §3.1 no los muestra: está atrasado; rigen BR-U8-06 y el modelo de U0.
  - Cada cambio de estado pasa por `case_fsm.transition` y lleva la guarda `WHERE state IN (…) AND attempts = :attempt`. Los triggers de U08-T01 son la segunda defensa.
  - Cada `UPDATE` sobre `cases` fija `updated_at` (P-4 (a) de U08-T03: `PersistentFailure.since` sale de ahí).
  - `result` de `vectra_case_attempts_total` ∈ {`recommendation`, `failclosed`, `model_frozen`, `scoring_unreachable`, `serving_config_unavailable`, `scoring_rejected`} y `attempt` de 1 a 6; ya está declarada en `metrics.py` (U08-T03). Se añade `vectra_case_time_to_ready_seconds`, sin etiquetas, de `created_at` a `listo`, solo si el caso llegó a `listo` en el intento 1 y `ever_degraded = false`.
  - El gauge de «6 fallos → gauge = 1» es `vectra_cases_failclosed_persistent`, que calcula `DbGauges` de `case-service`. La prueba corre un ciclo de `DbGauges` después del escalamiento. `FailClosedPersistente` es de U1 y no se prueba aquí.
  - La entrada `fail_closed` se inserta con la forma que fijó U08-T03 (`code/services.md`, «Contrato entre `case-service` y `case-worker` sobre el outbox»): `payload` es la entrada completa del registro, con un `FailClosedPayload` de U0 dentro.
- **`worker` (Paso 15).** `python -m vectra_case.worker`: lee su configuración del entorno (`CASE_DB_DSN` con el rol `case_worker`, `CASE_GOVERNANCE_URL`, `CASE_SCORING_URL` y las de U0 para el token), sirve solo las sondas y `/metrics` en 8081 con `ops_server.create_ops_app` (readiness solo con `case-db`), y arranca el bucle. No expone 8080. Si a `ops_server` le falta algo para un proceso sin app HTTP, se reporta como candidata de U0; no se cambia U0. Las variables de entorno quedan en `services.md`, para el chart de U08-T05.
- **`core-banking-mock` (Paso 17).**
  - `create_app("core-banking-mock", handlers=…)` con las 2 rutas de `REGISTRY["core-banking-mock"]` y `authenticator_from_env("core-banking-mock")`; arranque con `ops_server.run_service` (8080 y 8081). No importa `vectra_case`.
  - Fixtures: `core_banking_mock/fixtures/credits.json`, con la entidad `Credit` de domain-entities §5 (`case_id`, `status`, `updated_at`), al menos un crédito por cada uno de los cinco estados del core (`en_estudio`, `aprobado`, `desembolsado`, `rechazado`, `cancelado`). La ruta por omisión es `/app/fixtures/credits.json` (INF-U8-02); las pruebas pasan la del repositorio. Copiarlo a la imagen es del Paso 19.
  - Como nadie tiene `core:write-credit`, el 403 lo emite la autorización de U0 antes del handler. El conteo y el `WriteAttempt` cuelgan de la denegación de esa ruta, no del handler; el handler, si llegara a ejecutarse, también rechaza y cuenta. Ver P-4.
  - `vectra_core_write_attempts_total` no lleva etiquetas y se crea en 0 al importar `core_banking_mock.metrics`.
- **PBT-U8-01** (`tests/property/test_case_machine.py`). `RuleBasedStateMachine` contra PostgreSQL real, con el arnés de `u8_support.harness`, los dobles de governance, scoring y registro, y el reloj simulado, como hizo U08-T03 con PBT-U8-07. Entra **entera**, con todos los eventos e invariantes de business-logic-model §4:
  - comandos: resultado de scoring de cada tipo (`Recommendation`, `FailClosed` con las 10 causas, fallo de transporte, 5xx, 401 y otros 4xx), congelar y descongelar (barrido), `retry`, decisión con y sin ack, ciclo del reconciliador, abandono a las 24 h, vencimiento de la retención, `worker_lost` y `late_result`; secuencias de 1 a 50 comandos;
  - invariantes: estado alcanzable por BR-U8-12; `listo` nunca recibe otro intento; `decidido` y `vencido` terminales; como máximo una decisión `confirmada`; un 4xx distinto de 401 escala de inmediato; el 401 no cuenta como intento; un resultado tardío nunca modifica el caso; la marca `model_frozen_after_recommendation` ⇔ versión `congelado` en el último barrido; exactamente un trabajo vivo en `en_evaluacion` y `en_sincronizacion`; `attempts ≤ 6`; toda toma incrementa; la retoma con `attempt = 6` escala sin incrementar.

  El modelo de referencia es un dato de la prueba (tabla de BR-U8-12 y contadores), no una llamada a `evaluation`. El vencimiento depende de código diferido: ver P-5.
- **Cobertura (Paso 18).**
  - En `main` hoy: total 87 %, `evidence.py` 89 %, `sweeps.py` 83 %, `api.py` 90 %, `db.py` 77 %, `app.py` 57 % (`bitacoras/U08-T03.md`, «Cobertura medida»). Esta tarea sube `evidence` y `sweeps` al 100 % y el total al 95 %, con pruebas. No se cambia su comportamiento; una rama inalcanzable se quita, o lleva `# pragma: no cover` con su razón en `services.md`.
  - `app.py` queda en 57 % porque `main()` corre en un subproceso que `coverage` no mide. Lo mismo le pasará a `worker.py`. Se mide el subproceso (`coverage` 7.17 admite `patch = subprocess` y `sigterm = true` en `coveragerc`) o se cubre `main` en proceso. Está **prohibido** llegar al umbral con `omit` o excluyendo archivos de `source`.
  - `make -C case-management check` hace cumplir los dos umbrales: 95 % en `vectra_case` y 100 % en los ocho módulos. Hoy solo exige los cuatro puros (`COV_PURE`).
  - `retention.py` sigue con la purga de U08-T03 y sin umbral propio.
- **Semilla impresa (NFR-U8-52).** `case-management/tests/conftest.py` solo imprime la semilla cuando una prueba falla (`print_blob`). Se fija y se imprime en el encabezado de pytest también en verde, como `scoring-explainability/tests/conftest.py` (`CANDIDATAS.md`, «Todas las unidades (revisor, U07-T02): imprimir la semilla de Hypothesis también en las corridas verdes»).
- **Documentación.**
  - `code/services.md`: una sección «Bloques E y F (U08-T04)» (módulos, decisiones P-1 a P-5 escritas como «U08-T04 P-1» … «U08-T04 P-5», porque el archivo ya tiene las P-1 a P-4 de U08-T03; variables de entorno del worker y del mock, la expresión de `vectra_case_first_attempt_failure_ratio`, los diferidos). Además, dos notas que el revisor de U08-T03 pidió documentar ahí (`CANDIDATAS.md`): qué cubre y qué no la cifra de `RECONCILER_LEASE` (F-01 de la ronda 2) y el envío inmediato que queda arrendado 125 s si se interrumpe (F-02 de la ronda 2). Solo texto: `evidence.py` no cambia por ellas.
  - `code/database.md`: resumen de la base tal como está en `main` (tablas, índices únicos, grants por rol, RLS, triggers y `case_transitions`), con la ruta de cada migración. No se cambia ninguna migración.
- **Plan.** Marca `[x]` los Pasos 14, 15, 17 y 18 con `(U08-T04)`. En el Paso 18, añade «umbral de `retention` y PBT-U8-08 diferidos por la demo». El Paso 16 queda `[ ]`.
- **Bitácora.** `bitacoras/U08-T04.md` lleva la salida **real** de cada comando, pegada como texto, con rutas absolutas a los logs largos, la semilla de cada corrida con Hypothesis y sin plantillas sin expandir.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Paso 16, la CLI `case-retention`**, con PBT-U8-08, la corrida de P-U8-07 y las tres métricas de retención. Enmienda §3, U8, fila «16 `case-retention`»: «D · D · Con PBT-U8-08»; §5.2. De `retention.py` solo existe la purga de `intake_keys` (U08-T03) y no se amplía.
- **El umbral de cobertura de `retention`** del Paso 18 (enmienda §3, U8, fila «18 Resumen»: «Sin el umbral de `retention`»).
- **`mutmut`** (NFR-U8-51; T3, enmienda §2 regla 3).
- **Bloque G y el cierre (U08-T05, Pasos 19 a 23, 25 y 26):** Dockerfiles y la copia del fixture a la imagen; chart, values y `terminationGracePeriodSeconds`; el Job `rt5-demo`; alertas y runbooks, incluidas `ScoringRequestRejected`, `CaseFirstAttemptFailureHigh` con su regla de grabación, `CaseJobsOverdue` y `CoreWriteAttempt`; `docs/api.md` y `tools/check_openapi.py`; Applications; k6; `evidence/cierre-demo.md` con la lista «Diferido por la demo».
- **Candidatas de `CANDIDATAS.md` que son de U08-T05**, no de esta tarea:
  - «U4/U7/U8, orden de despliegue» (revisor, U04-T09), en su parte de despliegue: wave, imágenes del mismo commit y digests en un solo PR. Aquí solo se cierra el lado del código (el worker falla cerrado con la forma vieja);
  - «U8, apagado (revisor, U08-T03)»: alinear `terminationGracePeriodSeconds` con `RECONCILER_LEASE`;
  - «U7, diseño (codificador, U07-T04)»: `/livez` frente a `/healthz` en el chart; el diseño de U8 lo repite (INF-U8-04);
  - «U6/U9 … `crd_to_schema.py`» y «Plantilla de tareas de despliegue … `EXPECTED_WAVES`».
- **El Paso 24** (kind): consolidado en U12 Paso 18 (enmienda §8).
- **Cambios a las migraciones de U08-T01** y a sus pruebas: las candidatas F-01 (`guard_vencido`) y F-03 (`retention_runs.finished_at`) de U08-T01, y F-04 de U08-T03 (`evidence_outbox.created_at` al reabrir una consulta).
- **Cambios a U0** (`vectra_contracts`, `vectra_common`): `deps._send` y el timeout por fase, los puertos fijos de `ops_server`, un `LogEvent` nuevo para el `WriteAttempt`, la convención de `principal_role`. Se reportan; no se corrigen aquí.
- **Cambios de comportamiento en `case-service`** (`intake`, `evidence`, `sweeps`, `api`, `credit`). Solo se le añaden pruebas para la cobertura y el parámetro de pool de `ServingConfigClient`.
- **Las candidatas de PBT de U08-T02** (F-02 `make_row`, F-03 jitter) y BR-U8-16 (qué código gana): no son de este bloque.
- **El realm de U2** (casos de PBT-10 sobre `core:read-credit`, decisión H7).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (§1 «Estructura de destino», Bloques E y F, §3, §4)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1.0, §1.1, §1.3, §2, §3 U8, §4, §5.2, §8)
- `aidlc-docs/construction/case-management/functional-design/business-rules.md` (BR-U8-05..09, 12, 21, 22)
- `aidlc-docs/construction/case-management/functional-design/business-logic-model.md` (§3.1; §4, PBT-U8-01 y 05; los ejemplos)
- `aidlc-docs/construction/case-management/functional-design/domain-entities.md` (§2.1, §2.2, §3, §5)
- `aidlc-docs/construction/case-management/nfr-requirements/nfr-requirements.md` (NFR-U8-02, 03, 04, 11, 15, 24, 26, 30..34, 45, 50, 52)
- `aidlc-docs/construction/case-management/nfr-design/nfr-design-patterns.md` (P-U8-01, 02, 06, 08, 09) y `logical-components.md` (§1, tablas y roles)
- `aidlc-docs/construction/case-management/infrastructure-design/infrastructure-design.md` (INF-U8-01, 02, 03, 06, 07)
- `aidlc-docs/construction/case-management/code/services.md` y `code/logic.md` (U08-T03 y U08-T02)
- `case-management/src/vectra_case/{config,metrics,db,governance_client,case_fsm,backoff,evidence,sweeps,credit,app}.py`
- `case-management/migrations/versions/0001_case_schema.py`, `0002_grants_and_rls.py` y `0003_guards.py`
- `case-management/tests/doubles/{u8_support,registry_double,case_strategies}.py`, `case-management/tests/property/test_evidence.py` (modelo de PBT stateful con base) y `case-management/tests/integration/test_service_shutdown.py` (modelo de arranque real)
- `case-management/Makefile`, `pytest.ini`, `coveragerc` y `.importlinter`
- `contracts/python/vectra_contracts/src/vectra_contracts/models/api.py` (`ScoringRequest`, `CreditStatusView`), `models/features.py` (`FeatureSpec`), `models/registry.py` (`FailClosedPayload`), `outcome/__init__.py` (`RecommendResult`), `labels.py` (`derive`, `derive_monitoring_labels`), `catalog.py` (`Scope`, `LocalCause`, `LogEvent`, `CreditStatus`) y `routes/__init__.py` (`_scoring()`, `_core()`, la ruta de `feature-spec`)
- `contracts/python/vectra_common/src/vectra_common/` (`deps`, `service_token`, `ops_server`, `app_factory`, `authn`, `logging`, `metrics`)
- `scoring-explainability/tests/conftest.py` (semilla impresa en el encabezado)
- `identity-edge/keycloak/realm/realm.kind.yaml` (cliente `case-worker`; scope `core:read-credit` y audiencia `core-banking-mock`)
- `platform/network/flows.yaml` (F15, F17, F40, F50, F104)
- `bitacoras/U08-T03.md` («Cobertura medida», «Candidatas») y `revisiones/U08-T03/` (rondas 1 y 2)
- `DECISIONES-LOOP.md` §6 y `CANDIDATAS.md` (las entradas citadas en esta tarea)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`, en serie, anotando `uptime` antes y después de cada uno. Estado sobre `main` al redactar la tarea (`fdff2a9`): CA-1, CA-2 y CA-3 terminan con código 4 (`ERROR: file or directory not found`); CA-4 termina con código 5 (`no tests collected`) y un `ImportError`; CA-5 imprime líneas `FALTA`; CA-6 no imprime el encabezado y el total medido es 87 %; CA-8 se corta en el primer `grep` (no hay sección de U08-T04 en `services.md`, ni `database.md`, ni los pasos en `[x]`); CA-10 lista 10 identificadores de los pasos de esta tarea. Ese es el rojo esperado. CA-7 hoy pasa (4 contratos `KEPT`) salvo por el `grep` de los esqueletos.

- [ ] **CA-1** — Clientes y caché de gobierno (Paso 14; BR-U8-05; P-U8-02, 09; NFR-U8-15, 30..33).
  ```bash
  uv run pytest case-management/tests/integration/test_worker_clients.py -v
  ```
  Esperado: código 0, con un caso por cada línea de aceptación del Paso 14, incluidas las tres de esta tarea. **Rojo primero:** contar un 422 como fallo del breaker hace fallar «20 respuestas 422 → circuito cerrado»; una LRU de 5 hace fallar «5 versiones → se descarta la menos usada». Regístralo.

- [ ] **CA-2** — PBT-U8-05 y PBT-U8-01, enteras (Paso 15; BR-U8-05..09, 12; US-109, US-112).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evaluation.py case-management/tests/property/test_case_machine.py -v
  ```
  Esperado: código 0; el encabezado muestra `hypothesis profile: ci` y la semilla; PBT-U8-05 con sus dos afirmaciones; PBT-U8-01 con todos los comandos e invariantes de las Precisiones. La bitácora anota cuántas veces la máquina recorrió `worker_lost` seis veces seguidas, `late_result` tras un vencimiento y decisión tras abandono (un contador como `STATS` de `test_evidence.py`): un comando que nunca se ejecuta no prueba nada (F-02 de la ronda 1 de U08-T03). **Rojo primero:** quitar `AND attempts = :attempt` de la guarda hace fallar PBT-U8-01 con `late_result`; incluir `free_text` en el `ScoringRequest` hace fallar PBT-U8-05. Regístralo.

- [ ] **CA-3** — Cola, evaluación, escalamiento y apagado (Paso 15; P-U8-01, 08, 09; INF-U8-06; NFR-U8-02, 03, 04, 11, 24).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/integration/test_worker.py case-management/tests/integration/test_worker_shutdown.py -v
  ```
  Esperado: código 0, con un caso por cada línea de aceptación del Paso 15 que no es PBT, incluidas las de esta tarea. Cada caso que cambia estado afirma sobre la **lectura de vuelta** con el rol de la prueba, no sobre el valor que devolvió la función: `SELECT state, attempts, last_cause, ever_degraded, escalation_count FROM cases`, `SELECT count(*) FROM evaluation_jobs WHERE case_id = …` y `SELECT entry_type, idempotency_key, payload FROM evidence_outbox`. La prueba del `SIGTERM` lanza `python -m vectra_case.worker` como proceso (no `runpy`; el revisor de U04-T09 marcó ese desvío) y lee el caso `listo` de la base después de que el proceso termina. **Rojo primero:** escribir `attempt + 1` sin mirar el valor leído hace fallar «worker perdido en el intento 6» con la violación del `CHECK`; no poner `ever_degraded = true` hace fallar la línea de `first_evaluation`. Regístralo.

- [ ] **CA-4** — `core-banking-mock` (Paso 17; BR-U8-22; INF-U8-02, 03; P-U8-06; NFR-U8-26, 45; US-603).
  ```bash
  uv run pytest case-management/core_banking_mock/tests -v && uv run python -c "from core_banking_mock.app import build_app; build_app(); from vectra_contracts.routes import REGISTRY; assert len(REGISTRY['core-banking-mock']) == 2; print('OK')"
  ```
  Esperado: código 0, con un caso por cada línea de aceptación del Paso 17, incluidas las cuatro de esta tarea, y `OK` al final (`create_app` falla si falta o sobra un handler). La métrica se lee de `GET /metrics` del puerto de sondas, no de la variable del módulo. Si el punto de entrada no se llama `build_app`, el comando se ajusta al nombre real y se anota. **Rojo primero:** crear el contador sin inicializarlo hace fallar «recién iniciado → 0»; contar en el handler y no en la denegación deja la métrica en 0 tras el `POST`. Regístralo. Hoy: `no tests collected`, código 5.

- [ ] **CA-5** — Estructura de §1 que toca esta tarea, sin esqueletos vacíos.
  ```bash
  cd case-management && for p in src/vectra_case/governance_client.py src/vectra_case/job_queue.py src/vectra_case/evaluation.py src/vectra_case/worker.py core_banking_mock/src/core_banking_mock/app.py core_banking_mock/src/core_banking_mock/auth.py core_banking_mock/src/core_banking_mock/metrics.py core_banking_mock/fixtures/credits.json tests/integration/test_worker_clients.py tests/integration/test_worker.py tests/integration/test_worker_shutdown.py tests/property/test_evaluation.py tests/property/test_case_machine.py ../aidlc-docs/construction/case-management/code/services.md ../aidlc-docs/construction/case-management/code/database.md; do test -s "$p" || echo "FALTA $p"; done; ! grep -rln "Modulo vacio del esqueleto" src core_banking_mock/src && ! find tests core_banking_mock/tests -name __init__.py | grep -q . && uv run python -c "import json; d = json.load(open('core_banking_mock/fixtures/credits.json')); print('fixture OK', len(d))"
  ```
  Esperado: ninguna línea `FALTA`, el `grep` sin salida y `fixture OK` con al menos 5 créditos. Hoy: 7 líneas `FALTA` (el fixture, las cinco pruebas y `database.md`) y el `grep` lista seis módulos.

- [ ] **CA-6** — Cobertura y semilla (Paso 18; NFR-U8-50, 52).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property --collect-only | grep -n "hypothesis profile: ci, seed:"
  uv run pytest case-management/tests --cov=vectra_case --cov-branch --cov-fail-under=95
  uv run coverage report --rcfile=case-management/coveragerc --fail-under=100 --include='*/vectra_case/case_fsm.py,*/vectra_case/backoff.py,*/vectra_case/decision.py,*/vectra_case/views.py,*/vectra_case/intake.py,*/vectra_case/evidence.py,*/vectra_case/evaluation.py,*/vectra_case/sweeps.py'
  ```
  Esperado: la primera orden imprime una línea con el perfil y la semilla; la segunda termina en 0 con `TOTAL` ≥ 95 % sobre `vectra_case` (no sobre U0); la tercera, que lee el `.coverage` de la segunda, termina en 0 con los ocho módulos al 100 %. Hoy: la primera no imprime nada y el total es 87 %.

- [ ] **CA-7** — Contratos de import-linter.
  ```bash
  uv run lint-imports --config case-management/.importlinter && ! grep -rnE "^\s*(import|from) (httpx|vectra_case)" case-management/core_banking_mock/src --include='*.py' && ! grep -rn "_internal\|_minting\|CONSTRUCTION_TOKEN" case-management/src case-management/core_banking_mock/src --include='*.py'
  ```
  Esperado: código 0, con los contratos `KEPT` (los 4 de hoy, y los que la tarea añada), y los dos `grep` sin salida: el mock no importa `httpx` ni `vectra_case`, y nadie importa el token privado.

- [ ] **CA-8** — Documentación y plan.
  ```bash
  grep -n "Bloques E y F (U08-T04)" aidlc-docs/construction/case-management/code/services.md && grep -c "U08-T04 P-[1-5]" aidlc-docs/construction/case-management/code/services.md && grep -n "first_attempt_failure_ratio" aidlc-docs/construction/case-management/code/services.md && grep -n "CASE_SCORING_URL" aidlc-docs/construction/case-management/code/services.md && grep -nE "case_transitions|worker_fail_closed_only|guard_ever_degraded" aidlc-docs/construction/case-management/code/database.md && grep -n "se borra" aidlc-docs/construction/case-management/functional-design/domain-entities.md && grep -nE "^- \[x\] \*\*Paso (14|15|17|18) " aidlc-docs/construction/plans/case-management-code-generation-plan.md && grep -nE "^- \[ \] \*\*Paso 16 " aidlc-docs/construction/plans/case-management-code-generation-plan.md
  ```
  Esperado: `services.md` tiene la sección «Bloques E y F (U08-T04)», nombra las cinco preguntas con la opción que rigió (el conteo es ≥ 5), la expresión de la razón y las variables del worker; `database.md` existe y nombra las tablas, la política RLS y los triggers; domain-entities §2.1 dice que la fila se borra; salen cuatro líneas del plan con `(U08-T04)`, la del 18 con la nota de los diferidos; el Paso 16 sigue `[ ]`. Además, `git diff origin/main -- aidlc-docs/construction/plans/case-management-code-generation-plan.md | grep -E "^[-+]- \["` muestra solo esos cuatro pasos.

- [ ] **CA-9** — `check` de la unidad (RL-4).
  ```bash
  make -C case-management check
  ```
  Esperado: código 0. Incluye lint, mypy estricto sobre `vectra_case` y `core_banking_mock`, import-linter, todas las pruebas con el perfil `ci` (migraciones, unitarias, propiedades, integración y las del mock) y los dos umbrales de cobertura del Paso 18. **Rojo primero:** con una prueba de `sweeps` desactivada, el `check` termina distinto de 0 por el umbral del 100 %; regístralo. La bitácora anota la duración; si pasa de 30 minutos sin carga, se anota como candidata. Esta tarea no toca U0 ni U1: no hace falta `make -C contracts check` ni `make -C platform check`.

- [ ] **CA-10** — Trazabilidad «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit case-management --all | grep -E "^(BR-U8-(05|06|07|08|09|12|22)|P-U8-0[12689]|INF-U8-0[236]|NFR-U8-(02|03|04|11|15|24|26|30|31|32|33|45|50|52)):"
  uv run python platform/tests/test_traceability.py --all | grep "sin trazabilidad" | sort
  ```
  Esperado: la primera orden no imprime nada: cada identificador que citan los Pasos 14, 15, 17 y 18 queda trazado. Hoy imprime 10: INF-U8-03, NFR-U8-02, 03, 11, 26, 32, 33, 45, 52 y P-U8-08. La segunda orden, comparada con la misma corrida sobre la base de la rama, no trae ningún identificador nuevo. Hoy la base tiene 67 líneas (43 de U10 y 24 de U8); de U8 deben quedar como mucho las 14 de pasos que esta tarea no cubre: INF-U8-05 y 08; NFR-U8-10, 12, 14, 20, 34, 40, 42, 44, 46, 47 y 51; P-U8-07. U8 no tiene `evidence/cierre-demo.md`, así que esas 14 no bloquean; el revisor corre `--all` en la base y en la rama y cruza cada línea.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/integration/test_worker_clients.py`: las líneas del Paso 14.
- `tests/property/test_evaluation.py`: PBT-U8-05, con el generador de `ApplicationIn` de `tests/doubles/case_strategies.py` (PII y texto libre adversarial) y `FeatureSpec` con búsquedas.
- `tests/property/test_case_machine.py`: PBT-U8-01 (`RuleBasedStateMachine`), con contadores de recorrido.
- `tests/integration/test_worker.py`: las líneas del Paso 15 que no son PBT ni apagado.
- `tests/integration/test_worker_shutdown.py`: el `SIGTERM` y el arranque real de `python -m vectra_case.worker`.
- `tests/doubles/`: doble de scoring (resultados por caso e intento, latencia, 401, 4xx, 5xx, `version_mismatch`; guarda cada `ScoringRequest` recibido) y `feature-spec` en el doble de governance. Si el doble de scoring necesita construir una `Recommendation`, usa `recommendation_from_wire` de `case_strategies.py`, nunca el token privado.
- `core_banking_mock/tests/`: las líneas del Paso 17, con un `Authenticator` de prueba y llaves generadas en la prueba; ninguna toca Keycloak.
- Pruebas añadidas a `tests/integration/` para llevar `evidence` y `sweeps` al 100 % y el total al 95 %.
- `tests/conftest.py`: la semilla fija e impresa en el encabezado.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U08-T04.md`, con la salida pegada. Como mínimo los de CA-1, CA-2, CA-3, CA-4 y CA-9. El par falla-pasa es la prueba.

Sin `__init__.py` en `tests/` ni en `core_banking_mock/tests/` (`CANDIDATAS.md`, «Todas las unidades, paquetes de prueba», F-06 de U07-T03): `case-management/pytest.ini` ya usa `--import-mode=importlib`. Los módulos de apoyo van en `tests/doubles/`, que ya está en `pythonpath`.

---

## Preguntas abiertas

Si no hay respuesta, rige la recomendación. P-1 y P-2 cambian texto del diseño o una línea de aceptación del plan: conviene que el usuario las confirme antes del despacho. P-3, P-4 y P-5 tienen una opción por omisión que no cambia el diseño.

- **P-1 — Escalar desde `en_evaluacion` cuando se pierde el intento 6.** BR-U8-07 y el Paso 15 mandan que una retoma con `attempt = 6` escale a `no_disponible`. Pero la tabla de BR-U8-12, y con ella `case_fsm.TRANSITIONS` (U08-T02), solo admite «Fallo del intento 6» desde `en_sincronizacion`. Un caso cuyo worker se pierde en los seis intentos, o que falla el intento 6 sin haber aplicado ningún resultado antes, sigue en `en_evaluacion`: `case_fsm.transition(en_evaluacion, attempt_6_failed)` devuelve `Rechazo`. PBT-U8-01 lo encuentra con seis `worker_lost` seguidos. La base sí lo permite: `case_transitions` tiene (`en_evaluacion`, `no_disponible`, `case_worker`).
  - **(a) Recomendada:** añadir la fila (`en_evaluacion`, `attempt_6_failed`) → `no_disponible` a `case_fsm.TRANSITIONS` y a su prueba unitaria, y precisar la fila de BR-U8-12 («`en_evaluacion`, `en_sincronizacion` | Fallo del intento 6»). La prueba que compara `case_fsm` con `case_transitions` sigue en verde, porque el par de estados ya existe. No toca la migración.
  - (b) Pasar por `en_sincronizacion` y a `no_disponible` en la misma transacción (dos `UPDATE`). No toca `case_fsm`, pero escribe un estado que nadie ve.
  - (c) Dejar el caso en `en_evaluacion` con el trabajo borrado. Rompe «exactamente un trabajo vivo» de PBT-U8-01; no se recomienda.
- **P-2 — El `SIGTERM` con un scoring «que responde a los 10 s».** La línea del Paso 15 (y la verificación de INF-U8-06) espera que el intento termine y el caso quede `listo`. Con `SCORING_TIMEOUT` = 7 s (NFR-U8-30, `config.py`), una respuesta a los 10 s nunca llega: el intento termina a los 7 s como `scoring_unreachable` y el caso queda `en_sincronizacion`.
  - **(a) Recomendada:** el doble responde a los **5 s** (dentro del timeout y muy por encima de los 0,5 s del `SIGTERM`). Se prueba lo que la línea quiere probar: el worker deja de sondear, espera la llamada en vuelo y el caso queda `listo`. Se añade un segundo caso con el doble a los 10 s: el intento termina a los 7 s como `scoring_unreachable`, el trabajo queda reprogramado y sin arrendamiento, y el proceso sale antes de los 20 s. Se anota en el plan y se propone corregir INF-U8-06 como candidata.
  - (b) Mantener los 10 s e inyectar un timeout de scoring mayor solo en esa prueba. La prueba dejaría de usar la configuración real.
  - (c) Mantener los 10 s y cambiar lo esperado a `en_sincronizacion`. Deja sin probar que un intento en vuelo se entrega durante el apagado.
- **P-3 — `vectra_case_first_attempt_failure_ratio` sin su regla de grabación.** La línea del Paso 15 mide esa razón, pero P-U8-08 la define como una regla de grabación sobre `vectra_case_attempts_total{attempt="1"}`, y las reglas son del Paso 21 (U08-T05).
  - **(a) Recomendada:** la prueba calcula la razón desde los contadores del proceso, con la definición de NFR-U8-03 (intentos 1 que no terminaron en `recommendation` / intentos 1), sobre al menos 200 casos y con semilla fija. La expresión PromQL equivalente queda escrita en `services.md`, para que U08-T05 la copie en la regla y la pruebe con `promtool`.
  - (b) Adelantar la regla de grabación y su prueba de `promtool` a esta tarea. Abre `observability/rules/` antes del Paso 21.
- **P-4 — El `WriteAttempt` «en el log» sin un evento en el catálogo de U0.** `vectra_common.logging.log_event` solo acepta un `LogEvent`, y el catálogo no tiene ninguno para el intento de escritura. Además, el 403 lo emite la autorización de U0 antes del handler.
  - **(a) Recomendada:** el `WriteAttempt` es el registro `authz.denied` que U0 ya emite en ese 403, con `http_method = POST`, `route_template = /v1/credits/{id}/status` y `principal_subject` (la `source_identity` de domain-entities §5), más el incremento de `vectra_core_write_attempts_total`, que el mock engancha a la denegación de esa ruta. La prueba afirma exactamente un registro con esos campos y la métrica en 1. Un 401 en esa ruta (sin token o con firma inválida) no cuenta como `WriteAttempt`, porque no hay identidad que registrar; queda en `vectra_authz_denied_total`. No cambia U0.
  - (b) Añadir `core.write_attempt` a `LogEvent` (U0). Cambia el catálogo y sus pruebas: otra tarea de U0.
  - (c) Escribir el registro con otro logger, fuera de la allowlist. Viola P-U0-04; no se recomienda.
- **P-5 — El comando «vencimiento de la retención» de PBT-U8-01 depende de código diferido.** La PBT entra entera (enmienda §3, fila «1–7»: «`retry` y `vencido` en `case_fsm` por PBT-U8-01»), pero quien pasa un caso a `vencido` es la corrida de `case-retention`, que está en D. La enmienda no nombra esta dependencia (§2 regla 1 pide nombrarla). La línea «resultado que llega con el caso `vencido`» tiene el mismo problema.
  - **(a) Recomendada:** el vencimiento lo aplica un apoyo de la prueba, en `tests/doubles/`, con el rol `case_retention` real: envejece `created_at` con el rol dueño, pasa el caso a `vencido` y borra su trabajo, igual que las pruebas de migraciones de U08-T01. `guard_vencido` y `guard_transition` siguen activos. No se añade código de producción a `retention.py`. Se anota en `services.md` como dependencia de PBT-U8-01 sobre el Paso 16.
  - (b) Adelantar a `retention.py` la función que vence un caso, sin CLI, como hizo P-5 de la enmienda con la purga. Mete parte del Paso 16, que el usuario difirió.

---

## Notas

- Archivos que se **modifican en su sitio**: `governance_client.py`, `job_queue.py`, `evaluation.py`, `worker.py`, `metrics.py` (el histograma) y `config.py` (solo si falta una constante; ninguna se lee del entorno, `tests/unit/test_config.py` lo vigila); los tres módulos del mock; `case_fsm.py` y `tests/unit/test_case_fsm.py` (solo con P-1 (a)); `tests/conftest.py`; `tests/doubles/u8_support.py`; `Makefile`, `coveragerc` y, si hace falta un contrato nuevo, `.importlinter`; `code/services.md`; `functional-design/domain-entities.md` §2.1 y, con P-1 (a), `business-rules.md` BR-U8-12; las casillas del plan. Nada de duplicados con sufijo.
- Archivos nuevos: las cinco pruebas, los dobles, las pruebas del mock, `fixtures/credits.json` y `code/database.md`.
- No se esperan dependencias nuevas: `pyproject.toml` y `uv.lock` no deberían cambiar. Si cambian, la bitácora dice por qué.
- **Puertos fijos.** `ops_server` usa 8080 y 8081 sin opción (`bitacoras/U08-T03.md`, candidata 2). Las pruebas de arranque real del worker, del mock y de `case-service` no pueden correr a la vez: comprueban que los puertos estén libres y fallan con un mensaje claro. No uses `pytest-xdist` en esta unidad.
- **Tras el apagado ordenado**, uvicorn vuelve a emitir `SIGTERM` y el proceso puede terminar con `-15` (`bitacoras/U08-T03.md`, candidata 3). Por eso la prueba del `SIGTERM` afirma sobre la base, no sobre el código de salida.
- **Nombres de constantes.** `LEASE`, `BACKOFF_*`, `POLL_*`, `WORKER_*` y `MAX_ATTEMPTS` de `config.py` son del worker; `RECONCILER_*` son de `case-service`. El revisor de U08-T03 (F-05) hizo quitar los duplicados: no declares constantes sueltas en los módulos.
- **PBT stateful.** Una PBT que no recorre el escenario difícil pasa en verde sin probarlo (F-02 de la ronda 1 de U08-T03: PBT-U8-07 no llegaba al abandono seguido de una decisión nueva). Fuerza los recorridos raros en parte de los ejemplos y cuenta cuántas veces ocurren.
- **Contenedores huérfanos.** Antes de cada corrida larga, revisa `docker ps --filter label=org.testcontainers` y limpia los de corridas interrumpidas (`CANDIDATAS.md`, «Loop (revisor, U03-T06, cierre)»). Una corrida completa de U8 levanta tres PostgreSQL (candidata 6 de U08-T03); no añadas un cuarto: reutiliza los fixtures de `case_pg`.
- **Máquina compartida.** Corre los criterios en serie, nunca en paralelo, con `uptime` antes y después, y una carpeta propia en el scratchpad para logs y temporales. Las líneas con tiempo de pared (< 50 ms, ≤ 600 ms) pueden fallar con carga alta: si pasa, anota la carga y repite la prueba aislada; no subas el umbral.
- PBT-U8-01..08 nunca se recortan. En esta tarea entran la 01 y la 05, enteras. La 08 está diferida con su código.
