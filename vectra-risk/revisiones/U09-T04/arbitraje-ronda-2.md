# U09-T04 — Arbitraje de la ronda 2 (orquestador, 2026-11-10)

Informe: `ronda-2.md`. El veredicto es NO-VERDE, sin ningún ROJO. La ronda 2 es la última (RL-1). Por RL-4 solo un ROJO bloquea, así que la tarea pasa a PR y los hallazgos pendientes van a `CANDIDATAS.md`. RL-5 mandaría corregirlos antes del PR si rompieran alguna de las cuatro demos, y ninguno lo hace.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-06 NARANJA: un `n_min` ≥ 1 000 000 pasa conftest, pero el CronJob lo rechaza porque Helm lo convierte a float | Pasa a `CANDIDATAS.md` | La política de la demo usa `n_min` = 30. El caso exige editar la política con un valor absurdo, y aun así el CronJob falla cerrado: rechaza la política, no la aplica mal. No rompe ninguna demo. |
| F-07 NARANJA: la bitácora tiene plantillas sin expandir | Evidencia copiada en el anexo de `ronda-2.md`; la corrección de la bitácora pasa a `CANDIDATAS.md` | Los archivos existían y el revisor comprobó que coinciden con su corrida. Ahora la evidencia queda versionada en la revisión. |
| F-08 AMARILLO: RE2 frente a `re` de Python | Pasa a `CANDIDATAS.md` | Va en la dirección conservadora. |
| F-09 AMARILLO: `CANDIDATAS.md:392` cita una sección que ya se quitó | Pasa a `CANDIDATAS.md` | — |

Resueltos en la ronda 2: F-01 (los casos de la ronda 1 dan FAIL y el conteo 650/660 está explicado), F-02 y F-05.
