# Reglas de negocio — U8 `case-management`

Los IDs `BR-U8-xx` se referencian en los planes de tareas. La validación de los tipos
(BR-U0-20..36), `derive` (U0 §2.3) y las causas de fail-closed (BR-U0-01..08) son de U0:
U8 las **aplica**.

---

## 1. Ingesta y alta manual (US-101, US-102)

**BR-U8-01 — Validación.** `ApplicationIn` se valida con U0. Un error responde 4xx genérico
(BR-U0-30) y **no** crea caso. El gateway ya limita el tamaño (32 KiB) y la tasa (U2).

**BR-U8-02 — Idempotencia (Q9).**
- `POST /v1/intake/applications` exige la cabecera `Idempotency-Key`, única por cliente del canal.
- Misma llave y mismo `body_sha256` → el mismo `case_id` (200).
- Misma llave y otro cuerpo → `409 conflict_state`.
- La llave, el caso y su trabajo de evaluación se crean en **una** transacción.

**BR-U8-03 — Escenarios adversariales (Q9; US-101).**
- `X-Test-Scenario` (la pregunta decía `X-Vectra-Scenario`; se renombró porque el gateway elimina el prefijo reservado `x-vectra-`, U2 P-U2-06 precisado) solo se acepta si el cliente es el simulador **y** el despliegue tiene `allow_test_scenarios = true`. Ese valor es `false` en producción, fijado en los values y verificado por política.
- En producción la cabecera → 400.
- Se guarda como `test_scenario_id` y nunca se envía a scoring, al registro ni a los logs de negocio.

**BR-U8-04 — Alta manual.** Solo `analista` (US-102; otro rol → 403 y log `authz.denied`).
Canal `manual` y `created_by` = el usuario del token.

## 2. Evaluación (Q1, Q3; US-112)

**BR-U8-05 — Vector de la versión activa (Q1).** En **cada** intento:
1. leer `serving-config` (F104, caché ≤ 5 s);
2. si no responde → el intento termina como `serving_config_unavailable`, sin llamar a scoring;
3. obtener el `FeatureSpec` de esa `model_version_id` (F104, caché por versión);
4. `derive(application + identificadores, evaluated_at = ahora, feature_spec)` → `FeatureVector` y `MonitoringLabels`;
5. enviar `ScoringRequest` con `model_version_id` = la versión leída.

scoring compara ese `model_version_id` con su `serving-config`. Si difieren, responde
`FailClosed(version_mismatch)` sin invocar a KServe (BR-U0-02 precisada). El caso reintenta
con el backoff normal; la versión nueva ya será visible para los dos.

**BR-U8-06 — `ScoringRequest`.** Lleva:
- `case_id`;
- `features`;
- `monitoring_labels`;
- `policy_inputs` (`property_value`, `proposed_rate_ea`, `channel`);
- `attempt` (el número del intento);
- `model_version_id`.

Nunca lleva identificadores directos, `free_text` ni `test_scenario_id` (BR-U0-34, RT-1).

**BR-U8-07 — Backoff y cola (Q3).**
- Retraso del intento `n` (n = 1..5): `30 s · 2^(n−1)`, con jitter de ±20 %. Máximo 6 intentos, unos 31 min.
- El trabajo vive en `evaluation_jobs`. Los workers lo toman con `FOR UPDATE SKIP LOCKED` y `locked_until = ahora + 30 s`; si un worker muere, otro lo retoma al vencer ese plazo.
- Llamada a scoring: timeout de **7 s** (P-U7-02).
- La reprogramación y el cambio de estado van en la misma transacción.

**BR-U8-08 — Resultado de un intento.**

| Resultado | Efecto |
|---|---|
| `Recommendation` | Guardar la recomendación y `recommendation_entry_id = registry_entry_id`; pasar a `listo`; borrar el trabajo |
| `FailClosed` con `status = en_sincronizacion` | `last_cause = cause`; pasar a `en_sincronizacion`; reprogramar o escalar (BR-U8-09) |
| `FailClosed(model_frozen)` | Pasar a `modelo_congelado`; borrar el trabajo; `attempts = 0` |
| Timeout, error de conexión o 4xx/5xx de scoring | `last_cause = scoring_unreachable`; igual que `en_sincronizacion` (BR-U0-06: se tratan como reintentables) |

**BR-U8-09 — Escalamiento (Q3, Q4).** Cuando falla el intento 6:
- el caso pasa a `no_disponible` y aparece en `list_persistent_failures`;
- el gauge `vectra_cases_failclosed_persistent` cuenta los casos en `no_disponible` y dispara `FailClosedPersistente` (U1);
- case-service escribe **una** entrada `fail_closed` (por `evidence_outbox`) con `cause = last_cause` (o `timeout` si fue `scoring_unreachable`), `retryable = false` y `attempt = 6`.

Las entradas de cada intento las escribe scoring (BR-U7-16). case-service no las duplica.

**BR-U8-10 — Salida de `modelo_congelado` (Q2).**
- Un barrido cada 5 min lee `serving-config`.
- Si su `state` es `activo`, los casos en `modelo_congelado` pasan a `en_evaluacion` con `attempts = 0` y un trabajo nuevo.
- La versión activa puede ser otra, si cumplimiento resolvió el congelamiento con un rollback; el vector se arma con la versión de ese momento (BR-U8-05).

**BR-U8-11 — `retry` del CRO (Q2).**
- `POST /v1/cases/{id}/retry`, solo para `cro` y solo desde `no_disponible`; si el caso no está en ese estado → 409.
- Pasa a `en_evaluacion` con `attempts = 0` y un trabajo nuevo.
- Log `case.retry_requested` con el `user_id`.

## 3. Estados (Q2; US-107)

**BR-U8-12 — Transiciones.** Solo estas:

| De | Evento | A |
|---|---|---|
| — | Ingesta o alta manual válida | `en_evaluacion` |
| `en_evaluacion`, `en_sincronizacion` | `Recommendation` | `listo` |
| `en_evaluacion`, `en_sincronizacion` | Fail-closed reintentable o scoring sin respuesta, con intentos restantes | `en_sincronizacion` |
| `en_sincronizacion` | Fallo del intento 6 | `no_disponible` |
| `en_evaluacion`, `en_sincronizacion` | `FailClosed(model_frozen)` | `modelo_congelado` |
| `modelo_congelado` | Barrido: `serving-config` activo | `en_evaluacion` |
| `no_disponible` | `retry` del CRO | `en_evaluacion` |
| `listo` | Decisión confirmada en el registro (BR-U8-18) | `decidido` |

- `decidido` es terminal.
- Un caso `listo` **nunca** se reevalúa: hay una sola recomendación entregada por decisión, y así se cumple el supuesto de P-U7-03.
- Una transición que no está en la tabla se rechaza en la capa de dominio y también con un `CHECK` sobre la tabla de transiciones permitidas.

**BR-U8-13 — Visibilidad (US-107).** En los estados distintos de `listo` y `decidido`,
`CaseSummary` y `CaseDetail` no llevan `score`, `outcome`, `recommendation` ni
`explanation`. Un caso `en_sincronizacion` o `no_disponible` muestra `attempts` y
`last_cause`.

**BR-U8-14 — Congelamiento después de la recomendación (Q2).**
- El barrido de BR-U8-10 también marca `model_frozen_after_recommendation = true` en los casos `listo` cuya `recommendation.model_version_id` coincide con la versión que `serving-config` reporta `congelado`.
- El caso sigue `listo` y el analista puede decidir. La consola muestra el aviso (U10).

## 4. Decisión (Q5; US-108, US-502)

**BR-U8-15 — Quién y cuándo.**
- Solo `analista`; queda a nombre del llamante.
- Solo con el caso `listo`, sin otra decisión `pendiente_registro` ni `confirmada`. Si no → `409 conflict_state`.

**BR-U8-16 — Contenido.**
- **BR-U0-35** contra `cases.recommendation.outcome`.
- **`used_factors`**: subconjunto de los `feature_id` de `recommendation.explanation.shap_vector`, o exactamente `["ninguno"]`. Si no → 422.
- **`se_aparta`**: al menos un factor o `["ninguno"]`, más justificación (US-502).
- **`sigue`**: factores o `["ninguno"]` («sin uso de la explicación»).
- **Justificación**: obligatoria en `se_aparta` y `resuelve_revision`, de 20 a 2000 caracteres tras quitar los espacios del inicio y del final (BR-U0-36). En `sigue` es opcional.

**BR-U8-17 — `explanation_viewed_before`.** Es `true` si existe un `explanation_views`
del **mismo** usuario y caso con `first_viewed_at` anterior a la decisión.

**BR-U8-18 — Evidencia en dos fases.**
1. En una transacción: insertar `decisions` (`pendiente_registro`) y su `evidence_outbox` con una `idempotency_key` nueva.
2. Hacer el append de `human_decision`:
   - `payload`: `DecisionIn`, más `explanation_viewed_before` y `recommendation_entry_id = cases.recommendation_entry_id`;
   - sobre: `model_version_id` y `policy_version_id` de la recomendación y `actor` del token (US-108).
3. Con el ack, en una transacción: evidencia y decisión `confirmada` y caso `decidido`. Se responde `DecisionRef`.
4. Sin ack (503 o timeout del registro): se responde `503` y la decisión sigue pendiente.

El **reconciliador** reintenta cada evidencia pendiente con su misma llave y un backoff de
1 s a 5 min. Al confirmar, aplica el paso 3. Las entradas `explanation_view` y `fail_closed`
usan el mismo outbox y el mismo reconciliador; solo las decisiones cambian el estado del caso.

## 5. Consulta de la explicación (Q6; US-501)

**BR-U8-19 — Primera consulta.**
- `record_explanation_view` solo con el caso `listo` o `decidido` (si no → 409).
- La primera vez por (`case_id`, `user_id`): insertar `explanation_views` + `evidence_outbox` con `idempotency_key = UUIDv5(case_id, user_id)` y hacer el append de `explanation_view`.
- Las siguientes → 204, sin entrada nueva.
- La clave única y la llave derivada impiden duplicados en una carrera.
- La entrada lleva caso, usuario y momento, sin PII del solicitante.

## 6. Retención (Q7; NFR-U3-03)

**BR-U8-20 — Eliminación de identificadores.**
- **Plazos**:
  - casos `decidido`: 10 años desde la decisión **[VERIFICAR]**;
  - casos nunca decididos: 2 años desde la creación **[VERIFICAR]**, con cumplimiento y la Ley 1581.
- **Job diario**:
  - borra la fila de `case_identifiers`;
  - borra `cases.application.free_text`, que puede contener PII;
  - fija `anonymized_at`.
- Un caso no decidido conserva su estado, pero el job borra su trabajo de evaluación, si lo tiene. El barrido de BR-U8-10 y el `retry` de BR-U8-11 ignoran los casos anonimizados (`retry` → 409), porque `derive` ya no tendría los identificadores. No hay transición nueva.
- Desde entonces, `get_case` y el expediente salen sin identificadores (`anonymized = true`). El registro no se toca (NFR-U3-03).

## 7. Core bancario (Q8; FR-INT-01, US-603)

**BR-U8-21 — Lectura del estado de crédito.**
- `get_case` consulta `GET /v1/credits/{case_id}` (F17) solo para casos `decidido`, con timeout de 500 ms y sin caché.
- 404 → `sin_credito`; error o timeout → `no_disponible`. La respuesta de `get_case` nunca falla por el core.

**BR-U8-22 — Escritura imposible (RT-5).**
- case-service no tiene ningún cliente ni método de escritura hacia el core.
- El mock expone `POST /v1/credits/{id}/status` **solo** para la demostración: exige `core:write-credit`, que nadie tiene (U0 §7.2), responde 403 y guarda un `WriteAttempt`.
- X01 bloquea por red cualquier método distinto de `GET` y cualquier origen distinto de case-service.

## 8. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 domain-entities §9.1 `ScoringRequest` | Campo `model_version_id` (la versión cuyo `feature_spec` armó el vector) | Q1 |
| U0 BR-U0-01, BR-U0-02, business-logic-model §2.2, PBT-U0-01 | `check_preconditions` recibe `requested_model_version_id` y `serving_model_version_id?`; la causa 7 aplica también si difieren; en ese caso las ausencias de las causas 2, 5 y 8 no aplican, porque scoring no invocó nada (S2) | Q1 |
| U0 BR-U0-08 | «se reintenta con el caso» = el intento siguiente del caso produce su propia entrada; case-service escribe una sola entrada al escalar | Q4 |
| U0 nueva BR-U0-36 | Justificación de 20 a 2000 caracteres en `se_aparta` y `resuelve_revision` | Q5 |
| U0 §1.2 `CaseDetail` | Campos `model_frozen_after_recommendation`, `anonymized`, `attempts`, `last_cause` | Q2, Q7 |
| U0 §7.2 catálogo de scopes | `governance:read-serving` también para case-service; scope nuevo `governance:read-feature-spec` (case-service) | Q1 |
| U0 plan de tareas, Paso 6 | PBT-U0-01 con versión pedida igual o distinta | Q1 |
| U2 realm | Cliente `case-service`: scopes `governance:read-serving`, `governance:read-feature-spec`; audiencia `governance-service` | Q1 |
| U4 BR-U4-06, nueva BR-U4-19, domain-entities §1.1, plan de tareas Pasos 2 y 10 | governance guarda el `feature_spec` verificado al registrar y lo sirve en `GET /v1/models/{id}/feature-spec` | Q1 |
| U7 BR-U7-01, PBT-U7-07, plan de tareas Paso 11 | scoring compara `ScoringRequest.model_version_id` con `serving-config` antes de `:predict` | Q1 |
| U7 BR-U7-16 | case-service no duplica las entradas por intento | Q4 |
| U2 NFR Design P-U2-06 (cabeceras internas) | El prefijo `x-vectra-` queda reservado a cabeceras internas y el gateway lo elimina siempre (incluye `x-vectra-deadline` de U7) | Q9 |
| U0 y U3 (rango de validación) | `BR-U0-20..35` pasa a `20..36` en U0 business-logic-model, NFR Design, plan de tareas Paso 3 y la introducción de U3 business-rules | Q5 |
| Inventario | Flujo F104 (case-service → governance); `component-methods` C04 `retry_case`, C09 `get_feature_spec` y BFF `retry_case`; rangos F01–F104; U8 y U4 en `unit-of-work.md` | Q1, Q2 |
| `services.md` S2 | Quién escribe cada entrada `fail_closed` | Q4 |
| U5 FD §7 | Pendiente «el `FeatureVector` se arma con el `feature_spec` de la versión activa» resuelto por BR-U8-05 | Q1 |
| **Pendiente para U8 NFR Requirements** | Las lecturas de `serving-config` de case-service se suman a las de scoring: verificar contra NFR-U4-10/11 y el script k6 de U4 | Q1 |
