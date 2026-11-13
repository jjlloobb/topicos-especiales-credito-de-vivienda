# U10-T03 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con dos ROJO (F-01 y F-02). La puerta del Paso 10 pasa de verdad: 6 de 6 corridas en Chromium y Firefox, con las mutaciones del revisor muertas.

## Decisión del usuario sobre el login (F-03), 2026-11-12
El diseño se contradice: P-U10-07 y tech-stack §2 piden `InMemoryWebStorage` para el login, y el Paso 11 pide login por redirección; una redirección completa borra `state` y `code_verifier`. La ronda 1 lo resolvió con `signinPopup` y `signinSilent` (iframe), que tech-stack §2 y la tarea prohíben, y el iframe no puede cargar `/callback` bajo la CSP de U2 (`frame-ancestors 'none'`, `identity-edge/gateway/routes.yaml`).

**El usuario decidió:** login por **redirección**, guardando **solo el estado transitorio** del flujo (`state`, `code_verifier`, `nonce`) en `sessionStorage`. Los tokens y el usuario siguen **en memoria**, como exige BR-U10-05. La recarga de la página se resuelve con otra redirección con `prompt=none`, sin iframe. No se toca U2.

Enmienda de la tarea (rige sobre su texto):
- **Login interactivo:** `signinRedirect`. No se usa `signinPopup` ni `signinSilent`, ni ningún iframe.
- **Recarga:** al cargar sin sesión en memoria, una redirección con `prompt=none`. Si el emisor responde `login_required` (o cualquier error de `prompt=none`), se muestra el login interactivo. Nunca un bucle de redirecciones: una prueba lo fija.
- **`stateStore` del login:** `sessionStorage`, con una clave por flujo que se borra al terminar el callback, con éxito o con error. **`userStore`: en memoria.** Nada en `localStorage` ni en cookies.
- **Step-up (Paso 10, P-U10-07): no cambia.** Sigue con ventana emergente y `stateStore` en memoria, tal como pasó la puerta. El commit de la puerta (`a143250`) no se reescribe.
- **ESLint y CA-7:** la prohibición de `sessionStorage` se mantiene, con **una** excepción acotada al módulo que crea el `stateStore` del login (un archivo, nombrado en la configuración de ESLint). El `grep` de CA-7 pasa a exigir que `sessionStorage` aparezca solo en ese archivo. Una prueba de ESLint fija que cualquier otro uso sigue prohibido.
- **Diseño:** se precisan P-U10-07, tech-stack §2 y el Paso 11 del plan con esta decisión (fecha y motivo). `spa.md` lo anota.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: con `npm ci` limpio vitest no encuentra `jsdom` | **Entra en la ronda 2** | El verde no salió del lockfile del diff; fallan CA-4, 5, 6 y 10 |
| F-02 ROJO: el rojo de PBT-U10-05 no se reproduce; detecta el reintento doble en 4 de 8 corridas | **Entra en la ronda 2** | CA-4 promete la PBT; las PBT no se recortan |
| F-03 NARANJA: `signinPopup` e iframe silencioso | **Entra en la ronda 2**, con la decisión de arriba | Decisión del usuario |
| F-04 NARANJA: la prueba del refresco pasa en vacío | **Entra en la ronda 2** | BR-U10-20 queda sin fijar; arreglo acotado |
| F-05 NARANJA: `numRuns` pisa el perfil en PBT-U10-06 | **Entra en la ronda 2** | Incumple NFR-U10-62 y la línea impresa miente |
| F-06 AMARILLO: NFR-U10-50 trazado por adelantado | **Entra en la ronda 2** | Trivial: se quita la cita, para que U10-T04 conserve la señal |
| F-08 AMARILLO: el modelo de PBT-U10-05 lee la fase del código | **Entra en la ronda 2**, junto con F-02 | Se rehacen los generadores de todos modos |
| F-07 AMARILLO: `inClick` mide el despacho del clic, no la sincronía | Pasa a `CANDIDATAS.md` | `flow.test.ts` sí mata la microtarea; la PoC ya pasó la puerta |

## Lo que se espera de la ronda 2
- **F-01:**
  - un lockfile limpio, con `jsdom` instalable desde la raíz en una versión que funcione en Node 22.17.1 y sin la entrada vieja de la 31.0.0;
  - **`npm ci --ignore-scripts` justo antes de cada verde** de CA-4, CA-5, CA-6 y CA-10, y la bitácora lo muestra con la salida;
  - `npm audit --audit-level=high` y `make -C contracts check` vuelven a correr, porque el lockfile cambia.
- **F-02 y F-08:**
  - los generadores de PBT-U10-05 llegan al camino de éxito con peso suficiente (un comando compuesto o pesos), y el modelo decide qué mensaje es válido con su propio estado, sin leer `flow.state.phase` ni `busy()`;
  - el rojo se toma con la prueba del commit: las mutaciones «reintento doble» y «no borrar el `state` tras un canje bueno» mueren en **10 de 10** corridas con semillas distintas, y la bitácora da las semillas.
- **F-03:** la enmienda de arriba, con evidencia en navegador real, no solo en jsdom:
  - una prueba de Playwright, en Chromium y Firefox, con el emisor OIDC de prueba y el `UserManager` real: login por redirección → sesión; recarga → redirección `prompt=none` → sesión sin interacción; recarga con la sesión del emisor cerrada → login interactivo, sin bucle;
  - en cada paso se lee el almacenamiento: `localStorage` vacío, ninguna cookie de la SPA, y en `sessionStorage` como mucho la clave del flujo en curso, que desaparece tras el callback. Ningún token aparece nunca en `sessionStorage`;
  - rojo primero: con el `userStore` en `sessionStorage` la prueba falla.
  - **Si esta opción no resulta realizable** (por la librería, por la CSP o por otra causa), el codificador para y lo reporta con la evidencia; no vuelve a `signinPopup` ni elige otra salida por su cuenta.
- **F-04:** la prueba usa `createQueryClient()` e `InactivityProvider` reales; el mutante V6 del revisor (un refresco automático que reinicia el contador) queda en rojo.
- **F-05:** `nightly` corre de verdad los casos que imprime; la línea impresa dice lo que se corrió; el muestreo cubre todos los textos.
- **F-06:** se quita la cita de NFR-U10-50 de `playwright.config.ts`. `console` debe quedar en 21 sin trazar.
- **`CANDIDATAS.md`:** F-07; y se corrige la candidata del iframe y `/auth/**`: con la redirección ya no hace falta cambiar U2.
- **Se vuelven a correr:** CA-1 a CA-10, la PoC incluida. La puerta sigue en PASA.

Es la última ronda (RL-2). Si queda un ROJO, la tarea se para y va al usuario.
