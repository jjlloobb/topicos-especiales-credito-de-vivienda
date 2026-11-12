# Ronda 2 — U08-T03

VEREDICTO: VERDE

Los 8 criterios pedidos y `make -C case-management check` pasan en mi propia corrida, en serie, sobre `7ad2c89` (HEAD `91dd39e`). Los tres NARANJA de la ronda 1 (F-01, F-02 y F-03) quedan cerrados. Lo comprobé con experimentos en tiempo real y con mutaciones, y todas las mutaciones dan rojo. Quedan tres AMARILLO, ninguno bloquea. La tarea en el worktree es el blob `bac5c9ce…` (`git hash-object`). El worktree está limpio antes y después (`git status --short` sale vacío).

## Criterios de aceptación, verificados por mí
Corrí todo desde `vectra-risk/` con `run_ca.sh`, en serie, con `uptime` antes y después de cada corrida. La carga estuvo entre 9 y 17.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | intake + PBT-U8-06 | el de la tarea, con `-rs -s` | pasa: 18 passed en 118 s (carga 9,2 → 17,4) |
| 2 | evidencia + PBT-U8-07 | el de la tarea, con `-rs -s` | pasa: 49 passed en 359 s (carga 17,4 → 12,5). Aparecen las 5 pruebas nuevas y la PBT imprime `recorridos abandono -> decision nueva: 40` |
| 3 | barrido, retry y gauges | el de la tarea | pasa: 20 passed en 22 s |
| 4 | credit | el de la tarea | pasa: 21 passed en 10 s |
| 5 | API, degradación y apagado | el de la tarea | pasa: 19 passed en 31 s |
| 6 | 9 rutas | `build_app()` + `REGISTRY` | pasa: imprime `OK` |
| 7 | import-linter + grep | el de la tarea | pasa: 4 KEPT; el grep sale vacío |
| 8 | docs y plan | el de la tarea | pasa: 5 líneas `[x]` con `(U08-T03)` |
| 9a | `make -C case-management check` | — | pasa: lint, ruff format y mypy strict limpios; **305 passed en 566 s**; los 4 módulos puros siguen al 100 %; carga 13,0 → 14,1 |
| 9b | `contracts` | `git diff --stat b0130ae..91dd39e -- vectra-risk/contracts` | vacío: no cambia, así que no la volví a correr |

Ninguna prueba se saltó: `-rs` no muestra omisiones y ningún archivo tocado tiene `skip` ni `xfail`. CA-2 dura 6 minutos con Postgres real, así que no es una suite vacía.

## Verificación de los hallazgos de la ronda 1
- **F-01, arrendamiento: cerrado.** Las salidas están en `exp.log`.
  - **E1 en tiempo real** (100 `fail_closed`, registro de 2 s, la réplica B arranca a los 32 s): `claimed_a=100 claimed_b=0 requests=100 dup=0 states={confirmada:100} batch_s=50.4 max_in_flight=4`. En la ronda 1 eran 40 llaves duplicadas.
  - **Envío inmediato que falla con el registro caído (E4):** la decisión da 503 y la consulta 204. En los dos casos la fila queda con `attempts=1` y `next_attempt_at` en +0,97 s y +0,80 s: vuelve a ser elegible según el backoff, no a los 125 s. A los 1,5 s el reconciliador la reclama y queda `confirmada`.
  - **Reapertura de una consulta abandonada con el registro caído (E6):** 204 y `next_attempt_at` en +0,88 s; luego queda `confirmada`.
  - **Envío inmediato que lanza una excepción inesperada (E5):** 500 y la fila queda arrendada 124,9 s; el reconciliador reclama 0 en ese momento. Es el costo esperado, igual que el de una réplica muerta (ver F-02 abajo).
  - **Mutaciones sobre las pruebas del diff:** con `_LEASE = 30 s`, la prueba de las 2 réplicas da rojo. Con `_LEASE = 0`, las dos pruebas del envío inmediato (decisión y consulta) dan rojo.
  - **Cifra y costo:** 125 s se deriva por fórmula (`BATCH_SIZE // RECONCILER_CONCURRENCY * REGISTRY_TIMEOUT * 2`), con el mismo estilo que `WORKER_WORST_CASE` del diseño (P-U8-01). P-U8-04 no fija ningún arrendamiento. Que una réplica muerta retenga sus filas hasta 125 s es aceptable: la alerta `CaseEvidencePending` salta a 1800 s y el abandono es a las 24 h. Hay matices de la derivación en F-01 abajo.
- **F-02, PBT-U8-07: cerrado.** Las salidas están en `mut.log`, `mut2.log` y `mut3.log`.
  - El recorrido forzado se cuenta: 40 en mi corrida de CA-2, y la prueba exige más de 0.
  - Mi mutación de `_resolve_conflict` (confirmar la decisión nueva) da **rojo**.
  - Payload de otra evidencia con la misma llave: **rojo**.
  - Momento cambiado en el reenvío: **rojo**.
  - Momento corrido 1 h, estable entre reintentos y **con el recorrido forzado anulado** para aislar el invariante: **rojo** en `test_evidence.py:129` (`norm(req["payload"]) in candidates[...]`). Es decir, el invariante de carga por evidencia funciona por sí mismo, no solo el recorrido forzado.
- **F-03, 401: cerrado.** Quitando la guarda de `_actor`, la prueba del diff da rojo para `acr` y para `auth_time` (500 en lugar de 401).
- **F-05: cerrado.** Comparé cada constante movida con su valor anterior y con el diseño:
  - `SWEEP_INTERVAL` 300 s: igual al anterior y a BR-U8-10 (5 min).
  - `GAUGE_INTERVAL` 30 s: igual al anterior y dentro del rango de P-U8-04 y 08.
  - `JOBS_OVERDUE_AFTER` 30: igual al anterior y a la definición de `vectra_case_jobs_overdue` en P-U8-07 («`run_at < now() - 30 s`»).
  - `SERVING_CONFIG_CACHE_TTL` 5 s: igual al anterior y a NFR-U8-15.
  - `RECONCILER_BACKOFF_JITTER` 0,2 e `RECONCILER_INTERVAL` 1 s: iguales a los anteriores y a P-U8-04.
  - `DB_ACQUIRE_TIMEOUT` 2,0 y `DB_CONNECT_TIMEOUT` 2: iguales a los anteriores.

  El único valor que cambia es el arrendamiento, a propósito. Ya no hay nombres repetidos con el worker.
- **F-07: cerrado.** `handlers()` ya no recibe parámetros.
- **F-06:** la nota está en la bitácora (sección «F-06»): explica que la salida roja se sobrescribió y aclara qué contiene el commit `520741a`.
- **`CANDIDATAS.md`:** el diff de la ronda no lo toca. Contra la base (`5cf2ebb..91dd39e`) solo tiene 2 líneas añadidas, por el arbitraje, y ninguna quitada.

## Hallazgos
### F-01 · AMARILLO · config.py (`RECONCILER_LEASE`) · La derivación de 125 s no cuenta todo el tiempo de un turno
La fórmula solo cuenta 2 × `REGISTRY_TIMEOUT` por turno. Deja fuera tres cosas:
- la obtención del token en cada intento (`TOKEN_TIMEOUT` = 2 s; tras un 401 se invalida y se vuelve a pedir);
- las transacciones de `_confirm` y `_fail` (con `DB_ACQUIRE_TIMEOUT` de 2 s cuando el pool está lleno);
- los envíos extra de `_resolve_conflict`, uno por cada decisión abandonada del caso.

Además, `httpx.Timeout(2.5)` se aplica por fase (conexión, lectura y escritura), no al total de la llamada. Con todo eso, el peor caso real ronda los 9 s por turno, unos 225 s por lote. Si se supera, el único efecto es un reenvío idempotente: no se corrompe nada. El patrón es el mismo de `WORKER_WORST_CASE` en el diseño, por eso no bloquea. Para no depender de la cifra, se podría renovar el arrendamiento por fila, o al menos documentar qué cubre.

### F-02 · AMARILLO · evidence.py (envío inmediato) · Si el envío inmediato se interrumpe, la fila espera 125 s
Si el proceso muere, o `settle` lanza algo que no es `VectraError`, después del INSERT, la evidencia queda arrendada 125 s. Antes de esta ronda volvía a ser elegible al instante. Lo medí en E5: 500 y 124,9 s de espera. Es aceptable frente a la alerta de 30 min, pero `services.md` solo documenta este costo para una réplica muerta, no para el envío inmediato.

### F-03 · AMARILLO · CANDIDATAS.md (línea del apagado) · La candidata del SIGTERM dice «~62 s» y ya no es exacta
Con la cifra de esta ronda, el lote puede durar hasta 125 s, y más según F-01. La línea la escribió el orquestador; conviene actualizarla para U08-T05 (`terminationGracePeriodSeconds`). No es un defecto del codificador.

## Tareas candidatas (defectos reales fuera de alcance)
- U0, `deps._send`: `httpx.Timeout(timeout)` es por fase, no el total de la llamada. El «timeout por llamada» de NFR-U8-30 no se cumple de forma estricta.
- Que la candidata del apagado diga 125 s o más (F-03).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u08-t03-r2/`:
- `CA1.log` … `CA8.log`, `CA9a.log` y `summary.txt`: cada corrida con su `uptime`.
- `run_ca.sh`: el script de la corrida en serie.
- `exp/test_rev2_exp.py`: E1, E4, E5 y E6, y las mutaciones (fuera del worktree).
- `exp.log`: E1 a E6, la mutación del 401 y las del arrendamiento.
- `mut.log`, `mut2.log` y `mut3.log`: las mutaciones de PBT-U8-07.

```
VEREDICTO: VERDE
AMARILLO|config.py RECONCILER_LEASE|La derivación de 125 s no cuenta el token, la base ni los envíos extra de _resolve_conflict; httpx.Timeout es por fase
AMARILLO|evidence.py envío inmediato|Si el envío inmediato se interrumpe, la fila espera 125 s (E5); no está documentado
AMARILLO|CANDIDATAS.md apagado|La candidata del SIGTERM dice ~62 s; con el arrendamiento nuevo el lote puede durar 125 s o más
INFORME: revisiones/U08-T03/ronda-2.md
```
