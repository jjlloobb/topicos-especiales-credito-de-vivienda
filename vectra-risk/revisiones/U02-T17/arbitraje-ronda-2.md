# U02-T17 — Arbitraje después de la ronda 2 (orquestador, 2026-11-07)

La ronda 2 salió VERDE y se abrió el PR 74. Después, a pedido del usuario, la revisión de código del PR 74 (`revision-codigo-pr74.md`) encontró falsas alarmas en la forma que fija el diseño. **El usuario decidió enmendar P-U2-09 (B16 y B17) y hacer una ronda 3.**

| Hallazgo | Decisión |
|---|---|
| C-01 y C-02: la rama de serie nueva dispara después de un hueco de scrape | **Ronda 3** (B16) |
| C-03: `absent()` con `for` 0m dispara con un solo scrape fallido | **Ronda 3** (B17) |
| C-05: con kube-state-metrics caído dispara `RateLimitBackendDown` | **Ronda 3** (B17) |
| F-02 de la ronda 1: subcadenas en lugar del operador | **Ronda 3**, porque toca las mismas comprobaciones |
| C-04: un solo StatefulSet de Valkey | Sigue en `CANDIDATAS.md` |
| C-06 a C-09 (helpers de prueba) | `CANDIDATAS.md` |

La tarea enmendada dice qué se espera.
