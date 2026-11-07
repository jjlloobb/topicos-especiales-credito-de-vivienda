# U02-T15 — Arbitraje tras la ronda 2 (orquestador, 2026-11-06)

La ronda 2 salió VERDE y se abrió el PR 72. El usuario pidió revisar el PR; el informe es `revision-codigo-pr72.md`, sin verificar con ejecución. **El usuario decidió una ronda 3** con R-01 a R-05 y mandar R-06 a R-10 a `CANDIDATAS.md`.

| Hallazgo | Decisión |
|---|---|
| R-01 cookies SSO en el re-login | **Ronda 3.** Primero se confirma con k6 v2.3.0 real (qué borra `clear(url)` con cookies de otra ruta), con un gateway falso que ponga cookies con `Path=/auth/realms/vectra/` y responda 302 si las recibe |
| R-02 `r.json` en un 429 sin JSON | **Ronda 3** |
| R-03 prefijo de usuarios duplicado | **Ronda 3.** Una sola fuente: el script lee lo que valida `load_checks`, o `load_checks` deja de validar un env que no se usa y comprueba lo que el script usa de verdad |
| R-04 `MAX_DIFF_P95_MS` sin leer | **Ronda 3**, con la misma regla que R-03 |
| R-05 `REDIRECT_URI` con puerto o ruta | **Ronda 3.** El redirect URI tiene que coincidir con el registrado en el realm de kind para el cliente que usa el script; la prueba lo lee del realm |
| R-06 a R-10 | `CANDIDATAS.md` (decisión del usuario) |

## Lo que se espera de la ronda 3

- Cada R-01..R-05 con rojo primero, contra el gateway falso o con k6 real, y la respuesta por id en la bitácora (sección Ronda 3).
- Si R-01 resulta no ser un defecto con k6 v2.3.0, el codificador lo demuestra con el comando y la salida; no se cambia el código.
- CA-1 a CA-6 se vuelven a correr; CA-6 en serie después de CA-5.
- El codificador no toca `CANDIDATAS.md`, el plan ni `routes.yaml`.
