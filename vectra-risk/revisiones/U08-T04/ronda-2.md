# Ronda 2 — U08-T04

VEREDICTO: NO-VERDE

F-01 está resuelto. La guarda nueva aguanta todos los ataques que probé, y PBT-U8-01 ya no copia la guarda. Queda un ROJO nuevo, introducido en esta ronda al arreglar F-03: la línea de aceptación del Paso 17 «`GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0» se quedó sin ninguna prueba que la verifique (CA-4). El worktree quedó limpio: `git status --short` vacío, HEAD `989ecad`, blob de la tarea `c374ce1005f4a06f9e14ebf22311900731508a47`. Todo lo que corrí sobre copias está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev2-u08-t04/`, que en adelante llamo `R/`. Copias usadas: `new` = `git archive HEAD`, `old` = `git archive 812d885`, `mut` = otra copia de HEAD para las mutaciones.

## Criterios de aceptación, verificados por mí
Los corrí en el worktree y en serie con `R/run-cas.sh`. El `uptime` de antes y después de cada corrida está en `R/summary.txt`.

| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `uv run pytest …/test_worker_clients.py -v` | pasa: 15 passed en 9,8 s (carga 6,7) |
| 2 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_evaluation.py …/test_case_machine.py -v -s` | pasa: 3 passed en 201 s, semilla 1647643744, `late_after_reset` = 351, los demás contadores > 0. También pasa sobre la copia `new` (semilla 2180337286, `late_after_reset` = 323) |
| 3 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_worker.py …/test_worker_shutdown.py -v`, **6 veces** | pasa 6/6: 42 passed cada vez, entre 52 y 76 s, con carga de 5,2 a 10,9 y el puerto 8081 libre antes de cada corrida (`R/ca3-1.log` a `R/ca3-6.log`) |
| 4 | `uv run pytest case-management/core_banking_mock/tests -v && … build_app …` | rc 0 (14 passed y `OK`), **pero el contenido falla: ver F-01** |
| 5 | bucle `test -s`, `grep` de esqueletos, fixture | pasa: sin `FALTA`, `fixture OK 5` |
| 6 | encabezado de semilla; `--cov … --cov-fail-under=95`; `coverage report --fail-under=100` sobre los 8 módulos | pasa: semilla 3529919823; 376 passed, total 96,95 %; los 8 módulos al 100 % (650 sentencias / 0 sin cubrir / 126 ramas / 0 parciales). `grep omit\|pragma` en `src`, `coveragerc` y `pytest.ini`: vacío |
| 7 | `lint-imports` y los dos `grep` | pasa: 5 kept, 0 broken |
| 8 | los 8 `grep` y el diff del plan | pasa: conteo 5; solo cambian los Pasos 14, 15, 17 y 18; el 16 sigue `[ ]` |
| 9 | `make -C case-management check`, una vez y en serie | pasa: rc 0, 390 passed en 12 min 36 s (carga 9,8 → 6,7) |
| 10 | trazabilidad `--unit case-management --all \| grep …` y `--all` | pasa: la primera no imprime nada; `--all` da 57 líneas, idénticas a las de la ronda 1 |

Sin migración: `git diff a782f25 HEAD --name-only -- case-management/migrations contracts pyproject.toml uv.lock` sale vacío.

## F-01 de la ronda 1 (la guarda por toma): resuelto
- **Mi reproducción** de la ronda 1 (`test_rev_aba.py`, las dos variantes), sobre `new`: `2 passed`. El resultado tardío de A da `applied False` y el caso queda intacto (`R/aba-new.log`).
- **Ataques**, en `R/test_rev2_attack.py`, corridos sobre `new` (`R/attack-new.log`):
  - **(a) `:lease IS NULL`.** Solo pasa `None` el escalamiento del intento 6 dentro de la propia `take`, con la fila bloqueada (`job_queue.py:62`). `Taken.leased_until` es un `datetime` sin opción de `None`, y `Evaluator._apply` siempre pasa `taken.leased_until`. Un resultado tardío no puede llegar con `None`.
  - **(b) Quién escribe `locked_until`.** Solo dos sitios: la toma (`now + 30 s`) y el reprogramado (`NULL`). Los `INSERT` del barrido y del `retry` lo dejan en `NULL`, y no hay renovación del arrendamiento. Mi prueba `test_d` pasa: tras un 503 reintentable, el trabajo queda con `locked_until NULL`; el resultado tardío de A se descarta; C toma el intento 3; A y B tardíos se descartan; el de C se aplica.
  - **(c) Mismo microsegundo.** Lo reproduje: la colisión ocurre, pero solo si fuerzo **dos** relojes atrasados (el del barrido y el del worker C) exactamente a `t_A`.
    - Con un único reloj coherente es imposible. El trabajo nuevo nace con `run_at` igual al reloj del reinicio, que es mayor que `t_A`, así que `L_C > L_A`. Una retoma exige además `now ≥ L_A`, así que `L_C ≥ L_A + 30 s`.
    - En producción haría falta un desfase de al menos 30 s entre pods y coincidencia al microsegundo: es teórico.
    - Hay otro límite teórico: en READ COMMITTED, el `EXISTS` se reevalúa con la instantánea de inicio de la sentencia (EvalPlanQual). Solo lo explotaría un backend detenido varios segundos entre su instantánea y el bloqueo de la fila, a lo largo de varias transacciones separadas por llamadas a scoring.
  - **(d) Retoma a los 30 s del mismo intento.** A se descarta y el resultado de B se aplica (`test_d`, y la prueba de la ronda 1 `stopped_worker`). Un arrendamiento vencido sin retoma sigue aplicando su resultado (`test_d2`); es coherente con `Model.live`.
  - Un resultado tardío que escalaría (403) de otro ciclo no escala ni emite `fail_closed` (`test_e`).
- **Mutaciones sobre la guarda**, en la copia `mut`, con `src` restaurado y comprobado con `cmp`:
  - **M20**, guarda de toma anulada en los 4 `UPDATE`: muere (`2 failed`, las pruebas `previous_cycle`).
  - **M21b**, guarda anulada solo en `_FROZEN`, `_RETRY` y `_ESCALATE`: **sobrevive a `test_worker.py`** (`38 passed`) y solo la mata la PBT, a los 6 min (`R/mut-M21b-*.log`). Ver F-02.
- **`Model.live` es independiente del código.** Es la identidad del último `Taken` que entregó un intento. Se anula por sus propios eventos: resultado aplicado, descongelamiento, `retry`, escalamiento en la toma, vencimiento y decisión. No mira `attempts`; el contador solo usa `attempts` para clasificar el recorrido.
- **PBT corregida contra el código de la ronda 1** (copia `old` con el `test_case_machine.py` nuevo): falla, `assert True is False` en `_late`, con `script='late_after_thaw'`, semilla 1214157013 (`R/pbt-old.log`).
- **Guiones forzados.** Quité `late_after_thaw` y `late_after_retry` en las dos copias y corrí con `ci`:
  - sobre `old`, la exploración libre **también encuentra el defecto** (semilla 2995875698, 5 min 32 s). El camino que encuentra es otro: dos `late_result` de la misma toma, cuyo primer resultado reprogramó el trabajo;
  - sobre `new`, `late_after_reset` = 24 sin guiones.
  - Conclusión: los guiones aceleran la exploración, pero no esconden que la exploración libre no llegaría sola. No importa (`R/pbt-old-free.log`, `R/pbt-new-free.log`).
- **Ninguna propiedad se aflojó.** En `git diff 812d885 HEAD -- case-management/tests/property` solo hay añadidos: guiones, `live` y el contador. La condición de `_late` se endurece (identidad de la toma), y `assert applied is current` y la igualdad del `snapshot` siguen como estaban.

## Hallazgos
### F-01 · ROJO · `case-management/core_banking_mock/tests/test_core_mock.py:63-73` (CA-4) · «Recién iniciado → 0» quedó sin prueba
- **Qué exige la tarea.** CA-4 pide «un caso por cada línea de aceptación del Paso 17», y una de esas líneas es «`GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0». Su rojo obligatorio es: «crear el contador sin inicializarlo hace fallar "recién iniciado → 0"». Además, «la métrica se lee de `GET /metrics`, no de la variable del módulo».
- **Qué hace la prueba nueva.** Compara `/metrics` contra `WRITE_ATTEMPTS._value.get()`, es decir, contra la variable del módulo. Eso es una tautología para el valor inicial.
- **Mutación M22**, `WRITE_ATTEMPTS.inc(3)` al importar `metrics.py` (el contador ya no nace en 0):
  - sobre HEAD **sobrevive**: `14 passed`, y tampoco la ve ninguna otra prueba de U8 (`R/mut-M22*.log`);
  - sobre el código de la ronda 1 muere: `1 failed, 13 passed`.
- **Impacto.** Es la base de la demo D3.
- **Arreglo posible.** Medir en un proceso nuevo, por ejemplo `subprocess.run([sys.executable, "-c", …build_app… GET /metrics])` con la afirmación `== 0`. Así no se depende ni del orden ni del valor global.
- **Lo que sí quedó bien de F-03.** La prueba sola, después de dos `POST` y con el archivo entero en orden inverso: siempre pasa (`R/f03.log`).

### F-02 · AMARILLO · `case-management/tests/integration/test_worker.py` · La guarda de toma en `_FROZEN`, `_RETRY` y `_ESCALATE` solo la cubre la PBT
M21b sobrevive a CA-3 y muere solo en PBT-U8-01. Bastarían pruebas deterministas con un resultado tardío no-`Recommendation` tras el reinicio: `model_frozen`, 503 y 403. Mi `test_e` es un ejemplo de la última.

### F-03 · AMARILLO · `business-rules.md` BR-U8-08 · «Nunca pasa la guarda» no dice su supuesto
La afirmación supone un reloj coherente entre los pods que toman y los que recrean el trabajo. La colisión del punto (c) es real si hay un desfase de al menos 30 s y coincidencia al microsegundo. Es teórica, pero el texto debería decirlo.

### F-04 · AMARILLO · `services.md` «Arranque y apagado del worker» · «≈ 20 s en el normal» exagera el caso normal
- **El caso normal.** `drain` termina cuando terminan las llamadas en vuelo, y esas llamadas están acotadas a 15,5 s o menos por sus timeouts; con un scoring sano, el apagado tarda segundos.
- **El peor caso.** Los ≈ 34 s (toma en curso ≤ 4 s + 20 s + `GRACEFUL_SHUTDOWN` de 10 s, en serie) son coherentes con `worker.run`.
- **Comprobación con un proceso real**, con 16 huecos ocupados y scoring de 6,5 s, y la gracia parcheada a 2 s en `-c` (`R/f04-*.log`):
  - código nuevo: `SIGTERM` → salida en 2,37 s, ninguna llamada nueva tras la señal, y los 16 trabajos quedan arrendados para la retoma;
  - código de la ronda 1: 5,78 s, porque esperaba a que se liberara un hueco.

## CA-3: el fallo no identificado del codificador
- **No lo reproduje.** CA-3 pasó en las 6 corridas propias (carga de 5 a 11), y sus pruebas también pasaron dentro de CA-6 y CA-9.
- **La prueba más ajustada en tiempo** es `test_an_idle_worker_takes_a_new_job_within_600_ms`. La medí 14 veces:
  - con carga de 6 a 8: entre 0,14 y 0,34 s;
  - con dos `test_worker.py` en paralelo (carga de 15 a 18,5): entre 0,30 y 0,35 s.
  - Siempre quedó por debajo de 0,6 s (`R/idle600.log`).
- **Sospechoso más plausible:** del entorno, no del código. `test_worker_shutdown.py` exige el puerto fijo 8081 (`assert port_free(8081)`), así que choca si otra suite de U8 o un port-forward lo ocupa a la vez. Sin el log del codificador no se puede confirmar.

## Precisión de BR-U8-08 y del business-logic-model
- **Describen lo que hace el código:** `attempts` y el `EXISTS` sobre `locked_until`, el reprogramado a `NULL` y los trabajos nuevos sin arrendamiento.
- **No cambian ningún comportamiento que el diseño pidiera; lo hacen cumplir.** El único efecto observable nuevo es descartar un resultado repetido de la misma toma después de su propio reprogramado, y eso es coherente con PBT-U8-01.
- La salvedad del reloj está en F-03.

## Tareas candidatas (defectos reales fuera de alcance)
- Pruebas de U8 que usan el puerto fijo 8081 (`test_worker_shutdown.py`): chocan entre suites concurrentes. Conviene un puerto de sondas configurable para las pruebas, o serializar.
- Sigue en pie la candidata de la ronda 1: una decisión `pendiente_registro` cuyo caso vence antes del ack.

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev2-u08-t04/`:
- `summary.txt` (con `uptime`)
- `ca1.log` … `ca10.log`, `ca3-1.log` … `ca3-6.log`, `ca6a.log`, `ca6b.log`, `ca6c.log`, `ca9.log`
- `aba-new.log`, `test_rev2_attack.py`, `attack-new*.log`
- `pbt-old.log`, `pbt-new.log`, `pbt-old-free.log`, `pbt-new-free.log`
- `mut-M01.log`, `mut-M20.log`, `mut-M21b-*.log`, `mut-M22*.log`
- `f03.log`, `f04-new.log`, `f04-old.log`, `idle600.log`

**F-02 de la ronda 1:** M01 (`FOR UPDATE` sin `SKIP LOCKED`) muere: `TimeoutError` en `test_a_job_row_locked_by_another_transaction…`, `1 failed, 1 passed` (`R/mut-M01.log`).

**Contenedores:** no queda ninguno mío. El único con la etiqueta `org.testcontainers` en marcha es un ryuk de las 16:34, de la suite de `u10-t03` (otro agente). Los contenedores salidos son del 8 y el 10 de noviembre. No los toqué.

```
VEREDICTO: NO-VERDE
ROJO|case-management/core_banking_mock/tests/test_core_mock.py:63-73 (CA-4)|«GET /metrics recién iniciado → vectra_core_write_attempts_total = 0» quedó sin prueba (M22 sobrevive; la prueba compara contra la variable del módulo)
AMARILLO|case-management/tests/integration/test_worker.py|La guarda de toma en _FROZEN/_RETRY/_ESCALATE solo la cubre la PBT (M21b sobrevive a CA-3)
AMARILLO|business-rules.md BR-U8-08|«nunca pasa la guarda» supone un reloj coherente entre pods y no lo dice
AMARILLO|services.md «Arranque y apagado del worker»|«≈ 20 s en el normal» exagera; el peor caso ≈ 34 s es coherente
INFORME: revisiones/U08-T04/ronda-2.md
```
