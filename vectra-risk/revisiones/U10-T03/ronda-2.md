# Ronda 2 — U10-T03

VEREDICTO: VERDE

Corrí yo mismo los diez criterios, con la enmienda del arbitraje, y todos pasan. Los dos ROJO de la ronda 1 están cerrados: F-01 pasa tras un `npm ci --ignore-scripts` limpio, y F-02 mata las dos mutaciones en 10 de 10 corridas con semillas mías. Los tres NARANJA (F-03, F-04 y F-05) también están cerrados: los comprobé con mutantes en navegador real y en vitest. No queda ningún ROJO ni NARANJA. Quedan cuatro AMARILLO, que no bloquean.

Revisé la rama en HEAD `ba2c3d2` contra la base `ab80f4c`. El blob de la tarea es `65f5134d…` y coincide. Todo lo corrí en serie, con `uptime` junto a cada medida; la carga estuvo entre 4 y 26.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | CA-1, 3 corridas (18:10–18:12, carga 12–19) | pasa: 10 passed en cada una, rc=0. En `tests/` no hay `skip`, `fixme`, `only`, `todo` ni `skipIf` |
| 2 | La cadena de CA-2 | pasa: `PASA`, `PUERTA-EN-ORDEN`, 20 archivos y `src/views` vacío. `a143250` es el primer commit sobre la base y es ancestro de HEAD |
| 3 | `uv run pytest …test_bff_e2e_server.py -v` | pasa: 15 passed |
| 4 | `npm ci --ignore-scripts` y luego CA-4 | pasa: ci rc=0; 11 archivos y 132 tests; semilla impresa (`seed=1375391430`) |
| 5 | La cadena de CA-5 | pasa: rc=0, 51 tests, semillas de PBT-U10-06 impresas, `forbidden_phrases` sin líneas |
| 6 | `… test -- --coverage` | pasa: rc=0, 250 tests; ramas al 97,6 % en total y al 100 % en `src/stepup` |
| 7 | CA-7 con el `grep` enmendado | pasa: lint, tipos y 23 casos de ESLint. `localStorage`, `eslint-disable` y `dangerouslySetInnerHTML` no aparecen en `src`. `sessionStorage` aparece solo en `src/auth/loginStateStorage.ts` |
| 8 | La cadena de CA-8 | pasa: `3`, `4`, `OK` |
| 9 | Trazador de `console` y `--all` en la rama, contra la base de mi ronda 1 (mismo `ab80f4c`) | pasa: el primer `grep` no imprime nada; `console` queda en 21; NFR-U10-50 sigue sin trazar; 0 líneas nuevas; desaparecen exactamente las 9 pedidas |
| 10 | `npm ci --ignore-scripts`, `make -C console check`, `make -C contracts check` y `npm audit --audit-level=high` | pasa: console rc=0 (18:14:35→18:19:34, carga 13,8→26; 14 passed en Playwright); contracts rc=0 (→18:25:04, `bench` en verde); audit con 0 vulnerabilidades |

## Verificación por punto del encargo
1. **F-01, el lockfile.**
   - Hay una sola entrada de `jsdom`, la `node_modules/jsdom` 31.0.0, sin la marca `peer/optional` y sin copia anidada. Está anclada en el `package.json` raíz y en el de `console/spa`.
   - `npm ci` avisa **tres** `EBADENGINE`, no uno: `jsdom` 31.0.0, `undici` 8.12.4 (pide `>=22.19.0`) y `w3c-xmlserializer` 6.0.0 (ver F-01).
   - Mi juicio: la elección es defendible.
     - Es una dependencia solo de pruebas y no llega al bundle.
     - npm no está en modo estricto de motores, así que solo avisa.
     - En el Node 22.17.1 de la máquina, CA-4, 5, 6 y 10 pasan.
     - El único workflow con Node (`contracts.yml`) usa `"22"`, que hoy es una versión soportada.
   - Riesgo real pero acotado: las pruebas de la SPA corren con Node fuera del rango declarado en la máquina de la demo, y nada fija la versión de Node.
2. **F-03, el login.** Cumple la enmienda punto por punto.
   - **Login y renovación sin iframe.** Se usa `signinRedirect`. En `src` no hay ninguna llamada a `signinPopup`, `signinSilent`, `querySessionStatus` ni `monitorSession`. En oidc-client-ts 3.5.0 el valor por omisión `= args.redirect_uri` solo se aplica a `undefined`, así que `""` se queda tal cual. `signinSilent` (al que llama `automaticSilentRenew`) usa el refresh token si lo hay; si no, lanza `No silent_redirect_uri configured` **antes** de `_iframeNavigator.prepare`, y `querySessionStatus` hace lo mismo. Ningún camino de la librería abre un iframe: lo confirmé leyendo la librería en `node_modules`.
     - Mutante: con `silent_redirect_uri: config.redirect_uri`, `session.test.tsx` lo mata.
   - **Almacenamiento.** `userStore` vive en `InMemoryWebStorage`. El `stateStore` está en `sessionStorage`, y solo `loginStateStorage.ts` lo nombra. La librería borra la clave del flujo (`readSigninResponseState(…, true)`) antes de validar, así que desaparece con éxito y con error. El e2e lo lee en los pasos 1, 3 y 5, después de `login_required`.
   - **Una sola redirección `prompt=none` por carga.** `started` la protege, y después de un callback nunca se vuelve a redirigir.
   - **e2e en Chromium y Firefox.** 3 corridas: 4 passed cada una (29,0 s, 22,0 s y 27,5 s; carga 8–10). No pasa en vacío: los tres mutantes mueren en los dos navegadores.
     - **R0**, `userStore` en `sessionStorage`: muere en el e2e (`auth.spec.ts:106`, recibe `oidc.user:…`) y en vitest (2 fallos). El lint **no** lo ve.
     - **(a)**, el token copiado además en `sessionStorage` con `vectra.copy` a través de `loginStateStorage`: muere en los 4 casos del e2e (`Received ["vectra.copy"]`) y en vitest (2 fallos). Lint y tipos pasan, así que solo las pruebas lo detectan.
     - **(b)**, volver a redirigir con `prompt=none` tras `login_required` (bucle): muere en los 4 casos del e2e (`auth.spec.ts:87`, el login nunca aparece) y en vitest (4 fallos en `auth-provider.test.tsx`).
   - **ESLint.**
     - **`sessionStorage`:** `eslint.test.ts` fija la excepción en un solo archivo y prueba el global y `window`, `globalThis` y `self` en 5 rutas (incluidas `src/auth/otro.ts` y `src/loginStateStorage.ts`). Además corre el `grep` sobre `src`.
     - **`localStorage`:** sigue prohibido también en ese archivo, y el fixture global se mantiene.
   - **CSP de `routes.yaml`.** No veo choque con el perfil `spa`, siempre que `authority` sea del mismo origen (`/auth/realms/vectra`), que es lo que dice P-1.
     - El descubrimiento y el canje en `/token` son `fetch` al mismo origen, que `connect-src 'self'` admite.
     - El login y la vuelta a `/callback` son navegaciones de nivel superior: `connect-src` no las mira, y no hay `frame-ancestors` en juego porque no hay iframe.
     - El formulario lo envía la página de Keycloak (perfil `auth`) a su propio origen, así que `form-action 'self'` no se aplica a la SPA.
     - `history.replaceState` y `location.assign` no son sumideros de Trusted Types.
     - `Referrer-Policy: no-referrer` evita que el `code` se filtre por la cabecera Referer.
     - No se puede probar hasta U12.
   - **Ruta profunda.** No incumple los Pasos 10 a 12 ni BR-U10-05: ninguno pide conservar la ruta de origen, y las rutas son de U10-T04. La candidata está bien puesta.
3. **F-02 y F-08, PBT-U10-05.**
   - **El modelo es independiente.** Ya no importa `busy` ni lee `flow.state`: su `busy(model)` es propio. Lo único que lee del mundo falso es el `state` que devuelve `resolveRequest`.
   - **Tasa de detección.** Usé las semillas 7, 99, 1234, 4242, 8080, 65537, 271828, 314159, 1000003 y 2147483, distintas de las del codificador. Las dos mutaciones se aplican sobre el código, no sobre la prueba.
     - V1, reintento doble: muere en **10 de 10**.
     - V4, no borrar el `state` cuando el resultado es `done`: muere en **10 de 10**.
     - Sin mutación, las semillas 7 y 99 pasan.
4. **F-04 y F-05.**
   - **F-04.** Mi mutante V6 (el `QueryCache.onSuccess` dispara `focusin` sobre `document`) muere: 1 fallo en 250 casos. Una variante con `scroll` sobre `document.body` también muere. Otra que dispara `pointerdown` sobre `window` sobrevive, pero es equivalente: los oyentes están en `document`, en captura, y un evento lanzado sobre `window` no llega a `document` tampoco en un navegador real.
   - **F-05.** Instrumenté el conteo temporalmente y lo revertí después. Con `nightly` se imprime `numRuns=10000` y se corren 10 000 casos en cada propiedad, más un recorrido completo de 117 y 175 elementos. Con `ci`, 300 más el mismo recorrido.
5. **Los dos defectos que el codificador arregló.**
   - **Fallo tardío del step-up.** Sin la guarda falla `flow.test.ts` («el FALLO tardío…», `expected 'failed' to be 'opening'`), y la PBT da el contraejemplo `abandona-y-reintenta(tardia falla)` con la semilla 4242. El arreglo solo cambia el `catch` de `createRequest` cuando el intento ya no es el vigente. La PoC nunca llega a ese caso: el `window.open` síncrono y la validación siguen iguales. CA-1 pasa 3 de 3.
   - **Foco del aviso de inactividad.** Sin el filtro fallan 2 casos de `inactivity-ui.test.tsx`. Con un filtro que ignora todo `focusin`, falla el caso de `isWarningFocus`.
6. **La puerta.** `a143250` sigue intacto y es el primer commit sobre la base. La PoC pasa 3 de 3 en los dos navegadores, sin pruebas saltadas.
7. **Alcance.**
   - **No hay desborde (no es ROJO).** El arbitraje, que rige sobre el texto de la tarea, exige una prueba de Playwright con la SPA real y el `UserManager` real, y eso es lo que hay en `tests/e2e`; el arbitraje no dice dónde ponerla. El cambio del `Makefile` es la consecuencia mínima para correrla.
   - **Pero choca con la letra** de «siguen vacíos: `tests/e2e/`» (ver F-02).
   - `src/views` sigue vacío. No se tocan `console/bff/src`, `contracts/` ni `identity-edge` (`git diff --stat` vacío). Los cambios de diseño son los que pidió el arbitraje, más el texto de BR-U10-05, que lo refleja.

## Hallazgos
### F-01 · AMARILLO · `package-lock.json` · Tres dependencias fuera del rango de Node declarado, y la bitácora solo menciona una
- `undici` 8.12.4 (`>=22.19.0`) y `w3c-xmlserializer` 6.0.0 también avisan `EBADENGINE` en 22.17.1; la bitácora y `CANDIDATAS.md` solo hablan de `jsdom`.
- Hoy funciona: lo probé con mi `npm ci`, CA-4 a CA-6 y CA-10.
- Pero nada fija Node. Si la máquina de la demo tiene un Node anterior, o alguien activa `engine-strict`, la suite de la SPA queda fuera de lo soportado.
- Alternativas: fijar Node ≥ 22.22.2 (`.nvmrc` o `platform/tools.env`) o evaluar `happy-dom`, que la tarea admite.

### F-02 · AMARILLO · `console/spa/tests/e2e/` · La prueba vive donde la tarea dice «siguen vacíos», y sigue el `.gitkeep`
- La prueba es evidencia que exigió el arbitraje. Pero `U10-T04-spa-vistas-y-e2e.md:196` da por hecho que `tests/e2e` está vacío, y el `.gitkeep` sigue en un directorio que ya tiene archivos (la tarea pide borrarlo).
- El orquestador debería actualizar la precondición de U10-T04.

### F-03 · AMARILLO · `src/auth/AuthProvider.tsx` · Un flujo abandonado deja su clave en `sessionStorage` hasta 15 minutos
- Si alguien hace clic en «Iniciar sesión» y vuelve atrás sin terminar, la clave `oidc.<state>`, con `code_verifier` y sin tokens, se queda en `sessionStorage`. Solo la borra `clearStaleState` en el siguiente `signinRedirect`, y solo si tiene más de 900 s.
- Esto lo deduzco leyendo la librería; no lo reproduje.
- No incumple la enmienda, que pide borrar la clave al terminar el callback, pero sí la lectura estricta de «como mucho la clave del flujo en curso». Se podría bajar `staleStateAgeInSeconds` o limpiar el `stateStore` al cargar sin callback.

### F-04 · AMARILLO · `src/inactivity/InactivityProvider.tsx:28` · `isWarningFocus` ignora el `focusin` dentro de cualquier `alertdialog`
- Hoy solo existe el aviso de inactividad. Si U10-T04 añade otro `alertdialog`, el foco que se mueva dentro de él no contará como actividad. `keydown` y `pointerdown` sí cuentan, así que el efecto es menor.
- Convendría marcar el aviso con un selector propio.

## Tareas candidatas (defectos reales fuera de alcance)
- U10-T04 o U10-T05: `AuthProvider` no escucha `silentRenewError` ni `accessTokenExpired`. Si el refresco rotativo falla, la sesión se queda «autenticada» con un token vencido hasta el próximo 401.
- U10-T04 o U12 Paso 18: probar la redirección y `/callback` bajo la CSP real del perfil `spa`. Lo único que conviene vigilar es el `authority` del `config.json` de kind, que tiene que ser del mismo origen.
- Orquestador: fijar la versión de Node de la máquina y del CI de la SPA (F-01).

## Estado al terminar
- **Worktree:** cada mutación se aplicó en el worktree y se revirtió con `git checkout --`, comprobando `git status --short` vacío después de cada una. Al final está vacío. `node_modules` quedó en el estado exacto del lockfile, por el `npm ci` de CA-10.
- **Procesos y puertos:** no queda ningún navegador de Playwright, Vite, `bff_e2e_server` ni vitest vivo, y nada escucha en 47170–47189. Solo sigue el Edge de otra sesión.
- **`/tmp`:** sin copias del repositorio ni `npm ci` ahí; solo logs. Uso al 79 %.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t03-r2/`:
  - instalación y criterios: `npm-ci-1.log`, `npm-ci-2.log`, `ca1-1..3.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca7.log`, `ca10.txt`, `ca10-console.log`, `ca10-contracts.log`, `ca10-audit.log`
  - e2e y F-05: `e2e-1..3.log`, `trace-rama.txt`, `f05-nightly.log`, `f05-ci.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t03-r2/mut/`:
  - login: `R0-*`, `Ra-*`, `Rb-*`, `Rc-silent-uri.log`
  - PBT-U10-05: `V1-seed*.log`, `V4-seed*.log`, `V1-summary.txt`, `V4-summary.txt`
  - refresco: `V6-full.log`, `V6b-window-pointerdown.log`, `V6c-body-scroll.log`
  - los dos arreglos: `D1-sin-filtro-foco.log`, `D1b-ignora-todo-focusin.log`, `D2-sin-guarda-unit.log`, `D2-sin-guarda-pbt.log`

```
VEREDICTO: VERDE
AMARILLO|vectra-risk/package-lock.json (jsdom, undici, w3c-xmlserializer)|Tres dependencias de prueba fuera del rango de Node 22.17.1; la bitácora solo nombra jsdom y nada fija Node
AMARILLO|console/spa/tests/e2e/|La prueba exigida por el arbitraje vive en tests/e2e (reservado a T04, que lo da por vacío) y sigue el .gitkeep
AMARILLO|console/spa/src/auth/AuthProvider.tsx|Un flujo de login abandonado deja su clave oidc.<state> en sessionStorage hasta 15 min
AMARILLO|console/spa/src/inactivity/InactivityProvider.tsx:28|isWarningFocus ignora el focusin de cualquier alertdialog, no solo el del aviso
INFORME: revisiones/U10-T03/ronda-2.md
```
