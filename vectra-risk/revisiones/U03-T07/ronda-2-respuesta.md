# Respuesta del codificador a la ronda 1 (retrabajo, ronda 2) — U03-T07

- F-01: Corregido en 4859247 y d428ecd: `QUERY_BUDGET_S = POOL_SIZES['projections'][1] - QUERY_RELEASE_MARGIN_S` (0,5 s; tope 1,5 s), peor caso sin retraso artificial. Rojo previo 2 de 13; verde 20 de 20 de `-k peor_caso` (cargas 6 a 19). **Pendiente:** `make -C decision-registry check` dio exit 0 en la corrida 1 y exit 2 en la corrida 2 por CA-2 (cron, un 200 a 1,528 s con carga 12 a 14); ver bitácora, «Para el orquestador».
- F-02: Corregido en 4859247 y d428ecd: 12 ejecuciones del descubrimiento y guarda sobre `pg_prepared_statements`; M5 (quitar `prepare=False`) queda en rojo (`1 failed, 1 passed`); comentario de `queries.py` corregido (6.a ejecución prepara, 11.a plan genérico). Además la sentencia `versions` también va sin preparar (hallazgo propio, 5/25 -> 0/25).
- F-03: Corregido en 4859247: `monitoring_lag(conn, now, budget)` arma el tope antes de cada una de sus dos sentencias.
- F-04: Corregido en 4859247: la aserción de la `explanation` vuelve a `waited < POOL_SIZES['projections'][1]` y se quitó `EXPLANATION_LLEGA_DESPUES_S`.
- Nota `cierre-demo.md` fila 20: Corregido en 2c4e747: refleja las dos corridas (exit 0 y exit 2), no una cifra única.
- Nota bitácora «135 failed»: Corregido en 2c4e747: nota en la bitácora (dos corridas distintas).
