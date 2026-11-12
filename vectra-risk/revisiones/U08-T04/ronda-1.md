# Ronda 1 — U08-T04

VEREDICTO: NO-VERDE

Hay un ROJO: un resultado tardío de un ciclo anterior se aplica al caso, y PBT-U8-01 no lo detecta porque su modelo de referencia copia la guarda del código. Todo lo demás pasa: los diez criterios dan código 0 con mi propia corrida, y de 19 mutaciones sobrevive una. El worktree quedó limpio (`git status --short` vacío, HEAD `6e2251f`, blob de la tarea `c374ce1005f4a06f9e14ebf22311900731508a47` comprobado).

## Criterios de aceptación, verificados por mí
Todo corrió en serie desde el script `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08-t04/run-cas.sh`. El `uptime` de cada corrida, antes y después, está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08-t04/summary.txt`.

| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `uv run pytest case-management/tests/integration/test_worker_clients.py -v` | pasa: 15 passed en 10,2 s (carga 5,7 → 7,6) |
| 2 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_evaluation.py …/test_case_machine.py -v -s` | pasa: 3 passed en 233 s (carga 7,6 → 11,8). Semilla `1488649833`, `max_examples=500`. Recorridos: `six_lost` 63, `late_after_expire` 680, `late_after_retake` 85, `abandon_decide` 69, `escalations` 176, `frozen_then_thawed` 67. **Pero su oráculo de `late_result` copia la guarda: ver F-01** |
| 3 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_worker.py …/test_worker_shutdown.py -v` | pasa: 38 passed en 61,5 s (carga 11,8 → 8,8) |
| 4 | `uv run pytest case-management/core_banking_mock/tests -v && uv run python -c "…build_app()…"` | pasa: 14 passed y `OK` |
| 5 | bucle `test -s`, `grep` de esqueletos, fixture | pasa: sin `FALTA`, `fixture OK 5` |
| 6 | encabezado de semilla; `--cov=vectra_case --cov-branch --cov-fail-under=95`; `coverage report --fail-under=100` sobre los 8 módulos | pasa: semilla impresa; 372 passed en 503 s; total 96,72 %; los 8 módulos al 100 % (649/0/126/0). Sin `omit` ni `pragma` (`grep` vacío en `src`, `coveragerc` y `pytest.ini`) |
| 7 | `uv run lint-imports --config case-management/.importlinter` y los dos `grep` | pasa: 5 contratos kept, `grep` sin salida |
| 8 | la cadena de 8 `grep` y el diff del plan | pasa: conteo de P-1..P-5 = 5; el diff solo cambia las casillas de los Pasos 14, 15, 17 y 18; el 16 sigue `[ ]` |
| 9 | `make -C case-management check` | pasa: rc=0, 386 passed en 22 min 20 s (carga 11,5 → 11,2, con picos de 19) |
| 10 | `test_traceability.py --unit case-management --all \| grep …` y `--all` en la rama y en la base (`git archive a782f25`) | pasa: la primera no imprime nada. Base 67 líneas, rama 57; `comm -13` vacío (ningún identificador nuevo); se cierran 10 (INF-U8-03, NFR-U8-02, 03, 11, 26, 32, 33, 45, 52 y P-U8-08); de U8 quedan las 14 esperadas |

## Hallazgos

### F-01 · ROJO · `case-management/src/vectra_case/evaluation.py:62-77` y `case-management/tests/property/test_case_machine.py:377` · Un resultado tardío de otro ciclo se aplica, y el modelo de PBT-U8-01 copia la guarda
- **El código.** La guarda `attempts = :attempt` no distingue entre tomas de ciclos distintos.
  - `_FROZEN` vuelve `attempts` a 0, y el `retry` del CRO también.
  - Después de esos reinicios, la toma siguiente vuelve a ser el intento 1.
  - El resultado tardío de un intento 1 anterior pasa entonces la guarda.
- **Reproducción**, con mi prueba `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08-t04/test_rev_aba.py`, corrida sobre una copia (`git archive`), nunca en el worktree:
  1. A toma el intento 1 y se queda parado.
  2. Pasan 30 s y B lo retoma como intento 2.
  3. El intento de B termina en `FailClosed(model_frozen)`.
  4. El barrido descongela el caso y C toma el intento 1.
  5. Llega el resultado de A: `applied True`, el caso pasa de `en_evaluacion` a `listo` con `recommendation_entry_id='7'` y se borra el trabajo vivo, así que el intento de C se descartará.
  - Con un 403 → `retry` del CRO → nueva toma, la variante da lo mismo: `ABA retry True … 'listo'`.
  - Resultado: `2 failed in 17.62s`.
- **Qué incumple.** BLM §4 (PBT-U8-01): «el resultado de una toma anterior nunca modifica el caso». Ese es un invariante que las Precisiones exigen a CA-2.
- **Por qué la PBT no lo ve.** `_late` decide si el resultado cuenta con `current = m.state in IN_FLIGHT and m.job is not None and m.attempts == old.attempt`. Es la misma guarda del código: el oráculo no es independiente en ese punto. El resto del modelo (`expected()` y la tabla `ALLOWED`) sí está escrito aparte.
- **También el diseño.** BR-U8-08 afirma «como cada toma incrementa el número (BR-U8-07), el resultado tardío de una toma anterior nunca pasa la guarda». Es falso cuando `attempts` vuelve a 0.
- **Arreglo posible:** una guarda que identifique la toma, por ejemplo el `locked_until` que fijó esa toma, o un contador de tomas monotónico. El modelo de la PBT debería marcar como «vigente» solo una toma sin otra posterior.
- Esto cambia el texto de BR-U8-08: el orquestador decide si pide una precisión del diseño.
- **Afecta a la demo D2**: congelar y descongelar es justo ese recorrido.

### F-02 · NARANJA · `case-management/src/vectra_case/job_queue.py:23` · Ninguna prueba distingue `SKIP LOCKED`
- La mutación M01 cambia `FOR UPDATE SKIP LOCKED` por `FOR UPDATE` y sobrevive (`1 passed`).
- `test_a_job_that_is_not_due_yet_is_not_taken_and_two_workers_never_take_the_same_job` solo comprueba que no haya doble toma, y un bloqueo simple también cumple eso.
- Lo que P-U8-01 pide (no esperar a la fila bloqueada) queda sin probar.
- Quitar el bloqueo entero (M02) sí muere.

### F-03 · AMARILLO · `case-management/core_banking_mock/tests/test_core_mock.py` (`test_a_fresh_start_has_zero_write_attempts_in_metrics`) · «Recién iniciado → 0» depende del orden de las pruebas
`WRITE_ATTEMPTS` es global al proceso, y la prueba exige el valor absoluto 0. Pasa porque corre antes que los `POST` del mismo archivo; con otro orden, o con otra prueba antes en el proceso, fallaría.

### F-04 · AMARILLO · `case-management/src/vectra_case/worker.py:78-93` · La gracia de 20 s no empieza en el `SIGTERM`
- Con los 16 trabajos en vuelo, el bucle queda bloqueado en `_sem.acquire()` hasta que termina uno, y solo después empieza `drain(20 s)`.
- Los topes duros (`asyncio.timeout`) acotan la espera, así que no rompe ningún criterio.
- Pero el peor caso del apagado no es 20 s, y eso importa para el `terminationGracePeriodSeconds` de U08-T05.

## Comprobaciones pedidas
- **PBT-U8-01: las cuatro corridas `ci` que fallaron**, leídas en `pbt01-ci1..4.log` del scratchpad del codificador:
  - ci1: «`listo` nunca recibe otro intento» pasó de contar llamadas a scoring a contar tomas. Es coherente con BR-U8-07 (un intento es una toma) y no afloja el invariante.
  - ci2: corrigió `has_rec` en el modelo tras un vencimiento.
  - ci3: en una decisión sobre un caso que no está `listo`, ahora acepta 422 además de 409. Afloja un poco la aserción de estado HTTP, pero el invariante de estado (terminales, transición alcanzable) se sigue leyendo de la base.
  - ci4: el contador `frozen_then_thawed` daba 0; se añadió un recorrido forzado.
  - Ninguna afloja la propiedad sobre el código. El problema de verdad es F-01, que estaba en el modelo desde el diseño de `_late`.
- **PBT-U8-05:** compara contra hojas de texto (exacto, o subcadena si tiene ≥ 4 caracteres). Es razonable, y M11 (`free_text` en `channel`) muere.
- **P-1:** la tabla de `case_fsm` pasa de 18 a 19 transiciones aceptadas y solo añade (`en_evaluacion`, `attempt_6_failed`); la prueba unitaria lo fija en `80 - 19`. `git diff --name-only a782f25 HEAD -- case-management/migrations` sale vacío.
- **P-5 y el Paso 16:** `retention.py` y `config.py` no aparecen en el diff. `expire_case` vive solo en `tests/doubles/worker_support.py`.
- **Espera de 10 → 30 s en la prueba de `SIGTERM`:** es el `wait_until` previo a la señal (esperar la primera llamada a scoring). Las aserciones del apagado no cambiaron: `proc.wait(timeout=20)`, `3 ≤ elapsed ≤ 10` y `5 ≤ elapsed < 20`. Es holgura de la prueba, no esconde un defecto. M18 (drenaje sin espera) muere.
- **Ramas quitadas:**
  - `Evidence.record_view`: es inalcanzable de verdad. Nadie salvo el dueño tiene `DELETE` sobre `evidence_outbox`, así que el `UPDATE … RETURNING` de una fila recién leída siempre devuelve una fila. Ningún otro archivo de `case-service` cambia.
  - La rama de `worker.run` es código nuevo de esta tarea, no de `case-service`.
- **`case-management/conftest.py`:** es necesario. En mi copia, sin él, `core_banking_mock/tests` falla en la recolección (`1 error`), y la tarea prohíbe `__init__.py`. No es desborde.
- **Contrato `mock-isolated`:** la tarea lo permite («si hace falta un contrato nuevo, `.importlinter`»), y M19 (`import vectra_case.credit` en el mock) lo rompe (`4 kept, 1 broken`).
- **U0, migraciones, `pyproject.toml`, `uv.lock`:** fuera del diff (`git diff --name-only a782f25 HEAD` vacío para todos).
- **Mutaciones**, todas sobre una copia (`git archive`) en mi scratchpad (resumen: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08-t04/mut-summary.txt`; detalle: un `mut-*.log` por mutación en esa misma carpeta). **Mueren** las 18 restantes; cada una cae por una prueba que afirma sobre ese comportamiento:
  - M02: sin `FOR UPDATE`.
  - M03: sin la guarda `attempts`; cae `test_a_stopped_worker_is_replaced_after_30_s_and_the_late_result_of_the_first_is_discarded`.
  - M04: escala con `read > 6`.
  - M05: sin escalar en el intento 6 al aplicar.
  - M06: la forma vieja de `ServingConfig` no falla cerrado.
  - M07: LRU de 5.
  - M08: LRU convertida en FIFO.
  - M09: `first_evaluation` sin mirar `ever_degraded`.
  - M10: `_FROZEN` sin `ever_degraded`.
  - M11: `free_text` en la solicitud.
  - M12: sin `SAVEPOINT`.
  - M13: el mock sin el middleware.
  - M14: el mock cuenta cualquier 4xx.
  - M15: contador con etiqueta.
  - M16: el handler acepta.
  - M17: la reprogramación no suelta el arrendamiento.
  - M18: drenaje sin espera.
  - M19: el mock importa `vectra_case`.

  **Sobrevive** M01 (`SKIP LOCKED`; ver F-02).

## Tareas candidatas (defectos reales fuera de alcance)
- **Decisión `pendiente_registro` cuyo caso vence antes del ack** (queda `confirmada` con el caso `vencido`):
  - Es código de U08-T03 (`Evidence._confirm`), y esta tarea no lo toca: el único cambio en `evidence.py` es el `assert`.
  - Solo ocurre si algo pasa el caso a `vencido`, y eso lo hace el Paso 16, diferido. Ninguna demo (flujo base, D1, D2, D3) corre la retención.
  - Es bien llevada como candidata.
- **BR-U8-08 y BLM §4:** la afirmación de que «cada toma incrementa el número» es falsa cuando `attempts` vuelve a 0. Si el orquestador decide resolver F-01 con una precisión del diseño, la candidata es esa.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u08-t04/`:
- `ca1.log` a `ca10.log`, `ca6a.log`, `ca6b.log`, `ca6c.log`, `ca9.log` y `summary.txt` (con `uptime`).
- `trace-base.txt` y `trace-rama.txt`.
- `test_rev_aba.py` (reproducción de F-01).
- `mut-summary.txt` y los `mut-*.log`.

**Contenedores:** no queda ninguno mío. Los 9 que siguen con la etiqueta `org.testcontainers` son de la sesión `71364cca-4f64-45f9-823d-73a4a28460fe` (ryuk creado a las 14:36), de otro agente: mis procesos ya terminaron y no los toqué.

```
VEREDICTO: NO-VERDE
ROJO|case-management/src/vectra_case/evaluation.py:62-77 y case-management/tests/property/test_case_machine.py:377 (CA-2)|Un resultado tardío de un ciclo anterior (tras congelar/descongelar o retry) se aplica; el modelo de PBT-U8-01 copia la guarda attempts = :attempt
NARANJA|case-management/src/vectra_case/job_queue.py:23|Ninguna prueba distingue FOR UPDATE SKIP LOCKED de FOR UPDATE (mutación M01 sobrevive)
AMARILLO|case-management/core_banking_mock/tests/test_core_mock.py|«Recién iniciado → 0» depende del orden de las pruebas
AMARILLO|case-management/src/vectra_case/worker.py:78-93|La gracia de 20 s empieza después de liberar el semáforo, no en el SIGTERM
INFORME: revisiones/U08-T04/ronda-1.md
```
