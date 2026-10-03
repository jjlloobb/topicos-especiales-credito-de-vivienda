# Entidades de dominio — U8 `case-management`

Decisiones del plan (`case-management-functional-design-plan.md`, Q1–Q9 = A). Los tipos
del contrato (`ApplicationIn`, `CaseRef`/`CaseSummary`/`CaseDetail`, `DecisionIn`,
`DecisionRef`, `ScoringRequest`, `RecommendResult`) son de U0 y no se repiten aquí. Este
documento define cómo los guarda y los usa case-service.

---

## 1. Caso

### 1.1 `Case` (tabla `cases`)

| Campo | Tipo | Notas |
|---|---|---|
| `case_id` | UUID | Generado por case-service. Es también la referencia externa del crédito en el core (Q8) |
| `state` | `en_evaluacion \| listo \| en_sincronizacion \| no_disponible \| modelo_congelado \| decidido` | Máquina de estados de business-rules §3 |
| `channel` | `str` | Del catálogo de canales, o `manual` (US-102) |
| `created_by` | `{kind: user \| service, id}` | Analista (alta manual) o cliente del canal (ingesta) |
| `created_at`, `updated_at` | timestamp | — |
| `application` | JSON | `ApplicationIn` **sin** el grupo de identificación de U0 §1.1, que vive en `case_identifiers` (§1.2) |
| `test_scenario_id` | `str?` | Solo fuera de producción (BR-U8-03). Nunca sale hacia scoring ni hacia el registro |
| `attempts` | `int` | Intentos de evaluación del ciclo actual (se reinicia a 0 en `retry` y al descongelar) |
| `last_cause` | causa de U0 o `scoring_unreachable` | Última causa de fail-closed recibida, o `scoring_unreachable` si scoring no respondió |
| `recommendation` | JSON `Recommendation?` | La recibida de scoring, completa (con `Explanation`). Solo en `listo` y `decidido` |
| `recommendation_entry_id` | `str?` | `registry_entry_id` de esa `Recommendation` (P-U7-03) |
| `model_frozen_after_recommendation` | `bool` | Lo marca el barrido de BR-U8-14 |
| `anonymized_at` | timestamp? | Fecha de eliminación de los identificadores (BR-U8-20) |

### 1.2 `CaseIdentifiers` (tabla `case_identifiers`)
- Contiene `case_id` y los campos de identificación de U0 §1.1: `full_name`, `document_type`, `document_number`, `birth_date`, `phone`, `email`, `address` y `municipality_code`.
- Está separada para que la eliminación de BR-U8-20 sea un `DELETE` de una fila, sin reescribir `cases`.
- `department_code` se queda en `cases.application`, porque lo usa `derive` para la región.
- `derive` necesita `birth_date` y `municipality_code` (edad, región, búsquedas permitidas del `feature_spec`). Por eso solo se evalúan casos que todavía no están anonimizados. Un caso anonimizado siempre está `decidido` o lleva más de 2 años sin decisión, así que no vuelve a evaluarse.

### 1.3 `IntakeKey` (tabla `intake_keys`)
`client_id`, `idempotency_key`, `body_sha256` y `case_id`, con clave única
(`client_id`, `idempotency_key`) (BR-U8-02).

## 2. Evaluación

### 2.1 `EvaluationJob` (tabla `evaluation_jobs`)

| Campo | Notas |
|---|---|
| `case_id` | Un solo trabajo vivo por caso (índice único parcial) |
| `attempt` | 1..6 |
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
| `idempotency_key` | UUID fijo de la escritura (U3 BR-U3-06). En `explanation_view` es un UUIDv5 de (`case_id`, `user_id`) (Q6) |
| `payload` | `RegistryEntryIn` completo, listo para el append |
| `state` | `pendiente_registro \| confirmada` |
| `registry_entry_id` | Al confirmar |
| `attempts`, `next_attempt_at` | Del reconciliador (BR-U8-18) |

### 3.2 `Decision` (tabla `decisions`)
`case_id` (único), `decision`, `final_outcome`, `used_factors`, `justification`,
`explanation_viewed_before`, `decided_by`, `decided_at`, `evidence_id` (→ `evidence_outbox`)
y `state` (`pendiente_registro \| confirmada`, el mismo de su evidencia).

### 3.3 `ExplanationView` (tabla `explanation_views`)
`case_id`, `user_id`, `first_viewed_at` y `evidence_id`, con clave única (`case_id`,
`user_id`) (BR-U8-19).

## 4. Vistas hacia el BFF (amplían U0 §1.2)

| Tipo | Agrega |
|---|---|
| `CaseSummary` | Nada. `score` y `outcome` solo en `listo` y `decidido` (BR-U8-13) |
| `CaseDetail` | `recommendation?` (solo en `listo` y `decidido`), `decision?`, `credit_status?` (§5), `model_frozen_after_recommendation`, `anonymized` (`bool`), `attempts` y `last_cause` (para `en_sincronizacion` y `no_disponible`) |
| `PersistentFailure` | `case_id`, `channel`, `created_at`, `attempts`, `last_cause`, `since` (fecha de entrada a `no_disponible`) |

Los identificadores directos solo salen en `get_case` hacia el BFF, y solo para el
expediente de `cro` y `cumplimiento` (U3 FD Q7). La bandeja nunca los incluye.

## 5. `core-banking-mock`

| Entidad | Campos |
|---|---|
| `Credit` | `case_id` (referencia externa), `status` (`en_estudio \| aprobado \| desembolsado \| rechazado \| cancelado`), `updated_at`. Datos sembrados por fixtures de prueba |
| `CreditStatus` (lo que ve case-service) | `status` del core, o `no_disponible` si el core no respondió a tiempo, o `sin_credito` si no existe (BR-U8-21) |
| `WriteAttempt` | `at`, `source_identity`, `outcome = rechazado` (403 por scope). Solo para la evidencia de RT-5 (BR-U8-22) |

## 6. Errores

| Situación | Respuesta |
|---|---|
| Validación de `ApplicationIn` o `DecisionIn` | 422 `validation_error` (BR-U0-30, sin valores) |
| Misma `Idempotency-Key` con otro cuerpo | 409 `conflict_state` |
| `X-Test-Scenario` en producción | 400 `validation_error` |
| Decisión sobre un caso que no está `listo`, segunda decisión o decisión pendiente | 409 `conflict_state` |
| Registro sin confirmar una decisión | 503 `dependency_unavailable` (la decisión queda `pendiente_registro`) |
| Rol sin permiso | 403 (BR-U0-71) |
