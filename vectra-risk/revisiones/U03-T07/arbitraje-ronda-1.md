# U03-T07 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). El revisor señaló que la tarea se contradice: CA-4 y P-1 fijan el tope igual a la espera del pool `projections` (2 s), y CA-3 exige que una `explanation` concurrente obtenga la conexión dentro de esa misma espera. Una respuesta 200 retiene la conexión hasta 2,33 s, así que no queda holgura.

**Decisión del usuario (2026-11-12): opción (a).** El tope se deriva como la espera del pool `projections` **menos un margen de liberación**. Las opciones (b), subir la espera del pool, y (c), relajar CA-3, quedan descartadas.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: tope igual a la espera del pool; la `explanation` recibe 503 y `make check` termina en 2 | **Entra en la ronda 2**, con la opción (a) | Decisión del usuario. Conserva el valor del diseño (2 s de espera del pool) y la garantía de CA-3 |
| F-02 NARANJA: la guarda de `prepare=False` no detecta su retirada | **Entra en la ronda 2** | CA-7 pide que CA-2 lo demuestre, y hoy no lo demuestra. El arreglo es acotado |
| F-03 AMARILLO: un solo `arm` para las dos sentencias de `monitoring_lag` | **Entra en la ronda 2** | Contribuye a F-01: es parte de lo que retiene la conexión después del plazo |
| F-04 AMARILLO: la aserción de `explanation` se aflojó a pool + margen | **Entra en la ronda 2** | Con el margen de liberación ya no hace falta: vuelve a «dentro de la espera del pool» |
| Nota sobre `cierre-demo.md`, fila 20 | **Entra en la ronda 2** | La cifra debe salir de una corrida reproducible de esta ronda |
| Bitácora: «135 failed» inconsistente | **Entra en la ronda 2** (solo la bitácora) | Basta con una nota |

## Enmienda de la tarea (rige sobre el texto de `tareas/U03-T07-tope-de-daily-query.md`)

- **P-1 y Alcance, «Valor del tope».** `QUERY_BUDGET_S` se deriva así: `POOL_SIZES["projections"][1] - QUERY_RELEASE_MARGIN_S`. `QUERY_RELEASE_MARGIN_S` es una constante tipada (`Final`) nueva en `queries.py`, con un comentario que diga qué cubre: lo que la solicitud retiene la conexión después del plazo (la sentencia en curso hasta su `statement_timeout`, `monitoring_lag` y el commit o rollback).
  - Valor de partida: **0,5 s** (tope de 1,5 s). El codificador lo confirma o lo ajusta con medidas propias y lo justifica en la bitácora. El revisor midió 200 a los 2,33 y 2,34 s y 504 entre 2,01 y 2,11 s, con el tope en 2 s y carga entre 8 y 30.
  - Límite inferior del tope: las formas reales de U9 tardan entre 0,22 y 1,3 s (ronda 1, CA-2). El tope no puede dejar esas formas en 504: CA-2 sigue exigiendo 200 en cada solicitud.
- **CA-4, segunda orden.** Se reemplaza por:
  ```
  uv run python -c "from vectra_registry import pools, queries; m = queries.QUERY_RELEASE_MARGIN_S; assert 0 < m < pools.POOL_SIZES['projections'][1]; assert queries.QUERY_BUDGET_S == pools.POOL_SIZES['projections'][1] - m"
  ```
  La primera y la tercera orden de CA-4 no cambian. El margen tampoco puede aparecer como literal en un punto de decisión.
- **CA-3.** No cambia su texto, pero la prueba del peor caso deja de depender de `EXPLANATION_LLEGA_DESPUES_S`: la `explanation` se lanza a la vez que el `daily`, o con retraso 0, y debe recibir 200 dentro de la espera del pool (sin sumar `TOPE_MARGEN_S`).
- **CA-5** sigue valiendo tal cual (el tope baja, así que cabe con más holgura).

## Lo que se espera de la ronda 2

- **F-01:**
  - la constante y la derivación de arriba;
  - la prueba del peor caso sin el retraso artificial;
  - evidencia de estabilidad: la prueba del peor caso (`-k peor_caso`) pasa **10 de 10** corridas seguidas, y `make -C decision-registry check` termina en 0. La bitácora anota la carga (`uptime`) de cada corrida. Se registra el rojo previo: la misma prueba, sin el retraso, con el tope igual a la espera del pool.
- **F-02:** la prueba de la forma (b) repite la sentencia sin versión al menos 12 veces en la misma conexión, o comprueba `pg_prepared_statements`. La mutación M5 del revisor (quitar `prepare=False`) debe quedar en rojo, y la bitácora lo registra. Se corrige el comentario de `queries.py:286-288`: el plan genérico llega hacia la ejecución 11, no tras 5 usos.
- **F-03:** un `arm` por sentencia en `monitoring_lag`.
- **F-04:** la aserción de la `explanation` vuelve a `waited <` la espera del pool.
- **Documentación:** `code/api-summary.md` y la nota del Paso 8 del plan dicen el valor nuevo y cómo se deriva. La fila 20 de «Re-corrido en U03-T07» de `evidence/cierre-demo.md` se actualiza con la corrida de esta ronda.
- **Bitácora:** una nota que aclare la cifra de la primera corrida («135 failed»).
- **Se vuelven a correr:** CA-1 a CA-8. `make -C bias-monitoring check` y `make -C platform check` se corren esta vez, en serie y con la máquina sin otra carga del loop si es posible.

Es la última ronda (RL-2). Si F-01 sigue en ROJO, la tarea se para y va al usuario.
