# Resumen del código — U12 `system-verification`, Pasos 5 y 6 (U12-T02)

Código en `vectra-risk/system-verification/src/vectra_verification/`: `clock`, `clients/` (`oidc`, `_api`, `gateway`, `bff`, `registry`, `prom`, `loki`, `k8s_read`), `simulator` y `driver`. Los escenarios `rt1` y `rt4`
del simulador están diferidos por la demo (enmienda §3 U12, fila «6»): pedirlos da `scenario_deferred` y ninguna solicitud. Los tres contratos nuevos de import-linter:
`playwright` solo en `clients.oidc`, `subprocess` solo en `clients.k8s_read` y `pyarrow` solo en `simulator`.

## Decisiones de las preguntas abiertas

Del usuario (2026-11-13): P-1 autorizada; keycloak-config-cli (a); **host dinámico** (b). Las demás: nadie respondió y rige la recomendación de la tarea.

| Pregunta | Decisión | Dónde |
|---|---|---|
| P-1 Keycloak de Testcontainers | Imagen por digest de `identity-edge/keycloak/Dockerfile`, realm `realm.kind.yaml` leído sin editar, aplicado con keycloak-config-cli (digest de `values/kind.yaml`, variables `IMPORT_VARSUBSTITUTION_*` y `PUBLIC_HOSTNAME`), tema `vectra` montado, `KC_HOSTNAME` como URL completa, host `127.0.0.1:<puerto al azar>` (no el real). El emisor y los `redirect_uri` de kind se atan en una prueba unitaria contra `realm.kind.yaml` y los values del gateway | `tests/doubles/keycloak_tc.py`, `tests/unit/test_oidc_flow.py` |
| P-2 confianza de Chromium en la CA | (a) `--ignore-certificate-errors-spki-list` con la huella SPKI del certificado del servidor, tomada por una conexión TLS **verificada** con la CA. Además `route.fetch` lo hace el proceso de Playwright (Node), que confía en la CA por `NODE_EXTRA_CA_CERTS` | `clients/oidc.py` |
| P-3 dobles o servicios reales | (a) `case-service` real y el BFF real en proceso (transporte sincrónico sobre ASGI); dobles ligeros solo para fallos inyectados y los 2 000 casos, validados contra el contrato | `tests/doubles/real_case.py`, `real_bff.py`, `contract_world.py` |
| P-4 módulos nuevos | (a) `clients/oidc.py`, `clients/_api.py` y `clock.py` | `src/` |
| P-5 lectura de U5 | (a) `pyarrow` directo; carpeta por parámetro (por omisión `reference-model/.out`); `generator_version` y `seed` del manifiesto adversarial; tamaño de `test` y SHA-256 del Parquet | `simulator.read_delivery` |
| P-6 semántica de `DecisionMix` | (a) `sigue` con `p_sigue / (p_sigue + p_se_aparta)` (si ambas son 0, `sigue`); con `revision_requerida`, decide con `p_resuelve_revision` o no decide | `driver.plan` |
| P-7 token de 300 s | (a) `refresh_token` rotativo en memoria renovado antes de vencer (60 s de margen); si falla, **un** login nuevo | `oidc.UserSession.refresh` |
| P-8 reintentos | (a) simulador: 429 y 503 reenvían la misma solicitud (misma clave y mismo cuerpo) hasta 3 veces y se cuentan (`resends`); `port-forward`: una nueva elección de pod, registrada (`pods_used`, `attempts`) y error claro si cae otra vez. El conductor no reenvía 429/503: los cuenta | `simulator`, `k8s_read` |
| P-9 navegador | (a) se reusa `~/.cache/ms-playwright` (revisión 1248); no se instaló nada | `CA-2` |
| P-10 cabecera y prefijo | (a) `X-Test-Scenario: <escenario>.<prefijo>`, prefijo de 8 hex que recibe el cliente | `clients/_api.RunTag` |

## Firmas

```python
# clock
class Clock:  now() -> datetime (UTC con zona); monotonic() -> float; sleep(seconds)

# clients.oidc
OidcClient(environment, credentials, clock, *, ca_file=None, transport=None, form=None)
  .login(user) -> UserSession;  .step_up(user) -> UserSession          # PKCE S256, Chromium sin interfaz, TOTP sin reuso de ventana (la ventana de cada usuario se comparte entre clientes del proceso: `totp_windows=`, `live.TOTP_WINDOWS`)
  .service_session(client_id, scopes) -> ServiceSession                # private_key_jwt ES256, aud = emisor del entorno
  .authorization_request(step_up) -> AuthorizationRequest;  .exchange_refresh(refresh) -> (TokenSet, claims);  .close()
UserSession: .bearer() (renueva), .refresh(), .claims, .acr, .auth_time, .tokens, .step_up, .refreshes, .relogins
ServiceSession: .bearer(), .claims;  TokenSet(access_token, refresh_token, id_token): Secret;  OidcError(code)

# clients.gateway / clients.bff   (RunTag(scenario, prefix8); un gancho de cliente pone X-Test-Scenario, traceparent y Authorization)
GatewayClient(environment, bearer, tag, *, transport=None, verify=True).submit_application(ApplicationIn, idempotency_key) -> CaseRef
BffClient(environment, session, tag, ...): me() list_cases(state, page, page_size) get_case(id) record_explanation_view(id)
                                            record_decision(id, DecisionIn) resolve_frozen(model_id, FrozenResolutionIn, section)
ApiError(status, code, reason, retry_after)     # un Problem; status 0 = fallo de transporte

# clients.registry / prom / loki / k8s_read
RegistryClient(base_url, bearer, *, transport=None).metrics(...) / .freezes(...)      RegistryClient.through_port_forward(k8s, bearer)
PromClient.query(expr, at) / .query_range(expr, start, end, step)    LokiClient.query_range(expr, start, end, limit)   # QueryResult(query, start, end, step, ...)
K8sRead(runner, context=None): get(resource, ns, selector, output) logs(pod, ns, tail, since) auth_can_i(verb, resource, ns) port_forward(ns, selector, remote_port) -> Forward

# simulator
read_delivery(directory, evaluated_on) -> Population;  Simulator(environment, gateway, clock, population, run_prefix)
  .run(scenario, volume, seed, *, rate=10.0, section="decisions") -> SimulationResult(report: RunReport, sent_positions)

# driver
DecisionMix(p_view, p_sigue, p_se_aparta, p_resuelve_revision, p_factors, seed);  plan(mix, CaseFacts, rng) -> Plan   # pura: PBT-U12-03
Driver(environment, sessions, tag, clock, mix, *, transport=None, rate=10.0).run(case_ids=None) -> DriverReport
run_decisions(simulator, driver, seed, *, volume=None, rate=10.0, environment) -> DecisionsResult(simulation, driver, record)   # DEMO_VOLUME = 2000
```

La sección `decisions` se corre **con el modelo de referencia activo y antes de RT-2**: ese orden es el de la CLI (Paso 13, U12-T04) y el del operador (Paso 18).

## BR → prueba

| Regla | Prueba |
|---|---|
| BR-U12-01 (escenarios `normal` y `stratified`, lectura de U5) | `tests/unit/test_u5_reader.py`; `tests/integration/test_simulator.py` |
| BR-U12-02 (una `Idempotency-Key` por solicitud, ritmo ≤ 30/s, informe sin solicitante) | `tests/integration/test_simulator.py` (ventana deslizante, claves, informe); CA-11 contra `case-service` real |
| BR-U12-03 (login OIDC sin navegador visible, conductor, 409 y 422 sin reintento) | `tests/integration/test_oidc_headless.py`, `tests/unit/test_oidc_flow.py`, `tests/integration/test_driver.py` (BFF real), `tests/property/test_driver_mix.py` (PBT-U12-03) |
| BR-U12-06 (volumen de 2 000) | `tests/integration/test_decisions_volume.py` |

## Lo que T03 a T05 pueden llamar

- **U12-T03:** `BffClient.resolve_frozen` con `OidcClient.step_up("cumplimiento-1")` (la espera de TOTP entre reactivaciones la hace `otp_code`); `OidcClient.login` de `ingeniero-1` y `cro-1`; `RegistryClient.metrics` (filtrar por los `case_id` del `RunReport`) y `.freezes`; `PromClient.query_range`; `K8sRead.get` y `.logs`; `Simulator.run("stratified", ...)` con `short_cells`; `RunReport` (`sent`, `accepted`, `case_ids`).
- **U12-T04:** `run_decisions` y su `DecisionsRecord` (enviado y decidido, primeros 1 000 `case_ids`); `RunReport.generator_version`, `seed`, `test_rows`, `parquet_sha256` y `SimulationResult.sent_positions`; el prefijo (8 hex) derivado del `runId`; `QueryResult` de `prom` y `loki`; para la imagen, Playwright 1.64.0 con Chromium revisión 1248, el sandbox activo y la CA del entorno (`ca_file`).
- **U12-T05:** lo que solo se ve en kind, abajo.

## Lo que queda sin probar por usar el host dinámico (para U12-T05)

- El login por el gateway real: `https://vectra.localtest.me/auth/...`, la resolución del nombre y el certificado de la CA interna (`HeadlessForm` toma la huella del certificado real del entorno).
- Que Keycloak de kind publique el emisor `https://vectra.localtest.me/auth/realms/vectra` y acepte `redirect_uri` `https://vectra.localtest.me/callback` y `/stepup-callback`: la prueba unitaria ata los textos, no el comportamiento de kind.
- Los límites `auth-login`, `auth-token` y `console` del gateway; `CASE_ALLOW_TEST_SCENARIOS`; K16 y el camino a la bóveda; los selectores y puertos de Prometheus y Loki (`app.kubernetes.io/name=prometheus` en 9090 y `loki` en 3100: valores de partida sin comprobar).
- `/callback` y `/stepup-callback` bajo la CSP real de U2: el login de U12 nunca los carga.

## Dos hallazgos de la prueba con Keycloak real (candidatas para U2, no se editó el realm)

1. `realm.kind.yaml` reutiliza los alias `loa-mfa`, `amr-otp` y `amr-hwk` en varios subflujos; keycloak-config-cli 6.5.1 con Keycloak 26.8.1 solo enlaza el alias a la **primera** ejecución que lo cita. Sin enlazar, Keycloak falla **todo** login con `NullPointerException: loaConditionConfig is null`. La prueba lo repara por la API de administración (`repair_shared_authenticator_configs`: 15 ejecuciones) leyendo del mismo YAML qué alias corresponde a cada una.
2. El realm no configura el perfil de usuario y los usuarios semilla no tienen `email`, `firstName` ni `lastName`: con el perfil por omisión de Keycloak 26.8.1, el primer login termina en la acción requerida `VERIFY_PROFILE` y nunca llega al `redirect_uri`. La prueba completa los usuarios con datos inventados (`complete_user_profiles`).

Si kind aplica el realm de la misma forma, ambos afectan al login de kind.

## Candidatas de U12-T01 atendidas aquí

F-04 (`guard.check_known`, `Credentials` atada al entorno de la lista y a `ALLOWED_VAULT_HOSTS` cuando hay conexión real), F-07 (la armadura PEM no cuenta como trozo de secreto), F-08 (cabeceras en tupla y de HAR, `code=` de una URL, `code_verifier` y `otp`; `code` solo en la URL, nunca como campo) y F-09 (el token de desarrollo `root` de kind no es un secreto; un token real sigue protegido). Detalle en `logic.md`.
