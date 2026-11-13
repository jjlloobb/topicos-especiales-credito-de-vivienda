# Capa de API del BFF de `console` (U10, Pasos 5 a 9)

Resumen de `console/bff/src/console_bff/{routes,clients,compose,client_errors,metrics,app}.py`, escrito en U10-T02.
La lógica pura (`config`, `object_rules`, `errors`) está en `bff-logic.md`. Sin base de datos (Paso 9: N/A, `console/bff/migrations/` no existe).

## 1. Endpoints y destinos

Los 30 `RouteContract` son de U0 (`REGISTRY["console-bff"]`): `routes.py` no los copia. Un endpoint del BFF, una llamada al
destino (BR-U10-03), salvo las composiciones. La ruta de destino es la misma bajo `/v1`. «Clave» es la de `config.OPERATION_TIMEOUT_SECONDS`.

| BFF (bajo `/api/console`) | Destino | Clave de timeout |
|---|---|---|
| `GET /me`, `POST /client-errors` | ninguno | — |
| `GET /cases`, `GET /cases/failures`, `GET /cases/{id}` | case | `case.list_cases`, `case.list_persistent_failures`, `case.get_case` |
| `POST /cases` (reenvía `Idempotency-Key`), `POST /cases/{id}/explanation-views`, `…/decision`, `…/retry` | case | `case.create_manual_application`, `case.record_explanation_view`, `case.record_decision`, `case.retry_case` |
| `POST /cases/{id}/applicant-summary` | explainability `POST /v1/applicant-summaries` | `explainability.applicant_summary` |
| `GET /cases/{id}/dossier` | registry `GET /v1/dossiers/{case_id}` y case `GET /v1/cases/{id}/identifiers` | `registry.get_case_dossier` y `case.get_case_identifiers` (P-1) |
| `POST /integrity-checks`, `GET /integrity-checks/{id}` | registry | `registry.run_integrity_check`, `registry.get_integrity_check` |
| `GET /models`, `GET /models/{id}`, `GET /policies`, `GET /data-sources` | governance | `governance.read` |
| Los 10 `POST` de modelos, políticas y fuentes | governance | `governance.transition` |
| `GET /disparity` | governance `GET /v1/models?state=activo,congelado` y bias `GET /v1/disparity` | `governance.read` y `bias.get_dashboard` |
| `GET /freezes`, `GET /freezes/{id}` | bias | `bias.list_freezes`, `bias.get_context_package` |

- **Token.** El BFF reenvía el `Authorization` del usuario tal cual; los clientes no llevan `token_source` (con él, `deps.call`
  reintenta ante un 401). También viajan `traceparent` (el `correlation_id`) e `Idempotency-Key` (solo si llega; nunca se inventa).
- **Plazo.** `x-vectra-deadline` = el reloj de la app al entrar + 9 s; si la solicitud ya trae uno menor, rige el menor.
- **Solicitud.** La query validada por U0 y el cuerpo validado se reenvían serializados desde el modelo, no desde los bytes de entrada.
  Un `{id}` de ruta se codifica como un solo segmento; `.` y `..` son 404 sin llamar al destino.
- **Respuesta 2xx.** Se valida contra el `response_model` de la ruta y sale con el mismo estado que el destino (202 en
  `integrity-checks` con `respond(model, 202)`; 204 donde no hay cuerpo). Un 2xx que no valida, un 2xx no declarado o una
  redirección → 500 `internal_error`. `CaseDetail` se lee con `read_wire` (U00-T03).
- **Respuesta de error.** Siempre por `errors.translate_error` (`Problem` sin `detail` ni trazas); ningún handler arma un `Problem` a mano.

## 2. Los tres controles y la lectura previa de cada regla (BR-U10-01; P-U10-01)

Rol y MFA los aplica el middleware de U0; la regla de objeto corre dentro del handler, **antes** de reenviar la acción: el BFF
lee el objeto con el token del usuario, aplica la función pura de `OBJECT_RULES` y, si rechaza, responde sin llamar a la escritura
(`CONFLICT` → 409 `conflict_state`, `FORBIDDEN` → 403 `forbidden`). El destino vuelve a validar (la carrera la resuelve él).
Antes de `create_app`, `routes.verify_object_rules()` exige que las claves de `OBJECT_RULES` sean **exactamente** los `operation_id`
de las 30 rutas (`ContractViolation` si falta o sobra una; `None` declarado vale).

| Regla | Lectura previa | Datos que usa |
|---|---|---|
| `record_explanation_view`, `record_decision`, `retry_case`, `create_applicant_summary` | case `GET /v1/cases/{id}` | `state`, `anonymized`, `decision.final_outcome`, `recommendation_entry_id` |
| `start_validation`, `approve_model`, `resolve_frozen`, `retire_model` | governance `GET /v1/models/{id}` | `state` |
| `approve_policy` | governance `GET /v1/policies` | la política con ese `policy_version_id` y el cuerpo |
| `decide_data_source` | governance `GET /v1/data-sources` | `state` y `pre_post_report is not None` |
| `start_source_comparison` | `GET /v1/data-sources`, `GET /v1/models/{candidate_version_id}` y `GET /v1/models?state=activo` | estado de la fuente, `source_candidate_for` de la candidata y si existe una `activo` |

Un objeto que no aparece en la lista → 404 `not_found`; un error de la lectura previa se traduce como cualquier otro. El peor caso es
`start_source_comparison`: 3 × 1,5 s + 4 s = 8,5 s < 9 s. `create_applicant_summary` envía a U7 `ApplicantSummaryRequest(case_id,
recommendation_entry_id)` con el valor del detalle; si el detalle no lo trae, 409 `conflict_state` sin llamar a U7.

## 3. Composiciones (BR-U10-03; P-U10-02, 05)

- `get_dossier`: registry y case en paralelo con `asyncio.TaskGroup`. Registro sin respuesta (timeout, conexión, 5xx o circuito abierto)
  → 503 y se cancela la llamada a case; 403/404 del registro → ese error. Case sin respuesta → `identifiers = None`,
  `identifiers_unavailable = true`, `anonymized = false`. 403/404 de case → ese error, nunca `identifiers_unavailable`. Case con
  `anonymized = true` → sin identificadores. Un `{id}` que no es UUID → 404 sin llamadas.
- `get_disparity` (P-6 (a)): con `version` en el filtro no se consulta governance y bias recibe esa versión; sin ella, governance
  (`state=activo,congelado`) y **después** bias con la servible; ninguna → bias sin versión; varias → la `activo` (si no hay, la más
  reciente); governance caído sin `version` → 503. Sin caché: dos consultas son dos llamadas a governance y dos a bias.
- `run_integrity_check`: 202 con `IntegrityCheckRef` (`already_active = false`) o 200 con la activa (`already_active = true`).
  `get_integrity_check`: de paso.
- `get_me` (P-8 (a)): solo de los claims. Varios roles → el primero alfabético; sin `auth_time` → 403 `forbidden`; `mfa = (acr == "mfa")`.

## 4. Resiliencia (P-U10-03, 04; NFR-U10-30..33)

Cinco `DependencyClient` (`case`, `governance`, `registry`, `explainability`, `bias`; la etiqueta `dependency` de `vectra_circuit_state` y
de `ConsoleDependencyCircuitOpen`), cada uno con `max_connections = config.CONNECTIONS_PER_REPLICA[destino]` y breaker
`BreakerConfig(window_size=20, failure_ratio=0.5, window_seconds=30, open_for=10)` (constantes `BREAKER_*` de `config.py`).
Fallo = timeout, conexión o 5xx; un 4xx no cuenta. Sin reintentos.

**P-2 (a): un timeout es 503.** `Calls.send` convierte todo `DependencyTimeout` de un destino en `DependencyUnavailable`
(503 `dependency_unavailable`): así lo dicen P-U10-03 y BR-U10-03 y así no cuenta contra `ConsoleBffErrorBudget*`. El 504
`deadline_exceeded` queda solo para la solicitud que **entra** con el plazo vencido (lo lanza U0 antes del handler).

## 5. Variables de entorno (INF-U10-01)

| Variable | Obligatoria | Uso |
|---|---|---|
| `VECTRA_CASE_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_REGISTRY_URL`, `VECTRA_EXPLAINABILITY_URL`, `VECTRA_BIAS_URL` | sí | URL de cada destino (las fija el `ConfigMap` del chart, Paso 18) |
| `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` | sí | validación de los tokens de entrada (U0); la audiencia es `console-bff` |
| `VECTRA_CA_BUNDLE` | con `https` | CA de las URL anteriores; nunca se desactiva la verificación |

Sin una obligatoria, o con `https` sin CA, el proceso termina con código 2 y el mensaje nombra la variable, antes de escuchar. Las
URL no están en `config.py` (contrato `config-no-env`).

## 6. Arranque y apagado (Paso 8)

`python -m console_bff.app`: `build_app()` + `vectra_common.ops_server.run_service(app)` (8080 con el contrato y 8081 con
`/metrics`, `/healthz` y `/readyz`). Las sondas son solo del proceso (`readiness=None`): `/readyz` es 200 con los cinco destinos caídos
y sus circuitos abiertos. `SIGTERM` → apagado ordenado de ≤ 10 s (`GRACEFUL_SHUTDOWN` de U0), cierre de los cinco clientes (`aclose`
en el `lifespan`) y código 0: uvicorn re-emite la señal con el manejador previo y con el de fábrica el código sería -15, por eso
`main()` instala `_exit_clean` (`SystemExit(0)`) antes de arrancar.

**P-5 (a): lo que queda para el chart (Paso 18, U10-T04).** El `preStop` de 5 s y `terminationGracePeriodSeconds: 20` son campos del
`Deployment` y los pone el chart, con su `conftest`; también el `ConfigMap` de URLs, HPA, `ServiceMonitor` y la `ServiceAccount`
`console-bff`. Esta tarea no crea nada de eso.

## 7. Métricas (P-U10-09, 11; NFR-U10-34)

| Métrica | Etiquetas | Nota |
|---|---|---|
| `vectra_console_client_errors_total` | `error_code` (los seis del catálogo de `ClientErrorReport`) | las seis series se crean en 0 al importar `metrics.py` |
| `vectra_bff_dependency_duration_seconds` | `dependency` (los cinco destinos), `route` (la plantilla de la ruta del BFF) | se observa alrededor de cada `deps.call`, también en las lecturas previas y en las llamadas fallidas |
| `vectra_http_request_duration_seconds` | `service="console-bff"`, `route_template`, `method`, `status` | la emite U0; no se duplica |
| `vectra_circuit_state` | `dependency` | la publica `DependencyClient` (U0) |

Ninguna etiqueta lleva un identificador. `console.client_error` lleva `error_code`, `route_template` (la de la SPA), `app_version`,
`principal_subject` y `principal_role` (el primer rol en orden alfabético, como `_role` de U8 y U9).

## 8. Respuestas a P-1 a P-8 (todas en la opción recomendada (a); el usuario fusionó la tarea sin cambiarlas)

| Pregunta | Decisión |
|---|---|
| P-1 | `case.get_case_identifiers`: 1,5 s y las mismas 20 conexiones; nota fechada en P-U10-04 |
| P-2 | un timeout de un destino es 503 `dependency_unavailable` (la capa de clientes, sin tocar U0) |
| P-3 | `authz.denied` y `vectra_authz_denied_total` en cada 401 y 403; `principal_subject` en cada 403 y **ausente** en cada 401 (no se registra el `sub` de un token sin verificar) |
| P-4 | no hay otro archivo de matriz: `role_matrix.py --check` compara `REGISTRY`, C03 y `contracts/openapi/role-endpoint-matrix.md` (30 filas); las columnas de estado del token viven en `test_role_matrix.py` |
| P-5 | `run_service`, sondas y espera de ≤ 10 s aquí; `preStop` y el período de gracia, en el chart (Paso 18) |
| P-6 | las cinco reglas de `get_disparity` de §3 |
| P-7 | el `correlation_id` del cuerpo se valida y no se emite (candidata de U0: un campo propio en la allowlist) |
| P-8 | `get_me`: primer rol alfabético; sin `auth_time`, 403 `forbidden` |

## 9. Verificación

- `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests --cov=console_bff --cov-branch --cov-fail-under=90`
- `uv run python console/bff/tools/role_matrix.py --check`
- `make -C console check`
