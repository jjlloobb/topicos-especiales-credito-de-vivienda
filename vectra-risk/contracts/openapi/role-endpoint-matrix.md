# Matriz rol x endpoint (US-602). Generado: no editar.

| Servicio | Metodo | Ruta | analista | ingeniero_riesgo | cro | cumplimiento | MFA | Scopes |
|---|---|---|---|---|---|---|---|---|
| bias-monitoring-service | GET | `/v1/disparity` |  |  | x | x |  |  |
| bias-monitoring-service | GET | `/v1/freezes` |  |  | x | x |  |  |
| bias-monitoring-service | GET | `/v1/freezes/{id}` |  |  |  | x |  |  |
| bias-monitoring-service | POST | `/v1/source-comparisons` |  |  |  |  |  | bias:compare |
| case-service | GET | `/v1/cases` | x |  | x |  |  |  |
| case-service | POST | `/v1/cases` | x |  |  |  |  |  |
| case-service | GET | `/v1/cases/failures` |  |  | x |  |  |  |
| case-service | GET | `/v1/cases/{id}` | x |  | x |  |  |  |
| case-service | POST | `/v1/cases/{id}/decision` | x |  |  |  |  |  |
| case-service | POST | `/v1/cases/{id}/explanation-views` | x |  |  |  |  |  |
| case-service | GET | `/v1/cases/{id}/identifiers` |  |  | x | x |  |  |
| case-service | POST | `/v1/cases/{id}/retry` |  |  | x |  |  |  |
| case-service | POST | `/v1/intake/applications` |  |  |  |  |  | intake:submit |
| console-bff | GET | `/api/console/cases` | x |  | x |  |  |  |
| console-bff | POST | `/api/console/cases` | x |  |  |  |  |  |
| console-bff | GET | `/api/console/cases/failures` |  |  | x |  |  |  |
| console-bff | GET | `/api/console/cases/{id}` | x |  | x |  |  |  |
| console-bff | POST | `/api/console/cases/{id}/applicant-summary` | x |  | x |  |  |  |
| console-bff | POST | `/api/console/cases/{id}/decision` | x |  |  |  |  |  |
| console-bff | GET | `/api/console/cases/{id}/dossier` |  |  | x | x |  |  |
| console-bff | POST | `/api/console/cases/{id}/explanation-views` | x |  |  |  |  |  |
| console-bff | POST | `/api/console/cases/{id}/retry` |  |  | x |  |  |  |
| console-bff | POST | `/api/console/client-errors` | x | x | x | x |  |  |
| console-bff | GET | `/api/console/data-sources` |  | x | x | x |  |  |
| console-bff | POST | `/api/console/data-sources` |  | x |  |  | si |  |
| console-bff | POST | `/api/console/data-sources/{id}/comparisons` |  | x |  |  | si |  |
| console-bff | POST | `/api/console/data-sources/{id}/decision` |  |  |  | x | si |  |
| console-bff | GET | `/api/console/disparity` |  |  | x | x |  |  |
| console-bff | GET | `/api/console/freezes` |  |  | x | x |  |  |
| console-bff | GET | `/api/console/freezes/{id}` |  |  |  | x |  |  |
| console-bff | POST | `/api/console/integrity-checks` |  |  | x |  | si |  |
| console-bff | GET | `/api/console/integrity-checks/{id}` |  |  | x |  |  |  |
| console-bff | GET | `/api/console/me` | x | x | x | x |  |  |
| console-bff | GET | `/api/console/models` |  | x | x | x |  |  |
| console-bff | POST | `/api/console/models` |  | x |  |  | si |  |
| console-bff | GET | `/api/console/models/{id}` |  | x | x | x |  |  |
| console-bff | POST | `/api/console/models/{id}/approval` |  |  | x |  | si |  |
| console-bff | POST | `/api/console/models/{id}/frozen-resolution` |  |  |  | x | si |  |
| console-bff | POST | `/api/console/models/{id}/retirement` |  |  | x |  | si |  |
| console-bff | POST | `/api/console/models/{id}/validations` |  | x |  |  | si |  |
| console-bff | GET | `/api/console/policies` | x |  | x | x |  |  |
| console-bff | POST | `/api/console/policies` |  |  | x |  | si |  |
| console-bff | POST | `/api/console/policies/{id}/approval` |  |  | x |  | si |  |
| core-banking-mock | GET | `/v1/credits/{id}` |  |  |  |  |  | core:read-credit |
| core-banking-mock | POST | `/v1/credits/{id}/status` |  |  |  |  |  | core:write-credit |
| decision-registry-service | GET | `/v1/dossiers/{case_id}` |  |  | x | x |  |  |
| decision-registry-service | GET | `/v1/entries` |  |  |  |  |  | registry:read:explanation, registry:read:metrics, registry:read:monitoring |
| decision-registry-service | POST | `/v1/entries` |  |  |  |  |  | registry:append:case, registry:append:governance, registry:append:scoring |
| decision-registry-service | POST | `/v1/integrity-checks` |  |  | x |  | si |  |
| decision-registry-service | GET | `/v1/integrity-checks/{id}` |  |  | x |  |  |  |
| decision-registry-service | POST | `/v1/monitoring/daily:query` |  |  |  |  |  | registry:read:monitoring |
| decision-registry-service | GET | `/v1/monitoring/freezes` |  |  |  |  |  | registry:read:monitoring |
| explainability-service | POST | `/v1/applicant-summaries` | x |  | x |  |  |  |
| explainability-service | POST | `/v1/explanations` |  |  |  |  |  | scoring:explain |
| governance-service | GET | `/v1/data-sources` |  | x | x | x |  |  |
| governance-service | POST | `/v1/data-sources` |  | x |  |  | si |  |
| governance-service | POST | `/v1/data-sources/{id}/comparisons` |  | x |  |  | si |  |
| governance-service | POST | `/v1/data-sources/{id}/decision` |  |  |  | x | si |  |
| governance-service | GET | `/v1/models` |  | x | x | x |  |  |
| governance-service | POST | `/v1/models` |  | x |  |  | si |  |
| governance-service | GET | `/v1/models/{id}` |  | x | x | x |  |  |
| governance-service | POST | `/v1/models/{id}/activation` |  | x |  |  | si | governance:promotion |
| governance-service | POST | `/v1/models/{id}/approval` |  |  | x |  | si |  |
| governance-service | GET | `/v1/models/{id}/feature-dictionary` |  |  |  |  |  | governance:read-dictionary |
| governance-service | GET | `/v1/models/{id}/feature-spec` |  |  |  |  |  | governance:read-feature-spec |
| governance-service | POST | `/v1/models/{id}/freeze` |  |  |  |  |  | governance:freeze |
| governance-service | POST | `/v1/models/{id}/frozen-resolution` |  |  |  | x | si |  |
| governance-service | POST | `/v1/models/{id}/retirement` |  |  | x |  | si |  |
| governance-service | PUT | `/v1/models/{id}/validation-report` |  |  |  |  |  | governance:validation-report |
| governance-service | POST | `/v1/models/{id}/validations` |  | x |  |  | si |  |
| governance-service | GET | `/v1/policies` | x |  | x | x |  |  |
| governance-service | POST | `/v1/policies` |  |  | x |  | si |  |
| governance-service | POST | `/v1/policies/{id}/approval` |  |  | x |  | si |  |
| governance-service | GET | `/v1/serving-config` |  |  |  |  |  | governance:read-serving |
| governance-service | PUT | `/v1/validation-runs/{run_id}/source-counts` |  |  |  |  |  | governance:validation-report |
| scoring-service | POST | `/v1/recommendations` |  |  |  |  |  | case:recommend |
