# Plan de tareas (Code Generation Part 1) — U10 `console`

**Este plan es la única fuente de verdad para generar el código de U10.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U10. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U10 `console`: `console-bff` (FastAPI, 29 endpoints de C03, sin estado) y `console-spa` (React + TypeScript, estática) |
| Historias (dueña) | US-602 |
| Contribuye a | US-102, 104, 106, 107, 108, 109, 110, 112, 201, 203, 205, 206, 304, 305, 306, 307, 402, 403, 501, 502, 609, 611 (`unit-of-work-story-map.md`) |
| Ubicación | `vectra-risk/console/` (`bff/`, `spa/`, `chart/`) y Applications en `vectra-risk-gitops` |
| Datos propios | Ninguno: el BFF compone respuestas de los servicios de destino; la SPA guarda todo en memoria |
| Depende de | U0 (`RouteContract` con `max_body_bytes`, `create_app`, `deps.call`, tipos de §9.2, §9.5 y §9.6, `contracts/ts`, `forbidden_phrases.py`, catálogo de eventos), U1 (malla, cuotas, `flows.yaml`, `require-hpa-bounds`, PriorityClasses), U2 (cliente `vectra-console` con `/stepup-callback`, rutas, CSP con Trusted Types, COOP, afinidad por cookie, usuarios de prueba, equipos de Grafana), U3 (expediente, verificación bajo demanda), U4 (modelos, políticas, fuentes, congelamientos), U7 (resumen para el solicitante), U8 (casos, decisión, `get_case_identifiers`), U9 (dashboard, congelamientos, `bias.json`) |
| Lo consumen | Las cuatro personas por el navegador; U12 (pruebas de extremo a extremo y de carga) |

**Diseño de entrada:**
- Functional Design: `construction/console/functional-design/` (BR-U10-01..22, PBT-U10-01..06, frontend-components).
- NFR Requirements: `construction/console/nfr-requirements/` (NFR-U10-01..64).
- NFR Design: `construction/console/nfr-design/` (P-U10-01..11, E1–E7).
- Infrastructure Design: `construction/console/infrastructure-design/` (INF-U10-01..06).

**AUTONOMIA-01:** las verificaciones estáticas, las propiedades y las pruebas con dobles
corren en CI. Las que necesitan el clúster (Keycloak real, rollout, carga, Lighthouse, malla)
las ejecuta **un operador en kind** después de un PR aprobado (Paso 22), con la evidencia
adjunta al PR.

**Dobles hasta que existan las unidades reales:** en CI, el BFF se prueba con dobles HTTP de
case, governance, registry, explainability y bias que siguen `vectra_contracts`, y un emisor de
JWT de prueba con las claves y los claims de U2. La SPA se prueba contra el BFF con dobles. Las
pruebas de kind usan las unidades reales.

### Estructura de destino

```text
vectra-risk/console/
|-- Makefile
|-- bff/
|   |-- pyproject.toml  .importlinter
|   |-- src/console_bff/
|   |   |-- config.py                      # constantes: timeouts, conexiones, presupuesto
|   |   |-- object_rules.py  errors.py     # puros
|   |   |-- routes.py  compose.py  clients.py  client_errors.py  metrics.py  app.py
|   `-- tests/  unit/ property/ integration/ doubles/ load/
|-- spa/
|   |-- package.json  package-lock.json  vite.config.ts  tsconfig.json  .eslintrc.cjs  .size-limit.json
|   |-- index.html  nginx.conf  Dockerfile
|   |-- src/
|   |   |-- config/constants.ts  config/load.ts       # constantes y config.json por entorno
|   |   |-- auth/  stepup/  inactivity/  api/  i18n/  reporter/  version/
|   |   |-- views/cases/  views/governance/  views/bias/  views/shared/
|   |   `-- stepup-callback.ts
|   `-- tests/  unit/ property/ e2e/ a11y/ csp/ poc/
|-- chart/   templates/  values-{prod,staging,kind}.yaml
|-- policies/conftest/
`-- observability/  rules/  rules/tests/  runbooks/  dashboards/console.json
```

---

## 2. Pasos

### Bloque A — Estructura y constantes

- [ ] **Paso 1 — Esqueleto de `console/`**
  - Directorios de §1; `bff/pyproject.toml` como miembro del workspace de `uv` (depende de `vectra_contracts` y `vectra_common`); `spa/package.json` como workspace de npm que depende de `contracts/ts`.
  - import-linter del BFF: `object_rules` y `errors` sin E/S; ningún módulo importa `httpx` fuera de `vectra_common.deps`.
  - ESLint de la SPA: `react/no-danger` (prohíbe `dangerouslySetInnerHTML`), `jsx-a11y`, prohibición de literales de texto en JSX, de `localStorage`, de `sessionStorage` y de `Number(`/`parseFloat` sobre `Decimal*`; TypeScript con `strict` y `noUncheckedIndexedAccess`.
  - Diseño: NFR-U10-43, 53, 64; BR-U10-05, 11.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config console/bff/.importlinter`; `npm ci --ignore-scripts -w console/spa && npm run -w console/spa lint && npm run -w console/spa typecheck` sobre el esqueleto; un fixture con `dangerouslySetInnerHTML` y otro con `localStorage.setItem` → ESLint falla.

- [ ] **Paso 2 — Constantes y configuración**
  - BFF `config.py`: timeouts, conexiones por destino y presupuesto de P-U10-04 (incluidos los 4 s de escritura en case y governance).
  - SPA `config/constants.ts`: las constantes de domain-entities §4 (step-up, inactividad, difusión de actividad, consulta de versión, `reporter`, timeout de la API, refrescos).
  - SPA `config/load.ts`: carga `config.json` (solo OIDC y el `uid` de `bias.json`) con `fetch`; falla si falta un campo o aparece uno desconocido.
  - Diseño: P-U10-04; INF-U10-03; domain-entities §4.
  - **Aceptación**: `uv run pytest console/bff/tests/unit/test_config.py` (los valores coinciden con la tabla de P-U10-04; ningún timeout ≥ 9 s); `npm run -w console/spa test -- config` (`IDLE_LOGOUT_SECONDS` = `ssoSessionIdleTimeout` de los tres `realm.{env}.yaml` de U2; un `config.json` con una constante de tiempo → error).

### Bloque B — Lógica pura del BFF

- [ ] **Paso 3 — `object_rules` y `errors`**
  - `object_rules`: una función pura por endpoint con regla de objeto de C03 (`record_decision` ⇔ `listo`; `retry_case` ⇔ `no_disponible` y no anonimizado; `approve_model` ⇔ `lista_para_aprobacion`; `resolve_frozen` ⇔ `congelado`; `decide_data_source` ⇔ `en_evaluacion` con informe; `start_validation` ⇔ `registrado`; `approve_policy` ⇔ `propuesta`; etc.).
  - `errors`: traducción de cualquier respuesta de error de un destino al `Problem` de U0 (mismo `code`, o `internal_error`), sin `detail`; un 403 o 404 de un destino se propaga como tal.
  - Diseño: BR-U10-01, 03, 04; P-U10-01, 03. Historias: US-602, US-611.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_object_rules.py tests/property/test_errors.py`: PBT-U10-02 y PBT-U10-03.

- [ ] **Paso 4 — Resumen de la lógica pura**
  - Cobertura de ramas **100 %** en `object_rules` y `errors`; `mutmut` en `object_rules` con 0 sobrevivientes sin justificar.
  - Resumen en `aidlc-docs/construction/console/code/bff-logic.md`.
  - Diseño: NFR-U10-60.
  - **Aceptación**: `uv run pytest console/bff/tests/unit console/bff/tests/property --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100`; `uv run mutmut run --paths-to-mutate console/bff/src/console_bff/object_rules.py`.

### Bloque C — Capa de API del BFF

- [ ] **Paso 5 — Rutas, clientes y composición**
  - `routes.py`: los **29** `RouteContract` de C03 con `required_roles`, `mfa` (900 s) y `object_rule` explícita (una ruta sin ella no arranca); `max_body_bytes` por omisión.
  - `clients.py`: un cliente de `deps.call` por destino (case, governance, registry, explainability, bias) con timeout, presupuesto (`x-vectra-deadline` = entrada + 9 s), límite de conexiones y circuit breaker con los umbrales de U7; sin reintentos.
  - `compose.py`: `get_dossier` con `asyncio.TaskGroup` (registry `get_case_dossier` + case `get_case_identifiers`; registro caído → 503 y se cancela la otra; case caído → `identifiers_unavailable`; 403 o 404 de case → ese error); `get_disparity` (governance `list_models(state=activo,congelado)` y después bias, sin caché).
  - `run_integrity_check(req)` y `get_integrity_check(id)` de paso a U3, con `already_active` en la respuesta.
  - Diseño: BR-U10-01..04; P-U10-01..05; NFR-U10-30..33. Historias: US-402, US-403, US-602.
  - **Aceptación**: `uv run pytest console/bff/tests/integration/test_compose.py tests/integration/test_clients.py tests/integration/test_routes_registry.py`:
    - dobles de 500 ms en las dos ramas de `get_dossier` → < 700 ms;
    - registro caído → 503 y la llamada a case cancelada; case caído → `identifiers_unavailable = true`; case con 403 → 403;
    - cada destino corta en su timeout; la cabecera de plazo llega al doble; un circuito abierto da 503 de inmediato y 0 llamadas;
    - un 503 de un `POST` → una sola llamada al destino;
    - con bias caído, `list_cases` y `record_decision` responden 2xx;
    - una ruta sin `object_rule` → `create_app` falla al arrancar.

- [ ] **Paso 6 — `client_errors` y métricas**
  - `POST /api/console/client-errors`: `ClientErrorReport` (U0 §9.5, `extra = "forbid"`), evento `console.client_error`, métrica `vectra_console_client_errors_total{error_code}` con las **seis** series creadas en 0 al arrancar; 204.
  - Histogramas por ruta y `vectra_bff_dependency_duration_seconds{dependency, route}`.
  - Diseño: BR-U10-22; P-U10-09, 11; NFR-U10-34.
  - **Aceptación**: `uv run pytest console/bff/tests/integration/test_client_errors.py tests/integration/test_metrics.py`: un cuerpo con un campo extra o con un mensaje libre → 422; `GET /metrics` recién iniciado muestra las seis series en 0; PBT-U0-07 en modo strict sobre `console.client_error`.

- [ ] **Paso 7 — Matriz rol × endpoint y pruebas de ejemplo de la API**
  - Matriz generada desde el registro de rutas (BR-U10-19): 29 endpoints × (4 roles, sin rol de negocio, expirado, otra audiencia, `acr = pwd`, `auth_time` vencido), comparando status y `code`; un caso negativo por regla de objeto; `authz.denied` con `principal_subject` en cada 401/403. Se publica como `role-endpoint-matrix.md` y se compara con C03.
  - Pruebas de ejemplo del FD (business-logic-model §3): analista → aprobación de modelo → 403; JWT expirado, de otra audiencia o mal firmado → 401; aprobador sin MFA reciente → 403 `mfa_required`; `decision_already_recorded` → 409 con el `reason`; expediente de `cumplimiento`.
  - Diseño: BR-U10-19; PBT-U10-01; NFR-U10-46. Historias: US-602, US-611.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_role_matrix.py tests/integration/test_api_examples.py`; `uv run python console/bff/tools/role_matrix.py --check` (la matriz generada coincide con C03 y con `role-endpoint-matrix.md` versionado).

- [ ] **Paso 8 — Arranque, apagado y resumen de la API**
  - Readiness y liveness solo del proceso (8081); `preStop` de 5 s; uvicorn con `timeout_graceful_shutdown = 10`.
  - Cobertura ≥ 90 % en el resto del BFF; resumen en `aidlc-docs/construction/console/code/bff-api.md`.
  - Diseño: INF-U10-01; NFR-U10-60.
  - **Aceptación**: `uv run pytest console/bff/tests --cov=console_bff --cov-branch --cov-fail-under=90`; prueba de que `/readyz` responde 200 con todos los destinos caídos.

### Bloque D — Repositorio

- [ ] **Paso 9 — Repositorio y migraciones: N/A**
  - U10 no tiene base de datos.
  - **Aceptación**: `test ! -d console/bff/migrations`.

### Bloque E — SPA

- [ ] **Paso 10 — Prueba de concepto del step-up (puerta de los Pasos 11–15)**
  - Página mínima con un botón que, en su manejador de clic, llama a `OidcClient.createSigninRequest` (`prompt=login`, `max_age=0`, `acr_values=mfa`, `redirect_uri=/stepup-callback`, `stateStore` en `InMemoryWebStorage`) y a `window.open` de forma síncrona; `stepup-callback.ts` hace `postMessage({code, state}, location.origin)` y se cierra; la ventana principal valida origen, ventana y `state` y llama a `processSigninResponse`.
  - Diseño: P-U10-07; BR-U10-06; tech-stack (OIDC).
  - **Aceptación**: `npx playwright test console/spa/tests/poc` en Chromium y Firefox contra Keycloak de kind (operador) y contra un emisor OIDC de prueba en CI: el token nuevo trae `acr = mfa`; `sessionStorage` y `localStorage` vacíos; un `window.open` llamado fuera del clic queda bloqueado; un `postMessage` de otro origen se ignora. Si la prueba falla, se detiene el bloque y se revisa P-U10-07 antes de seguir.

- [ ] **Paso 11 — `auth`, `stepup` e `inactivity`**
  - `auth`: `UserManager` con `InMemoryWebStorage`, login con PKCE, refresco rotativo, login silencioso (`prompt=none`), logout con `end_session_endpoint`.
  - `stepup`: el flujo del Paso 10 con el botón «Verificar y confirmar» (token sin MFA reciente) y `StepUpDialog` (403 `mfa_required` inesperado); reintento único con el mismo cuerpo; vencimiento de 5 min; anuncio `aria-live` y devolución del foco en < 1 s.
  - `inactivity`: contador de la sesión (`keydown`, `pointerdown`, `focusin`, `wheel`, `scroll`), difusión `activity` y `logout` por `BroadcastChannel`, aviso a los 25 min y logout a los 30.
  - Diseño: BR-U10-05, 06, 20; P-U10-07; NFR-U10-40, 41, 52.
  - **Aceptación**: `npm run -w console/spa test -- auth stepup inactivity` con reloj simulado: PBT-U10-05 (fast-check, stateful); actividad en la pestaña A durante 40 min con B quieta → sin logout; 30 min sin actividad → logout en las dos; el refresco de la bandeja no reinicia el contador.

- [ ] **Paso 12 — `api`, `i18n`, `reporter` y `version`**
  - `api`: cliente `openapi-fetch` de U0 con timeout de 10 s y TanStack Query.
  - `i18n`: `messages.es.json` y `labels.es.json` con un texto por cada `code`, `reason` y valor de enumerado de U0 (arreglos constantes de `contracts/ts`); `Intl` en `es-CO`.
  - `reporter`: traducción al catálogo cerrado de `error_code`, ≤ 10 por minuto, `fetch` con `keepalive`, sin mensajes, trazas ni URL con parámetros.
  - `version`: consulta de `version.json` cada 5 min y `VersionBanner`; mensaje con botón al fallar un fragmento; nunca recarga sola.
  - Diseño: BR-U10-17, 18, 21, 22; P-U10-06, 09; NFR-U10-53.
  - **Aceptación**: `npm run -w console/spa test -- api i18n reporter version`: PBT-U10-06; `uv run python contracts/tools/forbidden_phrases.py console/spa/src/i18n/*.json` en 0; 20 errores en un minuto → 10 envíos; `version.json` distinto → aviso sin recarga.

- [ ] **Paso 13 — Vistas de casos**
  - `CasesInbox` (filtros de `CaseFilter` en la URL, «Ir al caso» por `case_id`, refresco de 15 s), `CaseDetail` (refresco de 3 s hasta 2 min), `RecommendationSummary`, `ExplanationPanel` (`record_explanation_view` una vez por vista), `ApplicationView` (`free_text` como texto), `CreditStatusBadge` (incluido `no_integrado`), `DecisionForm` (validación igual que el servidor, diálogo de confirmación, botón deshabilitado en curso), `ManualApplicationForm` (`Idempotency-Key` por envío), `PersistentFailures` con `retry`, `ApplicantSummaryButton`, `Dossier` (PDF en el navegador) e `IntegrityCheck` (inicio con MFA, `already_active`, estado cada 30 s).
  - Diseño: BR-U10-07..11, 03; frontend-components. Historias: US-102, 104, 106, 107, 108, 109, 110, 112, 402, 403, 501, 502.
  - **Aceptación**: `npm run -w console/spa test -- views/cases`: PBT-U10-04 (mismo oráculo que PBT-U8-03); las pruebas de ejemplo del FD de casos (bandeja sin `vencido` por omisión, `free_text` con `<script>`, `no_integrado`, baja confianza y `revision_requerida`, `decision_already_recorded`, expediente sin identificadores, `retry` del CRO, panel de explicación con una sola llamada y ninguna sin abrirlo); la URL de la bandeja nunca contiene datos del solicitante.

- [ ] **Paso 14 — Vistas de gobierno y sesgo**
  - `RoleMenu` desde `get_me` con las rutas por rol de BR-U10-12; modelos, políticas y fuentes con sus diálogos con MFA; `PrePostReportView` + `DecideDataSourceDialog` (sin informe, sin botones); `BiasDashboard` (`DisparityTables` con celdas insuficientes y `GrafanaEmbed` con la leyenda propia encima); `Freezes` y `FreezeContextView` + `ResolveFrozenDialog` (aviso de `reactivar`).
  - Diseño: BR-U10-12..16. Historias: US-201, 203, 205, 206, 304, 305, 306, 307.
  - **Aceptación**: `npm run -w console/spa test -- views/governance views/bias`: las rutas por rol coinciden con la columna «Roles» de C03 (`cro` no ve el paquete de contexto; `cumplimiento` no ve la bandeja); celdas insuficientes nunca muestran 0 ni una tasa; el `disclaimer` y la leyenda siempre presentes.

- [ ] **Paso 15 — CSP, accesibilidad y extremo a extremo con dobles**
  - Playwright contra la SPA de Vite y el BFF con dobles: recorrido de todas las vistas y diálogos con un listener de `securitypolicyviolation` (0 violaciones con la CSP de U2, Trusted Types incluido) y `@axe-core/playwright` (0 `serious` y `critical`).
  - `index.html` sin `<script>` ni `<style>` en línea; `build.modulePreload.polyfill = false`.
  - `size-limit` ≤ 250 KiB comprimido inicial.
  - Diseño: NFR-U10-03, 42, 50, 51; P-U10-08. Historias: US-611.
  - **Aceptación**: `npx playwright test console/spa/tests/e2e console/spa/tests/csp console/spa/tests/a11y --project=chromium --project=firefox`; `npx size-limit` en 0.

- [ ] **Paso 16 — Resumen del frontend**
  - Cobertura de ramas **100 %** en `stepup` y en la validación de la decisión, ≥ 80 % en el resto; Stryker en `stepup`.
  - Resumen en `aidlc-docs/construction/console/code/spa.md`.
  - Diseño: NFR-U10-61, 62.
  - **Aceptación**: `npm run -w console/spa test -- --coverage` con los umbrales por archivo; `npx stryker run console/spa/stryker.conf.json` sin sobrevivientes sin justificar en `stepup`.

### Bloque F — Despliegue y operación

- [ ] **Paso 17 — Imágenes**
  - BFF: Python oficial por digest, `runAsNonRoot`, `readOnlyRootFilesystem`.
  - SPA (INF-U10-02): etapas `build`, `no-previous` (`FROM scratch`, manifiesto vacío), `previous` (`FROM ${PREVIOUS_IMAGE}`, por omisión `no-previous`) y final `nginx-unprivileged` por digest; copia los recursos de `previous` listados en su `manifest.json`; etiqueta OCI `vectra.io/previous-digest` (`none` en el primer release).
  - `nginx.conf`: `no-store` en `index.html`, `version.json` y `config.json`; `immutable` en `assets/`; fallback a `index.html` solo para rutas sin extensión; sin `server_tokens`.
  - Construidas, escaneadas, con SBOM y firmadas por `supply-chain.yml` de U1; `npm ci --ignore-scripts`.
  - Diseño: INF-U10-02; NFR-U10-44, 45; P-U10-06.
  - **Aceptación**: `hadolint console/bff/Dockerfile console/spa/Dockerfile`; prueba sobre la imagen de la SPA construida con un `PREVIOUS_IMAGE` de fixture (contiene los recursos de las dos versiones y ninguno más viejo; la etiqueta tiene el digest) y sin él (etiqueta `none`, sin recursos anteriores); prueba de `nginx.conf` con `nginx -t` y `curl` en un contenedor local (`/cases/123` → `index.html`; `/assets/no-existe.js` → 404; cabeceras de caché).

- [ ] **Paso 18 — Chart, cuotas y flujos**
  - BFF: `Deployment` con HPA de 2 a 6 (en kind, `minReplicas = maxReplicas = 2`), `maxSurge: 1` y `maxUnavailable: 0`, PDB, spread por zona, `vectra-high`, `ServiceMonitor` 8081, `ConfigMap` de URLs y audiencias.
  - SPA: 2 réplicas fijas con `vectra.io/hpa-exempt`, `maxSurge: 100%` y `maxUnavailable: 0`, PDB, spread, `vectra-normal`, `ConfigMap` de `config.json` montado sin `subPath` y anotación `checksum/config`.
  - Aporte a las cuotas de `vectra-app` y `vectra-edge` con los pods del rollout y el proxy (INF-U10-01) en `platform/policies/quotas/` de U1.
  - Flujos en `platform/network/flows.yaml`: F02, F03, F10–F14, F50 y F60, con los casos bloqueados de INF-U10-04.
  - Diseño: INF-U10-01, 03, 04; NFR-U10-10..12, 20, 22.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test console/policies/conftest/` (réplicas, HPA de kind, exención, estrategias, PDB, spread, PriorityClass, sin `subPath`, `checksum/config`, `config.json` sin secretos y con los `redirect_uri` del realm del entorno); `kyverno test` de U1 (`require-hpa-bounds`); `conftest test platform/policies/quotas/`; `uv run python platform/network/generate.py --check`.

- [ ] **Paso 19 — Alertas, runbooks y dashboard**
  - `PrometheusRule` con las **seis** alertas de P-U10-10 y sus recording rules, cada una con `severity` y `runbook_url`.
  - Runbooks `console-bff-error-budget`, `console-bff-down`, `console-dependency-circuit-open`, `console-client-errors-spike` (con la sección de `csp_violation`) y `console-spa-emergency-rollback`.
  - Dashboard `observability/dashboards/console.json`.
  - Diseño: P-U10-10; INF-U10-05.
  - **Aceptación**: `promtool test rules console/observability/rules/tests/*.yaml` (cada alerta a los dos lados del umbral; un 503 `dependency_unavailable` no cuenta para el presupuesto; `ConsoleChunkOrCspError` dispara con una serie que pasa de 0 a 1); `uv run python platform/tests/test_runbooks.py --root console`; `uv run python contracts/tools/forbidden_phrases.py console/observability/dashboards/console.json`.

- [ ] **Paso 20 — Workflows de CI y de release**
  - `.github/workflows/console.yml` en cada PR que toca `console/`: `uv sync --frozen`, ruff, mypy, import-linter, `npm ci --ignore-scripts`, ESLint, typecheck, pruebas con perfil `ci` y semilla impresa, cobertura, matriz rol × endpoint, `size-limit`, Playwright con dobles, `helm template`, `conftest`, `promtool`; reutiliza `tests.yml`, `supply-chain.yml` y `policies.yml` de U1.
  - Workflow nocturno: perfiles `nightly`, `mutmut` y Stryker.
  - `.github/workflows/console-spa-release.yml`: lee el digest de `console-spa` de los values de producción en `vectra-risk-gitops`, lo verifica con `cosign verify`, construye con `PREVIOUS_IMAGE` (o sin él si producción no tiene digest) y abre el PR a **staging**.
  - En `vectra-risk-gitops`: `spa-previous-digest-check` (obligatorio en la protección de `main`) en los PR de promoción a producción: la etiqueta `vectra.io/previous-digest` coincide con el digest actual de producción (o es `none` sin digest en producción) y el digest a promover figura en el historial de staging.
  - **AUTONOMIA-01**: ningún paso `kubectl`, `helm install`/`upgrade` ni `terraform apply`.
  - Diseño: NFR-U10-44, 60..63; INF-U10-02.
  - **Aceptación**: `actionlint .github/workflows/console*.yml`; `! grep -E "kubectl|helm (install|upgrade)|terraform apply" .github/workflows/console*.yml`; `uv run pytest console/bff/tests/unit/test_previous_digest_check.py` (etiqueta distinta → falla; `none` con producción vacía → pasa; `none` con producción con digest → falla; digest que no estuvo en staging → falla; caso correcto → pasa).

- [ ] **Paso 21 — Applications, especificaciones de carga y trazabilidad**
  - Applications del BFF y de la SPA en la wave 5, por entorno y sin auto-sync.
  - Script k6 con el perfil por rol de P-U10-11 (200 usuarios, 30 min) y configuración de Lighthouse CI con el perfil de red del banco.
  - Trazabilidad de cada BR-U10 a una prueba.
  - Diseño: P-U1-12; P-U10-11; NFR-U10-01, 02, 04.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `k6 inspect console/bff/tests/load/console.js`; `npx lhci healthcheck --config console/spa/lighthouserc.json`; `uv run python platform/tests/test_traceability.py --unit console --all`.

### Bloque G — Verificación en kind (con aprobación humana)

- [ ] **Paso 22 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–21 aprobado por un humano, con U1–U4 y U7–U9 instalados en kind.
  - El operador ejecuta, con evidencia:
    1. la prueba de concepto del step-up (Paso 10) y la suite de Playwright con Keycloak real y los usuarios `analista-1` … `cumplimiento-2` (incluido aprobador ≠ proponente con `cro-1` y `cro-2`);
    2. la suite de conectividad de U1 con los casos de INF-U10-04;
    3. E1–E7 de P-U10-05 con las unidades reales (E7: borrar el pod de `registry-verify-ondemand` a mitad de una `full`);
    4. un rollout real de la SPA con una pestaña abierta antes y otra nueva a mitad: sin `chunk_load_failed` (afinidad por cookie y recursos de dos versiones);
    5. k6 con el perfil por rol (NFR-U10-01, 02, 10) y Lighthouse CI (NFR-U10-04);
    6. la lista de chequeo manual de accesibilidad por vista (NFR-U10-51), con NVDA en los flujos de decisión y aprobación.
  - Diseño: P-U10-05, 06, 10, 11; INF-U10-04, 06; NFR-U10-01..04, 21, 51, 63. Historias: US-602, US-609.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con el comando, la salida y el resultado esperado frente al obtenido.

### Bloque H — Documentación y cierre

- [ ] **Paso 23 — Documentación**
  - `console/README.md`: arquitectura, cómo correr el BFF con dobles y la SPA con Vite, constantes, flujo de release de la SPA y el rollback de emergencia; referencia a `role-endpoint-matrix.md`.
  - **Aceptación**: `test -s console/README.md`; un enlace por runbook y por documento de diseño, comprobado por `platform/tests/test_links.py`.

- [ ] **Paso 24 — Cierre de la unidad**
  - **Aceptación**: `make -C console check`, que corre en orden las verificaciones estáticas, las propiedades, las pruebas de integración y las de Playwright con dobles de los Pasos 1–21 y termina en 0. Las de kind (Paso 22) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-602 (dueña) | 3, 5, 7, 14, 22 |
| US-102, 108, 502 | 13 |
| US-104, 106, 109, 110, 501 | 13 |
| US-107, 112 | 13 |
| US-201, 203, 205, 206 | 11, 14 |
| US-304, 305, 306, 307 | 11, 14 |
| US-402, 403 | 5, 13, 22 |
| US-609 | 18, 22 |
| US-611 | 3, 7, 15 |

| Diseño | Pasos |
|---|---|
| BR-U10-01..04, 19 | 3, 5, 7 |
| BR-U10-05, 06, 20 | 10, 11 |
| BR-U10-07..11 | 13 |
| BR-U10-12..16 | 14 |
| BR-U10-17, 18, 21, 22 | 6, 12 |
| NFR-U10-01..64 | 2, 4–8, 11–22 |
| P-U10-01..11 | 3, 5, 6, 10–12, 15, 17, 19, 21, 22 |
| INF-U10-01..06 | 17, 18, 19, 20, 22 |

| Propiedad | Pasos |
|---|---|
| PBT-U10-01 | 7 |
| PBT-U10-02, 03 | 3 |
| PBT-U10-04 | 13 |
| PBT-U10-05 | 11 |
| PBT-U10-06 | 12 |

## 4. Cumplimiento de extensiones (plan de tareas U10)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ningún paso aplica ni sincroniza; los escenarios con clúster los ejecuta el operador (Paso 22) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 | Cumple | Casos bloqueados de INF-U10-04 (Pasos 18, 22) |
| AUTONOMIA-04 | Cumple | `resolve_frozen` solo para `cumplimiento` con MFA (Pasos 3, 7, 14) |
| SECURITY-04 / 05 / 08 / 10 / 12 / 14 / 15 | Cumple | Pasos 1, 3, 5–7, 10–12, 15, 17, 20 |
| RESILIENCY-01 / 04 / 05 / 07 / 08 / 09 / 10 / 14 / 15 | Cumple | Pasos 5, 8, 17–19, 22 |
| PBT-01..10 | Cumple | PBT-U10-01..06 (Pasos 3, 7, 11–13), perfiles `ci` y `nightly` (Paso 20) y pruebas de ejemplo (Pasos 7, 13, 14) |
