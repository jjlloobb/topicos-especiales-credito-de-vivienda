# Modelo de lógica — U7 `scoring-explainability`

## 1. Módulos lógicos

| Servicio | Módulo | Responsabilidad | Reglas |
|---|---|---|---|
| scoring | `orchestrator` | Secuencia de BR-U0-08 con `check_preconditions`/`build_outcome` de U0 | BR-U7-01, 15, 16 |
| scoring | `policy` | Función pura `evaluate(PolicyEvaluationInput) -> PolicyResult` | BR-U7-04..07 |
| scoring | `serving_config_client` | Caché ≤ 5 s con `If-None-Match` | BR-U7-01 |
| scoring | `clients` | KServe `:predict`, explainability, registro (con `deps.call` de U0) | BR-U7-01, 15 |
| explainability | `explain` | `:explain` + verificación de versión + diccionario | BR-U7-08, 09 |
| explainability | `narrative` | `TemplateNarrativeGenerator` (`template:v1`), detrás de la interfaz `NarrativeGenerator` | BR-U7-10 |
| explainability | `factuality` | `FactualityValidator` independiente | BR-U7-11 |
| explainability | `applicant` | Resumen al solicitante (`applicant:v1`) | BR-U7-13, 14 |

`policy`, `narrative`, `factuality` y `applicant` son funciones puras y se prueban con
propiedades. El contrato de import-linter impide que `factuality` importe `narrative`.

## 2. Flujos

### 2.1 Recomendación

```text
case -> POST /v1/recommendations (ScoringRequest)
scoring:
  serving-config (caché <= 5 s) ; fallo -> serving_state = no_disponible
  si activo: KServe :predict (isvc de serving-config) -> cuantizar (fuera de [0,1] -> model_output_invalid)
           policy.evaluate(...) -> outcome + reasons   (normative nulo -> revision_requerida)
           explainability POST /v1/explanations -> Explanation | error tipificado
  check_preconditions(...) -> FailClosed -> append fail_closed (best effort) -> 200 FailClosed
                           -> Ready -> append recommendation (idempotency_key del intento)
  build_outcome(ready, ack | RegistryError) -> 200 RecommendResult
```

### 2.2 Explicación

```text
scoring -> POST /v1/explanations (case_id, model_version_id, features, prediction_score)
explainability:
  diccionario de la versión (caché; si falta: GET /v1/models/{id}/feature-dictionary, F103)
  KServe :explain (isvc pedido) -> contribuciones, base_value, model_version_id
     versión distinta -> 409 version_mismatch
  ¿el diccionario cubre todos los factores? no -> 422 feature_dictionary_incomplete
  narrative.generate(top 5) -> texto
  factuality.validate(texto, vector, diccionario) ? no -> 422 factuality_failed
  -> 200 Explanation (factuality_check = "passed", feature_dictionary_version, posthoc_notice)
```

### 2.3 Resumen al solicitante

```text
BFF (analista | cro): ¿decisión final desfavorable? (case-service, regla de objeto de C03) no -> 409
BFF -> POST /v1/applicant-summaries {case_id, recommendation_entry_id del caso}
explainability: registro F23 (proyección explanation, entrada seq = recommendation_entry_id)
   ¿existe, es del case_id y tiene explicación? no -> 409
   applicant.generate(hasta 3 factores applicant_safe con SHAP > 0) -> ApplicantSummary
   log applicant_summary.generated (case_id), sin contenido
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U7-01 | `policy` | `outcome` ∈ {favorable, desfavorable, revision_requerida} para toda entrada; si `normative` es nulo, la tasa supera el tope o `confidence` < umbral, el `outcome` es `revision_requerida`; `reasons` sigue el orden de BR-U7-04 sin duplicados | Invariante | `score`/`confidence` en [0,1], tasas y valores alrededor de los umbrales, `normative` nulo o no, reglas por canal |
| PBT-U7-02 | `policy` | Bordes: `proposed_rate_ea == usury_cap_ea` no da `tasa_sobre_usura`; `property_value == vis_max` da `vis`; `score == cutoff` da `desfavorable` | Oráculo (bordes) | Valores exactamente en los umbrales y ± el paso de `Decimal4` |
| PBT-U7-03 | `narrative` | Determinismo: `generate(v) == generate(v)`; las líneas están en orden de \|SHAP\| descendente con el desempate de BR-U7-10; nunca más de 5 líneas ni números de SHAP | Idempotencia + invariante | Vectores con empates, ceros, signos mixtos y longitudes de 1 a 30 |
| PBT-U7-04 | `factuality` | `validate(generate(v), v) == True` para todo vector y diccionario que lo cubre | Round-trip | Vectores y diccionarios válidos |
| PBT-U7-05 | `factuality` | Para toda mutación de una narrativa válida (omitir, reordenar, invertir un signo, cambiar un factor, agregar texto, cambiar el encabezado o la leyenda), `validate` da `False` | Invariante (prueba de mutación) | Narrativas válidas × operadores de mutación |
| PBT-U7-06 | `applicant` | El resumen nunca contiene campos prohibidos ni números; solo factores `applicant_safe` con SHAP > 0, como máximo 3 | Invariante | Vectores y diccionarios con `applicant_safe` mixto |
| PBT-U7-07 | `orchestrator` | Para toda combinación de fallos de serving-config, KServe, explainability y registro: la respuesta es siempre 200 `RecommendResult`; una `Recommendation` solo sale con `registry_entry_id` y con la misma versión en predicción y explicación | Invariante (con dobles) | Productos de resultados de cada dependencia (ok, timeout, error, versión distinta) y versión pedida igual o distinta de la de `serving-config` (U8 FD Q1) |
| PBT-U7-08 | `orchestrator` | RT-1: dos `ScoringRequest` derivados de solicitudes que solo difieren en `free_text` dan la misma recomendación y la misma narrativa | Invariante | Pares de solicitudes del conjunto RT-1 de U5 y generados |

**Pruebas de ejemplo obligatorias (PBT-10):**
- recomendación completa con M y P: la respuesta trae `model_version_id = M` y `policy_version_id = P` (US-103);
- narrativa de un caso fijo, comparada con el texto esperado (US-104);
- narrativa con un factor invertido → `factuality_failed` → `FailClosed` (US-105);
- un caso RT-4 → `baja_confianza` y `revision_requerida` (US-106);
- un par RT-1 → salidas idénticas (US-109);
- resumen de un rechazo sin campos prohibidos; caso sin explicación → 409 (US-110);
- explicador de otra versión (RT-3) → `FailClosed(version_mismatch)` (US-111);
- registro sin réplica → `FailClosed(registry_unavailable)` y ninguna recomendación entregada (US-113);
- tasa sobre usura y parámetro normativo no vigente → `revision_requerida` con sus motivos (US-207).

## 4. Cumplimiento de extensiones (Functional Design U7)

Revisada contra el cuerpo de los tres artefactos antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-03 | Cumple | BR-U7-02 (sin cliente ni permiso hacia el core) |
| AUTONOMIA-05 | Cumple | BR-U7-12 (sin `free_text`); el diccionario y la explicación vienen de dentro del clúster (F22, F103) |
| AUTONOMIA-06 | Cumple | BR-U7-01, 08, 15 (fail-closed ante cualquier desincronía o falta de persistencia; nunca un respaldo); PBT-U7-07 |
| SECURITY-05 | Cumple | Validación de `ScoringRequest` (U0); BR-U7-13 (precondiciones del resumen) |
| SECURITY-08 | Cumple | BR-U7-13 (roles del resumen); scopes de F15, F12, F23, F103 |
| SECURITY-11 | Cumple | PBT-U7-05 (mutaciones de la narrativa), PBT-U7-08 y BR-U7-12 (casos de abuso RT-1 de U5) |
| SECURITY-13 | Cumple | Integridad de datos en runtime: BR-U7-08 y domain-entities §5 exigen que la predicción y la explicación sean exactamente de la misma versión antes de que exista una `Recommendation` (`version_mismatch` si no). Además, BR-U7-15: toda recomendación entregada queda auditable en el registro. Nota: la regla principal de esa verificación de versión es AUTONOMIA-06; aquí se cita como el componente de «integridad de datos» de SECURITY-13, distinto de los checksums de artefactos (U4, U6) y de la cadena del registro (U3) |
| SECURITY-15 | Cumple | BR-U7-15, 16; errores tipificados de domain-entities §5 |
| PBT-01 | Cumple | §3 |
| PBT-07 | Cumple | Columna «Generadores» de §3 |
| PBT-10 | Cumple | Pruebas de ejemplo de §3, una por historia |
| PBT-06 | N/A | Servicios sin estado; la máquina de estados del caso es de U8 |
