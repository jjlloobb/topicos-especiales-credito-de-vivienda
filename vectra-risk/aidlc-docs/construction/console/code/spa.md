# `console-spa` — resumen del código (U10, Bloque E)

Entrega de **U10-T03** (Pasos 10 a 12 del plan: acceso y base) y de **U10-T04** (Pasos 13 a 16: las vistas de la demo, la CSP, la accesibilidad, el
extremo a extremo con dobles y este resumen, «resumen del frontend» del Paso 16). Aquí: qué módulos hay y qué regla cubre cada uno, la tabla de rutas por
rol, cómo se corre todo, las decisiones de las dos tareas (con las respuestas a sus preguntas) y lo que el recorte difiere. Resumen de U10-T04 en §9.

## 1. Módulos (`console/spa/src/`)

| Módulo | Qué hace | Reglas |
|---|---|---|
| `config/` | `config.json` (`load.ts`) y constantes del código (`constants.ts`, con `MFA_MAX_AGE_SECONDS` = `MFA_MAX_AGE` de U0, atada por una prueba) | INF-U10-03; BR-U10-06 |
| `stepup/` | `machine.ts` (núcleo **puro**: máquina de estados del intento), `flow.ts` (la ventana, los temporizadores y el cliente OIDC inyectados), `oidc.ts` (`OidcClient` de bajo nivel con su propio `stateStore` en memoria), `mfa.ts` («MFA reciente»), `StepUpProvider`, `StepUpButton` («Verificar y confirmar») y `StepUpDialog` («Verificar identidad») | BR-U10-06; P-U10-07; NFR-U10-52, 61, 62; PBT-U10-05 |
| `stepup-callback.ts` | `postMessage({code, state}, location.origin)` al opener y se cierra; no canjea, no guarda nada y no pide `config.json` | BR-U10-06 |
| `auth/` | `manager.ts` (`UserManager` con login por redirección: `userStore` en `InMemoryWebStorage`, `stateStore` en `loginStateStorage`, sin `popup_redirect_uri` ni `silent_redirect_uri`), `loginStateStorage.ts` (**el único** módulo que nombra `sessionStorage`: solo `state`, `code_verifier` y `nonce` del flujo en curso) y `AuthProvider`/`TokenStore` (canjea `/callback` en la misma página, una redirección `prompt=none` al cargar sin sesión, `get_me` tras cada token nuevo) | BR-U10-05; NFR-U10-40 |
| `inactivity/` | `monitor.ts` (contador de la sesión, cinco eventos, `BroadcastChannel("vectra-console")`), `InactivityProvider` e `InactivityDialog` | BR-U10-20; NFR-U10-40, 41 |
| `api/` | `client.ts` (`createClient<paths>` de `@vectra/contracts`, token, timeout de 10 s, sin reintentos, `ApiError`/`MfaRequiredError`/`TransportError`; U10-T04: el `Problem` conserva `invalid_params`), `queryClient.ts` (TanStack Query sin reintentos ni refresco por foco), `endpoints.ts` (`get_me` y, de U10-T04, las funciones de cada endpoint de las vistas que entran), `hooks.ts` (un hook por lectura; los refrescos de 15 s y de 3 s hasta 2 min van con `refetchInterval`) y `ApiProvider.tsx` | P-U10-04; NFR-U10-33; BR-U10-10 |
| `i18n/` | `messages.es.json` (códigos, motivos, avisos, interfaz), `labels.es.json` (enumerados) y `index.ts` (`ui`, `notice`, `label`, `problemText`, `formatDate`, `formatDecimal` con `Intl` es-CO) | BR-U10-17, 18; NFR-U10-53; PBT-U10-06 |
| `reporter/` | `reporter.ts` (catálogo cerrado de `error_code`, ≤ 10 por minuto, `keepalive`, sin mensajes ni URL), `ErrorBoundary`, `version.ts` (`app_version`) | BR-U10-22; P-U10-09; NFR-U10-34 |
| `entry.ts`, `main.tsx`, `wiring.ts`, `App.tsx` | La entrada detecta `/stepup-callback` **antes** de montar React y de crear el `UserManager` (`/callback` es la propia SPA: `AuthProvider` canjea el código en memoria); `wiring.ts` arma todo desde `config.json` (U10-T04: más el cliente de la API de las vistas y la plantilla de ruta del `reporter`, que sale de la tabla de rutas); `App` pone los proveedores alrededor del enrutador (se monta con la sesión: para entonces `/callback` ya se limpió) | BR-U10-05, 06 |
| `views/shared/` (U10-T04) | `routes.ts` (la **tabla de rutas por rol**, §8), `AppRoutes` (rutas y guarda por rol, cada vista con `React.lazy`), `loaders.ts` (los `import()`), `lazyView.ts` (un fragmento que no carga se reporta como `chunk_load_failed`), `Layout`, `RoleMenu`, `NotAvailable` (el marcador), `NoAccess` y `UnknownRoute`, `ProblemMessage` (el texto del catálogo y el código de soporte; nunca el `detail`) y `Choice` (casilla o radio con su etiqueta por `htmlFor`) | BR-U10-12, 17, 22; NFR-U10-03 |
| `views/cases/` (U10-T04) | `CasesInbox` (+ `CaseFilters`, `GoToCase`, `filters.ts`: filtros de `CaseFilter` en la URL con lectura estricta), `CaseDetail`, `RecommendationSummary`, `ExplanationPanel`, `ApplicationView`, `CreditStatusBadge`, `CaseStateBadge`, `DecisionForm` y **`decision-validation.ts`** (la validación pura: cuenta como el servidor, 100 % de ramas) | BR-U10-07 a 11; PBT-U10-04 |
| `views/governance/` (U10-T04) | `Models`, `ModelDetail` (de lectura; con el informe de validación, P-1), `Freezes`, `FreezeContextView` (paquete completo + `disclaimer`) y `ResolveFrozenDialog` (con `StepUpButton`; `resolution.ts` es la regla de la justificación) | BR-U10-12, 13 |
| `views/bias/` (U10-T04) | `DisparityTables` (la tabla de celdas con «muestra insuficiente»; `BiasDashboard` y `GrafanaEmbed` **no** existen) | BR-U10-15 |
| `styles.css` (U10-T04) | Una sola hoja, servida como archivo (la CSP de U2 tiene `style-src 'self'`); los estados con color **y** texto; contraste ≥ 4,5:1 | NFR-U10-42, 51 |

`version/` sigue vacío (la parte diferida: `version` y `VersionBanner`).

## 2. Cómo correrlo

Desde `vectra-risk/`, **en serie** (máquina compartida):

```bash
npm ci --ignore-scripts
npx playwright install chromium firefox          # una vez; a ~/.cache, sin sudo
make -C console check                            # lint + typecheck + BFF + vitest con cobertura + build + size-limit + Playwright (PoC, e2e, CSP y axe)
npm run -w console/spa test -- auth stepup inactivity   # filtros por ruta: tests/unit/<modulo>/, tests/property/<modulo>/ (views/cases, views/governance, views/bias)
npm run -w console/spa build && npm exec -w console/spa -- size-limit   # el build y el presupuesto del JavaScript inicial
npx playwright test -c console/spa/playwright.config.ts tests/poc tests/e2e tests/csp tests/a11y --project=chromium --project=firefox
```

- **Emisor OIDC de prueba y BFF con dobles** (P-1 (a)): `console/bff/tests/doubles/bff_oidc.py` (emisor bajo `/auth/realms/vectra/`) y
  `bff_e2e_server.py` (un solo proceso: el BFF real con los dobles de los cinco destinos + el emisor). `python console/bff/tests/doubles/bff_e2e_server.py`
  con `VECTRA_E2E_PORT` (nunca 8080 ni 8081) y `VECTRA_E2E_ORIGIN` (el origen público de la SPA, que es el `iss` de los tokens). Simplificaciones:
  el MFA se **simula** (`acr = mfa` si la solicitud pide `acr_values=mfa`, si no `pwd`), un cliente (`vectra-console`) con `/callback` y
  `/stepup-callback`, y `GET /auth/__e2e/stats` cuenta las llamadas por endpoint (la PoC lo usa para demostrar «cero canjes»). Prueba:
  `console/bff/tests/integration/test_bff_e2e_server.py`.
- **Un solo origen** (BR-U10-06): el servidor de Vite pasa `/auth/**` y `/api/**` al proceso de dobles. `vite.config.ts` lo hace en `server` y en `preview`
  cuando existe `VECTRA_E2E_PORT`; la PoC usa su propio `tests/poc/vite.poc.config.ts` (mismo proxy, y `/stepup-callback` → `tests/poc/stepup-callback.html`).
- **`playwright.config.ts`** (no está en el plan §1: se agregó): proyectos `chromium` y `firefox`, un `worker` (los contadores del emisor son del proceso), y los
  cuatro `webServer`: dos pares «dobles + servidor». El de la PoC (47173 y 47180: Vite en desarrollo) y el de la SPA real (47174 y 47181: **el build servido con `vite preview`**, con el
  mundo del recorrido, `VECTRA_E2E_DEMO=1`). Puertos: `VECTRA_E2E_SPA_PORT`, `VECTRA_E2E_PORT`, `VECTRA_E2E_APP_PORT` y `VECTRA_E2E_APP_DOUBLES_PORT` los cambian (nunca 8080 ni 8081).
- **El servidor de las pruebas con navegador** (`tests/e2e/vite.e2e.config.ts`, U10-T04, P-3 (a)): `vite build` + `vite preview` con **la misma configuración de build de `vite.config.ts`**
  (objetivos, sin polyfill de `modulepreload`, manifiesto), `/config.json` apuntando al emisor de prueba, `/auth/**` y `/api/**` al proceso de dobles, y **las cabeceras del perfil `spa` de U2
  leídas de `identity-edge/gateway/routes.yaml`** (`common` + `spa`): la CSP que recibe el navegador es la de U2. El servidor de desarrollo de Vite no sirve para esto: inyecta código en línea
  (React Refresh y HMR) que la CSP bloquearía sin que sea un defecto de la SPA.
- **Control solo de pruebas** (`bff_e2e_server.py`, `/__e2e/**`; no pasa por el proxy de la SPA, la prueba le habla al puerto de los dobles; el BFF real no lo tiene): `reset`, `down` (tumba un
  doble: `case`, `governance`, `registry`, `explainability` o `bias`), `force-mfa-required` (las próximas resoluciones de congelamiento dan 403 `mfa_required`: el 403 inesperado) y `count`
  (cuántas llamadas recibió un doble: «`record_explanation_view` una sola vez»). El mundo del recorrido está en `bff_e2e_world.py` (casos en cada estado, uno con `<script>` en `free_text`,
  modelos con informe, un congelamiento con el paquete completo y una celda `muestra_insuficiente`), construido y **validado** con los modelos de U0. Pruebas: `console/bff/tests/integration/test_bff_e2e_server.py`.
- **`make -C console e2e-spa`** falla con un mensaje que dice cómo instalar los navegadores si faltan (`scripts/check-browsers.mjs`); no se salta en silencio.
- No hay `config.json` de desarrollo: lo sirve el `ConfigMap` del chart (Paso 18, U10-T05) y el servidor de las pruebas con navegador trae el suyo.

## 3. Perfiles y semilla de las PBT (NFR-U10-62)

`tests/support/pbt.ts`: perfil `ci` (por omisión, **300 casos**) o `nightly` (**10 000**), elegido con `VECTRA_PBT_PROFILE=nightly`; la semilla se imprime en cada corrida
(`fast-check PBT-U10-05: perfil=ci numRuns=300 seed=…`) y `VECTRA_PBT_SEED=<n>` repite una corrida. PBT-U10-05 (`tests/property/stepup/`) usa `fc.commands`
(`maxCommands = 40`); PBT-U10-06 (`tests/property/i18n/`) corre `max(3 × pares, 300)` casos sobre todos los valores de los arreglos y de los textos. El perfil
`nightly` existe; su workflow (`console.yml`) está diferido (§3, fila «19 · 20»). `vite.config.ts` fija `silent: false`: sin eso el reportero por omisión oculta la semilla.

## 4. Diferido en los Pasos 10 a 16 (`demo-recorte-funcional.md`)

De los Pasos 13 a 16 (U10-T04): de cada vista diferida queda **solo su ruta con el marcador** «no disponible» (P-17; §8). Con su cita:

- **Paso 13** (§3, fila «13 Casos»): `ManualApplicationForm`, `PersistentFailures` con `retry` (P-16 sigue pendiente), `ApplicantSummaryButton`, `Dossier` (y su librería de PDF) e `IntegrityCheck`, con US-112, 402 y 403.
- **Paso 14** (§3, fila «14 Gobierno y sesgo»): `Policies`, `DataSources`, `PrePostReportView`, `DecideDataSourceDialog`, `RegisterModelForm`, `ApproveModelDialog`, el retiro y `GrafanaEmbed`; con US-201, 203, 205, 206, 306 y 307.
  **`BiasDashboard`** diferido con su ruta y el marcador (decisión del usuario, 2026-11-12, §6 P-14 «Solo el paquete»): el paquete de contexto de un congelamiento ya trae las tablas de disparidad,
  y las celdas insuficientes **sí** entran (`FreezeContextView`, BR-U10-15).
- **Paso 16** (§3, fila «4 · 16»): Stryker en `stepup`.
- **Paso 15:** la lista de chequeo manual por vista y NVDA (NFR-U10-51, segunda mitad) son del Paso 22, consolidado en U12 Paso 18; Lighthouse y la medida «bandeja → detalle p75 ≤ 1 s» (NFR-U10-04), de los Pasos 21 y 22.

De los Pasos 10 a 12 (U10-T03):

- **Paso 10:** la mitad con Keycloak de kind es el escenario 1 del Paso 22, consolidado en U12 Paso 18 (§8). La PoC corre contra el emisor de prueba.
- **Paso 12:** `version` y `VersionBanner` (BR-U10-21, P-U10-06; §3 fila «12» y §6 P-15). El reporte `chunk_load_failed` **sí** entra; el aviso con botón no.
  `app_version` es el `version` de `package.json` (`reporter/version.ts`, inyectado por `define`).
- Stryker (§3, fila «4 · 16»), `console.yml` y el workflow nocturno (fila «19 · 20»).

## 5. Qué error va a qué `error_code` (P-3 (a))

| Fuente | `error_code` |
|---|---|
| `ErrorBoundary` | `render_error` |
| `reportChunkLoadFailure()` (un `import()` de vista que no carga) | `chunk_load_failed` |
| `error` y `unhandledrejection` de `window` | `unhandled_rejection` |
| `securitypolicyviolation` | `csp_violation` |
| step-up que no termina (ventana bloqueada, cerrada, vencida, canje fallido o sin `acr = mfa`) | `stepup_failed` (el reenvío rechazado es un error de la acción, no del step-up: no se reporta) |
| 2xx que no es JSON, o error que no es un `Problem` | `api_contract_mismatch` |

## 6. Decisiones de esta mitad (respuestas a P-1 a P-7 y lo que apareció)

- **P-1 (a)**, **P-3 (a)**, **P-4 (a)**, **P-5 (a)**, **P-6 (a)**, **P-7 (a):** como recomendadas (ver arriba). P-4: PBT-U10-06 cubre los 17 arreglos; los enumerados de
  las vistas de T04 (estado de `ModelVersion`, acción de `Resolution`, `CellResult.status`, atributo y banda) están en `labels.es.json` y una prueba de ejemplo
  lee sus valores de `console-bff.yaml`; los de políticas y fuentes llegan con sus vistas (diferidas). P-5: ≥ 80 % de ramas sobre todo `src/` (se mide: ver §7).
- **P-2 (a):** el bloqueador de ventanas emergentes se enciende en los dos navegadores y la PoC pasa en **ambos** (no hay `fixme`). Para que exista en Chromium hay que usar
  `channel: "chromium"` (Chromium completo en el «nuevo» modo headless): el `chromium_headless_shell` que usa Playwright por omisión no trae el bloqueador. En Firefox basta
  `dom.disable_open_during_load = true`. `page.evaluate` da activación de usuario (5 s) en los dos: el caso abre la ventana al cargar la página, sin ninguna activación.
- **`window.open` en el clic (Paso 10, la puerta):** `createSigninRequest` es asíncrono, así que `StepUpFlow.start` abre una ventana **vacía** (`window.open("", nombre)`) en el
  manejador del clic y, con la URL de autorización, la navega (`location.replace`). La ventana conserva `window.opener` (mismo origen). P-U10-07 se mantuvo tal como está
  escrito: `OidcClient` de bajo nivel, `postMessage` validado en origen, ventana y `state`, canje en la ventana principal.
- **`oidc-client-ts` v3 y `acr`/`auth_time`:** la librería los quita de `profile` por omisión (`filterProtocolClaims`); `FILTER_PROTOCOL_CLAIMS` (`stepup/oidc.ts`) los deja pasar y lo usan
  el `OidcClient` del step-up y el `UserManager`. Tampoco genera `nonce` en el flujo de código: `createRequest` le pasa uno (`crypto.randomUUID()`) y la librería lo valida en el ID token.
  `UserManager.storeUser` solo guarda: el step-up usa `acceptStepUp` (`wiring.ts`), que además llama a `events.load` (rearma los temporizadores y avisa `userLoaded` para pedir `get_me`).
- **Login por redirección (decisión del usuario, 2026-11-12, tras la ronda 1):** la ronda 1 había hecho el login con `signinPopup` y `signinSilent` (iframe) porque BR-U10-05 y P-U10-07
  pedían todo en memoria y una redirección completa borra el `state` y el `code_verifier`. Eso contradecía tech-stack §2 y la tarea, y el iframe no puede cargar `/callback` bajo la CSP de U2
  (`frame-ancestors 'none'`). El usuario decidió: **`signinRedirect`**, con **solo el estado transitorio del flujo** (`state`, `code_verifier`, `nonce`; una clave `oidc.<state>` por flujo,
  que la librería borra al leer el callback, con éxito o con error) en `sessionStorage`, y los **tokens y el usuario en memoria**. La recarga es otra redirección con `prompt=none`; si el emisor
  responde `login_required` (o cualquier error) se muestra el login y no se vuelve a redirigir. `/callback` es la propia SPA (el canje ocurre en memoria y la URL se limpia con `replaceState`).
  `popup_redirect_uri` y `silent_redirect_uri` van vacíos (`""`): `oidc-client-ts` los iguala a `redirect_uri` si faltan; con `""` falla en vez de abrir una ventana o un iframe. El refresco
  automático usa el refresh token (la librería lo llama `signinSilent`, pero con refresh token no abre nada). **El step-up no cambia** (ventana emergente y `stateStore` en memoria).
  Diseño precisado: P-U10-07, tech-stack §2, BR-U10-05 y el Paso 11 del plan. **ESLint:** la prohibición de `sessionStorage` sigue, con **una** excepción por archivo
  (`src/auth/loginStateStorage.ts`, nombrado en `eslint.config.mjs`; `localStorage` sigue prohibido incluso ahí); el `grep` de CA-7 exige que `sessionStorage` aparezca solo en ese archivo.
  Pruebas: `session.test.tsx` (el `UserManager` real, con el almacenamiento leído en cada paso), `auth-provider.test.tsx` y, en navegador real (Chromium y Firefox), `tests/e2e/auth.spec.ts`
  (login → sesión; recarga → `prompt=none` → sesión sin interacción; sesión del emisor cerrada → login sin bucle; logout), con `localStorage` vacío, sin cookies de la SPA, sin IndexedDB y
  `sessionStorage` con a lo sumo la clave del flujo, sin tokens. Se sirve el bundle de producción (`vite preview`) en un segundo par servidor + dobles (47174 y 47181).
  Lo que **no** se probó: la CSP real de U2 (el Vite no la aplica; la prueba con el gateway es de U10-T04 y U12 Paso 18) ni Keycloak real.
- **React 19 y las dependencias:** `tech-stack-decisions.md` §2 dice «React 18»; se sigue con 19.3.1 (como en `main`). `react-aria-components` 1.22.1 declara `react ^19` y
  `@testing-library/react` 16.3.3 `^18 || ^19`. `jsdom` quedó en **31.0.0**, anclado en el `package.json` raíz (las 28.1.0 y 29.1.1 sirven en Node 22.17.1 pero no traen `CSS.escape`, que usa el `Modal` de `react-aria-components`; la 31.0.0 declara Node ≥ 22.22.2 y en 22.17.1 solo avisa `EBADENGINE`, y la suite corre tras un `npm ci --ignore-scripts` limpio; el CI usa `node-version: "22"`). `@playwright/test` 1.64.0 = el `playwright` del `pyproject.toml`.
- **Hallazgos de la ronda 2 que cambiaron el código:** (1) con el `document` de verdad, el `focusin` que el propio aviso de inactividad se da al abrirse contaba como actividad: el aviso se
  cerraba al instante y reiniciaba el contador (la prueba de la ronda 1 usaba un `EventTarget` falso). `attachActivity` recibe un filtro (`isWarningFocus`) y solo se ignora el `focusin` dentro
  del `alertdialog`. (2) El fallo tardío de la solicitud de un intento anterior del step-up terminaba el intento nuevo (el guardia por intento solo cubría el camino de éxito); ahora también
  se descarta. Lo encontró el modelo independiente de PBT-U10-05 (que no lee `flow.state` ni `busy()`; un comando compuesto `GoodStep` y otro `AbandonAndRetry` llegan al camino de éxito y a la
  solicitud tardía) y tiene su caso unitario en `flow.test.ts`. (3) `pbtOptions` recibe un piso (`atLeast`) en vez de pisar el perfil: `nightly` corre 10 000 casos y la línea impresa dice los que se corren.
- **Cobertura sin exclusiones:** `vite.config.ts` no tiene `exclude`; todo archivo de `src/` cuenta (incluido `main.tsx`, de 0 ramas).

## 7. Cobertura y pruebas

`npm run -w console/spa test -- --coverage`: umbral global de ramas 80 % y 100 % en `src/stepup/**` (NFR-U10-61). La tabla por archivo está en `bitacoras/U10-T03.md`.
Casos de las candidatas de ESLint: `tests/unit/eslint.test.ts` y `eslint-fixtures/` (`jsx-no-literals` con `ignoreProps`; los atributos que se ven o se leen —`aria-label`, `title`, `alt`,
`placeholder`…— los cubre `no-restricted-syntax`).

## 8. Tabla de rutas por rol (U10-T04; BR-U10-12)

Vive en un solo módulo (`src/views/shared/routes.ts`) y cada ruta nombra la operación de C03 de la que salen sus roles. La prueba `tests/unit/views/governance/routes-by-role.test.ts` la compara,
ruta por ruta, con la columna «Roles» de `component-methods.md` C03, **leída del archivo** (nunca con `REGISTRY` ni con la propia tabla). Una ruta a la que el rol no llega muestra «sin acceso» **sin montar
la vista** (ni cargar su fragmento) y sin llamar al BFF; el menú sale de `get_me` y de la tabla; `/` lleva al inicio del rol (`HOME`).

| Vista | Ruta | Operación de C03 | Roles | Estado |
|---|---|---|---|---|
| `CasesInbox` | `/casos` | `list_cases` | `analista`, `cro` | entra |
| `CaseDetail` | `/casos/:caseId` | `get_case` | `analista`, `cro` | entra |
| `ManualApplicationForm` | `/casos/nuevo` | `create_application` | `analista` | marcador |
| `PersistentFailures` | `/fallos` | `list_persistent_failures` | `cro` | marcador |
| `Dossier` | `/expedientes` | `get_dossier` | `cro`, `cumplimiento` | marcador |
| `IntegrityCheck` | `/integridad` | `run_integrity_check` | `cro` | marcador |
| `Models` | `/modelos` | `list_models` | `ingeniero_riesgo`, `cro`, `cumplimiento` | entra, de lectura |
| `ModelDetail` | `/modelos/:modelId` | `get_model` | `ingeniero_riesgo`, `cro`, `cumplimiento` | entra, de lectura |
| `Policies` | `/politicas` | `list_policies` | `analista`, `cro`, `cumplimiento` | marcador |
| `DataSources` | `/fuentes` | `list_data_sources` | `ingeniero_riesgo`, `cro`, `cumplimiento` | marcador |
| `BiasDashboard` | `/sesgo` | `get_disparity` | `cumplimiento`, `cro` | marcador (decidido) |
| `Freezes` | `/congelamientos` | `list_freezes` | `cumplimiento`, `cro` | entra |
| `FreezeContextView` | `/congelamientos/:freezeId` | `get_freeze` | `cumplimiento` | entra |

Inicio por rol: `analista` y `cro` → `/casos`; `ingeniero_riesgo` → `/modelos`; `cumplimiento` → `/congelamientos`. `/callback` y `/stepup-callback` son del realm de U2 (las atiende U10-T03).
`routeTemplate` (la plantilla que ve el `reporter`, P-7 de U10-T03) sale de esta tabla: `/casos/<uuid>` → `/casos/:caseId`; lo demás, `/{ruta}`.

## 9. Resumen de U10-T04 (Pasos 13 a 16)

**Vistas.** Bandeja (filtros de `CaseFilter` en la URL con lectura estricta —solo estados, canales conocidos, fechas y un entero—, «Ir al caso» por UUID, refresco de 15 s con la pestaña visible; **el refresco
no cuenta como actividad**: una prueba con el `InactivityMonitor` real ve el aviso a los 25 min tras ~96 refrescos), detalle (refresco de 3 s hasta 2 min mientras `en_evaluacion` o `en_sincronizacion`; estados con
color y texto; `free_text` como texto; `no_integrado`; marcas de baja confianza, `revision_requerida` y modelo congelado), panel de explicación (`record_explanation_view` **una vez por vista y solo con rol `analista`**; el CRO
abre el panel sin llamada; si la llamada falla el panel se muestra igual y se avisa), formulario de decisión (mismas reglas que el servidor; diálogo de confirmación; dos clics → una solicitud; 422 en su campo, 409 con
aviso y recarga, 503 con «el registro no responde»), modelos y su detalle con el informe, congelamientos (el CRO ve la lista sin enlace al paquete), paquete de contexto completo con el `disclaimer` siempre, y
`ResolveFrozenDialog` (tres acciones, justificación de 1 a 2000, aviso de `reactivar`, MFA con `StepUpButton` y `StepUpDialog`).

**La validación de la decisión** (`decision-validation.ts`) cuenta como el servidor: **puntos de código** (`[...texto].length`; un emoji es 1, no 2) y el `strip()` de Python (los 29 caracteres de `str.isspace()`,
que no son los de `trim()`: U+001C..U+001F y U+0085 los quita Python y no `trim()`; U+FEFF lo quita `trim()` y no Python), y rechaza más de 2000 caracteres **antes** de recortar (también en `sigue`). PBT-U10-04
(`tests/property/views/cases/decision.test.ts`) la compara con el oráculo de PBT-U8-03 transcrito (**P-2 (a)**: la tabla `COHERENT` y `oracle` en TypeScript, con los mismos generadores más los casos Python-vs-JavaScript; una
prueba lee `test_decision.py` como texto y exige las mismas 18 filas, y otra compara `pyStrip` con los 29 puntos de código calculados con Python).

**Extremo a extremo (Paso 15).** `tests/e2e/views.spec.ts` (las vistas en un navegador real), `session.spec.ts` (dos pestañas por `BroadcastChannel`, el foco < 1 s, los dobles de bias y de case caídos), `tests/csp/csp.spec.ts`
(la cabecera de U2 carácter por carácter y **cero** eventos `securitypolicyviolation` en el recorrido de los cuatro roles; el oyente se instala en el contexto antes de cargar nada y se prueba que ve una violación de verdad) y
`tests/a11y/a11y.spec.ts` (axe: cero `serious` y `critical` en cada parada). `tests/e2e/tour.ts` es el recorrido que comparten CSP y accesibilidad: bandeja, detalle en `listo`, `en_sincronizacion`, `decidido`, `modelo_congelado`,
`revision_requerida` y baja confianza, panel, formulario y diálogo de confirmación, modelos y su detalle, congelamientos, paquete de contexto, `ResolveFrozenDialog`, `StepUpDialog`, `InactivityDialog`, el marcador, «sin acceso» y
`ProblemMessage`. `index.html` sin `<script>` ni `<style>` en línea y `build.modulePreload.polyfill = false`; el JavaScript inicial se mide con `size-limit` (**gzip a propósito**: `size-limit` usa brotli por omisión, que da un
número menor; es gzip lo que sirve nginx) sobre el cierre del `index.html` (`.size-limit.mjs` lee el manifiesto de Vite: el entrada y lo que carga al arrancar, sin los fragmentos de las vistas ni `stepup-callback`).

**Respuestas a las preguntas de U10-T04** (todas como recomendadas): **P-1 (a)** `ModelDetail` muestra el informe que trae `get_model`, en lectura. **P-2 (a)** el oráculo de PBT-U10-04, transcrito (arriba). **P-3 (a)** el Paso 15 corre contra
el build y `vite preview` con las cabeceras de U2 (§2). **P-4 (a)** el `disclaimer` de `FreezeContextView` es un texto propio del catálogo (`bias_disclaimer`), igual a `DISCLAIMER` de U9 («mide y alerta, no certifica»); una prueba lee
`bias-monitoring/src/vectra_bias/dashboard.py` y los compara; el campo en el paquete queda como candidata de U0. **P-5 (a)** los defectos de U10-T03 que destapó el recorrido se corrigieron en su archivo, con su prueba y su rojo, sin
cambiar el flujo del step-up (abajo).

**Defectos de U10-T03 que destapó el recorrido (P-5)**
1. **El reenvío salía antes de instalar el token nuevo** (`stepup/oidc.ts` + `wiring.ts`). `exchange` devolvía `ok` sin esperar a `acceptStepUp` (`storeUser` + `events.load`, que pone el token en memoria): el reenvío llevaba el token
   viejo (sin MFA) y el BFF real contestaba 403 `mfa_required` otra vez («la acción no se pudo completar después de verificar tu identidad»). La PoC no lo veía (no llamaba al BFF). Ahora `accept` es asíncrono y el canje espera
   (`await accept(response)`); si instalar falla, el canje es `failed`. Prueba: `tests/unit/stepup/oidc.test.ts` (dos casos nuevos). El flujo (`machine.ts`, `flow.ts`) no cambió y `stepup` sigue en 100 % de ramas.
2. **`usePress` de react-aria inyecta un elemento de estilo** (`id="react-aria-pressable-style"`) la primera vez que se monta un botón, y la CSP de U2 (`style-src 'self'`) lo bloquea (`style-src-elem`). La biblioteca no inyecta nada
   si ya existe un elemento con ese id: `index.html` lo ocupa con un `<meta>` y la regla (`touch-action`) vive en `styles.css`. Prueba: `tests/csp` y `tests/unit/build-config.test.ts`.
3. (U10-T04, no de U10-T03) el `jsx-a11y/label-has-associated-control` falla con un `TypeError` (`minimatch` 11 por el `override` de la raíz) cuando una etiqueta contiene un elemento: por eso `Choice` asocia por `htmlFor`.

**Tres hechos del cable** que las vistas toleran: el BFF **omite** los campos nulos (`decision`, `recommendation`, `credit_status`, `rate`… no vienen como `null`): las vistas comparan con `== null`; una fecha sin hora (`window_from`)
se formatea en UTC (`formatDay`) para que no se corra al día anterior por la zona horaria; y los `Decimal4` son cadenas (`safeDecimal` los formatea con `Intl`, y si no son decimales los muestra tal cual).

**Dependencias nuevas, con versión exacta:** `react-router` 7.18.5 (la 8.5.1 pide Node ≥ 22.22 y la máquina tiene 22.17.1; la 7 acepta React ≥ 18), `@axe-core/playwright` 4.14.0, `size-limit` y `@size-limit/file` 12.1.0 (la 13 y la 14 piden Node ≥ 22.18 y 22.19).

## 10. Cobertura y pruebas de U10-T04

`npm run -w console/spa test -- --coverage`: umbrales en `vite.config.ts`: **100 %** de ramas en `src/stepup/**` y en `src/views/cases/decision-validation.ts`, **≥ 80 %** en el conjunto. Sin `exclude`. La tabla por archivo está en
`bitacoras/U10-T04.md`. `testTimeout` es de 20 s (la primera vista que se monta en cada archivo paga la carga de React Aria bajo la cobertura, y la máquina es compartida). Las pruebas de vistas montan `App` completa
(`tests/support/views-world.tsx`: los proveedores reales, el enrutador y un `fetch` falso que cuenta las solicitudes) y cargan los fragmentos de las vistas una vez al importar el soporte.

## 11. Lo que hizo U10-T05

- **La imagen** (`console/spa/Dockerfile`, `nginx.conf` y `Dockerfile.dockerignore`): dos etapas, `build` (Node 22 por digest, `npm ci --ignore-scripts` y el build de Vite) y la final (`nginx-unprivileged` por digest, usuario `101:101`), con `dist/` **sin** `.vite/manifest.json` (que solo lee `.size-limit.mjs`), sin Node, sin fuentes y sin mapas. `nginx.conf` sirve `/callback` y `/stepup-callback` con el fallback a `index.html` (rutas sin extensión), `config.json` desde el directorio donde el chart monta el `ConfigMap`, `no-store` en `index.html`, `config.json` y el fallback, `immutable` en `assets/` y `gzip`. **No** hay etapas `previous` ni etiqueta de digest anterior: se difieren con `version` (recorte funcional, P-15), que este documento daba por incluidas.
- **El chart** (`console/chart/spa`) genera el `config.json` desde sus values y lo monta como volumen completo, sin `subPath`; el `authority` y los dos `redirect_uri` salen del `hostname` de cada entorno y coinciden con el realm y el gateway de U2 (una prueba lo cierra, y `tests/unit/chart-config.test.ts` pasa cada `config.json` rendido por el `parseConfig` real). No hay `config.json` de desarrollo: lo sirve ese `ConfigMap` y el servidor de las pruebas con navegador trae el suyo.
- Quedan para U12 Paso 18, por necesitar el clúster: la CSP **real** del gateway (con el realm de Keycloak), el login y el step-up con Keycloak real, y la lista manual de accesibilidad con NVDA. Sigue diferido: k6, Lighthouse CI y `version`/`VersionBanner` (P-15). El detalle está en `evidence/cierre-demo.md`.
