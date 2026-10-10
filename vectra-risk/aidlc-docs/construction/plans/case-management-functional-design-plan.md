# Plan de Functional Design — U8 `case-management`

**Alcance de la unidad** (`unit-of-work.md` U8):
- `case-service`: ingesta, alta manual, estados del caso, cola transaccional de reintentos con backoff, escalamiento (`FailClosedPersistente` y lista para el CRO), decisión humana con justificación estructurada, eventos de consulta de la explicación y lectura del estado del crédito.
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
- **Tipos de U0**: `ApplicationIn` (§1.1), `CaseRef`/`CaseSummary`/`CaseDetail` y los estados del caso (§1.2), `DecisionIn`/`DecisionRef` (§9.2), `RecommendResult`/`FailClosed`; payload de `human_decision` con `recommendation_entry_id`, que llena case-service (U7 NFR Design Q3); BR-U0-35.
- **`derive(application, evaluated_at, feature_spec)`** de U0 (precisado por U5) y redacción de logs por allowlist.
- **Pendientes que otras unidades dejaron para U8:**
  - guardar el `registry_entry_id` de la `Recommendation` recibida (P-U7-03);
  - timeout hacia scoring ≥ 7 s (P-U7-02);
  - apagado ordenado como INF-U7-03;
  - eliminar los identificadores al vencer la retención (NFR-U3-03);
  - armar el `FeatureVector` con el `feature_spec` de la versión activa (U5 §7).
- **RT-5**: `core:write-credit` no lo tiene ninguna identidad; X01 bloquea por red.
- **Roles en el BFF** (C03): `analista` decide; `cro` ve fallos persistentes.

**Nota:** este plan reemplaza al de la versión revertida el 2026-10-06. Sus opciones
recomendadas ya incorporan lo que salió de esa revisión. Q10 y Q11 tratan defectos previos
fuera de U8 que la reversión dejó otra vez abiertos.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo arma case-service el `FeatureVector` (Business Logic / Integration)
**Hallazgo.** `derive` necesita el `feature_spec` de la **versión activa** (BR-U5 §7), pero
case-service no tiene flujo hacia governance ni hacia el model-store. Además, si entre armar
el vector y puntuarlo se activa otra versión, el vector no corresponde al modelo.

A) **governance sirve el `feature_spec` y la versión viaja en la solicitud**:
   - governance guarda el `feature_spec` verificado al registrar y lo sirve en `GET /v1/models/{id}/feature-spec` (inmutable);
   - flujo nuevo F104 case-service → governance, con `governance:read-serving` y el scope nuevo `governance:read-feature-spec`;
   - en cada intento, case-service arma el vector con la versión activa y la envía en `ScoringRequest.model_version_id`;
   - scoring la compara con su `serving-config` **antes** de `:predict`; si difiere → `FailClosed(version_mismatch)` sin llamadas;
   - cambios en U0 (campo nuevo; BR-U0-01/02/08 con las versiones pedida y servida), U2, U4, U7 e inventario.

   (Recomendado)

B) **scoring arma el vector** con la solicitud sin identificadores directos; scoring recibe datos crudos del solicitante

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Máquina de estados del caso (Business Logic, US-107, US-112)

A)
- Transiciones:
  - ingesta → `en_evaluacion`;
  - `Recommendation` → `listo`;
  - fail-closed reintentable → `en_sincronizacion`;
  - intento 6 fallido → `no_disponible`;
  - `model_frozen` → `modelo_congelado`;
  - `modelo_congelado` vuelve a `en_evaluacion` cuando `serving-config` está activo de nuevo (barrido cada 5 min);
  - `no_disponible` vuelve a `en_evaluacion` con un `retry` del CRO;
  - decisión confirmada → `decidido`;
  - retención vencida sin decisión → **`vencido`**, desde cualquier estado no terminal.
- `decidido` y `vencido` son terminales. Un caso `listo` nunca se reevalúa.
- Si la versión de un caso `listo` se congela, el caso sigue `listo` con el aviso `model_frozen_after_recommendation`.
- La bandeja oculta `vencido` por defecto.

(Recomendado)

B) Como A, pero sin `vencido`: los casos anonimizados sin decisión conservan su estado y la bandeja los oculta por una marca

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Reintentos y cola (Business Logic / Error Handling, FR-SCO-05/06, US-112)
Cola transaccional en `case-db` (`FOR UPDATE SKIP LOCKED`), timeout de 7 s hacia scoring y
escalamiento con el gauge `vectra_cases_failclosed_persistent`, igual en A y en B.

A) 6 intentos: el primero inmediato y luego esperas de 30 s, 1, 2, 4 y 8 min (base 30 s, factor 2, jitter ±20 %). Suman **930 s ≈ 15,5 min** (recomendado)

B) 6 intentos con base de 1 min: esperas de 1, 2, 4, 8 y 16 min, unos **31 min**

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Quién escribe las entradas `fail_closed` (Integration; ambigüedad entre BR-U0-08, BR-U7-16 y `services.md` S2)

A)
- scoring escribe la entrada de cada intento (BR-U7-16).
- case-service escribe **una** al escalar a `no_disponible`: con la última causa, `retryable = false`, `attempt = 6`, `escalated_at` y la llave `UUIDv5(case_id, "fail_closed", escalation_count)`, para que cada escalamiento tenga la suya.
- BR-U0-08 se precisa en ese sentido.

(Recomendado)

B) case-service escribe además una entrada por cada intento fallido

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Reglas de la decisión y evidencia en dos fases (Business Rules, US-108, US-502, BR-U0-35)

A)
- **Quién y cuándo**: solo `analista`, solo con el caso `listo`, una decisión por caso.
- **Factores**: subconjunto de los del `shap_vector`, o `["ninguno"]`.
- **Justificación**: de 20 a 2000 caracteres en `se_aparta` y `resuelve_revision`; opcional en `sigue` (BR-U0-36 nueva).
- **`explanation_viewed_before`**: lo calcula el sistema para el mismo usuario.
- **Evidencia en dos fases** con un outbox:
  - la llave **determinista** `UUIDv5(case_id, "human_decision")` hace que el registro admita una sola decisión por caso;
  - a las 24 h sin ack la decisión pasa a `abandonada` y el caso acepta otra;
  - si la abandonada sí estaba en el registro, la nueva recibe 409: se confirma la abandonada y se responde `409 conflict_state` con `reason = decision_already_recorded`. Esto requiere el campo `Problem.reason`, con catálogo cerrado, en U0 §6.

(Recomendado)

B) Escritura directa sin fase pendiente; justificación opcional en todos los casos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Consulta de la explicación (Business Rules, US-501)

A) Solo la primera consulta por caso y usuario, con la llave `UUIDv5(case_id, user_id)` y `viewed_at` en el payload. Permitida en `listo` y `decidido`, incluidos los casos `decidido` anonimizados (recomendado)

B) Una entrada por cada apertura

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Retención y eliminación de identificadores (Business Rules, NFR-U3-03, Ley 1581)

A)
- **Plazos**: 10 años desde la decisión, o 2 años sin decisión **[VERIFICAR]**.
- **Ejecución**: un CronJob `case-retention`, con el rol propio `case_retention` (flujo F105):
  - borra `case_identifiers` y el `free_text`;
  - marca `anonymized_at`;
  - pasa los no decididos a `vencido`.
- **Permisos**: `case_app` no puede borrar identificadores (`DELETE` solo sobre la cola). Un trigger `guard_vencido` asegura que solo `case_retention` escriba `vencido`.

(Recomendado)

B) Conservar los identificadores hasta una decisión posterior de cumplimiento

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Lectura del estado de crédito (Integration, F17)

A)
- `GET /v1/credits/{case_id}` (el `case_id` es la referencia externa), solo para casos `decidido`, con timeout de 500 ms y sin caché.
- Un fallo → `no_disponible`; un 404 → `sin_credito`.
- La escritura del mock responde 403 y registra el intento para RT-5.

(Recomendado)

B) Copiar periódicamente el estado del core a `case-db`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Ingesta: duplicados y escenarios adversariales (Business Rules, US-101)

A)
- **Duplicados**: `Idempotency-Key` obligatoria por cliente del canal.
  - Mismo cuerpo → el mismo caso.
  - Otro cuerpo → 409.
- **Escenarios**: la cabecera `X-Test-Scenario` solo para el simulador y fuera de producción.
  - No usa el prefijo `x-vectra-`, que U2 reserva para cabeceras internas y elimina en el gateway (se precisa en P-U2-06).
  - Se guarda como `test_scenario_id` y nunca sale hacia scoring ni hacia el registro.

(Recomendado)

B) Sin idempotencia; los duplicados los evita el canal

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Evidencia que llega tarde al registro (defecto previo en U3; afecta a U4 y a U8)
**Hallazgo.** BR-U3-05 rechaza `occurred_at` fuera de ±5 min, y BR-U3-06 compara el contenido
incluyendo `occurred_at`. Un reintento del reconciliador después de 5 min (U4 reintenta hasta
24 h; el outbox de U8, igual) se rechaza siempre. Ahora mismo, un `freeze` de U4 escrito tarde
nunca entraría a la cadena.

A) **Corregir en U3, U0 y U4**:
   - la ventana se comprueba solo para llaves nuevas y después de la idempotencia;
   - la comparación de contenido excluye `occurred_at`, que pasa a ser el momento del intento;
   - el momento de negocio viaja en el payload (`decided_at`, `viewed_at`, `frozen_at`, `escalated_at`) con la cota de BR-U0-37 nueva: ≤ `occurred_at` y como mucho 7 días antes;
   - en U4: llave determinista `UUIDv5(entidad, n)` con `n` = no abandonadas + 1, una sola transición pendiente por entidad (salvo `freeze`), y el reconciliador escribe en orden de `n`, tomando solo la menor pendiente de cada entidad.

   (Recomendado)

B) No corregir ahora; dejarlo anotado como riesgo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Respaldo en U0 del circuit breaker que usa U7 (defecto previo en U0)
**Hallazgo.** U7 delega en `vectra_common.deps` los timeouts, el presupuesto propagado y el
circuit breaker, pero en U0 ningún requisito ni propiedad lo respalda. La fila «RESILIENCY-* N/A
en U0» y «PBT-06 N/A» están desactualizadas.

A) **Corregir**:
   - NFR-U0-23 con su verificación;
   - PBT-U0-14 (stateful del breaker);
   - `deps` y `deadline` en los umbrales de 100 % de ramas y `mutmut` (NFR-U0-40/41);
   - filas RESILIENCY-10 y PBT-06 en «Cumple»;
   - httpx y prometheus-client en el stack;
   - módulo `deps` en las tablas de U0;
   - referencias desde U7 (NFR-U7-11/43 y filas PBT-06).

   (Recomendado)

B) No corregir ahora; dejarlo anotado como riesgo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, historias, C03/C04, S1/S2, tipos de U0, pendientes de U3/U5/U7, flujos de U8)
- [x] 2. Recoger y validar las respuestas (Q1–Q11 = A)
- [x] 3. Generar `construction/case-management/functional-design/domain-entities.md`
- [x] 4. Generar `construction/case-management/functional-design/business-rules.md`
- [x] 5. Generar `construction/case-management/functional-design/business-logic-model.md` (máquina de estados, flujos y PBT, incluidas las stateful)
- [x] 6. Aplicar y registrar los cambios en otras unidades según las respuestas, y propagarlos a Application Design
- [x] 7. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
