# API de `case-management` (U8)

Dos APIs: `case-service` (9 rutas, puerto 8080) y `core-banking-mock` (2 rutas, puerto 8080; solo kind y staging). El puerto 8081 de cada proceso sirve `/healthz`, `/readyz` y `/metrics` (`vectra_common.ops_server`). El contrato es el de U0 (`contracts/openapi/case-service.yaml` y `contracts/openapi/core-banking-mock.yaml`). El OpenAPI exportado de lo que sirve cada app está en [case-service](openapi/case-service.yaml) y [core-banking-mock](openapi/core-banking-mock.yaml); `uv run python case-management/tools/check_openapi.py` falla si difiere del de la app o del contrato (BR-U8-20).

Los errores son `Problem` de U0 (`application/problem+json`): `code`, `reason` opcional y `correlation_id`. Ningún cuerpo trae PII.

## `case-service`

| Método y ruta | Quién | Éxito | Otros códigos |
|---|---|---|---|
| `POST /v1/intake/applications` | scope `intake:submit` (el simulador de canales) | 200 `CaseRef` | 401, 403, 422 `validation_error` (`Idempotency-Key` o `X-Test-Scenario`), 409 `conflict_state` |
| `POST /v1/cases` | rol `analista` (alta manual) | 200 `CaseRef` | 401, 403, 422, 409 |
| `GET /v1/cases` | roles `analista`, `cro` | 200 página de `CaseSummary` | 401, 403, 422 (filtros) |
| `GET /v1/cases/failures` | rol `cro` | 200 lista de `PersistentFailure` | 401, 403 |
| `GET /v1/cases/{id}` | roles `analista`, `cro` | 200 `CaseDetail` | 401, 403, 404 |
| `GET /v1/cases/{id}/identifiers` | roles `cro`, `cumplimiento` | 200 `CaseIdentifiers` | 401, 403, 404 |
| `POST /v1/cases/{id}/explanation-views` | rol `analista` | 204 | 401, 403, 404, 409 |
| `POST /v1/cases/{id}/decision` | rol `analista` | 200 `DecisionRef` | 401, 403, 404, 409 `decision_already_recorded`, 422, 503 `dependency_unavailable` |
| `POST /v1/cases/{id}/retry` | rol `cro` | 200 `CaseRef` | 401, 403, 404, 409 |

- **`Idempotency-Key`** (ingesta y alta manual): obligatorio, con el formato que fija U0; la misma llave con el mismo cuerpo devuelve el mismo `CaseRef`, y con otro cuerpo, 409. Sin llave o con una inválida: 422 `validation_error` con `invalid_params`.
- **`X-Test-Scenario`**: solo se acepta con `allowTestScenarios = true` (kind y staging) y solo del cliente del simulador de canales; en producción, 422.
- **`reason` que sale a la red**: `decision_already_recorded` (409), cuando el caso ya tiene una decisión viva. Las razones internas de la validación de una decisión (`used_factors_not_in_shap_vector`, `decision_incoherent_with_outcome`) **no** salen: la respuesta lleva solo el `code` (422 `validation_error` o 409 `conflict_state`). `model_frozen_after_recommendation` no es un `reason`: es un campo de `CaseSummary` y `CaseDetail` y un filtro de `GET /v1/cases`; vale `true` mientras la versión del modelo de la recomendación esté congelada y el caso siga en `listo`.
- **`credit_status`** (en `CaseDetail`, valores de `CreditStatus` de U0): `en_estudio`, `aprobado`, `desembolsado`, `rechazado`, `cancelado`, `sin_credito`, `no_disponible` y `no_integrado`. Con `core.enabled = false` (producción) nunca se llama al core y vale `no_integrado`; con el core habilitado y caído o lento (0,5 s), `no_disponible`. `get_case` nunca falla por el core.
- **Degradación**: con `case-db` caída, de solo lectura o con el pool agotado (2 s), las rutas que escriben responden 503 `dependency_unavailable`; `GET /v1/cases` y `GET /v1/cases/{id}` siguen respondiendo con la base en solo lectura, y `/readyz` solo mira `case-db`.

## `core-banking-mock`

| Método y ruta | Quién | Respuesta |
|---|---|---|
| `GET /v1/credits/{id}` | scope `core:read-credit` (solo `case-service`, por la `AuthorizationPolicy` de U1) | 200 `CreditStatusView` o 404 |
| `POST /v1/credits/{id}/status` | nadie: el scope `core:write-credit` no lo tiene ningún cliente | siempre 403; `vectra_core_write_attempts_total` sube en 1 |

El segundo existe solo para la demostración de RT-5. En el clúster, Linkerd lo deniega antes (ruta `core-mock-catch-all` sin `AuthorizationPolicy`, 403 con `l5d-proxy-error`); ver [el runbook de `CoreWriteAttempt`](../observability/runbooks/core-write-attempt.md).

## Variables de entorno de cada proceso

Todas obligatorias, sin valores por omisión (si falta una, el proceso no arranca). Las pone el chart (`case-management/chart`); ninguna constante de `vectra_case/config.py` es variable de entorno (INF-U8-07).

| Proceso | Variables |
|---|---|
| `case-service` (`python -m vectra_case.app`) | `CASE_DB_DSN`, `CASE_GOVERNANCE_URL`, `CASE_REGISTRY_URL`, `CASE_CORE_ENABLED`, `CASE_CORE_URL` (solo con el core habilitado), `CASE_ALLOW_TEST_SCENARIOS`, `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH`, `VECTRA_CA_BUNDLE`; `PGUSER` y `PGPASSWORD` (Secret `pg-role-case-app`) |
| `case-worker` (`python -m vectra_case.worker`) | `CASE_DB_DSN`, `CASE_GOVERNANCE_URL`, `CASE_SCORING_URL`, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH`, `VECTRA_CA_BUNDLE`; `PGUSER` y `PGPASSWORD` (Secret `pg-role-case-worker`) |
| Migración (`alembic -c /app/alembic.ini upgrade head`) | `CASE_DATABASE_URL`, `RETENTION_DECIDED_YEARS`, `RETENTION_UNDECIDED_YEARS`, `RETENTION_INTAKE_KEYS_DAYS`; `PGUSER` y `PGPASSWORD` (Secret `pg-role-case-migrator`) |
| `core-banking-mock` (`python -m core_banking_mock.app`) | `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE` |

El DSN va sin credenciales y con `sslmode=verify-full` y la CA interna (`sslrootcert`).

## Qué quedó diferido (demo)

La retención: el CronJob `case-retention` y su CLI (Paso 16, T5), las métricas y alertas de retención y `docs/retention.md` (con la firma de cumplimiento). También las otras ocho alertas de U8 y sus runbooks (T2), la carga con k6 y `mutmut` (T3) y la firma, el SBOM y el escaneo de las imágenes (T1). La lista completa, con su destino, está en `aidlc-docs/construction/case-management/evidence/cierre-demo.md`.
