# Reglas de negocio — U7 `scoring-explainability`

Los IDs `BR-U7-xx` se referencian en los planes de tareas. El invariante de sincronía, las
10 causas de fail-closed y la cuantización son de U0 (BR-U0-01..08) y no se repiten aquí:
U7 los **aplica**.

---

## 1. Scoring: orquestación (US-103, US-111, US-113)

**BR-U7-01 — Secuencia.** scoring sigue exactamente BR-U0-08:
1. `serving-config` (caché ≤ 5 s, `If-None-Match`); si `ScoringRequest.model_version_id` difiere de la versión de `serving-config` → `version_mismatch` sin pasos 2–5 (BR-U0-02 causa 7; precisado el 2026-10-03 por U8 FD Q1);
2. `:predict` al `inference_service` de `serving-config`;
3. cuantización;
4. política (BR-U7-04..07);
5. `POST /v1/explanations`;
6. `check_preconditions`;
7. append de la entrada `recommendation` (o `fail_closed`);
8. `build_outcome`;
9. respuesta 200 con `RecommendResult`.

**BR-U7-02 — Nunca una decisión.** scoring no tiene cliente, ruta ni permiso hacia el core
bancario (FR-SCO-09, X01). Su respuesta es siempre una recomendación o un `FailClosed`.

**BR-U7-03 — Métrica de desincronía.** Cada `FailClosed(version_mismatch)` incrementa
`vectra_scoring_failclosed_total{cause="version_mismatch"}`. La alerta
`PromotionMismatchPersistent` de U4 (BR-U4-08) se calcula sobre esta métrica.

## 2. Política (Q1, Q3; US-103, US-106, US-207)

**BR-U7-04 — Todas las reglas se evalúan.** Para cada solicitud se evalúan las cinco reglas
y se acumulan sus motivos:

| # | Regla | Motivo | Efecto en el `outcome` |
|---|---|---|---|
| 1 | `normative` nulo | `parametro_normativo_no_vigente` | Fuerza `revision_requerida` |
| 2 | `proposed_rate_ea > normative.usury_cap_ea` (igual **no** es «sobre») | `tasa_sobre_usura` | Fuerza `revision_requerida` |
| 3 | `confidence < low_confidence_threshold` | `baja_confianza` | Fuerza `revision_requerida` |
| 4 | `score < cutoff_efectivo` | `score_bajo_corte` → `favorable`; si no, `score_sobre_corte` → `desfavorable` | Base |
| 5 | `property_value ≤ normative.vis_max_property_value` | `vis`; si no, `no_vis`. Si `normative` es nulo, no se clasifica | Informativo |

`cutoff_efectivo` = el `cutoff` de la regla del canal de la solicitud, si existe; si no, el
`cutoff` general de la política.

**BR-U7-05 — Combinación.** Si se cumple la regla 1, 2 o 3, el `outcome` es
`revision_requerida`; si no, el de la regla 4. `reasons` lista los motivos en el orden de la
tabla (sin duplicados). El `outcome` siempre ∈ {`favorable`, `desfavorable`,
`revision_requerida`}.

**BR-U7-06 — Parámetro normativo no vigente (Q1).** Un `normative` nulo **no** es un
fail-closed: la recomendación se entrega completa (con explicación sincronizada y
registrada) con `outcome = revision_requerida` y `parametro_normativo_no_vigente`, como pide
US-207.

**BR-U7-07 — Baja confianza visible (US-106).** Toda recomendación con `baja_confianza` en
`reasons` tiene `outcome = revision_requerida`, y la consola la marca como tal (U10).

## 3. Explicabilidad (Q4, Q5, Q6; US-104, US-105, US-111)

**BR-U7-08 — Misma versión o nada (FR-EXP-02).**
- explainability llama a `:explain` del `inference_service` indicado por scoring en `ExplainRequest`.
- Si el `model_version_id` de la respuesta de KServe no coincide con el pedido → error `version_mismatch`.
- **Nunca** usa un explicador de otra versión, un valor por defecto ni una plantilla genérica.

**BR-U7-09 — Diccionario (Q4).** explainability obtiene el diccionario de la versión con
`GET /v1/models/{id}/feature-dictionary` (F103) y lo cachea por `model_version_id`. Si no
lo puede obtener → `unavailable`. Si no cubre un factor del vector → `feature_dictionary_incomplete`.

**BR-U7-10 — Narrativa determinística (Q5).**
- Hasta 5 factores de mayor |SHAP| (excluidos los SHAP = 0), en orden descendente; los empates se rompen por `feature_id` (orden lexicográfico).
- Frase de dirección según el signo e intensidad según §3 de domain-entities.
- Encabezado con método, versión de modelo y `template:v1`, más la leyenda post-hoc.
- Sin números de SHAP en el texto.
- El mismo vector + la misma plantilla dan exactamente el mismo texto.

**BR-U7-11 — Factualidad (Q6).** El validador es independiente del generador:
1. parte la narrativa en encabezado, líneas y leyenda;
2. en cada línea identifica `label_es` y la frase de dirección contra el diccionario;
3. exige que el conjunto, el orden y el signo de los factores coincidan con los de mayor |SHAP| (la misma regla de selección y desempate de BR-U7-10, implementada por separado), y que el encabezado y la leyenda estén presentes y sin cambios.

Cualquier diferencia (omisión, reordenamiento, signo invertido, factor ajeno, texto
adicional) → `factuality_failed`.

**BR-U7-12 — Texto libre fuera (US-109, RT-1).** Ni scoring ni explainability reciben
`free_text` (BR-U0-29). Dos solicitudes que solo difieren en `free_text` producen el mismo
`FeatureVector`, la misma recomendación y la misma narrativa.

## 4. Resumen al solicitante (Q7; US-110)

**BR-U7-13 — Cuándo se puede.**
- `POST /v1/applicant-summaries` (F12) solo para los roles `analista` o `cro`.
- **El BFF** comprueba que el caso tiene decisión final `desfavorable` (regla de objeto de C03, con el detalle del caso de case-service); si no, `409 conflict_state`.
- **explainability** comprueba que existe la entrada `recommendation` con explicación en el registro (F23); si no, `409 conflict_state`. explainability no ve la decisión humana: su proyección del registro solo trae la explicación (BR-U3-15).
- El BFF envía el `recommendation_entry_id` guardado en el caso (la recomendación **entregada**); explainability lee esa entrada y comprueba que pertenece al `case_id`. Si no, `409 conflict_state`. Así el resumen nunca sale de una entrada escrita y no entregada (precisado el 2026-10-03 por U7 NFR Design Q3).

**BR-U7-14 — Contenido.**
- Hasta 3 factores con `applicant_safe = true` y SHAP > 0, en orden de |SHAP|.
- Plantilla `applicant:v1` y leyenda post-hoc.
- Ningún campo prohibido (domain-entities §4).
- No se guarda. Solo se emite un log técnico `applicant_summary.generated` con `case_id`.

## 5. Fail-closed hacia el caso (US-111, US-113)

**BR-U7-15 — Sin persistencia no hay recomendación (FR-SCO-08).** Si el append de la
entrada `recommendation` no se confirma (503 o timeout del registro), scoring responde
`FailClosed(registry_unavailable)` y reintenta el append solo dentro del mismo intento de
evaluación con la misma `idempotency_key` (BR-U3-06). Ninguna recomendación sale sin
`registry_entry_id`. El reintento es uno solo, solo ante 503, timeout o error de conexión
(nunca ante 4xx) y no se hace con el circuito abierto (P-U7-02) (precisado el 2026-10-03 por U7 NFR Design Q2).

**BR-U7-16 — Entrada `fail_closed`.** Por cada `FailClosed`, scoring intenta escribir la
entrada `fail_closed` (*best effort*). Si el registro no responde, la respuesta sale igual
y el caso la reintenta (BR-U0-08). case-service no duplica estas entradas; solo escribe una al escalar a `no_disponible` (BR-U8-09, precisado el 2026-10-03 por U8 FD Q4).

## 6. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 `ServingState`, `ServingConfig.normative_current`, `ReasonCode` | `normative_current` nulo ya **no** es `no_disponible`; motivo `parametro_normativo_no_vigente` | Q1 (US-207) |
| U0 catálogo de scopes | `governance:read-dictionary` para explainability-service | Q4 |
| U0 plan de tareas, Paso 7 | La prueba de `normative_current` nulo pasa a U7 | Q1 |
| U4 BR-U4-11, domain-entities §5, business-logic-model, NFR Design P-U4-05, plan de tareas §4 | Sin normativa vigente → revisión humana en U7, no fail-closed | Q1 |
| U4 BR-U4-06 y nueva BR-U4-18; domain-entities `feature_dictionary`; plan de tareas Paso 10 | Governance guarda y sirve el diccionario verificado | Q4 |
| U2 realm | Cliente `explainability-service`: scope `governance:read-dictionary` y audiencia `governance-service` | Q4 |
| Inventario | Flujo F103 (explainability → governance); `component-methods` C09 `get_feature_dictionary`; rangos F01–F103 | Q4 |
| U0 business-rules BR-U0-08 | Lo que se **entrega** siempre está en el registro; una entrada escrita y no entregada queda identificada (antes: «lo que queda en el registro es exactamente lo que se entrega») | NFR Design Q3 (P-U7-03) |
| U0 business-rules BR-U0-35 | case-service compara la decisión contra la recomendación cuyo `registry_entry_id` guardó el caso | NFR Design Q3 |
| U0 domain-entities §5.2 (`human_decision`) | Campo nuevo `recommendation_entry_id`; lo llena case-service desde el caso, no viene en `DecisionIn` | NFR Design Q3 |
| U0 domain-entities §9.1 | Tipo nuevo `ApplicantSummaryRequest` (`case_id`, `recommendation_entry_id`) | NFR Design Q3 (BR-U7-13) |
| U0 NFR Design P-U0-07 y fila RESILIENCY-10; plan de tareas Paso 10 | `deps.call(..., deadline=)` con la cabecera `x-vectra-deadline`, `deadline.py`, un cliente por dependencia con límite de conexiones; la fila de cumplimiento ya no dice que U7 y U8 diseñan el circuit breaker | NFR Design Q1, Q4 (P-U7-01, 04) |
| U3 business-rules BR-U3-14 | El expediente calcula `delivery_status` (`entregada`, `no_entregada`, `pendiente_de_decision`) para cada `recommendation` | NFR Design Q3 |
| U3 domain-entities §3 y §4.1 | `seq` y `recommendation_entry_id` en las proyecciones `explanation`, `monitoring` y `metrics`; `delivery_status` en `RegistryDossier.entries`, calculado al leer y nunca guardado | NFR Design Q3 |
| U3 plan de tareas, Paso 8 | Filtros de `GET /v1/entries` (`EntryFilter`: `case_id`, `entry_type`, `seq`, rango de `recorded_at`); dos criterios de aceptación nuevos: `no_entregada`, y un `seq` de otro caso → página vacía | NFR Design Q3 |
| `component-methods` (explainability `applicant_summary`) | Recibe `recommendation_entry_id`, que pone el BFF desde el caso | NFR Design Q3 |
| U8 (todavía sin artefactos) | **Pendiente** para su FD: guardar el `registry_entry_id` recibido y llenar `human_decision.recommendation_entry_id`; timeout hacia scoring ≥ 7 s; revisar `delivery_status` si permite reevaluar | NFR Design Q2, Q3 |
| U9, U11 (todavía sin artefactos) | **Pendiente**: contar solo las recomendaciones entregadas | NFR Design Q3 |
| U8 (todavía sin artefactos) | **Pendiente**: case-service también escribe en el registro (F16); debe adoptar el apagado ordenado de INF-U7-03 con su propio peor caso | Infrastructure Design Q2 |
