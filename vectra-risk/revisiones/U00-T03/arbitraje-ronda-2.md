# U00-T03 — Arbitraje de la ronda 2 (orquestador, 2026-11-10)

Informe: `ronda-2.md`. Veredicto NO-VERDE, sin ningún ROJO. Era la última ronda (RL-1). Por RL-4 solo un ROJO bloquea, así que la tarea pasa a PR y lo que queda va a `CANDIDATAS.md`.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: la ventana de acuñación se alcanza sin `_internal` (`_minting`, `__module__` falso, espía, `asyncio`) | Va a `CANDIDATAS.md`, con una entrada que corrige el cierre de R2-01 y lo que dice `nfr-design-patterns.md:52` | Las cuatro rutas exigen código hostil dentro del proceso. Ninguna de las cuatro demos lo ejecuta, y el uso legítimo (U7, U8) funciona. Que los textos digan más de lo que se cumple queda corregido en `CANDIDATAS.md`, que es lo que lee quien retome el tema. |
| F-02 | Cerrado | — |
| F-03 | Cerrado | — |
| F-04 AMARILLO: `_holds_token` solo entra en algunos contenedores | Va a `CANDIDATAS.md` | — |
| Pickle manipulado | Va a `CANDIDATAS.md` | Es de la misma clase que el límite aceptado en P-1. |
| `bench_gate` y `test_p_u7_01` | Son la carga, no el diff | El revisor corrió las pruebas en serie alternando rama y base: 5/5 frente a 5/5, y bench intermitente en las dos. |
