# U10-T02 — Capa de API del BFF de `console`: rutas, clientes, composición, `client_errors`, matriz y arranque

**Unidad:** U10 `console` (`console-bff`)
**Historias que implementa:**
- US-402 y US-403: verificación de integridad y expediente, en la parte del BFF (Paso 5);
- US-602: los tres controles por endpoint y la matriz rol × endpoint (Pasos 5 y 7);
- US-611: errores genéricos y pruebas de ejemplo de la API (Paso 7).

Los Pasos 6, 8 y 9 no tienen historia propia en la trazabilidad del plan (§3).

**Depende de:**
- **U10-T01 en `main`** (PR #139): esqueleto, `config.py`, `object_rules.py` con `OBJECT_RULES`, `errors.py`, `Makefile`, `pytest.ini`, `.importlinter` y los módulos vacíos que esta tarea llena.
- U0 en `main`: `create_app`, `authz`, `deps.call` y `DependencyClient`, `ops_server.run_service`, `metrics`, la allowlist de logs, `read_wire` (U00-T03), las 30 rutas de `REGISTRY["console-bff"]`, `ClientErrorReport`, `ConsoleDossier`, `SessionInfo` y `LogEvent.CONSOLE_CLIENT_ERROR`.
- **No** depende en runtime de U3, U4, U7, U8 ni U9: el BFF se prueba con dobles HTTP que siguen `vectra_contracts` (plan §1, «Dobles hasta que existan las unidades reales»; RL-5). Sus contratos ya están en `REGISTRY`; `get_case_identifiers` de U8 ya está en `main` (U08-T03, PR #140).

Sin clúster (AUTONOMIA-01) y sin base de datos.
**Rama:** `tarea/U10-T02`, desde `origin/main`.

Son los Bloques C y D del plan de U10 (`aidlc-docs/construction/plans/console-code-generation-plan.md`, Pasos 5 a 9), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 y §8 (fusión «C+D (5–9)»).
- Los Pasos 5 a 8 entran **completos** (E): enmienda §3, U10, fila «1–3, 5–8, 10»: «**Las 30 rutas del BFF** (P-1, opción a). Casi todas son de paso; PBT-U10-01 recorre las 30». Rige también §2 regla 2: «Toda ruta del contrato de U0 conserva su handler».
- El Paso 9 es N/A en el propio plan.
- **Esta tarea no tiene recortes E\*F**: la tabla §3 no difiere nada de los Pasos 5 a 9, así que no hay texto tachado. Lo único que no cabe aquí es el `preStop` del Paso 8, que es un campo del chart (ver P-5).
- Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas y solo un ROJO bloquea.

Tareas que siguen en U10:
- **U10-T03**: Bloque E, Pasos 10 a 16 (SPA).
- **U10-T04**: F y el cierre, Pasos 17, 18, 21, 23 y 24. Los Pasos 19 y 20 están diferidos (§3, fila «19 · 20»: D) y el Paso 22 queda consolidado en U12 Paso 18 (enmienda §8).

---

## Alcance

**Dentro:** los Pasos 5 a 9 del plan. Va el texto del plan sin recortes. Las rutas de los comandos se escriben completas desde `vectra-risk/` (ver Precisiones).

### Bloque C — Capa de API del BFF

- [ ] **Paso 5 — Rutas, clientes y composición** (E)
  - `routes.py`: los **30** `RouteContract` de C03 con `required_roles`, `mfa` (900 s) y `object_rule` explícita (una ruta sin ella no arranca); `max_body_bytes` por omisión.
  - `clients.py`: un cliente de `deps.call` por destino (case, governance, registry, explainability, bias) con timeout, presupuesto (`x-vectra-deadline` = entrada + 9 s), límite de conexiones y circuit breaker con los umbrales de U7; sin reintentos.
  - `compose.py`:
    - `get_dossier` con `asyncio.TaskGroup` (registry `get_case_dossier` + case `get_case_identifiers`; registro caído → 503 y se cancela la otra; case caído → `identifiers_unavailable`; 403 o 404 de case → ese error);
    - `get_disparity` (governance `list_models(state=activo,congelado)` y después bias, sin caché).
  - `run_integrity_check(req)` y `get_integrity_check(id)` de paso a U3, con `already_active` en la respuesta.
  - Diseño: BR-U10-01..04; P-U10-01..05; NFR-U10-30..33. Historias: US-402, US-403, US-602.
  - **Aceptación**: `uv run pytest console/bff/tests/integration/test_compose.py console/bff/tests/integration/test_clients.py console/bff/tests/integration/test_routes_registry.py`:
    - dobles de 500 ms en las dos ramas de `get_dossier` → < 700 ms;
    - registro caído → 503 y la llamada a case cancelada; case caído → `identifiers_unavailable = true`; case con 403 → 403;
    - cada destino corta en su timeout; la cabecera de plazo llega al doble; un circuito abierto da 503 de inmediato y 0 llamadas;
    - un 503 de un `POST` → una sola llamada al destino;
    - con bias caído, `list_cases` y `record_decision` responden 2xx;
    - una ruta sin `object_rule` → `create_app` falla al arrancar;
    - (de esta tarea; «Verificación» de P-U10-03, P-U10-04 y NFR-U10-30, 32) cada destino caído por turno → sus endpoints dan 503 y los de los demás 2xx (E1, E2 y E3 de P-U10-05 §5 con dobles); el circuito de un destino se abre tras 20 llamadas fallidas y los otros cuatro siguen cerrados; un pool agotado termina en timeout dentro del plazo;
    - (de esta tarea) `get_disparity` dos veces seguidas → dos llamadas a governance y dos a bias (sin caché); `run_integrity_check` con el doble en 202 → 202 con `already_active = false`, y en 200 → 200 con `already_active = true`.

- [ ] **Paso 6 — `client_errors` y métricas** (E)
  - `POST /api/console/client-errors`: `ClientErrorReport` (U0 §9.5, `extra = "forbid"`), evento `console.client_error`, métrica `vectra_console_client_errors_total{error_code}` con las **seis** series creadas en 0 al arrancar; 204.
  - Histogramas por ruta y `vectra_bff_dependency_duration_seconds{dependency, route}`.
  - Diseño: BR-U10-22; P-U10-09, 11; NFR-U10-34.
  - **Aceptación**: `uv run pytest console/bff/tests/integration/test_client_errors.py console/bff/tests/integration/test_metrics.py`:
    - un cuerpo con un campo extra o con un mensaje libre → 422;
    - `GET /metrics` recién iniciado muestra las seis series en 0;
    - PBT-U0-07 en modo strict sobre `console.client_error`.

- [ ] **Paso 7 — Matriz rol × endpoint y pruebas de ejemplo de la API** (E)
  - Matriz generada desde el registro de rutas (BR-U10-19): 30 endpoints × (4 roles, sin rol de negocio, expirado, otra audiencia, `acr = pwd`, `auth_time` vencido), comparando status y `code`; un caso negativo por regla de objeto; `authz.denied` con `principal_subject` en cada 401/403. Se publica como `role-endpoint-matrix.md` y se compara con C03.
  - Pruebas de ejemplo del FD (business-logic-model §3): analista → aprobación de modelo → 403; JWT expirado, de otra audiencia o mal firmado → 401; aprobador sin MFA reciente → 403 `mfa_required`; `decision_already_recorded` → 409 con el `reason`; expediente de `cumplimiento`.
  - Diseño: BR-U10-19; PBT-U10-01; NFR-U10-46. Historias: US-602, US-611.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_role_matrix.py console/bff/tests/integration/test_api_examples.py`; `uv run python console/bff/tools/role_matrix.py --check` (la matriz generada coincide con C03 y con `role-endpoint-matrix.md` versionado).

- [ ] **Paso 8 — Arranque, apagado y resumen de la API** (E)
  - Readiness y liveness solo del proceso (8081); `preStop` de 5 s; arranque con `vectra_common.ops_server.run_service(app)` y espera de ≤ 10 s en el apagado (revisión de consistencia entre unidades, 2026-11-01).
  - Cobertura ≥ 90 % en el resto del BFF; resumen en `aidlc-docs/construction/console/code/bff-api.md`.
  - Diseño: INF-U10-01; NFR-U10-60.
  - **Aceptación**: `uv run pytest console/bff/tests --cov=console_bff --cov-branch --cov-fail-under=90`; prueba de que `/readyz` responde 200 con todos los destinos caídos;
    - (de esta tarea) `python -m console_bff.app` arranca de verdad, como proceso, con las variables obligatorias; sin una de ellas no arranca; con `SIGTERM` termina en ≤ 10 s.

### Bloque D — Repositorio

- [ ] **Paso 9 — Repositorio y migraciones: N/A**
  - U10 no tiene base de datos.
  - **Aceptación**: `test ! -d console/bff/migrations`.

### Precisiones

- **Rutas de la aceptación.** El plan escribe algunas rutas relativas a `console/bff/` (`tests/integration/…`). Los comandos de esta tarea y de los CA usan la ruta completa desde `vectra-risk/`.
- **Archivos que esta tarea crea o llena (plan §1, más lo que piden los pasos).**
  - Módulos vacíos de U10-T01 que ahora llevan código: `console/bff/src/console_bff/{routes,clients,compose,client_errors,metrics,app}.py`.
  - `console/bff/tools/role_matrix.py` (Paso 7). El directorio `bff/tools/` **no** está en §1: se agrega con una nota en §1 del plan.
  - `console/bff/tests/doubles/`: los dobles de case, governance, registry, explainability y bias, y el soporte de tokens (se borra el `.gitkeep`).
  - `console/bff/tests/integration/`: `test_routes_registry.py`, `test_clients.py`, `test_compose.py`, `test_client_errors.py`, `test_metrics.py`, `test_api_examples.py`, `test_app.py` y `test_service_shutdown.py` (se borra el `.gitkeep`).
  - `console/bff/tests/property/test_role_matrix.py` y las pruebas unitarias que hagan falta en `console/bff/tests/unit/`.
  - `aidlc-docs/construction/console/code/bff-api.md`.
  - `console/bff/tests/load/` sigue vacío (el script k6 es del Paso 21) y **no** se crea `console/bff/migrations/` (Paso 9).
- **`routes.py` y los 30 `RouteContract`.** Los 30 contratos ya existen en U0: `REGISTRY["console-bff"]` (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`, `_bff()`). `routes.py` **no** los vuelve a declarar ni los copia.
  - «`required_roles`» es el campo `roles`; «`mfa` (900 s)» es `mfa=True` con `mfa_max_age = MFA_MAX_AGE`; «`max_body_bytes` por omisión» es `DEFAULT_MAX_BODY` (32 KiB). Una prueba lo fija sobre las 30: 11 rutas con `mfa` (las de la columna «MFA» de C03), todas con 900 s y todas con el cuerpo por omisión.
  - La `object_rule` de cada ruta sale de `OBJECT_RULES` (P-3 (a) de U10-T01, nota en §1 del plan): `routes.py` arma el mapa `(método, ruta) → handler` y, antes de llamar a `create_app`, exige que las claves de `OBJECT_RULES` sean **exactamente** los `operation_id` de las 30 rutas. Si falta o sobra una, lanza `ContractViolation` y el proceso no arranca (deny by default, P-U10-01). `None` declarado vale; una clave ausente no.
  - `create_app` de U0 ya falla si falta o sobra un handler. No se usa `create_app(contract=subconjunto)`.
- **Orden de los tres controles (BR-U10-01).** Rol y MFA los aplica el middleware de U0 (`require`). La regla de objeto corre dentro del handler, después, y **antes** de reenviar la acción: el BFF lee el objeto con el token del usuario, aplica la función pura de `OBJECT_RULES` y, si rechaza, responde sin llamar a la escritura (`CONFLICT` → 409 `conflict_state`; `FORBIDDEN` → 403 `forbidden`). El destino vuelve a validar.
- **Qué lectura alimenta cada regla.** El diseño dice «el BFF lee el objeto» (P-U10-01) sin nombrar la ruta. Con los contratos de `main`:

  | Regla (`OBJECT_RULES`) | Lectura previa | Datos que usa |
  |---|---|---|
  | `record_explanation_view`, `record_decision`, `retry_case`, `create_applicant_summary` | case `GET /v1/cases/{id}` | `state`, `anonymized`, `decision.final_outcome`, `recommendation_entry_id` |
  | `start_validation`, `approve_model`, `resolve_frozen`, `retire_model` | governance `GET /v1/models/{id}` | `state` |
  | `approve_policy` | governance `GET /v1/policies` (no hay lectura por id) | la política con ese `policy_version_id` y el cuerpo |
  | `decide_data_source` | governance `GET /v1/data-sources` (no hay lectura por id) | `state` y `pre_post_report is not None` |
  | `start_source_comparison` | `GET /v1/data-sources`, `GET /v1/models/{candidate_version_id}` y `GET /v1/models?state=activo` | estado de la fuente, `source_candidate_for` de la candidata y si existe una `activo` |

  - La lectura previa usa el timeout de lectura del destino y cabe en el presupuesto: el peor caso es `start_source_comparison`, con 3 × 1,5 s + 4 s = 8,5 s < 9 s.
  - Un objeto que no aparece en la lista → 404 `not_found`. Un error de la lectura previa se traduce como cualquier otro error del destino.
  - `create_applicant_summary` envía a U7 `ApplicantSummaryRequest(case_id, recommendation_entry_id)` con el valor del detalle (C03). Si el detalle no trae `recommendation_entry_id`, responde 409 `conflict_state` sin llamar a U7 (la parte «explicación sincronizada» de C03).
  - `CaseDetail` contiene `Recommendation`: se lee con `read_wire(CaseDetail, raw)` de U00-T03, nunca con `model_validate_json` a secas, `model_construct` ni nada privado de `outcome` (candidata «`CaseDetail.recommendation`» de `CANDIDATAS.md`, cerrada en U00-T03).
- **Endpoints de paso.** Un endpoint del BFF, una llamada al destino (BR-U10-03):

  | BFF (bajo `/api/console`) | Destino (`REGISTRY`) | Clave de `OPERATION_TIMEOUT_SECONDS` |
  |---|---|---|
  | `GET /me`, `POST /client-errors` | ninguno | — |
  | `GET /cases`, `GET /cases/failures`, `GET /cases/{id}` | case, la misma ruta bajo `/v1` | `case.list_cases`, `case.list_persistent_failures`, `case.get_case` |
  | `POST /cases` (reenvía `Idempotency-Key`), `POST /cases/{id}/explanation-views`, `…/decision`, `…/retry` | case, la misma ruta bajo `/v1` | `case.create_manual_application`, `case.record_explanation_view`, `case.record_decision`, `case.retry_case` |
  | `POST /cases/{id}/applicant-summary` | explainability `POST /v1/applicant-summaries` | `explainability.applicant_summary` |
  | `GET /cases/{id}/dossier` | registry `GET /v1/dossiers/{case_id}` y case `GET /v1/cases/{id}/identifiers` | `registry.get_case_dossier` y la de P-1 |
  | `POST /integrity-checks`, `GET /integrity-checks/{id}` | registry, la misma ruta bajo `/v1` | `registry.run_integrity_check`, `registry.get_integrity_check` |
  | `GET /models`, `GET /models/{id}`, `GET /policies`, `GET /data-sources` | governance, la misma ruta bajo `/v1` | `governance.read` |
  | Los 10 `POST` de modelos, políticas y fuentes | governance, la misma ruta bajo `/v1` | `governance.transition` |
  | `GET /disparity` | governance `GET /v1/models?state=activo,congelado` y bias `GET /v1/disparity` | `governance.read` y `bias.get_dashboard` |
  | `GET /freezes`, `GET /freezes/{id}` | bias, la misma ruta bajo `/v1` | `bias.list_freezes`, `bias.get_context_package` |

  - **Token.** El BFF reenvía el `Authorization` del usuario tal cual. Los clientes **no** llevan `token_source`: con él, `deps.call` reintenta una vez ante un 401, y el BFF no reintenta (NFR-U10-33). El token del usuario ya trae las audiencias de los cinco destinos (U2 domain-entities §1.3).
  - **Plazo.** `x-vectra-deadline` = el reloj de la app al entrar + `DEADLINE_BUDGET_SECONDS`. Si la solicitud ya trae un plazo menor, rige el menor (NFR-U0-23 (b)).
  - **Solicitud.** La query validada por U0 (`ctx.query`) y el cuerpo validado (`ctx.body`) se reenvían serializados desde el modelo, no desde los bytes de entrada.
  - **Respuesta 2xx.** Se valida contra el `response_model` de la ruta del BFF y se responde con el mismo estado que el destino: 202 en `integrity-checks` con `app_factory.respond(model, 202)`, y 204 donde no hay cuerpo. Un 2xx que no valida → 500 `internal_error` (BR-U10-04).
  - **Respuesta de error.** Pasa por `errors.translate_error`. Ningún handler arma un `Problem` a mano.
- **`clients.py`.**
  - Cinco `DependencyClient` con los nombres `case`, `governance`, `registry`, `explainability` y `bias`. Es la etiqueta `dependency` de `vectra_circuit_state` y de la alerta `ConsoleDependencyCircuitOpen` (P-U10-10).
  - `max_connections` sale de `config.CONNECTIONS_PER_REPLICA`.
  - Breaker de NFR-U10-30: `BreakerConfig(window_size=20, failure_ratio=0.5, window_seconds=30, open_for=10)`. Los cuatro valores van como constantes en `config.py`, con su caso en `test_config.py`.
  - Las URL de los destinos **no** van en `config.py` (contrato `config-no-env`): las lee `app.py` del entorno, con la convención de U9: `VECTRA_CASE_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_REGISTRY_URL`, `VECTRA_EXPLAINABILITY_URL` y `VECTRA_BIAS_URL`, más las de U0 (`VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE` con https). El chart del Paso 18 (U10-T04) las fija desde su `ConfigMap`; `bff-api.md` las lista.
  - Ningún módulo de `console_bff` importa `httpx` (contrato `no-httpx`). Los dobles sí pueden: se inyectan por el parámetro `transport` de `DependencyClient`.
  - `build_app` admite inyectar el `authenticator`, un transporte por destino y los relojes, como `vectra_bias.app.build`.
- **`compose.get_dossier` (BR-U10-03; P-U10-02).**
  - Las dos llamadas salen dentro de un `asyncio.TaskGroup`.
  - Registro sin respuesta (timeout, conexión, 5xx o circuito abierto; la misma definición que BR-U10-03 da para case) → 503 `dependency_unavailable`, y la llamada a case se cancela. La prueba lo comprueba en el doble: la llamada a case no termina y la respuesta no espera su timeout.
  - Registro con 403 o 404 → ese error.
  - Case sin respuesta → `ConsoleDossier` con `identifiers = None`, `identifiers_unavailable = true` y `anonymized = false` (no se sabe).
  - Case con 403 o 404 → ese error, **nunca** `identifiers_unavailable`.
  - Case con `anonymized = true` → `anonymized = true`, sin identificadores.
- **`compose.get_disparity`.** Governance y después bias, en serie y sin caché. Governance caído → 503: no se cae a «bias sin versión», porque mostraría la versión anterior tras un congelamiento (P-U10-02, Q7). Los casos que el diseño no cierra están en P-6.
- **Dobles (`console/bff/tests/doubles/`).**
  - Un doble por destino. Sus respuestas se construyen con los modelos de U0 (`response_model` de la ruta del destino) y una prueba exige que cada `(método, ruta)` que sirve un doble esté en `REGISTRY[<destino>]`. Así un cambio de contrato rompe el doble.
  - Cada doble cuenta llamadas, guarda las cabeceras recibidas y admite demora, caída (conexión), 5xx, un `Problem` dado y «no responde».
  - Tokens: el emisor de prueba de U0 (`contracts/tests/strategies/auth.py`: `token`, `bearer`, `jwks_document`), con los claims de U2 (`roles`, `acr`, `auth_time`, `aud`, `azp = vectra-console`). Se añade `pythonpath = tests/doubles ../../contracts/tests` a `console/bff/pytest.ini`, como hace `bias-monitoring/pytest.ini`. De otras unidades no se importa nada: lo que haga falta se copia citando el origen.
- **Paso 6.**
  - La validación del cuerpo ya la hace U0 (`_body_guard` con `StrictModel`). «Mensaje libre» se prueba con un campo `message`, con un `error_code` fuera del catálogo y con un `app_version` que no es SemVer: los tres → 422 `validation_error`, sin evento ni métrica.
  - El evento `console.client_error` lleva los campos de U0 §8.1: `error_code`, `route_template` (la ruta de la SPA que viene en el cuerpo), `app_version`, `principal_subject` y `principal_role`. `principal_role` sigue la convención que ya usan U8 y U9 (`_role` de `case-management/src/vectra_case/api.py`). Qué se hace con el `correlation_id` del cuerpo está en P-7.
  - `metrics.py` registra el contador en `vectra_common.metrics.REGISTRY` y crea las seis series en 0 al importar o al arrancar. La prueba lee `/metrics` de `app.state.ops_app`.
  - «Histogramas por ruta» es `vectra_http_request_duration_seconds{service, route_template, method, status}`, que U0 ya emite. No se duplica: la prueba comprueba que, tras una solicitud, existe la serie con `service="console-bff"` y la plantilla de la ruta.
  - `vectra_bff_dependency_duration_seconds{dependency, route}` es nuevo (P-U10-11, sobrecosto del BFF): se crea con `vectra_common.metrics.histogram` y `HTTP_BUCKETS`, y se observa alrededor de cada `deps.call`, también en las lecturas previas. `route` es la plantilla de la ruta del BFF. Una prueba exige que ninguna etiqueta lleve un identificador.
  - PBT-U0-07 en modo strict: `VECTRA_LOG_STRICT=1`, como `case-management/tests/integration/test_app.py` y `bias-monitoring/tests/integration/test_app.py`.
- **Paso 7.**
  - `test_role_matrix.py` corre la app real (`build_app` con los dobles) sobre el producto de los 30 endpoints por las 9 columnas del plan: `analista`, `ingeniero_riesgo`, `cro`, `cumplimiento`, sin rol de negocio, expirado, otra audiencia, `acr = pwd` y `auth_time` de hace más de 900 s.
  - El oráculo son las columnas «Roles» y «MFA» de C03, leídas de `aidlc-docs/inception/application-design/component-methods.md` o transcritas con cita. Nunca es `REGISTRY` ni el propio código del BFF.
  - Resultado esperado por celda: expirado u otra audiencia → 401 `unauthenticated`; rol fuera de «Roles» → 403 `forbidden`; rol válido en una ruta con MFA y sin MFA reciente → 403 `mfa_required`; lo demás → 2xx. El rol va antes que la MFA.
  - PBT-U10-01 **no se recorta**. Además del muestreo de Hypothesis, las 270 celdas corren como prueba parametrizada, porque 500 ejemplos no garantizan cubrirlas todas.
  - Para que una celda dé 2xx, cada endpoint necesita un cuerpo válido y un doble que devuelva el objeto en un estado que su regla acepte. Los generadores de U0 están en `contracts/tests/strategies/`.
  - «Un caso negativo por regla de objeto»: por cada una de las 11 reglas de `OBJECT_RULES`, el doble devuelve un estado que la regla rechaza → 409, y el doble cuenta **cero** llamadas a la escritura.
  - `authz.denied` y `principal_subject` en los 401: ver P-3.
  - `tools/role_matrix.py`: genera la matriz desde `REGISTRY["console-bff"]`, extrae las tablas de C03 y lee las filas `console-bff` de la matriz versionada (ver P-4). `--check` sale con 0 si las tres coinciden y con 1, mostrando la diferencia, si no. Admite `--c03 <ruta>` y `--matrix <ruta>` para probar el rojo sobre copias.
  - Pruebas de ejemplo del FD que son del BFF (las de la ventana emergente y el reintento son de U10-T03):
    - analista → `POST /api/console/models/{id}/approval` → 403 `forbidden` con `authz.denied`;
    - JWT expirado, de otra audiencia o firmado con otra llave → 401;
    - `cro` con `acr = pwd`, o con `auth_time` vencido, aprueba un modelo → 403 `mfa_required`;
    - `decision_already_recorded`: el doble de case devuelve el caso `listo` en la lectura y `409 conflict_state` con `reason = decision_already_recorded` en la escritura (la carrera de P-U10-01) → 409 con ese `reason`;
    - expediente para `cumplimiento`: case sano → con identificadores; case caído → `identifiers_unavailable = true`; 403 de case → 403 (BR-U10-03).
- **Paso 8.**
  - `app.py`: `build_app(...)`, `main()` con `run_service(app)` y la guarda `if __name__ == "__main__"`.
  - `/readyz` y `/healthz` son los de `ops_server`, sin predicado de `readiness` (INF-U10-01: sus destinos tienen su propio circuito). La prueba pone los cinco destinos caídos, abre sus circuitos y pide `/readyz` → 200.
  - Arranque real: un proceso lanzado tal cual (`python -m console_bff.app`), no `runpy` (el revisor de U04-T09 marcó ese desvío).
  - Apagado: `SIGTERM` → el proceso termina con código 0 en ≤ 10 s (`GRACEFUL_SHUTDOWN` de U0) y cierra los cinco clientes (`aclose`).
  - Cobertura: el 100 % de ramas de `object_rules` y `errors` (U10-T01) se mantiene y el total de `console_bff` queda en ≥ 90 %.
- **`bff-api.md`.** Lista: la tabla de endpoints y destinos; qué lectura alimenta cada regla; las variables de entorno; las métricas y sus etiquetas; las respuestas a P-1 a P-8; y lo que queda para el chart.
- **`make -C console check`.** `test-bff` pasa a correr `console/bff/tests` entero (unit, property, integration y doubles) con el perfil `ci`, conserva la puerta del 100 % de los dos módulos puros y añade la del 90 % total. Se agregan `role_matrix.py --check` y `mypy --strict` sobre `console/bff/tools`. Termina en 0.
- **Trazabilidad.** Cada identificador que citan los Pasos 5 a 8 queda trazado en el código o en sus pruebas (`DECISIONES-LOOP.md` §6, enmienda del 2026-11-09). Hoy fallan y deben dejar de fallar: P-U10-02, 05, 09 y 11; NFR-U10-02, 11, 30, 31, 32, 33, 34 y 46; e INF-U10-01.
- **Plan.** Marca `[x]` los Pasos 5 a 9, con `(U10-T02)`. En §1 agrega la nota de `bff/tools/role_matrix.py`. En el Paso 8 agrega «`preStop` en el chart (Paso 18)» si rige P-5 (a).
- **Bitácora.** `bitacoras/U10-T02.md` lleva la salida **real** de cada comando, pegada como texto y con rutas absolutas a los logs. Nada de plantillas sin expandir.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Bloque E, Pasos 10 a 16 (U10-T03)**: toda la SPA. Incluye la mitad de SPA de BR-U10-19 («las rutas de la SPA por rol», Paso 14), los ejemplos del FD con ventana emergente y las candidatas de ESLint de `CANDIDATAS.md`: «`console/spa/eslint.config.mjs:23` … F-01» y «fixtures de ESLint … F-03».
- **Bloque F y el cierre (U10-T04)**: `Dockerfile` del BFF (Paso 17); el chart con `preStop`, HPA, `ConfigMap` de URLs, `ServiceMonitor` y `ServiceAccount` (Paso 18; candidatas «U4/U10, runbook de política sin BFF» y «U4/U10, `ServiceAccount` `console-bff`»); el script k6 y la trazabilidad de cada BR (Paso 21); `console/README.md` (Paso 23); el cierre y `evidence/cierre-demo.md` (Paso 24).
- **Pasos 19 y 20, diferidos por la demo** (§3, U10, fila «19 · 20»: D): alertas, runbooks, dashboard y workflows. Por eso la mitad `promtool` de la verificación de P-U10-09 (`ConsoleChunkOrCspError` con una serie de 0 a 1) no entra; aquí solo entran las seis series en 0. Tampoco hay `console.yml`: la puerta es `make -C console check`.
- **Paso 22**, consolidado en U12 Paso 18 (enmienda §8): E1 a E7 con las unidades reales, k6 y Keycloak real.
- **`mutmut`**: sigue diferido (§3, fila «4 · 16»).
- **Cambios a U0, a U2 o a los servicios de destino.** No se agrega `object_rule` a `RouteContract`, no se toca `ProblemHandlerMiddleware` y no se cambia ningún contrato. Si un contrato de destino no encaja con C03, se reporta. Quedan como candidatas de U0, sin tocar: «convención única para `principal_role`» (revisor, U09-T03) y «`CaseDetail` … mover el invariante» (codificador, U08-T02).
- **Caché, reintentos o estado en el BFF** (BR-U10-02; NFR-U10-33).
- **La candidata «U3, `from_checkpoint_seq` / `to_checkpoint_seq` de `IntegrityStatus`»**: el BFF pasa `RegistryDossier` tal como llega. Cómo se muestra es de la vista `Dossier`, que la enmienda difiere (§3, fila «13 Casos»).
- **La candidata «Bitácora de U10-T01 … F-04»**: es historia, no código.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/console-code-generation-plan.md` (§1, Bloques C y D, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6, RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1.5, §2, §3 U10, §4, §6 P-1, §8)
- `aidlc-docs/inception/application-design/component-methods.md` (C03, las seis tablas: «Roles», «MFA», «Objeto» y «Destino»)
- `aidlc-docs/construction/console/functional-design/business-rules.md` (BR-U10-01..04, 19, 22)
- `aidlc-docs/construction/console/functional-design/business-logic-model.md` (§1, §2.4, §3: PBT-U10-01 y los ejemplos)
- `aidlc-docs/construction/console/functional-design/domain-entities.md`
- `aidlc-docs/construction/console/nfr-requirements/nfr-requirements.md` (NFR-U10-02, 11, 30..34, 46, 60)
- `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md` (P-U10-01..05, 09, 10, 11 y §5, E1 a E3)
- `aidlc-docs/construction/console/infrastructure-design/infrastructure-design.md` (INF-U10-01)
- `aidlc-docs/construction/console/code/bff-logic.md`, `bitacoras/U10-T01.md` y `revisiones/U10-T01/ronda-1.md`
- `aidlc-docs/construction/contracts/functional-design/domain-entities.md` (§6, §8.1: `authz.denied` y `console.client_error`; §9.5)
- `console/Makefile`, `console/bff/{pyproject.toml,.importlinter,pytest.ini,coveragerc}` y `console/bff/src/console_bff/{config,object_rules,errors}.py`
- `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py` (`_bff()`, `_case()`, `_governance()`, `_registry()`, `_explainability()`, `_bias()`)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/{api,application,governance,monitoring,registry}.py`, `catalog.py` y `outcome/__init__.py` (`read_wire`)
- `contracts/python/vectra_common/src/vectra_common/{app_factory,authn,authz,deps,deadline,errors,logging,metrics,ops_server}.py`
- `contracts/tests/strategies/auth.py` (emisor de tokens de prueba) y `contracts/openapi/role-endpoint-matrix.md` (la genera `contracts/tools/codegen.py`)
- Destinos reales, para que los dobles se parezcan: `case-management/src/vectra_case/api.py`, `governance/src/vectra_governance/api.py`, `decision-registry/src/vectra_registry/{api,dossier}.py`, `scoring-explainability/explainability/src/explainability/app.py` y `bias-monitoring/src/vectra_bias/app.py`
- Modelos de app sin base y de dobles HTTP: `bias-monitoring/src/vectra_bias/app.py`, `bias-monitoring/tests/doubles/{http_doubles,service_support}.py` y `bias-monitoring/pytest.ini`
- `identity-edge/keycloak/realm/realm.prod.yaml` (cliente `vectra-console`, audiencias)
- `DECISIONES-LOOP.md` (§6) y `CANDIDATAS.md` (las entradas citadas en «Fuera», en P-1 y en «Notas»)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`, en serie, anotando `uptime` antes y después. Comprobado sobre `main` (`fdff2a9`):
- CA-1, CA-3, CA-4 y CA-6 terminan con código 4 (`ERROR: file or directory not found`);
- CA-2 termina con código 1 (`ImportError: cannot import name 'build_app'`);
- CA-5 con código 2 (el archivo no existe);
- CA-10 con código 1 (falta `bff-api.md` y `KeyError: 'case.get_case_identifiers'`);
- CA-11 lista hoy los 13 identificadores.

Ese es el rojo esperado. CA-8 y CA-9 **ya pasan hoy** y deben seguir pasando. CA-7 no se corrió al redactar: hoy solo mediría los módulos puros de U10-T01, así que no es un rojo.

- [ ] **CA-1** — Rutas, clientes y composición (Paso 5; BR-U10-01..04; P-U10-01..05; NFR-U10-30..33; US-402, US-403, US-602).
  ```bash
  uv run pytest console/bff/tests/integration/test_compose.py console/bff/tests/integration/test_clients.py console/bff/tests/integration/test_routes_registry.py -v
  ```
  Esperado: código 0, con un caso por cada línea de aceptación del Paso 5, incluidas las marcadas «(de esta tarea)». **Rojo primero:** con las dos llamadas de `get_dossier` en serie, el caso de 500 ms tarda ≈ 1 s y falla; con `token_source` en un cliente, «una sola llamada» falla ante un 401.

- [ ] **CA-2** — Las 30 rutas con su handler y su regla declarada (Paso 5; P-U10-01).
  ```bash
  VECTRA_OIDC_ISSUER=http://kc.test/auth/realms/vectra VECTRA_JWKS_URL=http://kc.test/certs VECTRA_CASE_URL=http://case.test VECTRA_GOVERNANCE_URL=http://gov.test VECTRA_REGISTRY_URL=http://reg.test VECTRA_EXPLAINABILITY_URL=http://exp.test VECTRA_BIAS_URL=http://bias.test uv run python -c "from console_bff.app import build_app; from console_bff.object_rules import OBJECT_RULES; from vectra_contracts.routes import REGISTRY; app = build_app(); ids = {r.operation_id for r in REGISTRY['console-bff']}; assert ids == set(OBJECT_RULES); print(len(ids), len([r for r in app.router.routes if getattr(r, 'methods', None)]))"
  ```
  Esperado: imprime `30 30`. Si el punto de entrada no se llama `build_app` o pide otras variables, el comando se ajusta al nombre real y el cambio se anota en la bitácora. La prueba de `test_routes_registry.py` que quita una clave de `OBJECT_RULES` y espera `ContractViolation` es parte de CA-1.

- [ ] **CA-3** — `client_errors` y métricas (Paso 6; BR-U10-22; P-U10-09, 11; NFR-U10-34).
  ```bash
  uv run pytest console/bff/tests/integration/test_client_errors.py console/bff/tests/integration/test_metrics.py -v
  ```
  Esperado: código 0. Casos:
  - cuerpo válido → 204, un evento `console.client_error` y la serie de ese `error_code` en 1 (lectura de vuelta en `/metrics`, no el 204);
  - campo extra, `message`, `error_code` fuera del catálogo → 422, sin evento y con las seis series en 0;
  - `GET /metrics` recién iniciado → las seis series en 0;
  - PBT-U0-07 en modo strict;
  - `vectra_bff_dependency_duration_seconds` con `dependency` y `route` de conjunto cerrado.

  **Rojo primero:** sin crear las series al arrancar, `/metrics` recién iniciado no las muestra y la prueba falla.

- [ ] **CA-4** — PBT-U10-01 y las pruebas de ejemplo de la API (Paso 7; BR-U10-19; NFR-U10-46; US-602, US-611).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_role_matrix.py console/bff/tests/integration/test_api_examples.py -v
  ```
  Esperado: código 0. PBT-U10-01 entera, las 270 celdas parametrizadas, un caso negativo por cada una de las 11 reglas de objeto (409 y cero escrituras en el doble), `authz.denied` en cada 401 y 403 (con `principal_subject` según P-3) y los cinco ejemplos del FD. **Rojo primero:** con `roles=ALL_ROLES` forzado en el handler de aprobación de modelo (o con el oráculo de C03 alterado en una fila), la celda `analista` × `approve_model` falla.

- [ ] **CA-5** — La matriz generada coincide con C03 y con la versionada (Paso 7; BR-U10-19).
  ```bash
  uv run python console/bff/tools/role_matrix.py --check
  ```
  Esperado: código 0 y una línea que dice cuántos endpoints comparó (30). **Rojo primero:** con `--c03` sobre una copia de `component-methods.md` donde `retry_case` pierde `cro`, sale con código 1 y nombra la fila.

- [ ] **CA-6** — Arranque, sondas y apagado (Paso 8; INF-U10-01).
  ```bash
  uv run pytest console/bff/tests/integration/test_app.py console/bff/tests/integration/test_service_shutdown.py -v
  ```
  Esperado: código 0. Casos:
  - `/readyz` y `/healthz` → 200 con los cinco destinos caídos y sus circuitos abiertos;
  - `python -m console_bff.app` arranca como proceso y responde `/readyz` 200 en 8081;
  - sin `VECTRA_CASE_URL` el proceso termina con código distinto de 0 antes de escuchar;
  - `SIGTERM` → código 0 en ≤ 10 s.

- [ ] **CA-7** — Cobertura (Paso 8; NFR-U10-60).
  ```bash
  uv run pytest console/bff/tests --cov=console_bff --cov-branch --cov-fail-under=90 && uv run pytest console/bff/tests/unit console/bff/tests/property --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100
  ```
  Esperado: código 0 en los dos. La bitácora pega la tabla de cobertura por módulo. Ningún módulo nuevo queda excluido con `omit`, y `# pragma: no cover` solo va en la guarda `__main__`.

- [ ] **CA-8** — Sin base de datos (Paso 9).
  ```bash
  test ! -d console/bff/migrations && ! grep -rniE "sqlalchemy|alembic|psycopg|asyncpg" console/bff/src console/bff/pyproject.toml && echo OK
  ```
  Esperado: `OK`.

- [ ] **CA-9** — Contratos de imports y BFF sin `httpx` propio (NFR-U10-64; P-U0-07).
  ```bash
  uv run lint-imports --config console/bff/.importlinter && ! grep -rnE "^\s*(import|from) httpx" console/bff/src console/bff/tools
  ```
  Esperado: `Contracts: 3 kept, 0 broken.` (o más, si se agrega alguno) y el `grep` sin salida.

- [ ] **CA-10** — Documentación, plan y constantes.
  ```bash
  test -s aidlc-docs/construction/console/code/bff-api.md && grep -nE "^- \[x\] \*\*Paso [5-9] " aidlc-docs/construction/plans/console-code-generation-plan.md && uv run python -c "from console_bff import config; print(config.OPERATION_TIMEOUT_SECONDS['case.get_case_identifiers'])" && grep -n "get_case_identifiers" aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md
  ```
  Esperado: `bff-api.md` existe; salen cinco líneas del plan, cada una con `(U10-T02)`; se imprime el timeout fijado en P-1 (`1.5` con la opción (a)); y la fila de P-U10-04 nombra `get_case_identifiers`.

- [ ] **CA-11** — Trazabilidad, con la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit console --all | grep -E "^(P-U10-(02|05|09|11)|NFR-U10-(02|11|30|31|32|33|34|46)|INF-U10-01):" ; uv run python platform/tests/test_traceability.py --all | grep "sin trazabilidad" | sort > /tmp/u10-t02-rama.txt
  ```
  Esperado: el primer `grep` no imprime nada. El segundo archivo se compara con la misma corrida sobre la base de la rama: no hay ninguna línea nueva, y las 13 de arriba ya no están. El revisor corre `--all` en la base y en la rama.

- [ ] **CA-12** — `check` de la unidad (RL-4).
  ```bash
  make -C console check
  ```
  Esperado: código 0, con `uptime` antes y después en la bitácora. Si el diff cambia `uv.lock` o el `pyproject.toml` raíz, se corre también `make -C contracts check`, en serie. Si su `bench_gate` falla por carga, se anota con la carga y una corrida aislada en la rama y en la base.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `console/bff/tests/doubles/`: los cinco dobles, el soporte de tokens y la prueba de que cada ruta de un doble está en `REGISTRY`.
- `console/bff/tests/integration/test_routes_registry.py`: las 30 rutas, `mfa` y cuerpo por omisión, y el arranque que falla sin regla declarada.
- `console/bff/tests/integration/test_clients.py`: timeout por operación, cabecera de plazo, breaker, una sola llamada, pool agotado y cada destino caído por turno.
- `console/bff/tests/integration/test_compose.py`: `get_dossier`, `get_disparity` y los dos endpoints de integridad.
- `console/bff/tests/integration/test_client_errors.py` y `test_metrics.py`: las líneas del Paso 6.
- `console/bff/tests/property/test_role_matrix.py`: PBT-U10-01 y las 270 celdas.
- `console/bff/tests/integration/test_api_examples.py`: los ejemplos del FD y los casos negativos por regla.
- `console/bff/tests/integration/test_app.py` y `test_service_shutdown.py`: sondas, arranque real y apagado.
- `console/bff/tests/unit/`: `tools/role_matrix.py` (con `--c03` y `--matrix` sobre `tmp_path`), los casos nuevos de `test_config.py` (breaker y `get_case_identifiers`) y las dos pruebas de las candidatas que esta tarea atiende (ver Notas).
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U10-T02.md`, con la salida pegada. Como mínimo los de CA-1 (las dos llamadas en serie), CA-3 (series sin crear), CA-4 (rol de más) y CA-5 (copia de C03 alterada). El par falla-pasa es la prueba.

Los nombres de paquete de prueba no deben chocar con los de otras unidades (candidata F-06 de U07-T03): si hace falta un `__init__.py`, el paquete lleva un nombre propio de U10.

---

## Preguntas abiertas

Si no hay respuesta, rige la recomendación. **P-1 y P-2 cambian el diseño o un contrato visible para la SPA: conviene que el usuario las confirme antes del despacho.** Las demás tienen una opción por omisión.

- **P-1 — Timeout y conexiones de case `get_case_identifiers`.** `CANDIDATAS.md` lo exige: «**U10, diseño P-U10-04 (codificador y revisor, U10-T01): no fija timeout ni presupuesto de conexiones para case `get_case_identifiers`**, que `get_dossier` usa en paralelo (Bloque C). Hay que fijarlos antes del Paso 5.»
  - **(a) Recomendada:** 1,5 s, el timeout de las lecturas de case, y las mismas 20 conexiones compartidas. Es una lectura de una fila, va en paralelo con los 5 s del registro y no suma al p95 (P-U10-02). Se agrega `"case.get_case_identifiers": CASE_READ_TIMEOUT_SECONDS` a `config.py`, su caso a `test_config.py`, la operación a la primera fila de la tabla de P-U10-04 con una nota fechada, y se corrige la frase de `bff-logic.md` §3.
  - (b) 5 s, igual que `get_case_dossier`. No aporta: si case tarda más de 1,5 s ya está degradado, y el expediente sale igual con `identifiers_unavailable`.
  - (c) Un pool aparte para `get_dossier`. Cambia el presupuesto de conexiones que U8 ya confirmó (120 con 6 réplicas).
- **P-2 — Qué responde el BFF cuando un destino corta por timeout.** P-U10-03 dice «Timeout de un `POST`: 503 `dependency_unavailable`», y BR-U10-03 trata el timeout como «sin respuesta» → 503. Pero en U0 `deps.call` lanza `DependencyTimeout`, cuyo código es `deadline_exceeded` (504). Tal cual, un timeout sale 504, cuenta como 5xx propio del BFF en `ConsoleBffErrorBudget*` (P-U10-10 solo excluye `dependency_unavailable`) y la SPA necesitaría otro mensaje.
  - **(a) Recomendada:** seguir el diseño de U10. La capa de clientes del BFF convierte todo `DependencyTimeout` de un destino en `DependencyUnavailable` (503), sin tocar U0. `deadline_exceeded` queda solo para una solicitud que **entra** con el plazo vencido (lo lanza U0 antes del handler). Se documenta en `bff-api.md`.
  - (b) Seguir U0: un timeout responde 504 `deadline_exceeded`. Hay que corregir P-U10-03, BR-U10-03 y la expresión de las alertas de P-U10-10, y avisar a U10-T03 para el mensaje.
- **P-3 — `principal_subject` en el `authz.denied` de un 401.** El Paso 7 y BR-U10-01 piden `authz.denied` «con `principal_subject` en cada 401/403». En U0, `ProblemHandlerMiddleware` lo emite en los dos, pero en un 401 no hay `Principal` verificado y el campo no sale (U0 §8.1 lo declara opcional: `principal_subject?`).
  - **(a) Recomendada:** la prueba exige `authz.denied` y `vectra_authz_denied_total` en **cada** 401 y 403; `principal_subject` en cada 403; y su **ausencia** en cada 401. No se registra un `sub` de un token sin verificar. Se anota en `bff-api.md` y como candidata de diseño.
  - (b) Leer el `sub` sin verificar para registrarlo en los 401. Es dato controlado por quien ataca y obliga a tocar U0.
- **P-4 — Dónde se publica la matriz.** El Paso 7 dice «se publica como `role-endpoint-matrix.md`» y BR-U10-19 precisa «(U0, Paso 15)». Ese archivo ya existe, `contracts/openapi/role-endpoint-matrix.md`, lo genera `contracts/tools/codegen.py` y tiene las 30 filas de `console-bff` con roles y MFA, sin las columnas de estado del token.
  - **(a) Recomendada:** no se crea otro archivo. `role_matrix.py --check` compara tres cosas: lo generado desde `REGISTRY["console-bff"]`, C03 y las filas `console-bff` del archivo de U0. Las columnas de estado del token viven en la parametrización de `test_role_matrix.py`. `console/README.md` (Paso 23, U10-T04) enlaza el archivo de U0.
  - (b) Publicar además `console/bff/role-endpoint-matrix.md` con las 9 columnas. Son dos matrices versionadas que pueden divergir.
- **P-5 — El `preStop` de 5 s del Paso 8.** Es un campo del `Deployment`, y el chart es del Paso 18 (U10-T04).
  - **(a) Recomendada:** aquí entran `run_service`, las sondas y la espera de ≤ 10 s. El `preStop` y `terminationGracePeriodSeconds: 20` los pone el chart en U10-T04, con su `conftest`; `bff-api.md` lo deja escrito y el Paso 8 del plan lleva la nota. Es lo que hizo U08-T03 con el suyo.
  - (b) Crear ya un `Deployment` mínimo en `console/chart/`. Adelanta el Paso 18 sin sus políticas.
- **P-6 — Casos de `get_disparity` que el diseño no cierra.** BR-U9-18 dice que la versión servible es la que rige «por omisión»; P-U10-02 dice «governance y después bias», sin distinguir.
  - **(a) Recomendada:**
    - si el filtro trae `version`, el BFF no consulta governance y llama a bias con esa versión;
    - si no la trae, consulta governance y envía la servible;
    - si governance no devuelve ninguna, llama a bias sin versión (BR-U9-18: «si no llega, bias usa la versión con las recomendaciones más recientes»);
    - si devuelve más de una, envía la `activo` y lo registra como candidata;
    - governance caído, sin `version` en el filtro → 503.
  - (b) Consultar governance siempre, también con `version` explícita. Una caída de governance tumba una consulta que no lo necesita.
- **P-7 — El `correlation_id` de `ClientErrorReport`.** El contrato lo admite, pero los campos de `console.client_error` (U0 §8.1) no tienen dónde ponerlo: el `correlation_id` del registro es el de la solicitud al BFF y `_add_context` lo fija siempre.
  - **(a) Recomendada:** se valida y no se emite. Queda como candidata de U0 (un campo propio en la allowlist).
  - (b) Sustituir el `correlation_id` del registro por el del cuerpo. Rompe la correlación de la propia solicitud y exige manipular la `ContextVar` de U0.
- **P-8 — `get_me` con un token fuera de lo previsto.** `SessionInfo.role` es un solo rol y `auth_time` es obligatorio; el diseño no dice qué hacer con dos roles de negocio o sin `auth_time`.
  - **(a) Recomendada:** con varios roles, el primero en orden alfabético, la misma convención que `principal_role` en U8 y U9; sin `auth_time`, 403 `forbidden`. Los dos casos llevan prueba y quedan como candidata de diseño.
  - (b) 500 `internal_error` en los dos casos.

---

## Notas

- Archivos que se **modifican en su sitio**:
  - los seis módulos vacíos de U10-T01 (`routes.py`, `clients.py`, `compose.py`, `client_errors.py`, `metrics.py`, `app.py`);
  - `console/bff/src/console_bff/config.py` (constantes del breaker y `get_case_identifiers`) y `console/bff/tests/unit/test_config.py`;
  - `console/bff/pytest.ini`, `console/bff/.importlinter` si se agrega un contrato, y `console/Makefile`;
  - `aidlc-docs/construction/plans/console-code-generation-plan.md` (casillas y notas), `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md` (fila de P-U10-04, según P-1) y `aidlc-docs/construction/console/code/bff-logic.md` (§3);
  - `console/bff/pyproject.toml`, `pyproject.toml` raíz y `uv.lock` **solo** si hace falta una dependencia nueva; no debería, porque FastAPI, uvicorn y `prometheus-client` llegan por `vectra-common`.

  Nada de duplicados con sufijo. `object_rules.py` y `errors.py` no cambian de comportamiento.
- **Candidatas de `CANDIDATAS.md` que esta tarea atiende:**
  - «**U10, diseño P-U10-04 … `get_case_identifiers`**»: P-1.
  - «U10, `object_rules.py:20-22` (revisor, U10-T01, ronda 1, F-02, AMARILLO): `DataSourceState`, `PolicyState` y `PolicyDecision` copian los `Literal` de `models/governance.py` de U0 sin una prueba que compare `get_args`»: se agrega esa prueba, porque esta tarea ya lee `DataSource` y `PolicyVersion` para alimentar las reglas.
  - «U10, `SPA_API_TIMEOUT_SECONDS` (revisor, U10-T01, ronda 1, F-05, AMARILLO)»: una prueba lee `console/spa/src/config/constants.ts` y exige que `API_TIMEOUT_SECONDS` valga lo mismo que `SPA_API_TIMEOUT_SECONDS`.
  - «U0, `CaseDetail.recommendation` (codificador, U08-T02)», cerrada en U00-T03: el BFF lee con `read_wire`.

  Cada una se marca resuelta en `CANDIDATAS.md` citando esta tarea. Las candidatas nuevas (P-3, P-6, P-7, P-8) se agregan al final.
- **Trampas conocidas.**
  - `deps.call` con `token_source` reintenta ante un 401. El BFF no lo usa.
  - `create_app` no exige las cabeceras declaradas en `RouteContract.headers`: si falta `Idempotency-Key` en `POST /api/console/cases`, el BFF la reenvía ausente y traduce el error que dé case.
  - `DependencyClient` crea su breaker y publica `vectra_circuit_state` al construirse, y `process.ensure_service()` guarda estado global. Las pruebas que crean varias apps usan `process.reset_for_tests()` donde haga falta y no comparten clientes entre casos.
  - Los timeouts son reales: esperar 5 s por operación alarga el `check`. `httpx` entrega el timeout efectivo en `request.extensions["timeout"]`, así que el doble puede registrar el valor de cada operación y compararlo con `config`. Aun así debe quedar **al menos un corte real**, el de una lectura de 1,5 s contra un doble que no responde.
  - «< 700 ms» con dobles de 500 ms es sensible a la carga de la máquina compartida. No se sube el umbral, que es el de NFR-U10-02: si falla con carga, se anota `uptime` y se repite aislado.
  - Las etiquetas de métricas llevan plantillas de ruta, nunca rutas con identificadores.
- PBT-U10-01..06 nunca se recortan. En esta tarea entra la 01, entera. La 02 y la 03 ya están (U10-T01); la 04, la 05 y la 06 son de la SPA (U10-T03).
- Máquina compartida: los `make check` van en serie, con `uptime` antes y después. Si una corrida pasa más de 2 horas sin avanzar, se detiene, se anota y se repite.
