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
- `CaseFilter`: `state?: list[estado]` (por defecto, todos menos `vencido`; `vencido` solo con el filtro explícito, BR-U8-13), `channel?`, `created_from?`, `created_to?`, `model_frozen_after_recommendation?: bool`, `page`, `page_size` (≤ 100) (precisado el 2026-10-06, revisión del FD de U8; `model_frozen_after_recommendation` por la revisión del FD de U10, 2026-10-10, A4). No tiene búsqueda por texto: ningún campo lleva datos del solicitante, para que el filtro pueda ir en la URL (U10 BR-U10-10).
- `PersistentFailure`: `case_id`, `channel`, `created_at`, `attempts`, `last_cause`, `since` (entrada a `no_disponible`); lo devuelve `list_persistent_failures` (precisado el 2026-10-06, revisión del FD de U8).
- `CaseSummary`: `case_id`, `state`, `channel`, `created_at`, `outcome?`, `applicant_display` (nombre completo + los últimos 4 dígitos del documento; vacío si el caso está anonimizado) (precisado el 2026-10-06, revisión R1 del FD de U8). **Sin score** salvo en estado `listo` o `decidido`.
- `CaseDetail`: resumen, más `application` (la `ApplicationIn` **sin** el grupo de identificación de §1.1 y **sin** `sex` ni `socioeconomic_stratum`, que son solo de monitoreo), `identifiers?` (el grupo de identificación de §1.1: nombre, documento, fecha de nacimiento, contacto, dirección y municipio; **ausente** si el caso está anonimizado; precisado el 2026-10-06, revisión del FD de U8; precisado el 2026-10-06, revisión R1 del FD de U8), `recommendation?`, `credit_status?` (`CreditStatus`: `en_estudio \| aprobado \| desembolsado \| rechazado \| cancelado \| sin_credito \| no_disponible \| no_integrado`; `no_disponible` = core caído o lento, `no_integrado` = `core.enabled = false`; precisado el 2026-10-10 por U10 FD, Q3) y `decision?`, `model_frozen_after_recommendation`, `anonymized`, `attempts` y `last_cause` (precisado el 2026-10-06 por U8 FD Q2 y Q7); detalle en U8 domain-entities §4.
- Estados del caso: `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`, `decidido` y `vencido` (terminal: la retención venció sin decisión; agregado el 2026-10-06 por U8 FD). Las transiciones se detallan en el Functional Design de U8.

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
orden de precedencia está en BR-U0-02. Cada causa lleva una `category` (revisión del FD de U11, 2026-10-10; U11 genera desde
aquí su regla de fail-closed por desincronía, BR-U11-06):

| Causa | `category` |
|---|---|
| `model_output_invalid` | `calidad` |
| `version_mismatch` | `desincronia` |
| `explainer_unavailable` | `dependencia` |
| `explainer_error` | `calidad` |
| `timeout` | `dependencia` |
| `factuality_failed` | `calidad` |
| `feature_dictionary_incomplete` | `desincronia` |
| `registry_unavailable` | `dependencia` |
| `model_frozen` | `congelamiento` |
| `serving_config_unavailable` | `dependencia` |

`vectra_contracts.catalog` expone `FailClosedCause.category` y el conjunto
`FAIL_CLOSED_CAUSES_BY_CATEGORY`; una causa nueva sin categoría no compila.

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
| `ServingState` | `activo \| congelado \| no_disponible` (de `ServingConfig.state`; `no_disponible` solo si no se pudo leer. Un `normative_current` nulo **no** es `no_disponible`: la política produce `revision_requerida` con el motivo `parametro_normativo_no_vigente` (precisado el 2026-10-03 por U7 FD Q1: alinea con US-207)) |
| `Prediction` | `model_version_id`, `score: Decimal4`, `confidence: Decimal4` (ya cuantizados, BR-U0-07) |
| `PolicyResult` | `policy_version_id`, `outcome`, `reasons: list[ReasonCode]` |
| `ExplainerError` | `timeout \| unavailable \| error \| version_mismatch \| factuality_failed \| feature_dictionary_incomplete` |
| `RegistryAck` | `registry_entry_id`, `seq`, `recorded_at` |
| `RegistryError` | `unavailable` |
| `Ready` | `case_id`, `prediction`, `policy_result`, `explanation`, `feature_vector_hash`, `evaluated_at`. Solo lo construye `check_preconditions` y solo lo consume `build_outcome` y la escritura de la entrada `recommendation` (BR-U0-08) |

`ReasonCode` es un catálogo cerrado y versionado con la política. Valores iniciales:
`score_bajo_corte`, `score_sobre_corte`, `baja_confianza`, `vis`, `no_vis`,
`tasa_sobre_usura`, `parametro_normativo_no_vigente` (este último agregado por U7 FD Q1).

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
obligatorios **siempre** que `kind = user`, exija o no MFA la acción (BR-U0-72; antes solo con MFA; segunda revisión del Infrastructure Design de U10, 2026-10-10): así la decisión del analista, que no pide step-up (U10 BR-U10-09b), deja su nivel de autenticación como evidencia; prohibidos con `kind = service` o `system`), `occurred_at` (momento del **intento** de escritura; el del hecho de negocio va en el payload cuando la escritura puede llegar tarde, BR-U3-05; precisado el 2026-10-06),
`correlation_id`, `idempotency_key` (UUID que genera el cliente; el **mismo** en cada
reintento de la misma escritura; agregado por U3 FD Q5) y `payload` (según el tipo).

### 5.2 Payload por `entry_type`

| `entry_type` | Payload |
|---|---|
| `recommendation` | `score`, `confidence`, `outcome`, `reasons`, `feature_vector` (sin identificadores), `feature_vector_hash`, `evaluated_at`, `monitoring_labels`, `explanation` (completa, tal como se mostrará), `received_at` (el `created_at` del caso, de la `ScoringRequest`), `channel` (de `policy_inputs`) y `attempt` (los tres agregados por el FD de U11, 2026-10-10, Q3 y Q8, para el tiempo de originación y los cortes de U11), y `first_evaluation` (de la `ScoringRequest`; revisión del FD de U11, 2026-10-10). Se construye solo desde `Ready` (BR-U0-08) |
| `fail_closed` | `cause?` y `local_cause?`, **exactamente uno**: `cause` (catálogo de U0) en las entradas de scoring y en un escalamiento cuyo último intento terminó en `FailClosed`; `local_cause` (`serving_config_unavailable` \| `scoring_unreachable` \| `scoring_rejected`) en un escalamiento cuyo último intento no terminó con un `RecommendResult`. `retryable` (según BR-U0-04 con `cause`; con `local_cause`, `false` solo para `scoring_rejected`), `attempt`, `escalated_at?` (su presencia marca la entrada de escalamiento, BR-U8-09). `local_cause` y `escalated_at` **solo los escribe case-service** (`registry:append:case`); una entrada de scoring nunca los lleva (U3 BR-U3-03). Validación: BR-U0-38 (precisado el 2026-10-06, revisión del FD de U8) |
| `human_decision` | `decision` (`sigue` \| `se_aparta` \| `resuelve_revision`), `final_outcome`, `used_factors: list[feature_id]` o `["ninguno"]`, `justification` (`str(max=2000)`), `explanation_viewed_before` (`bool`), `decided_at` (agregado el 2026-10-06), `recommendation_entry_id` (`registry_entry_id` de la recomendación entregada al caso; lo llena case-service desde el caso, no viene en `DecisionIn`) (precisado el 2026-10-03 por U7 NFR Design Q3) |
| `explanation_view` | `viewed_at`, `recommendation_entry_id` (la recomendación consultada; lo llena case-service desde el caso, BR-U8-19) (precisado el 2026-10-06, revisión del FD de U8) |
| `model_event` | `event` (`registrado`, `validacion_iniciada`, `informe_validacion`, `validacion_fallida`, `aprobado`, `rechazado`, `activado`, `inactivado`, `retirado`, `transicion_descartada`; los dos primeros agregados por U4 FD Q1 y el último precisado el 2026-10-06, revisión del FD de U8: compensa una transición descartada por un `freeze`, BR-U4-17), `details` |
| `policy_event` | `event` (`propuesta`, `activada`, `rechazada`, `historica`), `policy_version_id`. Aprobar y activar son el mismo acto (U4 FD Q4): `activada` lleva como actor al CRO aprobador; `historica` la escribe la misma acción para la política que deja de estar activa (corregido el 2026-10-03: antes tenía `aprobada` y `activada` por separado y no tenía `historica`) |
| `data_source_event` | `event` (`propuesta`, `evaluacion_iniciada`, `aprobada`, `rechazada`), `pre_post_report?` (el `PrePostReport` de §9.4 en `aprobada` y `rechazada`, ≤ 48 KiB con la regla de recorte de U9 BR-U9-17; antes `pre_post_report_ref`, que no apuntaba a nada; segunda revisión del FD de U9, 2026-10-08). `evaluacion_iniciada` corresponde a la transición `propuesta → en_evaluacion` de U4 (agregado el 2026-10-03, porque BR-U4-17 exige evento por transición) |
| `freeze` | `freeze_id`, `frozen_at` (cuándo se aplicó el congelamiento, que es inmediato aunque el evento se escriba después, BR-U4-15; agregado el 2026-10-06), `context_package` (métricas agregadas, sin PII): el tipo `FreezeContext` de §9.4 (semántica en U9 domain-entities §3.1) más `data_sources: list[ds_id \| DataSource]` e `initial_disparity` (formato de §9.4 `AttributeResult` por atributo), que agrega governance (precisado el 2026-10-08 por U9 FD). **Tamaño** (BR-U0-93: la forma vive aquí; tercera revisión del FD de U9, 2026-10-10): la entrada canónica ≤ 64 KiB (BR-U3-07); `FreezeContext` ≤ 48 KiB; si la entrada supera 60 KiB, `initial_disparity` lleva solo sus agregadas; si aún supera 64 KiB, `data_sources` lleva solo ids |
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
`type` (URI del catálogo), `title` (genérico, i18n), `status`, `code`, `correlation_id` y
`reason?`. No tiene otros campos. `reason` precisa un `conflict_state` o un
`unprocessable_explanation` con un catálogo cerrado, sin valores ni datos del caso (precisado el 2026-10-06, revisión del FD de U8):

| `reason` (con `conflict_state` o `unprocessable_explanation`, según la fila) | Uso |
|---|---|
| `decision_already_recorded` (con `conflict_state`) | U8 BR-U8-18: había una decisión abandonada que el registro sí había escrito |
| `transition_pending` (con `conflict_state`) | U4 BR-U4-17: la entidad ya tiene una transición pendiente |
| `version_mismatch` (con `conflict_state`) | U7: el explicador devolvió otra versión |
| `feature_dictionary_incomplete` (con `unprocessable_explanation`) | U7: el diccionario no cubre un factor |
| `factuality_failed` (con `unprocessable_explanation`) | U7: la narrativa no pasó la validación |
| `no_active_version` (con `conflict_state`) | U4 BR-U4-13: no hay versión `activo` para comparar una fuente (agregado el 2026-10-10 por U10 FD, Q7) |
| `active_version_frozen` (con `conflict_state`) | U4 BR-U4-13: la versión servible está `congelado` (agregado el 2026-10-10 por U10 FD, Q7) |

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
| `unprocessable_explanation` | 422 (solo entre explainability y scoring; siempre con `reason`, U7) (precisado el 2026-10-06, revisión del FD de U8) |
| `deadline_exceeded` | 504 (`x-vectra-deadline` ya vencido al llegar, NFR-U0-23 (b); antes se nombraba el 504 sin un `code`; revisión del Infrastructure Design de U10, 2026-10-10) |

No existe un `code` `fail_closed`: el fail-closed viaja como `FailClosed` en una respuesta
200 (R2, §3.5).

En `validation_error` se permite un campo adicional `invalid_params: [{name, reason_code}]`,
**sin valores**.

## 7. Seguridad

### 7.1 `Principal`
`subject`, `kind` (`user` \| `service`), `roles: set`, `scopes: set`, `acr: str?`, `auth_time: timestamp?`, `token_expiry`. `mfa` deja de ser un campo: se deriva como `acr == "mfa"` (BR-U0-72).

### 7.1b `RouteContract` (forma; patrón P-U0-12)
`service`, `method`, `path`, `request_model`, `response_model`, `scopes`, `roles`, `mfa`,
`mfa_max_age` (900 s), `port` (8080), `read_only: bool` (por omisión `false`; `true` solo en un
`POST` de consulta sin efectos con scopes de lectura, BR-U0-71) (revisión del NFR Requirements de U9, 2026-10-10) y
`max_body_bytes` (por omisión 32 KiB; revisión del Infrastructure Design de U10, 2026-10-10). El BodyGuard del pipeline (P-U0-01, paso 4) usa
el de la ruta. Rutas con un valor mayor: `POST /v1/entries` del registro, 80 KiB (el `canonical`
puede llegar a 64 KiB y el registro responde su propio 413 por BR-U3-07); `POST /v1/models/{id}/freeze`
de governance, 64 KiB (lleva el paquete de contexto de ≤ 48 KiB, U9 BR-U9-15). El registro de
contratos rechaza al arrancar un valor > 128 KiB y lo publica en la matriz de rutas.

### 7.2 Catálogo de scopes de servicio (fuente para el realm de U2)

| Scope | Otorgado a |
|---|---|
| `case:recommend` | case-worker (llamar a scoring; antes case-service, cambiado el 2026-10-08 por U8 INF-U8-01) |
| `scoring:explain` | scoring-service (llamar a explainability) |
| `governance:read-serving` | scoring-service, case-service (barrido de BR-U8-10/14), case-worker (agregados por U8 FD Q1 e INF-U8-01) |
| `governance:freeze` | `bias-monitoring-job` (el CronJob de U9; el servicio HTTP `bias-monitoring-service` no lo tiene; revisión del FD de U9, 2026-10-08) |
| `governance:validation-report` | model-validation-job |
| `governance:promotion` | promotion-tool, **con token del usuario** `ingeniero_riesgo` (`list_promotable`, `mark_active`), vía F08 |
| `bias:compare` | governance-service |
| `governance:read-dictionary` | explainability-service (leer el diccionario de features de una versión; agregado por U7 FD Q4) |
| `governance:read-feature-spec` | case-worker (leer el `feature_spec` de una versión para `derive`; agregado por U8 FD Q1; pasó de case-service a case-worker el 2026-10-08, INF-U8-01) |
| `registry:append:case` | case-service |
| `registry:append:scoring` | scoring-service |
| `registry:append:governance` | governance-service |
| `registry:read:explanation` | explainability-service |
| `registry:read:monitoring` | `bias-monitoring-service` y `bias-monitoring-job` (revisión del FD de U9, 2026-10-08) |
| `registry:read:metrics` | product-metrics |
| `intake:submit` | cliente `channel` (canales del banco) y, solo en kind y staging, `channel-simulator` (U2 BR-U2-11; revisión del Infrastructure Design de U10, 2026-10-10) |
| `core:read-credit` | case-service (`GET /v1/credits/{id}` de core-banking-mock, F17), **solo** en kind y staging: el realm de producción no lo tiene (`core.enabled = false`, U8 INF-U8-02; revisión del Infrastructure Design de U10, 2026-10-10) |
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
- `app_version`: la versión SemVer de la SPA en `console.client_error` (NFR Requirements de U10, 2026-10-10, Q12);
- `principal_subject`: el `sub` opaco del token (UUID de Keycloak), nunca el username ni el email. Permite alertar por fallos repetidos del mismo sujeto (SECURITY-14).

Cualquier otro campo se descarta antes de emitir el registro.

### 8.1 Catálogo de eventos (`event`, BR-U0-51; segunda revisión del NFR Requirements de U9, 2026-10-10)
El campo `event` toma valores de un `Enum` de `vectra_contracts.log_events`. Cada unidad
agrega los suyos en su FD y aquí se listan; un evento fuera del catálogo no compila.

| Evento | Unidad | Campos además de los comunes |
|---|---|---|
| `authz.denied` | U0 (BR-U0-73) | `principal_subject?`, `route_template`, `error_code` |
| `recommendation.fail_closed` | U7 | `case_id`, `fail_closed_cause`, `attempt` |
| `applicant_summary.generated` | U7 (BR-U7-13) | `case_id` |
| `case.viewed`, `case.retry_requested` | U8 (BR-U8-11, 13b) | `case_id`, `principal_subject`, `principal_role` |
| `evaluation.result_discarded` | U8 (BR-U8-08) | `case_id`, `attempt` |
| `disparity.viewed`, `freeze_context.viewed` | U9 (BR-U9-18, 19; NFR-U9-32) | `principal_subject`, `principal_role`, `model_version_id` |
| `console.client_error` | U10 (NFR-U10-34) | `error_code` (catálogo cerrado de errores del navegador), `route_template` (la ruta de la SPA, sin parámetros), `app_version`, `principal_subject`, `principal_role` (NFR Requirements de U10, 2026-10-10, Q12) |

Unidades sin eventos propios (revisión del FD de U10, 2026-10-10, B5): U2 no emite `LogRecord` (sus registros son el
access log de Envoy y los `KeycloakEvent` de U2 domain-entities §5). U3, U4 y U6 solo emiten `authz.denied` y el log de petición común (`event` vacío, con
`route_template`, `status` y `duration_ms`). Si una unidad agrega un evento, lo registra en
esta tabla en su FD.

## 9. Tipos de las APIs (R4)

U0 fija aquí la forma y la validación de estructura. El comportamiento (transiciones,
reglas de política, autorización por objeto) lo detalla la unidad dueña.

### 9.1 Scoring y explicabilidad (dueña: U7)

| Tipo | Campos |
|---|---|
| `ScoringRequest` | `case_id`, `features: FeatureVector`, `monitoring_labels: MonitoringLabels`, `policy_inputs: PolicyInputs`, `attempt: int ≥ 1`, `model_version_id` (la versión cuyo `feature_spec` armó el vector; si difiere de `serving-config`, `version_mismatch`, BR-U0-02) (precisado el 2026-10-06 por U8 FD Q1); `received_at` (el `created_at` del caso en case-service; lo copia scoring al payload de `recommendation`; FD de U11, 2026-10-10); `first_evaluation: bool` (`true` solo si el caso nunca pasó por `en_sincronizacion`, `no_disponible` ni `modelo_congelado` y `attempt = 1`; lo calcula U8; revisión del FD de U11, 2026-10-10) |
| `PolicyInputs` | `property_value: COP`, `proposed_rate_ea: Decimal4`, `channel`; datos de la solicitud que la política necesita y que no son features (VIS, usura, reglas por canal) |
| `ExplainRequest` | `case_id`, `model_version_id`, `features: FeatureVector`, `prediction_score: Decimal4` |
| `ApplicantSummaryRequest` | `case_id`, `recommendation_entry_id` (lo pone el BFF desde el caso; BR-U7-13) (precisado el 2026-10-03 por U7 NFR Design Q3) |
| `ApplicantSummary` | `case_id`, `factors: list[{label_es, direction: aumenta \| reduce}]` (solo entradas con `applicant_safe = true`), `posthoc_notice`, `generated_at`. **Sin** valores SHAP, `score` ni `model_version_id` (US-110) |

### 9.2 Casos (dueña: U8)

| Tipo | Campos |
|---|---|
| `DecisionIn` | `decision: sigue \| se_aparta \| resuelve_revision` (S4, BR-U0-35), `final_outcome: favorable \| desfavorable`, `used_factors: list[feature_id]` (1..20) o exactamente `["ninguno"]`, `justification: str(max=2000)` |
| `DecisionRef` | `case_id`, `registry_entry_id`, `recorded_at` |
| `CaseIdentifiers` | `case_id`, `identifiers?` (el grupo de identificación de §1.1), `anonymized: bool`; `anonymized = true` ⇒ sin `identifiers` (revisión del Infrastructure Design de U10, 2026-10-10) |

El usuario y su rol salen del token, nunca del cuerpo. `explanation_viewed_before` lo
calcula case-service a partir de las entradas `explanation_view`.

### 9.3 Gobierno (dueña: U4)

| Tipo | Campos |
|---|---|
| `ServingConfig` | `model_version_id`, `state: activo \| congelado`, `policy_version_id`, `feature_dictionary_version`, `effective_from`, `inference_service` (nombre del `InferenceService` de la versión servible, `isvc-<8 hex>`; agregado por U6 NFR Design Q2), `etag` (cambia si y solo si cambia el contenido), `normative_current: NormativeParams?` (el vigente a la fecha; nulo si no hay ninguno → la política da `revision_requerida` con `parametro_normativo_no_vigente`, precisado el 2026-10-03 por U7 FD Q1: alinea con US-207) (U4 FD Q4, Q5, Q9). Sin `bias_monitoring_age_s`: bias no puede informarla (X04) y `MonitoreoSesgoDetenido` sale de una métrica de U9 (precisado el 2026-10-08 por U9 FD) |
| `PolicyDraft` | `cutoff: Decimal4` en [0, 1], `low_confidence_threshold: Decimal4` en [0, 1], `channel_rules: list[{channel, cutoff?: Decimal4}]`, `normative: list[NormativeParams]` (vigencias sin solaparse; se pueden cargar vigencias futuras, U4 FD Q4) |
| `NormativeParams` | `vis_max_property_value: COP`, `usury_cap_ea: Decimal4`, `effective_from: date`, `effective_to: date?`, `source_ref: str(max=300)`. Los valores concretos son **[VERIFICAR]** contra la fuente oficial (FR-POL-02) |
| `PolicyVersion` | `PolicyDraft`, más `policy_version_id`, `state: propuesta \| activa \| rechazada \| historica` (aprobar = activar de inmediato; la anterior pasa a `historica`, U4 FD Q4), `proposed_by`, `approved_by?` (distinto de `proposed_by`, U4 FD Q3), `created_at` |

### 9.4 Monitoreo de sesgo (dueña: U9; agregada en la revisión del FD de U9, 2026-10-08)

La semántica de cada campo está en U9 domain-entities; aquí vive el tipo (BR-U0-93).

| Tipo | Campos |
|---|---|
| `MonitoringMarginalCount` | `population: modelo \| humana`, `model_version_id`, `range_id`, `attribute: sexo \| rango_edad \| region \| estrato`, `group` (valor del catálogo de §2.2), `band: lt_20 \| 20_30 \| gt_30`, `result: outcome \| final_outcome` (el `outcome` de la recomendación en `modelo`; el `final_outcome` de la decisión en `humana`), `decision: sigue \| se_aparta \| resuelve_revision \| null`, `count: int ≥ 0` |
| `MonitoringRangeRequest` | `range_id`, `model_version_id?`, `population`, `from_day: date`, `to_day: date`; hasta 12 por solicitud (segunda revisión del FD de U9, 2026-10-08) |
| `MonitoringQuery` | `ranges: list[MonitoringRangeRequest]` (1 a 12), `include_versions: bool` y `unattributable_range?: {from_day, to_day}`; es el cuerpo de `POST /v1/monitoring/daily:query` (quinta revisión del FD de U9; `unattributable_range` y POST en la sexta revisión del FD de U9, 2026-10-10) |
| `MonitoringWindow` | `versions: list[{model_version_id, population, first_day, last_day}]`, `counts: list[MonitoringMarginalCount]` (sumados por rango), `totals: list[{range_id, total_entries, invalid_entries}]`, `unattributable_invalid: int` (un **solo** valor por solicitud, sobre `unattributable_range`: decisiones de `humana` cuya recomendación no existe o no es una `recommendation`, sin versión; 0 si no se pidió el rango; sexta revisión del FD de U9, 2026-10-10), `invalid_seqs: list[int]` (≤ 100), `watermark_seq: int`, `lag_seconds: int` |
| `FreezeRecord` | `freeze_id`, `model_version_id`, `frozen_at`, `context_package: FreezeContext` (+ `data_sources`, `initial_disparity`), `resolution?: {action, recorded_at}` |
| `CountTable` | `attribute`, `cells: list[{group, band, favorable: int ≥ 0, total: int ≥ favorable}]` |
| `CellResult`, `BandResult`, `AttributeResult`, `DisparityResult` | Como U9 domain-entities §2.2–§2.5; las tasas y diferencias son `Decimal4`; una celda insuficiente no lleva `rate`; `AttributeResult` lleva `population_difference_partial: bool` (precisado el 2026-10-10 por U9 NFR Requirements) |
| `FreezeContext` | `model_version_id`, `computed_at`, `threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s` (los cinco de U9 BR-U9-13; revisión del FD de U10, 2026-10-10, A7), `library_version`, `window_start`, `before: DisparityResult \| "sin_datos"`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `truncated: bool`; JCS ≤ 48 KiB |
| `CompareSourceRequest` | `source_id`, `pre: list[CountTable]`, `post: list[CountTable]` (los cuatro atributos en cada una, sin repetir) |
| `PrePostReport` | `source_id`, `pre: DisparityResult`, `post: DisparityResult`, `delta`, `threshold_pp`, `n_min`, `truncated: bool`, `disclaimer`; JCS ≤ 48 KiB (tercera revisión del FD de U9, 2026-10-10) |
| `DisparityView` | `model_version_id`, `window`, `computed_at`, `model: DisparityResult`, `human: DisparityResult`, `threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s` (los cinco de U9 BR-U9-13; revisión del FD de U10, 2026-10-10, A7), `invalid_entries`, `disclaimer` |
| `FreezeSummary` | `freeze_id`, `model_version_id`, `frozen_at`, `trigger_attribute`, `model_aggregate`, `resolution?` |

**Validación de estructura de §9.4** (cuarta revisión del FD de U9, 2026-10-10). U0 valida, con `model_validator` y pruebas de
ejemplo en el Paso 3 de su plan: `MonitoringQuery.ranges` de 1 a 12 (13 → error);
`CountTable`: `0 ≤ favorable ≤ total`; `MonitoringRangeRequest` y `unattributable_range`: `from_day ≤ to_day`; `CellResult` con `status = muestra_insuficiente` no lleva `rate` (precisado el 2026-10-10 por U9 NFR Design); `unattributable_invalid ≥ 0` (séptima revisión del FD de U9, 2026-10-10); `CompareSourceRequest`: exactamente los cuatro
atributos, sin repetir. La **escalera de tamaño** (48 KiB de `FreezeContext` y `PrePostReport`;
60 y 64 KiB del evento `freeze`) no es validación de estructura: la aplican U9 (BR-U9-15, 17)
y U4 (BR-U4-15), y la prueban sus planes.


### 9.5 Consola (dueña: U10; agregada en la revisión del FD de U10, 2026-10-10, B1)

| Tipo | Campos |
|---|---|
| `SessionInfo` | `role: analista \| ingeniero_riesgo \| cro \| cumplimiento`, `mfa: bool` (`acr = mfa`), `auth_time`, `locale: es-CO`. Sale solo de los claims del token |
| `ConsoleDossier` | `dossier: RegistryDossier` (§9.6), `identifiers?` (el grupo de identificación de §1.1), `identifiers_unavailable: bool`, `anonymized: bool`. Lo compone el BFF (U10 BR-U10-03) |
| `ClientErrorReport` | `error_code: render_error \| chunk_load_failed \| unhandled_rejection \| api_contract_mismatch \| stepup_failed \| csp_violation`, `route_template: str(max=200)`, `app_version` (SemVer), `correlation_id?`. Sin mensajes, trazas, URL completa ni datos de formularios; `extra="forbid"` (U10 NFR-U10-34; NFR Requirements de U10, 2026-10-10, Q12) |

### 9.6 Registro (dueña: U3; agregada en la revisión del FD de U10, 2026-10-10, B1)

La semántica está en U3 domain-entities §4; aquí vive el tipo (BR-U0-93).

| Tipo | Campos |
|---|---|
| `RegistryDossier` | `case_id`, `entries: list[DossierEntry]` (en orden de `seq`), `integrity: IntegrityStatus`, `last_full_verification: LastFullVerification \| null` |
| `DossierEntry` | `seq`, `entry_type`, `canonical` (base64), los campos decodificados del `RegistryEntry` (§5.3), y en una `recommendation`, `delivery_status: entregada \| no_entregada \| pendiente_de_decision` (calculado al leer, U3 BR-U3-14) (revisión del Infrastructure Design de U10, 2026-10-10) |
| `LastFullVerification` | `check_id`, `finished_at`, `result: integra \| inconsistente` (la `full` `terminada` más reciente, U3 BR-U3-13b) (revisión del Infrastructure Design de U10, 2026-10-10) |
| `IntegrityCheckRequest` | `mode: full \| range`, `from_seq?`, `to_seq?` (obligatorios en `range` y prohibidos en `full`) (revisión del Infrastructure Design de U10, 2026-10-10) |
| `IntegrityCheckRef` | `check_id`, `mode: full \| range`, `requested_at`, `already_active: bool` (`true` si ya había una activa y se devuelve esa; NFR Design de U10, Q3; precisado en la revisión del Infrastructure Design de U10, 2026-10-10) |
| `IntegrityCheckStatus` | `check_id`, `mode`, `status: pendiente \| en_curso \| terminada \| fallida`, `progress: {checked, total}`, `report?: IntegrityReport`, `reason?: interrumpida \| error_de_ejecucion \| plazo_vencido`, `requested_at`, `started_at?`, `finished_at?` (NFR Design de U10, Q3; precisado en la revisión del Infrastructure Design de U10, 2026-10-10) |
| `IntegrityReport` | `mode: incremental \| nightly \| full \| range`, `from_seq`, `to_seq`, `entries_checked`, `checkpoints_checked`, `result: integra \| inconsistente \| error`, `first_inconsistent_seq?`, `reason?: hash \| link \| checkpoint_signature \| checkpoint_mismatch \| seq_gap \| column_mismatch`, `started_at`, `finished_at` (antes solo en U3 domain-entities §5; revisión del Infrastructure Design de U10, 2026-10-10) |
| `IntegrityStatus` | `status: verified \| not_verified`, `from_checkpoint_seq: int`, `to_checkpoint_seq: int \| "head"`, `entries_checked`, `first_inconsistent_seq?`, `reason?: hash \| link \| checkpoint_signature \| checkpoint_mismatch \| seq_gap \| column_mismatch` |

**Validación de estructura de §9.5 y §9.6** (revisión del Infrastructure Design de U10, 2026-10-10), con `model_validator` y pruebas de ejemplo en el Paso 3 del plan:
- `IntegrityCheckStatus`: `terminada` ⇔ `report` presente con `result ∈ {integra, inconsistente}`; `fallida` ⇔ `reason` presente; `pendiente` y `en_curso` sin `report` ni `reason`; `progress.checked ≤ progress.total`;
- `IntegrityCheckRequest`: `range` ⇔ `from_seq` y `to_seq` presentes, con `from_seq ≤ to_seq`;
- `IntegrityReport`: `inconsistente` ⇔ `first_inconsistent_seq` y `reason` presentes;
- `IntegrityStatus`: `not_verified` ⇔ `reason` presente (y `first_inconsistent_seq` presente salvo cuando el motivo es la falta de una verificación);
- `ConsoleDossier`: `anonymized = true` ⇒ sin `identifiers`; `identifiers_unavailable = true` ⇒ sin `identifiers`;
- `ClientErrorReport`: campos extra → error.
