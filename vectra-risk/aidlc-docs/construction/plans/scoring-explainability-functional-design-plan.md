# Plan de Functional Design — U7 `scoring-explainability`

**Alcance de la unidad** (`unit-of-work.md` §1): dos servicios en una unidad.
- **`scoring-service`**:
  - lectura de `serving-config` con TTL;
  - predictor y motor de política (corte, baja confianza, VIS y usura);
  - llamada a la explicación y verificación de versión;
  - append al registro antes de responder;
  - circuit breakers y `FailClosed` tipificado.
- **`explainability-service`**:
  - vector SHAP del explicador;
  - `TemplateNarrativeGenerator` y `FactualityValidator`, detrás de la interfaz `NarrativeGenerator`;
  - resumen para el solicitante.

**Historias (dueña):** US-103, US-104, US-105, US-106, US-109, US-110, US-111, US-113, US-207.

**Ya decidido** (no se pregunta):
- invariante en dos fases `check_preconditions` → append → `build_outcome`, 10 causas y su precedencia, cuantización de la predicción, transporte en 200 (U0 BR-U0-01..08);
- `ScoringRequest` (features + `monitoring_labels` + `policy_inputs`), `ExplainRequest`, `ApplicantSummary` (U0 §9.1); `free_text` nunca llega a scoring ni a explicabilidad (BR-U0-29);
- `serving-config` con `etag`, `inference_service`, `normative_current`, caché ≤ 5 s con `If-None-Match`, sin configuración vencida (U4, NFR-U4-02);
- predictor de un solo proceso y explicador con TreeSHAP nativo; `base_value` = término de sesgo (U6);
- append al registro con `idempotency_key` por intento, 503 en ≤ 2,5 s si no hay réplica síncrona (U3);
- métrica de `version_mismatch` para la alerta `PromotionMismatchPersistent` (pendiente de U4).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Parámetro normativo no vigente: conflicto entre una historia y U4 (Business Rules, US-207)
**Hay dos decisiones aprobadas que se contradicen:**
- US-207: «si no hay tope vigente para la fecha de evaluación → la recomendación es `revision_requerida` con el motivo "parámetro normativo no vigente"».
- U4 FD Q4 (BR-U4-11) y U0 `ServingState`: `normative_current` nulo → `serving_config_unavailable`, es decir, **fail-closed**, sin recomendación.

A) **Seguir la historia**: sin parámetro vigente, scoring entrega una recomendación completa (con explicación y registrada) con `outcome = revision_requerida` y el motivo `parametro_normativo_no_vigente`. Un humano decide. La alerta `NormativeParamsExpiring` (SEV1 el día del vencimiento) sigue igual. Se corrigen U4 (BR-U4-11) y U0 (`ServingState`: `normative_current` nulo **ya no** es `no_disponible`) (recomendado: el fail-closed protege la sincronía de la explicación; aquí la explicación es válida y el riesgo lo cubre la revisión humana obligatoria)

B) **Mantener U4**: fail-closed sin recomendación, y se corrige US-207

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2 — Qué significa el `score` (Domain Model)

A) **Probabilidad de incumplimiento (PD)** en [0, 1]: más alto = más riesgo. `favorable` si `score < cutoff`. La consola lo muestra como «riesgo estimado» (recomendado: es lo que produce el modelo de referencia y lo que entiende el área de riesgo)

B) Puntaje de aprobación (más alto = mejor)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3 — Orden de las reglas de la política y cómo se combinan los motivos (Business Rules, US-103, US-106, US-207)

A) **Todas las reglas se evalúan y todos los motivos se acumulan**; el `outcome` es el más conservador:
   1. sin parámetro normativo vigente → `revision_requerida` (`parametro_normativo_no_vigente`), si la Q1 es A;
   2. `proposed_rate_ea` **>** tope de usura vigente → `revision_requerida` (`tasa_sobre_usura`); igual al tope **no** es «sobre»;
   3. `confidence` **<** `low_confidence_threshold` → `revision_requerida` (`baja_confianza`);
   4. corte (el de la regla del canal si existe; si no, el general): `score < cutoff` → `favorable` (`score_bajo_corte`); si no → `desfavorable` (`score_sobre_corte`);
   5. clasificación VIS, siempre como motivo informativo: `vis` si `property_value ≤ vis_max_property_value`, si no `no_vis`.

   Si se cumple 1, 2 o 3, el `outcome` es `revision_requerida` aunque el corte diga otra cosa (recomendado)

B) Las reglas se evalúan en orden y se detienen en la primera que aplica (un solo motivo)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4 — De dónde saca explicabilidad el diccionario de features (Integration, U0 Q5)
**Hueco en el inventario.** U0 decidió que «U5 produce el diccionario, governance lo registra
con la versión y explicabilidad lo usa». Pero no hay ningún flujo de explicabilidad hacia
governance ni hacia el model-store, y la narrativa y el resumen al solicitante necesitan
las etiquetas y frases del diccionario.

A) **Governance lo sirve**: al registrar, governance guarda el `feature_dictionary.json` verificado (ya lo lee para el checksum, BR-U4-06) y lo expone en `GET /v1/models/{id}/feature-dictionary`. explicabilidad lo cachea por `model_version_id` (es inmutable). Requiere un flujo nuevo (explicabilidad → governance) y un scope `governance:read-dictionary` en el catálogo de U0 (recomendado: una sola fuente, ya verificada)

B) explicabilidad lo lee directamente del model-store con una credencial de solo lectura (flujo nuevo hacia `vectra-data`)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5 — Plantilla de la narrativa (Business Logic, US-104)

A) **Los 5 factores de mayor |SHAP|** (o todos, si son menos), en orden descendente. Cada factor en una línea: `label_es` + la frase de dirección del diccionario (`increases_risk_phrase_es` o `decreases_risk_phrase_es`, según el signo) + una intensidad relativa: «fuerte» si aporta ≥ 30 % de la suma de |SHAP| de los 5, «moderada» si aporta entre 10 % y 30 %, «leve» si menos. Encabezado fijo con el método («SHAP»), la versión de modelo y `template:v1`; al final, la leyenda post-hoc. Sin números de SHAP en el texto (recomendado)

B) Todos los factores con su valor SHAP numérico

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6 — Cómo valida la factualidad (Business Logic, US-105)

A) **Validación estructural, independiente de la generación**: el validador **no** reutiliza el código del generador.
   - Parte de la narrativa por líneas y, para cada línea, identifica la `label_es` y la frase de dirección usando el diccionario.
   - Exige que el conjunto, el orden y el signo de los factores coincidan con los 5 de mayor |SHAP| del vector, y que estén el encabezado y la leyenda.
   - Cualquier diferencia (omisión, reordenamiento, signo invertido, factor ajeno o texto extra) → `factuality_failed`.

   (Recomendado: un error en el generador no se valida a sí mismo)

B) Comparar la narrativa con una segunda ejecución del mismo generador

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7 — Resumen para el solicitante (Business Logic, US-110)

A)
   - Se genera **bajo demanda** (rol `analista` o `cro`), solo si el caso tiene decisión final `desfavorable` y una explicación sincronizada en el registro (F23); si no, `409`.
   - Contenido: hasta **3** factores con `applicant_safe = true` que empujaron hacia más riesgo (SHAP > 0), en orden, con una plantilla de lenguaje llano distinta de la del analista, más la leyenda post-hoc.
   - Sin valores SHAP, sin `model_version_id`, sin `score` y sin datos de otros solicitantes.
   - No se guarda. Se registra un log técnico sin contenido (`event = applicant_summary.generated`, con `case_id`).

   (Recomendado)

B) Se genera automáticamente con cada decisión desfavorable y se guarda en el caso

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, historias, requisitos FR-SCO/FR-EXP, decisiones de U0, U3, U4, U5 y U6)
- [ ] 2. Recoger y validar las respuestas
- [ ] 3. Generar `construction/scoring-explainability/functional-design/domain-entities.md`
- [ ] 4. Generar `construction/scoring-explainability/functional-design/business-rules.md`
- [ ] 5. Generar `construction/scoring-explainability/functional-design/business-logic-model.md` (flujos de scoring y explicabilidad; PBT)
- [ ] 6. Aplicar y registrar los cambios a otras unidades que resulten (Q1, Q4)
- [ ] 7. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
