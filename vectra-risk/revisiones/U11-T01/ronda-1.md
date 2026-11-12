# Ronda 1 — U11-T01

VEREDICTO: NO-VERDE

Comprobaciones previas: el blob de la tarea es `79d69e1…` (coincide), HEAD es `9195580`, la base es `81a8fd0` y el diff tiene 41 archivos. Al terminar, `git status --short` está **vacío**: el worktree quedó limpio. Hice todas las mutaciones sobre copias en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/u11/mut/`, con `PYTHONPATH` apuntando a la copia. Antes verifiqué que la copia es la que se carga: una mutación de prueba con `SystemExit` salió con rc=3.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | import-linter | `uv sync --frozen && uv run lint-imports --config product-metrics/.importlinter` | pasa: 3 contratos KEPT, 0 rotos |
| 2 | Estructura §1 | el bucle `test -e` de CA-2 | pasa: `OK`, ninguna línea `FALTA` |
| 3 | config y params | `uv run pytest …/test_config.py …/test_params.py -v` | pasa: 38 en 0,97 s (load 3,84) |
| 4 | compute y noise | `HYPOTHESIS_PROFILE=ci uv run pytest …test_compute.py …test_noise.py …test_compute_examples.py -v` | el comando pasa: 29 en 71 s, semilla 3540713197, load 3,8→3,3. **El fondo falla: ver F-01** |
| 5 | state y reader | `HYPOTHESIS_PROFILE=ci uv run pytest …test_state_machine.py …test_reader.py -v` | pasa: 32 en 30 s, semilla 1315498963, load 3,7→4,7 |
| 6 | Cobertura 100 % y `logic.md` | el comando de CA-6 | pasa: compute y noise al 100 %, `TOTAL 214/66 100%`, 118 en 9,96 s; el grep encuentra `compute`, `days_below_floor` y `mutmut` |
| 7 | `make check` | `make -C product-metrics check` y luego `make -C platform check`, en serie | pasa: PM=0 en 340,55 s (semillas 639022195 y 2476847246) y PL=0 en 413,51 s (`pass: 372, fail: 0`). Load 4,38 al empezar, 4,80 entre uno y otro y 5,80 al final |
| 8 | Plan | los dos grep de CA-8, contra la base y contra `origin/main` | pasa: solo los Pasos 1 a 5 cambian a `[x] (U11-T01)` y el 5 lleva la nota de `mutmut` |

Ninguna prueba sale como omitida. Los tiempos cuadran con el perfil `ci`: no son corridas de 0,0 s.

**Estructura de §1.** Está completa: `tools/` sin `gen_rules.py`, `chart/templates/` vacío, `policies/conftest/` y `observability/{rules/tests,runbooks,dashboards}/`. Los directorios vacíos llevan `.gitkeep`, y no hay `__init__.py` en `tests/`. `scheduler`, `collector` y `main` tienen solo el docstring.

**Lo marcado «Fuera».** No aparece nada en el diff: ni `mutmut` (solo se menciona en comentarios y documentación), ni `Chart.yaml`, `Dockerfile`, `product.json`, workflow, `migrations/` o `frontend/`, ni cambios a U0, U1 o U3.

**`pyproject.toml` raíz y `uv.lock`.** Solo hay el alta de `product-metrics`: el miembro, la fuente, `vectra-product` editable en `dev` y el paquete en el lock. A eso se suman dos cosas que lo acompañan:
- una línea de `per-file-ignores` para `product-metrics/tests/**`, igual que en las demás unidades;
- la dependencia `pyyaml==6.0.3` del miembro, que ya estaba en el lock con esa versión.

No veo nada más.

## Hallazgos

### F-01 · ROJO · CA-4 / PBT-U11-01 (`tests/property/test_compute.py`) · Ninguna prueba compara la tasa de consulta (BR-U11-07) con un oráculo
- **Qué dice la definición.** business-logic-model §3, PBT-U11-01: «los conteos coinciden con un oráculo que cuenta por definición (BR-U11-03, 04, **07**)». CA-4 lo repite.
- **Qué hace la prueba.** El oráculo de `test_pbt_u11_01_*` cubre la North Star, el desglose, la sostenida y las no atribuibles. Nunca compara con un oráculo `explanation_view` ni `explanation_view_daily`.
- **Qué cubren las demás.** PBT-U11-04 recibe las ventanas ya armadas. PBT-U11-07 solo comprueba que `explanation_view` cuadra consigo misma. Los ejemplos solo miran `.decisions` de tres ventanas con todas las decisiones en un solo día.
- **Mutaciones que lo demuestran.** Las dos sobreviven a la suite entera (`tests/unit`, `property` e `integration`, perfil `ci`):
  - `compute.py`: la ventana diaria pasa a 8 días (`range(end - span, end + 1)`). Resultado: **149 passed en 446 s**.
  - `compute.py`: la semana publicada pasa a 8 días (`over(yesterday - span, yesterday)`). Resultado: **149 passed en 407 s**.
- **Por qué importa.** Es una de las cifras de la demo D4 (la tasa de consulta) y la entrada de `days_below_floor`.
- **Qué falta.** Un oráculo por definición de la tasa de 7 días por `decided_at`, total y por canal, y de las ventanas diarias.

### F-02 · NARANJA · `test_traceability.py --all` (DECISIONES-LOOP §6, enmienda) · Fallan identificadores nuevos de pasos que la tarea cubre
- **Cómo lo corrí.** En la rama y en `git archive 81a8fd0`. Los dos salen con rc=1.
- **Fallos nuevos de U11.** INF-U11-01..05, NFR-U11-02, 03, 05..08, 10, 13, 14, 21, 22, 32, 33, 41 y 42, y P-U11-03, 05 y 06.
- **Cruce con los pasos de la tarea.** Tres pertenecen a pasos que esta tarea cubre:
  - **NFR-U11-21**: Paso 1, «Diseño: NFR-U11-21». Solo se cita en `.importlinter`, un archivo que la herramienta no lee (sin sufijo y fuera de `NAMES`).
  - **NFR-U11-10**: Paso 4, «NFR-U11-01, 02, 09..12». Los 6 meses están implementados, pero no se citan.
  - **NFR-U11-02**: Paso 4. Su evidencia de volumen es del Paso 7.
- **Precedente.** El mismo caso salió NARANJA en U04-T05 (F-05).
- **Aparte, no atribuible al diff.** En la extracción de la base fallan NFR-U0-04, 17 y 43 y NFR-U1-40, y en la rama no. Probablemente la causa son archivos ignorados que solo están en el worktree. Las salidas están en `…/scratchpad/u11/trace-base.log` y `…/trace-rama.log`.

### F-03 · NARANJA · `product-metrics/src/vectra_product/params.py:50-62` · Los rangos de BR-U11-09 están escritos como literales en los puntos de decisión
- **Qué hay.** `0 < floor < 1`, `1 <= sustain <= 14`, `minimum < 30` y `0..1` están incrustados en `parse`, y también en los mensajes que ve el operador. Mientras tanto, el resto de las constantes viven con nombre en `config.py`.
- **Por qué importa.** El Paso 11 anuncia una regla de conftest «con los mismos rangos», así que habrá dos fuentes de verdad sin un nombre común.

### F-04 · AMARILLO · `tests/property/test_state_machine.py` (`read_with_a_failure_on_page`) · La rama `else` acepta en silencio una pasada que debió fallar
- **La mutación.** En `state.full_pass` le puse `try/except ReadError: pass` alrededor del `async for`, de modo que publica la pasada parcial.
- **Resultado.** **Sobrevive a PBT-U11-02** (1 passed en 86 s). La atrapa la prueba de integración `test_a_failed_full_pass_leaves_the_current_state_intact`.

### F-05 · AMARILLO · `tests/unit/test_compute_examples.py:88-94` · El comentario de `test_a_healthy_day_stops_the_count` queda colgando
El comentario termina en «… ver abajo» y no explica el número 2 que se espera.

### F-06 · AMARILLO · `product-metrics/src/vectra_product/model.py` · Validación más estricta que el contrato y literales sueltos
- `_text` exige un `channel` de al menos 1 carácter. `MetricsRecommendationRef` admite `""`, así que se excluiría una entrada válida de U3.
- `model_version_id` tiene un tope de `1 << 16` que no está en el contrato.
- `"human_decision"` está escrito como literal en lugar de `EntryType`.

## Mutaciones propias (todas sobre copias; resultado completo en el log)
- **Detectadas por la PBT que corresponde:**
  - PBT-01: sostenida, vista con `["ninguno"]` en el numerador, `30d` desplazado un día, no atribuible dentro del cociente.
  - PBT-03: sin deduplicar por `seq`, día tomado de `recorded_at`.
  - PBT-04: con menos de N reinicia la cuenta, `<=` N, tasa igual a F cuenta, piso como `float`.
  - PBT-06: `manual` entra, `revision_requerida` entra, cuantil desplazado, `<=` en el target.
  - PBT-07: `by_model` agrupado por el corte equivocado, promedio de razones, total de la vista.
- **`reader` y PBT-02:**
  - Dos páginas en vuelo (prefetch): el doble lanza `SimultaneousConnections` tanto en la integración como en PBT-02.
  - Saltar una página fallida: lo atrapan la prueba de la página 3 y PBT-02.
  - Breaker con 4 fallos, `close_after=2` u `open_for×2`: lo atrapa la prueba del breaker.
  - El mes de una entrada de 40 días no se pliega: lo atrapan la prueba de 40 días y PBT-02.
  - La incremental no pliega meses: lo atrapa PBT-02.
- **Sobrevivientes no preocupantes:**
  - `degraded >=`: una PBT de 60 entradas como máximo no puede llegar al 1 % exacto; lo atrapa el ejemplo del 1 %.
  - `month_to_date` hasta hoy: es equivalente, porque `by_day` ya excluye el día de hoy.
  - Doble pliegue: es equivalente, porque `_envelope` rechaza `seq <= cursor`.
  - Quitar el candado a la incremental: lo frena la guarda `pages()` con `RuntimeError`, no la prueba de la carrera. La concurrencia la cubre el prefetch.

## Tareas candidatas (defectos reales fuera de alcance)
- `test_traceability.py` no lee archivos sin sufijo como `.importlinter`: un identificador citado solo ahí cuenta como «sin trazabilidad».
- El ejemplo de ruido «los mismos 3 días con 40 decisiones» es ambiguo con la ventana móvil de 7 días. Ya lo anotó el codificador; confirmo la lectura doble en las pruebas.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/u11/ca1.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca7-pm.log`, `ca7-pl.log` y `ca7-resumen.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/u11/mutaciones.log` (y cada `mut/m-<nombre>/out.log`)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/u11/trace-rama.log` y `trace-base.log`

```
VEREDICTO: NO-VERDE
ROJO|CA-4 / tests/property/test_compute.py (PBT-U11-01)|sin oráculo de la tasa de consulta (BR-U11-07); ventana de 8 días sobrevive a toda la suite
NARANJA|test_traceability.py --all (§6)|NFR-U11-10, 21 (y 02) de pasos cubiertos quedan sin trazar
NARANJA|product-metrics/src/vectra_product/params.py:50-62|rangos de BR-U11-09 como literales en el punto de decisión
AMARILLO|tests/property/test_state_machine.py|la rama else de la pasada con fallo no exige que falle; pasada parcial publicada sobrevive a PBT-02
AMARILLO|tests/unit/test_compute_examples.py:88-94|comentario colgante en test_a_healthy_day_stops_the_count
AMARILLO|product-metrics/src/vectra_product/model.py|channel vacío rechazado contra el contrato; 1<<16 y "human_decision" como literales
INFORME: revisiones/U11-T01/ronda-1.md
```
