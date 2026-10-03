# Entidades de dominio — U7 `scoring-explainability`

Decisiones del plan (`scoring-explainability-functional-design-plan.md`, Q1–Q7 = A). Los dos
servicios son **sin estado**: no tienen base de datos propia. Los tipos de la API
(`ScoringRequest`, `PolicyInputs`, `RecommendResult`, `Recommendation`, `FailClosed`,
`Explanation`, `ExplainRequest`, `ApplicantSummary`, `ReasonCode`) son de U0 y no se
redefinen aquí.

---

## 1. Significado del score (Q2)

`score` = **probabilidad de incumplimiento (PD)** en [0, 1], cuantizada a `Decimal4`
(BR-U0-07): más alto = más riesgo. En la consola se muestra como «riesgo estimado».

## 2. Entrada de la política

### `PolicyEvaluationInput` (interno de scoring)

| Campo | Origen |
|---|---|
| `score`, `confidence` | `Prediction` cuantizada (U0 §3.6) |
| `property_value`, `proposed_rate_ea`, `channel` | `ScoringRequest.policy_inputs` |
| `cutoff`, `low_confidence_threshold`, `channel_rules` | Política activa (`policy_version_id` de `serving-config`) |
| `normative` | `serving-config.normative_current` (puede ser nulo, Q1) |

### `PolicyResult` (U0 §3.6)
`policy_version_id`, `outcome`, `reasons: list[ReasonCode]` (ordenada según BR-U7-05).

## 3. Narrativa (Q5)

### `NarrativeLine`
`feature_id`, `label_es`, `direction` (`aumenta` \| `reduce`), `intensity` (`fuerte` \|
`moderada` \| `leve`).

### Forma del texto (`template:v1`)

```text
Explicación del riesgo estimado — método SHAP · modelo <model_version_id> · plantilla template:v1
1. <label_es>: <frase de dirección> (influencia <intensidad>).
2. ...
(hasta 5 líneas, en orden de |SHAP| descendente)
<posthoc_notice>
```

- `<frase de dirección>` = `increases_risk_phrase_es` si el SHAP es > 0, o `decreases_risk_phrase_es` si es < 0.
- Un SHAP exactamente 0 no entra entre los 5.
- `posthoc_notice` (fijo, i18n): «Aproximación post-hoc: describe qué variables movieron el riesgo estimado; no es una lectura del razonamiento del modelo».

### Intensidad
Con `S = Σ |SHAP|` de los factores mostrados: `fuerte` si `|SHAP_i| / S ≥ 0,30`, `moderada`
si está en [0,10; 0,30) y `leve` si es < 0,10.

## 4. Resumen para el solicitante (Q7)

### `ApplicantSummary` (U0 §9.1)
`case_id`, `factors` (hasta 3: `label_es`, `direction = aumenta`), `posthoc_notice` y
`generated_at`. Plantilla `applicant:v1`, en lenguaje llano, distinta de la del analista.

Se pide con `ApplicantSummaryRequest` (U0 §9.1): `case_id` y `recommendation_entry_id`,
que el BFF toma del caso (precisado el 2026-10-03 por U7 NFR Design Q3).

**Campos prohibidos** (nunca presentes): valores SHAP, `model_version_id`, `score`,
`confidence`, `policy_version_id`, `feature_vector` y cualquier dato de otro caso.

## 5. Errores tipificados del explicador (hacia scoring)

`explainability-service` responde a `POST /v1/explanations` con una `Explanation` (200) o
con un error tipificado que scoring convierte en `ExplainerError` (U0 §3.6):

| Situación | Código HTTP | `ExplainerError` |
|---|---|---|
| El `model_version_id` pedido no coincide con el que devuelve el explicador de KServe | 409 `conflict_state` + `reason = version_mismatch` | `version_mismatch` |
| El diccionario no cubre un factor del vector | 422 + `reason = feature_dictionary_incomplete` | `feature_dictionary_incomplete` |
| La narrativa no pasa la validación | 422 + `reason = factuality_failed` | `factuality_failed` |
| KServe no responde a tiempo | 504 | `timeout` |
| KServe o el diccionario no disponibles (503, circuito abierto) | 503 | `unavailable` |
| Cualquier otro error | 500 | `error` |

El cuerpo del error es un `Problem` (U0) con un campo de extensión `reason` del catálogo de
la tabla. Ningún otro dato.

## 6. Caché

| Dato | Dónde | Duración |
|---|---|---|
| `serving-config` | scoring | ≤ 5 s, con `If-None-Match` (BR-U4-14) |
| Diccionario de features | explainability, por `model_version_id` | Sin vencimiento: es inmutable (BR-U4-18) |
| Diccionario de features | explainability | Se descarta el de versiones que no se usaron en 24 h (memoria acotada) |
