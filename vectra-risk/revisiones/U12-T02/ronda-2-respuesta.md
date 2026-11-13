# Respuesta a la ronda 1 — U12-T02 (ronda 2)

Arbitraje: `arbitraje-ronda-1.md`. Commit de la ronda: bb3eae5. Detalle y salidas en `bitacoras/U12-T02.md`, sección «Ronda 2».

F-01: Corregido en bb3eae5: el comentario de `system-verification/pyproject.toml:7` ya no nombra la biblioteca; rojo previo: el comando literal de CA-1 salía con `exit=1` sin `OK`; verde: imprime `OK`, bitácora con la salida completa.
F-02: Corregido en bb3eae5 (solo el docstring de `clients/oidc.py`: dos caminos de confianza TLS, cada uno con lo que protege); el resto sigue como candidata para U12-T04.
F-03: Corregido en bb3eae5: `HeadlessForm.submit` convierte todo fallo de Playwright (arranque, navegación, cierre del contexto) en `OidcError` con código estable (`browser_launch_error`, `browser_error`, `browser_close_error`), sin cadena de excepción; pruebas `unit/test_oidc_form_errors.py` (rojo previo: 5 fallos) y `test_red_f03_...` con Keycloak real y Node sin la CA (rojo previo: `playwright.Error: BrowserContext.close: Route.fetch: self-signed certificate...` con la URL de autorización).
F-04: Fuera de alcance: destino U12-T03 (candidata en `CANDIDATAS.md`), según el arbitraje.
F-05: Corregido en bb3eae5: `evidence.scrub` limpia el objeto HAR con cualquier orden de claves y `code=` al principio de un cuerpo, tras un espacio o un salto de línea; `{"code": "conflict_state"}` queda intacto; pruebas `test_f05_*` en `unit/test_evidence_filter.py` (rojo previo: 8 fallos).
F-06: Fuera de alcance: ya está en `CANDIDATAS.md`, según el arbitraje.
F-07: Corregido en bb3eae5 (solo las dos que dijo el arbitraje): la aserción con `or` de `test_oidc_headless.py` ahora compara contra los valores generados y las lecturas de la bóveda (mutación que devuelve otra contraseña: falla), y el CA-2 viejo de la bitácora quedó marcado y reemplazado por `limpio=0`; lo demás de F-07 es candidata.
Defectos del realm de kind: No es de esta tarea: tarea de U2 aparte (U02-T22), según el arbitraje.
