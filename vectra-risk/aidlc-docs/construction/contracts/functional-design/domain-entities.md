# Entidades de dominio — U0 `contracts`

Decisiones del plan (`contracts-functional-design-plan.md`, Q1–Q8 = A):
- Q1: solicitud completa.
- Q2: redacción de logs por allowlist.
- Q3: 6 regiones naturales y bandas de cuota/ingreso.
- Q4: el registro guarda features, no identificadores.
- Q5: diccionario de features por versión de modelo.
- Q6: errores en `problem+json`.
- Q7: una versión semántica para todo el paquete.
- Q8: montos en pesos enteros y tasas en decimal EA con 4 decimales.

Decisiones de la revisión (`contracts-functional-design-review-questions.md`, Q1–Q8 = A):
- R1: las causas se deciden con el estado de serving y el error tipificado del explicador como entradas explícitas (refinado por S1 y S3: dos fases, 10 causas).
- R2: `FailClosed` viaja como 200 con unión discriminada por `kind`.
- R3: `score` y `confidence` son `Decimal4`.
- R4: U0 define ahora todos los tipos del contrato (§9).
- R5: decimales como cadena en JSON; valores de features como `{type, value}`.
- R6: este documento es la **fuente autoritativa** de los contratos y prevalece sobre `component-methods.md`.
- R7: el registro guarda datos seudonimizados **[VERIFICAR]** con cumplimiento (§5.4).
- R8: se mantienen las 6 regiones; la muestra mínima la decide U9.

Decisiones de la segunda revisión (`contracts-functional-design-review2-questions.md`, Q1–Q4 = A):
- S1: dos fases, `check_preconditions` → `Ready` → registro → `build_outcome`.
- S2: una dependencia no invocada se pasa ausente.
- S3: causa nueva `model_output_invalid`.
- S4: `decision` admite `resuelve_revision`.

Notación: `str(max=N)` = longitud máxima · `Decimal4` = decimal con 4 decimales ·
`COP` = entero en pesos colombianos, ≥ 0. Todos los tipos se publican en OpenAPI y se
generan como Pydantic y TypeScript.

Representación JSON (R5, BR-U0-15):
- `COP` e `int`: número entero JSON. El máximo (10¹²) es menor que 2⁵³, así que no se pierde precisión en TypeScript.
- `Decimal4`: cadena con patrón `^-?\d+\.\d{4}$` (p. ej. `"0.1350"`).
- `Decimal` (sin escala fija, p. ej. valores SHAP): cadena con patrón `^-?\d+(\.\d+)?$`.
- Fechas y timestamps: cadena RFC 3339; timestamps siempre en UTC.

---

## 1. Solicitud

### 1.1 `ApplicationIn` (entrada; la persiste `case-service`)

| Grupo | Campo | Tipo | Clasificación |
|---|---|---|---|
| Identificación | `full_name` | `str(max=200)` | PII |
| | `document_type` | `CC \| CE \| PA \| PPT` | PII |
| | `document_number` | `str(max=15)` | PII |
| | `birth_date` | `date` | PII |
| | `phone` | `str(max=20)` | PII |
| | `email` | `str(max=254)` | PII |
| | `address` | `str(max=300)` | PII |
| | `department_code` | código DANE del departamento (2 dígitos) | quasi-identificador |
| | `municipality_code` | código DANE del municipio (5 dígitos) | quasi-identificador |
| Ingresos | `monthly_income` | `COP` | financiero sensible |
| | `other_income` | `COP` | financiero sensible |
| | `employment_type` | `asalariado \| independiente \| pensionado` | financiero sensible |
| | `employment_months` | `int` 0–720 | financiero sensible |
| | `monthly_obligations` | `COP` | financiero sensible |
| | `max_days_past_due_12m` | `int` 0–365 | financiero sensible |
| Crédito | `property_value` | `COP` | financiero sensible |
| | `requested_amount` | `COP` | financiero sensible |
| | `term_months` | `int` 12–360 | — |
| | `proposed_rate_ea` | `Decimal4` en (0, 1) | — |
| | `property_condition` | `nueva \| usada` | — |
| | `channel` | `str(max=40)` del catálogo de canales | — |
| | `broker_id` | `str(max=40)` opcional | — |
| Monitoreo | `sex` | `F \| M \| no_informado` | sensible (solo monitoreo) |
| | `socioeconomic_stratum` | `1..6 \| no_informado` | sensible (solo monitoreo) |
| Texto libre | `free_text` | `str(max=2000)` opcional | **no confiable**; puede contener PII |

### 1.2 `CaseRef`, `CaseSummary` y `CaseDetail`
- `CaseRef`: `case_id` (UUID), `state`.
- `CaseSummary`: `case_id`, `state`, `channel`, `created_at`, `outcome?`. **Sin score** salvo en estado `listo` o `decidido`.
- `CaseDetail`: resumen, más `recommendation?`, `credit_status?` y `decision?`.
- Estados del caso: `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`, `decidido`. Las transiciones se detallan en el Functional Design de U8.

## 2. Features y etiquetas derivadas

### 2.1 `FeatureVector`
- `features: dict[feature_id, FeatureValue]`, producido por la transformación de la versión de modelo.
- `FeatureValue` es un objeto discriminado `{type, value}` (R5), sin uniones ambiguas:
  - `{type: "decimal", value: Decimal}`;
  - `{type: "int", value: int}`;
  - `{type: "category", value: str(max=60)}`.
- Nunca contiene identificadores directos ni el texto libre (RT-1).
- Features derivadas estándar que U0 calcula y ofrece a todos:
  - `installment_cop`: cuota mensual estimada (§2 de business-rules);
  - `installment_to_income`: `Decimal4`;
  - `loan_to_value`: monto / valor de la vivienda, `Decimal4`;
  - `age_years`: edad a la fecha de evaluación.

### 2.2 `MonitoringLabels` (Q3=A)

| Campo | Valores |
|---|---|
| `sexo` | `F`, `M`, `no_informado` |
| `rango_edad` | `18-25`, `26-35`, `36-45`, `46-55`, `56-65`, `66+` |
| `region` | `andina`, `caribe`, `pacifica`, `orinoquia`, `amazonia`, `insular` |
| `estrato` | `1`–`6`, `no_informado` |
| `banda_capacidad_pago` | `lt_20`, `20_30`, `gt_30` (por `installment_to_income`) |

Solo se usan para monitoreo (FR-ING-05). **No** son features del modelo, salvo una
decisión explícita registrada en la política. **No** aparecen en los logs (Q2).

Insular y Amazonía tendrán muestras pequeñas (R8). U0 solo define la etiqueta. La regla de
muestra mínima (no calcular disparidad bajo un n mínimo y reportar «muestra insuficiente»)
se fija en el Functional Design de U9.

## 3. Recomendación y explicación

### 3.1 `FeatureContribution`
`feature_id`, `value` (valor de la feature), `contribution` (`Decimal`, valor SHAP con signo).

### 3.2 `Explanation`
| Campo | Tipo |
|---|---|
| `model_version_id` | `str` |
| `method` | `"shap"` |
| `shap_vector` | `list[FeatureContribution]`, ordenado por `abs(contribution)` descendente |
| `base_value` | `Decimal` |
| `narrative` | `str(max=4000)` |
| `narrative_generator` | `str`, p. ej. `template:v1` |
| `feature_dictionary_version` | `str` |
| `posthoc_notice` | `str` (texto i18n fijo) |
| `factuality_check` | `"passed"` (literal: no existe otro valor válido en una `Explanation` entregada) |

`base_value` y `feature_dictionary_version` amplían el tipo de `component-methods.md`
(R6: prevalece este documento).

### 3.3 `Recommendation`
Solo se construye con la fábrica `build_outcome` (business-rules §1).

| Campo | Tipo |
|---|---|
| `kind` | `"recommendation"` (discriminador, R2) |
| `case_id` | UUID |
| `score` | `Decimal4` en [0, 1] (R3, BR-U0-07) |
| `confidence` | `Decimal4` en [0, 1] (R3, BR-U0-07) |
| `outcome` | `favorable \| desfavorable \| revision_requerida` |
| `reasons` | `list[ReasonCode]` (§3.6) |
| `model_version_id` | `str` |
| `policy_version_id` | `str` |
| `explanation` | `Explanation` (obligatoria) |
| `registry_entry_id` | `str` (prueba de persistencia previa) |
| `evaluated_at` | timestamp |
| `feature_vector_hash` | `str`: SHA-256 hex del `FeatureVector` serializado en JSON canónico RFC 8785 (JCS) con las reglas de BR-U0-15; el expediente lo recalcula desde el registro |

### 3.4 `FailClosed`

| Campo | Tipo |
|---|---|
| `kind` | `"fail_closed"` (discriminador, R2) |
| `case_id` | UUID |
| `status` | `en_sincronizacion \| modelo_congelado` |
| `cause` | catálogo cerrado (abajo) |
| `retryable` | `bool` |
| `occurred_at` | timestamp |

Catálogo cerrado de `cause` (10 valores; amplía los 7 de `component-methods.md`, R6). El
orden de precedencia está en BR-U0-02:
- `model_output_invalid`
- `version_mismatch`
- `explainer_unavailable`
- `explainer_error`
- `timeout`
- `factuality_failed`
- `feature_dictionary_incomplete`
- `registry_unavailable`
- `model_frozen`
- `serving_config_unavailable`

`status = modelo_congelado` solo con `cause = model_frozen`; todas las demás causas usan
`en_sincronizacion`.

### 3.5 `RecommendResult`
Unión discriminada por `kind`: `Recommendation | FailClosed`. Es el cuerpo de una respuesta
**200** de `POST /v1/recommendations` (R2). Un fail-closed es un resultado de negocio
esperado, no un error de transporte.

### 3.6 Entradas internas de `check_preconditions` y `build_outcome` (R1, S1, S2)

Los parámetros de dependencias (`prediction`, `policy_result`, resultado del explicador,
`dictionary`, resultado del registro) son **opcionales**: ausente = no se invocó (S2).

| Tipo | Campos |
|---|---|
| `ServingState` | `activo \| congelado \| no_disponible` (de `ServingConfig.state`; `no_disponible` si no se pudo leer **o** si `ServingConfig.normative_current` es nulo, U4 FD Q4) |
| `Prediction` | `model_version_id`, `score: Decimal4`, `confidence: Decimal4` (ya cuantizados, BR-U0-07) |
| `PolicyResult` | `policy_version_id`, `outcome`, `reasons: list[ReasonCode]` |
| `ExplainerError` | `timeout \| unavailable \| error \| version_mismatch \| factuality_failed \| feature_dictionary_incomplete` |
| `RegistryAck` | `registry_entry_id`, `seq`, `recorded_at` |
| `RegistryError` | `unavailable` |
| `Ready` | `case_id`, `prediction`, `policy_result`, `explanation`, `feature_vector_hash`, `evaluated_at`. Solo lo construye `check_preconditions` y solo lo consume `build_outcome` y la escritura de la entrada `recommendation` (BR-U0-08) |

`ReasonCode` es un catálogo cerrado y versionado con la política. Valores iniciales:
`score_bajo_corte`, `score_sobre_corte`, `baja_confianza`, `vis`, `no_vis`,
`tasa_sobre_usura`.

## 4. Diccionario de features (Q5=A)

### `FeatureDictionary`
| Campo | Tipo |
|---|---|
| `dictionary_version` | `str` |
| `model_version_id` | `str` (al que pertenece) |
| `entries` | `list[FeatureDictionaryEntry]` |

### `FeatureDictionaryEntry`
| Campo | Tipo | Ejemplo |
|---|---|---|
| `feature_id` | `str` | `installment_to_income` |
| `label_es` | `str(max=80)` | "relación cuota/ingreso" |
| `unit` | `str(max=20)` opcional | "%" |
| `increases_risk_phrase_es` | `str(max=160)` | "una relación cuota/ingreso alta aumenta el riesgo" |
| `decreases_risk_phrase_es` | `str(max=160)` | "una relación cuota/ingreso baja reduce el riesgo" |
| `applicant_safe` | `bool` | si puede aparecer en el resumen al solicitante (US-110) |

Lo produce U5, lo registra U4 junto con la versión y lo consume U7.

## 5. Registro (Q4=A)

### 5.1 `RegistryEntryIn` (campos comunes)
`entry_type`, `case_id?`, `model_version_id?`, `policy_version_id?`, `actor`
(`{kind: user|service|system, id, role, acr?, auth_time?}`; `acr` y `auth_time` son
obligatorios cuando `kind = user` y la acción exige MFA, BR-U0-72), `occurred_at`,
`correlation_id`, `idempotency_key` (UUID que genera el cliente; el **mismo** en cada
reintento de la misma escritura; agregado por U3 FD Q5) y `payload` (según el tipo).

### 5.2 Payload por `entry_type`

| `entry_type` | Payload |
|---|---|
| `recommendation` | `score`, `confidence`, `outcome`, `reasons`, `feature_vector` (sin identificadores), `feature_vector_hash`, `evaluated_at`, `monitoring_labels`, `explanation` (completa, tal como se mostrará). Se construye solo desde `Ready` (BR-U0-08) |
| `fail_closed` | `cause`, `retryable`, `attempt` |
| `human_decision` | `decision` (`sigue` \| `se_aparta` \| `resuelve_revision`), `final_outcome`, `used_factors: list[feature_id]` o `["ninguno"]`, `justification` (`str(max=2000)`), `explanation_viewed_before` (`bool`) |
| `explanation_view` | `viewed_at` |
| `model_event` | `event` (`registrado`, `validacion_iniciada`, `informe_validacion`, `validacion_fallida`, `aprobado`, `rechazado`, `activado`, `inactivado`, `retirado`; los dos agregados por U4 FD Q1), `details` |
| `policy_event` | `event` (`propuesta`, `activada`, `rechazada`, `historica`), `policy_version_id`. Aprobar y activar son el mismo acto (U4 FD Q4): `activada` lleva como actor al CRO aprobador; `historica` la escribe la misma acción para la política que deja de estar activa (corregido el 2026-10-03: antes tenía `aprobada` y `activada` por separado y no tenía `historica`) |
| `data_source_event` | `event` (`propuesta`, `evaluacion_iniciada`, `aprobada`, `rechazada`), `pre_post_report_ref`. `evaluacion_iniciada` corresponde a la transición `propuesta → en_evaluacion` de U4 (agregado el 2026-10-03, porque BR-U4-17 exige evento por transición) |
| `freeze` | `freeze_id`, `context_package` (métricas agregadas, sin PII) |
| `frozen_resolution` | `action` (`reactivar` \| `descartar` \| `investigar`), `justification` |
| `genesis` | `schema_version`, `contract_version`, `checkpoint_key_fingerprint`. Solo la escribe el propio registro, una vez (`seq = 0`; U3 FD Q3) |
| `checkpoint` | `checkpoint_seq`, `checkpoint_hash`, `signature` (Ed25519), `key_fingerprint`. Solo la escribe el propio registro (U3 FD Q1) |

### 5.3 `RegistryEntry` (salida)
`RegistryEntryIn`, más `seq` (contiguo, sin huecos), `prev_hash`, `hash`, `recorded_at` y
`contract_version`; los bytes canónicos (`canonical`) se guardan tal cual (U3 FD Q2).
Los identificadores directos **nunca** están en el registro. El **BFF** los une al
expediente desde case-service solo para `cro` y `cumplimiento` (U3 FD Q7).

### 5.4 Clasificación de los datos del registro (R7)
- `feature_vector`, `monitoring_labels` y `case_id` son **datos personales seudonimizados**, no anónimos: se pueden volver a unir con `case-db`.
- Como el registro es inmutable, no admite supresión.
- **[VERIFICAR]** con cumplimiento su compatibilidad con la Ley 1581 de 2012 (supresión y retención). Decidido en el NFR Requirements de U3 (2026-10-03, Q1=A): retención de 10 años **[VERIFICAR]**, sin supresión en el registro por obligación legal de conservación **[VERIFICAR]**, eliminación de los identificadores en case-db al vencer su retención (U8) y archivo mensual firmado a WORM por 10 años.

## 6. Modelo de errores (Q6=A)

### `Problem` (`application/problem+json`, RFC 9457)
`type` (URI del catálogo), `title` (genérico, i18n), `status`, `code`, `correlation_id`.
No tiene otros campos.

Catálogo cerrado de `code`:

| `code` | Status |
|---|---|
| `malformed_request` | 400 (JSON malformado) |
| `unsupported_media_type` | 415 |
| `validation_error` | 422 |
| `unauthenticated` | 401 |
| `forbidden` | 403 |
| `mfa_required` | 403 |
| `not_found` | 404 |
| `conflict_state` | 409 |
| `payload_too_large` | 413 |
| `rate_limited` | 429 |
| `dependency_unavailable` | 503 |
| `internal_error` | 500 |

No existe un `code` `fail_closed`: el fail-closed viaja como `FailClosed` en una respuesta
200 (R2, §3.5).

En `validation_error` se permite un campo adicional `invalid_params: [{name, reason_code}]`,
**sin valores**.

## 7. Seguridad

### 7.1 `Principal`
`subject`, `kind` (`user` \| `service`), `roles: set`, `scopes: set`, `acr: str?`, `auth_time: timestamp?`, `token_expiry`. `mfa` deja de ser un campo: se deriva como `acr == "mfa"` (BR-U0-72).

### 7.2 Catálogo de scopes de servicio (fuente para el realm de U2)

| Scope | Otorgado a |
|---|---|
| `case:recommend` | case-service (llamar a scoring) |
| `scoring:explain` | scoring-service (llamar a explainability) |
| `governance:read-serving` | scoring-service |
| `governance:freeze` | bias-monitoring-service |
| `governance:validation-report` | model-validation-job |
| `governance:promotion` | promotion-tool, **con token del usuario** `ingeniero_riesgo` (`list_promotable`, `mark_active`), vía F08 |
| `bias:compare` | governance-service |
| `registry:append:case` | case-service |
| `registry:append:scoring` | scoring-service |
| `registry:append:governance` | governance-service |
| `registry:read:explanation` | explainability-service |
| `registry:read:monitoring` | bias-monitoring-service |
| `registry:read:metrics` | product-metrics |
| `intake:submit` | cliente `channel` (simulador y canales) |
| `core:read-credit` | case-service (`GET /v1/credits/{id}` de core-banking-mock, F17) |
| `core:write-credit` | **ninguna identidad**. Lo exige `POST /v1/credits/{id}/status` para que RT-5 falle con 403 aunque una NetworkPolicy estuviera mal (AUTONOMIA-03). U2 no crea ningún cliente con este scope |

Los roles de usuario (`analista`, `ingeniero_riesgo`, `cro`, `cumplimiento`) se
autorizan por endpoint según la tabla del BFF.

## 8. Log

### `LogRecord` (allowlist, Q2=A)
Solo pueden aparecer estos campos:
- `timestamp`, `level`, `service`, `correlation_id`, `span_id`, `event` (`correlation_id` es el `trace-id` W3C, BR-U0-62);
- `case_id`, `model_version_id`, `policy_version_id`, `entry_type`;
- `status`, `http_method`, `route_template` (nunca la URL con parámetros), `duration_ms`;
- `error_code`, `fail_closed_cause`, `attempt`, `principal_kind`, `principal_role`;
- `principal_subject`: el `sub` opaco del token (UUID de Keycloak), nunca el username ni el email. Permite alertar por fallos repetidos del mismo sujeto (SECURITY-14).

Cualquier otro campo se descarta antes de emitir el registro.

## 9. Tipos de las APIs (R4)

U0 fija aquí la forma y la validación de estructura. El comportamiento (transiciones,
reglas de política, autorización por objeto) lo detalla la unidad dueña.

### 9.1 Scoring y explicabilidad (dueña: U7)

| Tipo | Campos |
|---|---|
| `ScoringRequest` | `case_id`, `features: FeatureVector`, `monitoring_labels: MonitoringLabels`, `policy_inputs: PolicyInputs`, `attempt: int ≥ 1` |
| `PolicyInputs` | `property_value: COP`, `proposed_rate_ea: Decimal4`, `channel`; datos de la solicitud que la política necesita y que no son features (VIS, usura, reglas por canal) |
| `ExplainRequest` | `case_id`, `model_version_id`, `features: FeatureVector`, `prediction_score: Decimal4` |
| `ApplicantSummary` | `case_id`, `factors: list[{label_es, direction: aumenta \| reduce}]` (solo entradas con `applicant_safe = true`), `posthoc_notice`, `generated_at`. **Sin** valores SHAP, `score` ni `model_version_id` (US-110) |

### 9.2 Casos (dueña: U8)

| Tipo | Campos |
|---|---|
| `DecisionIn` | `decision: sigue \| se_aparta \| resuelve_revision` (S4, BR-U0-35), `final_outcome: favorable \| desfavorable`, `used_factors: list[feature_id]` (1..20) o exactamente `["ninguno"]`, `justification: str(max=2000)` |
| `DecisionRef` | `case_id`, `registry_entry_id`, `recorded_at` |

El usuario y su rol salen del token, nunca del cuerpo. `explanation_viewed_before` lo
calcula case-service a partir de las entradas `explanation_view`.

### 9.3 Gobierno (dueña: U4)

| Tipo | Campos |
|---|---|
| `ServingConfig` | `model_version_id`, `state: activo \| congelado`, `policy_version_id`, `feature_dictionary_version`, `effective_from`, `inference_service` (nombre del `InferenceService` de la versión servible, `isvc-<8 hex>`; agregado por U6 NFR Design Q2), `etag` (cambia si y solo si cambia el contenido), `normative_current: NormativeParams?` (el vigente a la fecha; nulo si no hay ninguno → fail-closed), `bias_monitoring_age_s: int` (U4 FD Q4, Q5, Q9) |
| `PolicyDraft` | `cutoff: Decimal4` en [0, 1], `low_confidence_threshold: Decimal4` en [0, 1], `channel_rules: list[{channel, cutoff?: Decimal4}]`, `normative: list[NormativeParams]` (vigencias sin solaparse; se pueden cargar vigencias futuras, U4 FD Q4) |
| `NormativeParams` | `vis_max_property_value: COP`, `usury_cap_ea: Decimal4`, `effective_from: date`, `effective_to: date?`, `source_ref: str(max=300)`. Los valores concretos son **[VERIFICAR]** contra la fuente oficial (FR-POL-02) |
| `PolicyVersion` | `PolicyDraft`, más `policy_version_id`, `state: propuesta \| activa \| rechazada \| historica` (aprobar = activar de inmediato; la anterior pasa a `historica`, U4 FD Q4), `proposed_by`, `approved_by?` (distinto de `proposed_by`, U4 FD Q3), `created_at` |
