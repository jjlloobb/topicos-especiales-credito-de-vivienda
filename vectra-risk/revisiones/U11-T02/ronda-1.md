# Ronda 1 — U11-T02

VEREDICTO: NO-VERDE

Ningún hallazgo es ROJO. Corrí los 10 criterios y todos pasan. Quedan tres NARANJA, que son huecos en las pruebas: el código se comporta bien en mi propia ejecución, pero hay mutaciones que sobreviven. Con RL-3 no bloquean y van a `CANDIDATAS.md`. Por contrato, cualquier NARANJA hace el veredicto NO-VERDE.

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u11-t02`, HEAD `b5bde13`, contra la base `7d05454`. El blob de la tarea es `1ab4455c…`, que coincide.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Proceso (CA-1) | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_process.py -v` (carga 10,07 → 9,31) | pasa: 18 passed en 7,76 s, rc 0, semilla 2730346764, 0 skipped. El tiempo corto se explica porque el reloj es simulado (`VirtualClock`) |
| 2 | Publicación (CA-2) | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_collector.py -v` (carga 8,64 → 10,79) | pasa: 21 passed en 78,97 s, semilla 848716036. PBT-U11-05 tarda 52 s y PBT-U11-07 tarda 25,6 s |
| 3 | Proceso real (CA-3) | el bloque literal, con `--basetemp` en mi scratchpad (carga 9,58 → 6,23) | pasa: 5 passed. Los archivos contienen `…north_star_ratio{channel="all",model_version_id="all",outcome="all",period="day"} 0.4`, luego `2`, `503`/`200`, las 4 rutas (`/v1/entries 404`) y `0` |
| 3b | Mi sonda de un solo proceso real | `scratchpad/rev-u11-t02/probe/probe.py` (carga 6,82 → 8,66) | pasa: ver la sección «Desviaciones» |
| 4 | Ejemplos E/S (CA-4) | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_examples.py -v` (carga 6,23) | pasa: 3 passed, semilla 606773709 |
| 5 | Volumen diferido (CA-5) | los tres comandos del criterio | pasa: da `0`, el grep no encuentra líneas (rc 1) y aparecen solo el marcador `volume` y `-m "not volume"` |
| 6 | Cobertura y `process.md` (CA-6) | el bloque literal (carga 8,23 → 10,47) | pasa: TOTAL 98,47 %. `collector` 100 %, `main` 98 %, `scheduler` 96 %, `state` 95 %. `compute` y `noise` 100 %. El grep sobre `process.md` encuentra los 6 términos |
| 7 | Paso 9 (CA-7) | `test ! -d … && echo OK` | pasa: `OK` |
| 8 | `check` (CA-8) | `uptime && make -C product-metrics check && uptime` (carga 5,36 → 11,74; 18 min 49 s) | pasa: rc 0. Lint y formato limpios, mypy da `Success` en 11 archivos, 3 contratos KEPT. Con `ci` (semilla 399450296): 199 passed. Cobertura del 100 %: 121 passed. Cobertura del 90 %: 199 passed, 98,47 % |
| 9 | Trazabilidad (CA-9) | `--unit product-metrics` y `--all` sobre HEAD y sobre `git archive 7d05454` | pasa: `--unit` da exactamente las 16 esperadas. En `--all`, la base tiene 75 y HEAD 70. El `diff` solo quita `INF-U11-01`, `NFR-U11-07`, `08`, `22` y `P-U11-03`, sin ningún fallo nuevo |
| 10 | Plan (CA-10) | `grep` y `git diff 7d05454 -- plan` | pasa: los Pasos 6 a 9 están `[x] (U11-T02)` y el 7 lleva la nota T3. No cambia ningún otro paso |

## Hallazgos

### F-01 · NARANJA · `test_process.py:183` y `test_main_process.py:164` · Ninguna prueba fija que la página en vuelo termine; cancelarla sobrevive
Probé la mutación S6: el `scheduler` compite `full_pass` contra `stop` y cancela la página en vuelo. **Sobreviven las 23 pruebas** de `test_process.py` y `test_main_process.py`. Hay dos causas:
- En proceso, la prueba activa `stop` dentro de `on_request`, después de la latencia y justo antes de responder, así que la página nunca queda cancelada a mitad.
- En subproceso, la prueba comprueba `double.completed == [1]` **después** de `process.stop()`. La parada ordenada de uvicorn deja terminar el handler del doble aunque el cliente ya haya cortado.

Lo comprobé con `probe2.py`, mandando SIGTERM con una página de 4 s en vuelo:
- El código real da `exit=0 apagado=3.97s completed_al_salir=[1]`. **El comportamiento es correcto.**
- Con el mutante da `exit=0 apagado=0.78s completed_al_salir=[] … completed_tras_parar_servidores=[1]`.

La afirmación de la bitácora («la página en vuelo quedó completa en el doble: `completed == [1]`») no distingue entre los dos casos. Arreglo: leer `completed` en el instante en que el proceso sale, antes de parar los servidores, o exigir que el apagado tarde al menos la latencia restante.

### F-02 · NARANJA · `scheduler.py:146` y `scheduler.py:195-197` · El plazo de 75 min y el reinicio diario de los reintentos no están fijados
- **D2.** Sobrevive con el plazo en 90 min. La prueba usa páginas de 18 min 45 s: con cualquier plazo en [75, 93,75) min la pasada vence igual en la quinta página. Arreglo: un caso justo por encima y otro justo por debajo de 75 min.
- **T6.** Sobrevive si la diaria no reinicia `_retries`. Con esa mutación, si la diaria de un día ya agotó sus 6 reintentos, la del día siguiente falla sin **ningún** reintento, lo que viola NFR-U11-09. `test_failed_daily_pass_retries_6_times…` deja de contar en el primer intento de la segunda diaria. Arreglo: que la segunda diaria también falle y haga 6 reintentos.

### F-03 · NARANJA · `main.py:67-72` · `_OpsServer.capture_signals` es código redundante y ninguna prueba lo ejerce
La mutación S3 quita el override y sobreviven las 23 pruebas, con salida 0. La S7 quita el override **y** el manejador del bucle, y da `assert -15 == 0`. Esto confirma la discrepancia 3 del codificador: el rojo de CA-3 descrito en la tarea es inexacto. El docstring de `main.py`, líneas 10-13, y `process.md` dicen que el override es lo que evita el `-15`, pero lo que lo evita es `loop.add_signal_handler`. Hay que quitar el override o corregir el texto.

### F-04 · AMARILLO · `state.py:128-130` · La rama `incremental_after_full_failed` se cubre de forma no determinista
En mi `check` y en mi CA-6 quedan sin cubrir las líneas 128-130, y `state` queda en 95 %. En el `check.txt` del propio codificador también salen sin cubrir. Sin embargo, la bitácora dice «`state.py` 97 %» (eso es de su `cov1.txt`). Falta una prueba que fije esa rama.

### F-05 · AMARILLO · `test_collector.py:600-614` · La fila «pasada fallida o vencida» de NFR-U11-07 no está en la tabla de CA-2
Esa fila se prueba en `test_process.py` (arranque y plazo), no en `test_collector.py`. El predicado no distingue el motivo, así que el efecto es equivalente.

### F-06 · AMARILLO · Logs vacíos
El proceso real emite líneas `{"level":"info","timestamp":…,"service":"product-metrics"}` sin contenido, unas 11 por recorrido en mi sonda. Es el texto de uvicorn y de httpx, que el filtro de U0 descarta. Es ruido y se trata como candidata.

### Desviaciones y afirmaciones que me pediste juzgar
- **CA-3 con dos subprocesos.** Cumple. El proceso del SIGTERM lo recibe durante la pasada del arranque, sin estado previo, así que «estado intacto» solo se prueba en proceso, y eso es CA-1. Mi sonda en **un** proceso hizo todo el recorrido: `/readyz` 503 → 200, `/metrics` con 0.4 y las dos marcas, las 4 rutas, la espera del ciclo incremental real (5 min), SIGTERM con su página de 4 s en vuelo, salida `0` en 4,6 s, `completed [1..5]` y `max_active 1`. Transcripción en `probe/probe.log`.
- **El `-15` solo sin ningún manejador.** Confirmado con S3 y S7 (ver F-03).
- **`test_reader.py`.** La afirmación no se aflojó, se endureció: pasa de «`seq=7` en algún mensaje» a «la lista de `seq` es exactamente `[7]`», ahora con el filtro real de U0. El fixture autouse solo restaura los manejadores y el nivel del logger raíz. No oculta fugas: evita que un `StringIO` de una prueba capture lo de las siguientes, y cada prueba de logs configura su propio stream.
- **El doble de U3.** Todos los valores por omisión son nulos o equivalentes (`asyncio.sleep`, `None`, `completed` solo acumula). El renombre `_handle` → `handle` no tiene otros usos. `tests/property/` no aparece en el diff, así que PBT-U11-02 está intacta. `test_reader` da 31 passed.
- **Denominador 0 con `BusinessMetrics` armado a mano.** La prueba vale: la mutación A9 (emitir siempre la razón) muere en ella.
- **SIGTERM en la incremental que sigue a una pasada ya terminada.** No incumple nada. La pasada no está a medias, y lo no publicado muere con el proceso, que sale. La readiness no se ve afectada.
- **Dos diarias en la misma noche.** Está fijado: la mutación T7 muere en `test_failed_daily_pass_retries_6_times…`, con intentos en `[0, 428, …]` en vez de `[0, 900, …]`. La semilla es fija, así que es determinista.
- **P-2 (b).** La condición es `never_succeeded = snapshot() is None`, así que solo aplica mientras no haya habido ninguna pasada exitosa. Hay prueba de las dos ramas: sin estado, 21 intentos; con estado, 1 + 6. Muere T4 (literal (a), con tope) y muere T5 (sin tope nunca).

### Mutaciones (copias en el scratchpad, perfil `dev`)
- **Muertas (25):**
  - Readiness: R1 (siempre lista), R2 (semiabierto da 503), R3 (cualquier estado del breaker).
  - Plazo: D1 (×2), D3 (`>=`), D4 (sin plazo).
  - Reintentos: T1 (16 min), T2 (7), T3 (5), T4, T5, T7.
  - `last_success`: L1 (avanza y publica en un ciclo fallido).
  - Allowlist y collector: A1 (etiqueta de más), A2 (`month=""` en todas), A3 (`month` en la consulta), A4 (constante de la allowlist), A5 (razón con dos cortes), A6 (identificador como valor), A7 (serie nueva), A8 (doble lectura), A9 (denominador 0), A10 (`last_full` en 0).
  - Pasada a medias: H1 (visible), H2 (borra el estado al parar).
  - Apagado: S2 (sin punto de parada entre páginas), S4 (sin manejador del bucle), S7.
- **Sobreviven:**
  - **D2, T6 y S6** (F-01 y F-02).
  - **S3** (F-03).
  - **S1 y L2**, que son equivalentes en lo observable: el punto de parada inicial ya impide la lectura, y `last_success` del estado se reescribe antes de cada publicación.
- **Oráculos:**
  - PBT-U11-05 es independiente del código: transcribe §5 y usa valores cerrados más identificadores generados, sin usar `PRODUCT_SERIES`.
  - PBT-U11-07 es mixta. La razón total frente a la suma de conteos publicados es consistencia interna. El total de `day`, en cambio, se calcula desde las `Spec`, independiente de `compute`.

### Alcance
- `git diff 7d05454 HEAD --stat` no toca U0, U1, U3, `compute.py`, `noise.py`, `reader.py`, `tests/volume/` ni chart, tools, observability, workflow o imagen.
- NFR-U11-02, 03 y 13 no aparecen escritos en `product-metrics/`.
- Sin desborde de alcance.

## Tareas candidatas (defectos reales fuera de alcance)
- U0 y U11: las líneas de log vacías de uvicorn y httpx (F-06). Se podría subir esos loggers a WARNING, o que U0 descarte los registros que se quedan sin campos.
- Diseño (ya anotada por el codificador): INF-U11-01 dice «unos 15 s» y, con P-1 (a), el breaker abre a los 30 min.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u11-t02/make-check.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u11-t02/ca1.log`, `ca2.log`, `ca3.log`, `ca4.log`, `ca6.log` (misma carpeta)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u11-t02/trace-head-unit.txt`, `trace-head-all.txt`, `trace-base-unit.txt`, `trace-base-all.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u11-t02/probe/probe.log` (sonda de un proceso) y `probe/probe2.py` (original frente a S6)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u11-t02/mut-batch1.txt`, `mut-batch2.txt`, `mut-batch3.txt`, `mut-S7-ninguno.log`, `mut-<id>.log`

Al terminar, el worktree está limpio: `git status --short` sale vacío y HEAD sigue en `b5bde13`. No dejé ningún proceso mío escuchando.

```
VEREDICTO: NO-VERDE
NARANJA|test_main_process.py:164, test_process.py:183|ninguna prueba fija que la página en vuelo termine (mutante que la cancela sobrevive)
NARANJA|scheduler.py:146,195-197|plazo de 75 min y reinicio diario de reintentos no fijados (D2 y T6 sobreviven)
NARANJA|main.py:67-72|override capture_signals redundante y sin prueba; docstring y process.md atribuyen mal el código 0
INFORME: revisiones/U11-T02/ronda-1.md
```
