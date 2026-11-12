# U10-T03 — SPA de `console`, acceso y base: puerta del step-up, sesión, inactividad, API, textos y `reporter`

**Unidad:** U10 `console` (`console-spa`)
**Historias que implementa** (plan §3):
- US-304, US-305 y US-203 en su mitad de sesión: el step-up con MFA que usan las aprobaciones y la resolución de un congelamiento (Pasos 10 y 11). Las vistas que lo usan son de U10-T04.
- US-602 y US-611 en la parte del navegador: tokens solo en memoria, inactividad, errores genéricos del catálogo y telemetría sin datos (Pasos 11 y 12).

Los Pasos 10 y 12 no tienen historia propia en la trazabilidad del plan (§3).

**Depende de:**
- **U10-T02 en `main`** (PR #142, ya fusionada; `main` en `7d05454`): `console_bff.app.build`, los dobles de `console/bff/tests/doubles/`, `console/Makefile` y `aidlc-docs/construction/console/code/bff-api.md`.
- **U10-T01 en `main`** (PR #139): `console/spa/` con `package.json`, `vite.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `src/config/{constants,load}.ts` y los directorios vacíos que esta tarea llena.
- U0 en `main`: `contracts/ts` (`createClient` de `openapi-fetch`, `src/generated/console-bff.d.ts`, los 17 arreglos de `src/enums.generated.ts`, `decimal.ts`), `contracts/tools/forbidden_phrases.py` y `contracts/tests/strategies/auth.py` (emisor de tokens de prueba).
- U2 en `main`, **solo como dato de las pruebas**: `identity-edge/keycloak/realm/realm.{kind,staging,prod}.yaml` (cliente `vectra-console`, `/callback` y `/stepup-callback`).
- **No** depende en runtime de Keycloak ni de U3, U4, U7, U8 o U9: todo corre con dobles (plan §1, «Dobles hasta que existan las unidades reales»; RL-5).

Sin clúster (AUTONOMIA-01) y sin base de datos.
**Rama:** `tarea/U10-T03`, desde `origin/main`.

Es la **primera mitad del Bloque E** del plan de U10 (`aidlc-docs/construction/plans/console-code-generation-plan.md`, Pasos 10 a 12).
- El Bloque E se partió en dos tareas por **decisión del usuario del 2026-11-12**: Pasos 10–12 aquí y Pasos 13–16 en U10-T04. Es la alternativa que `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 ya nombraba («U10 a 6 (E partido en 10–12 y 13–16)»), porque el bloque entero «pasaría de 2 rondas (RL-2)». U10 queda en **5 tareas**; la tabla de §8 todavía dice 4.
- Los Pasos 10 y 11 entran **completos** (E). `inactivity` se mantiene: §6, P-15, «Mantener `inactivity`, que es un control de seguridad y es pequeño».
- El Paso 12 entra **E\*F**: lo que la tabla §3 nombra como diferido va tachado, con la cita de su fila. Lo demás entra completo.
- **Las PBT no se recortan** (§5.2: «U10: PBT-U10-01..06»). Aquí entran la 05 y la 06, enteras.
- Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas y solo un ROJO bloquea.

Tareas que siguen en U10:
- **U10-T04**: segunda mitad del Bloque E, Pasos 13 a 16 (vistas de casos, vistas de gobierno y sesgo, CSP, accesibilidad, extremo a extremo y resumen). No se despacha si la puerta de esta tarea falla.
- **U10-T05**: F y el cierre, Pasos 17, 18, 21, 23 y 24. Los Pasos 19 y 20 están diferidos (§3, fila «19 · 20»: D) y el Paso 22 queda consolidado en U12 Paso 18 (enmienda §8).

---

## Alcance

**Dentro:** los Pasos 10 a 12 del plan. Va el texto del plan; lo tachado es lo que el recorte difiere, con su cita. Las rutas de los comandos se escriben completas desde `vectra-risk/` (ver Precisiones).

### Bloque E — SPA (primera mitad)

- [ ] **Paso 10 — Prueba de concepto del step-up (puerta de los Pasos 11–15)** (E)
  - Página mínima con un botón que, en su manejador de clic, llama a `OidcClient.createSigninRequest` (`prompt=login`, `max_age=0`, `acr_values=mfa`, `redirect_uri=/stepup-callback`, `stateStore` en `InMemoryWebStorage`) y a `window.open` de forma síncrona; `stepup-callback.ts` hace `postMessage({code, state}, location.origin)` y se cierra; la ventana principal valida origen, ventana y `state` y llama a `processSigninResponse`.
  - Diseño: P-U10-07; BR-U10-06; tech-stack (OIDC).
  - **Aceptación**: `npx playwright test console/spa/tests/poc` en Chromium y Firefox ~~contra Keycloak de kind (operador) y~~ contra un emisor OIDC de prueba en CI: el token nuevo trae `acr = mfa`; `sessionStorage` y `localStorage` vacíos; un `window.open` llamado fuera del clic queda bloqueado; un `postMessage` de otro origen se ignora. Si la prueba falla, se detiene el bloque y se revisa P-U10-07 antes de seguir.
    - Tachado: la mitad con Keycloak real es el escenario 1 del Paso 22, consolidado en U12 Paso 18 (enmienda §8). No es un recorte de esta tarea: nunca fue de CI.

- [ ] **Paso 11 — `auth`, `stepup` e `inactivity`** (E)
  - `auth`: `UserManager` con `InMemoryWebStorage`, login con PKCE, refresco rotativo, login silencioso (`prompt=none`), logout con `end_session_endpoint`.
  - `stepup`: el flujo del Paso 10 con el botón «Verificar y confirmar» (token sin MFA reciente) y `StepUpDialog` (403 `mfa_required` inesperado); reintento único con el mismo cuerpo; vencimiento de 5 min; anuncio `aria-live` y devolución del foco en < 1 s.
  - `inactivity`: contador de la sesión (`keydown`, `pointerdown`, `focusin`, `wheel`, `scroll`), difusión `activity` y `logout` por `BroadcastChannel`, aviso a los 25 min y logout a los 30.
  - Diseño: BR-U10-05, 06, 20; P-U10-07; NFR-U10-40, 41, 52.
  - **Aceptación**: `npm run -w console/spa test -- auth stepup inactivity` con reloj simulado: PBT-U10-05 (fast-check, stateful); actividad en la pestaña A durante 40 min con B quieta → sin logout; 30 min sin actividad → logout en las dos; el refresco de la bandeja no reinicia el contador;
    - (de esta tarea; «Verificación» de NFR-U10-40) 24 min → sin aviso; 25 min → aviso; «seguir» → reinicia; `wheel` y `scroll` cuentan como actividad; un formulario sin enviar no evita el cierre;
    - (de esta tarea; ejemplos del FD, business-logic-model §3) token sin MFA reciente → el botón dice «Verificar y confirmar» y `window.open` se llama de forma síncrona en ese clic; un 403 `mfa_required` inesperado → diálogo, y la ventana se abre en el clic de «Verificar identidad»; ventana bloqueada o cerrada sin terminar → sin reintento, con el formulario y su justificación intactos y el aviso «vuelve a confirmar»; un `postMessage` de otro origen o con otro `state` → ignorado, sin canje ni reintento;
    - (de esta tarea; ejemplo del FD) un aprobador sin MFA reciente confirma → 403 `mfa_required`, ventana emergente y reintento único con la misma justificación → 200. Aquí se prueba con un formulario de prueba dentro de `tests/`; con `ResolveFrozenDialog` y en el navegador lo prueba U10-T04.
    - «El refresco de la bandeja no reinicia el contador»: la bandeja es de U10-T04. Aquí se prueba con una consulta de TanStack Query que se refresca sola, que es el mecanismo; U10-T04 lo repite con la bandeja real.

- [ ] **Paso 12 — `api`, `i18n`, `reporter` y ~~`version`~~** (E\*F)
  - `api`: cliente `openapi-fetch` de U0 con timeout de 10 s y TanStack Query.
  - `i18n`: `messages.es.json` y `labels.es.json` con un texto por cada `code`, `reason` y valor de enumerado de U0 (arreglos constantes de `contracts/ts`); `Intl` en `es-CO`.
  - `reporter`: traducción al catálogo cerrado de `error_code`, ≤ 10 por minuto, `fetch` con `keepalive`, sin mensajes, trazas ni URL con parámetros.
  - ~~`version`: consulta de `version.json` cada 5 min y `VersionBanner`; mensaje con botón al fallar un fragmento; nunca recarga sola.~~
  - Diseño: BR-U10-17, 18, ~~21,~~ 22; ~~P-U10-06,~~ 09; NFR-U10-53.
  - **Aceptación**: `npm run -w console/spa test -- api i18n reporter` ~~`version`~~: PBT-U10-06; `uv run python contracts/tools/forbidden_phrases.py console/spa/src/i18n/*.json` en 0; 20 errores en un minuto → 10 envíos; ~~`version.json` distinto → aviso sin recarga~~.
    - Tachado: §3, U10, fila «12»: «`api`, `i18n` completo (PBT-U10-06) y `reporter`. Se difiere `version`/`VersionBanner` (P-15)»; §6, P-15: «Diferir `version`».

- **Del Paso 16 (U10-T04), la parte de `stepup`** (decisión del coordinador al partir la tarea, 2026-11-12): «Cobertura de ramas **100 %** en `stepup`» (NFR-U10-61) y la semilla y los perfiles de las PBT (NFR-U10-62) se exigen **aquí**, donde `stepup` se escribe y se prueba. El resto del Paso 16 (la validación de la decisión, el resumen `spa.md` completo y el umbral del conjunto) es de U10-T04. El alcance exacto del umbral del 80 % en esta tarea está en P-5.

### Precisiones

- **La puerta del Paso 10 (regla dura).**
  - El Paso 10 se hace **primero** y se confirma (commit) **antes** de escribir una línea de `src/auth/`, `src/inactivity/`, `src/api/`, `src/i18n/` o `src/reporter/`. CA-1 es la puerta y CA-2 comprueba el orden. Antes de ese commit solo pueden ir las dependencias, los navegadores, el emisor de prueba, `src/stepup/` y `src/stepup-callback.ts`.
  - La bitácora abre con la sección `## Puerta del Paso 10: PASA` o `## Puerta del Paso 10: FALLA`, con la salida real de CA-1 pegada y `uptime`.
  - **Si CA-1 falla y no hay arreglo dentro de P-U10-07 tal como está escrito, el codificador para.** No sigue con los Pasos 11 y 12, no cambia el diseño (nada de `signinPopup`, de redirección completa ni de guardar algo en `sessionStorage` para que pase) y no relaja la prueba. Entrega la rama con el Paso 10, la sección `FALLA` con qué línea de la aceptación falló, en qué navegador y qué probó, y lo reporta. Decide el usuario (plan, Paso 10: «se detiene el bloque y se revisa P-U10-07 antes de seguir»). U10-T04 no se despacha.
  - La puerta **falla** si en Chromium o en Firefox no se cumple alguna de estas tres: el token nuevo trae `acr = mfa`; nada en `sessionStorage` ni en `localStorage` (en ninguna de las dos ventanas); un `postMessage` de otro origen se ignora. La cuarta línea (ventana bloqueada fuera del clic) se rige por P-2.
  - Una prueba marcada `skip`, `fixme` u `only` en `tests/poc/` cuenta como fallo, salvo el caso exacto de P-2 (a).
- **Navegadores de Playwright (decidido por el usuario, 2026-11-12).** En la máquina del loop no están: no existe `~/.cache/ms-playwright`, no hay Chromium ni Chrome, y el Firefox 160 de `/usr/bin` no sirve (Playwright usa su propia compilación).
  - El codificador corre `npx playwright install chromium firefox`: descarga unos cientos de MB a `~/.cache/ms-playwright`, fuera del repositorio y **sin `sudo`**.
  - `@playwright/test` va en **1.64.0**, la misma versión que el `playwright` de Python del `pyproject.toml` raíz, para que U2 use los mismos navegadores.
  - **Si falta una librería del sistema** (lo dicen `npx playwright install --dry-run` y el primer arranque), **para y lo reporta**: `--with-deps` pide `sudo` y no se usa. Tampoco se cae a «solo Chromium»: incumple el Paso 10 y NFR-U10-50.
  - La bitácora pega la salida de la instalación y de `ls ~/.cache/ms-playwright`.
- **Rutas de la aceptación.** El plan escribe `npx playwright test console/spa/tests/poc` sin decir desde dónde. Los CA usan la forma que corre desde `vectra-risk/`: `npx playwright test -c console/spa/playwright.config.ts <filtro>`. Los filtros de vitest (`auth`, `stepup`, `api`…) casan con la ruta del archivo de prueba, así que las pruebas viven en `console/spa/tests/unit/<módulo>/` y `console/spa/tests/property/<módulo>/` con esos nombres.
- **Archivos que esta tarea crea o llena (plan §1, más lo que piden los pasos).** Se borra el `.gitkeep` de cada directorio que recibe archivos.
  - `console/spa/src/auth/`: el `UserManager`, `AuthProvider`, el callback de `/callback` y el logout.
  - `console/spa/src/stepup/`: el núcleo puro (máquina de estados del intento), `StepUpProvider`, el botón de confirmación con «Verificar y confirmar» y `StepUpDialog`. `console/spa/src/stepup-callback.ts` deja de estar vacío.
  - `console/spa/src/inactivity/`: el contador, `InactivityProvider` e `InactivityDialog`.
  - `console/spa/src/api/`: el cliente y el `QueryClient`. Los hooks por endpoint los agrega U10-T04 con cada vista; aquí solo van `get_me` y `report_client_error`.
  - `console/spa/src/i18n/`: `messages.es.json`, `labels.es.json` y el acceso tipado (`t(...)`, el texto de un `Problem`, formato con `Intl`).
  - `console/spa/src/reporter/`: el reportero único y `ErrorBoundary`.
  - `console/spa/src/main.tsx` y `App.tsx` (o los nombres que elijas), e `index.html` con la entrada: la detección de `/stepup-callback` y `/callback`, y los proveedores (`AuthProvider`, `StepUpProvider`, `InactivityProvider`, `ErrorBoundary`) alrededor de un contenido mínimo. `Layout`, `RoleMenu`, las rutas y las vistas son de U10-T04.
  - `console/spa/playwright.config.ts`, con los proyectos `chromium` y `firefox`. No está en §1: se agrega con una nota.
  - `console/spa/tests/poc/`: la página mínima y su especificación. `tests/unit/` y `tests/property/`: las de vitest.
  - `console/bff/tests/doubles/`: el emisor OIDC de prueba y el servidor del BFF con dobles para Playwright (P-1), con su prueba de Python.
  - `aidlc-docs/construction/console/code/spa.md`, con las secciones de esta mitad (P-6).
  - **Siguen vacíos** (con su `.gitkeep`): `src/views/{cases,governance,bias,shared}/`, `src/version/`, `tests/e2e/`, `tests/csp/` y `tests/a11y/`.
  - **No** se crean: `console/spa/stryker.conf.json` (diferido), `console/spa/nginx.conf` ni `console/spa/Dockerfile` (Paso 17, U10-T05), `console/spa/lighthouserc.json` (Paso 21).
- **Dependencias de npm.** Hoy `console/spa/package.json` solo trae React 19.3.1, `oidc-client-ts` 3.5.0 y las herramientas de U10-T01. Esta tarea agrega, **con versión exacta**, como en `contracts/ts/package.json`:
  - de ejecución: `@tanstack/react-query` y `react-aria-components` (tech-stack §2; sin CSS-in-JS en tiempo de ejecución). `openapi-fetch` y `decimal.js` llegan por `@vectra/contracts`: no se duplican.
  - de desarrollo: `fast-check` (la misma versión que `contracts/ts`, 4.10.2), `@vitest/coverage-v8` (la de vitest, 5.0.5), `@testing-library/react` y un DOM para vitest (`jsdom` o `happy-dom`), y `@playwright/test` 1.64.0.
  - React Router, `@axe-core/playwright` y `size-limit` los agrega U10-T04, que es quien los usa.
  - El lockfile es el `package-lock.json` raíz (P-2 de U10-T01). Elige versiones sin avisos altos: `npm audit --audit-level=high` va en CA-10.
- **El emisor OIDC de prueba y el servidor de dobles** (detalle en P-1).
  - El emisor es lo que la PoC necesita; el BFF con dobles es lo que U10-T04 usa en su recorrido. Los dos nacen aquí, en un solo proceso, para que la configuración de Playwright quede hecha.
  - No se usa `run_service`: sus puertos 8080 y 8081 son fijos y chocan con otros agentes (candidatas de U10-T02 sobre `test_service_shutdown.py`). Los puertos se eligen libres o por variable de entorno, nunca 8080 ni 8081.
  - La SPA y el emisor tienen que verse como **un solo origen** (BR-U10-06): el servidor de Vite pasa `/auth/**` y `/api/**` al proceso de dobles.
  - La PoC puede correr contra `vite preview` (el build) o contra el servidor de desarrollo. U10-T04 exige el build con la CSP de U2 (su P-3): conviene dejar `playwright.config.ts` armado para `vite build` + `vite preview` desde ya.
  - `workers` de Playwright acotado (2 como máximo): la máquina es compartida.
- **`auth` (BR-U10-05).**
  - `userStore` y `stateStore` en `InMemoryWebStorage`. Una prueba recorre login, refresco, login silencioso y logout y comprueba que `localStorage`, `sessionStorage` y `document.cookie` no cambian y que la URL queda sin `code` ni `state` después del callback.
  - Login: Authorization Code con PKCE (S256) y `redirect_uri` de `config.json` (`/callback`). Refresco con el refresh token, que rota. Recarga o pestaña nueva: `prompt=none`; sin sesión, login. Logout: borra la memoria y va al `end_session_endpoint`.
  - `get_me` se pide tras cada token nuevo; `SessionInfo` (`role`, `mfa`, `auth_time`, `locale`) vive en memoria.
- **`stepup` (BR-U10-06; P-U10-07).**
  - El núcleo es **puro**: una máquina de estados que recibe eventos (clic, mensaje, cierre, vencimiento, resultado del canje, respuesta del reintento) y devuelve efectos. No toca `window`, `fetch` ni el reloj: se inyectan. Es lo que recorre PBT-U10-05 y lo que lleva el 100 % de ramas.
  - «MFA reciente» se lee de `SessionInfo`: `mfa` y `auth_time` de hace ≤ 900 s. Los 900 s son `MFA_MAX_AGE` de U0 (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`, BR-U0-72): se agrega como constante a `constants.ts`, con una prueba que lee ese archivo y la ata, no como literal suelto. La tabla de domain-entities §4 no la trae: se anota como candidata de diseño.
  - Un intento a la vez. `state`, `nonce` y `code_verifier` se borran **siempre** al terminar, con éxito o sin él.
  - El reintento es **uno** y lleva exactamente el cuerpo original. Si el reintento falla (incluido otro 403), se muestra el error y no hay tercero.
  - `STEPUP_TIMEOUT_SECONDS` (300) sale de `constants.ts`.
  - `/stepup-callback`: la entrada de la SPA lo detecta **antes** de montar React y de crear el `UserManager`, y solo corre `stepup-callback.ts`. Esa página no canjea, no guarda nada y no pide `config.json`.
  - Anuncio `aria-live` al abrir la ventana; el foco vuelve al control que la abrió tras cerrarse (NFR-U10-52). Aquí se prueba que vuelve, con el DOM de vitest; la medida de «< 1 s» en un navegador real es de U10-T04.
- **`inactivity` (BR-U10-20).** Los cinco eventos; `BroadcastChannel("vectra-console")` con `{type: "activity"}` como máximo cada `ACTIVITY_BROADCAST_SECONDS` y `{type: "logout"}` **sin datos**; aviso a `IDLE_WARNING_SECONDS` y logout a `IDLE_LOGOUT_SECONDS`. Las respuestas de TanStack Query no tocan el contador. Una prueba exige que ningún mensaje del canal lleve otra clave que `type`. La prueba de Playwright con dos pestañas (verificación de NFR-U10-41) es de U10-T04.
- **`api` (P-U10-04; NFR-U10-33).**
  - `createClient<paths>` de `@vectra/contracts` con los tipos de `contracts/ts/src/generated/console-bff.d.ts`. `contracts/ts` **no se modifica**.
  - Timeout de `API_TIMEOUT_SECONDS` (10 s) por solicitud. **Ojo:** `console/bff/tests/unit/test_u10_candidates.py` (U10-T02) lee la línea `export const API_TIMEOUT_SECONDS = 10;` de `constants.ts` con una expresión regular: no cambies su forma.
  - TanStack Query **sin reintentos** (`retry: false` en consultas y mutaciones) y sin refresco al volver el foco: el BFF no reintenta y la SPA tampoco; un `GET` se vuelve a pedir en su siguiente refresco. El único reintento que existe es el del step-up.
  - El token va en `Authorization`. Un 403 con `code = mfa_required` se entrega a `stepup`; cualquier otro error llega a quien llamó como `Problem` (`code`, `reason?`, `correlation_id`).
- **`i18n` (BR-U10-17, 18; NFR-U10-53).**
  - PBT-U10-06 recorre **los 17 arreglos** de `contracts/ts/src/enums.generated.ts`, importados como módulo (no una lista escrita a mano): un arreglo nuevo en U0 rompe la prueba hasta que tenga textos. `PROBLEM_CODES` y `PROBLEM_REASONS` van a `messages.es.json`; los demás, a `labels.es.json`.
  - También exige que ningún texto de los dos catálogos contenga una frase de `contracts/forbidden-phrases.yaml`, con la misma normalización que `forbidden_phrases.py` (sin tildes y en minúsculas). El comando de Python de la aceptación corre además, tal cual.
  - Un `code` desconocido → el mensaje genérico con el `correlation_id`. Nunca se muestra `detail`.
  - Avisos de negocio en el mismo catálogo: `model_frozen_after_recommendation`, baja confianza, `revision_requerida`, caso anonimizado, crédito no integrado y crédito no disponible (BR-U10-07, 17). Las vistas que los muestran son de U10-T04; los textos nacen aquí («`i18n` completo»).
  - Fechas y números con `Intl` en `es-CO`. Los `Decimal4` son cadenas: se formatean sin pasar por `Number(` ni `parseFloat` (ESLint lo prohíbe); `Intl.NumberFormat.prototype.format` acepta la cadena decimal.
  - Los enumerados que **no** están en esos arreglos están en P-4.
  - U10-T04 agregará claves (los textos de sus vistas). El catálogo y sus pruebas deben admitirlo sin tocar la PBT.
- **`reporter` (BR-U10-22; P-U10-09).**
  - Un reportero único engancha `window.onerror`, `unhandledrejection`, `securitypolicyviolation` y el `ErrorBoundary`, y expone la función que reporta un fallo de carga de fragmento.
  - Envía `ClientErrorReport` y nada más: `error_code`, `route_template` (la **plantilla** de la ruta de la SPA, nunca la URL), `app_version` y, si lo hay, `correlation_id`. El BFF rechaza con 422 cualquier campo extra.
  - `app_version` tiene que ser SemVer (`^\d+\.\d+\.\d+$`). Con `version` diferido, sale de `version` de `console/spa/package.json`, inyectado en el build; una prueba lo comprueba contra ese patrón.
  - Ventana de 60 s con `REPORTER_MAX_PER_MINUTE` (10); los que sobran se descartan, no se encolan. `fetch` con `keepalive: true`. Sin token no se envía. Un fallo del envío no genera otro reporte.
  - El aviso «mensaje con botón al fallar un fragmento» es de `version` (BR-U10-21) y está diferido; el reporte `chunk_load_failed` **sí** entra.
  - Qué error va a qué `error_code`: P-3. De dónde sale `route_template` sin enrutador: P-7.
- **Cobertura y PBT (la parte del Paso 16 que entra aquí).**
  - Umbral en la configuración de vitest: 100 % de ramas en `src/stepup/**`. El del resto: P-5.
  - Ningún archivo de `src/` queda fuera con `exclude` para llegar al número; si alguno se excluye, `spa.md` dice cuál y por qué.
  - NFR-U10-62: PBT-U10-05 y PBT-U10-06 imprimen su semilla (como `contracts/ts/test/client.test.ts`) y tienen perfil `ci` y `nightly`, elegido por una variable de entorno; `spa.md` dice cuál es y cuántos casos corre cada uno.
- **`make -C console check`.** `lint-spa` y `test-spa` siguen; `test-spa` pasa a correr con cobertura y sus umbrales. Se agrega un objetivo (por ejemplo `e2e-spa`) que corre Playwright sobre `tests/poc` en los dos navegadores, y `check` lo incluye. U10-T04 lo amplía con el recorrido. Si los navegadores no están instalados, el objetivo falla con un mensaje que dice cómo instalarlos; no se salta en silencio. Todo en serie.
- **Trazabilidad.** Cada identificador que citan los Pasos 10 a 12 queda trazado en el código o en sus pruebas (`DECISIONES-LOOP.md` §6, enmienda del 2026-11-09).
  - Hoy (`main` en `7d05454`) fallan **30** identificadores de `console`. Esta tarea debe dejar trazados **9**: P-U10-07; NFR-U10-40, 41, 43, 52, 53, 61, 62 y 64. Quedan 21.
  - **Trampa:** `test_traceability.py` no lee archivos `.mjs`. NFR-U10-43, 53 y 64 ya están citados en `eslint.config.mjs` y aun así fallan: cítalos en un `.ts`, `.tsx` o `.json` (por ejemplo en `eslint.test.ts`, que esta tarea ya toca).
  - Los otros 6 de la SPA son de U10-T04: P-U10-08; NFR-U10-03, 42, 50, 51 y 63.
  - Quedan sin trazar hasta U10-T05, o están diferidos: INF-U10-02, 04, 05 y 06; NFR-U10-01, 04, 10, 12, 20, 21, 22, 44 y 45; P-U10-06 y 10.
- **Plan.** Marca `[x]` los Pasos 10 a 12, con `(U10-T03)` y, en el 12, «parcial: ver `tareas/U10-T03-spa-acceso-y-base.md`». En §1 agrega la nota de `spa/playwright.config.ts` y la de los archivos de `bff/tests/doubles/` del e2e. Los Pasos 13 a 16 quedan en `[ ]`.
- **Bitácora.** `bitacoras/U10-T03.md` lleva la salida **real** de cada comando, pegada como texto y con rutas absolutas a los logs. **Junto a toda medida de tiempo va `uptime`**, antes y después: duración de `make check`, de cada corrida de Playwright y cualquier timeout que falle.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Segunda mitad del Bloque E, Pasos 13 a 16 (U10-T04)**: todas las vistas (`CasesInbox`, `CaseDetail`, `DecisionForm`, `Models`, `Freezes`, `FreezeContextView`, `ResolveFrozenDialog`…), `Layout`, `RoleMenu`, la tabla de rutas por rol, el marcador de P-17, `ProblemMessage`, React Router, PBT-U10-04, el recorrido de CSP y accesibilidad, las pruebas de `tests/e2e`, `tests/csp` y `tests/a11y`, `size-limit`, `browserslist`, la carga a demanda y el resumen completo de `spa.md`.
- **Lo diferido por el recorte en estos pasos**: `version` y `VersionBanner` (cita arriba); Stryker (§3, U10, fila «4 · 16»: «Sin `mutmut` ni Stryker (T3)»).
- **Bloque F y el cierre (U10-T05)**: `Dockerfile` y `nginx.conf` de la SPA (Paso 17); el chart y el `ConfigMap` de `config.json` (Paso 18); k6, Lighthouse CI y la trazabilidad de cada BR con su lista de diferidos (Paso 21); `console/README.md` (Paso 23); el cierre y `evidence/cierre-demo.md` (Paso 24).
- **Candidata «`console/bff/tests/integration/test_clients.py:408-438` … F-01, NARANJA» (pool agotado; `CANDIDATAS.md`, línea 552), con destino «U10-T03 o U10-T04» según el arbitraje: va a U10-T05**, la tarea de despliegue y cierre, que vuelve a tocar `console/bff/`. Las dos tareas de la SPA no la arreglan.
- **Las demás candidatas de U10-T02 sobre el BFF**: puertos fijos de `test_service_shutdown.py` (F-02), `page_size` de `get_disparity` (F-03), `principal_role`, P-2, P-3, P-6, P-7 y P-8. Ninguna se toca.
- **Pasos 19 y 20, diferidos** (§3, fila «19 · 20»: D): no hay `console.yml`; la puerta es `make -C console check`. Tampoco el workflow nocturno con el perfil `nightly`: el perfil existe, no su workflow.
- **Paso 22**, consolidado en U12 Paso 18 (enmienda §8): la PoC con Keycloak real.
- **Cambios al BFF, a U0 o a U2.** No se toca `console/bff/src/`, ni `contracts/` (tampoco `contracts/ts`: ni arreglos nuevos), ni `identity-edge/` (el realm se lee, no se cambia).
- **Excepciones al lint**: nada de `// eslint-disable` para `react/no-danger`, almacenamiento o literales.
- **Estado fuera de la memoria**: nada en `localStorage`, `sessionStorage`, cookies ni IndexedDB. Sin WebSockets ni SSE (tech-stack §3).
- **La candidata «Bitácora de U10-T01 … F-04»**: es historia, no código.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/console-code-generation-plan.md` (§1 «Estructura de destino», Bloque E: Pasos 10 a 12 y 16, §3)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1.2, §2, §3 U10, §4, §5.2, §6 P-15, §8)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6, RL-1 a RL-5)
- `aidlc-docs/construction/console/functional-design/business-rules.md` (BR-U10-05, 06, 17, 18, 20, 22)
- `aidlc-docs/construction/console/functional-design/business-logic-model.md` (§1, §2.1, §2.2, §3: PBT-U10-05, 06 y los ejemplos)
- `aidlc-docs/construction/console/functional-design/frontend-components.md` (§1: los proveedores; §4)
- `aidlc-docs/construction/console/functional-design/domain-entities.md` (§2, §3, §4)
- `aidlc-docs/construction/console/nfr-requirements/nfr-requirements.md` (NFR-U10-34, 40, 41, 43, 52, 53, 61, 62, 64) y `tech-stack-decisions.md` (§2, §3)
- `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md` (P-U10-07, 09) y `logical-components.md`
- `aidlc-docs/construction/console/code/bff-api.md` (U10-T02: endpoints, `get_me`, `client-errors`) y `bff-logic.md`
- `console/Makefile`, `console/spa/{package.json,vite.config.ts,tsconfig.json,eslint.config.mjs,index.html}`
- `console/spa/src/config/{constants,load}.ts`, `console/spa/src/stepup-callback.ts` y `console/spa/tests/unit/{config,eslint}.test.ts` con `eslint-fixtures/`
- `console/bff/src/console_bff/app.py` (`build(urls, authenticator=, transports=, clock=)`) y `console/bff/tests/doubles/{bff_doubles,bff_builders,bff_world,bff_tokens,bff_support}.py` (U10-T02)
- `console/bff/tests/unit/test_u10_candidates.py` (lee `constants.ts`) y `console/bff/pytest.ini`
- `contracts/ts/package.json`, `contracts/ts/src/{index,enums.generated,decimal}.ts`, `contracts/ts/src/generated/console-bff.d.ts` y `contracts/ts/test/client.test.ts` (semilla de fast-check)
- `contracts/openapi/console-bff.yaml`
- `contracts/tools/forbidden_phrases.py` y `contracts/forbidden-phrases.yaml`
- `contracts/tests/strategies/auth.py` (`KEY`, `token`, `jwks_document`)
- `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py` (`MFA_MAX_AGE`) y `models/api.py` (`SessionInfo`, `ClientErrorReport`)
- `identity-edge/keycloak/realm/realm.kind.yaml` (cliente `vectra-console`)
- `pyproject.toml` raíz (versión de `playwright`), `package.json` raíz y `package-lock.json`
- `bitacoras/U10-T01.md`, `bitacoras/U10-T02.md`, `revisiones/U10-T01/ronda-1.md` y `revisiones/U10-T02/{ronda-1,arbitraje-ronda-1}.md`
- `DECISIONES-LOOP.md` (§6) y `CANDIDATAS.md` (líneas 537, 539, 541, 551 y 552)
- `tareas/U10-T04-spa-vistas-y-e2e.md` (la otra mitad: qué espera de esta)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`, **en serie**, anotando `uptime` antes y después. Antes del primero: `npm ci --ignore-scripts` y `npx playwright install chromium firefox`.

Estado al redactar (2026-11-12, `origin/main` en `7d05454`, con U10-T02 fusionada):
- **CA-9 se corrió** con `python3 -B platform/tests/test_traceability.py --unit console --all`: 30 líneas «sin trazabilidad», que incluyen las 9 de esta tarea.
- **Comprobado con comandos de solo lectura:** no existe `~/.cache/ms-playwright`; no hay Chromium ni Chrome; `@playwright/test`, `@tanstack/react-query`, `react-aria-components`, `@vitest/coverage-v8`, Testing Library y `jsdom` no están en `package-lock.json`. `src/` solo tiene `config/` y los `.gitkeep`; `console/bff/tests/doubles/` no tiene emisor OIDC.
- **No se corrieron** los demás (el worktree de redacción no tiene `node_modules`). Por lo anterior, hoy fallan porque el código no existe: CA-1 a CA-6 (sin configuración de Playwright, sin el módulo de Python, sin archivos de prueba que casen con el filtro, sin proveedor de cobertura) y CA-8 (falta `spa.md`).
- CA-7 pasa hoy en su mitad de `lint` y `typecheck` y falla en los casos nuevos de `eslint.test.ts`. CA-10 **pasa hoy** (revisión de U10-T02, rc 0) y debe seguir pasando con los objetivos nuevos.

- [ ] **CA-1** — La puerta: prueba de concepto del step-up (Paso 10; P-U10-07; BR-U10-06).
  ```bash
  uptime; npx playwright test -c console/spa/playwright.config.ts tests/poc --project=chromium --project=firefox --reporter=list; echo "rc=$?"; uptime
  ```
  Esperado: `rc=0`, sin pruebas saltadas, con las cuatro líneas de la aceptación en cada navegador (8 casos como mínimo): el token nuevo trae `acr = mfa`; `sessionStorage.length` y `localStorage.length` en 0 en la ventana principal y en la emergente; `window.open` fuera del clic bloqueado; `postMessage` de otro origen ignorado (sin canje: el emisor de prueba cuenta cero llamadas a su endpoint de token). **Rojo primero:** con `window.open` movido a después de un `await`, el caso «se abre en el clic» falla; con la comprobación de `event.origin` quitada, el caso del otro origen falla.

- [ ] **CA-2** — La puerta se respetó (Paso 10: «se detiene el bloque»).
  ```bash
  grep -n "^## Puerta del Paso 10: " bitacoras/U10-T03.md; poc=$(git log --reverse --format=%H origin/main..HEAD -- console/spa/tests/poc | head -1); resto=$(git log --reverse --format=%H origin/main..HEAD -- console/spa/src/auth console/spa/src/inactivity console/spa/src/api console/spa/src/i18n console/spa/src/reporter | head -1); test -n "$poc" && test "$poc" != "$resto" && git merge-base --is-ancestor "$poc" "${resto:-HEAD}" && echo PUERTA-EN-ORDEN; git diff --stat origin/main..HEAD -- console/spa/src/auth console/spa/src/inactivity console/spa/src/api console/spa/src/i18n console/spa/src/reporter | tail -1; git diff --stat origin/main..HEAD -- console/spa/src/views | tail -1
  ```
  Esperado: una sola línea de bitácora, `PASA` o `FALLA`, y `PUERTA-EN-ORDEN` (el primer commit de la PoC es anterior al primero que toca `auth`, `inactivity`, `api`, `i18n` o `reporter`). Con `PASA`, la línea siguiente resume los archivos de los Pasos 11 y 12. Con `FALLA`, esa línea sale **vacía**: no hay nada de los Pasos 11 y 12, y la tarea se entrega así. La última línea sale vacía siempre: `src/views/` no se toca en esta tarea.

- [ ] **CA-3** — El emisor OIDC de prueba y el BFF con dobles (P-1; soporte de los Pasos 10 y 15).
  ```bash
  uv run pytest console/bff/tests/integration/test_bff_e2e_server.py -v
  ```
  Esperado: código 0. Casos: descubrimiento y JWKS; PKCE (un `code_verifier` equivocado → error); el `nonce` vuelve en el ID token; `prompt=none` sin sesión → `login_required`; `prompt=login` con `acr_values=mfa` → `acr = mfa` y `auth_time` nuevo; el refresh rota y el reusado se rechaza; `end_session`; un token del emisor sirve en `GET /api/console/me` del BFF con dobles → 200 con el rol del usuario de prueba; el proceso no escucha en 8080 ni en 8081. Si el archivo se llama distinto, se ajusta y se anota.

- [ ] **CA-4** — `auth`, `stepup` e `inactivity` (Paso 11; BR-U10-05, 06, 20; NFR-U10-40, 41, 52).
  ```bash
  npm run -w console/spa test -- auth stepup inactivity
  ```
  Esperado: código 0, con la semilla de fast-check impresa. PBT-U10-05 entera (stateful; las siete clases de evento de business-logic-model §3 y sus cinco invariantes) y un caso por cada línea de aceptación del Paso 11, incluidas las marcadas «(de esta tarea)». **Rojo primero:** con el reintento permitido dos veces, PBT-U10-05 encuentra una secuencia con dos envíos; con la consulta que se refresca reiniciando el contador, el caso de inactividad falla.

- [ ] **CA-5** — `api`, `i18n` y `reporter` (Paso 12; BR-U10-17, 18, 22; P-U10-09; NFR-U10-53).
  ```bash
  npm run -w console/spa test -- api i18n reporter && uv run python contracts/tools/forbidden_phrases.py console/spa/src/i18n/*.json; echo "rc=$?"
  ```
  Esperado: `rc=0` y ninguna línea «frase prohibida». Casos:
  - PBT-U10-06 sobre los 17 arreglos, con la semilla impresa;
  - 20 errores en un minuto → exactamente 10 envíos, y ninguno lleva una clave fuera de `ClientErrorReport` ni una `route_template` con `?` o con un identificador;
  - un `code` desconocido → el mensaje genérico con el `correlation_id`;
  - el timeout de 10 s corta la solicitud, y un 503 produce **una** solicitud (sin reintento);
  - los enumerados de P-4 tienen su texto.

  **Rojo primero:** con una clave borrada de `labels.es.json`, PBT-U10-06 falla y nombra el valor; con una frase de `forbidden-phrases.yaml` en un mensaje, fallan la PBT y el comando de Python (código 1).

- [ ] **CA-6** — Cobertura de `stepup` (Paso 16, la parte que entra aquí; NFR-U10-61, 62).
  ```bash
  npm run -w console/spa test -- --coverage
  ```
  Esperado: código 0, con los umbrales en la configuración de vitest: 100 % de ramas en `src/stepup/**` y, según P-5 (a), ≥ 80 % de ramas en el resto de lo que esta tarea escribe. La bitácora pega la tabla por archivo. **Rojo primero:** con un caso de `stepup` quitado, el comando sale distinto de 0 y nombra el archivo.

- [ ] **CA-7** — Lint, tipos y las candidatas de ESLint (NFR-U10-43, 53, 64; ver «Notas»).
  ```bash
  npm run -w console/spa lint && npm run -w console/spa typecheck && npm run -w console/spa test -- eslint && ! grep -rnE "eslint-disable|dangerouslySetInnerHTML|localStorage|sessionStorage" console/spa/src
  ```
  Esperado: código 0 y el `grep` sin salida. `eslint.test.ts` tiene además: un fixture por `parseFloat`, `Number.parseFloat`, `sessionStorage` global y `globalThis.localStorage`, y cada uno falla con su regla; un componente con `role`, `id`, `htmlFor` y `href` literales pasa limpio; un literal de texto visible sigue fallando con `react/jsx-no-literals`. El caso lento ya no depende del timeout de 5 s de vitest.

- [ ] **CA-8** — Documentación, plan y estructura.
  ```bash
  test -s aidlc-docs/construction/console/code/spa.md && grep -cE "^- \[x\] \*\*Paso 1[0-2] .*U10-T03" aidlc-docs/construction/plans/console-code-generation-plan.md; grep -cE "^- \[ \] \*\*Paso 1[3-6] " aidlc-docs/construction/plans/console-code-generation-plan.md; for d in auth stepup inactivity api i18n reporter; do test -n "$(find console/spa/src/$d -type f ! -name .gitkeep | head -1)" || echo "VACIO $d"; done; for f in console/spa/playwright.config.ts console/spa/src/i18n/messages.es.json console/spa/src/i18n/labels.es.json; do test -s $f || echo "FALTA $f"; done; test ! -e console/spa/stryker.conf.json && test ! -e console/spa/Dockerfile && test ! -e console/spa/nginx.conf && echo OK
  ```
  Esperado: imprime `3` (los Pasos 10 a 12 marcados con `(U10-T03)`) y `4` (los Pasos 13 a 16 siguen sin marcar), ninguna línea `VACIO` ni `FALTA`, y `OK`. Si la marca `(U10-T03)` no queda en la misma línea del paso, el `grep` se ajusta y se anota.

- [ ] **CA-9** — Trazabilidad, con la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit console --all | grep -E "^(P-U10-07|NFR-U10-(40|41|43|52|53|61|62|64)):" ; uv run python platform/tests/test_traceability.py --unit console --all | grep -c "sin trazabilidad"; uv run python platform/tests/test_traceability.py --all | grep "sin trazabilidad" | sort > /tmp/u10-t03-rama.txt
  ```
  Esperado: el primer `grep` no imprime nada y el conteo de `console` baja de 30 a **21**. El archivo se compara con la misma corrida sobre la base de la rama: no hay ninguna línea nueva y las 9 de arriba ya no están. El revisor corre `--all` en la base y en la rama.

- [ ] **CA-10** — `check` de la unidad (RL-4) y de U0, porque el diff cambia el lockfile de npm.
  ```bash
  uptime; make -C console check; echo "console rc=$?"; uptime; make -C contracts check; echo "contracts rc=$?"; uptime; npm audit --audit-level=high; echo "audit rc=$?"
  ```
  Esperado: `rc=0` en los tres, **en serie**. `console check` incluye ya la cobertura de la SPA y la PoC en los dos navegadores. Si `bench_gate` de `contracts` falla por carga, se anota con la carga y una corrida aislada en la rama y en la base.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `console/spa/tests/poc/`: la página mínima y las cuatro líneas de la puerta, en los dos navegadores.
- `console/bff/tests/doubles/` y `console/bff/tests/integration/test_bff_e2e_server.py`: el emisor, el servidor y los casos de CA-3.
- `console/spa/tests/unit/auth/`, `stepup/` e `inactivity/`, y `console/spa/tests/property/stepup/` (PBT-U10-05).
- `console/spa/tests/unit/api/`, `i18n/` y `reporter/`, y `console/spa/tests/property/i18n/` (PBT-U10-06).
- `console/spa/tests/unit/eslint.test.ts` y `eslint-fixtures/`: los casos de las candidatas.
- `console/spa/tests/unit/config.test.ts`: el caso de la constante de los 900 s contra `MFA_MAX_AGE`.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U10-T03.md`, con la salida pegada. Como mínimo los de CA-1 (los dos), CA-4 (reintento doble y contador), CA-5 (clave borrada y frase prohibida) y CA-6 (caso quitado). El par falla-pasa es la prueba.

Reglas de las pruebas:
- Reloj simulado en vitest para todo lo que espera (5 min, 25 y 30 min, 60 s del `reporter`, 10 s del timeout). Ninguna prueba unitaria duerme de verdad.
- En Playwright no hay `waitForTimeout` fijo: se espera por estado.
- Las pruebas de vitest de componentes necesitan un DOM: `vite.config.ts` pasa a incluir `*.test.tsx` y el entorno de DOM solo donde hace falta.
- Los nombres de los módulos de prueba de Python nuevos no chocan con los de otras unidades (candidata F-06 de U07-T03): llevan el prefijo `bff_`, como los de U10-T02.

---

## Preguntas abiertas

**Ya decidido por el usuario (2026-11-12), no es pregunta:** el Bloque E se parte en 10–12 y 13–16; los navegadores los instala el codificador con `npx playwright install chromium firefox` (ver Precisiones).

Ninguna de las que siguen necesita decisión previa: si no hay respuesta, rige la recomendación.

- **P-1 — El emisor OIDC de prueba y el BFF con dobles para Playwright.** El plan dice «un emisor OIDC de prueba en CI» y «el BFF con dobles», sin decir en qué se escriben ni dónde viven.
  - **(a) Recomendada:** en Python, en `console/bff/tests/doubles/`, en un solo proceso: el BFF real (`console_bff.app.build` con los transportes de `bff_doubles` y `bff_world.populate`) y un emisor mínimo bajo `/auth/realms/vectra/` que firma con la llave de `contracts/tests/strategies/auth.py`. Sirve descubrimiento, JWKS, autorización (con una página de formulario sin scripts para elegir usuario de prueba), token con PKCE, refresh rotativo, `end_session`, `prompt=none`, `prompt=login`, `max_age` y `acr_values`. Lo arranca `webServer` de Playwright. Se agrega una nota a §1.
  - (b) En Node, en `console/spa/tests/`. Duplica la emisión de tokens de U0 y obliga a otro juego de dobles del BFF.
- **P-2 — «Un `window.open` llamado fuera del clic queda bloqueado» bajo automatización.** Playwright suele arrancar los navegadores con el bloqueador de ventanas emergentes apagado.
  - **(a) Recomendada:** la prueba lo enciende (en Chromium, sin el argumento `--disable-popup-blocking`; en Firefox, con la preferencia `dom.disable_open_during_load`). Si en uno de los dos no hay forma de encenderlo bajo automatización, ese caso se marca `fixme` **solo en ese navegador**, con el motivo, se anota en la bitácora y en `CANDIDATAS.md` para U12 Paso 18, y la puerta cuenta como pasada si las otras tres líneas pasan en los dos y esta pasa en uno. Lo que el código garantiza se prueba aparte y siempre: `window.open` se llama de forma síncrona dentro del manejador.
  - (b) Exigirla en los dos o parar. Puede detener el bloque por un límite de la herramienta, no del diseño.
- **P-3 — Qué error va a qué `error_code`.** P-U10-09 da las fuentes y el catálogo de seis, no la correspondencia.
  - **(a) Recomendada:** `ErrorBoundary` → `render_error`; fallo de un `import()` de vista → `chunk_load_failed`; `window.onerror` y `unhandledrejection` → `unhandled_rejection`; `securitypolicyviolation` → `csp_violation`; step-up que no termina (ventana bloqueada, cerrada, vencida, canje fallido o sin `acr = mfa`) → `stepup_failed`; una respuesta 2xx que no es JSON, o un error que no es un `Problem` → `api_contract_mismatch`. Se documenta en `spa.md`.
  - (b) Reportar solo los cuatro que tienen fuente explícita. Dos series del BFF no se moverían nunca.
- **P-4 — Enumerados que no están en los arreglos de `contracts/ts`.** domain-entities §3 pide en `labels.es.json` los «estados de modelo, política y fuente», pero esos son `Literal` de `models/governance.py` y no están entre los 17 arreglos de `enums.generated.ts`, que es lo que el Paso 12 nombra.
  - **(a) Recomendada:** PBT-U10-06 cubre los 17 arreglos. Para los enumerados que muestran las vistas que entran en U10-T04 (estado de `ModelVersion`, acción de `Resolution`, `CellResult.status`, atributo y banda), una prueba de ejemplo lee sus valores de `contracts/openapi/console-bff.yaml` y exige un texto por valor. Los de políticas y fuentes llegan con sus vistas, que están diferidas. Queda como candidata de U0 (generar esos arreglos).
  - (b) Agregar los arreglos a la generación de `contracts/ts`. Es un cambio de U0.
- **P-5 — Qué cobertura se exige aquí, además del 100 % de `stepup`.** El Paso 16 («100 % en `stepup` …, ≥ 80 % en el resto») está en U10-T04; al partir, el coordinador fijó que el 100 % de `stepup` se exige aquí.
  - **(a) Recomendada:** además, ≥ 80 % de ramas sobre todo `src/` ya en esta tarea. Lo que existe de `src/` al cerrarla es lo que ella escribe (`auth`, `inactivity`, `api`, `i18n`, `reporter`, la entrada). Si no, U10-T04 hereda una deuda de pruebas de código que no escribió, además de sus vistas.
  - (b) Solo el 100 % de `stepup`; el 80 % del resto se mide por primera vez en U10-T04.
- **P-6 — `spa.md` en dos entregas.** El Paso 16 pide el «resumen en `spa.md`», y es de U10-T04; pero esta tarea necesita dejar escrito cómo correr los dobles y qué decidió.
  - **(a) Recomendada:** esta tarea crea `spa.md` con sus secciones: módulos y qué regla cubre cada uno; cómo correr la SPA con Vite, el emisor y los dobles; perfiles y semilla de las PBT; lo diferido de los Pasos 10 a 12 con su cita; la correspondencia de P-3; y las respuestas a P-1 a P-7. U10-T04 lo completa y lo cierra como resumen del Paso 16.
  - (b) Dejarlo todo para U10-T04 y documentar esto solo en la bitácora. U10-T04 tendría que reconstruirlo.
- **P-7 — `route_template` sin enrutador.** El `reporter` envía la plantilla de la ruta, pero React Router y la tabla de rutas llegan en U10-T04.
  - **(a) Recomendada:** el `reporter` recibe por inyección una función que devuelve la plantilla actual. Aquí la entrada le pasa una que conoce `/`, `/callback` y `/stepup-callback` y devuelve una plantilla fija para lo demás; U10-T04 la sustituye por la del enrutador. Nunca se usa `location.pathname` tal cual.
  - (b) Agregar React Router ya en esta tarea. Adelanta la tabla de rutas sin sus vistas.

---

## Notas

- **Orden de trabajo.** (1) dependencias, navegadores y el emisor de prueba; (2) Paso 10 y su commit; (3) las candidatas de ESLint, antes de escribir JSX; (4) Paso 11; (5) Paso 12; (6) cobertura, `spa.md` y `check`.
- Archivos que se **modifican en su sitio**:
  - `console/spa/{package.json,vite.config.ts,tsconfig.json,eslint.config.mjs,index.html}`, `console/spa/src/stepup-callback.ts`, `console/spa/src/config/constants.ts` (solo para agregar la constante de los 900 s) y `console/spa/tests/unit/{eslint,config}.test.ts`;
  - `package-lock.json` raíz, y `package.json` raíz solo si hace falta un `override`;
  - `console/Makefile` y `console/bff/pytest.ini` si las pruebas nuevas de `doubles/` lo piden;
  - `aidlc-docs/construction/plans/console-code-generation-plan.md` (casillas y notas de §1);
  - `CANDIDATAS.md`.

  Nada de duplicados con sufijo. `console/bff/src/` no cambia. `.size-limit.json` no se toca (U10-T04).
- **Candidatas de `CANDIDATAS.md` que esta tarea atiende** (números de línea en `main`, `7d05454`):
  - línea 537: «**U10, `console/spa/eslint.config.mjs:23` (revisor, U10-T01, ronda 1, F-01, AMARILLO).** `jsx-no-literals` con `noStrings` también prohíbe atributos (`role`, `id`, `htmlFor`, `href`). NFR-U10-53 habla de texto visible. Usar `ignoreProps: true` o `allowedStrings` antes de los Bloques D-E (U10-T03)». Se ajusta la regla y se fija con los dos casos de CA-7. Ojo: los atributos que **sí** son texto visible o leído (`aria-label`, `title`, `alt`, `placeholder`) tienen que seguir saliendo del catálogo; si `ignoreProps` los deja pasar, se cubren con otra regla o con una prueba.
  - línea 539: «U10, fixtures de ESLint (revisor, U10-T01, ronda 1, F-03, AMARILLO): faltan casos para `parseFloat`, `Number.parseFloat`, `sessionStorage` global y `globalThis.localStorage`». Se agregan los cuatro fixtures.
  - línea 551: «U10, `console/spa/tests/unit/eslint.test.ts` (codificador, U10-T02): con la máquina cargada (carga 13 a 20) el caso `dangerously-set-inner-html.tsx falla con react/no-danger` pasó del timeout de 5 s de vitest (5137 ms, ESLint en frío) … Subir el `testTimeout` de ese archivo es de U10-T03». Se sube el timeout **de ese archivo** (no el global) o se comparte una instancia de `ESLint` entre casos; se anota la medida con `uptime`.
  - línea 541, «`SPA_API_TIMEOUT_SECONDS` … F-05»: **ya la atendió U10-T02**. Aquí solo hay que no romper su prueba (ver `api`).

  Cada una se marca resuelta en `CANDIDATAS.md` citando esta tarea. Las candidatas nuevas (P-2 si aplica, P-4, la constante de los 900 s y lo que aparezca) se agregan al final.
- **Trampas conocidas.**
  - `tech-stack-decisions.md` §2 dice «React 18», pero `main` tiene React 19.3.1 desde U10-T01. Se sigue con 19; comprueba que `react-aria-components` y Testing Library lo admiten antes de fijar versiones, y anótalo en `spa.md`.
  - `oidc-client-ts`: `signinPopup` está prohibido (P-U10-07). El step-up usa `OidcClient` de bajo nivel, con su propio `stateStore` en memoria.
  - `window.open` tiene que salir en la misma tarea síncrona del clic: `createSigninRequest` es asíncrono. El Paso 10 existe para resolver exactamente eso sin romper BR-U10-06; si no se puede, es la puerta.
  - U10-T04 va a servir esta SPA con la CSP de U2 (`script-src 'self'; style-src 'self'; frame-src 'self'; connect-src 'self'; require-trusted-types-for 'script'; trusted-types 'none'`). Lo que se escriba aquí no puede depender de estilos o scripts en línea ni de `innerHTML`: estilos con CSS Modules, diálogos de React Aria sin `style` en línea, login silencioso y emisor en el mismo origen. Un defecto de este tipo lo encontraría U10-T04, ya tarde.
  - TanStack Query reintenta tres veces por omisión y refresca al volver el foco: las dos cosas rompen «sin reintentos» y «el refresco no cuenta como actividad» si no se configuran.
  - `BroadcastChannel` existe en Node, pero dos «pestañas» en vitest son dos instancias del módulo en el mismo proceso: cierra los canales al terminar cada caso o vitest no sale.
  - Los 30 min de inactividad son los de `ssoSessionIdleTimeout` del realm (`config.test.ts` ya los ata). No los cambies.
  - Bajo carga, Playwright en dos navegadores tarda. Un timeout se anota con `uptime` y se repite aislado; no se suben los tiempos de espera sin anotarlo.
- PBT-U10-01..06 nunca se recortan. En esta tarea entran la 05 y la 06, enteras. La 01 (U10-T02) y la 02 y la 03 (U10-T01) ya están; la 04 es de U10-T04.
- Máquina compartida (8 núcleos, 14 GiB, varios agentes a la vez): las suites largas (`make -C console check`, `make -C contracts check`, Playwright y la cobertura) van **en serie**, nunca dos a la vez, con `uptime` antes y después. Si una corrida pasa más de 2 horas sin avanzar, se detiene, se anota y se repite.
