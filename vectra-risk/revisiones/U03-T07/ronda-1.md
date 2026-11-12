# Ronda 1 — U03-T07

VEREDICTO: NO-VERDE

Revisé el HEAD `edd4059` (el código está en `474874c` y la base es `a10b930`). El blob de la tarea coincide: `a2d7cf86…`. Al terminar, el worktree quedó limpio: `git status --short` da 0 líneas. Las mutaciones las hice sobre copias en mi scratchpad, nunca en el worktree. La carga de cada corrida va anotada en sus logs, entre 6 y 30 en 8 núcleos, porque había otros agentes corriendo a la vez.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | El tope corta y libera la conexión | `pytest … -k tope -v -s` | pasa (17 s, carga 13) |
| 2 | Formas de U9: 200 en cada solicitud | `pytest … -k forma_de_u9 -v -s`, 4 corridas | pasa. Forma (a) entre 0,29 y 0,60 s; forma (b) entre 0,22 y 0,66 s; todas las respuestas 200 |
| 3 | El peor caso respeta el tope y `explanation` responde 200 | `-k peor_caso` 7 veces y `-k test_f04` 3 veces | **falla 1 de 10**: `(503, 2.067, [(504, 2.066), (200, 2.327)])` |
| 4 | Sin `best_of` ni literales | los tres greps y la aserción de la tarea | pasa |
| 5 | `QUERY_BUDGET_S` < `QUERY_TIMEOUT_S` | el `python -c` de la tarea | pasa (2,0 < 5) |
| 6 | U9 no se rompe | `git diff a10b930 --stat -- bias-monitoring/ platform/`, que da vacío | el diff pasa. No corrí `make -C bias-monitoring check`, por tu instrucción: el diff no toca esa unidad |
| 7 | Sentencias preparadas (P-6) | mi propio `EXPLAIN (ANALYZE, BUFFERS)` en la réplica y los conteos de `pg_prepared_statements` | el diagnóstico se confirma. La prueba que debía demostrarlo no lo demuestra (F-02) |
| 8 | Unidad y documentación | `make -C decision-registry check` en serie, con `uptime` antes y después | **falla, exit 2**: `1 failed, 671 passed`, la misma prueba de CA-3 con `(503, 2.069, […, (200, 2.34)])`. La cobertura llega a 96,13 %. Los greps de la documentación y `test_traceability` (41 identificadores, igual que la base) pasan. No corrí `make -C platform check`, por tu instrucción |

## Hallazgos

### F-01 · ROJO · CA-3 y CA-8 · `test_queries.py:582-584` y `:684` · tope igual a la espera del pool: `explanation` recibe 503 aunque se lance 0,25 s después
- **Lo que vi.** En 11 corridas mías de la prueba del peor caso fallan 2:
  - una corrida aislada, con carga 8 a 12;
  - la corrida dentro de `make check`, que por eso termina en exit 2.

  En ambas, la `explanation` agota su espera de 2 s en el pool y recibe 503. El `daily` responde **200 a los 2,33 y 2,34 s**.
- **Causa.**
  - Una respuesta 200 retiene la conexión más allá de `QUERY_BUDGET_S`. La última sentencia termina justo antes del plazo y después vienen el `monitoring_lag` y el commit.
  - El presupuesto empieza al obtener la conexión (P-2). Todo lo que ocurre antes de ese momento no cuenta contra el tope, pero sí cuenta contra la espera de la `explanation`.
  - Con el tope y la espera iguales (2 s, CA-4), no queda holgura.
  - `EXPLANATION_LLEGA_DESPUES_S = 0.25` es un ajuste de la prueba que esconde el defecto, y además no alcanza.
  - El codificador lo vio y lo reportó, y su propio `make check` también falló una vez. Aun así entregó la prueba con el ajuste.
- **Sobre tu punto 2.** Lo clasifico ROJO por el criterio: CA-3 y la viñeta del Paso 8 («una consulta `explanation` concurrente no supera su límite») no se cumplen de forma fiable. El riesgo para la demo es bajo:
  - en D2, las formas reales de U9 tardan entre 0,22 y 1,3 s, lejos de 2 s;
  - D3 no lee de U3.

  Aun así, sin tope la situación era peor, porque antes se retenía la conexión hasta 5,7 s.
- **Mutación.** Quitar el `min()` del `statement_timeout` también la detecta esta prueba, por la misma vía: una `explanation` con 503.
- **Decisión que necesitas tomar.** La especificación se contradice: CA-4 y P-1 fijan la igualdad, y CA-3 exige que la `explanation` llegue a tiempo. El codificador no puede arreglarlo sin romper CA-4. Hay tres salidas:
  - (a) derivar el tope como la espera del pool menos un margen de liberación;
  - (b) subir la espera del pool `projections`;
  - (c) relajar CA-3.

### F-02 · NARANJA · CA-7 · `test_queries.py:654-661` y `queries.py:286-288` · la guarda de `prepare=False` no detecta su retirada
- La mutación M5 quita `prepare=False`. **Sobrevive** en 2 corridas de `-k forma_de_u9`; las 4 pruebas siguen en verde.
- Medí con psycopg 3.3.8 la sentencia sin versión, ejecutada 15 veces en la misma conexión:
  - psycopg la prepara en la ejecución 6;
  - el servidor usa planes a medida en las 5 siguientes;
  - el plan genérico llega en la **ejecución 11**: `generic_plans` pasa de 0 a 1, y el tiempo, de 0,16 a 0,32 s.
- La prueba del descubrimiento lanza 10 solicitudes de 1 rango cada una, así que nunca llega al plan genérico. La aserción `timings[-1] <= 2*timings[0]` no puede fallar por esta causa.
- El comentario del código («tras 5 usos psycopg pasa al plan generico») es inexacto por la misma razón: hacen falta unos 10 usos.
- El diagnóstico en sí lo confirmé con mi propio `EXPLAIN`:
  - con un `PREPARE` explícito, la ejecución 6 sin versión cambia a `Finalize GroupAggregate` + `Sort`, con desborde a disco en la 7, y pasa de 329–420 ms a 769–807 ms;
  - con versión el plan no cambia (`Bitmap Index Scan` + `HashAggregate`).
- `prepare=False` aparece en un solo sitio (`queries.py:288`), así que no afecta a otras consultas.
- **Arreglo:** repetir la forma (b) 12 veces o más en la prueba, o comprobar `pg_prepared_statements`.

### F-03 · AMARILLO · `queries.py:325-326` · `monitoring_lag` corre dos sentencias con un solo `arm`
Las dos sentencias heredan el mismo `statement_timeout`. En teoría la solicitud puede pasarse del plazo hasta una vez lo que quedaba de presupuesto. En la práctica son búsquedas por llave primaria y el efecto es mínimo, pero contribuye a F-01.

### F-04 · AMARILLO · `test_queries.py:684` · la aserción de `explanation` se aflojó
Ahora exige `waited < 2.0 + TOPE_MARGEN_S` en lugar de «dentro del límite del pool». Es defendible, porque un 200 ya implica que la espera en el pool fue menor de 2 s. Está documentado en la bitácora.

### Notas sin hallazgo (tus puntos 1, 4, 5 y 6)
- **Tope (punto 1).** Usa `statement_timeout` = mínimo entre `STATEMENT_TIMEOUT_MS` y lo que queda del presupuesto, no solo la revisión entre sentencias. Una sola sentencia lenta queda cortada al llegar al plazo. Los 504 que vi caen entre 2,01 y 2,11 s.
- **Mutaciones mías:**
  - M1, sin tope: muere en CA-1 (200 en vez de 504) y en CA-3 (2,78 s);
  - M2, 503 en vez de 504: muere en ambas;
  - M3b, sin transacción y con un pool que reutiliza conexiones sucias: muere, con un 500 en la solicitud siguiente;
  - M3a, sin `conn.transaction()` pero con el pool real: **sobrevive**, y es correcto, porque `pools._reusable` descarta las conexiones que no quedan ociosas. Sin el rollback, la conexión no vuelve sucia al pool.
- **`test_f04` aislado (punto 4).**
  - En la base, 3 de 3 corridas fallan con `best_of`: 3,34, 3,41 y 3,30 s, con carga entre 11 y 15.
  - En la rama, las pruebas de las formas de U9 y de CA-1 pasan 3 de 3; la del peor caso, 2 de 3 (F-01).
  - La candidata «Prioritaria» queda atendida en cuanto al tope y a `best_of`. La holgura sigue abierta: es F-01, y ya está anotada como candidata en `CANDIDATAS.md:255`.
- **`cierre-demo.md` (punto 5).**
  - La línea 7 y la columna «Resultado en `fe0c9f3`» están bien.
  - `test_waves.py` da kind 52, staging 51 y prod 49 tanto en la rama como en la base. Lo corrí yo.
  - Paso 8: 95 pruebas recogidas en la rama frente a 92 en la base (`--collect-only`).
  - **Pero** la fila 20 de «Re-corrido en U03-T07» dice «`make -C decision-registry check` código 0, 672 pruebas». Mi corrida da exit 2 con `1 failed, 671 passed`. La cifra es real como corrida del codificador, pero hoy no es reproducible: se cae con F-01.
- **`CANDIDATAS.md` (punto 6).** Las 2 líneas retiradas reaparecen literales entre `~~`, así que no se quitó ninguna línea ajena. F-01 de U03-T03 queda atendida salvo por la holgura, que va en una entrada nueva. F-09, F-10 y F-11 sí quedaron corregidas en `cierre-demo.md`.

## Tareas candidatas (defectos reales fuera de alcance)
- La consulta sin versión hace `Parallel Seq Scan` de toda la tabla, sin usar el índice. Ya está anotada en `CANDIDATAS.md:256`.
- Bitácora: dice «135 failed, 537 passed» y en otro sitio «135 failed, 1 failed, 671 passed» para la misma primera corrida. Es una inconsistencia menor.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t07-r1/`:
- `check-decision-registry.log`: `make check` completo, con `uptime`; exit 2 en 38 min 26 s.
- `ca1-2-3-rama.log`, `f04-base-rama.log` y `peor-caso-6x.log`: CA-1 a CA-3, `test_f04` en base y rama, y las corridas extra del peor caso.
- `mut-1-2.log`, `mut-3-4.log` y `mut-5.log`: las mutaciones (los scripts están en `mutations/`).
- `explain-revisor.log` y `psycopg-prepare-revisor.log`: los `EXPLAIN` y los conteos de planes genéricos.
- `ca4-5-6-8greps.log`: los greps de CA-4, CA-5, CA-6 y CA-8.

```
VEREDICTO: NO-VERDE
ROJO|CA-3 y CA-8, test_queries.py:684|explanation recibe 503 con el daily en 200 a 2,33 s: tope igual a la espera del pool sin holgura; make check exit 2
NARANJA|CA-7, test_queries.py:654-661|la guarda de prepare=False no detecta su retirada: el plan genérico llega en la ejecución 11 y la prueba hace 10
AMARILLO|queries.py:325-326|un solo arm para las dos sentencias de monitoring_lag
AMARILLO|test_queries.py:684|aserción de explanation aflojada a pool + margen
INFORME: revisiones/U03-T07/ronda-1.md
```
