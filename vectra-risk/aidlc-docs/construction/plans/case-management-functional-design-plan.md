# Plan de Functional Design — U8 `case-management`

**Alcance de la unidad** (`unit-of-work.md` U8):
- `case-service`:
  - ingesta y alta manual;
  - estados del caso;
  - cola transaccional de reintentos con backoff;
  - escalamiento (`FailClosedPersistente` y lista para el CRO);
  - decisión humana con justificación estructurada;
  - eventos de consulta de la explicación;
  - lectura del estado del crédito.
- Esquema de `case-db`.
- `core-banking-mock`: `GET` del estado de crédito, más una ruta de escritura que existe **solo** para demostrar el bloqueo RT-5.

**Historias (dueña):**

| Historia | Tema |
|---|---|
| US-101 | Ingesta |
| US-102 | Alta manual |
| US-107 | Bandeja con estados |
| US-108 | Decisión firmada |
| US-112 | Reintento y escalamiento |
| US-501 | Consulta de la explicación |
| US-502 | Justificación estructurada |
| US-603 | RT-5 |

**Ya decidido** (no se pregunta):
- **Tipos de U0**:
  - `ApplicationIn` (§1.1) y `CaseRef`/`CaseSummary`/`CaseDetail`;
  - los 6 estados del caso (§1.2), `DecisionIn`/`DecisionRef` (§9.2) y `RecommendResult`/`FailClosed`;
  - payload de `human_decision` con `recommendation_entry_id`, que llena case-service (U7 NFR Design Q3);
  - BR-U0-35 (coherencia de la decisión con la recomendación).
- **`derive(application, evaluated_at, feature_spec)`** de U0 (precisado por U5) y redacción de logs por allowlist.
- **Pendientes que otras unidades dejaron para U8:**
  - guardar el `registry_entry_id` de la `Recommendation` recibida (P-U7-03);
  - timeout hacia scoring ≥ 7 s (P-U7-02);
  - apagado ordenado como INF-U7-03;
  - eliminar los identificadores al vencer la retención (NFR-U3-03);
  - armar el `FeatureVector` con el `feature_spec` de la versión activa (U5 §7).
- **RT-5** (US-603): `core:write-credit` no lo tiene ninguna identidad; X01 bloquea por red cualquier método distinto de `GET` y cualquier origen distinto de case-service.
- **Roles en el BFF** (C03): `analista` decide; `cro` ve fallos persistentes. La decisión queda a nombre del llamante.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo arma case-service el `FeatureVector` (Business Logic / Integration)
**Hallazgo.** Hay dos problemas:
- **Falta un flujo.** `derive` necesita el `feature_spec` de la **versión activa**, con sus tablas de búsqueda (BR-U5 §7). Pero case-service no tiene ningún flujo hacia governance ni hacia el model-store (sus flujos son F04, F10, F15, F16, F17, F40 y F44).
- **Hay una carrera.** Si entre armar el vector y que scoring lea `serving-config` se activa otra versión, el vector no corresponde al modelo que lo puntúa.

A) **governance sirve el `feature_spec` y la versión viaja en la solicitud**:
   - governance guarda el `feature_spec` verificado, con sus tablas, al registrar la versión, igual que el diccionario (BR-U4-18). Lo sirve en `GET /v1/models/{id}/feature-spec`; es inmutable y se puede cachear sin límite;
   - flujo nuevo **F104** case-service → governance, con dos scopes:
     - `governance:read-serving`, para leer `serving-config` (caché ≤ 5 s);
     - `governance:read-feature-spec`, nuevo;
   - en **cada intento** de evaluación, case-service lee la versión activa, arma el vector con su `feature_spec` y envía `model_version_id` en `ScoringRequest`;
   - scoring compara ese `model_version_id` con su `serving-config`. Si difiere, responde `FailClosed(version_mismatch)` sin llamar a KServe y el caso reintenta;
   - **cambios en otras unidades**:
     - U0: campo nuevo en `ScoringRequest`, y BR-U0-02/08 aceptan esa discrepancia como motivo para no invocar `:predict`;
     - U4: almacenamiento y endpoint;
     - U2: scopes;
     - U7: la comparación;
     - inventario: F104.

   (Recomendado: el vector y el modelo nunca pueden ser de versiones distintas, y scoring sigue sin recibir datos crudos del solicitante)

B) **scoring arma el vector**: case-service envía la solicitud sin identificadores directos y scoring aplica `derive` con el `feature_spec` de la versión que va a usar. Desaparece la carrera, pero scoring recibe ingresos, fecha de nacimiento y otros datos crudos, y cambian el contrato de U0, el de U7 y la frontera de BR-U7-12

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Máquina de estados del caso (Business Logic, US-107, US-112)

A)

| De | Evento | A |
|---|---|---|
| — | Ingesta o alta manual válida | `en_evaluacion`; encola el intento 1 en la misma transacción |
| `en_evaluacion`, `en_sincronizacion` | `Recommendation` | `listo` (guarda la recomendación y su `registry_entry_id`) |
| `en_evaluacion`, `en_sincronizacion` | `FailClosed` con `status = en_sincronizacion`, o scoring no responde | `en_sincronizacion` (reprograma, Q3) |
| `en_evaluacion`, `en_sincronizacion` | `FailClosed(model_frozen)` | `modelo_congelado` |
| `en_sincronizacion` | Reintentos agotados | `no_disponible` |
| `modelo_congelado` | `serving-config` vuelve a `activo`; se revisa cada 5 min con la lectura de Q1 | `en_evaluacion`, con el contador de reintentos en cero |
| `no_disponible` | Acción `retry` del CRO (endpoint nuevo en C04 y en el BFF) | `en_evaluacion`, con el contador en cero |
| `listo` | Decisión confirmada en el registro (Q5) | `decidido` |

- `decidido` es terminal.
- Un caso `listo` **nunca** se reevalúa: hay una sola recomendación entregada por decisión, el supuesto de P-U7-03.
- Si la versión de un caso `listo` se congela antes de la decisión, el caso sigue `listo` y el detalle lleva el aviso `model_frozen_after_recommendation`. La recomendación ya se entregó y quedó registrada; el analista decide con esa advertencia visible.

(Recomendado)

B) Como A, pero un caso `listo` cuya versión se congela vuelve a `modelo_congelado` y descarta la recomendación. Así quedarían recomendaciones entregadas sin decisión y se complicaría `delivery_status` (P-U7-03)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Reintentos y cola (Business Logic / Error Handling, FR-SCO-05/06, US-112)

A)
- **Backoff exponencial** con base de 30 s, factor 2 y jitter de ±20 %, con un máximo de **6 intentos**: 30 s, 1, 2, 4, 8 y 16 min, unos 31 min en total. Después, el caso pasa a `no_disponible`.
- **Cola transaccional** en `case-db`:
  - tabla `evaluation_jobs` (`case_id`, `attempt`, `run_at`, `locked_until`);
  - el trabajo se crea en la misma transacción que el caso o que su reprogramación, así que no puede haber un caso sin trabajo;
  - los workers de case-service toman trabajos con `FOR UPDATE SKIP LOCKED`.
- **Llamada a scoring**:
  - timeout de 7 s (P-U7-02);
  - `attempt` = número del intento;
  - el vector se vuelve a armar en cada intento (Q1).
- **Escalamiento**:
  - métrica `vectra_cases_failclosed_persistent` (gauge de casos en `no_disponible`), que dispara `FailClosedPersistente` (U1);
  - el caso aparece en `list_persistent_failures`.

(Recomendado: cubre la ventana de propagación de una promoción, ≤ 6 s, y una caída breve de un componente, sin dejar casos colgados más de media hora)

B) Reintentos fijos cada 1 min durante 10 min

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Quién escribe las entradas `fail_closed` (Integration, ambigüedad entre BR-U0-08, BR-U7-16 y `services.md` S2)
- BR-U7-16 dice que scoring escribe la entrada `fail_closed` de cada intento como best effort.
- BR-U0-08 dice que «la entrada `fail_closed` se reintenta con el caso».
- `services.md` S2 dice que «cada fail-closed también se agrega al registro».

Ninguno aclara si case-service escribe algo.

A)
- scoring escribe la entrada de **cada intento** (BR-U7-16). case-service no la duplica.
- case-service escribe **una** entrada `fail_closed` al **escalar** a `no_disponible`: con la última causa recibida (o `timeout` si scoring no respondió), `retryable = false` y `attempt = 6`. Queda en el registro el hecho de negocio «el caso agotó los reintentos».
- BR-U0-08 se precisa: «se reintenta con el caso» significa que el intento siguiente del caso vuelve a producir la entrada; no es un reintento de la misma escritura.

(Recomendado)

B) case-service escribe también una entrada por cada intento fallido, duplicando la de scoring

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Reglas de la decisión (Business Rules, US-108, US-502, BR-U0-35)

A)
- **Quién y cuándo**: solo `analista`, solo con el caso `listo` y una sola decisión por caso. Si no se cumple → `409 conflict_state`.
- **Coherencia**: BR-U0-35 contra el `outcome` de la recomendación guardada en el caso.
- **Factores**: `used_factors` debe ser un subconjunto de los `feature_id` del `shap_vector` de la explicación, o exactamente `["ninguno"]`; si no → 422.
  - `se_aparta` exige al menos un factor o `["ninguno"]`, más justificación (US-502).
  - `sigue` acepta factores o `["ninguno"]` («sin uso de la explicación»).
- **Justificación**: obligatoria, de 20 a 2000 caracteres sin contar espacios al inicio y al final, en `se_aparta` y `resuelve_revision`. En `sigue` es opcional.
- **`explanation_viewed_before`**: verdadero si el **mismo usuario** registró un `explanation_view` del caso antes de decidir.
- **Evidencia en dos fases** (el mismo patrón que U4):
  1. la decisión se guarda como `pendiente_registro`, con su `idempotency_key`;
  2. se hace el append de `human_decision`, con `recommendation_entry_id`, `model_version_id` y `policy_version_id` de la recomendación (US-108);
  3. al confirmarse, la decisión pasa a `confirmada` y el caso a `decidido`.
- Si el registro no responde → `503` y la decisión queda pendiente. Un reconciliador la reintenta con la misma llave. Mientras tanto, otra decisión sobre el caso → 409.

(Recomendado)

B) Escribir directamente en el registro sin fase pendiente, y justificación opcional en todos los casos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Eventos de consulta de la explicación (Business Rules, US-501, FR-MET-02)

A)
- `record_explanation_view` solo con el caso `listo` o `decidido`.
- case-service hace el append de `explanation_view` **la primera vez** por par (caso, usuario). Las siguientes responden 204 sin una entrada nueva.
- Usa una `idempotency_key` derivada de (`case_id`, `user_id`), así que una carrera entre dos clics no duplica.

(Recomendado: la métrica y `explanation_viewed_before` solo necesitan la primera consulta, y no se infla el registro)

B) Una entrada por cada apertura

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Retención de `case-db` y eliminación de identificadores (Business Rules, NFR-U3-03, Ley 1581)

A)
- **Plazos**:
  - casos `decidido`: identificadores directos durante **10 años desde la decisión** **[VERIFICAR]** con cumplimiento, el mismo plazo del registro;
  - casos nunca decididos: **2 años desde la creación** **[VERIFICAR]**.
- **Job diario de eliminación**:
  - borra los campos de identificación de §1.1: `full_name`, `document_type`, `document_number`, `birth_date`, `phone`, `email`, `address` y `municipality_code`;
  - conserva `department_code`, el estado y las referencias al registro;
  - marca el caso como `anonimizado` con su fecha.
- Desde entonces, el expediente del BFF muestra el caso sin identificadores (NFR-U3-03).
- La eliminación no toca el registro.

(Recomendado)

B) Conservar los identificadores indefinidamente hasta una decisión posterior de cumplimiento

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Lectura del estado de crédito (Integration, F17, FR-INT-01)
El banco crea el crédito en su core, fuera de Vectra, después de la decisión humana.

A)
- El core identifica el crédito con el `case_id` de Vectra como referencia externa. En el mock, `GET /v1/credits/{case_id}` devuelve `{status, updated_at}` o 404 «sin crédito».
- `get_case` lo consulta solo para casos `decidido`, con timeout de 500 ms y sin caché.
- Un fallo no rompe la respuesta: `credit_status = {status: no_disponible}`.
- La ruta de escritura del mock (`POST /v1/credits/{id}/status`) exige `core:write-credit`, que nadie tiene, y registra cada intento rechazado para la evidencia de RT-5.

(Recomendado)

B) Copiar periódicamente el estado del core a `case-db`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Ingesta: duplicados y escenarios adversariales (Business Rules, US-101, SECURITY-05)

A)
- **Duplicados**: `POST /v1/intake/applications` exige la cabecera `Idempotency-Key`, única por cliente del canal.
  - El mismo cuerpo con la misma llave → el mismo `case_id` (200).
  - Otro cuerpo con la misma llave → `409`.
- **Escenarios adversariales**:
  - la cabecera `X-Vectra-Scenario` (p. ej. `RT-1-007`) solo se acepta si el cliente es el simulador **y** el entorno no es producción (configuración del despliegue); en producción → 400;
  - se guarda como `test_scenario_id` y **nunca** se envía a scoring ni al registro.
- **Errores**: los de validación son genéricos (BR-U0-30) y no crean caso.

(Recomendado)

B) Sin idempotencia; los duplicados los evita el canal

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, historias, C03/C04, S1/S2, tipos de U0, pendientes de U3/U5/U7, flujos de U8)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/case-management/functional-design/domain-entities.md`
- [x] 4. Generar `construction/case-management/functional-design/business-rules.md`
- [x] 5. Generar `construction/case-management/functional-design/business-logic-model.md` (máquina de estados, flujos y PBT, incluida la stateful)
- [x] 6. Aplicar y registrar los cambios en otras unidades según las respuestas (Q1, Q2, Q4)
- [x] 7. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
