# Ronda 1 — U10-T03

VEREDICTO: NO-VERDE

Hay dos ROJO. El primero: con una instalación limpia del lockfile (`npm ci --ignore-scripts`, el paso que la tarea manda dar antes de los CA), CA-4, CA-5, CA-6 y el `test-spa` de CA-10 fallan. El segundo: el rojo primero de CA-4 no se reproduce con la prueba que está en el commit. La puerta del Paso 10 sí pasa, y pasa de verdad en los dos navegadores.

Revisé la rama `tarea/U10-T03` en HEAD `af64f40` contra la base `ab80f4c`. El blob de la tarea es `65f5134d…` y coincide. Todo lo corrí en serie, con `uptime` antes y después de cada medida.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | El de CA-1, 6 corridas seguidas (16:17–16:20, carga de 7,6 a 17,3) | **pasa**: 6 de 6 con rc=0, 60 de 60 casos, 0 saltados, 0 fallos. No hubo `address already in use`. En `tests/` no hay `skip`, `fixme` ni `only` |
| 2 | La cadena de CA-2 | **pasa**: `PASA`, `PUERTA-EN-ORDEN` (`a143250` va antes de `c793337`), 20 archivos y `src/views` vacío |
| 3 | `uv run pytest …test_bff_e2e_server.py -v` | **pasa**: 15 passed (16:29, carga 15) |
| 4 | `npm run -w console/spa test -- auth stepup inactivity` | **falla** tras `npm ci`: rc=1 por `Cannot find package 'jsdom'` y 9 archivos que no arrancan, entre ellos PBT-U10-05. Con jsdom 31 en la raíz: 122 passed |
| 5 | La cadena de CA-5 | **falla** tras `npm ci` (rc=1). Con jsdom 31: 51 passed, y `forbidden_phrases.py` sale en 0 |
| 6 | `… test -- --coverage` | **falla** tras `npm ci` (rc=1, 9 archivos KO). Con jsdom 31: rc=0, 100 % de ramas en `src/stepup` y 97,4 % en total. Hay umbrales en `vite.config.ts` y no hay `exclude` |
| 7 | La cadena de CA-7 | **pasa**: lint, tipos y 15 casos de ESLint; el `grep` no saca nada |
| 8 | La cadena de CA-8 | **pasa**: `3`, `4`, `OK` |
| 9 | `test_traceability.py --all` en la base (`git archive`) y en la rama | **pasa con nota**: `console` baja de 30 a **20**; 75 líneas en la base y 65 en la rama; 0 nuevas; desaparecen las 9 pedidas más NFR-U10-50 (ver F-06) |
| 10 | `make -C console check`, `make -C contracts check`, `npm audit` | **falla** tras `npm ci` (`test-spa` es CA-6). Con jsdom 31: console rc=0 en 3 min 11 s (carga 8→17,7), contracts rc=0 en 2 min 54 s y audit con 0 vulnerabilidades |

## Hallazgos

### F-01 · ROJO · `vectra-risk/package-lock.json` (jsdom) · CA-4, 5, 6 y 10 · La evidencia verde no sale del lockfile del diff
- El lockfile deja `jsdom` 28.1.0 anidado en `console/spa/node_modules/`. En la raíz queda una entrada vieja `node_modules/jsdom` 31.0.0 marcada `dev/optional/peer`, que `npm ci` no instala.
- `vitest` está en la raíz y no encuentra ninguno de los dos. Fallan al arrancar `stepup.test.ts`, `flow.test.ts`, `stepup-ui`, `auth-provider`, `session`, `inactivity-ui`, `monitor`, `error-boundary` y `app.test`.
- `npm-i-dev.log` del codificador muestra que instaló jsdom 31.0.0 con `EBADENGINE`. Repetí eso con `npm install --no-save jsdom@31.0.0` (`md5sum` del lockfile y de los `package.json` sin cambios) y todo pasa. O sea, el verde de la bitácora corrió con jsdom 31 en un Node que esa versión no soporta, no con la 28.1.0 que la bitácora declara.
- La 28.1.0 enlazada en la raíz tampoco sirve tal cual: falla en 4 casos con `Cannot read properties of undefined (reading 'escape')`.
- Arreglo: un lockfile limpio con jsdom en la raíz que funcione en Node 22.17.1. Y en la bitácora, `npm ci --ignore-scripts` justo antes de cada verde.

### F-02 · ROJO · `console/spa/tests/property/stepup/stepup.test.ts` · CA-4 «rojo primero» · El rojo de la PBT no se reproduce con el diff
- Apliqué la misma mutación de la bitácora (dos `send` tras `exchanged ok`) con `VECTRA_PBT_SEED=12345`, que es la semilla del log `ca4-rojo-reintento-doble.log`. La PBT del commit **pasa**, en dos corridas.
- Con semillas aleatorias, PBT-U10-05 encuentra el reintento doble en 4 de 8 corridas. Sin borrar el `state` tras un canje bueno (invariante 4), lo encuentra en 1 de 5.
- Los generadores casi nunca llegan a `done`. Los unitarios (`flow`, `machine`, `stepup-ui`) sí matan las dos mutaciones siempre. Pero la PBT es lo que promete CA-4, y la salida pegada es de una versión anterior de la prueba.
- Arreglo: dar más peso al camino de éxito o un comando compuesto, y volver a sacar el rojo con la prueba del commit.

### F-03 · NARANJA · `src/auth/manager.ts`, `AuthProvider.tsx` · Login con `signinPopup` en lugar de redirección: decide el usuario
- **¿Es irrealizable con redirección?** Sí, con las reglas tal como están. P-U10-07 y tech-stack §2 piden «`InMemoryWebStorage` para el login», y la tarea prohíbe `sessionStorage` (ESLint y el `grep` de CA-7 lo hacen cumplir). Una redirección completa borra `state` y `code_verifier`. Solo hay una lectura que la permite: BR-U10-05 restringe únicamente los *tokens*, así que guardar el estado transitorio en `sessionStorage` cumpliría su letra, pero choca con la tarea y con P-U10-07. Es una contradicción del diseño, no un error del diff.
- **Lo que sí es del diff:** tech-stack §2 («No se usa `signinPopup`») y la Trampa de la tarea («`signinPopup` está prohibido») lo prohíben de forma explícita. El motivo de esa prohibición no aplica a oidc-client-ts 3.5.0 sin DPoP (lo leí en `node_modules`):
  - `PopupNavigator.prepare` abre la ventana con `window.open` de forma síncrona en el clic;
  - la ventana emergente solo hace `notifyOpener`, y el canje ocurre en la principal;
  - la validación del mensaje en la librería es más floja (acepta si coincide la ventana **o** el `state`), pero en el login `processSigninResponse` vuelve a validar el `state`.

  Había una alternativa que cumplía todo dentro del mismo diff: el patrón `OidcClient` + `StepUpFlow`. Es defendible en el fondo, pero contradice una decisión escrita sin haberla consultado.
- **CSP de U2 y riesgo para U12 Paso 18:**
  - Con `frame-src 'self'` no hay problema, y no hay cookies de terceros porque todo es un solo origen.
  - Con COOP `same-origin` se conserva `window.opener`.
  - El problema está en el login silencioso: el iframe vuelve a `/callback`, que se sirve con el perfil `spa`, y ese perfil trae `frame-ancestors 'none'` y `X-Frame-Options: DENY` (`identity-edge/gateway/routes.yaml:73-76`, ruta `spa` en las líneas 118-129). En kind y en producción, `signinSilent` será rechazado: cada recarga esperaría el timeout de la librería (10 s) y mostraría el login, y BR-U10-05 («recargar → `prompt=none`») no se cumpliría.
  - Ningún diseño en memoria se libra de esto. La candidata del codificador lo diagnostica mal: habla de enmarcar `/auth/**` (que ya admite `'self'`), cuando el problema es `/callback`.
  - Nada lo prueba en un navegador real: el login emergente y el iframe solo se ejercitan con navegadores falsos en jsdom, y el Vite de la PoC no aplica CSP.

### F-04 · NARANJA · `tests/unit/inactivity/monitor.test.ts:199-225` · «El refresco no reinicia el contador» pasa en vacío
- La prueba arma su propio `new QueryClient` y no usa `createQueryClient()` ni `InactivityProvider`. El rojo del codificador mutó la prueba, no el código.
- Mi mutante V6 en `src/api/queryClient.ts` (`QueryCache.onSuccess` dispara `focusin`) **sobrevive** a los 229 casos.

### F-05 · NARANJA · `tests/property/i18n/i18n.test.ts:38,61` · El perfil `nightly` no cambia nada en PBT-U10-06, y la línea impresa miente
- `{...pbtOptions(), numRuns: Math.max(...)}` pisa el perfil. Con `VECTRA_PBT_PROFILE=nightly` imprime `numRuns=10000`, pero corre 350 casos (y en `ci` imprime 300). Eso incumple NFR-U10-62.
- Además muestrea con reemplazo sobre 175 textos: en teoría puede saltarse uno. Mi medida: 12 de 12 detecciones de una frase prohibida.

### F-06 · AMARILLO · `console/spa/playwright.config.ts:1` · NFR-U10-50 queda trazado por adelantado
- La cita es medio legítima: los proyectos de Chromium y Firefox son la mitad de su verificación. La otra mitad, `browserslist`, es de U10-T04.
- El trazador ya lo da por cumplido, así que U10-T04 pierde esa señal y su cuenta baja de 21 a 20. Conviene que el CA de `browserslist` de T04 lo compruebe aparte.

### F-07 · AMARILLO · `tests/poc/poc.ts:27-34` · El instrumento `inClick` mide «dentro del despacho del clic», no «síncrono»
- `window.open` dentro de una microtarea sobrevive a la PoC en los dos navegadores.
- Si se abre después de `crypto.subtle.digest`, sobrevive en Chromium y muere en Firefox.
- `flow.test.ts` sí mata la versión de la microtarea (V10).

### F-08 · AMARILLO · `stepup.test.ts:100-110, 75` · El modelo de PBT-U10-05 no es del todo independiente
- Decide qué mensaje es «válido» y qué `start` cuenta leyendo `flow.state.phase` y `busy()` del código bajo prueba.
- Las invariantes (conteos, `secrets`, ventanas, almacenamiento) sí son propias. PBT-U10-06 es independiente: importa los 17 arreglos de U0.

## La puerta del Paso 10, línea por línea (mutaciones en una copia `git archive`)
- **`acr = mfa`:** real. Hay canje con `processSigninResponse`, se valida el `nonce` y el emisor cuenta 1 llamada al token.
- **Almacenamiento vacío:** se comprueba en las dos ventanas y en el callback suelto.
- **Bloqueador:** apagarlo (sin `ignoreDefaultArgs` ni la preferencia de Firefox) hace fallar el caso en Chromium y en Firefox, así que estaba encendido. Sin `channel: "chromium"` (con el headless shell) también falla, lo que confirma lo que dice el codificador.
- **Otro origen:** quité la comprobación de `event.origin` y muere en los dos navegadores (`failed:exchange`).

## Mutaciones propias en vitest (suite completa; transcripción en `mut/summary.txt`)
- **Mueren:**
  - el reintento doble (solo unitarios; la PBT, a medias: F-02);
  - sin comprobar `state` y sin comprobar el origen (PBT y unitarios);
  - sin borrar el `state` tras el canje y con `removeState` vacío;
  - `userStore` en `localStorage`;
  - una clave de i18n borrada (PBT y unitario);
  - una frase prohibida (PBT y Python con rc=1);
  - el `reporter` con un campo `message`, con la URL cruda, sin `keepalive` o con 11 envíos por minuto;
  - el callback con `postMessage` a `"*"`;
  - el «MFA reciente» sin mirar `auth_time`;
  - sin comprobar `acr`.
- **Sobreviven a vitest, pero los mata el lint (CA-7):** el token en `sessionStorage` y el `stateStore` del step-up en `sessionStorage` (`no-restricted-properties`).
- **Sobrevive a todo:** V6 (F-04).

## Alcance y dependencias
- `src/views` está vacío. No se tocan `console/bff/src`, `contracts/`, `identity-edge`, el chart, Dockerfile, nginx ni los workflows. Los dobles van en `console/bff/tests/doubles/`.
- El commit de la puerta (`a143250`) solo trae dependencias, el emisor, `src/stepup*`, `tests/poc` y configuración.
- Las dependencias son las que nombra la tarea, con versión exacta (`@tanstack/react-query` 5.107.1, `react-aria-components` 1.22.1, `fast-check` 4.10.2, `@vitest/coverage-v8` 5.0.5, `@testing-library/react` 16.3.3 + `dom` 10.4.2, `jsdom` 28.1.0, `@playwright/test` 1.64.0), salvo la entrada vieja de jsdom 31.0.0 en la raíz (F-01).
- `npm audit --audit-level=high` pasa.

## Tareas candidatas (defectos reales fuera de alcance)
- U2/U12: `frame-ancestors 'none'` y `X-Frame-Options: DENY` en `/callback` impiden el login silencioso en iframe que BR-U10-05 necesita estando todo en memoria. Hace falta un perfil o una ruta de callback silencioso con `frame-ancestors 'self'`, y probarlo en U12 Paso 18. Hay que corregir la candidata actual, que habla de `/auth/**`.
- Diseño U10: decidir el mecanismo del login interactivo y actualizar tech-stack §2 y P-U10-07 (F-03).
- U10-T04: probar en un navegador real el login emergente y la recarga (`prompt=none`) bajo la CSP de U2.

## Estado al terminar
- **Worktree:** `git status --short` vacío. Dejé `node_modules` en el estado exacto del lockfile (un `npm ci` final), así que F-01 se reproduce corriendo CA-4 directamente.
- **Procesos y puertos:** `ps` y `ss` no muestran navegadores, Vite, `bff_e2e_server` ni vitest vivos, y no hay nada escuchando en 47170–47289. Solo queda el Edge de otra sesión, abierto desde las 10:55.
- **Cuota de `/tmp`:** un `npm ci` en la copia de mi scratchpad llenó la cuota del tmpfs (`EDQUOT`). Borré solo mis propios archivos: la copia y la extracción de la base.

## Rutas de transcripciones largas
`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t03-r1/`, y dentro:
- `ca1-run1..6.log`, `ca4.log`, `ca6-clean-ci.log`, `ca4-j31.log`, `ca6-j31.log`, `ca10-console.log`, `ca10-contracts.log`
- `mut-M1-origin.log`, `mut-M2-blocker-off.log`, `mut-M3-headless-shell.log`, `mut-M4b-open-after-digest.log`
- `mut/summary.txt`, `mut/V1-pbt-seed12345-b1.log`, `trace-base.txt`, `trace-rama.txt`

```
VEREDICTO: NO-VERDE
ROJO|vectra-risk/package-lock.json (jsdom) · CA-4, CA-5, CA-6, CA-10|Con npm ci limpio vitest no encuentra jsdom; el verde salió de jsdom 31 instalado a mano
ROJO|console/spa/tests/property/stepup/stepup.test.ts · CA-4|El rojo de PBT-U10-05 (semilla 12345) no se reproduce; detecta el reintento doble en 4 de 8 corridas
NARANJA|console/spa/src/auth/manager.ts|signinPopup prohibido por tech-stack §2 y la tarea; iframe silencioso bloqueado por frame-ancestors 'none' en /callback (U2)
NARANJA|console/spa/tests/unit/inactivity/monitor.test.ts:199|La prueba del refresco no toca createQueryClient ni InactivityProvider; el mutante V6 sobrevive
NARANJA|console/spa/tests/property/i18n/i18n.test.ts:38|numRuns pisa el perfil: nightly no cambia nada y la línea impresa miente (NFR-U10-62)
AMARILLO|console/spa/playwright.config.ts:1|NFR-U10-50 trazado por adelantado; la mitad de browserslist es de U10-T04
AMARILLO|console/spa/tests/poc/poc.ts:27|inClick mide el despacho del clic, no la sincronía (la microtarea sobrevive a la PoC)
AMARILLO|console/spa/tests/property/stepup/stepup.test.ts:100|El modelo de PBT-U10-05 lee la fase del código bajo prueba
INFORME: revisiones/U10-T03/ronda-1.md
```
