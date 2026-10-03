# Entidades de dominio — U4 `governance`

Decisiones del plan (`governance-functional-design-plan.md`, Q1–Q9 = A). Los tipos de la API
(`ServingConfig`, `PolicyDraft`, `NormativeParams`, `PolicyVersion`) son de U0 §9.3,
actualizados por este diseño. Aquí se definen las entidades de `governance-db` y sus estados.

---

## 1. Versión de modelo

### 1.1 `ModelVersion` (tabla `model_versions`)

| Campo | Tipo | Notas |
|---|---|---|
| `model_version_id` | `str` | Inmutable, p. ej. `mv-2026-09-01-abc123` |
| `state` | enum (§1.2) | — |
| `artifact_uri` | `str` | Ruta en el model-store (MinIO, bucket `model-store`) |
| `artifact_format` | `onnx \| xgboost_json \| xgboost_ubj \| lightgbm_txt` | Q7 |
| `artifact_sha256` | `str` (64 hex) | Lo declara el ingeniero y governance lo verifica (F47) |
| `explainer_uri`, `explainer_sha256` | `str` | El explicador asociado (FR-SCO-10) |
| `inference_service` | `str` | `isvc-<primeros 8 hex del model_version_id>` (U6, azul/verde) |
| `manifest_uri`, `manifest_sha256` | `str` | `manifest.json` del paquete (U5): lista cada archivo (predictor, explicador, fondo, envolvente de dominio, diccionario, especificación de features) con su SHA-256 (agregado por U5 FD) |
| `feature_dictionary_version` | `str` | Diccionario de features de esa versión (U0 §4) |
| `feature_dictionary` | JSON | Copia del `feature_dictionary.json` del paquete, guardada al registrar tras verificar su SHA-256; la sirve `GET /v1/models/{id}/feature-dictionary` (agregado por U7 FD Q4) |
| `feature_spec` | JSON | Copia del `feature_spec.json` del paquete, con sus tablas de búsqueda, guardada al registrar tras verificar su SHA-256; la sirve `GET /v1/models/{id}/feature-spec` (BR-U4-19; agregado por U8 FD Q1) |
| `data_sources` | `list[ds_id]` | Fuentes aprobadas que usa (Q8) |
| `registered_by` | `sub` | `ingeniero_riesgo` |
| `approved_by?` | `sub` | `cro`, distinto de `registered_by` (Q3) |
| `investigation` | `bool` | Marca de `investigar` en `congelado` (Q1) |
| `archived_uri?`, `archived_at?` | `str`, timestamp | Copia WORM de 10 años en el S3 del banco, para toda versión que llegó a `activo` (agregado por INF-U4-02) |
| `created_at`, `updated_at` | timestamp | — |

### 1.2 Estados

`registrado`, `en_validacion`, `validacion_fallida`, `lista_para_aprobacion`, `aprobado`,
`rechazado`, `activo`, `inactivo`, `congelado`, `retirado`. Las transiciones están en
business-rules §1.

### 1.3 `ModelTransition` (tabla `model_transitions`, historial)
`transition_id` (UUID; también es la `idempotency_key` del evento del registro), `model_version_id`,
`from_state`, `to_state`, `actor` (`{kind, sub, role, acr?, auth_time?}`), `justification?`,
`status` (`pendiente_registro` \| `confirmada` \| `abandonada`), `registry_entry_id?`,
`created_at`, `confirmed_at?`.

## 2. Validación

### 2.1 `ValidationRun` (tabla `validation_runs`)
`run_id`, `model_version_id`, `job_name` (Job en `vectra-staging`, K01), `state` (`lanzado` \|
`informe_recibido` \| `fallido` \| `timeout`), `started_at`, `deadline_at` (2 h), `finished_at?`.

### 2.2 `ValidationReport`

| Campo | Contenido |
|---|---|
| `auc_roc` | `Decimal4`, con `auc_target` (0,85 **[INTERNO]**) y `auc_meets_target: bool` |
| `initial_disparity` | Por grupo y banda (`MonitoringLabels`), con el umbral de U9 y la indicación de si lo supera |
| `sync_check` | `passed: bool`, `predictor_version`, `explainer_version`, `samples_checked`, `failure_reason?` |
| `dataset_ref` | Dataset de validación del model-store |
| `disclaimer` | Texto fijo: el monitoreo mide disparidad en este dataset y **no** certifica la ausencia de discriminación (FR-BIA-08) |

Solo `sync_check.passed = false` bloquea (Q6).

## 3. Política

### 3.1 `PolicyVersion` (tabla `policies`)
Los campos de U0 §9.3: `cutoff`, `low_confidence_threshold`, `channel_rules`, `normative:
list[NormativeParams]`, `state` (`propuesta` \| `activa` \| `rechazada` \| `historica`),
`proposed_by`, `approved_by?` y `created_at`, más `activated_at?`, `superseded_at?` y
`rejection_justification?`.

Como máximo **una** política `activa`.

### 3.2 Selección del parámetro normativo
`normative_at(policy, date)` devuelve el único `NormativeParams` con `effective_from ≤ date`
y (`effective_to` nulo o `date < effective_to`), o nulo si no hay ninguno. Como las
vigencias no se solapan (BR-U0-33), hay a lo sumo uno.

## 4. Fuente de datos (Q8)

### `DataSource` (tabla `data_sources`)
`ds_id`, `name`, `description`, `provides_features: list[feature_id]`, `owner`, `proposed_by`
(`ingeniero_riesgo`), `state` (`propuesta` → `en_evaluacion` → `aprobada` \| `rechazada`),
`pre_post_report_ref?`, `decided_by?` (`cumplimiento`), `decision_justification?`, fechas.

## 5. `serving-config` (tabla `serving_config`, una fila)

| Campo | Origen |
|---|---|
| `model_version_id`, `state` | La versión en `activo` o `congelado` |
| `policy_version_id` | La política `activa` |
| `feature_dictionary_version` | De la versión de modelo |
| `inference_service` | `ModelVersion.inference_service` de la versión en `activo` o `congelado` (`isvc-<8 hex>`); es lo que scoring y explainability usan para saber a qué `InferenceService` llamar (azul/verde, P-U6-02; agregado aquí el 2026-10-03, faltaba en esta tabla aunque ya estaba en el contrato de U0) |
| `normative_current` | `normative_at(policy, hoy)`; nulo → la política de scoring da `revision_requerida` con `parametro_normativo_no_vigente` (precisado el 2026-10-03 por U7 FD Q1: alinea con US-207) |
| `bias_monitoring_age_s` | Edad del último cálculo de disparidad que informó U9 |
| `effective_from` | Momento de la última transición confirmada |
| `etag` | SHA-256 del contenido canónico (JCS) de todos los campos anteriores salvo `bias_monitoring_age_s` (incluido `inference_service`); cambia si y solo si cambia el contenido, así que un cambio de `InferenceService` en `mark_active` dispara la convergencia de P-U4-01 y el límite de ≤ 6 s de BR-U4-14 |

`GET /v1/serving-config` admite `If-None-Match` (304 si no cambió).

## 6. Parámetros

| Parámetro | Valor | Regla |
|---|---|---|
| Plazo de la validación | 2 h | BR-U4-05 |
| Caché de `serving-config` en scoring | ≤ 5 s (efecto del congelamiento ≤ 6 s con la convergencia entre réplicas) | BR-U4-14, NFR-U4-06 |
| Aviso de vencimiento normativo | 15 días (SEV2) y el día del vencimiento (SEV1) | BR-U4-11 |
| Desfase de promoción tolerado | 10 min | BR-U4-08 |
| Monitoreo de sesgo detenido | SEV2 a W, SEV1 a 2W (W lo define U9) | BR-U4-16 |
