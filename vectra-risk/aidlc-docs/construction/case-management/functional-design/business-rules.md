# Reglas de negocio — U8 `case-management`

Los IDs `BR-U8-xx` se referencian en los planes de tareas. La validación de los tipos
(BR-U0-20..38), `derive` (U0 §2.3) y las causas de fail-closed (BR-U0-01..08) son de U0:
U8 las **aplica**.

---

## 1. Ingesta y alta manual (US-101, US-102)

**BR-U8-01 — Validación.** `ApplicationIn` se valida con U0. Un error responde 4xx genérico
(BR-U0-30) y **no** crea caso. El gateway ya limita el tamaño (32 KiB) y la tasa (U2).
- **`free_text`** (FR-ING-04, US-109, BR-U0-29): se guarda **tal cual**, siempre con consultas parametrizadas (nunca interpolado en SQL ni en ningún lenguaje); nunca se interpreta ni sale hacia scoring. El escape ocurre al **presentarlo**, en la consola (U10). Guardarlo ya escapado corrompería el dato y produciría doble escape (precisado el 2026-10-06, revisión del FD de U8).

**BR-U8-02 — Idempotencia (Q9).**
- `POST /v1/intake/applications` exige la cabecera `Idempotency-Key`, única por cliente del canal.
- Misma llave y mismo `body_sha256` → el mismo `case_id` (200).
- Misma llave y otro cuerpo → `409 conflict_state`.
- La llave, el caso y su trabajo de evaluación se crean en **una** transacción.
- **Alta manual** (precisado el 2026-10-06, revisión del FD de U8): `POST /v1/cases` también exige `Idempotency-Key`. La genera la consola por envío del formulario, y su alcance es (`user_id`, llave), con las mismas reglas.
- **Limpieza**: el CronJob `case-retention` borra las filas de `intake_keys` con más de 30 días (rol `case_retention`). Pasado ese plazo, un reenvío del canal con la misma llave crearía un caso nuevo; los canales no reintentan después de 30 días.

**BR-U8-03 — Escenarios adversariales (Q9; US-101).**
- `X-Test-Scenario` (sin el prefijo `x-vectra-`, que el gateway reserva a las cabeceras internas y elimina; U2 P-U2-06 precisado) solo se acepta si el cliente es el simulador (`azp = channel-simulator`, un cliente de U2 que solo existe fuera de producción) **y** el despliegue tiene `allow_test_scenarios = true`. Ese valor es `false` en producción, fijado en los values y verificado por política.
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
- El intento 1 sale de inmediato. Retraso antes del intento `n + 1` (n = 1..5): `30 s · 2^(n−1)`, con jitter de ±20 %, es decir, 30 s, 1, 2, 4 y 8 min. Máximo 6 intentos, que suman **930 s ≈ 15,5 min** de esperas (hasta 1,2 · 930 s con jitter), más hasta 6 × 7 s de llamadas. (Q3 = A).
- El trabajo vive en `evaluation_jobs`. Los workers lo toman con `FOR UPDATE SKIP LOCKED` y `locked_until = ahora + 30 s`; si un worker muere, otro lo retoma al vencer ese plazo.
- Llamada a scoring: timeout de **7 s** (P-U7-02).
- La reprogramación y el cambio de estado van en la misma transacción.
- **Número de intento** (precisado el 2026-10-08, revisión del plan de tareas de U8, punto 1):
  - un trabajo nuevo (ingesta, alta manual, `retry`, descongelamiento) nace con `evaluation_jobs.attempt = 0`, y el caso con `attempts = 0`;
  - **cada toma** incrementa `evaluation_jobs.attempt` y copia el valor a `cases.attempts` en la misma transacción, **incluida la retoma** de un trabajo cuyo arrendamiento venció. El intento perdido con el worker cuenta como uno de los 6;
  - la reprogramación tras un fallo fija `run_at`, `last_cause` y `locked_until = NULL` (el trabajo queda libre para la toma en `run_at`): el número sube en la toma siguiente (revisión del FD de U9, 2026-10-08);
  - la toma lee el número antes de escribir: si ya vale 6 (el worker se perdió en el intento 6), el caso escala en esa misma transacción con `local_cause = scoring_unreachable` (BR-U8-09), **sin incrementar** y sin llamar a scoring; el número nunca pasa de 6 (`CHECK`) (precisado el 2026-10-08, segunda revisión del plan de tareas de U8);
  - una retoma no agrega backoff: el trabajo ya estaba vencido y el arrendamiento de 30 s hace de espera.

**BR-U8-08 — Resultado de un intento.**

| Resultado | Efecto |
|---|---|
| `Recommendation` | Guardar la recomendación y `recommendation_entry_id = registry_entry_id`; pasar a `listo`; borrar el trabajo |
| `FailClosed` con `status = en_sincronizacion` | `last_cause = cause`; pasar a `en_sincronizacion`; reprogramar o escalar (BR-U8-09) |
| `FailClosed(model_frozen)` | Pasar a `modelo_congelado`; borrar el trabajo; `attempts = 0` |
| Timeout, error de conexión, 5xx de scoring o falla al leer `serving-config` o el `feature_spec` | `last_cause = scoring_unreachable` o `serving_config_unavailable`; igual que `en_sincronizacion` (reintentable) |
| 401 de scoring | Un reintento inmediato con un token nuevo, **dentro del mismo intento**: no consume uno de los 6 ni cambia `attempt`. Si se repite, como la fila siguiente (precisado el 2026-10-06, revisión del FD de U8) |
| Otro 4xx de scoring (400, 403, 404, 409, 415, 422) | Defecto o configuración: **no** se reintenta. `last_cause = scoring_rejected`; el caso escala de inmediato a `no_disponible` (BR-U8-09) y se dispara la alerta `ScoringRequestRejected` (umbral en NFR Design) (precisado el 2026-10-06, revisión del FD de U8) |

**Resultado tardío** (precisado el 2026-10-06, revisión del FD de U8): la transacción que aplica el resultado solo actualiza el caso si sigue en `en_evaluacion` o `en_sincronizacion` y el trabajo es el mismo (`UPDATE … WHERE state IN (…) AND attempts = :attempt`, donde `:attempt` es el número que devolvió **esa** toma). Como cada toma incrementa el número (BR-U8-07), el resultado tardío de una toma anterior nunca pasa la guarda (precisado el 2026-10-08, revisión del plan de tareas de U8). Si el caso ya está `vencido` o cambió, el resultado se descarta con el log `evaluation.result_discarded`. Una `Recommendation` descartada queda en el registro sin entregar, y su `delivery_status` nunca será `entregada` (P-U7-03).

**BR-U8-09 — Escalamiento (Q3, Q4).** Cuando falla el intento 6, o antes, cuando scoring rechaza la solicitud con un 4xx no reintentable (`scoring_rejected`, BR-U8-08) (precisado el 2026-10-06, revisión del FD de U8):
- el caso pasa a `no_disponible` y aparece en `list_persistent_failures`;
- el gauge `vectra_cases_failclosed_persistent` cuenta los casos en `no_disponible` y dispara `FailClosedPersistente` (U1);
- se escribe **una** entrada `fail_closed`: la inserta `case-worker` en `evidence_outbox` (la política RLS de INF-U8-01 solo le permite ese `entry_type`) y la envía al registro el reconciliador de `case-service`, con su scope `registry:append:case` (precisado el 2026-10-08, INF-U8-01) (con `idempotency_key = UUIDv5(case_id, "fail_closed", ciclo)`, donde `ciclo` es `cases.escalation_count` después de incrementarlo: 1 en el primer escalamiento y +1 en cada escalamiento posterior a un `retry` del CRO; así cada escalamiento tiene su llave; precisado el 2026-10-06) con **exactamente uno** de estos dos campos (precisado el 2026-10-06, revisión del FD de U8):
  - `cause`: la causa del `FailClosed` de scoring, si el último intento terminó así;
  - `local_cause`: `serving_config_unavailable`, `scoring_unreachable` o `scoring_rejected`, si el último intento no terminó con un `RecommendResult`. No se fuerza una causa del catálogo de U0 que no ocurrió.

  **Escritura de la entrada** (precisado el 2026-10-08, revisión del plan de tareas de U8, punto 2): `case_worker` no tiene `SELECT` sobre `evidence_outbox`, así que hace un `INSERT` simple, sin `RETURNING` ni `ON CONFLICT`, dentro de un `SAVEPOINT` en la misma transacción que el cambio a `no_disponible`. Un `unique_violation` sobre la llave de idempotencia se trata como éxito (la misma llave es el mismo escalamiento) y se vuelve al `SAVEPOINT`, para que la transacción siga; cualquier otro error aborta. En la práctica el duplicado no debería ocurrir, porque la guarda de estado descarta una segunda aplicación; esta regla cubre el caso de un commit incierto.

  Además lleva `retryable` (según BR-U0-04 si hay `cause`; con `local_cause`, `false` solo para `scoring_rejected`, que es un defecto), `attempt` = el último intento y `escalated_at`. El escalamiento lo marca `escalated_at`, no `retryable`. PBT-U0-01 rige los `FailClosed` que construye `build_outcome`; esta entrada no es uno de ellos.

Las entradas de cada intento las escribe scoring (BR-U7-16), solo cuando scoring respondió con un `FailClosed`. case-service no las duplica. Los intentos que no llegan a scoring no dejan entrada propia en el registro: quedan en `cases.last_cause`, en la métrica `vectra_case_attempts_total{result}` y, si el caso escala, en la entrada de escalamiento con `local_cause` (precisado el 2026-10-06, revisión del FD de U8).

**BR-U8-10 — Salida de `modelo_congelado` (Q2).**
- Un barrido cada 5 min lee `serving-config`.
- Si su `state` es `activo`, los casos en `modelo_congelado` pasan a `en_evaluacion` con `attempts = 0` y un trabajo nuevo.
- La versión activa puede ser otra, si cumplimiento resolvió el congelamiento con un rollback; el vector se arma con la versión de ese momento (BR-U8-05).

**BR-U8-11 — `retry` del CRO (Q2).**
- `POST /v1/cases/{id}/retry`, solo para `cro` y solo desde `no_disponible`; si el caso no está en ese estado → 409. Sin MFA: es una acción técnica sin efecto sobre el crédito (`component-methods`, BFF `retry_case`; precisado el 2026-10-06).
- Pasa a `en_evaluacion` con `attempts = 0` y un trabajo nuevo.
- Log `case.retry_requested` con `principal_subject` y `principal_role` (allowlist de U0 §8; precisado el 2026-10-08 por U8 NFR Design).

## 3. Estados (Q2; US-107)

**BR-U8-12 — Transiciones.** Solo estas:

| De | Evento | A |
|---|---|---|
| — | Ingesta o alta manual válida | `en_evaluacion` |
| `en_evaluacion`, `en_sincronizacion` | `Recommendation` | `listo` |
| `en_evaluacion`, `en_sincronizacion` | Fail-closed reintentable o scoring sin respuesta, con intentos restantes | `en_sincronizacion` |
| `en_sincronizacion` | Fallo del intento 6 | `no_disponible` |
| `en_evaluacion`, `en_sincronizacion` | `scoring_rejected` (4xx no reintentable, BR-U8-08) | `no_disponible` (precisado el 2026-10-06, revisión del FD de U8) |
| `en_evaluacion`, `en_sincronizacion` | `FailClosed(model_frozen)` | `modelo_congelado` |
| `modelo_congelado` | Barrido: `serving-config` activo | `en_evaluacion` |
| `no_disponible` | `retry` del CRO | `en_evaluacion` |
| `listo` | Decisión confirmada en el registro (BR-U8-18) | `decidido` |
| `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado` | Retención vencida sin decisión (BR-U8-20) | `vencido` |

- `decidido` y `vencido` son terminales. Un caso `decidido` cuya retención vence sigue `decidido`, con `anonymized = true` (precisado el 2026-10-06).
- Un caso `listo` **nunca** se reevalúa: hay una sola recomendación entregada por decisión, y así se cumple el supuesto de P-U7-03.
- Una transición que no está en la tabla se rechaza en la capa de dominio y también en la base, con el trigger `guard_transition` sobre la tabla `case_transitions` (par de estados y rol). Un `CHECK` de PostgreSQL no puede consultar otra tabla (precisado el 2026-10-08 por U8 INF-U8-01).

**BR-U8-13 — Visibilidad (US-107).** `list_cases` excluye los casos `vencido` por defecto;
se ven solo con el filtro explícito `state=vencido` (precisado el 2026-10-06). En los estados distintos de `listo` y `decidido`,
`CaseSummary` y `CaseDetail` no llevan `score`, `outcome`, `recommendation` ni
`explanation`. Un caso `en_sincronizacion` o `no_disponible` muestra `attempts` y
`last_cause`.

**BR-U8-13b — Qué ve el analista (R1).**
- `CaseSummary` (bandeja) lleva `applicant_display`: nombre completo + los últimos 4 dígitos del documento.
- `CaseDetail` (para `analista` y `cro`) lleva la solicitud completa, en dos campos: `application` (de `cases.application`) e `identifiers?` (de `case_identifiers`, ausente si el caso está anonimizado) (precisado el 2026-10-06, revisión del FD de U8); además del `free_text`, que la consola escapa (BR-U8-01). **Nunca** lleva `sex` ni `socioeconomic_stratum`, que son solo de monitoreo (FR-ING-05).
- **Riesgo aceptado y documentado**: la fecha de nacimiento (edad) y la dirección, el departamento y el municipio (región) quedan visibles, porque hacen falta para identificar a la persona y ubicar el inmueble. La disparidad de las decisiones humanas por edad y región la vigila U9 (S4 paso 5).
- Cada `get_case` emite el log `case.viewed` (`principal_subject`, `principal_role` y `case_id`, campos de la allowlist de U0 §8; precisado el 2026-10-08 por U8 NFR Design), sin datos del solicitante.
- Un caso anonimizado (BR-U8-20) se muestra sin identificadores (precisado el 2026-10-06, revisión R1 del FD de U8).

**BR-U8-14 — Congelamiento después de la recomendación (Q2).**
- El barrido de BR-U8-10 también marca `model_frozen_after_recommendation = true` en los casos `listo` cuya `recommendation.model_version_id` coincide con la versión que `serving-config` reporta `congelado`.
- El caso sigue `listo` y el analista puede decidir. La consola muestra el aviso (U10).
- El mismo barrido **apaga** la marca si `serving-config` ya no reporta esa versión como `congelado` (por ejemplo, tras una reactivación de cumplimiento) (precisado el 2026-10-06, revisión del FD de U8).

## 4. Decisión (Q5; US-108, US-502)

**BR-U8-15 — Quién y cuándo.**
- Solo `analista`; queda a nombre del llamante.
- Solo con el caso `listo` y sin otra decisión `pendiente_registro` ni `confirmada`. Si no → `409 conflict_state`. Un caso anonimizado sin decisión ya está `vencido`, así que también recibe 409 (precisado el 2026-10-06).

**BR-U8-16 — Contenido.**
- **BR-U0-35** contra `cases.recommendation.outcome`.
- **`used_factors`**: subconjunto de los `feature_id` de `recommendation.explanation.shap_vector`, o exactamente `["ninguno"]`. Si no → 422.
- **`se_aparta`**: al menos un factor o `["ninguno"]`, más justificación (US-502).
- **`sigue`**: factores o `["ninguno"]` («sin uso de la explicación»).
- **Justificación**: obligatoria en `se_aparta` y `resuelve_revision`, de 20 a 2000 caracteres tras quitar los espacios del inicio y del final (BR-U0-36). En `sigue` es opcional.

**BR-U8-17 — `explanation_viewed_before`.** Es `true` si existe un `explanation_views`
del **mismo** usuario y caso con `first_viewed_at` anterior a la decisión **y su evidencia
`confirmada`** en el registro. Una consulta pendiente o abandonada no cuenta: el valor nunca
afirma algo que el registro no respalda (puede subestimar, nunca sobrestimar) (precisado el 2026-10-06, revisión del FD de U8).

**BR-U8-18 — Evidencia en dos fases.**
1. En una transacción: insertar `decisions` (`pendiente_registro`) y su `evidence_outbox` con `idempotency_key = UUIDv5(case_id, "human_decision")`. La llave es **determinista por caso**: el registro admite como mucho una `human_decision` por caso, aunque una decisión anterior se haya abandonado (precisado el 2026-10-06).
2. Hacer el append de `human_decision`:
   - `payload`: `DecisionIn`, más `explanation_viewed_before`, `decided_at` y `recommendation_entry_id = cases.recommendation_entry_id`;
   - `occurred_at` = el momento de **cada** intento (BR-U3-05). El outbox conserva el `correlation_id` original y el payload tal como se construyó, así que la comparación de BR-U3-06 coincide aunque el reintento corra en otra traza o después de un despliegue (precisado el 2026-10-06, revisión del FD de U8). El hecho de negocio queda en `decided_at`, así que un reintento tardío del reconciliador no se rechaza por la ventana de ±5 min (precisado el 2026-10-06);
   - sobre: `model_version_id` y `policy_version_id` de la recomendación y `actor` del token (US-108).
3. Con el ack, en una transacción: evidencia y decisión `confirmada` y caso `decidido`. Se responde `DecisionRef`.
4. Sin ack (503 o timeout del registro): se responde `503` y la decisión sigue pendiente.

El **reconciliador** reintenta cada evidencia pendiente con su misma llave y un backoff de
1 s a 5 min. A las **24 h** sin confirmar, la evidencia pasa a `abandonada` (como en U4), su
decisión también, y el caso vuelve a aceptar una decisión. Se conserva el payload de la
decisión abandonada.

**Conflicto tras un abandono** (precisado el 2026-10-06): la decisión nueva usa la **misma** llave del caso.
- Si la abandonada nunca se escribió, el append de la nueva se confirma normalmente.
- Si la abandonada sí se había confirmado en el registro (ack perdido), el registro responde 409, porque el contenido es distinto. Entonces case-service:
  1. reenvía el payload de la abandonada con su llave y obtiene el ack original;
  2. en **una** transacción, y en este orden: pasa la nueva decisión y su evidencia a `abandonada` (conservando su payload) y **después** marca la anterior `confirmada` y el caso `decidido` con **esa** decisión. El orden importa porque los índices únicos parciales de `decisions` (por `case_id`) y de `evidence_outbox` (por `idempotency_key`, `state <> 'abandonada'`) admiten una sola fila viva y se comprueban sentencia por sentencia (precisado el 2026-10-08, segunda revisión del plan de tareas de U8);
  3. responde `409 conflict_state` con `reason = decision_already_recorded` (catálogo de U0 §6), para que la consola avise al analista.
- Si el registro sigue sin responder, se responde 503 y la nueva queda pendiente, con la misma llave. Antes de eso, la alerta de
evidencia pendiente avisa (umbral y severidad en NFR Design). Las 24 h se alinean con el
abandono de U4 (BR-U4-17) y acotan cuánto tiempo puede quedar un caso bloqueado por una
decisión sin confirmar; un reenvío posterior sigue funcionando gracias a BR-U3-05 (precisado el 2026-10-06, revisión del FD de U8). Al confirmar, aplica el paso 3. Las entradas `explanation_view` y `fail_closed`
usan el mismo outbox y el mismo reconciliador; solo las decisiones cambian el estado del caso.

## 5. Consulta de la explicación (Q6; US-501)

**BR-U8-19 — Primera consulta.**
- `record_explanation_view` solo para el rol `analista` (como en el BFF; otro rol → 403) y solo con el caso `listo` o `decidido`; si no → 409, lo que incluye `vencido`. Un caso `decidido` anonimizado **sí** acepta la consulta: no expone datos y conserva la métrica (precisado el 2026-10-06).
- La primera vez por (`case_id`, `user_id`): insertar `explanation_views` + `evidence_outbox` con `idempotency_key = UUIDv5(case_id, user_id)` y hacer el append de `explanation_view`.
- Las siguientes → 204, sin entrada nueva. Si la evidencia de la primera quedó `abandonada`, la apertura siguiente reenvía el **payload original** con la misma llave: con ack, se confirma; si el registro sigue sin responder, la consulta continúa pendiente (precisado el 2026-10-06, revisión del FD de U8).
- La clave única y la llave derivada impiden duplicados en una carrera.
- La entrada lleva caso, usuario, `viewed_at` (el momento de la primera consulta, dentro del payload; `occurred_at` es el del intento, BR-U3-05) y `recommendation_entry_id` = `cases.recommendation_entry_id`, es decir, la recomendación que se consultó (precisado el 2026-10-06, revisión del FD de U8). No lleva PII del solicitante.

## 6. Retención (Q7; NFR-U3-03)

**BR-U8-20 — Eliminación de identificadores.**
- **Plazos**:
  - casos `decidido`: 10 años desde la decisión **[VERIFICAR]**;
  - casos nunca decididos: 2 años desde la creación **[VERIFICAR]**, con cumplimiento y la Ley 1581.
- **Job diario**: CronJob `case-retention`, con el rol propio `case_retention` (flujo F105). `case_app` no puede borrar identificadores (precisado el 2026-10-06):
  - borra la fila de `case_identifiers`;
  - borra `cases.application.free_text`, que puede contener PII;
  - fija `anonymized_at`.
- **Guarda de `vencido`** (precisado el 2026-10-06). Un permiso por columna no restringe valores, así que un trigger `guard_vencido` (como P-U4-06; la implementación va en NFR Design) asegura que:
  - solo el rol `case_retention` escribe `state = vencido`, y solo desde un estado no terminal y con la retención vencida;
  - ese rol no puede escribir ningún otro valor de `state`;
  - `case_app` nunca escribe `vencido`.
- **Plazos en una sola fuente** (precisado el 2026-10-08 por U8 NFR Design, Q2): los plazos viven en la tabla `retention_settings` de `case-db`, que solo escribe `case_migrator` desde los values de Helm. El job, el trigger y las métricas los leen de ahí (P-U8-05).
- Un caso no decidido pasa a **`vencido`** en la misma transacción, y se borra su trabajo de evaluación si lo tiene. Así ningún caso queda `listo` o `modelo_congelado` para siempre sin identificadores. El barrido de BR-U8-10 y el `retry` de BR-U8-11 no lo tocan, porque ya no está en `modelo_congelado` ni en `no_disponible` (precisado el 2026-10-06).
- **Después de cada restauración de `case-db`** (precisado el 2026-10-06, revisión R2 del FD de U8): el runbook de restauración del sitio (NFR-U1-07) ejecuta `case-retention` **antes** de que case-service quede listo. La retención se calcula con las fechas del caso, que también se restauran, así que el resultado es el mismo que antes de la pérdida. El `restore-drill` semanal (P-U1-05) también restaura `case-db` en un cluster efímero, ejecuta `case-retention` y comprueba que no quedan identificadores vencidos, así que esta regla queda **probada**, no solo documentada (precisado el 2026-10-06, revisión del FD de U8). Por eso `case-retention` debe ofrecer una CLI que se pueda ejecutar contra cualquier `case-db` (pendiente para el plan de U8).
- **Riesgo aceptado** **[VERIFICAR]** con cumplimiento frente a la Ley 1581: los respaldos mensuales (12 meses, NFR-U1-06), cifrados y de acceso restringido, contienen identificadores ya vencidos hasta que expiran.
- Desde entonces, `get_case` y el expediente salen sin identificadores (`anonymized = true`). El registro no se toca (NFR-U3-03).

## 7. Core bancario (Q8; FR-INT-01, US-603)

**BR-U8-21 — Lectura del estado de crédito.**
- `get_case` consulta `GET /v1/credits/{case_id}` (F17) solo para casos `decidido`, con timeout de 500 ms y sin caché.
- 404 → `sin_credito`; error o timeout → `no_disponible`. La respuesta de `get_case` nunca falla por el core.
- **Core deshabilitado** (`core.enabled = false`, el valor de producción en el MVP; precisado el 2026-10-08 por U8 INF-U8-02, aclaración Q1 = A): `get_case` responde `credit_status = no_disponible` **sin llamar** al core y **sin contar para el circuit breaker**, porque es una configuración y no una falla. F17 y X01 existen solo en kind y staging, con el mock. La integración con el core real queda pendiente para Operations.

**BR-U8-22 — Escritura imposible (RT-5).**
- case-service no tiene ningún cliente ni método de escritura hacia el core.
- El mock expone `POST /v1/credits/{id}/status` **solo** para la demostración: exige `core:write-credit`, que nadie tiene (U0 §7.2), responde 403 y guarda un `WriteAttempt`.
- X01 tiene dos capas (precisado el 2026-10-06, revisión del FD de U8); rige donde existe el mock, en kind y staging (INF-U8-02):
  - una `NetworkPolicy` (L3/L4) bloquea cualquier origen distinto de case-service;
  - Linkerd, con `HTTPRoute` y `AuthorizationPolicy` (L7), solo autoriza `GET /v1/credits/{id}` desde la identidad de case-service.

  Una `NetworkPolicy` no ve métodos HTTP. Además, el scope `core:write-credit` no lo tiene nadie.
- **Evidencia de RT-5** (precisado el 2026-10-08 por U8 INF-U8-03): como Linkerd rechaza el `POST` antes de que llegue al mock, la evidencia es el 403 del proxy (`inbound_http_authz_deny_total`). El `WriteAttempt` del mock queda como tercera capa, por si Linkerd estuviera mal configurado. `CoreWriteAttempt` se dispara con cualquiera de las dos.

## 8. Cambios a otras unidades (registrados en `audit.md`)

Las filas con motivo «Revisión 2026-10-06» salen de las respuestas Q2, Q5, Q7, Q10 y Q11 del
plan vigente y de las precisiones de la revisión de este FD.

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 domain-entities §9.1 `ScoringRequest` | Campo `model_version_id` (la versión cuyo `feature_spec` armó el vector) | Q1 |
| U0 BR-U0-01, BR-U0-02, business-logic-model §2.2, PBT-U0-01 | `check_preconditions` recibe `requested_model_version_id` y `serving_model_version_id?`; la causa 7 aplica también si difieren; en ese caso las ausencias de las causas 2, 5 y 8 no aplican, porque scoring no invocó nada (S2) | Q1 |
| U0 BR-U0-08 | «se reintenta con el caso» = el intento siguiente del caso produce su propia entrada; case-service escribe una sola entrada al escalar | Q4 |
| U0 nueva BR-U0-36 | Justificación de 20 a 2000 caracteres en `se_aparta` y `resuelve_revision` | Q5 |
| U0 §1.2 `CaseDetail` | Campos `model_frozen_after_recommendation`, `anonymized`, `attempts`, `last_cause` | Q2, Q7 |
| U0 §7.2 catálogo de scopes | `governance:read-serving` también para case-service; scope nuevo `governance:read-feature-spec` (case-service). **Superado el 2026-10-08** por INF-U8-01: `governance:read-feature-spec` y `case:recommend` son de `case-worker` | Q1 |
| U0 plan de tareas, Paso 6 | PBT-U0-01 con versión pedida igual o distinta | Q1 |
| U2 realm | Cliente `case-service`: scopes `governance:read-serving`, `governance:read-feature-spec`; audiencia `governance-service`. **Superado el 2026-10-08** por INF-U8-01: `governance:read-feature-spec` pasó al cliente nuevo `case-worker` | Q1 |
| U4 BR-U4-06, nueva BR-U4-19, domain-entities §1.1, plan de tareas Pasos 2 y 10 | governance guarda el `feature_spec` verificado al registrar y lo sirve en `GET /v1/models/{id}/feature-spec` | Q1 |
| U7 BR-U7-01, PBT-U7-07, plan de tareas Paso 11 | scoring compara `ScoringRequest.model_version_id` con `serving-config` antes de `:predict` | Q1 |
| U7 BR-U7-16 | case-service no duplica las entradas por intento | Q4 |
| U2 NFR Design P-U2-06 (cabeceras internas) | El prefijo `x-vectra-` queda reservado a cabeceras internas y el gateway lo elimina siempre (incluye `x-vectra-deadline` de U7) | Q9 |
| U0 y U3 (rango de validación) | `BR-U0-20..35` pasa a `20..38` (BR-U0-36, 37 y 38) en U0 business-logic-model, NFR Design, plan de tareas Paso 3 y la introducción de U3 business-rules | Q5; Q10 |
| Inventario | Flujo F104 (case-service → governance); `component-methods` C04 `retry_case`, C09 `get_feature_spec` y BFF `retry_case`; rangos F01–F105 (con F105 de la retención); U8 y U4 en `unit-of-work.md` | Q1, Q2 |
| `services.md` S2 | Quién escribe cada entrada `fail_closed` | Q4 |
| U5 FD §7 | Pendiente «el `FeatureVector` se arma con el `feature_spec` de la versión activa» resuelto por BR-U8-05 | Q1 |
| U3 BR-U3-05, BR-U3-06, business-logic-model §2.1, PBT-U3-01, PBT-U3-08, plan de tareas Paso 7 | La ventana de `occurred_at` solo aplica a llaves nuevas y después de la idempotencia; la comparación de contenido excluye `occurred_at`. Sin esto, el reconciliador de U8 (y el de U4) no podría confirmar nada después de 5 min | Revisión 2026-10-06 |
| U0 §5.1 y §5.2 | `occurred_at` = intento; payloads con `decided_at` (`human_decision`), `escalated_at?` (`fail_closed`) y `frozen_at` (`freeze`); `viewed_at` (`explanation_view`) ya existía y es el momento de negocio de BR-U8-19 | Revisión 2026-10-06 |
| U0 nueva BR-U0-37 | Momentos de negocio ≤ `occurred_at` y a lo sumo 7 días antes, solo para llaves nuevas (BR-U3-05) | Revisión 2026-10-06 |
| U0 §1.2 estados del caso; `components.md` C04 | Estado terminal `vencido` | Revisión 2026-10-06 |
| U3 BR-U3-05 | Cita la cota de BR-U0-37 | Revisión 2026-10-06 |
| Inventario §4 | `case_retention` también puede actualizar `state` (solo para `vencido`) | Revisión 2026-10-06 |
| ~~Pendiente para U8 NFR Design~~ **Resuelto** | Alerta de evidencia pendiente (umbral antes de las 24 h) y alerta al abandonar; trigger `guard_vencido` (resuelto el 2026-10-08 por U8 NFR Design: P-U8-04 y P-U8-05) | Revisión 2026-10-06 |
| U4 BR-U4-17, domain-entities §1.3, business-logic-model §2.2, PBT-U4-07, NFR Design P-U4-02, plan de tareas Pasos 2 y 8 | Llave determinista UUIDv5(entidad, n), con `n` = no abandonadas + 1 e índice único parcial; una sola transición pendiente por entidad (salvo `freeze`, que toma el `n` siguiente); el reconciliador escribe en orden de `n` y solo toma la menor pendiente por entidad; resolución del conflicto tras un abandono | Revisión 2026-10-06 |
| `stories.md` US-107 | Escenario de casos `vencido`, fuera de la bandeja por defecto; la verificación e2e incluye un caso `vencido` además de los 4 estados | Revisión 2026-10-06 |
| U0 §6 `Problem.reason` y PBT-U0-08 | Campo `reason` con catálogo cerrado (`decision_already_recorded`, `transition_pending`) | Revisión 2026-10-06 |
| **Pendiente para U10** | La bandeja oculta `vencido` por defecto y ofrece el filtro; aviso `decision_already_recorded` al analista; escape de `free_text` al presentarlo | Revisión 2026-10-06 |
| U3 BR-U3-06, business-logic-model, PBT-U3-01, plan Paso 7; U4 business-rules | Idempotencia por campos de negocio (sin `correlation_id` ni `contract_version`); los reconciliadores conservan el `correlation_id` y el payload originales | Revisión 2026-10-06 |
| U0 BR-U0-08; U7 BR-U7-15/16 | Llave de scoring: UUID v4 por solicitud, nunca derivado de `case_id` ni de `attempt` | Revisión 2026-10-06 |
| U3 domain-entities §3; U0 §5.2 `explanation_view` | Momento de negocio en `monitoring` (retirada en la revisión del FD de U9, 2026-10-08; `monitoring_daily` ya cuenta por momento de negocio) y `metrics`; `recommendation_entry_id` en `explanation_view` | Revisión 2026-10-06 |
| U0 §1.2; `component-methods` | `CaseFilter` y `PersistentFailure`; columna MFA = no en `retry_case` del BFF | Revisión 2026-10-06 |
| `stories.md` US-501; `services.md` S1 paso 5; `requirements.md` FR-ING-04 | Solo la primera consulta; `free_text` tal cual con escape al presentar | Revisión 2026-10-06 |
| U4 BR-U4-17/08, domain-entities §1.3, business-logic-model §2.2, PBT-U4-01/07, P-U4-02, plan Paso 8; U0 §5.2 `model_event` | Revalidación en la segunda transacción; `mark_active` como unidad; `freeze` descarta las pendientes de la versión; evento `transicion_descartada`; se quita la regla de «no abandonar con un `freeze` detrás» | Revisión 2026-10-06 |
| U3 §3 `monitoring` (retirada en la revisión del FD de U9, 2026-10-08; `monitoring_daily` usa `evaluated_at`) | `evaluated_at` en las recomendaciones | Revisión 2026-10-06 |
| U4 BR-U4-17, domain-entities §1.3 (`kind`), PBT-U4-07, plan Paso 2; U3 BR-U3-16 | Abandono y recuperación por unidad completa; `transicion_descartada` como fila de compensación sin cambio de estado; actor de sistema; prueba del `n` reservado | Revisión 2026-10-06 |
| U0 §1.2 `CaseSummary`/`CaseDetail` | `applicant_display`; `application` sin `sex` ni `socioeconomic_stratum` | R1 |
| U1 NFR-U1-07, P-U1-05, plan de tareas Paso 13 | El runbook ejecuta `case-retention` después de restaurar `case-db`, y el `restore-drill` semanal lo prueba con un segundo cluster efímero y la métrica `vectra_restore_drill_retention_violations` | R2; revisión 2026-10-06 |
| U0 §1.2 `CaseDetail` | `identifiers?` aparte de `application`; ausente si el caso está anonimizado | Revisión 2026-10-06 |
| **Pendiente para U10** (R1) | Bandeja con `applicant_display`; detalle con la solicitud sin etiquetas de monitoreo y `free_text` escapado | R1 |
| **Pendiente para el plan de tareas de U8** | CLI `case-retention` ejecutable contra cualquier `case-db` (la usa el `restore-drill` de U1) | R2; revisión 2026-10-06 |
| U0 BR-U0-06, §5.2 `fail_closed` (`local_cause`, `retryable` según BR-U0-04), §6 (`unprocessable_explanation` y tres `reason` de U7); U7 domain-entities §5; U3 BR-U3-05 (cota solo para llaves nuevas) | 4xx no reintentables; escalamiento con `retryable` coherente con PBT-U0-01; códigos de los 422 de U7 | Revisión 2026-10-06 |
| U2 realm | Cliente `channel-simulator` solo fuera de producción | Revisión 2026-10-06 |
| Inventario X01, §4 | X01 en dos capas (NetworkPolicy + Linkerd L7); `case_retention` también borra `intake_keys` | Revisión 2026-10-06 |
| `services.md` S2 | Las entradas por intento solo existen si scoring respondió; los fallos locales van a la entrada de escalamiento | Revisión 2026-10-06 |
| U1 NFR-U1-32, P-U1-05, plan de tareas Paso 13 | Alerta `RestoreDrillRetentionViolation` (SEV2, con `runbook_url`) sobre `vectra_restore_drill_retention_violations` | Revisión 2026-10-06 |
| U0 BR-U0-37, business-logic-model §1 y §3 (PBT-U0-15 y ejemplos), plan Pasos 3 y 6; U3 plan Paso 7 | Función `check_business_time`, llamada por el registro solo para llaves nuevas, con su propiedad y sus ejemplos | Revisión 2026-10-06 |
| U0 §5.2 `fail_closed`, BR-U0-04 (causas locales), BR-U0-08, nueva BR-U0-38, PBT-U0-16, plan Pasos 3 y 6; U3 BR-U3-03 | Exactamente uno de `cause` o `local_cause`; `retryable` según BR-U0-04 extendida; solo case-service escribe `local_cause` y `escalated_at` (scoring → 403) | Revisión 2026-10-06 |
| ~~Pendiente para U8 NFR Design~~ **Resuelto** | Alerta `ScoringRequestRejected` y métrica `vectra_case_attempts_total` (resuelto el 2026-10-08 por U8 NFR Design: P-U8-08) | Revisión 2026-10-06 |
| U3 BR-U3-03 y BR-U3-05; U4 BR-U4-14 y BR-U4-17; U7 BR-U7-01 y BR-U7-16 | Ajustes de redacción: `fail_closed` simétrico por scope; `check_business_time` nombrada en el append; case-service como lector de `serving-config` (verificar en el NFR de U8 contra NFR-U4-10/11); compensaciones pendientes que bloquean y `n` descartadas que el orden salta; `model_frozen` antes que la versión distinta; scoring solo con `cause`, y el intento siguiente produce su propia entrada | Revisión 2026-10-06 |
| U4 BR-U4-17, alertas de §9, P-U4-02 y su tabla de alertas, PBT-U4-07, plan Pasos 8 y 17 | Las compensaciones `transicion_descartada` nunca se abandonan; alerta `CompensationEventPending` (SEV2) con su `runbook_url` en la `PrometheusRule` del Paso 17 | Revisión 2026-10-06 |
| U7 PBT-U7-07 y flujo §2.1; U3 plan Paso 7 | Congelado con versión distinta → `model_frozen` (también en el flujo); el flujo usa el UUID v4 de la solicitud; descripción del Paso 7 al día (campos de negocio, ventana y `check_business_time` solo para llaves nuevas, forma del payload por scope); prueba del 403 simétrico, incluido `local_cause` | Revisión 2026-10-06 |
| U3 business-logic-model §2.1 y PBT-U3-01; BR-U3-04 | El flujo muestra la forma del payload de `fail_closed` por scope y `check_business_time` tras la ventana, solo para llaves nuevas; PBT-U3-01 con la misma llave y un momento de negocio de más de 7 días → ack original; BR-U3-04 empieza con la búsqueda de idempotencia y las comprobaciones de llave nueva | Revisión 2026-10-06 |
| **Pendiente para U11** (U9 resuelto el 2026-10-08 por U9 FD, BR-U9-07) | Medir con `evaluated_at`, `decided_at` y `viewed_at`, no con `recorded_at` | Revisión 2026-10-06 |
| U0 plan de tareas, Paso 3 | Pruebas de ejemplo de BR-U0-37 | Revisión 2026-10-06 |
| U0 NFR Requirements, FD y NFR Design; U7 NFR Requirements, NFR Design y FD | NFR-U0-23 y PBT-U0-14 (respaldo de `vectra_common.deps`); `deps` y `deadline` en NFR-U0-40/41; filas RESILIENCY-10 y PBT-06; httpx y prometheus-client en el stack; módulo `deps` y componente `deadline`; referencias desde NFR-U7-11/43 y las filas PBT-06 de U7 | Q11 |
| U4 business-rules (reconciliador y `freeze`) | `occurred_at` nuevo en cada intento; `frozen_at` en el payload | Revisión 2026-10-06 |
| Inventario §4 y §2 | `case_app` con `DELETE` solo sobre `evaluation_jobs`; rol nuevo `case_retention`; flujo F105 (CronJob `case-retention` → `case-db`) | Revisión 2026-10-06 |
| Documentos de Application Design anteriores a F104 | Diagrama y texto de §7 de `component-dependency.md` (también faltaba F103), `unit-of-work-dependency.md` (matriz, diagrama y orden), `components.md` (C04 y C09), `services.md` S1, `unit-of-work.md` U8 y U0 business-logic-model §2.3 | Revisión 2026-10-06 |
| ~~Pendiente para U8 NFR Requirements~~ **Resuelto** | Las lecturas de `serving-config` de case-service se suman a las de scoring: cubierto por NFR-U8-15, NFR-U4-10 (12 clientes cada 5 s) y el script k6 del Paso 19 del plan de U4 (resuelto el 2026-10-06 por U8 NFR Requirements) | Q1 |
| U4 domain-entities §1.3 (y referencias en §3.1 y §4), BR-U4-17, business-logic-model §2.1 y PBT-U4-07, P-U4-02, P-U4-06 (`guard_unfreeze`, `guard_freeze`; antes `model_transitions`), INF-U4-03, plan Pasos 2 y 8; `component-dependency.md` (`gov_archiver`) | Tabla única `transitions` con `entity_type` y `entity_id` para modelo, política y fuente; los triggers `guard_unfreeze` y `guard_freeze` (P-U4-06 y prueba del Paso 2) buscan la transición en `transitions` con `entity_type = model_version` y `entity_id` igual a la versión actualizada; índice `(entity_type, entity_id, transition_number)`; llave UUIDv5(`entity_type`:`entity_id`, n) (el flujo §2.1 decía `transition_id`); la activación de una política es una unidad, como `mark_active` | Revisión 2026-10-06 |
| U7 plan de tareas, Paso 11 | Llave UUID v4 por solicitud (nunca derivada de `case_id` ni de `attempt`, reutilizada solo por el reintento del append) y otro UUID v4 para el `fail_closed`; ejemplos «congelado con versión distinta → `model_frozen`», llaves distintas con el mismo `attempt` y `fail_closed` de scoring solo con `cause` | Revisión 2026-10-06 |
| U5 FD §7; U0 business-logic-model §2.3 | `derive` recibe campos de identificación como origen de una búsqueda (`municipality_code` → `zona_vivienda`), pero nunca los devuelve ni los usa como clave (BR-U0-34); fila U6 de U5 §7 resuelta por NFR-U6-05 y P-U6-01 | Revisión 2026-10-06 |
| `component-dependency.md` F75; U1 P-U1-05 y plan Paso 13 | Sin flujo nuevo: la restauración de `case-db` lee el mismo destino que F70; la credencial de solo lectura de F75 se limita a los prefijos de `registry-db` y `case-db` y a `vectra-registry-checkpoints`, y el `conftest` del Paso 13 lo comprueba | Revisión 2026-10-06 |
| U2 domain-entities §4 (ruta de intake), BR-U2-11, plan Pasos 2 y 7; U8 BR-U8-11; `unit-of-work-story-map.md` US-101 y US-109 | La ruta de intake admite `azp = channel-simulator` fuera de producción; límite propio del simulador (30 req/s, ráfaga 60) para los 20/s de NFR-U1-11, con contador separado del canal real; cliente `channel-simulator` en los realms de kind y staging, nunca en prod; `retry` sin MFA (BR-U8-11); mapa de historias al día (F07, almacenamiento tal cual) | Revisión 2026-10-06 |
| U2 P-U2-06, NFR-U2-42, plan Paso 13 | `Idempotency-Key` y `X-Test-Scenario` pasan intactas por el gateway; la prueba con el backend de eco lo comprueba junto con la eliminación de `x-vectra-*`. `unit-of-work-dependency.md`: la celda U8 → U4 cita F104, como la de U7 cita F103 | Revisión 2026-10-06 |
| U8 BR-U8-20, domain-entities §1.5, NFR-U8-46(f); `component-dependency.md` §4 | Tabla `retention_settings` (una fila, escrita solo por `case_migrator` desde los values); el job, el trigger `guard_vencido` y las métricas leen los plazos de ella | U8 NFR Design Q2, 2026-10-08 |
| `component-dependency.md` (F15, F40, F50, F104, §4, X01, diagrama); U0 §7.2; U2 clientes; U7 INF-U7-05, deployment-architecture y logical-components; U8 NFR-U8-41, NFR-U8-45, P-U8-06 | Identidad propia de `case-worker` (ServiceAccount, cliente `case-worker` con `case:recommend`, rol `case_worker`); mock en F50 solo para el JWKS; `CoreWriteAttempt` también con la denegación del proxy de Linkerd (NFR-U8-45(b)) | U8 Infrastructure Design Q1–Q3, 2026-10-08 |
| U1 deployment-architecture (`vectra-mock`); `component-dependency.md` §1 | El mock solo existe en kind y staging | U8 Infrastructure Design Q2, 2026-10-08 |
| U8 BR-U8-07, 08, 09; domain-entities §2.1; business-logic-model §3.1 y PBT-U8-01; NFR-U8-11; P-U8-01; INF-U8-01 | Cada toma incrementa `evaluation_jobs.attempt` y lo copia a `cases.attempts` (también la retoma tras un arrendamiento vencido; el paso a 7 escala); la guarda compara con el número de esa toma. `case_worker` inserta `fail_closed` sin `RETURNING` ni `ON CONFLICT`, con `SAVEPOINT` y `unique_violation` como éxito | U8 plan de tareas, revisión 2026-10-08 |
| U8 domain-entities §2.1 y §3.1; BR-U8-07, BR-U8-18; P-U8-01; business-logic-model §3.1 y PBT-U8-01 | Índice único parcial de `evidence_outbox` por `idempotency_key` (`state <> 'abandonada'`); orden del conflicto tras un abandono (la nueva a `abandonada` antes de confirmar la anterior); `CHECK (attempt BETWEEN 0 AND 6)` y la toma decide con el valor leído: con 6, escala sin incrementar | U8 plan de tareas, segunda revisión 2026-10-08 |
| U8 BR-U8-12; `component-dependency.md` §4 | Transiciones con trigger `guard_transition` sobre `case_transitions` (par de estados y rol), no un `CHECK`; `UPDATE` por columna de `case_app` | U8 Infrastructure Design, revisión 2026-10-08 |
| U8 BR-U8-21, BR-U8-22, NFR-U8-25, 31; P-U8-06; `component-dependency.md` F17, X01, §5; U2 realm de producción | Core deshabilitado en producción: `no_disponible` sin llamar y sin contar para el breaker; F17, X01 y `CoreWriteAttempt` solo en kind y staging; sin `core:read-credit` en el realm de producción | U8 Infrastructure Design, aclaración Q1 = A, 2026-10-08 |
| **Pendiente para Operations** | Integración con el core real: contrato **[VERIFICAR]**, egress en §5, revisión de seguridad, equivalente de X01 fuera de la malla y `CoreWriteAttempt` del gateway (INF-U8 §8) | U8 Infrastructure Design, aclaración Q1 = A, 2026-10-08 |
| `component-dependency.md` §4 | RLS en `evidence_outbox`: `case_worker` solo inserta `fail_closed` (INF-U8-01) | U8 Infrastructure Design, revisión 2026-10-08 |
