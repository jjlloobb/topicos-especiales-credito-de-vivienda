# Segunda revisión del Functional Design — U0 `contracts`

**Fecha:** 2026-10-03
**Alcance:** los tres artefactos de `construction/contracts/functional-design/` después de
aplicar la primera revisión (`contracts-functional-design-review-questions.md`).

U0 es la única unidad con trabajo en CONSTRUCTION. Las otras 12 siguen pendientes.

---

## Parte A — Hallazgos

### Importantes

**N1 — Hay un ciclo entre `build_outcome` y el registro.**
- `Recommendation` exige un `registry_ack` (condición 9).
- Pero la entrada `recommendation` del registro guarda `score`, `outcome`, `reasons` y `explanation`, es decir, el resultado que la fábrica todavía no ha decidido.
- Además, si fallan las condiciones 1–8, no se debería escribir una entrada `recommendation`, y saber eso exige evaluar la tabla **antes** de llamar al registro.
- Tal como está, scoring tendría que adivinar el resultado o duplicar la tabla de causas fuera de la fábrica, que es justo lo que BR-U0-01 prohíbe.

**N2 — La firma no admite dependencias no invocadas.**
- Si `serving_state = no_disponible`, el explicador y el registro nunca se llaman.
- Aun así, la firma exige `explanation | ExplainerError` y `registry_ack | RegistryError`, y business-logic-model §2.2 dice «llama igual sin `prediction`».
- Hace falta poder decir «no se invocó» sin inventar un error.

**N3 — Una salida inválida del modelo se reporta como `serving_config_unavailable`.**
- BR-U0-07 usa esa causa para un `score` `NaN`, infinito o fuera de [0, 1]. Pero la configuración de serving sí está disponible: lo que falla es el modelo.
- Esto engaña al diagnóstico del CRO (`list_persistent_failures`) y a las alertas.

**N4 — `DecisionIn` no cubre la recomendación `revision_requerida`.**
- `decision` es `sigue | se_aparta` y `final_outcome` es `favorable | desfavorable`.
- Si la recomendación es `revision_requerida`, «sigue» no tiene sentido, porque no hay un resultado al cual adherirse.
- Esto afecta directamente a la North Star (decisiones donde la explicación sustenta o cambia la decisión del comité).

### Menores (los corrijo sin preguntar al aplicar los cambios)

- **N5**: `feature_vector_hash` dice «`FeatureVector` canónico», pero no define la canonicalización. Sin ella, el expediente no puede recalcular el hash. Propongo JSON canónico RFC 8785 (JCS) sobre la representación de BR-U0-15.
- **N6**: el *deny by default* de BR-U0-71 rechazaría al arrancar los health checks y `/metrics`, que no llevan token. Según `component-dependency.md`, esos endpoints viven en el puerto 8081, separado de la API. Aclaro que el middleware de autorización aplica al puerto de la API (8080) y que el 8081 no expone rutas de negocio.
- **N7**: la `Recommendation` tiene `evaluated_at` y `feature_vector_hash`, pero el payload `recommendation` del registro no los incluye. El expediente debe poder reconstruir la `Recommendation` completa desde el registro, así que los agrego al payload.

### Higiene del repositorio (sigue pendiente, no es del FD)

- Siguen ahí las copias `*original.md` y el archivo swap `.limite-autonomia.md.swp`.

---

## Parte B — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1
¿Cómo se rompe el ciclo entre `build_outcome` y el registro (N1)?

A) **Dos fases sobre la misma tabla.**
   - `check_preconditions(...)` evalúa las causas 1–8 y devuelve `Ready(prediction, policy_result, explanation)` o `FailClosed`.
   - Solo con `Ready`, scoring escribe la entrada `recommendation` en el registro.
   - Después llama a `build_outcome(ready, registry_ack | RegistryError)`, que solo evalúa la causa 9 y es la única que construye `Recommendation`.
   - `Ready` solo lo construye `check_preconditions` (recomendado: no se duplica la tabla y lo que se registra es exactamente lo que se entrega).

B) **Borrador y sellado.** `build_outcome` devuelve un `RecommendationDraft` (sin `registry_entry_id`) o `FailClosed`. scoring registra el borrador y `seal(draft, ack)` produce la `Recommendation`.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
¿Cómo se representa «no se invocó» en las entradas (N2)?

A) Los parámetros de dependencias son opcionales. La tabla de BR-U0-02 añade que un parámetro ausente solo es válido si una causa anterior ya aplicó. Si falta sin causa previa, la función falla con `explainer_unavailable` o `registry_unavailable` según el caso, nunca con una `Recommendation` (recomendado)

B) Se agrega un valor explícito `not_called` a `ExplainerError` y a `RegistryError`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
¿Qué causa produce una salida inválida del modelo (N3)?

A) Una causa nueva, `model_output_invalid`, que queda en la posición 3 de la precedencia, después de `serving_config_unavailable`. Tiene `retryable = true`, y el presupuesto de reintentos de case-service termina en `no_disponible`, como el resto. El catálogo pasa a 10 causas (recomendado)

B) Se mantiene `serving_config_unavailable`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
¿Cómo registra el analista su decisión cuando la recomendación es `revision_requerida` (N4)?

A) `decision` admite un tercer valor, `resuelve_revision`, válido **solo** si la recomendación fue `revision_requerida`. `sigue` y `se_aparta` quedan para `favorable` y `desfavorable`, y `sigue` exige `final_outcome == recommendation.outcome`. U0 fija la forma. La validación cruzada contra la recomendación del caso la implementa U8 (recomendado)

B) Con `revision_requerida` siempre se registra `se_aparta`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte C — Resolución (Q1–Q4 = A)

- [x] N1 → BR-U0-01 y BR-U0-08: `check_preconditions` (causas 1–9, único constructor de `Ready`) → append de la entrada `recommendation` desde `Ready` → `build_outcome` (causa 10, único constructor de `Recommendation`)
- [x] N2 → dependencias opcionales; ausencia sin causa previa = causa 5 o 10 (BR-U0-02, domain-entities §3.6)
- [x] N3 → causa `model_output_invalid` en la posición 3; el catálogo pasa a 10 causas; BR-U0-07 y PBT-U0-12 actualizadas; nota de `component-methods.md` ajustada
- [x] N4 → `resuelve_revision` en `DecisionIn` y en el payload `human_decision`; BR-U0-35 (`conflict_state`), comprobación contra el caso en U8
- [x] N5 → `feature_vector_hash` con JCS (RFC 8785)
- [x] N6 → BR-U0-71 limitado al puerto 8080; health y `/metrics` en 8081
- [x] N7 → `evaluated_at` y `feature_vector_hash` en el payload `recommendation`
- [x] PBT-U0-01 redefinida sobre la composición de las dos fases; pruebas de ejemplo ampliadas
