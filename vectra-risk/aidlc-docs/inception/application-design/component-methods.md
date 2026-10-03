# Métodos e interfaces de componentes — Vectra Risk

Firmas de alto nivel. Los endpoints REST llevan su operación lógica en notación Python.
**Las reglas de negocio detalladas** (umbrales, fórmulas, tablas de estados completas)
**se definen en Functional Design** de cada unidad.

Todos los endpoints de la API (puerto 8080):
- exigen JWT válido (de usuario o de servicio) y un correlation ID;
- validan el payload por esquema (Pydantic, con longitudes y rangos);
- devuelven errores genéricos (SECURITY-05, -08, -15).

Los health checks y `/metrics` viven en el puerto 8081, sin token y sin rutas de negocio
(BR-U0-71).

---

## Tipos compartidos (contrato de sincronía)

> **Fuente autoritativa de los contratos (2026-10-03):** los tipos compartidos y los tipos
> de request/response de las APIs se definen **solo** en
> `aidlc-docs/construction/contracts/functional-design/domain-entities.md` (U0, BR-U0-93).
> Esta sección los nombra y no repite sus campos, para que no haya dos definiciones.

| Tipo | Rol | Definición en U0 |
|---|---|---|
| `Recommendation` | recomendación usable; incluye la `Explanation` y el `registry_entry_id` | domain-entities §3.3 |
| `Explanation` | vector SHAP, narrativa, aviso post-hoc y versión del diccionario | §3.2 |
| `FailClosed` | respuesta tipificada sin score, con 10 causas posibles | §3.4 |
| `RecommendResult` | `Recommendation \| FailClosed`, discriminado por `kind`; viaja en HTTP 200 | §3.5 |
| `Ready`, `Prediction`, `PolicyResult`, `RegistryAck` | entradas internas del invariante | §3.6 |
| `MonitoringLabels` | categorías gruesas para monitoreo, sin PII | §2.2 |
| Tipos de las APIs (`ScoringRequest`, `ExplainRequest`, `DecisionIn`, `ServingConfig`, `PolicyVersion`, ...) | requests y responses | §9 |

**Invariante del contrato (AUTONOMIA-06):** una `Recommendation` solo sale de dos
funciones puras, `check_preconditions` → append al registro → `build_outcome`, que evalúan
una tabla fija de 10 causas. Cualquier causa produce `FailClosed`. Ver BR-U0-01..08 y
PBT-U0-01.

---

## C03 `console-bff`

Única API que consume la SPA (`/api/console/**`, vía api-gateway, F03). Para cada
endpoint el BFF aplica tres controles en el servidor, en este orden (SECURITY-08):
1. **Autorización por función**: el rol del JWT tiene que estar en la columna "Roles". Si no, devuelve 403 y registra el fallo de autorización (SECURITY-14).
2. **MFA**: si la columna lo indica, se exige el claim de MFA (`acr`/`amr`) en el token. Si no está, devuelve 403 con el código `mfa_required`.
3. **Autorización por objeto**: se aplica la regla de la columna "Objeto".

Después propaga el token del usuario y el correlation ID al servicio de destino, que
**vuelve a validar** rol y objeto (defensa en profundidad). El BFF no guarda estado:
compone las respuestas de los servicios de destino.

Los dashboards de métricas y de operación **no** pasan por el BFF: se sirven desde
Grafana (F06), con login OIDC y permisos por equipo.

### Sesión

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `get_me() -> SessionInfo` | `GET /api/console/me` | todos | — | propio | ninguno (claims del JWT): roles, estado de MFA, locale |

### Casos (E1, E4, E5)

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `list_cases(filter) -> Page[CaseSummary]` | `GET /api/console/cases` | analista, cro | — | bandeja común del banco; los casos no listos se devuelven sin score ni explicación | case `list_cases` |
| `get_case(case_id) -> CaseDetail` | `GET /api/console/cases/{id}` | analista, cro | — | el caso existe; sin score si no está `listo` o `decidido` | case `get_case` |
| `create_application(app) -> CaseRef` | `POST /api/console/cases` | analista | — | — | case `create_manual_application` |
| `record_explanation_view(case_id)` | `POST /api/console/cases/{id}/explanation-views` | analista | — | el caso está `listo` o `decidido` | case `record_explanation_view` |
| `record_decision(case_id, d) -> DecisionRef` | `POST /api/console/cases/{id}/decision` | analista | — | el caso está `listo` (si no, 409); la decisión queda a nombre del llamante | case `record_decision` |
| `create_applicant_summary(case_id) -> ApplicantSummary` | `POST /api/console/cases/{id}/applicant-summary` | analista, cro | — | caso `decidido` con explicación sincronizada | explainability `applicant_summary` |
| `list_persistent_failures() -> list[CaseSummary]` | `GET /api/console/cases/failures` | cro | — | — | case `list_persistent_failures` |
| `get_dossier(case_id) -> Dossier` | `GET /api/console/cases/{id}/dossier` | cro, cumplimiento | — | el caso existe | registry `get_case_dossier` + case `get_case` (identificadores directos); el BFF compone, el registro no toca identificadores (U3 FD Q7) |
| `run_integrity_check() -> IntegrityReport` | `POST /api/console/integrity-checks` | cro | sí | — | registry `verify_chain` |

### Modelos (E2, E3)

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `list_models(filter) -> Page[ModelVersion]` | `GET /api/console/models` | ingeniero_riesgo, cro, cumplimiento | — | — | governance |
| `get_model(mv_id) -> ModelVersionDetail` | `GET /api/console/models/{id}` | ingeniero_riesgo, cro, cumplimiento | — | incluye el informe de validación | governance |
| `register_model(m) -> ModelVersion` | `POST /api/console/models` | ingeniero_riesgo | sí | — | governance `register_model` |
| `start_validation(mv_id) -> ValidationRun` | `POST /api/console/models/{id}/validations` | ingeniero_riesgo | sí | estado `registrado` | governance `start_validation` |
| `approve_model(mv_id, decision)` | `POST /api/console/models/{id}/approval` | cro | sí | estado `lista_para_aprobacion` | governance `approve_model` |
| `resolve_frozen(mv_id, action, justification)` | `POST /api/console/models/{id}/frozen-resolution` | **cumplimiento** | sí | estado `congelado` | governance `resolve_frozen` |

`mark_active` **no** se expone en el BFF. Solo lo usa `promotion-tool` después de un
sync manual aprobado (flujo S3).

### Políticas (E2)

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `list_policies() -> list[PolicyVersion]` | `GET /api/console/policies` | analista, cro, cumplimiento | — | — (lectura, para transparencia) | governance |
| `propose_policy(p) -> PolicyVersion` | `POST /api/console/policies` | cro | sí | — | governance `propose_policy` |
| `approve_policy(pv_id)` | `POST /api/console/policies/{id}/approval` | cro | sí | estado `propuesta` | governance `approve_policy` |

### Fuentes de datos (E3)

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `list_data_sources() -> list[DataSource]` | `GET /api/console/data-sources` | ingeniero_riesgo, cumplimiento, cro | — | — | governance |
| `propose_data_source(s) -> DataSource` | `POST /api/console/data-sources` | ingeniero_riesgo | sí | — | governance `propose_data_source` |
| `decide_data_source(ds_id, decision)` | `POST /api/console/data-sources/{id}/decision` | cumplimiento | sí | estado `en_evaluacion` con informe antes/después | governance `decide_data_source` |

### Vigilancia de sesgo (E3)

| Operación | Endpoint | Roles | MFA | Objeto | Destino |
|---|---|---|---|---|---|
| `get_disparity(filter) -> DisparityView` | `GET /api/console/disparity` | cumplimiento, cro | — | — | bias `get_dashboard` |
| `list_freezes() -> list[FreezeSummary]` | `GET /api/console/freezes` | cumplimiento, cro | — | — | bias |
| `get_freeze(freeze_id) -> FreezeContext` | `GET /api/console/freezes/{id}` | cumplimiento | — | el congelamiento existe | bias `get_context_package` |

**Cobertura:** cada acción de usuario de las historias de E1–E5 tiene un endpoint en
esta tabla, salvo la visualización de métricas, que se hace en Grafana (F06). La matriz
rol × endpoint de US-602 se genera desde esta tabla.

## C04 `case-service`

| Operación | Endpoint | Entrada → Salida | Llamado por |
|---|---|---|---|
| `submit_application(app: ApplicationIn) -> CaseRef` | `POST /v1/intake/applications` | solicitud validada → `case_id`, estado | gateway (simulador) |
| `create_manual_application(app: ApplicationIn, user) -> CaseRef` | `POST /v1/cases` | ídem, canal "manual" | BFF (analista) |
| `list_cases(filter: CaseFilter, user) -> Page[CaseSummary]` | `GET /v1/cases` | filtros → bandeja (sin score en casos no listos) | BFF |
| `get_case(case_id, user) -> CaseDetail` | `GET /v1/cases/{id}` | → detalle (+ estado de crédito en lectura) | BFF |
| `record_explanation_view(case_id, user) -> None` | `POST /v1/cases/{id}/explanation-views` | → evento al registro | BFF |
| `record_decision(case_id, d: DecisionIn, user) -> DecisionRef` | `POST /v1/cases/{id}/decision` | sigue / se aparta / resuelve_revision + factores + texto → registro (BR-U0-35) | BFF (analista) |
| `list_persistent_failures(user) -> list[CaseSummary]` | `GET /v1/cases/failures` | → casos `no_disponible` | BFF (CRO) |
| `evaluate(case_id) -> RecommendResult` | interno (worker) | invoca a scoring; reprograma el reintento | cola de trabajos |

## C05 `scoring-service`

| Operación | Endpoint | Entrada → Salida | Llamado por |
|---|---|---|---|
| `recommend(req: ScoringRequest) -> RecommendResult` | `POST /v1/recommendations` | features + `case_id` + etiquetas de monitoreo + `policy_inputs` → recomendación o fail-closed (siempre HTTP 200, BR-U0-06) | case-service |
| `apply_policy(score: Decimal4, confidence: Decimal4, inputs: PolicyInputs, policy: PolicyVersion) -> PolicyResult` | módulo interno puro | → outcome + `ReasonCode` | interno |

## C06 `explainability-service`

| Operación | Endpoint | Entrada → Salida | Llamado por |
|---|---|---|---|
| `explain(req: ExplainRequest) -> Explanation` | `POST /v1/explanations` | features + `model_version_id` → explicación; error tipificado si la versión no coincide o la factualidad falla | scoring-service |
| `applicant_summary(case_id, user) -> ApplicantSummary` | `POST /v1/applicant-summaries` | → resumen apto para el solicitante (sin SHAP ni versión) | BFF (CRO, analista) |

Interfaces internas reemplazables (FR-EXP-06):
```python
class NarrativeGenerator(Protocol):
    id: str
    def generate(self, shap_vector: list[FeatureContribution], locale: str) -> str: ...

class FactualityValidator(Protocol):
    def validate(self, narrative: str, shap_vector: list[FeatureContribution]) -> bool: ...
```
En el MVP solo existe `TemplateNarrativeGenerator`. Un futuro `InClusterLLMNarrativeGenerator` recibiría **solo** el vector SHAP estructurado.

## C07 `model-serving` (KServe)

| Operación | Endpoint |
|---|---|
| `predict(features) -> {score, confidence, model_version_id}` | `POST /v1/models/{name}:predict` |
| `explain(features) -> {shap_vector, model_version_id}` | `POST /v1/models/{name}:explain` |

## C09 `governance-service`

| Operación | Endpoint | Llamado por (rol) |
|---|---|---|
| `register_model(m: ModelRegistration) -> ModelVersion` | `POST /v1/models` | BFF (ingeniero_riesgo) |
| `start_validation(mv_id) -> ValidationRun` | `POST /v1/models/{id}/validations` | BFF (ingeniero_riesgo) |
| `submit_validation_report(mv_id, r: ValidationReport)` | `PUT /v1/models/{id}/validation-report` | model-validation-job (identidad de servicio) |
| `approve_model(mv_id, decision, user)` | `POST /v1/models/{id}/approval` | BFF (cro, con MFA) |
| `list_promotable() -> list[ModelVersion]` | `GET /v1/models?state=aprobado` | promotion-tool |
| `mark_active(mv_id, evidence)` | `POST /v1/models/{id}/activation` | promotion-tool tras sync aprobado (ingeniero_riesgo) |
| `freeze_model(mv_id, ctx: FreezeContext)` | `POST /v1/models/{id}/freeze` | **solo** identidad `bias-monitoring` |
| `resolve_frozen(mv_id, action: Literal["reactivar","descartar","investigar"], justification, user)` | `POST /v1/models/{id}/frozen-resolution` | BFF (**solo** cumplimiento, con MFA) |
| `get_active_serving_config() -> ServingConfig` | `GET /v1/serving-config` | scoring-service (lectura: versión activa, estado, política vigente) |
| `propose_policy(p: PolicyDraft, user) -> PolicyVersion` | `POST /v1/policies` | BFF (cro) |
| `approve_policy(pv_id, user)` | `POST /v1/policies/{id}/approval` | BFF (cro, con MFA) |
| `propose_data_source(s: DataSourceProposal, user)` | `POST /v1/data-sources` | BFF (ingeniero_riesgo) |
| `decide_data_source(ds_id, decision, user)` | `POST /v1/data-sources/{id}/decision` | BFF (cumplimiento) |

## C10 `model-validation-job`
```python
def run_validation(model_version_id: ModelVersionId, dataset_ref: str) -> ValidationReport
    # AUC-ROC, disparidad inicial (librería de C11), prueba de sincronía predictor↔explainer
```

## C11 `bias-monitoring-service`

| Operación | Endpoint / disparador |
|---|---|
| `compute_disparity(window) -> DisparityReport` | CronJob periódico |
| `evaluate_freeze(report) -> FreezeDecision` | tras cada cálculo (umbral en Functional Design) |
| `build_context_package(mv_id, report) -> FreezeContext` | al congelar |
| `compare_source(ds_id) -> PrePostReport` | a pedido desde governance (fuente nueva) |
| `get_dashboard(filter, user) -> DisparityView` | `GET /v1/disparity` (BFF: cumplimiento, cro) |
| `get_context_package(freeze_id, user)` | `GET /v1/freezes/{id}` (BFF: cumplimiento) |

Librería compartida (también la usa C10):
```python
def disparity_by_band(records: Iterable[LabeledOutcome], group: str) -> DisparityResult
```

## C12 `decision-registry-service`

| Operación | Endpoint | Llamado por |
|---|---|---|
| `append(entry: RegistryEntryIn) -> RegistryAck` | `POST /v1/entries` | scoring, case, governance (identidades de servicio). bias **no** escribe: el congelamiento lo registra governance (F24) |
| `query(filter: EntryFilter, principal) -> Page[RegistryEntry]` | `GET /v1/entries` | BFF (filtrado por rol), explainability (F23), bias, product-metrics |
| `get_case_dossier(case_id, principal) -> Dossier` | `GET /v1/dossiers/{case_id}` | BFF (cro, cumplimiento) |
| `verify_chain(from_seq=None) -> IntegrityReport` | `POST /v1/integrity-checks` + CLI/Job | BFF (cro), CronJob |

Tipos de entrada (`entry_type`): `recommendation`, `fail_closed`, `human_decision`,
`explanation_view`, `model_event`, `policy_event`, `data_source_event`, `freeze`,
`frozen_resolution`.

## C13 `product-metrics`
```python
def compute_business_metrics(period) -> BusinessMetrics  # north_star, explanation_view_rate,
                                                         # sustained_rate, origination_time
# expone /metrics (Prometheus)
```

## C14 `channel-simulator`
```python
def run(volume: int, mode: Literal["normal", "adversarial"], scenario: str | None) -> RunReport
```

## C15 `core-banking-mock`
| Operación | Endpoint |
|---|---|
| `get_credit_status(credit_id)` | `GET /v1/credits/{id}`; scope `core:read-credit` (solo case-service) |
| `update_credit_status(...)` | `POST /v1/credits/{id}/status`: existe **solo** para demostrar el bloqueo RT-5; exige `core:write-credit`, que no se otorga a ninguna identidad |

## C18 `promotion-tool` (CLI)
```python
def create_promotion_pr(model_version_id: ModelVersionId) -> PullRequestUrl
    # un solo commit: InferenceService (predictor + explainer) + values; adjunta helm template y kubectl diff
```
