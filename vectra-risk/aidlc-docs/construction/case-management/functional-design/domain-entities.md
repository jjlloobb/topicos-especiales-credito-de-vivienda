# Entidades de dominio — U8 `case-management`

Decisiones del plan (`case-management-functional-design-plan.md`, Q1–Q11 = A). Los tipos
del contrato (`ApplicationIn`, `CaseRef`/`CaseSummary`/`CaseDetail`, `DecisionIn`,
`DecisionRef`, `ScoringRequest`, `RecommendResult`) son de U0 y no se repiten aquí. Este
documento define cómo los guarda y los usa case-service.

---

## 1. Caso

### 1.1 `Case` (tabla `cases`)

| Campo | Tipo | Notas |
|---|---|---|
| `case_id` | UUID | Generado por case-service. Es también la referencia externa del crédito en el core (Q8) |
| `state` | `en_evaluacion \| listo \| en_sincronizacion \| no_disponible \| modelo_congelado \| decidido \| vencido` | Máquina de estados de business-rules §3 |
| `channel` | `str` | Del catálogo de canales, o `manual` (US-102) |
| `created_by` | `{kind: user \| service, id}` | Analista (alta manual) o cliente del canal (ingesta) |
| `created_at`, `updated_at` | timestamp | — |
| `application` | JSON | `ApplicationIn` **sin** el grupo de identificación de U0 §1.1, que vive en `case_identifiers` (§1.2) |
| `test_scenario_id` | `str?` | Solo fuera de producción y solo si `azp = channel-simulator` (BR-U8-03). Nunca sale hacia scoring ni hacia el registro |
| `escalation_count` | `int` | Escalamientos del caso; es el `ciclo` de la llave de `fail_closed` (BR-U8-09) (precisado el 2026-10-06) |
| `attempts` | `int` | Intentos de evaluación del ciclo actual (se reinicia a 0 en `retry` y al descongelar) |
| `last_cause` | causa de U0, o una causa local: `serving_config_unavailable` (falló la lectura de `serving-config` o del `feature_spec`), `scoring_unreachable` (timeout, conexión o 5xx) o `scoring_rejected` (4xx no reintentable) | La última del ciclo; la entrada de escalamiento la lleva como `local_cause` cuando es local (BR-U8-08, 09) (precisado el 2026-10-06, revisión del FD de U8) |
| `recommendation` | JSON `Recommendation?` | La recibida de scoring, completa (con `Explanation`). Solo en `listo` y `decidido` |
| `recommendation_entry_id` | `str?` | `registry_entry_id` de esa `Recommendation` (P-U7-03) |
| `model_frozen_after_recommendation` | `bool` | Lo marca el barrido de BR-U8-14 |
| `anonymized_at` | timestamp? | Fecha de eliminación de los identificadores (BR-U8-20) |

### 1.2 `CaseIdentifiers` (tabla `case_identifiers`)
- Contiene `case_id` y los campos de identificación de U0 §1.1: `full_name`, `document_type`, `document_number`, `birth_date`, `phone`, `email`, `address` y `municipality_code`.
- Está separada para que la eliminación de BR-U8-20 sea un `DELETE` de una fila, sin reescribir `cases`.
- `department_code` se queda en `cases.application`, porque lo usa `derive` para la región.
- `derive` necesita `birth_date` y `municipality_code` (edad, región, búsquedas permitidas del `feature_spec`). Por eso solo se evalúan casos que todavía no están anonimizados. Un caso anonimizado está `decidido` o `vencido`, así que no vuelve a evaluarse.

### 1.3 `IntakeKey` (tabla `intake_keys`)
`scope` (`client_id` del canal, o `user_id` en el alta manual), `idempotency_key`, `body_sha256`, `case_id` y `created_at`, con clave única (`scope`, `idempotency_key`) (BR-U8-02). El CronJob `case-retention` borra las filas de más de 30 días (precisado el 2026-10-06, revisión del FD de U8).

### 1.4 `RetentionRun` (tabla `retention_runs`)
Una fila por corrida de `case-retention`: `run_id`, `started_at`, `finished_at?`, `status` (`exitosa` \| `fallida`), `anonymized_count`, `expired_count` (casos que pasaron a `vencido`) y `overdue_remaining` (casos con la retención vencida que conservan identificadores o `free_text` al terminar; por ejemplo, filas que la API tenía tomadas, NFR-U8-46). Solo `case_retention` inserta (sin `UPDATE` ni `DELETE`): la fila se escribe al terminar, con `started_at` y `finished_at`. `case_app` solo la lee, para las métricas `vectra_case_retention_last_success_timestamp` y la alerta `CaseRetentionOverdue` (agregado el 2026-10-06 por U8 NFR Requirements).

### 1.5 `RetentionSettings` (tabla `retention_settings`)
Una sola fila (`CHECK (id = 1)`): `decided_years`, `undecided_years`, `intake_keys_days`, `created_at` (de la primera migración, no cambia; es el valor de `vectra_case_retention_last_success_timestamp` antes de la primera corrida) y `updated_at`. La escribe solo `case_migrator`, con el Job de migración, desde los values de Helm (`retention.*`). `case_retention` y `case_app` solo la leen. Es la única fuente de los plazos para el job, el trigger `guard_vencido` y las métricas de retención (agregado el 2026-10-08 por U8 NFR Design, Q2; P-U8-05).

## 2. Evaluación

### 2.1 `EvaluationJob` (tabla `evaluation_jobs`)

| Campo | Notas |
|---|---|
| `case_id` | Un solo trabajo vivo por caso (índice único parcial) |
| `attempt` | 0..6: 0 en un trabajo recién creado; **cada toma** lo incrementa y lo copia a `cases.attempts`, incluida la retoma tras un arrendamiento vencido. `CHECK (attempt BETWEEN 0 AND 6)`: la toma lee el valor antes de escribir y, si ya vale 6, escala **sin incrementar** (BR-U8-07; precisado el 2026-10-08, revisión del plan de tareas de U8; precisado el 2026-10-08, segunda revisión del plan de tareas de U8) |
| `run_at` | Siguiente ejecución (BR-U8-07) |
| `locked_until` | Lo fija el worker que lo toma (`FOR UPDATE SKIP LOCKED`) |

### 2.2 Lectura de gobierno (Q1)
- **`serving-config`**: se usan `model_version_id` y `state`. Caché ≤ 5 s con `If-None-Match`, como en scoring (BR-U7-01).
- **`FeatureSpec`**: el `feature_spec.json` de la versión, con sus tablas de búsqueda. Viene de `GET /v1/models/{id}/feature-spec` (BR-U4-19), que solo leen los clientes con `governance:read-feature-spec`. Es inmutable por versión, así que se cachea sin expiración (LRU de 4 versiones).

## 3. Evidencia hacia el registro

### 3.1 `EvidenceOutbox` (tabla `evidence_outbox`; evidencia en dos fases, Q5)

| Campo | Notas |
|---|---|
| `evidence_id` | UUID |
| `case_id` | — |
| `entry_type` | `human_decision \| explanation_view \| fail_closed` |
| `idempotency_key` | UUID fijo de la escritura (U3 BR-U3-06), **determinista** por hecho de negocio: `human_decision` → UUIDv5(`case_id`, "human_decision"); `explanation_view` → UUIDv5(`case_id`, `user_id`) (Q6); `fail_closed` → UUIDv5(`case_id`, "fail_closed", ciclo) (precisado el 2026-10-06). **Índice único parcial** `UNIQUE (idempotency_key) WHERE state <> 'abandonada'`, con la misma lógica que el de `decisions`: una evidencia viva por llave, y una decisión nueva tras un abandono puede insertar su fila con la misma llave (BR-U8-18). Es el índice que produce el `unique_violation` de BR-U8-09 (precisado el 2026-10-08, segunda revisión del plan de tareas de U8) |
| `payload` | `RegistryEntryIn` sin `occurred_at`, con el `correlation_id` original de la solicitud que lo originó (precisado el 2026-10-06, revisión del FD de U8). El reconciliador fija `occurred_at` en cada intento (BR-U3-05); el momento de negocio va dentro del payload (precisado el 2026-10-06) |
| `state` | `pendiente_registro \| confirmada \| abandonada` (a las 24 h, BR-U8-18) |
| `registry_entry_id` | Al confirmar |
| `attempts`, `next_attempt_at` | Del reconciliador (BR-U8-18) |

### 3.2 `Decision` (tabla `decisions`)
`case_id` (índice único parcial sobre las decisiones `pendiente_registro` o `confirmada`, para que una `abandonada` no impida decidir de nuevo; precisado el 2026-10-06), `decision`, `final_outcome`, `used_factors`, `justification`,
`explanation_viewed_before`, `decided_by`, `decided_at`, `evidence_id` (→ `evidence_outbox`)
y `state` (`pendiente_registro \| confirmada \| abandonada`, el mismo de su evidencia).

### 3.3 `ExplanationView` (tabla `explanation_views`)
`case_id`, `user_id`, `first_viewed_at` y `evidence_id`, con clave única (`case_id`,
`user_id`) (BR-U8-19).

## 4. Vistas hacia el BFF (amplían U0 §1.2)

| Tipo | Agrega |
|---|---|
| `CaseSummary` | `applicant_display` (BR-U8-13b). `score` y `outcome` solo en `listo` y `decidido` (BR-U8-13) |
| `CaseDetail` | `application` (de `cases.application`, sin `sex` ni `socioeconomic_stratum`; BR-U8-13b), `identifiers?` (de `case_identifiers`; ausente si el caso está anonimizado) (precisado el 2026-10-06, revisión del FD de U8), `recommendation?` (solo en `listo` y `decidido`), `decision?`, `credit_status?` (§5), `model_frozen_after_recommendation`, `anonymized` (`bool`), `attempts` y `last_cause` (para `en_sincronizacion` y `no_disponible`) |
| `PersistentFailure` | `case_id`, `channel`, `created_at`, `attempts`, `last_cause`, `since` (fecha de entrada a `no_disponible`) |

Los identificadores salen en `get_case` hacia el BFF, para el detalle del analista y del `cro`
(BR-U8-13b) y para el expediente de `cro` y `cumplimiento` (U3 FD Q7). La bandeja solo lleva
`applicant_display`. `sex` y `socioeconomic_stratum` no salen en ninguna vista del analista (precisado el 2026-10-06, revisión R1 del FD de U8).

## 5. `core-banking-mock`

| Entidad | Campos |
|---|---|
| `Credit` | `case_id` (referencia externa), `status` (`en_estudio \| aprobado \| desembolsado \| rechazado \| cancelado`), `updated_at`. Datos sembrados por fixtures de prueba |
| `CreditStatus` (lo que ve case-service) | `status` del core, o `no_disponible` si el core no respondió a tiempo **o si `core.enabled = false`** (producción en el MVP, sin llamar; precisado el 2026-10-08 por INF-U8-02), o `sin_credito` si no existe (BR-U8-21) |
| `WriteAttempt` | `at`, `source_identity`, `outcome = rechazado` (403 por scope). Solo para la evidencia de RT-5 (BR-U8-22) |

## 6. Errores

| Situación | Respuesta |
|---|---|
| Validación de `ApplicationIn` o `DecisionIn` | 422 `validation_error` (BR-U0-30, sin valores) |
| Misma `Idempotency-Key` con otro cuerpo | 409 `conflict_state` |
| `X-Test-Scenario` en producción | 400 `validation_error` |
| Decisión sobre un caso que no está `listo` (incluido `vencido`), segunda decisión o decisión pendiente | 409 `conflict_state` |
| Consulta de la explicación sobre un caso que no está `listo` ni `decidido` (incluido `vencido`) | 409 `conflict_state` |
| `retry` sobre un caso que no está `no_disponible` (incluido `vencido`) | 409 `conflict_state` |
| Decisión nueva cuando la abandonada sí estaba en el registro | 409 `conflict_state`, `reason = decision_already_recorded` (BR-U8-18) |
| Registro sin confirmar una decisión | 503 `dependency_unavailable` (la decisión queda `pendiente_registro`) |
| Rol sin permiso | 403 (BR-U0-71) |
