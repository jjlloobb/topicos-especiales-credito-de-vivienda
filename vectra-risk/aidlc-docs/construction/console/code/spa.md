# `console-spa` — resumen del código (U10, primera mitad del Bloque E)

Entrega de **U10-T03** (Pasos 10 a 12 del plan). **U10-T04** completa este archivo con las vistas, la CSP, la accesibilidad, el extremo a
extremo y lo que cierra como «resumen del frontend» del Paso 16. Aquí: qué módulos hay y qué regla cubre cada uno, cómo se corre todo, las
decisiones de esta mitad y lo que el recorte difiere.

## 1. Módulos (`console/spa/src/`)

| Módulo | Qué hace | Reglas |
|---|---|---|
| `config/` | `config.json` (`load.ts`) y constantes del código (`constants.ts`, con `MFA_MAX_AGE_SECONDS` = `MFA_MAX_AGE` de U0, atada por una prueba) | INF-U10-03; BR-U10-06 |
| `stepup/` | `machine.ts` (núcleo **puro**: máquina de estados del intento), `flow.ts` (la ventana, los temporizadores y el cliente OIDC inyectados), `oidc.ts` (`OidcClient` de bajo nivel con su propio `stateStore` en memoria), `mfa.ts` («MFA reciente»), `StepUpProvider`, `StepUpButton` («Verificar y confirmar») y `StepUpDialog` («Verificar identidad») | BR-U10-06; P-U10-07; NFR-U10-52, 61, 62; PBT-U10-05 |
| `stepup-callback.ts` | `postMessage({code, state}, location.origin)` al opener y se cierra; no canjea, no guarda nada y no pide `config.json` | BR-U10-06 |
| `auth/` | `UserManager` con `InMemoryWebStorage` (`manager.ts`), `AuthProvider`/`TokenStore` (login silencioso al montar, `get_me` tras cada token nuevo) y `callback.ts` (`/callback`) | BR-U10-05; NFR-U10-40 |
| `inactivity/` | `monitor.ts` (contador de la sesión, cinco eventos, `BroadcastChannel("vectra-console")`), `InactivityProvider` e `InactivityDialog` | BR-U10-20; NFR-U10-40, 41 |
| `api/` | `client.ts` (`createClient<paths>` de `@vectra/contracts`, token, timeout de 10 s, sin reintentos, `ApiError`/`MfaRequiredError`/`TransportError`), `queryClient.ts` (TanStack Query sin reintentos ni refresco por foco), `endpoints.ts` (`get_me`) | P-U10-04; NFR-U10-33 |
| `i18n/` | `messages.es.json` (códigos, motivos, avisos, interfaz), `labels.es.json` (enumerados) y `index.ts` (`ui`, `notice`, `label`, `problemText`, `formatDate`, `formatDecimal` con `Intl` es-CO) | BR-U10-17, 18; NFR-U10-53; PBT-U10-06 |
| `reporter/` | `reporter.ts` (catálogo cerrado de `error_code`, ≤ 10 por minuto, `keepalive`, sin mensajes ni URL), `ErrorBoundary`, `version.ts` (`app_version`) | BR-U10-22; P-U10-09; NFR-U10-34 |
| `entry.ts`, `main.tsx`, `wiring.ts`, `App.tsx` | La entrada detecta `/stepup-callback` y `/callback` **antes** de montar React y de crear el `UserManager`; `wiring.ts` arma todo desde `config.json`; `App` pone los proveedores alrededor de un contenido mínimo | BR-U10-05, 06 |

`views/`, `version/` siguen vacíos (T04 y el recorte).

## 2. Cómo correrlo

Desde `vectra-risk/`, **en serie** (máquina compartida):

```bash
npm ci --ignore-scripts
npx playwright install chromium firefox          # una vez; a ~/.cache, sin sudo
make -C console check                            # lint + typecheck + BFF + vitest con cobertura + Playwright (PoC)
npm run -w console/spa test -- auth stepup inactivity   # filtros por ruta: tests/unit/<modulo>/, tests/property/<modulo>/
npx playwright test -c console/spa/playwright.config.ts tests/poc --project=chromium --project=firefox
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
  dos `webServer` (dobles y Vite). Puertos por omisión 47173 (SPA) y 47180 (dobles); `VECTRA_E2E_SPA_PORT` y `VECTRA_E2E_PORT` los cambian. U10-T04 lo amplía con el
  recorrido (`vite build` + `vite preview` con la CSP de U2).
- **`make -C console e2e-spa`** falla con un mensaje que dice cómo instalar los navegadores si faltan (`scripts/check-browsers.mjs`); no se salta en silencio.
- No hay `config.json` de desarrollo: lo sirve el `ConfigMap` del chart (Paso 18, U10-T05) y el recorrido de U10-T04 trae el suyo.

## 3. Perfiles y semilla de las PBT (NFR-U10-62)

`tests/support/pbt.ts`: perfil `ci` (por omisión, **300 casos**) o `nightly` (**10 000**), elegido con `VECTRA_PBT_PROFILE=nightly`; la semilla se imprime en cada corrida
(`fast-check PBT-U10-05: perfil=ci numRuns=300 seed=…`) y `VECTRA_PBT_SEED=<n>` repite una corrida. PBT-U10-05 (`tests/property/stepup/`) usa `fc.commands`
(`maxCommands = 40`); PBT-U10-06 (`tests/property/i18n/`) corre `max(3 × pares, 300)` casos sobre todos los valores de los arreglos y de los textos. El perfil
`nightly` existe; su workflow (`console.yml`) está diferido (§3, fila «19 · 20»). `vite.config.ts` fija `silent: false`: sin eso el reportero por omisión oculta la semilla.

## 4. Diferido en los Pasos 10 a 12 (`demo-recorte-funcional.md`)

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
- **Login interactivo en ventana emergente (no redirección):** BR-U10-05 manda `stateStore` y `userStore` en memoria; una redirección completa recarga la página y borra el `state` y el
  `code_verifier`, así que el login por redirección **no puede terminar**. El login interactivo usa `signinPopup` (abierta de forma síncrona en el clic de «Iniciar sesión»; callback
  `/callback` abierta por la ventana emergente) y el login silencioso usa `signinSilent` (iframe con `prompt=none`; `/callback` dentro de un iframe). La ventana principal nunca cambia de URL.
  Es una desviación de la letra de «login con PKCE… `redirect_uri` `/callback`» que el plan no preveía: se registra como candidata de diseño.
- **React 19 y las dependencias:** `tech-stack-decisions.md` §2 dice «React 18»; se sigue con 19.3.1 (como en `main`). `react-aria-components` 1.22.1 declara `react ^19` y
  `@testing-library/react` 16.3.3 `^18 || ^19`. `jsdom` quedó en **28.1.0** (la 31.0.0 pide Node ≥ 22.22.2 y la máquina tiene 22.17.1). `@playwright/test` 1.64.0 = el `playwright` del `pyproject.toml`.
- **Cobertura sin exclusiones:** `vite.config.ts` no tiene `exclude`; todo archivo de `src/` cuenta (incluido `main.tsx`, de 0 ramas).

## 7. Cobertura y pruebas

`npm run -w console/spa test -- --coverage`: umbral global de ramas 80 % y 100 % en `src/stepup/**` (NFR-U10-61). La tabla por archivo está en `bitacoras/U10-T03.md`.
Casos de las candidatas de ESLint: `tests/unit/eslint.test.ts` y `eslint-fixtures/` (`jsx-no-literals` con `ignoreProps`; los atributos que se ven o se leen —`aria-label`, `title`, `alt`,
`placeholder`…— los cubre `no-restricted-syntax`).

## 8. Pendiente de U10-T04

Vistas, `Layout`, `RoleMenu`, rutas, `ProblemMessage`, PBT-U10-04, CSP y Trusted Types, accesibilidad, `tests/e2e`, `size-limit`, la medida de «foco < 1 s» y de las dos pestañas en un
navegador real, el resumen completo y el umbral del conjunto.
