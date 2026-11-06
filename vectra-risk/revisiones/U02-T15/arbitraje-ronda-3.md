# U02-T15 — Arbitraje de la ronda 3 (orquestador, 2026-11-06)

Informe: `ronda-3.md`, NO-VERDE. R-01 a R-05 cerrados. Al llegar a la ronda 4 se paró y **el usuario la acotó a F-09**.

| Hallazgo | Decisión |
|---|---|
| F-09 NARANJA: nadie comprueba que el GET y el POST del login compartan jar | **Ronda 4, única** |
| F-10 AMARILLO: `undefinedNaN` sin el env del escenario | `CANDIDATAS.md` |
| F-08 AMARILLO (ronda 2) | Ya está en `CANDIDATAS.md` |

## Lo que se espera de la ronda 4

- El gateway falso pone una cookie de sesión de autenticación (como `AUTH_SESSION_ID`, con `Path=/auth/realms/vectra/`) en la respuesta del GET de autorización, y el POST de `login-actions` la exige y responde 400 si falta.
- Las mutaciones R01c (sin `jar` en el POST) y R01d (sin `jar` en el GET) mueren; rojo de las dos en la bitácora (sección Ronda 4).
- La prueba de re-login de R-01 sigue pasando, y R01a y R01b siguen muriendo.
- Nada más se reabre. CA-1 a CA-6 se vuelven a correr; CA-6 en serie después de CA-5.
