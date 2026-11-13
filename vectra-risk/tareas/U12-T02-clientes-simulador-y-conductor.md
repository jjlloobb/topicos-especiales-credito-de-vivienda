# U12-T02 — Clientes, login sin navegador visible, simulador y conductor de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. La trazabilidad del plan (§3) nombra el Paso 6 en US-101 (`SIM-NORMAL`, con los Pasos 10 y 18): aquí se escribe el `simulator` que esa evidencia usa. El Paso 5 no tiene historia; sostiene todo lo que U12 hace como persona o como canal.
**Depende de:**
- **U12-T01 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). Sin ella no existen `vectra-risk/system-verification/` ni `aidlc-docs/construction/system-verification/code/`. Lo que esta tarea da por sentado, leído en la rama `tarea/U12-T01` (`9b18465`):
  - `system-verification/src/vectra_verification/guard.py`: `Environment`, `KIND`, `STAGING`, `check_environment`, `check_token_issuer`, `gateway_client`, `check_section`, `check_reactivation` y `check_decisions` (rechaza un reloj sin zona: `clock_without_timezone`).
  - `credentials.py`: `Credentials.client_key`, `user_password`, `user_totp_seed`, `totp(user, at)` y `secret_values()`; la clase `Secret`, que no se muestra en `repr()`.
  - `evidence.py`: `scrub`, `ensure_clean` y `prepare`. Quita `Authorization`, `Cookie`, `Set-Cookie` y los campos `access_token`, `refresh_token`, `id_token`, `client_assertion` y `password`; falla ante un JWT o un secreto cargado.
  - `sampler.py`: `Row`, `normal`, `stratified` (devuelve `StratifiedSample` con `ids`, `cells` y `short`) y `cell_report`.
  - Vacíos, con docstring: `simulator.py`, `driver.py` y `clients/__init__.py`. `tests/integration/` solo tiene `.gitkeep`.
  - `.importlinter` (3 contratos), `Makefile` (`lint`, `types`, `imports`, `test`, `check`), `pytest.ini` (`--import-mode=importlib`, `pythonpath = tests/doubles`) y `tests/unit/test_kubectl_verbs.py`, que recorre `src/`, `demos/` y el `Makefile`.
  - `make -C system-verification check` tardó 2 min 33 s con carga 6 a 9 (`bitacoras/U12-T01.md`, CA-14).
- **U2, realm de kind** (`identity-edge/keycloak/realm/realm.kind.yaml`, comprobado sobre `origin/main` `82c1718`):
  - cliente público `vectra-console` (líneas 834 a 851): `publicClient: true`, `standardFlowEnabled: true`, `directAccessGrantsEnabled: false`, `pkce.code.challenge.method: S256`, `use.refresh.tokens: 'true'`, `default.acr.values: mfa`, y los dos `redirectUris` `https://$(env:PUBLIC_HOSTNAME)/callback` y `/stepup-callback`. Sus mapeadores ponen `aud = console-bff` (línea 857), `roles` (899), `acr`, `amr` y `auth_time`;
  - usuarios semilla (líneas 688 a 818): `analista-1`, `analista-2`, `ingeniero-1`, `cro-1` y `cumplimiento-1`, entre otros. Cada uno con contraseña `$(env:SYNTH_<USUARIO>_PASSWORD)` y una credencial `otp` cuya semilla es `$(env:SYNTH_<USUARIO>_TOTP_SEED)`: TOTP de 6 dígitos, 30 s, `HmacSHA1`, Base32 (líneas 699 a 701). `requiredActions: []`;
  - `verification-reader` (líneas 1267 a 1286) y `channel-simulator` (1310 a 1327): `client-jwt` con ES256 y JWKS por `$(env:CLIENT_<CLIENTE>_JWKS)`. Sus scopes son **opcionales**: hay que pedirlos en la solicitud de token (`registry:read:metrics` y `registry:read:monitoring`; `intake:submit`). El scope `registry:read:metrics` agrega `aud = decision-registry-service` (líneas 228 a 240);
  - del realm: `sslRequired: all` (línea 8), `acr.loa.map` `{"pwd":1,"mfa":2}` (18), `accessTokenLifespan: 300` (19), fuerza bruta con `failureFactor: 5` y `permanentLockout: true` (22 a 28), `revokeRefreshToken: true` con `refreshTokenMaxReuse: 0` (30 y 31) y `browserFlow: vectra-browser` (42);
  - el archivo es un YAML de keycloak-config-cli con 36 referencias `$(env:…)`. No es un JSON de `--import-realm`.
- **U2, imagen y tema:** `identity-edge/keycloak/Dockerfile` (línea 3: `quay.io/keycloak/keycloak:26.8.1` por digest; `--http-relative-path=/auth`; tema `themes/vectra`). keycloak-config-cli: `identity-edge/keycloak/values/kind.yaml` (líneas 9 a 16) y sus variables en `values/common.yaml` (líneas 449 a 462).
- **U2, gateway** (`identity-edge/gateway/routes.yaml`): `/api/console` exige `azp = vectra-console` y un rol (líneas 130 a 147); `/api/intake/v1/intake/applications` exige `azp` `channel` o `channel-simulator` y el scope `intake:submit`, y se reescribe a `/v1/intake/applications` (148 a 165). Límites sin ráfaga: `console` 20/s por `x-vectra-sub` (87), `intake-channel-simulator` 30/s (93 a 97), `auth-login` y `auth-token` 600/min por IP (99 a 110).
- **U2, patrón de login sin SPA:** `identity-edge/tests/e2e/e2e_support.py`: `totp_code` (línea 196, evita reusar el código), `Flow` (210 a 270, Authorization Code + PKCE con `httpx`) y `service_token` (288, `private_key_jwt` con `jwt.encode`). Corre **solo contra kind**. **No hay en el repositorio ninguna prueba con Keycloak de Testcontainers**: ni en `identity-edge/tests`, ni en `console/bff/tests`, ni en `console/spa/tests/e2e` (que usa el emisor de prueba `console/bff/tests/doubles/bff_oidc.py`).
- **U10, BFF** (`contracts/openapi/console-bff.yaml`; `aidlc-docs/construction/console/code/bff-api.md`): `GET /api/console/cases` (filtros `state`, `page`, `page_size`), `GET /api/console/cases/{id}`, `POST …/explanation-views` (204), `POST …/decision` (200) y `POST /api/console/models/{id}/frozen-resolution` (204; solo `cumplimiento`, con MFA: `contracts/openapi/role-endpoint-matrix.md`, línea 42). El BFF reenvía el `Authorization` del usuario tal cual, y también `traceparent` e `Idempotency-Key` (bff-api.md, líneas 24 y 25). MFA reciente: `MFA_MAX_AGE = 900` s (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`, línea 21). El BFF real corre en proceso con `console_bff.app.build(urls, authenticator=…, transports=…)` y los dobles de U10 (`console/bff/tests/doubles/bff_e2e_server.py`, `build_server`).
- **U8, ingesta** (`case-management/src/vectra_case/intake.py`): `Idempotency-Key` con `^[\x21-\x7e]{1,128}$` (línea 29); `X-Test-Scenario` con `^[A-Za-z0-9_.:-]{1,100}$` (30), solo con `azp = channel-simulator` y `allow_test_scenarios`, si no 422 (43 a 50). Respuesta `CaseRef` (`case_id`, `state`), estado 200 (`contracts/openapi/case-service.yaml`). La app corre en proceso con `vectra_case.app.build_app(settings, authenticator=…, services=…)` (`app.py`, línea 122) sobre PostgreSQL de Testcontainers (`case-management/tests/migrations/case_pg.py`; la imagen `postgres:17.9-trixie` ya está en el Docker local).
- **U8 y U0, decisión:** `DecisionIn` (`vectra_contracts/models/api.py`, línea 75); `decision_is_coherent`, `check_used_factors` y `check_justification` (`vectra_contracts/validation.py`, líneas 80 a 106); `validate_decision` (`case-management/src/vectra_case/decision.py`, línea 30). El 409 por decisión repetida es un `Problem` con `code = conflict_state` y `reason = decision_already_recorded` (`vectra_case/evidence.py`, línea 392).
- **U5, datos** (`reference-model/`): `make -C reference-model release` escribe en `reference-model/.out/` (sin versionar) `datasets/test.parquet` y `adversarial/manifest.json` (`docs/release.md`, línea 27). El manifiesto adversarial trae `generator_version` y `seed` (`src/vectra_reference/adversarial.py`, líneas 470 a 473). `config/generator.yaml`: `generator_version: "1.0.0"`, `seed: 20261101`. El Parquet **no** guarda esos dos valores (`generate.py`, `store_schema=False`). `generate(out_dir, config)` y `with_overrides(config, n_rows=…)` producen un Parquet pequeño con el generador real. Etiquetas: `derive_monitoring_labels` (`vectra_contracts/labels.py`, línea 63).
- **U3, lectura:** `GET /v1/entries` con `case_id`, `entry_type`, `limit`, `projection`, `recorded_from`, `recorded_to`, `seq` y `seq_after` (`contracts/openapi/decision-registry-service.yaml`). `registry:read:metrics` → proyección `metrics`; `registry:read:monitoring` → `monitoring_daily` y `monitoring_freezes` (`decision-registry/src/vectra_registry/projections.py`, líneas 51 a 53). Tipos: `MetricsProjection` y `FreezeProjection` de `vectra_contracts`.
- **U1, K16** (`platform/rbac/verification-operator/k16.yaml`): `pods/portforward` solo en `vectra-app` y `vectra-observability`; sin `get` sobre `services`.
- **Workspace** (`pyproject.toml` raíz y `uv.lock`): ya están `playwright==1.64.0`, `pytest-playwright==0.10.0`, `pyotp==2.10.0`, `pyjwt==2.15.1`, `cryptography==50.0.2`, `pyarrow==26.0.1`, `testcontainers==4.14.2` y `httpx==0.28.1`. El grupo `dev` instala editables `vectra-case`, `vectra-console-bff` y `vectra-reference`.
- **Navegadores:** Playwright de Python 1.64.0 espera `chromium` y `chromium-headless-shell` revisión **1248** (`.venv/lib/python3.12/site-packages/playwright/driver/package/browsers.json`). `~/.cache/ms-playwright/` ya tiene `chromium-1248` y `chromium_headless_shell-1248`, instalados por Playwright de Node. Es la misma revisión: se reusan (ver P-9).

Es código, dobles y pruebas sin clúster (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6). Usa Docker local para Testcontainers.
**Rama:** `tarea/U12-T02`, desde `origin/main` **después** de fusionar U12-T01.

Bloque C del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 5 y 6), según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fila U12: «A+B (1–4) · C (5–6) · D (8, 10) · E+F (12, 13, 15, 17) · G+H (18–19)») y §8 (U12: 5 tareas, sin cambio). Es la segunda de cinco. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 5 Clientes de lectura y del gateway | **E** | Completo | Enmienda §3 U12, fila «5: E, E, —, Todas»; §1: «Todo lo que U12 hace como persona pasa por el BFF, con login OIDC sin navegador visible (plan U12 Paso 5)» |
| 6 Simulador y conductor de decisiones | **E\*F** | Entran el `simulator` `normal` y `stratified` y el `driver`, con PBT-U12-03. Se difieren los escenarios `rt1` y `rt4` del simulador | Enmienda §3 U12, fila «6: E, E\*F, Entran el `simulator` `normal` y `stratified` y el `driver` (PBT-U12-03). Se difieren los escenarios `rt1` y `rt4`»; §1.5, fila U12 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09. **PBT-U12-03 no se recorta** (enmienda §5.2: «U12: PBT-U12-01..04»; §2 regla 1: «Una PBT que entra se corre entera»).

**Lección que esta tarea aplica** (enmienda §8 y U10-T03): un doble que no se parece al servicio real esconde defectos que solo aparecen en kind. U12 es la última unidad: después no hay tarea que los atrape. Por eso, donde hay un servicio real barato de levantar sin clúster, el criterio lo usa (Keycloak en Testcontainers, la app del BFF y la de `case-service` en proceso). Donde queda un doble escrito a mano, se valida contra `contracts/openapi/` o contra los tipos de `vectra_contracts`.

Lo que U12 hace en las demos (enmienda §1) y lo que esta tarea aporta:
- **Flujo base y D4:** `simulator` `normal` → gateway → U8 `POST /v1/intake/applications`, con `Idempotency-Key` y la cabecera de escenario. Después, el `driver` (`analista-1` y `analista-2`) por el BFF: `GET /api/console/cases`, `GET …/{id}`, con probabilidad `p_view` `POST …/explanation-views`, y `POST …/decision`. Son los 2 000 casos de D4.
- **D2 (RT-2):** el lote `stratified` y el step-up de `cumplimiento-1` para la reactivación. Aquí se escriben el simulador, el login y el step-up; la sección `rt2` es de U12-T03.
- **D1 y D3:** los clientes `registry`, `prom` y `k8s_read` que leerán los oráculos de RT-3 y RT-5 (U12-T03).

---

## Alcance

**Dentro:** los Pasos 5 y 6 del plan. Texto del plan, sin recortes salvo los escenarios `rt1` y `rt4` del simulador, que van ~~tachados~~ con su cita y en «Fuera»:

### Bloque C — Clientes, simulador y conductor

- [ ] **Paso 5 — Clientes de lectura y del gateway**
  - `gateway` y `bff`: `httpx` con la cabecera de escenario de U8 y un `traceparent` con el prefijo de la corrida.
  - **Login y step-up sin navegador visible** (revisión del plan de tareas de U12, 2026-10-10): el BFF no hace el flujo OIDC, lo hace el cliente público `vectra-console` (U2), y Keycloak solo ofrece Authorization Code + PKCE (sin *password grant*). La herramienta actúa como ese cliente:
    1. genera `state`, `nonce` y `code_verifier`;
    2. abre la URL de autorización (`prompt=login`, `max_age=0`, `acr_values=mfa` para el step-up) en **Chromium sin interfaz con Playwright**, que llena el formulario de Keycloak con la contraseña y el código TOTP calculado con `pyotp`;
    3. intercepta la navegación al `redirect_uri` registrado (`/callback` o `/stepup-callback`) **antes** de cargar la SPA, y toma de la URL `code` y `state`;
    4. valida que `state` coincida, canjea `code` con el `code_verifier` en el endpoint de token y valida el `nonce` y `acr = mfa` del ID token.

    Los tokens solo quedan en memoria; el contexto de Playwright se descarta tras cada login.
  - **Reuso de TOTP** (pendientes posteriores al cierre, 2026-10-10): Keycloak rechaza un código TOTP ya usado en la misma ventana de 30 s. La herramienta guarda en memoria, por usuario, la ventana del último código usado, y antes de un nuevo login o step-up del mismo usuario (por ejemplo, dos reactivaciones seguidas de `cumplimiento-1` en RT-2) espera a la ventana siguiente. El mismo mecanismo sirve para el login normal de los analistas y para el step-up de `cumplimiento-1` en la reactivación de RT-2.
  - **Aceptación del login**: `uv run pytest system-verification/tests/integration/test_oidc_headless.py` contra un Keycloak de Testcontainers con el realm de kind: login de `analista-1` → token con su rol; step-up de `cumplimiento-1` → `acr = mfa` y `auth_time` reciente; un `state` alterado → error sin canje; ningún token ni contraseña en disco.
  - `registry`: por `kubectl port-forward` a **un pod de** `decision-registry-service` (`pod/<nombre>`, elegido con `kubectl get pods -l …`; nunca `svc/…`, INF-U12-03; pendientes consolidados, segunda tanda, 2026-10-10), con el token de `verification-reader` (`registry:read:metrics` y `registry:read:monitoring`).
  - `prom` y `loki`: por `port-forward`, sus APIs de lectura.
  - `k8s_read`: envoltorio de `kubectl get`, `logs`, `auth can-i` y `port-forward` (lo único que el Paso 1 admite).
  - Diseño: INF-U12-03; NFR-U12-50.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_clients.py` con dobles (cada solicitud lleva la cabecera y el prefijo; el cliente del registro manda el token de `verification-reader`; un `port-forward` caído → error claro, sin reintento silencioso).

- [ ] **Paso 6 — Simulador y conductor de decisiones** (E\*F)
  - `simulator`: escenarios `normal`, `stratified`, ~~`rt1`, `rt4`~~ desde U5 (partición `test` y manifiesto adversarial), con `generator_version` y `seed` registrados; una `Idempotency-Key` por solicitud; ritmo ≤ 30/s; `RunReport` sin datos del solicitante. **(Los escenarios `rt1` y `rt4` se difieren por la demo: enmienda §3 U12, fila «6»: «Se difieren los escenarios `rt1` y `rt4`»; ver «Fuera». Con el recorte, del manifiesto adversarial solo se leen `generator_version` y `seed`: P-5.)**
  - `driver`: `analista-1` y `analista-2` por el BFF; `DecisionMix` con semilla; 409 y 422 contados, sin reintentar con otro contenido.
  - **Volumen de demostración** (BR-U12-06; pendientes consolidados, segunda tanda, 2026-10-10): la sección `decisions` envía **2 000** casos `normal` y el conductor los decide, con el modelo de referencia activo y antes de RT-2. Son los datos de la prueba en kind de U11 (INF-U11-06), del dashboard de producto, de la disparidad humana de U9 y, los primeros 1 000, de `CASE-SIZE`. El manifiesto registra el número enviado y el decidido.
  - Diseño: BR-U12-01..03; NFR-U12-10.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_driver_mix.py tests/integration/test_simulator.py tests/integration/test_driver.py` (dobles del gateway y del BFF): PBT-U12-03; el simulador nunca supera 30/s; claves distintas; el `RunReport` sin identificadores; el conductor ante un 409 `decision_already_recorded` sigue con el caso siguiente.

### Estructura de destino (§1 del plan): lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- pyproject.toml  .importlinter  Makefile        # se modifican (dependencias, contratos, objetivo de integracion)
|-- src/vectra_verification/
|   |-- clock.py                                   # nuevo, no esta en §1 (P-4): reloj inyectable con zona
|   |-- evidence.py                                # se amplia solo si CA-6 lo exige (campos de OIDC)
|   |-- clients/
|   |   |-- oidc.py                                # nuevo, no esta en §1 (P-4): login, step-up, refresco y tokens de servicio
|   |   |-- gateway.py  bff.py  registry.py  prom.py  loki.py  k8s_read.py     # Paso 5
|   |-- simulator.py  driver.py                    # Paso 6 (hoy vacios)
`-- tests/
    |-- unit/         test_oidc_flow.py  test_tokens_not_leaked.py  test_k8s_read.py  test_u5_reader.py
    |-- property/     test_driver_mix.py                                       # PBT-U12-03
    |-- integration/  test_oidc_headless.py  test_clients.py  test_simulator.py  test_driver.py  test_decisions_volume.py
    |-- doubles/      keycloak_tc.py  kubectl_double.py  gateway_double.py  registry_double.py  obs_double.py
    `-- fixtures/     (lo que haga falta; ningun secreto real)

vectra-risk/aidlc-docs/construction/system-verification/code/clients.md   # nuevo: firmas, decisiones de P-n y tabla BR -> prueba
```

Los nombres de los archivos de la aceptación del plan (`test_oidc_headless.py`, `test_clients.py`, `test_driver_mix.py`, `test_simulator.py` y `test_driver.py`) son fijos. Los demás son una propuesta: puedes fundir o partir archivos de prueba y de dobles, y lo anotas en la bitácora.

**No** se crean: `manifest.py` y `cli.py` siguen vacíos (Paso 13), `scenarios/` y `load/` siguen vacíos, y no hay `Dockerfile`, `README.md`, guiones de `demos/`, `chart/` ni `migrations/`.

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `uv.lock`, regenerado con `uv lock`. Solo cambian las dependencias del paquete `vectra-verification`: gana `playwright`, `pyjwt` (con el extra `crypto`) y `pyarrow`, en las versiones que el lock ya fija. Ninguna versión de un tercero cambia y no aparece ningún paquete nuevo.
2. `pyproject.toml` raíz: **solo si hace falta** un `[[tool.mypy.overrides]]` para un tercero sin tipos. Anótalo en la bitácora. No se tocan `members`, `sources` ni el grupo `dev`.
3. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas de los Pasos 5 y 6.
4. `aidlc-docs/construction/system-verification/code/clients.md`: nuevo.
5. `CANDIDATAS.md`: las candidatas nuevas de «Notas».
6. `bitacoras/U12-T02.md`: nuevo.

`identity-edge/`, `console/`, `case-management/`, `reference-model/`, `decision-registry/`, `contracts/` y `platform/` **se leen, no se editan**. Las pruebas pueden importar sus dobles y sus apps; el código de `src/` no.

### Precisiones

**Generales**

- **Dependencias** (`system-verification/pyproject.toml`): `playwright==1.64.0`, `pyjwt[crypto]==2.15.1` y `pyarrow==26.0.1` (P-5). `vectra-common` sigue prohibida: `jwt` se usa directo, no por `vectra_common`.
- **import-linter.** Los tres contratos de U12-T01 siguen. Se agregan:
  - `playwright`, `jwt` y `pyarrow` a los módulos prohibidos de la lógica pura (`sampler`, `report`, `story_map`, `rt2_latency`);
  - `playwright` solo en `clients.oidc`: prohibido en todos los demás módulos;
  - `subprocess` solo en `clients.k8s_read`: prohibido en todos los demás. Así `kubectl` se invoca desde un solo archivo, que es el que mira la prueba de verbos;
  - `pyarrow` solo en `simulator`.

  `test_traceability.py` no lee `.importlinter` (`CANDIDATAS.md`, líneas 415 y 531): cita los identificadores en archivos `.py`.
- **Reloj inyectable** (candidata de U12-T01: «U12-T02 debe inyectar un reloj con zona»). Un solo tipo, con `now()` (siempre con zona UTC), `monotonic()` y `sleep(segundos)`. Lo reciben `simulator`, `driver` y `clients.oidc`. El mismo `now()` es el que se pasa a `guard.check_decisions`. Ningún módulo llama a `datetime.now()`, `time.time()` ni `time.sleep()` directo, salvo la implementación real del reloj. Las pruebas de ritmo y de la ventana TOTP usan un reloj falso: **cero `sleep` reales**.
- **Barrera antes de enviar.** Todo cliente del gateway se crea con `guard.gateway_client` o pasa antes por `guard.check_environment`. Todo token recibido pasa por `guard.check_token_issuer` antes de usarse.
- **Tokens solo en memoria.** Un tipo que guarda `access_token`, `refresh_token` e `id_token` sin mostrarlos en `repr()` ni `str()`, como `credentials.Secret`. Nada de `open` en escritura, `write_text`, `tempfile`, `storage_state`, trazas, video, HAR ni capturas de Playwright. Ningún mensaje de excepción ni registro de log lleva un token, una contraseña, un código TOTP, el `code`, el `code_verifier` ni la URL de retorno con su query.
- **Un fallo de login no se reintenta.** El realm bloquea para siempre al quinto fallo (`failureFactor: 5`, `permanentLockout: true`). Ante una contraseña o un TOTP rechazados, la herramienta termina con un error claro. Nunca hace un bucle de logins.
- **`clients.md`.** Firmas reales de los clientes, del simulador y del conductor; la decisión tomada en cada P-n; la tabla BR-U12-01, 02 y 03 → prueba; y lo que T03 a T05 pueden llamar.

**Paso 5 — Login y step-up** (INF-U12-03; NFR-U12-04; BR-U12-03)

- **Módulo:** `clients/oidc.py` (P-4). Actúa como el cliente público `vectra-console`.
- **Solicitud de autorización:** `<issuer>/protocol/openid-connect/auth` con `response_type=code`, `client_id=vectra-console`, `scope=openid` (el de la SPA: `console/spa/src/auth/manager.ts`, línea 13), `state`, `nonce`, `code_challenge` y `code_challenge_method=S256`. `redirect_uri` es `https://<host>/callback` en el login y `https://<host>/stepup-callback` en el step-up. El step-up agrega `prompt=login`, `max_age=0` y `acr_values=mfa`, igual que la SPA (`console/spa/src/stepup/oidc.ts`, líneas 24 a 27). `issuer` y `host` salen del `guard.Environment`.
- **Formulario:** Chromium sin interfaz con la API síncrona de Playwright. Los campos del tema `vectra` se llaman `username`, `password` y `otp` (los que usa `e2e_support.Flow`, líneas 251 a 255). El TOTP sale de `Credentials.totp(user, at)`. `default.acr.values: mfa` hace que **todo** login pida el segundo factor.
- **Intercepción:** la navegación al `redirect_uri` se intercepta y se **aborta** antes de salir a la red. De su URL se toman `code` y `state`. La SPA nunca se carga. En esta máquina `vectra.localtest.me:443` es el gateway del kind que está corriendo: una prueba comprueba que no sale ninguna solicitud al `redirect_uri`.
- **Canje:** primero se compara `state`; si no coincide, error **sin** llamar al endpoint de token. Después `POST <issuer>/protocol/openid-connect/token` con `grant_type=authorization_code`, `client_id`, `code`, `redirect_uri` y `code_verifier`, por `httpx` con la CA del entorno.
- **Validación del ID token:** firma contra el JWKS del realm (`…/certs`), `iss` exacto (`guard.check_token_issuer`), `aud = vectra-console`, `exp`, `nonce` igual al generado y `acr = mfa`. En el step-up, además, `auth_time` de hace 900 s o menos (`MFA_MAX_AGE`), que es lo que el BFF exige. Cualquier fallo es un error y los tokens se descartan.
- **Contexto descartado:** un contexto de Playwright nuevo por login, cerrado en un `finally`, también cuando el login falla. Nunca `--no-sandbox` (Paso 15): CA-2 lo busca en `src/`.
- **Reuso de TOTP:** memoria por usuario de la ventana del último código usado (`floor(t / 30)`). Antes de otro login o step-up del mismo usuario en la misma ventana, espera a la siguiente con el reloj inyectado. La lógica se prueba con reloj falso. Contra el Keycloak real hay **una** espera real de 30 s como máximo, porque el reloj de Keycloak no se puede inyectar: es la única espera real permitida.
- **Vigencia del token** (P-7). `accessTokenLifespan` es de 300 s y decidir 2 000 casos tarda mucho más. El cliente renueva con `grant_type=refresh_token` antes de vencer y guarda **el refresh token nuevo** de cada respuesta: el realm los rota y rechaza uno ya usado.
- **Tokens de servicio:** `client_credentials` con `private_key_jwt` ES256 para `channel-simulator` (`scope=intake:submit`) y `verification-reader` (`scope=registry:read:metrics registry:read:monitoring`). El `client_assertion` lleva `iss = sub = client_id`, `aud` = la URL del endpoint de token, `jti`, `iat` y `exp` a 60 s, como `e2e_support.service_token`. La llave sale de `Credentials.client_key` y no se escribe en disco.
- **TLS de Chromium** (P-2): el navegador solo confía en el certificado del entorno. La prueba con Keycloak real nunca corre con los errores de certificado ignorados.

**Paso 5 — Keycloak de Testcontainers con el realm de kind** (P-1)

- El realm es `identity-edge/keycloak/realm/realm.kind.yaml`, **leído en la prueba y sin editar**. Nada de una copia en `tests/fixtures/`.
- Misma imagen de Keycloak que kind: el digest de la línea `FROM` de `identity-edge/keycloak/Dockerfile`, leído en la prueba. Con el tema `vectra` montado y la ruta `/auth`.
- El realm lo aplica keycloak-config-cli con la imagen y las variables de `identity-edge/keycloak/values/` (`IMPORT_VARSUBSTITUTION_ENABLED`, `IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR` y `PUBLIC_HOSTNAME`). Las 36 variables `$(env:…)` las genera la prueba: contraseñas al azar de 14 o más caracteres, semillas Base32 al azar y un JWKS ES256 por cliente. Ningún valor real.
- `sslRequired: all` obliga a HTTPS: la prueba genera una CA y un certificado con `cryptography`, en una carpeta temporal **dentro del worktree**.
- El contenedor escucha en un puerto al azar del host. Nunca 443, 8080, 8081 ni 8443. Lleva límite de memoria (≈ 1 GiB) y se borra al terminar, también si la prueba falla.
- Una sola instancia por sesión de pytest. Cada caso usa un usuario distinto cuando puede, para no chocar con la ventana TOTP ni con el contador de fuerza bruta.
- Las credenciales generadas llegan al código por un `Credentials` real con el doble de la bóveda de U12-T01 (`tests/doubles/vault_double.py`): así se prueba la cadena bóveda → `credentials` → TOTP → Keycloak.

**Paso 5 — Clientes** (INF-U12-03; NFR-U12-02, 50)

- **`gateway` y `bff`.** `httpx` propio. Cada solicitud lleva `X-Test-Scenario` y `traceparent` (P-10). El `traceparent` tiene la forma `00-<32 hex>-<16 hex>-01`; los primeros 8 hex del `trace-id` son el prefijo de la corrida y el resto es al azar por solicitud. La cabecera y el prefijo se ponen en **un solo sitio** (un gancho del cliente), no en cada método.
  - `gateway`: `POST /api/intake/v1/intake/applications` con el token de `channel-simulator`.
  - `bff`: `GET /api/console/me`, `GET /api/console/cases`, `GET /api/console/cases/{id}`, `POST …/explanation-views`, `POST …/decision` y `POST /api/console/models/{id}/frozen-resolution`. Este último llama antes a `guard.check_reactivation` y exige un token de step-up; lo usará U12-T03.
  - Solicitudes y respuestas se construyen y se validan con `vectra_contracts` (`ApplicationIn`, `CaseRef`, `CaseDetail`, `DecisionIn`, `DecisionRef`). Una respuesta 2xx que no valida es un error, no un dato.
  - Un error es un `Problem`: el cliente expone `status`, `code` y `reason`. Nunca pone el `Authorization` en el mensaje.
- **`registry`.** `GET /v1/entries` con `entry_type`, `projection` (`metrics` o `monitoring_freezes`), `case_id`, `recorded_from`, `recorded_to`, `seq_after` y `limit`, paginando hasta agotar. Con el token de `verification-reader`. Devuelve `MetricsProjection` y `FreezeProjection` validados. Por `port-forward` a **un pod** del namespace `vectra-app`.
- **`prom` y `loki`.** Solo lectura: `/api/v1/query` y `/api/v1/query_range` de Prometheus; `/loki/api/v1/query_range` de Loki. Por `port-forward` a un pod de `vectra-observability`, sin credencial. Cada resultado devuelve también el texto de la consulta y su ventana, para que U12-T04 los guarde (NFR-U12-50).
- **`k8s_read`.** Cuatro funciones y ninguna más: `get`, `logs`, `auth_can_i` y `port_forward`. Sin una función genérica que reciba el verbo: la prueba de U12-T01 la rechaza (`fixtures/kubectl/prohibited/list_variable_verb.py`).
  - Cada orden se arma como lista de argumentos con el verbo literal. Sin `shell=True`.
  - `port_forward`: elige el pod con `kubectl get pods -l <selector> -o json` (listo y sin `deletionTimestamp`) y usa `pod/<nombre>`. Nunca `svc/…`. Pide un puerto local libre (`:<puerto remoto>`) y lee de la salida el que `kubectl` asignó. Es un gestor de contexto: el proceso muere al salir.
  - `port-forward` caído (P-8): error claro con el pod, el namespace y la causa. Sin reintento silencioso.
  - El ejecutor de procesos se inyecta. **Las pruebas nunca llaman al `kubectl` real**: en esta máquina hay un kubeconfig de kind que funciona.

**Paso 6 — Simulador** (BR-U12-01, 02; NFR-U12-10, 11, 50)

- **Lectura de U5** (P-5). Recibe la carpeta de la entrega de U5 (por omisión `reference-model/.out`). Lee `datasets/test.parquet` con `pyarrow` y `adversarial/manifest.json`. De cada fila toma las columnas de `ApplicationIn` y la valida con ese modelo, que es estricto (`strict` y `extra="forbid"`: `vectra_contracts/models/base.py`, línea 16; se valida desde JSON, no desde tipos de Python). La columna `default` no se envía. `generator_version` y `seed` salen del manifiesto adversarial. Registra también el tamaño de `test` y el SHA-256 del Parquet (NFR-U12-11). Una carpeta sin esos archivos es un error claro que dice cómo generarla.
- **Población para el `sampler`.** Una `sampler.Row` por fila: `id` = la posición de la fila en `test.parquet` (no un dato de la solicitud); `groups` y `band` con `derive_monitoring_labels(application, evaluated_on)`, con la fecha del reloj inyectado.
- **Escenarios.** `normal` → `sampler.normal(población, volumen, semilla)`. `stratified` → `sampler.stratified(…)`: el volumen es un piso (candidata de U12-T01), así que el simulador envía **todas** las filas devueltas y el informe dice cuántas fueron. Las celdas cortas (`short`) van en el resultado; negarse a correr es de la sección `rt2` (U12-T03). ~~`rt1` y `rt4`~~: diferidos; pedirlos es un error claro (`scenario_deferred`), sin solicitudes.
- **Envío.** `POST /api/intake/v1/intake/applications`, una `Idempotency-Key` nueva por solicitud (UUID4; cumple el patrón de U8) y `X-Test-Scenario`.
- **Ritmo.** Parámetro `rate`, 10/s por omisión y 30/s como máximo (el límite de U2). Un `rate` mayor de 30 es un error **antes** de enviar. El ritmo se cumple con el reloj inyectado: en cualquier ventana de 1 s hay como mucho `rate` solicitudes. El límite del gateway no tiene ráfaga.
- **Antes de enviar:** `guard.check_section` y, en la sección `decisions`, `guard.check_decisions(environment, clock.now(), volumen, rate)`. En staging, más de 100 casos se niega.
- **Respuestas.** 200 → `accepted` y su `case_id`. Cualquier otro estado → `rejected_by_code`, con el `code` del `Problem` o el estado HTTP. 429 y 503: ver P-8. El simulador **nunca** cambia el contenido de una solicitud para reenviarla.
- **`RunReport`** (domain-entities §2): `scenario`, `sent`, `accepted`, `rejected_by_code`, `case_ids`, `started_at` y `finished_at`. Lleva además `generator_version`, `seed` (el de U5), la semilla del muestreo, `rate` y el prefijo de la corrida. **Sin datos del solicitante:** ningún campo de `ApplicationIn` ni la posición de las filas.
- **Filas enviadas, aparte.** La lista de posiciones enviadas se devuelve **fuera** del `RunReport`, para que U12-T04 detecte «solicitudes repetidas entre escenarios» en el manifiesto (NFR-U12-11).

**Paso 6 — Conductor** (BR-U12-03; business-logic-model §2.2; NFR-U12-10, 50)

- **Tipos:** `DecisionMix` (`p_view`, `p_sigue`, `p_se_aparta`, `p_resuelve_revision`, `p_factors`, `seed`) y `DriverReport` (`cases_seen`, `decisions_by_kind`, `views`, `conflicts_409`, `invalid_422`, `started_at`, `finished_at`), de domain-entities §1 y §2. Semántica de la mezcla: P-6.
- **Mezcla pura.** Una función sin E/S: `(DecisionMix, detalle del caso, generador con semilla) → DecisionIn o «no decide»`, más si abre la explicación. Es lo que prueba PBT-U12-03. Azar con `random.Random(seed)`; nunca el generador global.
  - `decision` y `final_outcome` cumplen BR-U0-35 contra el `outcome` de la recomendación: con `revision_requerida`, solo `resuelve_revision`; con `favorable` o `desfavorable`, `sigue` (mismo resultado) o `se_aparta` (el contrario).
  - `used_factors`: con probabilidad `p_factors`, una muestra sin repetición de 1 a 20 `feature_id` del `shap_vector` del caso; si no, exactamente `["ninguno"]`.
  - `justification`: texto de prueba de 20 a 2 000 caracteres en `se_aparta` y `resuelve_revision`; en `sigue` puede ir vacía (BR-U0-36).
- **Recorrido.** Login de `analista-1` y de `analista-2`. Los casos se reparten entre los dos de forma determinista. Por cada caso `listo` de la bandeja: `get_case`; con probabilidad `p_view`, `record_explanation_view`; después `record_decision`.
- **409 y 422.** Se cuentan (`conflicts_409`, `invalid_422`) y el conductor sigue con el caso siguiente. **Nunca** se reintenta con otro contenido. El 409 puede venir de la regla de objeto del BFF o de U8; el ejemplo del plan (`decision_already_recorded`) es el `reason` de un `Problem` con `code = conflict_state`.
- **Ritmo.** El gateway limita `/api/console` a 20/s por usuario. El conductor espacia sus solicitudes con el reloj inyectado, por debajo de ese límite.
- **401.** Renueva el token **una vez** y repite la misma solicitud, con el mismo contenido. Un segundo 401 es un error.
- **Sin datos del solicitante** en el `DriverReport`: solo `case_id` y conteos.

**Volumen de demostración** (BR-U12-06)

- Una función compone la sección `decisions`: simulador `normal` con **2 000** casos y después el conductor sobre los `case_ids` del `RunReport`. Devuelve los dos informes y un registro con **el número enviado y el decidido**, que U12-T04 escribirá en el manifiesto (`manifest.py` sigue vacío). Los primeros 1 000 `case_ids`, en orden de envío, quedan identificados para `CASE-SIZE`.
- 2 000 es una constante con nombre. En staging la barrera lo baja a 100.
- «Con el modelo de referencia activo y antes de RT-2» es el orden de la CLI (Paso 13, U12-T04) y del operador (Paso 18). Aquí queda escrito en el docstring y en `clients.md`.
- La prueba no corre contra nada real: dobles en proceso y reloj falso (CA-17).

**Plan.** Marca `[x]` los Pasos 5 y 6 con `(U12-T02)`; en el 6, la nota «escenarios `rt1` y `rt4` diferidos por la demo».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Los escenarios `rt1` y `rt4` del simulador.** Recorte E\*F: enmienda §3, U12, fila «6»: «Se difieren los escenarios `rt1` y `rt4`»; §0, punto 2: «En U12: RT-1/RT-4 en el simulador»; §1.5, fila U12. No se leen los pares RT-1 ni los 18 casos RT-4 del manifiesto adversarial.
- **Bloques D a H de U12** (Pasos 7 a 19): oráculos y secciones (`rt2`, `rt2-setup`, `rt3`, `rt5`, `SIM-NORMAL`), `manifest`, `cli`, demos, imagen, workflow, README y la verificación en kind. `manifest.py`, `cli.py`, `scenarios/` y `load/` siguen vacíos.
- **Escribir evidencias en disco.** Es del Paso 13. Aquí solo se garantiza que lo que estos módulos devuelven pasa por `evidence.prepare` sin fallar.
- **`mutmut`** (diferido en U12-T01) y **el workflow de CI** (Paso 16, D).
- **Editar otras unidades.** Si algo de U2, U3, U5, U8 o U10 no encaja, se reporta como candidata. En particular: no se agrega una ruta al gateway, no se toca el realm y no se cambia `e2e_support.py`.
- **Cualquier llamada a un clúster.** Nada de `kubectl`, `helm`, `argocd`, ni solicitudes a `vectra.localtest.me`. El kind de esta máquina está arriba: no se usa.
- **Instalar navegadores con privilegios.** Nada de `sudo` ni de `playwright install --with-deps`.
- **Generar la entrega completa de U5** (`make -C reference-model release`): entrena modelos y es pesada. Las pruebas usan un Parquet pequeño del generador real.

---

## Candidatas (`CANDIDATAS.md`)

**Se atienden aquí:**

| Dónde | Candidata | Qué se hace |
|---|---|---|
| Rama de U12-T01, última entrada | `guard.check_decisions` rechaza un reloj sin zona: «U12-T02 debe inyectar un reloj con zona» | El reloj inyectable siempre devuelve UTC con zona (CA-13) |
| Rama de U12-T01 | `sampler.stratified`: el volumen es un piso | El simulador envía todas las filas devueltas e informa cuántas (CA-12) |
| Rama de U12-T01 | El ≥ 85 % del resto del paquete: «con el recorte nadie lo comprueba» | CA-18 lo corre y entra en `make check` |
| `main`, línea 333 | 4 de las 65 celdas de U9 no llegan a 30 | El resultado de `stratified` lleva las celdas cortas; decidir es de U12-T03 (P-8 de U12-T01) |
| `main`, línea 44 | Verificar con un login real que Keycloak lee la semilla TOTP en Base32 y que config-cli aplica las credenciales | CA-3 lo ejerce con Keycloak y config-cli reales en Testcontainers. Sigue abierta para kind |
| `main`, línea 525 | Contenedores de Testcontainers huérfanos | CA-21 y «Restricciones del entorno» |
| `main`, líneas 562 y 566 | Puertos fijos 8080 y 8081 de `test_service_shutdown.py` de otras unidades | Esta tarea nunca los usa: puertos al azar y transportes en proceso |
| `main`, líneas 428, 444 y 549 | Semilla impresa también en verde; paquetes de prueba sin colisión | PBT-U12-03 con el `conftest.py` de U12-T01; sin `__init__.py` en `tests/` |
| `main`, líneas 415 y 531; 183 y 272 | `test_traceability.py` no lee `.importlinter` ni reconoce las BR en párrafos | Identificadores en `.py`; tabla BR-U12-01..03 → prueba en `clients.md` |

**Para una tarea posterior de U12** (no las atiendas):

- `main`, líneas 568, 577 y 607: `/callback` y la redirección bajo la CSP real de U2. El login de U12 **no** carga `/callback` (lo intercepta), así que no las prueba: son del ensayo de las demos (U12-T05).
- `main`, línea 572: `channel: "chromium"` frente a `chromium_headless_shell`. El login de U12 no abre ventanas emergentes: le sirve cualquiera de los dos (P-9).
- `main`, línea 122: `playwright install chromium` y la CA del gateway para el Paso 16 de U2 (U12-T05).
- Rama de U12-T01: K16 y la bóveda de kind (cómo llega la estación a `vault.vault.svc:8200`). Antes del Paso 18.
- `main`, línea 207 (marcadores de `LOGS-NO-PII`), 251 (caso bidi de RT-1) y 252 (variante proxy): Pasos 10 y 7, diferidos, y U12-T03.
- `main`, línea 601: `TMPDIR` y `make -C platform check`. Esta tarea no corre el `check` de U1.

---

## Preguntas abiertas

**P-1 necesita la decisión del usuario antes de despachar.** Las demás no: si nadie responde, rige la recomendación y el codificador la anota en `clients.md`.

- **P-1 — Keycloak de Testcontainers con el realm de kind (necesita al usuario).** El plan lo exige y el repositorio no tiene patrón. Hay tres cosas que decidir.
  - *Costo.* Las imágenes no están en el Docker local ni en `kind-registry`: hay que bajar Keycloak 26.8.1 de `quay.io` y keycloak-config-cli de Docker Hub (≈ 0,7 GB entre las dos). Keycloak ocupa ≈ 1 GiB de RAM. Al redactar había 2 GiB disponibles de 14, con kind arriba.
  - *Cómo se aplica el realm.* (a) **Recomendada.** Con keycloak-config-cli, como en kind: mismo YAML, misma sustitución de variables. (b) La prueba sustituye las variables, pasa el YAML a JSON y arranca Keycloak con `--import-realm`. Es más barata, pero no es el camino de kind y puede diferir en flujos y credenciales.
  - *Con qué nombre de host.* (a) **Recomendada.** El host real: `KC_HOSTNAME=https://vectra.localtest.me/auth` y `PUBLIC_HOSTNAME=vectra.localtest.me`. Chromium llega al contenedor con `--host-resolver-rules` y `httpx` con un transporte que redirige la conexión. Así se prueban el `issuer` de `guard.KIND` y los `redirect_uri` registrados tal como son. **Riesgo:** `vectra.localtest.me:443` es el kind de esta máquina. Si el desvío falla, el formulario se enviaría al Keycloak de kind con contraseñas equivocadas, y cinco fallos bloquean al usuario para siempre. Mitigación obligatoria: confianza solo en el certificado de la prueba (P-2), de modo que una conexión a kind falle antes de mostrar el formulario; y una comprobación previa que aborta la sesión si el certificado no es el de la prueba. (b) Host dinámico (`127.0.0.1:<puerto>`), con un `Environment` de prueba. No tiene ese riesgo, pero el `issuer` y los `redirect_uri` ya no son los de kind; habría que atarlos con una prueba unitaria contra `realm.kind.yaml` y `gateway/values/kind.yaml`.
  - Si la opción recomendada no funciona en una prueba de concepto de 1 h, el codificador pasa a (b) en lo que falle y lo anota. Si el usuario no autoriza bajar las imágenes, la tarea no puede cumplir la aceptación del plan y hay que decidir qué la reemplaza.
- **P-2 — Cómo confía Chromium en la CA.** deployment-architecture §2b dice que el certificado raíz entra como archivo de solo lectura, pero Chromium no lee un archivo PEM. Vale para kind, para staging y para la prueba.
  - (a) **Recomendada.** `--ignore-certificate-errors-spki-list` con la huella de la llave pública del certificado del servidor, que la herramienta obtiene por una conexión TLS **verificada** con la CA del entorno. Chromium solo acepta ese certificado.
  - (b) Una base NSS temporal con `certutil`. Exige `libnss3-tools` en la imagen (Paso 15).
  - (c) `ignore_https_errors` en el contexto del navegador. Es lo más simple, pero la contraseña y el TOTP se escribirían en una página sin verificar. Solo como último recurso, nunca en la prueba con el host real (riesgo de P-1), y con una candidata para U12-T04.
- **P-3 — Dobles frente a servicios reales en el Paso 6.**
  - (a) **Recomendada.** `test_simulator.py` contra la app real de `case-service` en proceso, con PostgreSQL de Testcontainers y un envoltorio mínimo que hace de gateway (la reescritura de ruta y el `azp`). `test_driver.py` contra la app real del BFF en proceso con los dobles de U10. Los casos que necesitan fallos inyectados (429, 503, latencia, 2 000 casos) usan un doble ligero, que una prueba valida contra `contracts/openapi/case-service.yaml` y `console-bff.yaml`.
  - (b) Encadenar BFF real → `case-service` real → PostgreSQL también para el conductor. Más fiel y más lento; solo si (a) sobra de tiempo.
  - (c) Solo dobles escritos a mano. Es lo que la lección prohíbe.
- **P-4 — Módulos que §1 del plan no tiene.** El login no cabe en ninguno de los seis clientes de §1, y el reloj lo usan tres módulos.
  - (a) **Recomendada.** `clients/oidc.py` y `clock.py`, nuevos.
  - (b) El login dentro de `clients/bff.py` y el reloj dentro de `guard.py`. No cambia §1, pero mezcla responsabilidades y `gateway` y `registry` también piden tokens.
- **P-5 — Cómo lee U12 la entrega de U5.** `reference-model/.out/` no se versiona y el Parquet no guarda `generator_version` ni `seed`.
  - (a) **Recomendada.** Dependencia directa de `pyarrow` (ya está en el lock). La carpeta es un parámetro. `generator_version` y `seed` se leen de `adversarial/manifest.json` de la misma carpeta, y se registran con el SHA-256 de `test.parquet`.
  - (b) Depender de `vectra-reference`. Arrastra `numpy`, `pandas` y el entrenamiento a la imagen de U12.
  - (c) Leer `generator_version` y `seed` de `reference-model/config/generator.yaml`. Dice con qué configuración se **generaría**, no con cuál se generó la carpeta.
- **P-6 — Semántica de `DecisionMix`.** BR-U0-35 solo admite `resuelve_revision` cuando el `outcome` es `revision_requerida`, y solo entonces. Tres probabilidades que suman 1 no tienen sentido en un mismo caso.
  - (a) **Recomendada.** Para `favorable` o `desfavorable`: `sigue` con probabilidad `p_sigue / (p_sigue + p_se_aparta)`; si no, `se_aparta`. Para `revision_requerida`: con probabilidad `p_resuelve_revision` decide `resuelve_revision` (con `final_outcome` al azar entre los dos, con la semilla); si no, **no decide** y el caso se cuenta como visto. En la sección `decisions` vale 1. PBT-U12-03 comprueba la convergencia por estrato de `outcome`.
  - (b) `p_resuelve_revision` es la probabilidad de `final_outcome = favorable` al resolver. Entonces todo caso se decide siempre.
- **P-7 — Token de 300 s en una corrida larga.**
  - (a) **Recomendada.** `refresh_token` rotativo en memoria, renovado antes de vencer; si el refresco falla, **un** login nuevo.
  - (b) Un login nuevo cada ≈ 4 min. Más logins, más esperas de TOTP y más carga en `auth-login`.
- **P-8 — Reintentos.** El diseño no dice qué hacer ante un 429 o un 503 del gateway. Y la aceptación del plan («sin reintento silencioso») y INF-U12-03 («elige otro y reintenta la lectura») no dicen lo mismo del `port-forward`.
  - (a) **Recomendada.** Simulador y conductor: ante 429 o 503 con `Retry-After`, reenvían **la misma solicitud** (misma `Idempotency-Key`, mismo cuerpo) hasta 3 veces, y el informe cuenta los reenvíos. Sin eso, un solo 429 deja `accepted < sent` y `SIM-NORMAL` falla. `port-forward`: **una** nueva elección de pod, registrada en el resultado (pods usados e intentos); si vuelve a caer, error claro.
  - (b) Nunca reintentar nada: contar y seguir. Es la lectura literal de la aceptación.
- **P-9 — Navegador de Playwright.**
  - (a) **Recomendada.** Reusar `~/.cache/ms-playwright` (revisión 1248, la que espera Playwright de Python 1.64.0). No se instala nada. CA-2 lo comprueba.
  - (b) Si CA-2 falla porque la revisión no coincide: `uv run playwright install chromium`, sin `sudo` y sin `--with-deps`. Agrega una carpeta a la caché compartida y no borra las demás. Se anota en la bitácora.
- **P-10 — Valor de la cabecera y del prefijo.** El diseño no los fija.
  - (a) **Recomendada.** El prefijo de la corrida son 8 hex que recibe el cliente (U12-T04 los derivará del `runId`). `X-Test-Scenario: <escenario>.<prefijo>` (por ejemplo, `normal.3fa9c2d1`), que cumple el patrón de U8.
  - (b) Solo el nombre del escenario en la cabecera. No distingue dos corridas.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloque C, y los Pasos 8, 10, 13 y 15, que usan lo de esta tarea)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1, §2, §3 U12, §5.2, §8) y `demo-kind-alcance.md` (§3 U12, §6)
- `DECISIONES-LOOP.md` (§6 y §9)
- `aidlc-docs/construction/system-verification/functional-design/business-rules.md` (BR-U12-01, 02, 03 y 06), `business-logic-model.md` (§2.2 y §3: PBT-U12-03 y pruebas de ejemplo) y `domain-entities.md` (§1 y §2)
- `aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements.md` (NFR-U12-02, 03, 04, 05, 10, 11, 32, 40, 50) y `tech-stack-decisions.md`
- `aidlc-docs/construction/system-verification/infrastructure-design/infrastructure-design.md` (INF-U12-01 y 03) y `deployment-architecture.md` (§2b)
- `tareas/U12-T01-esqueleto-y-logica-pura.md`, `bitacoras/U12-T01.md` y `aidlc-docs/construction/system-verification/code/logic.md`
- Los archivos de «Depende de»
- `console/bff/tests/doubles/` (`bff_e2e_server.py`, `bff_doubles.py`, `bff_world.py`, `bff_tokens.py`) y `case-management/tests/doubles/u8_support.py`
- `CANDIDATAS.md`: las líneas citadas en «Candidatas»

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Los comandos del plan abrevian rutas; aquí van completas. Ningún criterio admite pruebas omitidas ni `xfail`: sin Docker o sin Chromium, la prueba **falla**.

- [ ] **CA-1** — Dependencias, estructura y contratos de imports (Paso 5; NFR-U12-01).
  ```bash
  uv sync --frozen && uv run lint-imports --config system-verification/.importlinter && cd system-verification && for p in src/vectra_verification/clients/oidc.py src/vectra_verification/clients/gateway.py src/vectra_verification/clients/bff.py src/vectra_verification/clients/registry.py src/vectra_verification/clients/prom.py src/vectra_verification/clients/loki.py src/vectra_verification/clients/k8s_read.py tests/integration/test_oidc_headless.py tests/integration/test_clients.py tests/integration/test_simulator.py tests/integration/test_driver.py tests/property/test_driver_mix.py; do test -s "$p" || echo "FALTA $p"; done; test ! -e Dockerfile && test ! -e chart && ! find tests -name __init__.py | grep -q . && ! grep -rqE "vectra[-_]common" pyproject.toml src && echo OK
  ```
  Esperado: `Contracts: N kept, 0 broken.`, con los contratos nuevos de «Precisiones»; ninguna línea `FALTA`; `OK`. **Rojo primero:** un `import playwright` en `simulator.py`, un `import subprocess` en `clients/registry.py` y un `import jwt` en `sampler.py` rompen cada uno su contrato; regístralo.

- [ ] **CA-2** — Chromium sin interfaz disponible, sin instalar nada y sin `--no-sandbox` (Paso 5; P-9).
  ```bash
  uv run python -c "from playwright.sync_api import sync_playwright as sp; p = sp().start(); b = p.chromium.launch(headless=True); print(b.version); b.close(); p.stop()" && ! grep -rnE -- "--no-sandbox|storage_state|record_video|record_har|tracing\.start|screenshot\(" system-verification/src; echo "limpio=$?"
  ```
  Esperado: imprime la versión de Chromium (156.x con la revisión 1248) y `limpio=0`. Si el arranque falla por la revisión, aplica P-9 (b) y anótalo.

- [ ] **CA-3** — Login y step-up sin navegador visible contra Keycloak real (Paso 5, «Aceptación del login»; INF-U12-03; NFR-U12-04; BR-U12-03).
  ```bash
  uptime; time uv run pytest system-verification/tests/integration/test_oidc_headless.py -v; uptime
  ```
  Esperado: pasan, cada uno con su nombre, contra un Keycloak de Testcontainers con el realm de kind (según P-1):
  - login de `analista-1` → token con su rol: `roles` contiene `analista`, `azp = vectra-console`, `aud` contiene `console-bff`, `iss` es el del entorno y `acr = mfa`;
  - step-up de `cumplimiento-1` → `acr = mfa` y `auth_time` reciente (≤ 900 s, y posterior al inicio de la prueba), con `redirect_uri` `/stepup-callback`;
  - un `state` alterado en la URL de retorno → error sin canje: el endpoint de token recibe **0** solicitudes;
  - un `nonce` que no coincide → error y ningún token queda en memoria;
  - ningún token ni contraseña en disco: con el directorio de trabajo, `HOME` y `TMPDIR` en una carpeta de la prueba, después del login y **antes** de cerrar el navegador ningún archivo contiene la contraseña, la semilla, un token ni un JWT (se busca también en el perfil temporal de Chromium);
  - el contexto de Playwright queda cerrado tras cada login, también tras uno fallido;
  - la navegación al `redirect_uri` se aborta: 0 solicitudes salen hacia `/callback` y `/stepup-callback`;
  - **reuso de TOTP:** dos logins seguidos del mismo usuario → el segundo espera a la ventana siguiente y pasa. Y `cumplimiento-1` hace login y step-up seguidos, como en RT-2;
  - refresco: el token renovado es válido y el cliente guarda el refresh token nuevo;
  - `client_credentials` de `verification-reader` → token con los dos scopes y `aud = decision-registry-service`; de `channel-simulator` → `scope` con `intake:submit` y `azp = channel-simulator`;
  - las credenciales llegan por `Credentials` y el doble de la bóveda, no por variables de la prueba.

  **Rojo primero** (regístralos): sin la espera de la ventana, el segundo login lo rechaza **Keycloak** (no un doble); con `client_id` distinto de `vectra-console` o un `redirect_uri` no registrado, Keycloak no entrega el formulario; sin pedir los scopes, el token de `verification-reader` no trae `aud`. Tiempo esperado: menos de 5 min con la máquina cargada, la mayor parte en arrancar Keycloak. Es una estimación: anota el real.

- [ ] **CA-4** — El flujo OIDC sin Keycloak, con reloj falso (Paso 5).
  ```bash
  uv run pytest system-verification/tests/unit/test_oidc_flow.py -v
  ```
  Esperado: pasan:
  - la URL de autorización lleva `state`, `nonce`, `code_challenge` (S256 del `code_verifier`; un vector conocido de RFC 7636) y, en el step-up, `prompt=login`, `max_age=0` y `acr_values=mfa`;
  - con `guard.KIND`, el endpoint y los dos `redirect_uri` son los de `realm.kind.yaml` y `identity-edge/gateway/values/kind.yaml` (la prueba lee los dos archivos);
  - `state`, `nonce` y `code_verifier` cambian en cada login;
  - `state` distinto → 0 llamadas al transporte que cuenta;
  - ID token con `acr = pwd`, con `aud` ajeno, vencido o firmado con otra llave → error;
  - un token con el `iss` de producción → `GuardError` y no se usa;
  - step-up con `auth_time` de hace 901 s → error; de hace 900 s → pasa;
  - ventana TOTP: mismo usuario en la misma ventana → el reloj falso avanza hasta la siguiente, sin `sleep` real; otro usuario → no espera; el código usado es el de la ventana nueva;
  - un login fallido **no** se reintenta: una sola pasada por el formulario.

  **Rojo primero:** canjear antes de comparar `state` hace que el transporte cuente 1; regístralo.

- [ ] **CA-5** — Los tokens no quedan en disco ni en evidencias (Paso 5; NFR-U12-04, 05).
  ```bash
  uv run pytest system-verification/tests/unit/test_tokens_not_leaked.py -v && ! grep -rnE "write_text|write_bytes|tempfile|open\([^)]*['\"][wax]" system-verification/src/vectra_verification/clients system-verification/src/vectra_verification/simulator.py system-verification/src/vectra_verification/driver.py; echo "sin_escritura=$?"
  ```
  Esperado: código 0 y `sin_escritura=0`. Pasan:
  - `repr()` y `str()` del conjunto de tokens no muestran ninguno;
  - la respuesta completa del endpoint de token, un volcado de las cabeceras de una solicitud al BFF y el formulario del `client_assertion`, pasados por `evidence.prepare` (el filtro de U12-T01, con `Credentials.secret_values()`), salen sin tokens y sin fallar;
  - el mismo volcado **sin** filtrar → `ensure_clean` falla: la prueba demuestra que había un JWT;
  - los mensajes de todas las excepciones de `clients/` y los registros de log de una corrida con errores (401, 403, 500, tiempo agotado, `state` alterado) no contienen el token, la contraseña, el TOTP, el `code` ni el `code_verifier`;
  - `RunReport` y `DriverReport`, serializados, pasan `evidence.prepare` sin cambios.

  **Rojo primero:** poner la URL de retorno completa en el mensaje del error de `state` hace fallar el caso del `code`; regístralo.

- [ ] **CA-6** — El filtro de U12-T01 sigue verde con lo que esta tarea toque de `evidence.py`.
  ```bash
  uv run pytest system-verification/tests/unit/test_evidence_filter.py system-verification/tests/unit/test_guard.py system-verification/tests/unit/test_credentials.py
  ```
  Esperado: código 0, los mismos casos que en `main` más los que agregues. Si amplías el filtro (por ejemplo, `code_verifier` u `otp`), **no** agregues `code`: es el nombre del campo de `Problem` y borraría el código de error de las evidencias. Una prueba lo fija: `{"code": "conflict_state"}` sale sin cambios.

- [ ] **CA-7** — Clientes con dobles (Paso 5, «Aceptación»; INF-U12-03; NFR-U12-02, 50).
  ```bash
  uv run pytest system-verification/tests/integration/test_clients.py -v
  ```
  Esperado: pasan:
  - **cada** solicitud de `gateway` y de `bff` lleva la cabecera y el prefijo: la prueba recorre todos los métodos públicos de los dos clientes y falla si aparece uno nuevo sin cubrir. `X-Test-Scenario` cumple el patrón de U8 y el `traceparent` cumple `^00-[0-9a-f]{32}-[0-9a-f]{16}-01$` con el prefijo de la corrida;
  - el cliente del registro manda el token de `verification-reader` como `Bearer`, y sus parámetros de consulta son nombres que existen en `GET /v1/entries` de `contracts/openapi/decision-registry-service.yaml` (la prueba lee el OpenAPI);
  - `projection=metrics` y `projection=monitoring_freezes` devuelven `MetricsProjection` y `FreezeProjection` válidos; una respuesta que no valida → error; la paginación se agota;
  - un `port-forward` caído → error claro, sin reintento silencioso: el doble de `kubectl` cuenta los intentos y el error nombra el pod y el namespace (según P-8);
  - el reenvío usa `pod/<nombre>` y **nunca** `svc/`: la prueba mira los argumentos que recibió el doble de `kubectl`. El pod se elige con `get pods -l …`, listo y sin `deletionTimestamp`; sin pods listos → error claro;
  - el puerto local lo asigna `kubectl`; el cliente no pide 8080, 8081 ni ningún puerto fijo;
  - el proceso del `port-forward` muere al salir del contexto, también con una excepción;
  - `prom`: `query` y `query_range` con `start`, `end` y `step`; `loki`: `query_range`. Cada resultado trae el texto de la consulta y su ventana. Un `status: error` → error;
  - `bff.resolve_frozen` fuera de la sección `rt2` → `GuardError` y 0 solicitudes;
  - host de producción → 0 solicitudes (la barrera de U12-T01).

  **Rojo primero:** poner la cabecera en cada método, y olvidarla en uno, hace fallar el primer caso; cambiar `pod/` por `svc/` hace fallar el quinto. Regístralos.

- [ ] **CA-8** — El doble ligero del gateway y del BFF se parece al contrato (lección de la enmienda §8).
  ```bash
  uv run pytest system-verification/tests/integration/test_clients.py -v -k "contract or openapi"
  ```
  Esperado: pasan los casos que validan los dobles escritos a mano contra `contracts/openapi/case-service.yaml` y `console-bff.yaml`: cada ruta y método que el doble sirve existe en el OpenAPI; cada cuerpo 2xx que devuelve valida contra el esquema de esa respuesta; cada error es un `Problem` válido. Un doble con una ruta que no está en el contrato, o con un campo de más, hace fallar la prueba. **Rojo primero:** devolver 201 en la ingesta (el contrato dice 200) falla; regístralo.

- [ ] **CA-9** — `k8s_read` solo con los 4 verbos (Paso 5; NFR-U12-43; INF-U12-02).
  ```bash
  uv run pytest system-verification/tests/unit/test_kubectl_verbs.py system-verification/tests/unit/test_k8s_read.py -v && git diff origin/main...HEAD --stat -- system-verification/tests/unit/test_kubectl_verbs.py system-verification/tests/fixtures/kubectl
  ```
  Esperado: código 0. La prueba de verbos de U12-T01 sigue verde y su detector **no cambia** (el `--stat` no lista `test_kubectl_verbs.py`, o solo muestra casos agregados). `test_k8s_read.py` comprueba:
  - `clients/k8s_read.py` está entre los archivos que recorre `scan_tree` y contiene invocaciones de `kubectl` (la prueba no pasa en vacío);
  - el módulo expone solo `get`, `logs`, `auth_can_i` y `port_forward`;
  - las órdenes armadas son exactamente `kubectl … get`, `… logs`, `… auth can-i` y `… port-forward`, con `-n <namespace>` y sin `shell=True`;
  - ninguna prueba ejecuta el `kubectl` real: el ejecutor es un doble y `PATH` no lo alcanza.

  **Rojo primero:** agrega a `k8s_read.py` una lista con `kubectl` y `delete`; `test_real_files_have_no_findings` debe fallar y nombrar el archivo. Regístralo y quítala.

- [ ] **CA-10** — Lectura de la entrega de U5 (Paso 6; BR-U12-01; NFR-U12-10, 11).
  ```bash
  uv run pytest system-verification/tests/unit/test_u5_reader.py -v
  ```
  Esperado: pasan, con un `test.parquet` pequeño producido en la prueba por el generador real de U5 (`vectra_reference.generate.generate` con `with_overrides(config, n_rows=…)`) y un `adversarial/manifest.json` mínimo con la forma de `write_adversarial`:
  - cada fila leída valida como `ApplicationIn`; la columna `default` no llega a la solicitud;
  - `generator_version` y `seed` son los del manifiesto; quedan el tamaño de `test` y el SHA-256 del Parquet;
  - las etiquetas de cada fila son iguales a las de `vectra_reference.proxy.monitoring_labels` (el cálculo con el que U5 midió el congelamiento);
  - `Row.id` es la posición de la fila, no un campo de la solicitud;
  - carpeta ausente, sin `test.parquet` o sin manifiesto → error claro que nombra `make -C reference-model release`;
  - pedir el escenario `rt1` o `rt4` → `scenario_deferred` y 0 solicitudes.

- [ ] **CA-11** — El simulador contra `case-service` real (Paso 6; BR-U12-02; lección de la enmienda §8; P-3).
  ```bash
  uv run pytest system-verification/tests/integration/test_simulator.py -v -k real
  ```
  Esperado: pasan, con la app de `case-service` en proceso sobre PostgreSQL de Testcontainers y `allow_test_scenarios = true`:
  - 20 solicitudes `normal` del Parquet de CA-10 → `accepted = sent = 20`, 20 `case_id` distintos, y en la base hay 20 casos con su `test_scenario_id`;
  - con el `azp` de otro cliente, U8 responde 422 y el `RunReport` lo cuenta en `rejected_by_code` (no es una excepción);
  - una `Idempotency-Key` que U8 rechazaría no se genera nunca: las 20 claves cumplen el patrón de `intake.py`.

  **Rojo primero:** enviar las columnas del Parquet sin quitar `default` hace que U8 rechace las 20 (`ApplicationIn` es estricto); regístralo. Un doble escrito a mano no lo habría visto.

- [ ] **CA-12** — El simulador: ritmo, claves, informe y semillas (Paso 6, «Aceptación»; BR-U12-01, 02; NFR-U12-10, 50; PBT-10).
  ```bash
  uv run pytest system-verification/tests/integration/test_simulator.py -v
  ```
  Esperado: pasan, además de los de CA-11:
  - **el simulador nunca supera 30/s**, medido con el reloj inyectado: con `rate = 30` y 300 solicitudes, en toda ventana de 1 s del reloj falso hay ≤ 30 envíos; con `rate = 10`, ≤ 10; la prueba no duerme (termina en segundos de reloj real);
  - `rate = 31` → error y **0** solicitudes;
  - **claves distintas:** N solicitudes → N `Idempotency-Key` distintas, también entre dos corridas con la misma semilla;
  - **el `RunReport` sin identificadores:** sus campos son los de domain-entities §2 más los de «Precisiones»; serializado, no contiene ningún valor de `full_name`, `document_number`, `phone`, `email`, `address` ni `broker_id` de las filas enviadas, ni sus posiciones;
  - `generator_version` y `seed` de U5 y la semilla del muestreo quedan registrados; misma semilla → mismas filas en el mismo orden; otra semilla → otras;
  - `normal` usa `sampler.normal`, y `stratified`, `sampler.stratified`: envía todas las filas devueltas (el volumen es un piso) y el resultado trae las celdas cortas;
  - `rejected_by_code` agrupa por código; `accepted + Σ rejected = sent`;
  - 429 y 503 según P-8: el reenvío lleva la **misma** clave y el **mismo** cuerpo, y se cuenta;
  - cada solicitud lleva `X-Test-Scenario` y el prefijo en el `traceparent`;
  - las posiciones enviadas se devuelven aparte del `RunReport`.

  **Rojo primero:** un ritmo que duerme `1 / rate` **después** de cada lote de `rate` envíos deja 2 × `rate` en una ventana que cruza dos lotes; la prueba de ventana deslizante debe matarlo. Regístralo.

- [ ] **CA-13** — La barrera horaria recibe un reloj con zona (candidata de U12-T01; NFR-U12-32).
  ```bash
  uv run pytest system-verification/tests/integration/test_simulator.py system-verification/tests/integration/test_decisions_volume.py -v -k "clock or guard"
  ```
  Esperado: pasan: con el reloj falso a las 22:30 UTC, `decisions` se niega **antes** de la primera solicitud (0 envíos); a las 10:00 UTC empieza; el reloj real del módulo devuelve una hora con zona UTC; en staging, 101 casos → se niega. **Rojo primero:** un reloj que devuelve `datetime.utcnow()` (sin zona) da `clock_without_timezone`; regístralo.

- [ ] **CA-14** — El conductor contra el BFF real (Paso 6, «Aceptación»; BR-U12-03; P-3).
  ```bash
  uv run pytest system-verification/tests/integration/test_driver.py -v
  ```
  Esperado: pasan, con la app real del BFF en proceso (`console_bff.app.build`) y los dobles de U10 en sus destinos:
  - **el conductor ante un 409 `decision_already_recorded` sigue con el caso siguiente:** `conflicts_409 = 1`, el caso siguiente se decide, y ese caso recibió **un** solo `POST …/decision`;
  - un 409 de la regla de objeto del BFF (caso que ya no está `listo`) se cuenta igual;
  - un 422 → `invalid_422 = 1`, **un** solo `POST` para ese caso, sin segundo intento con otro contenido;
  - usa `analista-1` y `analista-2`: los dos `sub` aparecen en las solicitudes y el reparto de casos es determinista;
  - por cada caso: `GET` del detalle, la consulta de la explicación según `p_view` (`p_view = 1` → una por caso; `p_view = 0` → ninguna) y después la decisión; `views` las cuenta;
  - el cuerpo de cada decisión pasa la validación del BFF real (un cuerpo mal formado sería un 422 inesperado: 0 en la corrida base);
  - un rol que no es `analista` → 403, contado como error, no como decisión;
  - un 401 → un refresco y la misma solicitud; un segundo 401 → error;
  - el ritmo por usuario no pasa de 20/s en el reloj falso;
  - `DriverReport` con los campos de domain-entities §2, sin datos del solicitante;
  - cada solicitud lleva la cabecera y el prefijo.

  **Rojo primero:** ante un 422, reenviar con `used_factors = ["ninguno"]` hace que el doble cuente 2 `POST`; regístralo.

- [ ] **CA-15** — PBT-U12-03, la mezcla del conductor (Paso 6; BR-U12-03; NFR-U12-10, 41).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_driver_mix.py -v
  ```
  **Propiedad:** para toda `DecisionMix`, las decisiones generadas cumplen BR-U0-35 y 36 y BR-U8-16 (opciones según el `outcome`, justificación en rango, factores ⊆ `shap_vector` o exactamente `["ninguno"]`); con N grande, las proporciones convergen a las de la mezcla.
  **Generadores:** mezclas y casos generados con todos los `outcome`. En concreto: `DecisionMix` con probabilidades en [0, 1], incluidos los extremos 0 y 1, y semillas generadas; casos con `outcome` `favorable`, `desfavorable` y `revision_requerida`; `shap_vector` de 1 a 40 `feature_id` distintos (más de 20, para probar el tope de 20 de `check_used_factors`).
  Esperado: todo pasa; el encabezado muestra el perfil `ci` y la semilla. Una prueba por cada parte:
  - **validez:** toda decisión generada pasa `DecisionIn.model_validate`, `decision_is_coherent` (U0) y `validate_decision` de U8 (`vectra_case.decision`) contra la recomendación del caso. El oráculo son esos validadores reales, no una copia;
  - con `revision_requerida` nunca sale `sigue` ni `se_aparta`; sin ella nunca sale `resuelve_revision`;
  - `used_factors` ⊆ `feature_id` del `shap_vector`, sin repetidos, de 1 a 20; o exactamente `["ninguno"]`, nunca mezclado;
  - justificación de 20 a 2 000 caracteres (sin contar espacios de los extremos) en `se_aparta` y `resuelve_revision`;
  - **determinismo:** misma mezcla, misma semilla y mismos casos → mismas decisiones (NFR-U12-10);
  - **convergencia:** con N ≥ 5 000 casos por estrato de `outcome`, la proporción observada de cada clase (`sigue` frente a `se_aparta`, consulta de la explicación, factores frente a «Ninguno», y lo que fije P-6) queda dentro de una tolerancia declarada en la prueba (por ejemplo, 4 desviaciones estándar de la binomial). Con probabilidad 0 → ninguna; con 1 → todas.

  **Rojo primero:** elegir `se_aparta` con `final_outcome` igual al `outcome`, o muestrear factores de una lista fija en vez del `shap_vector` del caso, hace fallar la validez; usar el generador global hace fallar el determinismo. Regístralos (con el perfil `dev` para los rojos: `CANDIDATAS.md`, U11-T02).

- [ ] **CA-16** — El comando completo del Paso 6, como en el plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_driver_mix.py system-verification/tests/integration/test_simulator.py system-verification/tests/integration/test_driver.py
  ```
  Esperado: código 0, sin omitidas ni `xfail`.

- [ ] **CA-17** — Volumen de demostración de 2 000, sin correrlo de verdad (Paso 6; BR-U12-06).
  ```bash
  uptime; time uv run pytest system-verification/tests/integration/test_decisions_volume.py -v; uptime
  ```
  Esperado: pasan, con dobles en proceso (los validados en CA-8) y reloj falso:
  - la sección `decisions` envía **2 000** casos `normal` y el conductor los decide: `RunReport.sent = 2000`, y el registro para el manifiesto trae el número enviado y el decidido;
  - con 3 casos que el doble deja en 409 → enviado 2 000, decidido 1 997, y los dos números quedan en el registro;
  - los primeros 1 000 `case_ids`, en orden de envío, quedan identificados para `CASE-SIZE`;
  - 2 000 sale de una constante con nombre; en staging la barrera lo niega;
  - el conductor decide solo los `case_ids` del `RunReport`, no otros casos `listo` de la bandeja;
  - la corrida no abre sockets ni duerme: menos de 60 s de reloj real.

- [ ] **CA-18** — Cobertura al umbral del plan (Pasos 4 y 16; NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests --cov=vectra_verification --cov-branch --cov-fail-under=85 && uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100
  ```
  Esperado: los dos en 0: ≥ 85 % de ramas en el paquete y 100 % en `report` y `sampler`. Sin `# pragma: no cover` nuevos, salvo la implementación real del reloj y el lanzamiento real de `kubectl`, anotados en la bitácora. Si `make check` ya corre las dos medidas en una sola pasada, vale su salida.

- [ ] **CA-19** — Trazabilidad (`DECISIONES-LOOP.md` §6, regla «sin fallos nuevos», con su enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado:
  - el primero puede salir con código 1, y entonces cada línea que imprime es de este conjunto: NFR-U12-30, 31, 42 e INF-U12-04, 05 (pasos que esta tarea no cubre);
  - **ninguna** línea nombra NFR-U12-02, 10, 50 ni INF-U12-03 (Pasos 5 y 6), ni ninguno de los que U12-T01 ya dejó trazados;
  - el segundo da, para las demás unidades, el mismo conjunto de fallos que en la base de la rama. El revisor lo corre en la base y en la rama y los compara.

  Las BR-U12-01, 02 y 03 se trazan a mano: tabla en `clients.md` y citas en las pruebas.

- [ ] **CA-20** — `check` de la unidad (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime
  ```
  Esperado: código 0, con lint, mypy estricto, import-linter y **todas** las pruebas (`unit`, `property` e `integration`, con el perfil `ci` y la semilla impresa) y las dos coberturas de CA-18. Tiempo esperado: **menos de 10 min** con la máquina cargada. Referencia medida: 2 min 33 s en U12-T01; lo demás es una estimación (arranque de Keycloak, una espera de TOTP, PostgreSQL y PBT-U12-03). Anota el tiempo real y los dos `uptime`. Si pasa de 15 min, revisa antes de seguir.

- [ ] **CA-21** — Sin contenedores huérfanos (`CANDIDATAS.md`, línea 525).
  ```bash
  docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "keycloak|config-cli|postgres" ; echo "restantes=$?"
  ```
  Esperado: después de CA-20, `restantes=1` (ninguno), o solo contenedores que ya estaban antes de empezar: lista los de antes en la bitácora. Los nodos de kind y `kind-registry` no se tocan.

- [ ] **CA-22** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|pyproject\.toml$|uv\.lock$|CANDIDATAS\.md$|bitacoras/U12-T02\.md$|aidlc-docs/construction/system-verification/code/clients\.md$|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$)"; echo "fuera=$?"
  ```
  Esperado: `uv lock --check` en 0 y `fuera=1`. `git diff origin/main...HEAD -- vectra-risk/uv.lock` solo cambia las dependencias de `vectra-verification`: ninguna versión de un tercero cambia y no hay paquetes nuevos.

- [ ] **CA-23** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso [56] " aidlc-docs/construction/plans/system-verification-code-generation-plan.md && git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: los Pasos 5 y 6 en `[x] (U12-T02)`, el 6 con la nota de `rt1` y `rt4`; el diff muestra solo esas dos casillas. La sección de reglas de admisión sigue en el plan (`platform/tests/test_unit_plans.py`).

- [ ] **CA-24** — Enlaces.
  ```bash
  uv run python platform/tests/test_links.py
  ```
  Esperado: `N archivos Markdown sin enlaces rotos`, código 0.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/doubles/`: el arranque de Keycloak y config-cli en Testcontainers; el doble de `kubectl` (ejecutor inyectado, cuenta órdenes); el doble ligero del gateway y del BFF, validado contra el OpenAPI; los dobles del registro, de Prometheus y de Loki; y el reloj falso.
- `tests/integration/test_oidc_headless.py`: CA-3. `tests/unit/test_oidc_flow.py`: CA-4.
- `tests/unit/test_tokens_not_leaked.py`: CA-5.
- `tests/integration/test_clients.py`: CA-7 y CA-8. `tests/unit/test_k8s_read.py`: CA-9.
- `tests/unit/test_u5_reader.py`: CA-10.
- `tests/integration/test_simulator.py`: CA-11, CA-12 y CA-13.
- `tests/integration/test_driver.py`: CA-14. `tests/property/test_driver_mix.py`: CA-15 (PBT-U12-03).
- `tests/integration/test_decisions_volume.py`: CA-13 y CA-17.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U12-T02.md`, como mínimo los de CA-1, CA-3, CA-4, CA-5, CA-7, CA-8, CA-9, CA-11, CA-12, CA-13, CA-14 y CA-15. El par falla-pasa es la prueba.
- **Orden de las pruebas con Docker:** Keycloak y PostgreSQL no se levantan a la vez si la memoria disponible es menor de 2 GiB: una sesión por contenedor, o los fixtures en serie.

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota y está casi lleno** (80 % al redactar: 1,6 GB libres). No copies el repositorio allí. Los temporales van dentro del worktree, en una carpeta sin versionar (por ejemplo, `platform/.tools/tmp/`): `TMPDIR`, los certificados de la prueba, los perfiles temporales de Chromium y los logs. Docker no monta carpetas de `/tmp` de forma fiable en todas las configuraciones: monta desde el worktree.
- **Máquina compartida y cargada.** Al redactar: `load average: 8.96, 11.10, 9.05` y 2 GiB de memoria disponible de 14, con kind arriba. Anota `uptime` junto a cada medida de tiempo. **Las pruebas de tiempo usan el reloj inyectado, nunca `sleep` real**; la única espera real es la de la ventana TOTP contra Keycloak (CA-3). Una prueba que falla por tiempo con carga alta se repite en frío antes de darla por rota, y se anotan las dos corridas. No corras `make -C platform check` ni las suites de otras unidades.
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry` en `127.0.0.1:5001`) y con otros codificadores. Nombres y puertos de Testcontainers **al azar**, nunca fijos. Límite de memoria en Keycloak. **Borra tus contenedores al terminar**, también tras una corrida interrumpida (CA-21). No borres contenedores ni imágenes ajenos: nada de `docker system prune`.
- **Puertos ocupados.** 443 es del kind (`0.0.0.0:443`). 8080 y 8081 son fijos en las suites de otras unidades (`run_service`). No uses ninguno de los tres, ni 8443 ni 8200. Pide puertos libres al sistema (puerto 0).
- **Sin clúster.** El kind está corriendo y hay un kubeconfig que funciona: **no lo uses**. Ninguna prueba ejecuta el `kubectl` real ni llama a `vectra.localtest.me`. Ver el riesgo de P-1.
- **Navegadores.** Se reusan los de `~/.cache/ms-playwright` (P-9). No los borres ni los reinstales: los usan las pruebas de U10. Nada de `sudo` ni `--with-deps`.
- **Imágenes.** Bajar Keycloak y keycloak-config-cli necesita red y la decisión de P-1. Siempre por digest.
- **No toques el árbol principal ni otros worktrees.** Escribe solo en el tuyo. No uses `git stash` sin etiqueta (`git stash push -m "U12-T02 …"`): el `stash` es compartido entre worktrees.
- **Otros codificadores en paralelo.** Si otra tarea toca a la vez `uv.lock`, el orquestador fusiona `origin/main` y vuelve a correr `uv lock`.

---

## Notas

- **Orden sugerido:** (1) prueba de concepto de P-1 y P-2: Keycloak con el realm de kind arriba y un login a mano, antes de escribir nada más; (2) `clock`, `clients/oidc` y CA-3 a CA-5; (3) `k8s_read`, `registry`, `prom`, `loki` y CA-7 a CA-9; (4) lector de U5, `simulator` y CA-10 a CA-13; (5) mezcla pura, PBT-U12-03 y `driver`; (6) volumen, cobertura, `clients.md`, plan y bitácora. Lo que más riesgo tiene va primero: si P-1 no sale, se sabe en la primera hora.
- **Lo que las tareas siguientes necesitan de esta:**
  - **U12-T03 (D, Pasos 8 y 10):** `bff.resolve_frozen` con step-up de `cumplimiento-1` y la espera de TOTP entre reactivaciones; el login de `ingeniero-1` y `cro-1` para `rt2-setup` (las rutas de modelos del BFF las agrega T03 sobre el mismo cliente); `registry` con `metrics` (filtrada por los `case_id` del `RunReport`, para `rt2_latency`) y `monitoring_freezes`; `prom.query_range`; `k8s_read.get` y `logs` para el Job de RT-5; el simulador `stratified` con sus celdas cortas (P-8 de U12-T01); y el `RunReport` (`sent`, `accepted`, `case_ids`) para `SIM-NORMAL`.
  - **U12-T04 (E+F, Pasos 12, 13, 15 y 17):** la función de la sección `decisions` y su registro (enviado y decidido); `generator_version`, `seed`, tamaño de `test` y las posiciones enviadas, para el manifiesto; el prefijo de la corrida derivado del `runId`; las consultas que devuelven `prom` y `loki`; el refresco de tokens, para la sección `load`; y, para la imagen, Playwright 1.64.0 con Chromium revisión 1248, el sandbox activo y la confianza en la CA (P-2).
  - **U12-T05 (G+H, Pasos 18 y 19):** `make -C system-verification check` con las pruebas de integración; y lo que solo se ve en kind: el login por el gateway real, los límites de `auth-login` y de `console`, `CASE_ALLOW_TEST_SCENARIOS`, K16 y el camino a la bóveda.
- **Avisos: contradicciones entre plan, recorte, diseño y código** vistas al redactar. Deja en `CANDIDATAS.md` las que no estén ya:
  1. **Login por redirección de la consola (`DECISIONES-LOOP.md` §9) frente al Paso 5: no se contradicen.** El Paso 5 supone un cliente público `vectra-console` con Authorization Code + PKCE, sin *password grant*, y los `redirect_uri` `/callback` y `/stepup-callback`. Es lo que hay en `realm.kind.yaml` (líneas 834 a 851), y el step-up de la SPA usa los mismos parámetros (`console/spa/src/stepup/oidc.ts`). La decisión del 2026-11-12 cambió dónde guarda la SPA `state`, `code_verifier` y `nonce` (`sessionStorage`); U12 los genera y los guarda en memoria, y no toca U2. Una consecuencia: U12 intercepta el retorno y **nunca carga** `/callback`, así que su login no prueba la SPA ni la CSP. Eso queda para los ensayos de las demos.
  2. El plan pide «un Keycloak de Testcontainers con el realm de kind», pero el realm es un YAML de keycloak-config-cli con 36 variables y `sslRequired: all`, y no hay ningún patrón en el repositorio. Resuelta con P-1.
  3. U2 ya hace este mismo login **sin navegador**, con `httpx` (`e2e_support.Flow`). El plan y tech-stack exigen Playwright: rige el plan. Queda como alternativa si el sandbox de Chromium no arranca en la imagen (Paso 15).
  4. `accessTokenLifespan: 300` frente a decidir 2 000 casos: el plan no habla de renovar el token. Resuelta con P-7.
  5. La aceptación del Paso 5 («sin reintento silencioso») frente a INF-U12-03 («elige otro y reintenta la lectura»). Resuelta con P-8.
  6. El plan llama «409 `decision_already_recorded`» a lo que en el contrato es `code = conflict_state` con `reason = decision_already_recorded`.
  7. `DecisionMix` tiene `p_resuelve_revision` junto a `p_sigue` y `p_se_aparta`, pero BR-U0-35 no deja elegir entre las tres en un mismo caso. Resuelta con P-6.
  8. BR-U12-01 dice «partición `test` de U5», pero `reference-model/.out/` no se versiona y el Parquet no guarda `generator_version` ni `seed`. Resuelta con P-5. El diseño no dice cómo llega esa carpeta a la imagen de U12 (U12-T04).
  9. El límite `intake-channel-simulator` es de 30/s **sin ráfaga**, igual al máximo del simulador: a 30/s exactos, cualquier variación da 429. Y `console` limita a 20/s por usuario, que ni el plan ni el diseño nombran para el conductor. Por omisión, 10/s.
  10. `CASE_ALLOW_TEST_SCENARIOS` no está todavía en los values de kind de `main` (lo pone U08-T05, en curso). Sin él, U8 responde 422 a **toda** solicitud del simulador. Comprobarlo en el Paso 18.
  11. NFR-U12-50 pide la cabecera de escenario en las solicitudes del conductor, pero el BFF no la reenvía a U8 (bff-api.md, líneas 24 y 25). En el conductor solo el `traceparent` llega hasta el registro.
  12. deployment-architecture §2b no dice cómo confía Chromium en la CA. Resuelta con P-2; hay que cerrarla en la imagen (U12-T04).
  13. §1 del plan no tiene un módulo para el login ni para el reloj. Resuelta con P-4.
  14. El realm bloquea para siempre al quinto fallo de login. Ni el plan ni el diseño dicen qué hace la herramienta ante un login fallido: aquí, un error y ningún reintento.
- Archivos que se **modifican en su sitio**: `system-verification/pyproject.toml`, `.importlinter`, `Makefile`, `simulator.py`, `driver.py`, `clients/__init__.py`, `uv.lock`, el plan (casillas de los Pasos 5 y 6) y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **`Makefile`.** `test` pasa a correr también `tests/integration`. `check` sigue siendo `lint types imports test`. No se agregan `links` ni `traceability`: son de U12-T04.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`: `test_traceability.py` los salta.
- **Enlaces:** `test_links.py` lee como enlace cualquier corchete cerrado seguido de un paréntesis fuera de un bloque de código sin sangría. Cuidado con los patrones de `grep` en `clients.md` y en la bitácora.
- **Bitácora** `bitacoras/U12-T02.md`: la salida real de cada comando, pegada, con rutas absolutas a los logs largos y sin plantillas sin expandir. Incluye la semilla de cada corrida con Hypothesis, los pares falla-pasa, la decisión tomada en P-1 a P-10, el tiempo de cada `make check` con sus `uptime`, los digests de las imágenes bajadas, la lista de contenedores antes y después, y el `uv tree --package vectra-verification`. **Ningún secreto**: tampoco los generados para la prueba.
- PBT-U12-01..04 nunca se recortan. Con esta tarea quedan escritas las cuatro.
- U12 no tiene datos propios ni recursos en el clúster: no hay migraciones, chart ni nada que limpiar en kind.
