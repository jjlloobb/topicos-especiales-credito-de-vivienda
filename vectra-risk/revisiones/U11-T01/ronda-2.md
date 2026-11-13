# Ronda 2 — U11-T01

VEREDICTO: NO-VERDE

F-01, el ROJO que decidía la ronda, queda cerrado. El oráculo nuevo cuenta por definición y atrapa las 8 mutaciones de la tasa de consulta que le lancé. Los 8 criterios pasan en mi corrida. El NO-VERDE se debe a un solo NARANJA: un resto de F-03 que el arbitraje pedía y no se hizo (F-07). Según RL-1..RL-5, un NARANJA no bloquea.

**Comprobaciones previas**
- El blob de la tarea es `79d69e1…` y coincide. HEAD es `82b4240`.
- El diff de la ronda 2 (`5d7cd20..HEAD`) solo toca `product-metrics/` (8 archivos), `CANDIDATAS.md`, `bitacoras/U11-T01.md` y `revisiones/U11-T01/ronda-2-respuesta.md`. No hay nada fuera de alcance. U0, U1 y U3 están intactos: `git diff 81a8fd0 HEAD -- contracts platform` da 0 líneas.
- Al terminar, `git status --short` sale **vacío**: el worktree quedó limpio.
- Hice todas las mutaciones sobre copias en `…/scratchpad/u11/rev2/m-*`. Para confirmar que se cargaba la copia, metí un `SystemExit(3)` en una de ellas y salió rc=3.
- Ninguna prueba sale como omitida y no hay `skip` ni `xfail` en `tests/`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | import-linter | `uv sync --frozen && uv run lint-imports --config product-metrics/.importlinter` | pasa: 3 contratos KEPT, 0 rotos |
| 2 | Estructura §1 | el bucle `test -e` de CA-2 | pasa: `OK`, ninguna línea `FALTA` |
| 3 | config y params | `uv run pytest …/test_config.py …/test_params.py -v` | pasa: 38 en 1,54 s (load 13,2) |
| 4 | compute, noise y ejemplos | `HYPOTHESIS_PROFILE=ci uv run pytest …test_compute.py …test_noise.py …test_compute_examples.py -v` | pasa: 30 en 260 s, perfil `ci`, semilla 499801853, con la PBT nueva. Load 9,7 → 14,0 |
| 5 | state y reader | `HYPOTHESIS_PROFILE=ci uv run pytest …test_state_machine.py …test_reader.py -v` | pasa: 32 en 69 s, semilla 1156966199. Load 14,6 |
| 6 | Cobertura 100 % y `logic.md` | el comando de CA-6, tal cual | pasa: compute y noise al 100 %, `TOTAL 214 0 66 0 100%`, 121 en 45 s. El comando no fija perfil, así que corre en `dev`, y eso explica los 45 s. El grep encuentra `compute`, `days_below_floor` y `mutmut`. Load 14,6 → 12,5 |
| 7 | `make check` | `make -C product-metrics check` | pasa (rc 0): 152 en 337 s (semilla 608049846) y la cobertura, 121 en 683 s (semilla 546149469). 17 m 05 s de reloj. Load 12,45 al empezar y 13,64 al terminar |
| 7b | `make -C platform check` | **no lo corrí** | El diff de la ronda 2 no toca `platform/`, `pyproject.toml`, `uv.lock` ni gitops. `platform check` corre `test_traceability.py` sin `--all` (solo U1). La corrida del codificador está en `…/u11/r2/check-pl.log` |
| 8 | Plan | los dos grep de CA-8 | pasa: solo los Pasos 1 a 5 cambian a `[x] (U11-T01)` y el 5 lleva la nota de `mutmut` |

## Hallazgos de la ronda 1, comprobados por mí

### F-01 · ROJO → **cerrado**
- **El oráculo cuenta por definición; no copia `compute`.** `test_pbt_u11_01_explanation_view_rate_matches_the_oracle` trabaja sobre las `Spec`:
  - toma las válidas y atribuibles con `decided_at` UTC en [ayer−6, ayer], por canal y en total;
  - cuenta en el numerador la vista previa aunque los factores sean `["ninguno"]`;
  - para cada día de hoy−29 a ayer, arma la ventana de 7 días con `last − 6 días`.
- **No reutiliza nada de `compute` ni de `model`.** No usa `by_day`, ni `VIEW`/`DEN`, ni `config.VIEW_WINDOW_DAYS`: el 7 y el 29 están escritos por definición. Si la constante cambiara, la prueba fallaría, y así debe ser.
- **Mutaciones.** Todas corrieron sobre la PBT sola, perfil `ci`, y **todas quedan en rojo**:
  - v1, ventana diaria de 8 días (la tuya de la ronda 1): falla en 176 s, `(0, 1) == (0, 0)`.
  - v2, semana publicada de 8 días (la tuya de la ronda 1): falla en 315 s, `{'web': [0, 1]} == {}`.
  - v3, día tomado de `recorded_at` en lugar de `decided_at` (en `model._decision`): falla en 328 s; fallan la aserción diaria y la semanal.
  - v4, corte por `outcome` en lugar de `channel`: falla en 52 s, `{'0': …} == {'web': …}`.
  - v5, la vista con `["ninguno"]` no cuenta: falla en 319 s.
  - v6, las ventanas diarias empiezan un día tarde: falla en 28 s.
  - v7, semana corrida un día (incluye hoy): falla en 411 s.
  - v8, no atribuibles plegadas en la tasa: falla en 33 s.
  - Línea base sin mutación: 1 passed en 27 s.

### F-02 · NARANJA → **cerrado**
- Corrí `test_traceability.py --all` en la rama y en `git archive 81a8fd0`. Los dos salen con rc=1 por fallos de otras unidades.
- Lo que solo falla en la rama son 21 identificadores, todos de U11:
  - INF-U11-01..05;
  - NFR-U11-02, 03, 05..08, 13, 14, 22, 32, 33, 41 y 42;
  - P-U11-03, 05 y 06.
- NFR-U11-10 y NFR-U11-21 ya no salen.
- **Cruce con los pasos de la tarea** (NFR-U11-01, 02, 04, 09..12, 21, 30 y 31; P-U11-01, 02 y 04): solo queda NFR-U11-02, que el arbitraje excluye. Ningún otro pertenece a un paso de esta tarea.

### F-03 · NARANJA → **cerrado en parte** (ver F-07)
F, S, N y los targets 0..1 son ahora constantes con nombre en `config.py`, y `parse` y sus mensajes las usan.

### F-04 · AMARILLO → **cerrado**
- **Tu mutación.** `try/except ReadError: pass` en `full_pass` queda en rojo con PBT-U11-02 en 9 s: `('full', 1, True, None)`.
- **Mutaciones que añadí, todas en rojo:**
  - publicar la pasada parcial y volver a lanzar el error: 105 s; el estado no queda intacto;
  - la incremental se traga el fallo: 38 s;
  - quitar la excepción del codificador, de modo que el fallo de la incremental posterior se propaga: 18 s, `('full', 2, True, ReadError)`. Esto demuestra que esa rama se ejerce.
- **La excepción es correcta y no abre hueco:**
  - Distingue las solicitudes por `recorded_from`. El `reader` lo manda en **todas** las páginas de la pasada (`reader.py:169`) y en ninguna de la incremental.
  - Cuando la incremental posterior falla, la pasada ya publicó un estado completo. `_Data.apply` solo avanza `last_seq` por página confirmada, y el `invariant` compara `compute` sobre el estado con el oráculo de `seq <= last_seq`.
  - Concuerda con NFR-U11-09: un ciclo fallido se recupera en el siguiente, y los reintentos cada 15 min son solo para la pasada **fallida**.

### F-05 · AMARILLO → **cerrado**
El comentario explica el 2. Lo comprobé a mano: la ventana del 3 de octubre suma 110 decisiones con 70 vistas (≥ 0,6), y las del 4 y el 5 suman 160 con 80 (< 0,6).

### F-06 · AMARILLO → **cerrado**
- **El contrato de U0.** En `contracts/python/…/models/registry.py:360`:
  - `channel: Annotated[str, Field(max_length=40)]`, sin mínimo;
  - `model_version_id: str`, sin tope.
  - El OpenAPI (`decision-registry-service.yaml:1518-1529`) dice lo mismo: solo `maxLength: 40` en `channel`.
- **El código.** Aceptar `""` y quitar el tope es lo que dice el contrato. `EntryType.HUMAN_DECISION` reemplaza al literal.
- **La prueba.** La nueva lee de vuelta el valor parseado. El defecto `catalog` del generador pasó a 41 caracteres, en línea con el contrato.

## Hallazgos nuevos
### F-07 · NARANJA · `product-metrics/src/vectra_product/params.py:69-71` · El rango de `target_origination_hours` sigue como literal
- **Qué hay.** `if hours <= 0: raise ParamsError("target_origination_hours: no es mayor que 0")`. Es un target de BR-U11-09 con su cota en el punto de decisión y en el mensaje.
- **Por qué no está cerrado.** El arbitraje pedía «los rangos de F, S, N **y de los targets**». El comentario nuevo de `config.py:56-57` enumera los rangos y omite este. La regla de conftest del Paso 11 tendrá que repetir `> 0` sin una constante común.
- **Responsabilidad compartida.** Es un resto de la misma clase que F-03, y yo no lo barrí en la ronda 1: allí escribí «0..1» para los targets. Por eso no es culpa solo del codificador.

## Tareas candidatas (defectos reales fuera de alcance)
- No hay nuevas. Las cinco que añadió el codificador a `CANDIDATAS.md` están bien acotadas (U1 traceability, redacción del ejemplo de ruido, U0 `LogEvent`, `platform/.tools` y U3 `next_seq_after`).

## Rutas de transcripciones largas
Todas están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/u11/rev2/`:
- Criterios: `ca1.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca7-pm.log` y `ca8.log`.
- Mutaciones: `batch-f01.log` y `batch-f04.log` (con un `m-<nombre>/out.log` por cada una), y los scripts `batch-f01.sh`, `batch-f04.sh` y `run.sh`.
- Trazabilidad: `trace-rama.log` y `trace-base.log`.

```
VEREDICTO: NO-VERDE
NARANJA|product-metrics/src/vectra_product/params.py:69-71|rango de target_origination_hours (> 0) sigue como literal en el punto de decisión y el mensaje (resto de F-03)
INFORME: revisiones/U11-T01/ronda-2.md
```
