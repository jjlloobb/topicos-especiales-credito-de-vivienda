# Plan de tareas (Code Generation Part 1) — U8 `case-management`

**Este plan es la única fuente de verdad para generar el código de U8.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U8. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U8 `case-management`: `case-service` (API, barridos, reconciliador de evidencia, lectura del core), `case-worker` (evaluación), CronJob `case-retention` y `core-banking-mock` (solo kind y staging) |
| Historias (dueña) | US-101, US-102, US-107, US-108, US-112, US-501, US-502, US-603 |
| Historias (participa) | US-109 (`free_text` tal cual con consultas parametrizadas), US-609 (HPA en su chart) |
| Ubicación | `vectra-risk/case-management/` (una imagen para los tres procesos de U8 y otra para el mock) y Applications en `vectra-risk-gitops` |
| Datos propios | `case-db` (CloudNativePG de U1): `cases`, `case_identifiers`, `intake_keys`, `evaluation_jobs`, `evidence_outbox`, `decisions`, `explanation_views`, `retention_runs`, `retention_settings`, `case_transitions` |
| Depende de | U0 (tipos, validación BR-U0-20..38, `derive`, `create_app`, `authz`, allowlist de logs, `deps` con timeout y circuit breaker), U1 (`case-db`, cuotas, `flows.yaml`, supply chain, `restore-drill`, `PostgresVolumeUsageHigh`), U2 (clientes `case-service`, `case-worker`, `channel`, `channel-simulator`; ruta de intake F04/F07), U3 (append F16 con idempotencia), U4 (`serving-config` y `feature-spec`, F104), U7 (`POST /v1/recommendations`, F15) |
| Lo consumen | api-gateway (U2, F04/F07), console-bff (U10, F10), `restore-drill` (U1, CLI de retención), U9 y U11 (vía las entradas del registro), U12 (carga, RT-1, RT-5) |

**Diseño de entrada:**
- Functional Design: `construction/case-management/functional-design/` (BR-U8-01..22 y 13b, PBT-U8-01..08).
- NFR Requirements: `construction/case-management/nfr-requirements/` (NFR-U8-01..53).
- NFR Design: `construction/case-management/nfr-design/` (P-U8-01..10).
- Infrastructure Design: `construction/case-management/infrastructure-design/` (INF-U8-01..08).

**AUTONOMIA-01:** las verificaciones estáticas, las propiedades, las pruebas de migraciones
y las pruebas de integración con dobles corren en CI. Las que necesitan el clúster las
ejecuta **un operador en kind** después de un PR aprobado (Paso 24), con la evidencia
adjunta al PR.

**Dobles hasta que existan las unidades reales:** U3, U4 y U7 ya tienen plan, así que en CI
se usan dobles HTTP que siguen sus contratos (`vectra_contracts`). El doble del registro
implementa BR-U3-05/06 y BR-U0-37 y se valida con las pruebas de append de U3 (NFR-U8-53).
Las pruebas de kind usan las unidades reales.

**Fuera de este plan** (registrado en los diseños): la presentación en la consola de
`credit_status` (`no_disponible` y `no_integrado`), de `vencido`, de `decision_already_recorded` y de
`model_frozen_after_recommendation` (U10); el Job de demostración de RT-5 y la medición del
tamaño por caso (U12); la integración con el core real del banco (Operations, INF-U8 §8).

### Estructura de destino

```text
vectra-risk/case-management/
|-- Makefile  pyproject.toml  .importlinter
|-- src/vectra_case/
|   |-- config.py
|   |-- case_fsm.py  backoff.py  decision.py  views.py                 # puros
|   |-- db.py  metrics.py
|   |-- intake.py  evidence.py  sweeps.py  credit.py  db_gauges.py  api.py  app.py   # case-service
|   |-- governance_client.py  job_queue.py  evaluation.py  worker.py                # case-worker
|   `-- retention.py                                                   # CLI de case-retention
|-- migrations/          # Alembic: tablas, roles, permisos por columna, triggers, RLS, filas fijas
|-- core_banking_mock/   src/core_banking_mock/ {app, auth, metrics}.py  fixtures/credits.json
|-- chart/               templates/  values-{prod,staging,kind}.yaml
|-- policies/            conftest/
|-- observability/       rules/  rules/tests/  runbooks/
|-- docs/                retention.md  api.md
|-- tools/               check_openapi.py
`-- tests/               unit/ property/ migrations/ integration/ doubles/ load/
```

---

## 2. Pasos

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `case-management/`**
  - Directorios de §1; `pyproject.toml` (dos miembros del workspace: `vectra_case` y `core_banking_mock`) que dependen de `vectra_contracts` y `vectra_common`.
  - Contratos de import-linter:
    - `case_fsm`, `backoff`, `decision` y `views` no importan `db`, `httpx` ni `vectra_common.deps` (funciones puras);
    - ningún módulo importa `httpx` fuera de `vectra_common.deps` (P-U0-07);
    - ninguno importa librerías de circuit breaking (NFR-U8-34).
  - Prueba estática: el cliente del core (`credit`) no tiene ningún método distinto de `GET` (NFR-U8-43, BR-U8-22).
  - Diseño: BR-U8-06, 22; NFR-U8-34, 43; P-U8-02. Historia: US-603.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config case-management/.importlinter && make -C case-management check` sobre el esqueleto; `uv run pytest case-management/tests/unit/test_core_client_readonly.py`.

- [ ] **Paso 2 — Constantes tipadas**
  - `vectra_case/config.py`:
    - timeouts de NFR-U8-30 (`serving-config` 500 ms, `feature_spec` 1 s, scoring 7 s, registro 2,5 s, core 500 ms);
    - pools de P-U8-02 (scoring 16, governance 4 y 2, registro 10, core 10), `RECONCILER_CONCURRENCY = 4` y pool de `case-db` ≤ 5;
    - umbrales del circuit breaker (≥ 50 % en 20 llamadas dentro de 30 s; semiabierto a los 10 s);
    - backoff (BR-U8-07), arrendamiento de 30 s, sondeo 400 ms ± 100 ms y semáforo de 16 (P-U8-01);
    - lotes (100 en barridos y reconciliador, 500 en la retención), abandono a las 24 h (BR-U8-18), gracia del worker de 20 s (INF-U8-06).
  - Values (no constantes): URLs y audiencias, telemetría, `allowTestScenarios`, `core.enabled`, `coreMock.enabled`, `retention.*` (INF-U8-07).
  - Diseño: INF-U8-07; P-U8-01, 02; NFR-U8-30, 31.
  - **Aceptación**: `uv run pytest case-management/tests/unit/test_config.py`:
    - `WORKER_WORST_CASE (15,5 s) < LEASE (30 s)`;
    - `WORKER_WORST_CASE < WORKER_SHUTDOWN_GRACE (20 s) < terminationGracePeriodSeconds (30 s)`;
    - `RECONCILER_CONCURRENCY (4) < REGISTRY_POOL (10)`;
    - ninguna constante se lee de variables de entorno.

### Bloque B — Base de datos

- [ ] **Paso 3 — Migraciones de `case-db`**
  - Tablas de domain-entities §1–§3, con:
    - el índice único parcial «un trabajo vivo por caso» en `evaluation_jobs` y `CHECK (attempt BETWEEN 0 AND 6)`;
    - la clave única (`case_id`, `user_id`) en `explanation_views`;
    - el índice único parcial de `decisions` por `case_id` (`state` `pendiente_registro` o `confirmada`);
    - el índice único parcial de `evidence_outbox`: `UNIQUE (idempotency_key) WHERE state <> 'abandonada'` (domain-entities §3.1);
    - la columna `cases.ever_degraded boolean NOT NULL DEFAULT false` (FD de U11; pendientes posteriores al cierre, 2026-10-10), que solo el worker escribe (`case_worker`, en su `UPDATE` por columna; `case_app` no la tiene), y un trigger `guard_ever_degraded` que impide volverla a `false`; prueba de migraciones: el worker la pone en `true` → éxito, `case_app` → error de permisos, volver a `false` → excepción del trigger (pendientes consolidados, 2026-10-10).
  - Roles `case_app`, `case_worker`, `case_retention` y `case_migrator`, con los permisos por tabla y por columna de `logical-components.md` §1 (INF-U8-01): `UPDATE` por columna de `case_app` y `case_worker` sobre `cases`; `SELECT` por columna de `case_retention`.
  - Tabla `case_transitions (from_state, to_state, db_role)` con las filas de INF-U8-01 y trigger `guard_transition` (`BEFORE INSERT OR UPDATE OF state`, `SECURITY DEFINER`, dueño `case_migrator`, `SET search_path = pg_catalog, public`, compara con `session_user`).
  - Trigger `guard_vencido` (`SECURITY INVOKER`) y tabla `retention_settings` de una fila, escrita con `INSERT … ON CONFLICT (id) DO UPDATE` desde los values, sin tocar `created_at` (P-U8-05).
  - RLS en `evidence_outbox`: `worker_fail_closed_only` (`FOR INSERT TO case_worker WITH CHECK (entry_type = 'fail_closed')`) y `app_all` para `case_app` (INF-U8-01).
  - Las cadenas de conexión usan `sslmode=verify-full` y cada proceso se conecta con su rol, sin `SET ROLE` ni pooler (P-U1-08; `guard_transition` depende de `session_user`).
  - Diseño: BR-U8-02, 12, 20; INF-U8-01; P-U8-05; NFR-U8-40, 41.
  - **Aceptación**: `uv run pytest case-management/tests/migrations` (Testcontainers, cada caso con el rol real):
    - `case_worker` lee `decisions`, borra `case_identifiers` o escribe `vencido` → error; `case_app` hace `DELETE` sobre `evaluation_jobs` → error;
    - `case_app` escribe `recommendation`, `recommendation_entry_id`, `last_cause` o `escalation_count` → error de permisos; `INSERT` de un caso en `listo` o con `recommendation` → excepción de `guard_transition`;
    - para cada fila de `case_transitions`, el rol indicado hace la transición; otro rol o un par ausente → excepción; ningún rol de la aplicación lee ni escribe `case_transitions`;
    - `case_worker` inserta `fail_closed` en `evidence_outbox` → éxito; `human_decision` o `explanation_view` → error de RLS; `case_app` inserta los tres → éxito;
    - `case_worker` repite el `INSERT` de `fail_closed` con la misma llave, sin `RETURNING` ni `ON CONFLICT` y dentro de un `SAVEPOINT` → `unique_violation`, vuelta al `SAVEPOINT` y el resto de la transacción confirma (BR-U8-09);
    - `case_worker` intenta `INSERT … RETURNING` u `ON CONFLICT DO UPDATE` sobre `evidence_outbox` → error de permisos (documenta por qué el código no los usa);
    - con una `human_decision` `abandonada` (decisión y evidencia), `case_app` inserta la decisión nueva y su evidencia con la **misma** llave → sin choque; una segunda fila viva con esa llave → `unique_violation`;
    - el orden del conflicto tras un abandono (BR-U8-18): pasar la nueva a `abandonada` y después la anterior a `confirmada`, en una transacción → éxito; el orden inverso → `unique_violation`;
    - `evaluation_jobs.attempt = 7` → violación del `CHECK`;
    - `case_app` escribe `vencido` → excepción; `case_retention` escribe `vencido` en un caso de 1 año → excepción, en uno de 2 años y 1 día → éxito; `case_retention` escribe `listo` → excepción;
    - `case_retention` y `case_app` escriben en `retention_settings` → error; cambiar `retention.undecided_years` y migrar → el trigger aplica el valor nuevo y `created_at` no cambia.

### Bloque C — Lógica pura

- [ ] **Paso 4 — `case_fsm`**
  - `transition(state, event) -> state | Rechazo` con la tabla de BR-U8-12 (la misma que `case_transitions`, sin el rol).
  - `decidido` y `vencido` terminales; `listo` nunca vuelve a evaluarse.
  - Diseño: BR-U8-12. Historias: US-107, US-112.
  - **Aceptación**: `uv run pytest case-management/tests/unit/test_case_fsm.py`: cada fila de BR-U8-12 aceptada, cada par fuera de la tabla rechazado, y una prueba que compara la tabla de `case_fsm` con las filas de `case_transitions` de la migración (sin el rol).

- [ ] **Paso 5 — `backoff`**
  - `schedule(attempt, rng) -> delay`: `30 s · 2^(n−1)` con jitter de ±20 %, máximo 6 intentos.
  - Diseño: BR-U8-07. Historia: US-112.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_backoff.py`: PBT-U8-02.

- [ ] **Paso 6 — `decision`**
  - `validate_decision(DecisionIn, recommendation)`: BR-U0-35 contra `recommendation.outcome`, `used_factors` subconjunto de los `feature_id` del `shap_vector` o exactamente `["ninguno"]`, reglas de `se_aparta`, `sigue` y `resuelve_revision`, justificación de 20 a 2000 caracteres tras recortar los bordes (BR-U0-36).
  - Diseño: BR-U8-16. Historias: US-108, US-502.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_decision.py tests/unit/test_decision_examples.py`:
    - PBT-U8-03;
    - `se_aparta` sin factores ni `ninguno` → 422; `sigue` con `["ninguno"]` → aceptada (US-502).

- [ ] **Paso 7 — `views`**
  - Proyección a `CaseSummary`, `CaseDetail` y `PersistentFailure`:
    - sin `score`, `outcome`, `recommendation` ni `explanation` fuera de `listo` y `decidido`; `attempts` y `last_cause` en `en_sincronizacion` y `no_disponible`;
    - `applicant_display` (nombre + los últimos 4 dígitos del documento) como única identificación en la bandeja;
    - `CaseDetail` con `application` sin `sex` ni `socioeconomic_stratum` e `identifiers?` ausente si el caso está anonimizado;
    - `credit_status` en `CaseDetail` (BR-U8-21).
  - Diseño: BR-U8-13, 13b. Historia: US-107.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_views.py`: PBT-U8-04.

- [ ] **Paso 8 — Resumen de la lógica pura**
  - Cobertura de ramas **100 %** en `case_fsm`, `backoff`, `decision` y `views`.
  - `mutmut` en `case_fsm`, `validate_decision`, `views` y `backoff`, con 0 sobrevivientes sin justificar.
  - Resumen en `aidlc-docs/construction/case-management/code/logic.md`.
  - Diseño: NFR-U8-50, 51, 52.
  - **Aceptación**: `uv run pytest case-management/tests/unit case-management/tests/property --cov=vectra_case.case_fsm --cov=vectra_case.backoff --cov=vectra_case.decision --cov=vectra_case.views --cov-branch --cov-fail-under=100` y `uv run mutmut run --paths-to-mutate case-management/src/vectra_case/case_fsm.py,case-management/src/vectra_case/decision.py,case-management/src/vectra_case/views.py,case-management/src/vectra_case/backoff.py` sin sobrevivientes fuera de la allowlist.

### Bloque D — `case-service`

- [ ] **Paso 9 — `intake`: ingesta y alta manual**
  - `POST /v1/intake/applications` (F04/F07, scope `intake:submit`) y `POST /v1/cases` (F10, solo `analista`):
    - validación de U0 (4xx genérico sin caso, BR-U0-30); `free_text` tal cual, siempre con consultas parametrizadas;
    - `Idempotency-Key` obligatoria, con alcance `client_id` (ingesta) o `user_id` (alta manual); misma llave y mismo `body_sha256` → el mismo `case_id`; otro cuerpo → 409;
    - identificadores en `case_identifiers` y el resto en `cases.application`;
    - caso en `en_evaluacion`, llave y trabajo de evaluación en **una** transacción;
    - `X-Test-Scenario` solo con `azp = channel-simulator` y `allow_test_scenarios = true`; en producción → 400; se guarda como `test_scenario_id` y no sale a scoring, al registro ni a los logs de negocio.
  - Diseño: BR-U8-01, 02, 03, 04; NFR-U8-01, 44. Historias: US-101, US-102, US-109.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_intake.py tests/integration/test_intake.py` (Testcontainers):
    - PBT-U8-06;
    - solicitud válida del simulador → caso `en_evaluacion`; inválida → 4xx sin caso; un caso adversarial queda con su `test_scenario_id` (US-101);
    - alta manual de un analista → canal `manual` y su `user_id`; `cumplimiento` → 403 con `authz.denied` (US-102);
    - `free_text` con `'; DROP TABLE cases; --` y `<script>` → guardado byte a byte y sin escape (US-109);
    - alta manual repetida con la misma `Idempotency-Key` → el mismo caso;
    - `X-Test-Scenario` con `allow_test_scenarios = false` → 400.

- [ ] **Paso 10 — `evidence`: decisión, consulta de la explicación y reconciliador**
  - Decisión (`POST /v1/cases/{id}/decision`, solo `analista`): BR-U8-15 (caso `listo` y sin otra decisión), `validate_decision`, `explanation_viewed_before` solo con evidencia `confirmada` (BR-U8-17), evidencia en dos fases con `UUIDv5(case_id, "human_decision")` y el payload de BR-U8-18; 503 sin ack; conflicto tras un abandono → reenvío de la abandonada y `409 conflict_state` con `reason = decision_already_recorded`.
  - Consulta (`POST /v1/cases/{id}/explanation-views`, solo `analista`): primera vez por (`case_id`, `user_id`) con `UUIDv5(case_id, user_id)` y `viewed_at`; las siguientes → 204; recuperación de una abandonada con el payload original (BR-U8-19).
  - Reconciliador (P-U8-04): cada 1 s, lotes de 100 con `SKIP LOCKED`, como máximo 4 envíos en vuelo, misma llave, payload y `correlation_id`, `occurred_at` nuevo, backoff de 1 s a 5 min, abandono a las 24 h. Envía también las entradas `fail_closed` que inserta `case-worker` (BR-U8-09).
  - Métricas `vectra_case_evidence_pending_oldest_seconds{entry_type}` y `vectra_case_evidence_abandoned_total{entry_type}` (creada en 0).
  - Diseño: BR-U8-09, 15, 16, 17, 18, 19; P-U8-02, 04, 09; NFR-U8-13, 23, 53. Historias: US-108, US-501, US-502.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evidence.py tests/integration/test_decision.py tests/integration/test_explanation_views.py tests/doubles/test_registry_double.py`:
    - PBT-U8-07 contra el doble del registro;
    - el doble del registro pasa las pruebas de ejemplo de append de U3 (plan de U3, Paso 7) (NFR-U8-53);
    - `first_evaluation` (revisión del FD de U11, 2026-10-10): caso nuevo → `true` en el intento 1 y `false` en el 2; caso que pasó por `modelo_congelado` y se descongeló (`attempts = 0`, intento 1) → `false`; caso reintentado por el CRO desde `no_disponible` → `false`;
    - decisión `sigue` → entrada `human_decision` con `user_id`, `model_version_id`, `policy_version_id` y `recommendation_entry_id`, y con `actor.acr` y `actor.auth_time` del token aunque la decisión no pida MFA (BR-U8-18; segunda revisión del Infrastructure Design de U10, 2026-10-10); decisión sobre un caso `no_disponible` → 409 sin entrada (US-108);
    - primera consulta → una entrada; segunda → 204 sin entrada (US-501);
    - evidencia pendiente 24 h → `abandonada`, y el caso acepta otra decisión;
    - decisión abandonada que el registro sí había escrito + decisión nueva → 409 `decision_already_recorded`; la nueva queda `abandonada`, el caso queda `decidido` con la primera y el registro tiene una sola `human_decision`;
    - caso `decidido` anonimizado → la consulta se acepta; caso `vencido` → decisión y consulta 409;
    - registro doble que tarda 2 s con 100 evidencias pendientes → nunca más de 4 envíos en vuelo, y una decisión concurrente obtiene conexión sin esperar;
    - 2 réplicas → cada evidencia pendiente se reintenta una sola vez por ciclo;
    - registro caído durante una decisión → 503 y `pendiente_registro`; al volver, el reconciliador confirma y el caso pasa a `decidido` (E3 de P-U8-09).

- [ ] **Paso 11 — `sweeps`, `retry` y `db_gauges`**
  - Barrido cada 5 min (BR-U8-10, 14): con `serving-config` activo, `modelo_congelado` → `en_evaluacion` con `attempts = 0` y trabajo nuevo con `attempt = 0`; marca y desmarca `model_frozen_after_recommendation`; con governance caído, el barrido se salta el ciclo.
  - `POST /v1/cases/{id}/retry` (solo `cro`, solo desde `no_disponible`, sin MFA; 409 en otro estado): `en_evaluacion`, `attempts = 0`, trabajo nuevo con `attempt = 0`, log `case.retry_requested` y `vectra_case_retries_total`.
  - `db_gauges` cada 30–60 s, en todas las réplicas: `vectra_case_jobs_overdue`, `vectra_cases_failclosed_persistent`, métricas de evidencia y de retención (`vectra_case_retention_overdue_identifiers`, `vectra_case_retention_last_success_timestamp` con `retention_settings.created_at` mientras no haya corrida, `vectra_case_retention_consecutive_overdue_runs`).
  - Diseño: BR-U8-10, 11, 14; P-U8-04, 07, 08; NFR-U8-13, 45, 46. Historia: US-112.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_sweeps.py tests/integration/test_retry.py tests/integration/test_db_gauges.py`:
    - versión reactivada → el barrido apaga `model_frozen_after_recommendation`;
    - `retry` sobre un caso `vencido` o `listo` → 409; desde `no_disponible` → `en_evaluacion` y el log con `principal_subject` y `principal_role`;
    - instalación nueva sin corridas → `vectra_case_retention_last_success_timestamp` vale `retention_settings.created_at`;
    - 2 réplicas → los barridos no procesan dos veces el mismo caso.

- [ ] **Paso 12 — `credit`: lectura del core**
  - `GET /v1/credits/{case_id}` (F17) solo para casos `decidido`, timeout 500 ms, sin caché; 404 → `sin_credito`; error o timeout → `no_disponible`.
  - Con `core.enabled = false`: `no_integrado` (precisado el 2026-10-10 por U10 FD, Q3) sin crear el cliente, sin llamar y sin registrar nada en el breaker (INF-U8-02).
  - Diseño: BR-U8-21; INF-U8-02; P-U8-09; NFR-U8-25, 31.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_credit.py`:
    - mock detenido → `get_case` responde con `credit_status = no_disponible` dentro de su p99 (E6 de P-U8-09);
    - `core.enabled = false` y un doble que registra las llamadas → `no_integrado`, cero llamadas y breaker sin fallos registrados;
    - 404 → `sin_credito`.

- [ ] **Paso 13 — API, arranque y apagado de `case-service`**
  - `create_app` de U0 con las rutas de F04 y F10 (`list_cases`, `get_case`, `get_case_identifiers` (`cro` y `cumplimiento`; revisión del Infrastructure Design de U10, 2026-10-10), `create_case`, `record_decision`, `record_explanation_view`, `retry_case`, `list_persistent_failures`); scopes y audiencias de U2; `list_cases` excluye `vencido` salvo con `state=vencido`.
  - Logs `case.viewed` y `case.retry_requested` con la allowlist de U0 §8; `authz.denied` y `vectra_authz_denied_total` en cada 401/403.
  - Readiness (`/readyz`, 8081) solo con `case-db`; liveness solo del proceso.
  - Apagado: `preStop` de 5 s en el chart, uvicorn con `timeout_graceful_shutdown = 10`; al recibir `SIGTERM`, barridos y reconciliador dejan de tomar trabajo y terminan el lote.
  - Etiquetas de métricas dentro de la allowlist de P-U8-06 y contadores de conjunto cerrado creados en 0.
  - Diseño: BR-U8-13, 13b; P-U8-03, 06; INF-U8-04, 06; NFR-U8-21, 22, 42, 45. Historias: US-107, US-108.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_app.py tests/integration/test_degradation.py tests/integration/test_service_shutdown.py`:
    - bandeja con casos en `listo`, `en_sincronizacion`, `no_disponible` y `modelo_congelado`; el `GET` de un caso no listo no trae `score` (US-107);
    - `model_frozen_after_recommendation=true` en la consulta → solo los casos marcados; `false` → solo los no marcados (BR-U8-13; revisión del FD de U10, 2026-10-10, A4);
    - detalle para `analista` → sin `sex` ni `socioeconomic_stratum` y con el log `case.viewed`;
    - `get_case_identifiers` para `cumplimiento` → solo `identifiers` y `anonymized`, sin solicitud ni recomendación; para `analista` → 403; caso anonimizado → `anonymized = true` sin `identifiers` (revisión del Infrastructure Design de U10, 2026-10-10);
    - una fila de P-U8-03 por prueba: `case-db` en `default_transaction_read_only` → 503 sin efecto y `Ready`; governance, scoring, registro o core caídos → `Ready`;
    - `GET /metrics` recién iniciado muestra cada combinación de los contadores en 0; ninguna etiqueta fuera de la allowlist;
    - PBT-U0-07 en modo strict sobre `case.viewed` y `case.retry_requested`;
    - una ruta sin scope → 403 con `authz.denied`;
    - `SIGTERM` durante un lote del reconciliador → el lote termina y no queda evidencia a medio enviar.

### Bloque E — `case-worker`

- [ ] **Paso 14 — Clientes y caché de gobierno**
  - Un `httpx.AsyncClient` por dependencia con `deps.call` (P-U8-02): scoring 16 conexiones y 7 s; governance 4 conexiones, 500 ms (`serving-config`) y 1 s (`feature_spec`).
  - `governance_client`: `serving-config` con caché ≤ 5 s e `If-None-Match`; `feature_spec` por versión, sin expiración, LRU de 4.
  - Fallo del breaker = timeout, conexión o 5xx; un 4xx no cuenta (NFR-U8-32).
  - Diseño: BR-U8-05; P-U8-02, 09; NFR-U8-15, 24, 30, 31, 32, 33.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_worker_clients.py`:
    - scoring doble de 7 s con 16 trabajos en vuelo → las lecturas de `serving-config` siguen respondiendo en < 50 ms;
    - 20 respuestas 422 de scoring → circuito cerrado;
    - scoring caído → tras 20 llamadas, los intentos terminan en < 50 ms (E1 de P-U8-09);
    - 5 versiones de `feature_spec` → se descarta la menos usada.

- [ ] **Paso 15 — `job_queue`, `evaluation` y `worker`**
  - `job_queue` (P-U8-01): semáforo de 16; sondeo 400 ms ± 100 ms; toma en una transacción corta con `FOR UPDATE SKIP LOCKED`, `locked_until = now() + 30 s` y **`attempt = attempt + 1` copiado a `cases.attempts`**, también en la retoma tras un arrendamiento vencido; la decisión se toma con el `attempt` **leído**: si ya vale 6, escala en esa transacción con `local_cause = scoring_unreachable`, sin incrementar (nunca se escribe 7, que el `CHECK` rechaza) y sin llamar a scoring (BR-U8-07); la conexión vuelve al pool antes de las llamadas.
  - `evaluation` (BR-U8-05..09): `serving-config` → `feature_spec` → `derive` → `ScoringRequest` (sin identificadores, `free_text` ni `test_scenario_id`; con `received_at = cases.created_at` y `first_evaluation = not cases.ever_degraded and attempt = 1`, BR-U8-06; pendientes posteriores al cierre, 2026-10-10) → scoring; al entrar en `en_sincronizacion`, `no_disponible` o `modelo_congelado`, la misma transacción pone `cases.ever_degraded = true`; tabla de resultados de BR-U8-08, con el reintento por 401 dentro del mismo intento; aplicación del resultado con `UPDATE … WHERE state IN (…) AND attempts = :attempt`, con el número que devolvió esa toma, o `evaluation.result_discarded`; la reprogramación solo fija `run_at`, `last_cause` y `locked_until = NULL`.
  - Escalamiento: `no_disponible`, `escalation_count + 1` y la entrada `fail_closed` en `evidence_outbox` con `UUIDv5(case_id, "fail_closed", ciclo)`, exactamente uno de `cause` o `local_cause`, `retryable`, `attempt` y `escalated_at`, con un `INSERT` simple en un `SAVEPOINT` (sin `RETURNING` ni `ON CONFLICT`; `unique_violation` de la llave = éxito) en la misma transacción que el cambio de estado (BR-U8-09); la envía el reconciliador del Paso 10.
  - Métricas `vectra_case_attempts_total{result, attempt}` (creadas en 0) y `vectra_case_time_to_ready_seconds` (solo casos `listo` al primer intento).
  - Apagado: al recibir `SIGTERM` deja de sondear y espera las llamadas en vuelo hasta 20 s.
  - Diseño: BR-U8-05, 06, 07, 08, 09, 12; P-U8-01, 08, 09; INF-U8-06; NFR-U8-02, 03, 04, 11, 24. Historias: US-109, US-112.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evaluation.py tests/property/test_case_machine.py tests/integration/test_worker.py tests/integration/test_worker_shutdown.py` (Testcontainers y dobles):
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
    - doble de scoring que falla el 30 % de los primeros intentos → `vectra_case_first_attempt_failure_ratio` = 0,3 ± 0,05;
    - `SIGTERM` al worker a los 0,5 s con un scoring que responde a los 10 s → el intento termina y el caso queda `listo`.

### Bloque F — `case-retention` y `core-banking-mock`

- [ ] **Paso 16 — CLI `case-retention`**
  - `python -m vectra_case.retention --dsn …`, la misma CLI para el CronJob y el `restore-drill` de U1. No acepta plazos por argumento: los lee de `retention_settings`.
  - Corrida de P-U8-07: lotes de ≤ 500 con `FOR UPDATE SKIP LOCKED` y `lock_timeout = 1s`; borra `case_identifiers` y `application.free_text`, fija `anonymized_at`, pasa a `vencido` y borra el trabajo de los no decididos; el plazo de 10 años se cuenta desde `decisions.decided_at` de la decisión `confirmada`; borra `intake_keys` vencidas; inserta su fila en `retention_runs`.
  - Diseño: BR-U8-02, 20; P-U8-05, 07; NFR-U8-46.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_retention.py tests/integration/test_retention.py`:
    - PBT-U8-08;
    - la corrida completa con el rol `case_retention` real, sin superusuario, no recibe ningún `permission denied`;
    - 2 000 casos vencidos con la API escribiendo en paralelo → ninguna espera de bloqueo > 1 s y 0 vencidos tras dos corridas;
    - caso `listo` con la retención vencida → `vencido` sin identificadores; una decisión, una consulta o un `retry` sobre él → 409;
    - `--plazo` o cualquier argumento de plazos → error de uso.

- [ ] **Paso 17 — `core-banking-mock`**
  - FastAPI sin base, con los fixtures dentro de la imagen (`/app/fixtures/credits.json`).
  - `GET /v1/credits/{id}` con validación de firma por JWKS (F50), `aud = core-banking-mock` y scope `core:read-credit` con `vectra_common`.
  - `POST /v1/credits/{id}/status`: exige `core:write-credit`, que nadie tiene → 403, `WriteAttempt` en el log y `vectra_core_write_attempts_total` (creada en 0 al arrancar).
  - Métricas en 8081.
  - Diseño: BR-U8-22; INF-U8-02, 03; P-U8-06; NFR-U8-26, 45. Historia: US-603.
  - **Aceptación**: `uv run pytest case-management/core_banking_mock/tests`:
    - token sin `core:read-credit` → 403;
    - prueba **del mock aislado, sin proxy de Linkerd**: `POST` con cualquier token válido → 403, un `WriteAttempt` y la métrica en 1 (US-603);
    - `GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0.

- [ ] **Paso 18 — Resumen de los servicios**
  - Cobertura de ramas ≥ 95 % en `vectra_case` y **100 %** en `case_fsm`, `backoff`, `decision`, `views`, `intake`, `evidence`, `evaluation`, `sweeps` y `retention`.
  - PBT-U8-01..08 con el perfil `ci` (500 ejemplos, semilla impresa).
  - Resúmenes en `aidlc-docs/construction/case-management/code/services.md` y `code/database.md`.
  - Diseño: NFR-U8-50, 52.
  - **Aceptación**: `uv run pytest case-management/tests --cov=vectra_case --cov-branch --cov-fail-under=95` y el umbral por módulo (100 % en los nueve de NFR-U8-50).

### Bloque G — Despliegue y operación

- [ ] **Paso 19 — Dockerfiles y cadena de suministro**
  - Una imagen para `case-service`, `case-worker`, `case-retention` y la migración (P-U8-10), y otra para el mock con sus fixtures; base Python oficial pinneada por digest, `runAsNonRoot` y `readOnlyRootFilesystem`.
  - Construidas, escaneadas, con SBOM y firmadas por `supply-chain.yml` de U1.
  - Diseño: P-U8-10; NFR-U8-34.
  - **Aceptación**: `hadolint case-management/Dockerfile case-management/core_banking_mock/Dockerfile`; prueba sobre el SBOM: ninguna librería de circuit breaking.

- [ ] **Paso 20 — Chart, values, cuotas y flujos**
  - `case-service` y `case-worker`: `Deployment`, `Service`, `HorizontalPodAutoscaler` (2–6, CPU 70 %, estabilización 60/300 s), `PodDisruptionBudget`, `ServiceAccount` propia, `ExternalSecret` (llave `private_key_jwt`), `Secret` del rol de CloudNativePG y `ServiceMonitor`; recursos y probes de INF-U8-04; spread por zona; `vectra-high`; sidecar nativo de Linkerd.
    - `case-service`: `preStop.sleep` de 5 s y `terminationGracePeriodSeconds: 20`;
    - `case-worker`: `terminationGracePeriodSeconds: 30`.
  - `case-retention`: `CronJob` (`schedule` y `timeZone` desde los values, `Forbid`, `startingDeadlineSeconds: 3600`, `activeDeadlineSeconds: 7200`, `backoffLimit: 2`), `vectra-low`, sidecar nativo.
  - Job de migración como hook de sync (F44), con `case_migrator`, `vectra-low` y la fila de `retention_settings` desde los values.
  - `core-banking-mock` solo con `coreMock.enabled = true`: 2 réplicas, PDB, `vectra-low`, namespace `vectra-mock`; `Server`, `HTTPRoute` de `GET /v1/credits/{id}` autorizada solo para `case-service` y `HTTPRoute` `core-mock-catch-all` sin `AuthorizationPolicy` (INF-U8-03).
  - **Job `rt5-demo-<runId>`** (U12; pendientes posteriores al cierre, 2026-10-10): solo con los values de kind y con `probes.runId` (pendientes consolidados, 2026-10-10: ya no en staging), con la `ServiceAccount` `case-service`; envía `POST /v1/credits/{id}/status` al mock y deja en su log el 403 del proxy (INF-U8-03); `backoffLimit: 0`, sidecar nativo, **sin** `ttlSecondsAfterFinished` (se poda al cambiar `probes.runId`). `conftest`: `probes.runId` en los values de staging o de producción → falla; el Job no aparece con ellos ni sin `probes.runId` (pendientes consolidados, 2026-10-10).
  - Values de producción: `core.enabled = false`, `coreMock.enabled = false`, `allowTestScenarios = false`.
  - Aporte de U8 a las cuotas de `vectra-app` y `vectra-mock` en `platform/policies/quotas/` de U1 (INF-U8-05).
  - Comprobar en `platform/network/flows.yaml` F04, F07, F10, F15, F16, F17, F40, F44, F50, F60, F104 y F105, con `case-worker` como origen de F15, F40 y F104, y X01 en la suite de conectividad.
  - Diseño: INF-U8-01, 02, 03, 04, 05, 06, 07; P-U8-07, 10; NFR-U8-10, 12, 14, 20, 26, 43, 44. Historia: US-609.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test case-management/policies/conftest/`, que verifica:
    - HPA 2–6, PDB, `topologySpreadConstraints`, `priorityClassName`, requests y limits;
    - `preStop.sleep` y `terminationGracePeriodSeconds ≥ 20` en `case-service`, `≥ 30` en `case-worker`; la anotación del sidecar en el CronJob y el Job;
    - en los values de producción: `core.enabled = false`, `coreMock.enabled = false`, `allowTestScenarios = false`, y ningún recurso del mock renderizado;
    - ninguna constante de INF-U8-07 como variable de entorno.

    Además, `kyverno test` (sin excepción a `require-spread-and-pdb`), `conftest test platform/policies/quotas/` (cuota ≥ suma de aportes) y `uv run python platform/network/generate.py --check`.

- [ ] **Paso 21 — Alertas y runbooks**
  - `PrometheusRule` con:
    - `CaseEvidencePending` y `CaseEvidenceAbandoned` (P-U8-04);
    - `CaseRetentionMissing` y `CaseRetentionOverdue` (P-U8-07);
    - `CaseApiUnavailable`, `CaseJobsOverdue`, `CaseFirstAttemptFailureHigh` (con su regla de grabación) y `ScoringRequestRejected` (P-U8-08);
    - `CoreWriteAttempt` con la expresión de INF-U8-03, renderizada solo con `coreMock.enabled = true`.
  - `FailClosedPersistente` (U1), `AuthDeniedBurst` (U2) y `PostgresVolumeUsageHigh` (U1) no se definen aquí: se prueba que las métricas de U8 que las alimentan existen con esos nombres.
  - Un runbook por alerta. El de `CoreWriteAttempt` explica que en la demostración de RT-5 es la evidencia esperada y la limitación del `offset 5m` si el pod del mock se reemplaza (INF-U8-03).
  - Diseño: P-U8-04, 06, 07, 08; INF-U8-03, 08; NFR-U8-03, 45, 46. Historias: US-112, US-603.
  - **Aceptación**: `promtool test rules case-management/observability/rules/tests/*.yaml`:
    - cada alerta con series en los dos lados del umbral;
    - `CaseApiUnavailable` sin `up{job="case-service"}` durante 2 min → dispara;
    - `CaseRetentionMissing` con la serie ausente 1 h → dispara;
    - `CoreWriteAttempt`: la serie de Linkerd **arranca en 1** y dispara; una denegación con otro `route_name` no dispara; el contador del mock de 0 a 1 dispara.

    Además, `uv run python platform/tests/test_runbooks.py --root case-management` y `helm template` con los values de producción → sin `CoreWriteAttempt`.

- [ ] **Paso 22 — Documentación**
  - `case-management/docs/retention.md`: plazos, fuente única (`retention_settings`), riesgo aceptado de los respaldos y los tres **[VERIFICAR]**, con un espacio para la firma de cumplimiento; el despliegue a producción la exige (NFR-U8-47).
  - `case-management/docs/api.md` y el OpenAPI exportado de `case-service` y del mock.
  - Diseño: BR-U8-20; NFR-U8-47.
  - **Aceptación**: `uv run python case-management/tools/check_openapi.py` (el OpenAPI versionado coincide con el de la app) y una regla de `conftest` sobre la Application de producción que exige la anotación con la referencia a la firma de `retention.md`.

- [ ] **Paso 23 — Applications, especificación de carga y trazabilidad**
  - Applications en la wave 5 (migración como hook, `case-service`, `case-worker`, CronJob) por entorno y sin auto-sync; la del mock solo en kind y staging.
  - Script k6 para U12: 10 solicitudes/s de ingesta con la consola en paralelo, umbrales de NFR-U8-01 y el histograma de NFR-U8-02.
  - Trazabilidad de cada BR-U8 a una prueba.
  - Diseño: P-U1-12; NFR-U8-01, 02.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `k6 inspect case-management/tests/load/cases.js`; `uv run python platform/tests/test_traceability.py --unit case-management --all`.

### Bloque H — Verificación en kind (con aprobación humana)

- [ ] **Paso 24 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–23 aprobado por un humano, con U1–U7 instalados en kind y un modelo activo.
  - El operador ejecuta, con evidencia:
    1. suite de conectividad de U1: `case-service` → scoring denegado; `case-worker` → scoring permitido; `case-worker` → registro y core denegados; el mock alcanza solo el JWKS de Keycloak;
    2. un origen distinto de `case-service` hacia el mock → descartado por la `NetworkPolicy` (X01, capa 1);
    3. E1, E3, E5 y E6 de P-U8-09 con las unidades reales; E2 y E4 quedan para Operations (RESILIENCY-14 = C);
    4. `kubectl rollout restart` de `case-worker` durante la carga → ningún `evaluation.result_discarded`;
    5. PBT-U8-07 abreviado contra el registro real (NFR-U8-53);
    6. ampliar el volumen de `case-db` sin reiniciar el `Cluster` (INF-U8-08);
    7. cuando exista U12: la demostración de RT-5 dispara `CoreWriteAttempt` con `vectra_core_write_attempts_total` en 0, y la prueba de carga cumple NFR-U8-01 y 02 sin `too many connections`.
  - Diseño: P-U8-01, 03, 04, 09, 10; INF-U8-01, 03, 06, 08; NFR-U8-01, 02, 14, 43. Historias: US-603, US-609.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con el comando, la salida y el resultado esperado frente al obtenido.

### Bloque I — Cierre

- [ ] **Paso 25 — Frontend: N/A**
  - La consola es de U10.
  - **Aceptación**: `test ! -d case-management/frontend`.

- [ ] **Paso 26 — Cierre de la unidad**
  - **Aceptación**: `make -C case-management check`, que corre en orden las verificaciones estáticas, las migraciones, las propiedades y las pruebas de integración de los Pasos 1–23 y termina en 0. Las de kind (Paso 24) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-101 | 9 |
| US-102 | 9 |
| US-107 | 4, 7, 13 |
| US-108 | 6, 10, 13 |
| US-109 | 9, 15 |
| US-112 | 4, 5, 11, 15, 21 |
| US-501 | 10 |
| US-502 | 6, 10 |
| US-603 | 1, 17, 21, 24 |
| US-609 | 20, 24 |

| Diseño | Pasos |
|---|---|
| BR-U8-01..22 y 13b | 1, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 22 |
| NFR-U8-01..53 | 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24 |
| P-U8-01..10 | 1, 2, 3, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 24 |
| INF-U8-01..08 | 2, 3, 12, 13, 15, 17, 20, 21, 24 |

| Propiedad | Paso |
|---|---|
| PBT-U8-01 | 15, 18 |
| PBT-U8-02 | 5 |
| PBT-U8-03 | 6 |
| PBT-U8-04 | 7 |
| PBT-U8-05 | 15 |
| PBT-U8-06 | 9 |
| PBT-U8-07 | 10, 24 |
| PBT-U8-08 | 16 |

## 4. Cumplimiento de extensiones (plan de tareas U8)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ningún paso aplica ni sincroniza; los escenarios con clúster los ejecuta el operador (Paso 24) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 | Cumple | Cliente del core solo con `GET` (Paso 1); `core.enabled = false` en producción (Pasos 12, 20); escritura del mock siempre rechazada (Paso 17); X01 en kind (Paso 24) |
| AUTONOMIA-04 | Cumple | `guard_vencido` y `guard_transition` (Paso 3); `modelo_congelado` y el barrido (Pasos 11, 15) |
| AUTONOMIA-05 | Cumple | PBT-U8-05 (Paso 15); telemetría sin datos del solicitante (Paso 13); retención (Paso 16) |
| AUTONOMIA-06 | Cumple | PBT-U8-01 y la aplicación condicionada del resultado (Paso 15); evidencia en dos fases (Paso 10); apagado sin abandono (Pasos 13, 15, 24) |
| SECURITY-01 / 03 / 05 / 06 / 08 / 11 / 13 / 14 / 15 | Cumple | Pasos 3, 9, 10, 13, 15, 16, 17, 20, 21 (SECURITY-11: casos de abuso de llave reutilizada, `X-Test-Scenario` en producción, `free_text` adversarial, escritura al core, `entry_type` falsificado desde `case_worker` y transición fuera de `case_transitions`) |
| RESILIENCY-01 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 14 / 15 | Cumple | Pasos 10, 11, 13, 14, 15, 20, 21, 24 |
| PBT-01..10 | Cumple | Pasos 5, 6, 7, 9, 10, 15 y 16 (PBT-U8-01..08), Paso 18 (perfil `ci`) y pruebas de ejemplo en los Pasos 4, 6, 9, 10, 11, 13, 15, 16 y 17 |
