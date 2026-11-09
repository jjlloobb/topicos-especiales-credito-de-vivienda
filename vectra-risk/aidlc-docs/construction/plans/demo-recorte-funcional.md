# Enmienda al alcance de la demo: recorte funcional «solo lo que usan las demos» (U3–U12, salvo U5)

**Estado: APROBADO por el usuario el 2026-11-09**, con la recomendación de cada pregunta de §6 (P-1 a P-20). P-16 no tenía recomendación y queda **pendiente**: mientras no se decida, `PersistentFailures` y `retry` siguen diferidos. Enmienda a
`aidlc-docs/construction/plans/demo-kind-alcance.md` (en adelante «el alcance»). No cambia §1, §2, T1–T6
ni DD-1..DD-4. Solo afina la tabla de §3 y propone cómo aplicar RL-1 (§6). U5 no se toca. De U3 solo
entran los Pasos 11–20, porque los Pasos 1–10 ya están hechos.

Rutas relativas a `vectra-risk/`. Abreviaturas:
- «plan Ux» = `aidlc-docs/construction/plans/<unidad>-code-generation-plan.md`;
- «BR-U12» = `aidlc-docs/construction/system-verification/functional-design/business-rules.md`;
- «matriz» = `contracts/openapi/role-endpoint-matrix.md`.

## 0. Resumen

1. **El recorte funcional ahorra poco código de servicio.** `create_app` (U0,
   `contracts/python/vectra_common/src/vectra_common/app_factory.py`, `create_app`) dice «Falla si falta
   o sobra un handler» y compara con `REGISTRY[service_name]`. El catálogo `ProblemCode` no tiene `501`
   ni `not_implemented`. Por eso una ruta del contrato no se puede diferir sin una de tres cosas: un
   stub, un cambio en U0 o un contrato parcial (§5, P-1). Además, las PBT que entran cubren casi todas
   las ramas que parecían recortables, como el `orchestrator` de U7 (PBT-U7-07), `retry` y el
   vencimiento de U8 (PBT-U8-01) o el reconciliador (PBT-U4-01, PBT-U8-07).
2. **Lo que sí se difiere** (§3):
   - US-306 completa, es decir, fuentes de datos y `source_comparison` en U4. U10 difiere sus vistas;
     U9 no puede quitar sus rutas.
   - `applicant-summaries` (U7 Pasos 6 y 9) y sus vistas en U10.
   - En U3: 5 de 6 CronJobs, 4 de 5 subcomandos de la CLI, la bóveda y `decision-registry-rebuild`.
   - `retire_inference_service` y el CronJob de retención de U8.
   - Unas 12 vistas de la SPA.
   - En U12: RT-1/RT-4 en el simulador, `LOGS-NO-PII` y `network`.
   - La mutación donde el alcance no aplicó T3.
   - La mayoría de los escenarios en kind.
3. **El ahorro de tareas viene de fusionar bloques**, no del recorte: con bloques más pequeños cabe
   juntarlos. Se pasa de **64 a 42 tareas** (§4). La fusión va más allá de lo que hoy permite RL-1
   («un bloque de un solo paso puede juntarse con el siguiente»), así que exige decidir P-2.

## 1. Cadenas de llamadas por demo

Notación: `Ux artefacto` → `Uy artefacto` (flujo de U1). Todo lo que U12 hace como persona pasa por el
BFF, con login OIDC sin navegador visible (plan U12 Paso 5). U12 no tiene cliente de governance.

### 1.0 Flujo base (lo comparten las cuatro)

1. Arranque, una vez. **No está asignado a ninguna tarea (§5, P-7):**
   - Política activa: `cro-2` hace `POST /api/console/policies` y `cro-1` hace
     `POST /api/console/policies/{id}/approval`, que llegan a U4 `POST /v1/policies` y
     `…/approval`. Fuente: runbook de kind en plan U4 Paso 16; BR-U4-10 y 11. Sin política `activa`,
     `serving-config` no tiene `policy_version_id`.
   - Modelo de referencia: `POST /api/console/models` → `…/validations` (Job `model-validation-job`,
     K01; `PUT /v1/models/{id}/validation-report` por F32) → `…/approval`, y después `promotion-tool`
     (`create_promotion_pr`, `mark_active` → `POST /v1/models/{id}/activation`, F08). Fuente: plan U4
     Pasos 10, 12 y 13.
2. Ingesta:
   - U12 `simulator` (`normal`) → gateway → U8 `POST /v1/intake/applications`, con `Idempotency-Key` y
     la cabecera de escenario (BR-U12-02; plan U8 Paso 9).
   - U8 `case-worker` (`job_queue`, `evaluation`) → U4 `GET /v1/serving-config` y
     `GET /v1/models/{id}/feature-spec` (F104) (plan U8 Pasos 14 y 15).
3. Puntuación:
   - U8 → U7 `POST /v1/recommendations` (F15). U7 consulta la caché de `serving-config` (≤ 5 s) y
     llama a U6 `:predict` (F19) (plan U7 Pasos 10 y 11).
   - U7 scoring → U7 `POST /v1/explanations` (F20) → U4 `feature-dictionary` (F103) y U6 `:explain`
     (F22). Fuente: plan U7 Paso 8; plan U6 Pasos 3, 4 y 6.
   - U7 → U3 `POST /v1/entries` (`recommendation`, F21). El caso queda `listo`.
4. Decisión del analista. U12 `driver` (`analista-1/2`) o el presentador en la SPA (`CasesInbox`,
   `CaseDetail`, `ExplanationPanel`, `DecisionForm`; plan U10 Paso 13) → U10 BFF:
   - `GET /api/console/cases` y `GET /api/console/cases/{id}`;
   - con probabilidad `p_view`, `POST …/explanation-views`;
   - `POST …/decision`.

   El BFF llama a U8 `GET /v1/cases*` y `POST …/decision|explanation-views` (F10). U8 registra la
   evidencia en dos fases y el reconciliador hace `POST /v1/entries` (plan U8 Paso 10; BR-U12-03;
   business-logic-model U12 §2.2).

### 1.1 D1 · Journey 7.3: desincronía forzada (RT-3, `journey-7-3.md`)

Fuentes: BR-U12-04 (RT-3); business-logic-model U12 §2.1, punto 7; plan U12 Paso 8.

| Paso | Cadena |
|---|---|
| RT3-a, c, d | `ingeniero-1` → BFF `POST /api/console/models` → U4 `POST /v1/models` → `registration` (plan U4 Paso 6) → **422**; `serving-config` no cambia |
| RT3-a, d sin registrar | PR preparado (`demos/prs/`) con un `InferenceService` → U6 `package_loader` (plan U6 Paso 2) → no listo con `ModelPackageIntegrityFailed` |
| RT3-b | BFF `POST /models` → `…/validations` → U4 `model-validation-job` (`sync_check`, plan U4 Paso 13) → `validacion_fallida`. Si pasa: `cro-1` aprueba → `promotion-tool` → U7 `FailClosed(explainer_error \| feature_dictionary_incomplete)` → rollback |
| **F22 apagado (la evidencia de la demo)** | PR solo de kind en `platform/network/flows.yaml` (F22, `explainability-service` → `explainer`; `env_disabled.kind`, comentario en las líneas 5–6). Se regeneran `platform/network/generated/kind/` y desaparecen 2 NetworkPolicy, `MeshTLSAuthentication` y `AuthorizationPolicy`. U7 explainability → 504/503 → U7 scoring `FailClosed(timeout \| explainer_unavailable)` (breaker, plan U7 Pasos 10 y 11) → U8 worker `en_sincronizacion` con backoff (plan U8 Pasos 5 y 15) → `no_disponible` al intento 6 (≈ 12,4–19,3 min). U8 escribe `fail_closed` en el outbox y el reconciliador lo registra en U3. El gauge `vectra_cases_failclosed_persistent` dispara `FailClosedPersistente` (U1, `platform/observability/rules/platform-rules.yaml`), que es el «escala como incidente técnico» |
| Oráculo | U12 → U3 `GET /v1/entries` (proyección `metrics`, `verification-reader`): cero `recommendation`. La SPA muestra `en_sincronizacion` con refresco de 3 s (BR-U10-10) |

### 1.2 D2 · Journey 7.4: freeze, paquete y resolución (RT-2, `journey-7-4.md`)

Fuentes: BR-U12-04 (RT-2), BR-U12-07, BR-U12-10; plan U12 Paso 8; DD-1 = 1 versión.

| Paso | Cadena |
|---|---|
| `rt2-setup` | `ingeniero-1` → BFF `POST /api/console/models` y `…/validations` (MFA) → U4 + `model-validation-job`. La `initial_disparity` sale de la **librería `vectra_disparity` de U9** (plan U4 §1; plan U9 Pasos 3 y 4). Después `cro-1` → BFF `…/approval` (MFA), con `cro-1` distinto de `registered_by` |
| Promoción | Operador: `promotion-tool` `create_promotion_pr` → sync → `mark_active` (F08) → espera `activo` en `GET /api/console/models` → `post_activation_pr` (plan U4 Paso 12; plan U6 Pasos 6 y 7) |
| Lote | U12 `simulator` `stratified` (≈ 1 500, ≥ 30 por celda; `sampler`, plan U12 Paso 3) → flujo base hasta U3 |
| Agregación | U3 CronJob `registry-aggregator` → `vectra-registry aggregator run` cada 5 min (plan U3 Pasos 11 y 12; BR-U3-17). Llena `monitoring_daily`, `monitoring_case_index` y la marca de agua |
| Freeze | U9 CronJob `vectra_bias.run` → U3 `POST /v1/monitoring/daily:query` y `GET /v1/monitoring/freezes` → `window`, `freeze_rule`, `context` (plan U9 Pasos 6–8) → U4 `POST /v1/models/{id}/freeze` (F27). U4 agrega `data_sources` e `initial_disparity` (BR-U9-16; BR-U4-15) y registra `freeze` en U3 |
| Casos nuevos | U4 `serving-config` (≤ 6 s, plan U4 Paso 9) → U7 `FailClosed(model_frozen)` → U8 `modelo_congelado`. El barrido de 5 min marca los `listo` (plan U8 Paso 11; BR-U8-10 y 14) |
| Paquete en vivo | `cumplimiento-1` en la SPA: `Freezes` y `FreezeContextView` (plan U10 Paso 14) → BFF `GET /api/console/freezes` y `…/freezes/{id}` → U9 `GET /v1/freezes` y `/v1/freezes/{id}` (F14; plan U9 Paso 9) |
| Resolución | `ResolveFrozenDialog` con step-up MFA (plan U10 Pasos 10 y 11) → BFF `POST /api/console/models/{id}/frozen-resolution` → U4 `frozen-resolution` (`reactivar`, BR-U4-03). El barrido de U8 devuelve los `modelo_congelado` a `en_evaluacion`. U9 `window` (BR-U9-08) evita que se recongele ese día |
| Oráculo | U12 → U3 `GET /v1/entries` (proyección `monitoring_freezes`): `FreezeContext` completo más `data_sources` e `initial_disparity`. `rt2_latency` ≤ 1 800 s |
| Cierre | `promotion-tool` `rollback_pr` y `mark_active` al modelo de referencia (BR-U12-07; plan U4 Paso 12) |

### 1.3 D3 · RT-5 (`rt-5.md`)

| Paso | Cadena |
|---|---|
| Preparación | U12 `prepare` genera `runId` y el parche de `probes.runId` en `vectra-risk-gitops/values/kind/case-management` (plan U12 Paso 13). El operador abre el PR y sincroniza |
| Estímulo | U8 Job `rt5-demo-<runId>` (plan U8 Paso 20; INF-U8-03), con la SA de `case-service` → U8 `core-banking-mock` `POST /v1/credits/{id}/status` → **403 de Linkerd** en `core-mock-catch-all` |
| Lecturas | U8 alerta `CoreWriteAttempt` (plan U8 Paso 21); `vectra_core_write_attempts_total` en 0 desde el arranque (plan U8 Paso 17); U1 `inbound_http_authz_deny_total` |
| Oráculo | U12 `rt5` → Prometheus `query_range` sobre [t0, t1 + 15 min] y log del Job con `l5d-proxy-error` (plan U12 Paso 8) |

### 1.4 D4 · Dashboard: North Star y ruido (`dashboard.md`)

| Paso | Cadena |
|---|---|
| Día D | U12 `decisions`: 2 000 `normal` más el `driver` (§1.0, punto 4), antes de RT-2 (BR-U12-06) |
| Cálculo | U11 `collector` → U3 `GET /v1/entries` (proyección `metrics`, `human_decision`, paginada por `seq`) → `compute` y `noise` (plan U11 Pasos 3, 4 y 6). Se publican junto con las recording rules generadas (`:dedup`, `complete_response_ratio`, `desync_failclosed:rate1h`; plan U11 Paso 12) |
| Día D + 1 | El presentador abre Grafana `product.json` (plan U11 Paso 13; BR-U11-12) y ve North Star, sostenida, tasa de consulta y `vectra_product_noise_days_below_floor`. U12 `u11` lee las métricas. `RuidoExplicacion` se verifica con `promtool` y reloj simulado, no en kind (BR-U12-06) |

### 1.5 Lo que ninguna demo ejercita

| Unidad | Rutas, comandos o vistas |
|---|---|
| U3 | `vectra-registry verify`, `checkpoint`, `archive`, `aggregator reset` y `--until-head`; los CronJobs `registry-checkpoint`, `registry-verify-*` y `registry-archive`; `chart-rebuild/`; `x06-probe`; las políticas HCL de Transit |
| U4 | `GET/POST /v1/data-sources`, `…/comparisons`, `…/decision` y `PUT /v1/validation-runs/{id}/source-counts` (US-306); el modo `source_comparison`; `compare_source` (F25); `retirement`; `retire_inference_service`; `model-archive` |
| U7 | `POST /v1/applicant-summaries`; `applicant` |
| U8 | `POST /v1/cases` (alta manual), `GET /v1/cases/failures`, `POST …/retry`, `GET …/identifiers`, el mock `GET /v1/credits/{id}` y la CLI `case-retention` |
| U9 | `GET /v1/disparity` y `POST /v1/source-comparisons` |
| U10 | `cases/failures`, `retry`, `POST /cases`, `applicant-summary`, `dossier`, `integrity-checks`, `data-sources*`, `POST policies` (sí lo usa el arranque, §1.0), `retirement`, `client-errors`. Vistas: `ManualApplicationForm`, `PersistentFailures`, `ApplicantSummaryButton`, `Dossier`, `IntegrityCheck`, `RegisterModelForm`, `ApproveModelDialog`, `ValidationReportView`, `Policies`, `DataSources`, `PrePostReportView`, `DecideDataSourceDialog`, retiro, `GrafanaEmbed`, `VersionBanner` |
| U12 | `simulator` `rt1`/`rt4`, `network`, `rt1`, `rt4`, `load`, `pii`, `resilience` y X01–X10 |

## 2. Reglas de esta enmienda

1. **E\*F** = el paso entra solo con la funcionalidad nombrada en «Entra». Lo demás, incluidas sus
   líneas de aceptación, se difiere. Una PBT que entra se corre entera. Si una PBT depende de código
   diferido, se nombra en §3 y en §5.
2. **Toda ruta del contrato de U0 conserva su handler** mientras P-1 no diga otra cosa. Se pueden
   diferir vistas, CLI, CronJobs, modos y clientes salientes, pero no rutas entrantes.
3. Las pruebas que miden y no son PBT (mutación, benchmarks, volumen, Lighthouse) caen en T3 también
   donde la tabla del alcance marcó E. Pasa en U3 Paso 16, U4 Paso 19, U6 Paso 3, U7 Paso 7, U8 Paso 8,
   U9 Pasos 5 y 10, U10 Pasos 4, 16 y 21, U11 Pasos 5 y 7, y U12 Paso 4.
4. `test_traceability.py --all` corre con la lista de «diferido por la demo» que registra
   `cierre-demo.md` (§5, P-4).

## 3. Tabla por unidad

Columnas: la del **alcance** y la **propuesta**. Solo se detallan los pasos que cambian o que necesitan
aclaración; los demás siguen en E.

### U3 `decision-registry` (Pasos 11–20)

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 11 CLI | E | **E\*F** | Entran el entrypoint `vectra-registry` y `aggregator run` con el tope de 240 s. Se difieren `verify`, `checkpoint`, `archive`, `aggregator reset` y `--until-head`. Casi toda la aceptación de `test_cli.py` es de lo diferido | D2 |
| 12 CronJobs, identidades, bóveda | E\* | **E\*F** | Entran el módulo agregador (**hoy no existe**: `queries.py` solo lee `monitoring_daily`), el CronJob `registry-aggregator`, su SA, `pg-role-registry-aggregator`, `test_aggregator.py` (**PBT-U3-09**) y el conftest del CronJob. Se difieren los 5 CronJobs restantes, `test_ondemand.py`, `chart-rebuild/` y **las políticas HCL** (P-6) | D2 |
| 13 Chart, buckets, flujos | E\* | E\*F | Entran el Deployment (T6), el `ServiceMonitor` y la comprobación de flujos. Se difieren los values de buckets y Transit | Todas |
| 14 Alertas | D | D | T2 | — |
| 15 Applications | E | **E\*F** | Entra `decision-registry` (wave 5). Se difieren `decision-registry-rebuild`, `rebuild-history.yaml`, `rebuild-runid-check.yml` y la comprobación de wave 6 | — |
| 16 Cobertura y trazabilidad | E\* | E\* | Mutación (T3); trazabilidad con lista de diferidos (BR-U3-08 y 13b) | — |
| 17 Benchmarks | D | D | T3 | — |
| 18 Kind | E\* | **E\*F** | Un escenario: wave 5, readiness, appends del flujo base, agregador con atraso 0 y `daily:query` > 0 tras los 2 000 casos. Se difieren los escenarios 1–7 y 9, y en el 8 la suspensión de 35 min, el rebuild y los silencios | D2, D4 |
| 19 N/A · 20 Cierre | N/A · E\* | N/A · E\* | — | — |

### U4 `governance`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–7 | E | E | Completos. La migración 2 se queda entera (el `freeze` y el registro leen `data_sources`) | Todas |
| 8 Evidencia, reconciliador, barridos | E | **E\*F** | Entran las dos fases, la excepción de `freeze`, el reconciliador (P-U4-02, puntos 1–4), el barrido en modo `validacion` y PBT-U4-07. **PBT-U4-01** entra sin el invariante de `source_candidate_for` (P-5). Se difiere la rama `source_comparison` del barrido. La línea `promtool` de `CompensationEventPending` depende de P-3 | Todas |
| 9 | E | E | — | Base, D2 |
| 10 Endpoints | E | **E\*F** | Entran modelos (registrar, validar, informe, aprobar, `activation`, lista y detalle), `freeze`, `frozen-resolution`, `feature-dictionary`, `feature-spec`, `serving-config` y las 3 rutas de políticas (§1.0). Se difieren `data-sources*`, `comparisons`, `decision`, `source-counts`, `source_candidate_for`, `compare_source`, `pre_post_report` y `start_source_comparison`, con sus líneas de aceptación; sus handlers dependen de P-1. `retirement`: P-8 | Todas |
| 11 | E | E | — | — |
| 12 `promotion-tool` | E | **E\*F** | Entran `list_promotable`, `create_promotion_pr`, `post_activation_pr`, `rollback_pr` y `mark_active`. Se difiere `retire_inference_service` | D1, D2 |
| 13 `model-validation-job` | E | **E\*F** | Entra el modo `validacion` (AUC, `initial_disparity` con **la librería real de U9**, `sync_check`, F32). Se difiere el modo `source_comparison` | D1, D2 |
| 14 · 15 | D · D | D · D | T4 · T5 | — |
| 16 Chart, flujos, RBAC | E\* | **E\*F** | Entran Deployment (T6), hook de migración, `pg-role-gov-app`, `minio-governance`, RBAC K01, runbook de política en kind (P-9) y la ruta `freeze` solo para `bias-monitoring-job`. Se difieren el CronJob `model-archive`, `pg-role-gov-archiver`, `minio-model-archive`, F100 y los values de staging de INF-U4-05 | Todas |
| 17 | E\* | E\* | Solo `docs/slo.md` (salvo P-3) | — |
| 18 | E | E | — | — |
| 19 | E\* | E\* | Mutación y k6 (T3); trazabilidad con lista (BR-U4-13 parcial) | — |
| 20 Kind | E\* | **E\*F** | Entran los escenarios 2 (validación de referencia), 3 (promoción), 4 (rollback) y 7 (freeze ≤ 6 s). Se difieren el 1, 5, 6, 8 y 9 | Base, D1, D2 |
| 21 · 22 | N/A · E\* | N/A · E\* | — | — |

### U6 `model-serving`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1, 2, 4 | E | E | El semáforo de concurrencia entra | Base, D1 |
| 3 Predictor | E | **E\*F** | Entran el contrato y PBT-U5-04. Se difiere `tests/bench -m benchmark` (T3) | Base |
| 5 Dockerfiles | E\* | E\*F | T1, más la prueba sobre el SBOM (la cubre import-linter) y `kyverno test` de imagen sin firma | Base |
| 6, 7, 8 | E | E | Plantilla con perfiles `prod`, `inactive` y `staging`; los PR de `promotion-tool`; F19, F22, F30 y F46. El PR de retiro comparte esquema y prueba: entra igual | Base, D1, D2 |
| 9 Alertas | D | D | Salvo P-3 (`ModelPackageIntegrityFailed`) | ¿D1? |
| 10 | E | E | Trazabilidad con lista (P-U6-06) | — |
| 11 Kind | E\* | **E\*F** | Entran los escenarios 1 (promoción), 2 (rollback) y 3 (RT3-a/d no listos, b listo). Se difieren el 4 (saturación), 5 (drenado) y 6 (carga) | D1, D2 |
| 12 · 13 | N/A · E\* | N/A · E\* | Sin benchmark | — |

### U7 `scoring-explainability`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–5 | E | E | `narrative` y `factuality` son necesarias: sin `factuality_check = passed` no hay `Ready` (BR-U0-02; BR-U7-10 y 11) | Base, D4 |
| 6 `applicant` | E | **D** | Con **PBT-U7-06** y su código. Nadie más lo usa | — |
| 7 Resumen | E | **E\*F** | Sin `mutmut` (T3) | — |
| 8 `/v1/explanations` | E | E | Mapear la conexión descartada (F22 apagado) a 504/503 y nunca a 500. Ya cabe en la aceptación del Paso 8 (riesgo R-3) | Base, D1 |
| 9 `/v1/applicant-summaries` | E | **D** | Se difieren el cliente F23, la regla 409 y el log. El handler depende de P-1 | — |
| 10, 11, 13 | E | E | **Todas las ramas del `orchestrator`** (PBT-U7-07 y 08) | Base, D1, D2 |
| 12 Endpoints | E | **E\*F** | `/v1/recommendations` y `/v1/explanations`. `/v1/applicant-summaries` según P-1 | Base |
| 14 · 15 | E\* | E\* | T1 · T6 | — |
| 16 | D | D | T2 | — |
| 17 | E\* | E\* | Carga (T3); trazabilidad con lista (BR-U7-13 y 14, NFR-U7-03) | — |
| 18 Kind | E\* | **E\*F** | Entran los escenarios 5 (promoción → 0 `version_mismatch`), 7 (freeze → `model_frozen` ≤ 6 s) y el humo del flujo base. Se difieren el 1–4, 6, 8 y 9 (P-10) | D2 |
| 19 · 20 | N/A · E\* | N/A · E\* | Sin los Pasos 6 y 9 | — |

### U8 `case-management`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–7 | E | E | Completos (`retry` y `vencido` en `case_fsm` por PBT-U8-01) | Todas |
| 8 Resumen | E | **E\*F** | Sin `mutmut` (T3) | — |
| 9 `intake` | E | E | Incluye el alta manual (handler obligatorio; PBT-U8-06). **Ojo** con la purga de `intake_keys` (P-5) | Base |
| 10 `evidence` | E | **E\*F** | Entra el reconciliador completo (registra los `fail_closed` de D1), con PBT-U8-07. Se difiere la alerta `CaseEvidenceDiscarded` | D1, D4 |
| 11 `sweeps`, `retry`, `db_gauges` | E | **E\*F** | Entran el barrido (D2), `retry`, `vectra_cases_failclosed_persistent` (D1) y `vectra_case_jobs_overdue`. Se difieren las 3 métricas de retención | D1, D2 |
| 12 `credit` | E | E | `credit_status` es obligatorio en `CaseDetail` y `core.enabled = true` en kind (P-11) | — |
| 13–15 | E | E | Las 9 rutas | Todas |
| 16 `case-retention` | D | D | Con PBT-U8-08 | — |
| 17 mock | E | E | Contador en 0 al arrancar | D3 |
| 18 Resumen | E | **E\*F** | Sin el umbral de `retention` | — |
| 19 | E\* | E\*F | T1, más la prueba sobre el SBOM | — |
| 20 Chart | E\* | **E\*F** | T6; entra el Job `rt5-demo`. **Se quita la plantilla del CronJob `case-retention`**, porque su CLI está en D (P-12) | D3 |
| 21 Alertas | E\* | E\* | `CoreWriteAttempt`, más la prueba del nombre de `vectra_cases_failclosed_persistent` | D3, D1 |
| 22 Documentación | E | **E\*F** | `api.md` y `check_openapi.py`. Se difieren `retention.md` y el conftest de la firma en `values/prod` | — |
| 23 | E\* | E\* | k6 (T3); trazabilidad con lista (BR-U8-20) | — |
| 24 Kind | E\* | **E\*F** | Entran el escenario 1 (suite de conectividad), el 5 (PBT-U8-07 abreviado contra el registro real) y el 7 (RT-5, ver P-13). Se difieren el 2, 3, 4, 6 y la carga | D3, D4 |
| 25 · 26 | N/A · E\* | N/A · E\* | — | — |

### U9 `bias-monitoring`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–4, 6–8 | E | E | Completos. `publish` y la población humana entran por PBT-U9-05 y P-U9-01 | D2 |
| 5 · 10 Resúmenes | E | **E\*F** | Sin `mutmut` (T3). La simulación estadística del Paso 5 se queda (P-14) | — |
| 9 Servicio | E | E | `/v1/freezes` y `/{id}` (D2). `/v1/disparity` y `compare` entran porque `create_app` los exige; PBT-U9-07 | D2 |
| 11 | E\* | E\*F | T1. «Sin numpy» se comprueba con `pip list` en la imagen, no en el SBOM | — |
| 12 | E\* | E\* | T6; `x04-probe` (T5) | D2 |
| 13 · 15 | D · D | D · D | — | — |
| 14 | E\* | E\* | k6 (T3) | — |
| 16 Kind | E\* | **E\*F** | Entran el escenario 1 (conectividad), el 3 (RT-2 con 1 medición) y el 5 (duración y memoria, que miden DD-3). Se difieren el 4 y E1–E5 y E7 en kind | D2 |
| 17 · 18 | N/A · E\* | N/A · E\* | — | — |

### U10 `console`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–3, 5–8, 10 | E | E | **Las 30 rutas del BFF** (P-1, opción a). Casi todas son de paso; PBT-U10-01 recorre las 30 | Todas |
| 4 · 16 | E | **E\*F** | Sin `mutmut` ni Stryker (T3) | — |
| 11 | E | E | `auth` y `stepup` (PBT-U10-05). `inactivity`: P-15 | D1, D2 |
| 12 | E | **E\*F** | `api`, `i18n` completo (PBT-U10-06) y `reporter`. Se difiere `version`/`VersionBanner` (P-15) | Todas |
| 13 Casos | E | **E\*F** | Entran `CasesInbox`, `CaseDetail`, `RecommendationSummary`, `ExplanationPanel`, `ApplicationView`, `CreditStatusBadge`, `DecisionForm` y PBT-U10-04. Se difieren `ManualApplicationForm`, `PersistentFailures`/`retry` (P-16), `ApplicantSummaryButton`, `Dossier` e `IntegrityCheck`, con sus ejemplos | Base, D1 |
| 14 Gobierno y sesgo | E | **E\*F** | Entran `RoleMenu`, `Freezes`, `FreezeContextView`, `ResolveFrozenDialog` y `Models`/`ModelDetail` de lectura. `BiasDashboard` (`DisparityTables`) según P-14. Se difieren `Policies`, `DataSources`, `PrePostReportView`, `DecideDataSourceDialog`, `RegisterModelForm`, `ApproveModelDialog`, retiro y `GrafanaEmbed`. Las rutas de la SPA por rol se declaran todas, con un marcador en las diferidas (P-17) | D2 |
| 15 CSP, a11y, e2e | E | **E\*F** | Sobre las vistas que entran | D1, D2 |
| 17 · 18 | E\* | E\* | T1 (más las etapas `previous` si se difiere `version`) · T6 | — |
| 19 · 20 | D | D | — | — |
| 21 | E\* | E\* | k6 y Lighthouse CI (T3); trazabilidad con lista | — |
| 22 Kind | E\* | **E\*F** | Entran el escenario 1 (PoC y Playwright con Keycloak real: login y step-up de `cumplimiento-1`) y el 2 (conectividad F03, F10, F11, F14). Se difieren aprobador ≠ proponente, el 3–6 y NVDA | D1, D2 |
| 23 · 24 | E · E\* | E · E\* | — | — |

### U11 `product-metrics`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1–4, 6, 8 | E | E | Todas las PBT (01–07) | D4 |
| 5 | E | **E\*F** | Sin `mutmut` (T3) | — |
| 7 | E | **E\*F** | Entran los ejemplos con E/S. Se difiere la prueba de volumen (`-m volume`, T3; no es PBT) | — |
| 10 · 11 | E\* | E\* | T1 · T6 | — |
| 12 Reglas | E\* | E\* o **E** | Entran las reglas generadas. Las 4 alertas y su `promtool` dependen de P-3 | D4 |
| 13 | E\* | E\* | `product.json` completo; runbooks (T2) | D4 |
| 14 | D | D | — | — |
| 15 · 17 · 18 | E · E · E\* | igual | — | — |
| 16 Kind | E | **E\*F** | Entran el 5 (métricas D + 1), el 4 (permisos de carpeta, si el presentador usa `cro-1`/`cumplimiento-1`) y el 1 (conectividad mínima). Se difieren el 2 (E1–E8) y el 3 (rollouts) | D4 |

### U12 `system-verification`

| Paso | Alcance | Propuesta | Entra · se difiere | Demo |
|---|---|---|---|---|
| 1 · 2 | E | E | — | Todas |
| 3 | E | E | `sampler`, `rt2_latency`, `story_map` y `report` (PBT-U12-01, 02, 04) | D2, informe |
| 4 | E | **E\*F** | Sin `mutmut` (T3) | — |
| 5 | E | E | — | Todas |
| 6 | E | **E\*F** | Entran el `simulator` `normal` y `stratified` y el `driver` (PBT-U12-03). Se difieren los escenarios `rt1` y `rt4` | D2, D4 |
| 7 | D | D | — | — |
| 8 | E\* | E\* | RT-2 (1 versión), RT-3 y RT-5 | D1–D3 |
| 8b · 9 · 11 | D | D | — | — |
| 10 | E\* | **E\*F** | Entra `SIM-NORMAL`, que verifica el flujo base de D4. Se difieren `LOGS-NO-PII` (ninguna demo; P-18) y `CASE-SIZE` | D4 |
| 12 Demos | E | E | Los cuatro guiones, `verify/*.sh` y los PR preparados (F22 con `env_disabled.kind`, P-19) | Todas |
| 13 CLI | E\* | **E\*F** | Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`). El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`). Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D | Todas |
| 14 · 15 | N/A · E\* | N/A · E\* | — | — |
| 16 | D | D | — | — |
| 17 | E | **E\*F** | README de lo que entra; trazabilidad con lista | — |
| 18 · 19 | E\* | E\* | Con las secciones del Paso 13 | — |

## 4. Conteo de tareas (RL-1)

«Actual» = bloques con algún paso E o E\* según el alcance. «Propuesta» = bloques fusionados (P-2).

| Unidad | Actual | Propuesta | Fusión propuesta (en orden de dependencias) |
|---|---|---|---|
| U3 (11–20) | 5 | **3** | E (11–12) · F+G (13, 15, 16) · H+I (18–20) |
| U4 | 9 | **6** | A+B · C · D (8–11) · E (12–13) · F+G (16–19) · H+I (20–22) |
| U6 | 6 | **3** | A+B (1–5) · C+D (6–8, 10) · E+F (11–13) |
| U7 | 7 | **5** | A · B (3–5, 7) · C+D (8, 10–13) · E (14, 15, 17) · F+G (18–20) |
| U8 | 9 | **6** | A+B · C · D (9–13) · E+F (14, 15, 17, 18) · G (19–23) · H+I (24–26) |
| U9 | 7 | **5** | A+B (primero: la librería la usa U4 Paso 13) · C · D · E (11, 12, 14) · F+G |
| U10 | 7 | **5** | A+B · C+D (5–9) · E (10–16) · F (17, 18, 21) · G+H (22–24) |
| U11 | 6 | **4** | A+B · C+D · E (10–13, 15) · F+G (16–18) |
| U12 | 8 | **5** | A+B (1–4) · C (5–6) · D (8, 10) · E+F (12, 13, 15, 17) · G+H (18–19) |
| **Total** | **64** | **42** | — |

Notas:
- Sin fusionar bloques (RL-1 tal como está), el recorte funcional solo quita el Bloque C de U7 en
  la práctica, porque C se queda con un único paso y se junta con D. El total bajaría a unas **62**.
  El recorte aligera las tareas, pero no reduce su número.
- Bloques que conviene **no** juntar porque pasarían de 2 rondas (RL-2):
  - U4 D (dos PBT stateful y convergencia con 2 réplicas);
  - U8 D (Pasos 9–13);
  - U9 C con D (cuatro PBT compuestas);
  - U10 E (el Paso 10 es la puerta de los Pasos 11–15).
- Alternativas más conservadoras: U8 a 7 (E y F por separado), U10 a 6 (E partido en 10–12 y 13–16) y
  U4 a 7. Con ellas el total queda en **45**.

## 5. Riesgos

### 5.1 Parece recortable, pero rompe una demo

| Recorte tentador | Por qué no | Demo |
|---|---|---|
| Rutas sin demo de U4, U7, U8, U9 y U10 | `create_app` no arranca. Sin servicio no hay demo | Todas |
| Agregador de U3 (hoy no existe código) | Sin él, `daily:query` sale vacío, U9 falla con `agregador_atrasado` y no hay `freeze`. Además gasta hasta 5 min del margen de RT-2 (≈ 27 de 30 min) | D2 |
| Políticas de U4 (o una semilla por migración) | Sin política activa no hay `serving-config`. La semilla viola BR-U4-17, BR-U4-12 y «sin atajo» (plan U4 Paso 16) | Base |
| Librería de U9 en el job de validación de U4 (dejar el doble) | `initial_disparity` saldría vacía y el oráculo de RT-2 falla | D2 |
| `post_activation_pr` y `rollback_pr` | RT-2 y su cierre los usan | D2 |
| `data_sources` en el `freeze` | El oráculo exige el campo, aunque vaya vacío | D2 |
| Ramas del `orchestrator` de U7 | `model_frozen`, `timeout`, `explainer_unavailable` y `version_mismatch` son D1 y D2; además PBT-U7-07 | D1, D2 |
| Reconciliador de U8 | Es la única vía que registra los `fail_closed` de D1 | D1, D4 |
| Barrido de U8 | Sin él, los `modelo_congelado` no vuelven tras la reactivación | D2 |
| `window` de U9 | «No se recongela» es un oráculo de RT-2 | D2 |
| Rutas de modelos del BFF «porque son de D2» | RT3-b también las usa | D1 |
| Step-up y CSP con Trusted Types (U10 Pasos 10, 11 y 15) | Sin ellos no hay reactivación en vivo | D2 |
| `credit` de U8 | `credit_status` es obligatorio en `CaseDetail` | Base |

### 5.2 PBT

- **Entran todas:**
  - U3: PBT-U3-09.
  - U4: PBT-U4-01..07; la 01 sin el invariante de `source_candidate_for`.
  - U6: PBT-U5-04 y la propiedad de la suma.
  - U7: PBT-U7-01..05, 07 y 08.
  - U8: PBT-U8-01..07.
  - U9: PBT-U9-01..08.
  - U10: PBT-U10-01..06.
  - U11: PBT-U11-01..07.
  - U12: PBT-U12-01..04.
- **Se difieren con su código:** PBT-U7-06 (`applicant`) y PBT-U8-08 (`case-retention`, ya en D).
- **Choques con la regla «las PBT no se recortan»:**
  - **PBT-U8-06** exige que, tras la limpieza de 30 días, la llave quede libre. Esa purga la hace la
    CLI diferida (P-5).
  - **PBT-U4-01** tiene un invariante de `source_candidate_for`, que pertenece a US-306 (P-5).

### 5.3 Dependencias en runtime de la ruta crítica (alcance §4)

- **U9 antes de U4 en kind:** el Bloque B de U9 (`vectra_disparity`) tiene que estar fusionado antes
  de la verificación en kind de U4 (escenario 2) y de `rt2-setup`. Hoy la ruta crítica pone U9 después
  de U8. Se propone adelantar la tarea U9 A+B en paralelo con U4 (RL-5).
- **Arranque del modelo de referencia y de la política:** ningún plan asigna quién lo hace ni cuándo
  (U6 Paso 11 solo dice «un paquete de U5 registrado») (P-7).
- **U12 → U4:** la aceptación de U12 Paso 13 usa `branch-protection-check` de U4 Paso 14, que está en
  D.
- **U12 → U3/U9:** el parche de `prepare` apunta a tres values, dos de ellos de Jobs diferidos.
- **U8 Paso 24 → U12:** el Job `rt5-demo` necesita el `runId` de `prepare`, pero U8 se verifica en
  kind antes que U12 (P-13).
- **T6 frente a la admisión:** `require-hpa-bounds` (`platform/policies/kyverno/`) y los conftest
  exigen `minReplicas ≥ 2` en `vectra-app`/`vectra-serving`, y T6 pide 1 réplica. En D2 conviven el
  isvc activo, el proxy y los de staging, así que el riesgo es la memoria. Se resuelve con DD-3 b
  (medir), pero hay que confirmarlo antes de U6.
- **Tiempos de D1:** `no_disponible` tarda entre ≈ 12,4 y 19,3 min, y el guion debe esperar al menos
  ≈ 19,3. Los casos `no_disponible` y `FailClosedPersistente` quedan activos durante D2 y D4 si nadie
  los limpia (P-16).
- **Calendario de D4:** `day` es «ayer completo» y `decisions` no empieza después de las 23:00 UTC. Si
  D + 1 cae en día 1 del mes, falta `month_to_date`. North Star vale 0 si el `driver` nunca abre la
  explicación.
- **Vigencia de la política de U5:** `reference-policy.json` debe tener una vigencia normativa que
  cubra la fecha de la demo. Si no, todos los casos salen `revision_requerida` (BR-U4-11).

## 6. Preguntas abiertas

| Id | Pregunta | Recomendación |
|---|---|---|
| **P-1** | Rutas del contrato sin demo (U4 US-306, U7 `applicant-summaries`, U8 alta manual, `failures`, `retry`, `identifiers`, U9 `disparity` y `compare`, y las 30 del BFF): (a) se implementan, (b) stub con un código nuevo `not_implemented` en U0, (c) stub con un código existente, o (d) `create_app(contract=subconjunto)` | **(a)** donde el handler es fino (U8, U9, U10, U4 `retirement` y políticas). Para U4 US-306 y U7 `applicant-summaries`, elegir entre (a) y (b). La (b) cambia U0 y regenera OpenAPI y TS; la (d) rompe `check_openapi.py` y PBT-U10-01 |
| **P-2** | ¿Se amplía RL-1 para fusionar bloques contiguos (no solo los de un paso), con un máximo de unos 6 pasos con código por tarea? | **Sí**: es lo que lleva de 64 a 42. Es una enmienda a §6 |
| **P-3** | Excepciones a T2 que pide una aceptación o una demo: `CompensationEventPending` (U4 Paso 8), las 4 alertas de U11 (`RuidoExplicacion` y `ProductMetricsStale` en BR-U12-06) y `ModelPackageIntegrityFailed` (U6, si `journey-7-3` la muestra) | Entran las de U11 y `CompensationEventPending` como reglas con `promtool`. Sus runbooks, solo si `runbook_url` lo exige. La de U6 solo si el guion la enseña |
| **P-4** | `test_traceability.py --all` falla con BR diferidos (solo acepta «Diferido a `<unidad>`») | Una lista de «diferido por la demo» registrada en `cierre-demo.md` y aceptada por la prueba. Toca `platform/tests/test_traceability.py` (U1) |
| **P-5** | PBT-U8-06 (purga de `intake_keys`) y el invariante de `source_candidate_for` en PBT-U4-01 dependen de código diferido | U8: adelantar la función de purga al Paso 9, sin CLI. U4: diferir ese invariante con US-306 y registrarlo como excepción explícita |
| **P-6** | Políticas HCL de U3: el alcance las mete, pero solo las usan checkpoint y archivo | Diferirlas |
| **P-7** | ¿Quién arranca el modelo de referencia y la política en kind, y en qué tarea? | En la tarea H+I de U4 (escenarios 2 y 3), con su runbook, antes de U6 Paso 11 |
| **P-8** | `POST /v1/models/{id}/retirement` | Mantenerlo: es un handler fino y PBT-U4-01 lo modela |
| **P-9** | El runbook de política de U4 Paso 16 dice «`ingeniero-1` proponiendo», pero la matriz y BR-U4-10 exigen `cro` | Corregirlo a `cro-2` propone y `cro-1` aprueba |
| **P-10** | ¿U7 Paso 18 ensaya D1 (F22 apagado) o lo deja a U12? | Dejarlo a U12 Paso 18 |
| **P-11** | `credit` de U8: ¿se mantiene, o se pone `core.enabled = false` en kind? | Mantenerlo |
| **P-12** | CronJob `case-retention` sin CLI: ¿se quita la plantilla o se agrega un value `retention.enabled` (que es nuevo)? | Quitar la plantilla |
| **P-13** | Evidencia de RT-5: ¿la da U8 Paso 24 con un `runId` manual, o solo U12 Paso 18? | U8 con un `runId` manual. La de U12 es la que cuenta |
| **P-14** | ¿`journey-7-4` muestra `BiasDashboard` (`/v1/disparity`) o solo el paquete? ¿Y la simulación estadística de U9 Paso 5? | Solo el paquete. La simulación se queda |
| **P-15** | `inactivity` (U10 Paso 11) y `version` con `previous` (Pasos 12 y 17): son controles sin demo | Diferir `version`. Mantener `inactivity`, que es un control de seguridad y es pequeño |
| **P-16** | El «escala como incidente técnico» de 7.3: ¿se muestra con `PersistentFailures` y `retry` (CRO)? Sirve también para limpiar los casos de RT-3 antes de D2 | Pregunta abierta. Si es «sí», entran esa vista y esas rutas en kind |
| **P-17** | Rutas de la SPA diferidas: ¿marcador «no disponible» o se acota la prueba «rutas por rol = C03»? | El marcador |
| **P-18** | `LOGS-NO-PII` (US-604) no es de ninguna demo, pero es barato y es la evidencia de privacidad | Pregunta abierta. Por la regla del usuario, diferir |
| **P-19** | El PR de F22: BR-U12-04 dice `enabled: false`, que lo apagaría en todos los entornos | Usar `env_disabled.kind` |
| **P-20** | El journey 7.4 del PRD habla de «nueva fuente», pero D2 usa un modelo proxy sin fuentes (BR-U12-04; FD de U12, nota de Q1). ¿Se acepta que la demo no muestre US-306? | Sí. Es la decisión que permite diferir US-306 |

## 7. Tareas en curso al aprobar la enmienda

- **U03-T04** (Pasos 11 y 12 de U3) ya tenía implementados `verify`, `archive`, `worm` y las políticas HCL cuando se aprobó la enmienda. Ese código se queda, porque ya está probado y quitarlo cuesta más que conservarlo; P-6 rige para el trabajo nuevo. `checkpoint` se difiere con el Paso 11 (§3, U3). La decisión de diseño sobre su firma (opción A: firmar el `recorded_at` de la entrada cubierta, usuario, 2026-11-09) queda registrada en `CANDIDATAS.md` para el cierre completo.
