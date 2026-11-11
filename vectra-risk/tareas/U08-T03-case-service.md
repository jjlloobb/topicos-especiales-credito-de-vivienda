# U08-T03 — `case-service`: intake, evidencia, barridos, `credit` y API

**Unidad:** U8 `case-management`
**Historias que implementa:**
- US-101 y US-102: ingesta y alta manual (Paso 9);
- US-107: bandeja y detalle (Paso 13);
- US-108: decisión (Pasos 10 y 13);
- US-109: `free_text` guardado tal cual (Paso 9);
- US-112: barrido y `retry` (Paso 11);
- US-501: consulta de la explicación (Paso 10);
- US-502: `se_aparta` y `sigue` con su evidencia (Paso 10).

**Depende de:**
- U08-T01 y U08-T02 en `main`: esqueleto, migraciones, grants y RLS, `case_fsm`, `backoff`, `decision` y `views`.
- **U00-T03 en `main`** (PR #133). Es la lectura pública de `Recommendation`: `read_wire` en `vectra_contracts.outcome`, una `Recommendation` anidable en `CaseDetail` sin token, y el token que deja de exportarse, con lo que desaparece la excepción de import-linter para `views`. Hoy `from vectra_contracts.outcome import read_wire` da `ImportError` en `main`.
- U0 en `main`: `create_app`, `authz`, `deps`, `service_token`, `ops_server.run_service`, la allowlist de logs, `ServingConfig` con `cutoff`, `low_confidence_threshold` y `channel_rules` (U04-T09), y las 9 rutas de `REGISTRY["case-service"]`.

Sin clúster (AUTONOMIA-01). Las pruebas de integración usan Testcontainers (Docker local) y dobles HTTP.
**Se despacha** cuando U00-T03 esté fusionado en `main` con el CI en verde. Al redactar esta tarea, el PR #133 seguía abierto con el job `checks` en rojo por la mutación de U0.
**Rama:** `tarea/U08-T03`, desde `origin/main`.

Es el Bloque D del plan de U8 (`aidlc-docs/construction/plans/case-management-code-generation-plan.md`, Pasos 9 a 13), que en `demo-recorte-funcional.md` §4 y §8 es la tarea «D (9–13)». La enmienda pide **no** juntarla con otro bloque (§4, notas: «U8 D (Pasos 9–13)» pasaría de 2 rondas). Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): como máximo 2 rondas, y solo un ROJO bloquea.

Tareas que siguen en U8:
- **U08-T04**: E+F, Pasos 14, 15, 17 y 18 (clientes de `case-worker`, `job_queue`, `evaluation`, `worker`, el mock y el resumen de servicios).
- **U08-T05**: G y el cierre, Pasos 19 a 23, 25 y 26.
- El Paso 16 (`case-retention`) está en D.
- El Paso 24 queda consolidado en U12 Paso 18 (enmienda §8).

---

## Alcance

**Dentro:** los Pasos 9 a 13 del plan, con los recortes E\*F de la enmienda (§3, U8). Cada recorte se marca abajo con ~~tachado~~ y aparece también en «Fuera».

### Bloque D — `case-service`

- [ ] **Paso 9 — `intake`: ingesta y alta manual** (E)
  - `POST /v1/intake/applications` (F04/F07, scope `intake:submit`) y `POST /v1/cases` (F10, solo `analista`):
    - validación de U0 (4xx genérico sin caso, BR-U0-30); `free_text` tal cual, siempre con consultas parametrizadas;
    - `Idempotency-Key` obligatoria, con alcance `client_id` (ingesta; `Principal.client_id`, el `azp`) o `user_id` (alta manual). La misma llave con el mismo `body_sha256` da el mismo `case_id`; con otro cuerpo da 409;
    - identificadores en `case_identifiers` y el resto en `cases.application`;
    - el caso en `en_evaluacion`, la llave y el trabajo de evaluación se escriben en **una** transacción;
    - `X-Test-Scenario` solo con `azp = channel-simulator` y `allow_test_scenarios = true`; en producción da 422. Se guarda como `test_scenario_id` y no sale a scoring, al registro ni a los logs de negocio.
  - **P-5 de la enmienda:** la función de purga de `intake_keys` se adelanta a este paso, sin CLI (ver Precisiones), para que PBT-U8-06 se corra entera.
  - Diseño: BR-U8-01, 02, 03, 04; NFR-U8-01, 44. Historias: US-101, US-102, US-109.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_intake.py case-management/tests/integration/test_intake.py`:
    - PBT-U8-06, entera, incluida la llave libre tras la purga de 30 días;
    - solicitud válida del simulador → caso `en_evaluacion`; inválida → 4xx sin caso; un caso adversarial queda con su `test_scenario_id` (US-101);
    - alta manual de un analista → canal `manual` y su `user_id`; `cumplimiento` → 403 con `authz.denied` (US-102);
    - `free_text` con `'; DROP TABLE cases; --` y `<script>` → guardado byte a byte y sin escape (US-109);
    - alta manual repetida con la misma `Idempotency-Key` → el mismo caso;
    - `X-Test-Scenario` con `allow_test_scenarios = false` → 422.

- [ ] **Paso 10 — `evidence`: decisión, consulta de la explicación y reconciliador** (E\*F)
  - Decisión (`POST /v1/cases/{id}/decision`, solo `analista`):
    - BR-U8-15: el caso está `listo` y no tiene otra decisión;
    - `validate_decision` (U08-T02);
    - `explanation_viewed_before` cuenta solo con evidencia `confirmada` (BR-U8-17);
    - evidencia en dos fases, con `UUIDv5(case_id, "human_decision")` y el payload de BR-U8-18;
    - sin ack → 503;
    - conflicto tras un abandono → se reenvía la abandonada y se responde `409 conflict_state` con `reason = decision_already_recorded`.
  - Consulta (`POST /v1/cases/{id}/explanation-views`, solo `analista`):
    - la primera vez por (`case_id`, `user_id`) se registra con `UUIDv5(case_id, user_id)` y `viewed_at`;
    - las siguientes → 204;
    - una abandonada se recupera con el payload original (BR-U8-19).
  - Reconciliador (P-U8-04):
    - corre cada 1 s, en lotes de 100 con `SKIP LOCKED` y como máximo 4 envíos en vuelo;
    - reenvía con la misma llave, el mismo payload y el mismo `correlation_id`, y un `occurred_at` nuevo;
    - backoff de 1 s a 5 min; abandona a las 24 h;
    - envía también las entradas `fail_closed` que inserta `case-worker` (BR-U8-09). El worker es U08-T04; aquí las pruebas las insertan con el rol `case_worker`.
  - Métricas `vectra_case_evidence_pending_oldest_seconds{entry_type}` y `vectra_case_evidence_abandoned_total{entry_type}` (creada en 0).
  - `explanation_view` con 422 por BR-U0-37 → `descartada`, sin reenvío aunque se abra de nuevo. Lleva la métrica `vectra_case_evidence_discarded_total` (creada en 0) con su prueba. ~~La alerta `CaseEvidenceDiscarded` con su prueba~~ **(diferida por la demo; ver «Fuera»)**.
  - Diseño: BR-U8-09, 15, 16, 17, 18, 19; P-U8-02, 04, 09; NFR-U8-13, 23, 53. Historias: US-108, US-501, US-502.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evidence.py case-management/tests/integration/test_decision.py case-management/tests/integration/test_explanation_views.py case-management/tests/doubles/test_registry_double.py`. Las líneas son las del plan, todas:
    - PBT-U8-07 contra el doble del registro;
    - el doble del registro pasa las pruebas de ejemplo de append de U3 (NFR-U8-53; ver Precisiones);
    - `first_evaluation`: caso nuevo → `true` en el intento 1 y `false` en el 2. Caso descongelado con `attempts = 0`, intento 1 → `false`. Caso reintentado por el CRO desde `no_disponible` → `false`. Como `case-worker` es de U08-T04, aquí se comprueba sobre la fila y el payload que el reconciliador envía;
    - decisión `sigue` → entrada `human_decision` con `user_id`, `model_version_id`, `policy_version_id`, `recommendation_entry_id`, `actor.acr` y `actor.auth_time` del token, aunque la decisión no pida MFA (BR-U8-18). Decisión sobre un caso `no_disponible` → 409 sin entrada (US-108);
    - primera consulta → una entrada; segunda → 204 sin entrada (US-501);
    - evidencia pendiente 24 h → `abandonada`, y el caso acepta otra decisión;
    - decisión abandonada que el registro sí había escrito, seguida de una decisión nueva → 409 `decision_already_recorded`. La nueva queda `abandonada`, el caso queda `decidido` con la primera y el registro tiene una sola `human_decision`;
    - caso `decidido` anonimizado → la consulta se acepta; caso `vencido` → decisión y consulta dan 409;
    - registro doble que tarda 2 s con 100 evidencias pendientes → nunca más de 4 envíos en vuelo, y una decisión concurrente obtiene conexión sin esperar;
    - 2 réplicas → cada evidencia pendiente se reintenta una sola vez por ciclo;
    - registro caído durante una decisión → 503 y `pendiente_registro`. Al volver el registro, el reconciliador confirma y el caso pasa a `decidido` (E3 de P-U8-09);
    - `explanation_view` con 422 → `descartada` y `vectra_case_evidence_discarded_total` en 1.

- [ ] **Paso 11 — `sweeps`, `retry` y `db_gauges`** (E\*F)
  - Barrido cada 5 min (BR-U8-10, 14):
    - con `serving-config` activo, los `modelo_congelado` pasan a `en_evaluacion` con `attempts = 0` y un trabajo nuevo con `attempt = 0`;
    - marca y desmarca `model_frozen_after_recommendation`;
    - con governance caído, se salta el ciclo.
  - `POST /v1/cases/{id}/retry`:
    - solo `cro`, solo desde `no_disponible` y sin MFA; en otro estado → 409;
    - pasa a `en_evaluacion` con `attempts = 0` y un trabajo nuevo con `attempt = 0`;
    - deja el log `case.retry_requested` y suma en `vectra_case_retries_total`.
  - `db_gauges` cada 30–60 s, en todas las réplicas: `vectra_case_jobs_overdue`, `vectra_cases_failclosed_persistent` y las métricas de evidencia. ~~Las métricas de retención (`vectra_case_retention_overdue_identifiers`, `vectra_case_retention_last_success_timestamp`, `vectra_case_retention_consecutive_overdue_runs`)~~ **(diferidas por la demo; ver «Fuera»)**.
  - Diseño: BR-U8-10, 11, 14; P-U8-04, 07, 08; NFR-U8-13, 45, ~~46~~ (diferido con la retención). Historia: US-112.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_sweeps.py case-management/tests/integration/test_retry.py case-management/tests/integration/test_db_gauges.py`:
    - versión reactivada → el barrido apaga `model_frozen_after_recommendation`;
    - `retry` sobre un caso `vencido` o `listo` → 409; desde `no_disponible` → `en_evaluacion`, con el log que lleva `principal_subject` y `principal_role`;
    - ~~instalación nueva sin corridas → `vectra_case_retention_last_success_timestamp` vale `retention_settings.created_at`~~ (diferida);
    - 2 réplicas → los barridos no procesan dos veces el mismo caso;
    - (de esta tarea) `vectra_cases_failclosed_persistent` cuenta los `no_disponible`, y `vectra_case_jobs_overdue` cuenta los trabajos vencidos;
    - (de esta tarea) `serving-config` con la forma vieja, sin `cutoff`, `low_confidence_threshold` ni `channel_rules` → el barrido se salta el ciclo y no mueve ningún caso.

- [ ] **Paso 12 — `credit`: lectura del core** (E; P-11 de la enmienda: `core.enabled = true` en kind)
  - `GET /v1/credits/{case_id}` (F17) solo para casos `decidido`, con timeout de 500 ms y sin caché. 404 → `sin_credito`; error o timeout → `no_disponible`.
  - Con `core.enabled = false` → `no_integrado`, sin crear el cliente, sin llamar y sin registrar nada en el breaker (INF-U8-02).
  - Diseño: BR-U8-21; INF-U8-02; P-U8-09; NFR-U8-25, 31.
  - **Aceptación**: `uv run pytest case-management/tests/integration/test_credit.py case-management/tests/unit/test_core_client_readonly.py`:
    - mock detenido → `get_case` responde con `credit_status = no_disponible` dentro de su p99 (E6 de P-U8-09);
    - `core.enabled = false` y un doble que registra las llamadas → `no_integrado`, cero llamadas y el breaker sin fallos registrados;
    - 404 → `sin_credito`;
    - la guardia de U08-T01 (`test_core_client_readonly.py`) sigue en verde, ahora con código real en `credit.py`.

- [ ] **Paso 13 — API, arranque y apagado de `case-service`** (E)
  - `create_app` de U0 con las 9 rutas de F04 y F10: `submit_application`, `create_case`, `list_cases`, `list_persistent_failures`, `get_case`, `get_case_identifiers` (`cro` y `cumplimiento`), `record_explanation_view`, `record_decision` y `retry_case`. Usa los scopes y audiencias de U2. `list_cases` excluye `vencido` salvo con `state=vencido`.
  - Logs `case.viewed` y `case.retry_requested` con la allowlist de U0 §8. En cada 401/403, `authz.denied` y `vectra_authz_denied_total`.
  - Readiness (`/readyz`, 8081) solo con `case-db`; liveness solo del proceso.
  - Arranque con `vectra_common.ops_server.run_service(app)` y espera de ≤ 10 s. Al recibir `SIGTERM`, barridos y reconciliador dejan de tomar trabajo y terminan el lote. El `preStop` de 5 s es del chart (Paso 20, U08-T05).
  - Etiquetas de métricas dentro de la allowlist de P-U8-06, y contadores de conjunto cerrado creados en 0.
  - Diseño: BR-U8-13, 13b; P-U8-03, 06; INF-U8-04, 06; NFR-U8-21, 22, 42, 45. Historias: US-107, US-108.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/integration/test_app.py case-management/tests/integration/test_degradation.py case-management/tests/integration/test_service_shutdown.py`:
    - bandeja con casos en `listo`, `en_sincronizacion`, `no_disponible` y `modelo_congelado`; el `GET` de un caso no listo no trae `score` (US-107);
    - `model_frozen_after_recommendation=true` en la consulta → solo los casos marcados; `false` → solo los no marcados (BR-U8-13);
    - detalle para `analista` → sin `sex` ni `socioeconomic_stratum`, y con el log `case.viewed`;
    - `get_case_identifiers` para `cumplimiento` → solo `identifiers` y `anonymized`, sin solicitud ni recomendación; para `analista` → 403; caso anonimizado → `anonymized = true` sin `identifiers`;
    - una fila de P-U8-03 por prueba: `case-db` en `default_transaction_read_only` → 503 sin efecto y `Ready`; governance, scoring, registro o core caídos → `Ready`;
    - `GET /metrics` recién iniciado muestra cada combinación de los contadores en 0, y ninguna etiqueta fuera de la allowlist;
    - PBT-U0-07 en modo strict sobre `case.viewed` y `case.retry_requested`;
    - una ruta sin scope → 403 con `authz.denied`;
    - `SIGTERM` durante un lote del reconciliador → el lote termina y no queda evidencia a medio enviar;
    - (de esta tarea) `python -m vectra_case.app` arranca de verdad, como proceso, con las variables obligatorias, y `/readyz` responde 200 con `case-db` arriba.

### Precisiones

- **Rutas de la aceptación.** El plan escribe algunas rutas relativas a `case-management/` (`tests/integration/…`). Los comandos de esta tarea y de los CA usan la ruta completa desde `vectra-risk/`.
- **Roles de base.** Cada consulta corre con el rol del proceso, nunca con superusuario: `case_app` para `case-service` y `case_worker` para lo que en las pruebas haga el papel del worker. Los grants de U08-T01 no cambian. Algunas consecuencias:
  - `case_app` no tiene `UPDATE` ni `DELETE` en `evaluation_jobs`, solo `SELECT, INSERT`. El trabajo nuevo de `retry` y del barrido es un `INSERT` simple (ver P-2).
  - `case_app` puede escribir en `cases` solo `state`, `attempts`, `model_frozen_after_recommendation` y `updated_at`. Cada `UPDATE` de `case-service` fija `updated_at = now()` (ver P-4).
  - Si una prueba necesita un permiso que la migración no da, se reporta como hallazgo. No se cambia la migración en esta tarea.
- **`intake` y la purga (P-5 de la enmienda).**
  - La función de purga de `intake_keys` vencidas (30 días, BR-U8-02) se escribe ahora, sin CLI, en `vectra_case/retention.py`. La CLI completa es del Paso 16, que está en D.
  - La función corre con el rol `case_retention`, el único con `DELETE` sobre `intake_keys`.
  - PBT-U8-06 la llama para comprobar que la llave queda libre tras la limpieza.
- **Lectura de la recomendación persistida.** `cases.recommendation` (jsonb) se lee con `read_wire(Recommendation, raw)` de U00-T03, nunca con el token ni con `model_construct`. `views.case_detail` la recibe ya construida.
  - Rojo primero: en `main` sin U00-T03, la prueba de `get_case` de un caso `listo` falla. Con U00-T03 pasa.
  - El contrato `private-token` de `.importlinter` (o el que dejó U00-T03) sigue en `KEPT`.
- **`serving-config` en `case-service` (barrido).**
  - El barrido lee `GET /v1/serving-config` (F104; `case-service` tiene `governance:read-serving` en `realm.prod.yaml` y en `catalog.py`).
  - El cliente de governance completo es del Paso 14 (U08-T04, `case-worker`). Aquí entra solo la lectura de `serving-config` (ver P-1):
    - `deps.call` con timeout de 500 ms y el breaker de NFR-U8-31;
    - token `service_token.provider_from_env(audience, scopes)`;
    - caché ≤ 5 s con `If-None-Match`.
  - Lo escribe `vectra_case/governance_client.py`, para que U08-T04 lo extienda y no lo duplique.
  - **Tipo de U0.** Usa el `ServingConfig` de `main`, que ya trae `cutoff`, `low_confidence_threshold` y `channel_rules` (U04-T09). Una respuesta con la forma vieja falla la validación estricta y el barrido se salta el ciclo: falla cerrado, no mueve casos (ver la prueba del Paso 11).
  - Esto cierra para U8 la candidata «orden de despliegue» de U04-T09 (`CANDIDATAS.md`) en el código. El despliegue conjunto es de U08-T05 y U12.
- **Registro (reconciliador).**
  - El cliente de append (`POST /v1/entries`, scope `registry:append:case`) va con `deps.call`.
  - El doble del registro implementa BR-U3-05/06 y BR-U0-37, y vive en `case-management/tests/doubles/`.
  - NFR-U8-53 pide que pase «las pruebas de ejemplo de append de U3». Copia esos ejemplos de `decision-registry/tests/` a `tests/doubles/test_registry_double.py` y cita el archivo y la prueba de origen. No los importes por ruta: ninguna unidad importa las pruebas de otra, como ya hizo U08-T02 con los generadores de U0.
- **`first_evaluation` en el Paso 10.** La regla la aplica `evaluation`, que es de U08-T04. Lo que esta tarea prueba es que la entrada que arma y envía `case-service` lleva el valor que le corresponde según `cases.ever_degraded` y el intento. Si el campo no viaja en ninguna entrada que escriba `case-service`, la línea pasa a U08-T04 y se anota en la bitácora con su razón.
- **Rechazos de `validate_decision` (candidata F-04 de U08-T02).** Ver P-3.
- **`PersistentFailure.since` (P-3 de U08-T02).** Sale de `cases.updated_at`, que es la recomendación de esa tarea: en `no_disponible` nadie más escribe el caso.
  - Hay una prueba de integración: un caso en `no_disponible` → `GET /v1/cases/failures` trae `since` igual a la hora del cambio de estado.
  - La candidata F-05 de U08-T02 (`persistent_failure` con `since` ausente) deja de ocurrir en la práctica, porque `updated_at` es `NOT NULL`. Regístralo en `services.md` (ver la nota de documentación).
- **P-16 de la enmienda (pendiente).** No impide los handlers. `retry_case` y `list_persistent_failures` se implementan, por la regla 2 de la enmienda («Toda ruta del contrato de U0 conserva su handler») y por P-1 (a), que dice «(a) donde el handler es fino (U8…)». Lo que P-16 deja pendiente es mostrarlos en la consola y en kind (U10, U12).
- **Documentación.** Agrega a `aidlc-docs/construction/case-management/code/` un `services.md` con las decisiones de esta tarea:
  - P-1 a P-4;
  - la purga adelantada;
  - el reparto del cliente de governance;
  - los diferidos.

  `services.md` es el archivo que el Paso 18 (U08-T04) completa; aquí se crea con la sección del Bloque D.
- **Plan.** Marca `[x]` los Pasos 9 a 13 con `(U08-T03)`.
  - En el Paso 10, añade «alerta `CaseEvidenceDiscarded` diferida por la demo».
  - En el Paso 11, añade «métricas de retención diferidas por la demo».
- **Bitácora.** `bitacoras/U08-T03.md` lleva la salida **real** de cada comando, pegada como texto. Está prohibido dejar plantillas sin expandir (`{open(...).read()}`, `$(cat …)`, etc.); el revisor de U09-T04 lo marcó NARANJA.
- **`make -C case-management check`.**
  - Suma las pruebas de integración nuevas. La cobertura del 100 % de los cuatro módulos puros (U08-T02) se mantiene.
  - La cobertura de los módulos nuevos al 100 % es del Paso 18 (U08-T04). Aquí basta con que pasen y con anotar la cobertura medida en la bitácora.
  - Si el `check` pasa de 30 minutos sin carga, anótalo como candidata.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **La alerta `CaseEvidenceDiscarded`** y su prueba de `promtool` (Paso 10). Es un recorte E\*F de la enmienda (§3, U8, fila «10 `evidence`»: «Se difiere la alerta `CaseEvidenceDiscarded`»). Las alertas son del Paso 21 (U08-T05).
- **Las tres métricas de retención** del Paso 11 y NFR-U8-46 (§3, U8, fila «11»: «Se difieren las 3 métricas de retención»).
- **La CLI `case-retention`** y PBT-U8-08 (Paso 16, en D). Solo entra la función de purga de `intake_keys`.
- **Los Bloques E a I.** Cliente de scoring, `feature_spec`, `job_queue`, `evaluation`, `worker`, PBT-U8-01 y 05, mock, chart, alertas, Dockerfiles y Applications (U08-T04 y U08-T05).
- **El `preStop` y los values del chart** (Paso 20, U08-T05).
- **Cambios a U0** (`vectra_contracts`, `vectra_common`). Si un modelo o una función de U0 no encaja, se reporta; no se corrige aquí. Eso incluye las rutas del token que el revisor de U00-T03 dejó abiertas (`CANDIDATAS.md`, «R2-01 sigue abierta en parte»): esta tarea **no** importa `_minting` ni nada privado de `outcome`.
- **Cambios a las migraciones de U08-T01** y a sus pruebas, incluidas las candidatas F-01 (`guard_vencido`) y F-03 (`retention_runs.finished_at`) de U08-T01.
- **Las candidatas de PBT de U08-T02** (F-02 `make_row`, F-03 jitter): no son de este bloque.
- **La convención `principal_role` entre unidades** (candidata de U09-T03). Aquí se usa la allowlist de U0 §8 tal como está.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (§1, Bloque D, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U8, §4, §5.2, §6 P-1, P-5, P-11, P-16, §8)
- `aidlc-docs/construction/case-management/functional-design/business-rules.md` (BR-U8-01..04, 09..11, 13..19, 21)
- `aidlc-docs/construction/case-management/functional-design/business-logic-model.md` (PBT-U8-06, 07 y los ejemplos)
- `aidlc-docs/construction/case-management/functional-design/domain-entities.md` (§1, §2.1 `evaluation_jobs`, §3 evidencia)
- `aidlc-docs/construction/case-management/nfr-requirements/nfr-requirements.md` y `nfr-design/` (P-U8-02, 03, 04, 06, 07, 08, 09)
- `aidlc-docs/construction/case-management/infrastructure-design/infrastructure-design.md` (INF-U8-01, 02, 04, 06)
- `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py` (`_case()`, las 9 rutas)
- `contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py` (`read_wire`, después de U00-T03)
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (`Scope`, `ProblemCode`, `ProblemReason`, `REASON_ALLOWED_CODE`, `CreditStatus`)
- `contracts/python/vectra_common/src/vectra_common/` (`app_factory.create_app`, `deps`, `service_token`, `ops_server`, `metrics`, la allowlist de logs)
- `case-management/migrations/versions/0001_case_schema.py`, `0002_grants_and_rls.py` y `0003_guards.py` (U08-T01)
- `case-management/src/vectra_case/{case_fsm,backoff,decision,views,config}.py` (U08-T01 y U08-T02)
- `aidlc-docs/construction/case-management/code/logic.md` (U08-T02)
- `identity-edge/keycloak/realm/realm.prod.yaml` (clientes `case-service` y `case-worker`)
- `platform/network/flows.yaml` (F04, F07, F10, F16, F17, F104)
- `CANDIDATAS.md` (las entradas de U08-T01, U08-T02, U00-T03 y U04-T09 citadas arriba)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`, en serie, anotando `uptime` antes y después de cada uno. Sobre `main`, los CA-1 a CA-5 terminan hoy con código 4 (`ERROR: file or directory not found`): ese es el rojo esperado.

- [ ] **CA-1** — `intake` y PBT-U8-06 (Paso 9; BR-U8-01..04; US-101, US-102, US-109).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_intake.py case-management/tests/integration/test_intake.py -v
  ```
  Esperado: código 0, con PBT-U8-06 entera (la llave queda libre tras la purga) y cada línea de aceptación del Paso 9. **Rojo primero:** aceptar la misma llave con otro cuerpo hace fallar PBT-U8-06.

- [ ] **CA-2** — Evidencia, reconciliador y PBT-U8-07 (Paso 10; BR-U8-09, 15..19; US-108, US-501, US-502).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_evidence.py case-management/tests/integration/test_decision.py case-management/tests/integration/test_explanation_views.py case-management/tests/doubles/test_registry_double.py -v
  ```
  Esperado: código 0, con cada línea de aceptación del Paso 10 salvo la alerta diferida. **Rojo primero:** un reconciliador que cambia el payload en el reenvío hace fallar PBT-U8-07.

- [ ] **CA-3** — Barrido, `retry` y gauges (Paso 11; BR-U8-10, 11, 14; US-112).
  ```bash
  uv run pytest case-management/tests/integration/test_sweeps.py case-management/tests/integration/test_retry.py case-management/tests/integration/test_db_gauges.py -v
  ```
  Esperado: código 0, con las líneas que entran del Paso 11, más la del `serving-config` de forma vieja.

- [ ] **CA-4** — `credit` (Paso 12; BR-U8-21; INF-U8-02).
  ```bash
  uv run pytest case-management/tests/integration/test_credit.py case-management/tests/unit/test_core_client_readonly.py -v
  ```
  Esperado: código 0, con `no_disponible`, `no_integrado` (cero llamadas) y `sin_credito`.

- [ ] **CA-5** — API, degradación y apagado (Paso 13; BR-U8-13, 13b; P-U8-03, 06; US-107, US-108).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/integration/test_app.py case-management/tests/integration/test_degradation.py case-management/tests/integration/test_service_shutdown.py -v
  ```
  Esperado: código 0, con cada línea de aceptación del Paso 13 y el arranque real con `python -m vectra_case.app`. Es un proceso lanzado tal cual, no `runpy`: el revisor de U04-T09 marcó ese desvío como AMARILLO.

- [ ] **CA-6** — Las 9 rutas, sin handler de más ni de menos.
  ```bash
  uv run python -c "from vectra_case.app import build_app; build_app()" && uv run python -c "from vectra_contracts.routes import REGISTRY; assert len(REGISTRY['case-service']) == 9; print('OK')"
  ```
  Esperado: `create_app` no lanza nada (por U0, `create_app` falla si falta o sobra un handler), y la segunda orden imprime `OK`. Si el punto de entrada no se llama `build_app`, el comando se ajusta al nombre real y el cambio se anota en la bitácora. Hoy, en `main`, `vectra_case.app` está vacío.

- [ ] **CA-7** — Contratos de import-linter.
  ```bash
  uv run lint-imports --config case-management/.importlinter && ! grep -rn "_internal\|_minting\|CONSTRUCTION_TOKEN" case-management/src --include='*.py'
  ```
  Esperado: código 0, con todos los contratos `KEPT`, y el `grep` sin salida. El `grep` va solo sobre `*.py`, porque `.importlinter` tiene que nombrar el módulo que prohíbe (F-04 de U00-T03).

- [ ] **CA-8** — Documentación y plan.
  ```bash
  test -f aidlc-docs/construction/case-management/code/services.md && grep -n "P-5\|purga" aidlc-docs/construction/case-management/code/services.md && grep -nE "^- \[x\] \*\*Paso (9|1[0-3]) " aidlc-docs/construction/plans/case-management-code-generation-plan.md
  ```
  Esperado: `services.md` existe y nombra la purga adelantada. Salen cinco líneas del plan, cada una con `(U08-T03)`. Hoy `services.md` no existe.

- [ ] **CA-9** — `check` de la unidad y de las que tocan U8 (RL-4), en serie.
  ```bash
  make -C case-management check
  make -C contracts check
  ```
  Esperado: los dos terminan en código 0. `contracts` se corre aunque esta tarea no la cambie, porque U8 es su consumidor más amplio y U00-T03 acaba de cambiar `outcome`. Si `bench_gate` de contracts falla por carga, se anota con la carga (`uptime`) y una corrida aislada del bench en la rama y en la base. Ese fallo es la candidata conocida del bench, no esta tarea.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/property/test_intake.py`: PBT-U8-06.
- `tests/integration/test_intake.py`: las líneas del Paso 9.
- `tests/property/test_evidence.py`: PBT-U8-07.
- `tests/integration/test_decision.py` y `test_explanation_views.py`: las líneas del Paso 10.
- `tests/doubles/registry_double.py` y `tests/doubles/test_registry_double.py`: el doble y los ejemplos de append de U3, citados.
- `tests/integration/test_sweeps.py`, `test_retry.py` y `test_db_gauges.py`: las líneas del Paso 11.
- `tests/integration/test_credit.py`: las líneas del Paso 12.
- `tests/integration/test_app.py`, `test_degradation.py` y `test_service_shutdown.py`: las líneas del Paso 13 y el arranque real.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U08-T03.md`, con la salida pegada. Como mínimo los de CA-1, CA-2 y la lectura de la recomendación persistida (ver Precisiones). El par falla-pasa es la prueba.

Los nombres de paquete de prueba no deben chocar con los de otras unidades (candidata F-06 de U07-T03): si hace falta un `__init__.py`, el paquete lleva un nombre propio de U8.

---

## Notas

- Archivos que se **modifican en su sitio**: los módulos vacíos de U08-T01 (`intake.py`, `evidence.py`, `sweeps.py`, `credit.py`, `db_gauges.py`, `api.py`, `app.py`, `db.py`, `metrics.py`, `governance_client.py` y `retention.py`, este último solo con la purga) y las casillas del plan. Nada de duplicados con sufijo.
- `evaluation.py`, `job_queue.py` y `worker.py` siguen vacíos (U08-T04).
- PBT-U8-01..08 nunca se recortan. En esta tarea entran la 06 (Paso 9) y la 07 (Paso 10), enteras.
- Cada `UPDATE` sobre `cases` lleva la guarda de estado (`WHERE state = …`). Los triggers de U08-T01 (`guard_transition`, `guard_vencido`) son la segunda defensa, no la primera.

---

## Preguntas abiertas

Si no hay respuesta, rige la recomendación.

- **P-1 — Cliente de `serving-config` en esta tarea o en U08-T04.** El barrido del Paso 11 (`case-service`) necesita leer `serving-config`, pero el plan pone el cliente de governance en el Paso 14 (`case-worker`).
  - **(a) Recomendada:** escribir aquí solo la parte de `serving-config` de `governance_client.py` (500 ms, breaker, caché ≤ 5 s con `If-None-Match`). U08-T04 le añade `feature_spec` y el cliente de scoring.
  - (b) Un puerto inyectado con un doble en las pruebas, y el cliente real en U08-T04. `case-service` no arrancaría completo hasta U08-T04.
- **P-2 — La fila de `evaluation_jobs` al escalar** (candidata F-02 de U08-T01). Es la duda de si el escalamiento a `no_disponible` (y el paso a `modelo_congelado`) borra el trabajo, para que el `INSERT` de `retry` y del barrido no choque con el índice único sobre `case_id`.
  - **(a) Recomendada:** sí, se borra. La migración ya lo da por hecho («el trabajo se borra al terminar (BR-U8-07), así que toda fila está viva»), y `case_app` no tiene `UPDATE` ni `DELETE` en `evaluation_jobs`, así que no puede hacer un upsert. Se precisa en domain-entities §2.1 y lo implementa el worker en U08-T04. Aquí:
    - `retry` y el barrido hacen un `INSERT` simple;
    - si aun así choca con una fila viva, la transacción se revierte y la respuesta es `409 conflict_state`, sin cambio de estado, con una prueba;
    - se anota en `services.md`.
  - (b) Dar a `case_app` `UPDATE` en `evaluation_jobs` y usar `ON CONFLICT (case_id) DO UPDATE`. Toca la migración y los grants de U08-T01.
- **P-3 — Las razones de los rechazos de `validate_decision`** (candidata F-04 de U08-T02). `Rechazo.reason` usa valores fuera de `ProblemReason` (`used_factors_not_in_shap_vector`, `decision_incoherent_with_outcome`), y `REASON_ALLOWED_CODE` no admite `reason` con `validation_error`.
  - **(a) Recomendada:** la respuesta HTTP lleva solo el `code` (422 `validation_error` o 409 `conflict_state`), sin `reason`. La razón interna no sale a la red ni a los logs de negocio, y queda documentada en `services.md`. No cambia U0.
  - (b) Añadir las dos razones a `ProblemReason` en U0, lo que cambia OpenAPI y TS (otra tarea de U0).
- **P-4 — De dónde sale `PersistentFailure.since`** (P-3 de U08-T02, que quedó sin respuesta).
  - **(a) Recomendada:** `cases.updated_at`, con cada `UPDATE` de U8 fijando `updated_at = now()` y una prueba de integración.
  - (b) Una columna `no_disponible_since`. Toca la migración y los grants de U08-T01.
