# Revisión de `component-methods.md` contra U0

**Fecha:** 2026-10-03
**Alcance:** `inception/application-design/component-methods.md` (aprobado en INCEPTION), comparado con el
Functional Design aprobado de U0 (`construction/contracts/functional-design/`) y con
`component-dependency.md`.

En la primera revisión (Q6=A) se decidió poner solo una nota que remite a U0. Pero el
documento todavía tiene texto **normativo** que contradice a U0. Un equipo que lo lea sin
abrir U0 (p. ej. al hacer el FD de U7 o U8) implementaría algo incorrecto.

---

## Parte A — Hallazgos

### Contradicen a U0

**C1 — El bloque de «Tipos compartidos» y el párrafo del invariante están desactualizados.**
- `score` y `confidence` como `float`.
- 7 causas de `FailClosed`, cuando son 10.
- Faltan `kind`, `evaluated_at`, `feature_vector_hash` y `occurred_at`.
- `reasons: list[str]` en vez de `ReasonCode`.
- El invariante describe 3 condiciones y una sola fase, cuando U0 define 10 causas en dos fases (`check_preconditions` → registro → `build_outcome`).
- La nota de arriba solo menciona parte de estas diferencias.

**C2 — `apply_policy(score, confidence, app, policy)` (C05).** scoring nunca recibe la
solicitud (`app`). Recibe `ScoringRequest`, que trae `policy_inputs`, y devuelve
`PolicyResult`, no `Outcome`. La descripción de `recommend` tampoco menciona
`policy_inputs`.

**C3 — Llamadores de `append` (C12).** Lista a `bias` como escritor del registro. U0 eliminó
`registry:append:bias`: el congelamiento lo registra governance (F24). Además, el método
devuelve `RegistryEntryRef`, mientras que U0 lo llama `RegistryAck`.

**C4 — Llamadores de `query` (C12).** No incluye a `explainability-service`, que lee el
registro para el resumen al solicitante (F23, scope `registry:read:explanation`).

**C5 — `record_decision` (C04).** Dice «sigue/se aparta», pero falta `resuelve_revision` (S4, BR-U0-35).

**C6 — Encabezado «Todos los endpoints exigen JWT».** Los health checks y `/metrics` del puerto
8081 no llevan token (BR-U0-71). Hay que aclarar que la regla es para la API (8080).

### Hueco en U0 que esta revisión destapó

**C7 — No hay scope para `core-banking-mock`.**
- F17 dice «authz del mock: solo `GET`», pero el catálogo de scopes de U0 (domain-entities §7.2) no tiene ningún scope para leer el estado de crédito.
- Con el *deny by default* de BR-U0-71, `GET /v1/credits/{id}` no puede declarar requisitos y el mock no arrancaría.
- `update_credit_status`, que existe solo para demostrar el bloqueo RT-5, necesita un scope que **nadie** tenga, para que el intento falle por autorización además de por NetworkPolicy.
- Corregirlo toca el FD de U0, que ya está aprobado.

---

## Parte B — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1
¿Cómo se corrige el texto desactualizado de `component-methods.md` (C1)?

A) **Reemplazar** el bloque de tipos y el párrafo del invariante por un resumen breve, alineado con U0. Los tipos solo se nombran, sin campos, y el invariante se resume en una línea que remite a BR-U0-01..08. La nota de fuente autoritativa se mantiene. Así no quedan dos definiciones que puedan divergir otra vez (recomendado)

B) **Mantener** el bloque como histórico, marcado «SUPERSEDED, ver U0», y completar en la nota la lista de diferencias

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
¿Cómo se autoriza el acceso a `core-banking-mock` (C7)?

A) Agregar al catálogo de U0:
   - `core:read-credit`, otorgado **solo** a case-service, para `GET /v1/credits/{id}`;
   - `core:write-credit`, que **no se otorga a ninguna identidad**, como requisito de `POST /v1/credits/{id}/status`. Así, RT-5 falla con 403 aunque una NetworkPolicy estuviera mal.

   Se registra como corrección al FD aprobado de U0. U2 no crea ningún cliente con `core:write-credit` (recomendado: defensa en profundidad para AUTONOMIA-03)

B) Solo `core:read-credit`. El endpoint de escritura queda protegido únicamente por la NetworkPolicy y por la restricción de método

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte C — Correcciones que aplico sin preguntar (C2–C6)

- C2: `apply_policy(score: Decimal4, confidence: Decimal4, inputs: PolicyInputs, policy: PolicyVersion) -> PolicyResult`; añadir `policy_inputs` a `recommend`.
- C3: `append` → `RegistryAck`; llamadores: scoring, case y governance.
- C4: añadir explainability a `query` (F23).
- C5: «sigue / se aparta / resuelve_revision».
- C6: aclarar que la regla de JWT aplica al puerto de la API (8080).

---

## Parte D — Resolución (Q1–Q2 = A)

- [x] C1 → bloque de tipos y párrafo del invariante reemplazados por una tabla que nombra los tipos y remite a U0, más un resumen de una línea del invariante en dos fases
- [x] C2 → `apply_policy(score: Decimal4, confidence: Decimal4, inputs: PolicyInputs, policy: PolicyVersion) -> PolicyResult`; `recommend` incluye `policy_inputs` y devuelve `RecommendResult`
- [x] C3 → `append -> RegistryAck`; llamadores: scoring, case y governance
- [x] C4 → explainability en `query` (F23)
- [x] C5 → `resuelve_revision` en `record_decision`
- [x] C6 → regla de JWT limitada al puerto 8080; 8081 sin token
- [x] C7 → `core:read-credit` (case-service) y `core:write-credit` (ninguna identidad) en domain-entities §7.2; C15 y F17 de `component-dependency.md` actualizados
