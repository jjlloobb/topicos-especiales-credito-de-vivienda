# Ronda 2 — U03-T06

VEREDICTO: NO-VERDE

Hay un solo NARANJA y ningún ROJO. La línea 7 de `cierre-demo.md`, que es justo la frase con la que se resuelve F-07, dice que «el diff posterior al `fe0c9f3` es solo documentación de `vectra-risk/`». Eso es falso: lo que trajo el merge de `5cf2ebb` incluye código de otras unidades, y al menos un resultado de «Comprobado» ya no coincide en HEAD. F-02, F-03, F-04, F-05, F-06 y F-08 quedaron bien resueltos. CA-1, CA-3 y CA-5 pasan con mis propias corridas. Según RL-1 y RL-4 solo bloquea un ROJO, así que fusionar o no lo decides tú. No suavizo el veredicto por ser la última ronda.

Worktree `.claude/worktrees/u03-t06`, HEAD `e78703b`. Diff de la ronda: `3f367eb..e78703b`. `origin/main` = `5cf2ebb`, que es ancestro de HEAD. El blob de la tarea es `70e003a56607772030d542b413a3291eea95773a` y coincide. Al terminar, `git status --short` sale vacío. No corrí ningún `make check`, como pide el arbitraje.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Paso 19 N/A | `test ! -d decision-registry/frontend` | pasa, rc 0 |
| 3 | Trazabilidad | `test_traceability.py --unit decision-registry --all`, y también `--section logic` y `--section api` | pasa: «41 identificadores con trazabilidad», rc 0 en los tres. Tarda 1,30 s porque es un escaneo estático sin estado externo, así que no se saltó nada |
| 3 | Las 5 secciones | el `grep -nE "^## (...)"` de CA-3 | pasa: líneas 5, 33, 65, 77 y 88 |
| 3 | Sin filas quitadas | `git diff origin/main -- …/cierre-demo.md \| grep -E "^-\|"` | pasa: «sin filas quitadas» |
| 5 | Estado del plan | `git diff origin/main -- …plan.md \| grep -E "^[-+]- \[.\]"`, más `--stat` | pasa: solo cambian los Pasos 18 (sigue `[ ]` con la nota), 19 (`[x] (U03-T06)`) y 20 (`[x] (U03-T06, acotado a la demo)`), con 3 inserciones y 3 borrados |
| 2, 4 | `make check` | no se corrieron | eximidos por el arbitraje de la ronda 1 |

## Comprobaciones del encargo
- **Alcance del diff de la ronda:** toca solo `cierre-demo.md` (+13/−14) y `bitacoras/U03-T06.md` (+48). Las tablas tienen 50 filas `|` en `3f367eb` y 50 en `e78703b`. Las 3 líneas `-|` del diff de la ronda son las filas del Paso 1, del Paso 15 y de los escenarios, reescritas en el mismo sitio con su `+|` correspondiente.
- **Las líneas de `CANDIDATAS.md` citadas existen en HEAD y dicen lo que afirma el cierre** (lo comprobé con `sed -n Np`):
  - :192 `checkpoint`/`recorded_at`
  - :199 `fail_closed` 403/422
  - :200 `inconsistente` de `incremental`/`nightly`
  - :201 `pools.py`
  - :254 la candidata prioritaria `test_f04`/`daily:query`
  - :305 límites de 2 s
  - :507 identity-edge, tachada y marcada «Resuelta (U02-T20)»
- **La entrada nueva de `CANDIDATAS.md`** (contenedores huérfanos de Testcontainers) está en `5cf2ebb..HEAD`, línea 511. Entró en `3f367eb`, no en esta ronda.
- **F-06:** `eaa81a8` es U02-T20 y es ancestro de `5cf2ebb`. La nota de la bitácora dice que las líneas 70 a 80 son históricas, y ese rango corresponde al bloque CA-4 y al fallo de identity-edge. Resuelto.
- **F-08:** `tareas/U03-T07-tope-de-daily-query.md` está en `5cf2ebb`, y su línea 5 dice «Decisión del usuario: 2026-11-10». Resuelto.
- **F-03, F-04 y F-05:** resueltos. No hay líneas en blanco dobles.

## Hallazgos
### F-09 · NARANJA · `cierre-demo.md:7` · la frase «El diff posterior al `fe0c9f3` es solo documentación» es falsa
`git diff --stat fe0c9f3 HEAD` da 201 archivos y 15 488 inserciones. Entre `fe0c9f3` y `5cf2ebb` hay código de otras unidades:
- `contracts/src/vectra_contracts/outcome/__init__.py`;
- `platform/tests/test_kind_profile.py` y `test_platform.py`;
- `vectra-risk-gitops/apps/{kind,staging,prod}/bias-monitoring.yaml`;
- bias-monitoring, case-management, scoring-explainability, governance e identity-edge.

Lo único cierto de la frase es «sin cambios en `decision-registry/`», que comprobé: `git diff --stat fe0c9f3 5cf2ebb -- vectra-risk/decision-registry/` sale vacío.

La frase no es inocua, porque es lo que justifica que «Comprobado» siga valiendo. Corrí `uv run python platform/tests/test_waves.py` en HEAD y salió **kind 52, staging 51, prod 49**. La fila del Paso 15 (línea 24) dice 51, 50 y 48. Lo mismo puede pasar con los Pasos 9 y 13 (`make -C contracts check`) y con «`platform check`… 802 pruebas» (líneas 24 y 27), porque sus entradas cambiaron. Los resultados en sí están bien fechados en `fe0c9f3`. Lo que está mal es la afirmación de contexto.

Arreglo de una línea: decir que el diff **propio de la rama** frente a `5cf2ebb` es solo documentación, y que el merge trajo código de otras unidades que puede cambiar las cifras de los Pasos 9, 13, 15 y 20.

Transcripción: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-r2/waves.log`

### F-10 · AMARILLO · `cierre-demo.md:9` · el encabezado «Resultado ahora» choca con «no se volvió a correr»
Es de la misma clase que F-09. La columna se lee como si fuera el estado de HEAD, pero es el de `fe0c9f3`. Bastaría con cambiarlo a «Resultado en `fe0c9f3`».

### F-11 · AMARILLO · `cierre-demo.md:7` · «incluye U02-T20 y la tarea U03-T07» es ambiguo
`5cf2ebb` trae solo el **archivo** de la tarea U03-T07, no su arreglo, y `decision-registry/` no cambia entre `fe0c9f3` y `5cf2ebb`. Se puede leer como si el tope de `daily:query` ya estuviera en `main`. Sugiero escribir «el archivo de la tarea U03-T07 (sin implementar)».

### F-12 · AMARILLO · `bitacoras/U03-T06.md`, Ronda 2 · ruta relativa de la evidencia
«Salida completa en `scratchpad/cod-u03-t06-r2/r2.log`» no es una ruta absoluta, así que no se puede encontrar.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-r2/ca.log` (CA-1, CA-3 y CA-5)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-r2/waves.log` (Applications en HEAD: 52, 51 y 49)

```
VEREDICTO: NO-VERDE
NARANJA|cierre-demo.md:7|Afirma que el diff posterior a fe0c9f3 es solo documentación; el merge trajo código de otras unidades y test_waves ya da 52/51/49, no 51/50/48
AMARILLO|cierre-demo.md:9|Encabezado «Resultado ahora» frente a resultados de fe0c9f3 sin volver a correr
AMARILLO|cierre-demo.md:7|«incluye … la tarea U03-T07» sugiere que el arreglo ya está en main; solo está el archivo de la tarea
AMARILLO|bitacoras/U03-T06.md (Ronda 2)|Ruta relativa a scratchpad/cod-u03-t06-r2/r2.log
INFORME: revisiones/U03-T06/ronda-2.md
```
