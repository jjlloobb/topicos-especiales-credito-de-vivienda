# Ronda 3 — U02-T16

VEREDICTO: VERDE

F-04 y F-05 están cerrados. Las mutaciones de las rondas 1 y 2 dan los mismos resultados que antes, así que no hay regresiones. Corrí CA-1 a CA-5 y todos pasan. No queda ningún ROJO ni NARANJA.

Comprobaciones previas:
- **Hash de la tarea:** `git hash-object` da ffc1f3bbc7dd918551ac62bdd0250484506d9f54, el esperado.
- **Alcance:** el retrabajo daa2d61..32a7244 toca solo `identity-edge/tests/unit/test_e2e_inventory.py` (+10 líneas, un caso nuevo) y `bitacoras/U02-T16.md` (+33). El plan, `INVENTORY` y las pruebas e2e no cambian. No hay desborde.
- **Mutaciones:** en una copia sacada con `git archive 32a7244` a `U02-T16-r3/rev/`, corridas con el `.venv` del worktree. El worktree no se tocó.
- **Estado al terminar:** worktree limpio (`git status --short` vacío) y HEAD en 32a7244b56e0683ec65e90064d5ae7532ab75790.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Pasa con el plan de main (Paso 13 en `[x]`) | `pytest identity-edge/tests/unit/test_e2e_inventory.py -q -rs` | pasa: `26 passed in 1.76s`, ninguna omitida |
| 2 | Localización independiente del checkbox; mismo bloque | `... -q -k "checkbox or state"` | pasa: `18 passed, 8 deselected in 0.05s`. Los 0,05 s se explican porque solo lee un archivo local. El rojo contra 08e29d2 se reproduce (ver F-04) |
| 3 | Borrar una viñeta del Paso 13 que está en INVENTORY hace fallar la prueba | en la copia, sobre el plan: `sed -i '/429 con \`Retry-After\`/d'` y aparte `sed -i '/refresh reusado → sesión revocada/d'` | pasa: `3 failed, 23 passed` y `4 failed, 22 passed`. Sin mutación, `26 passed` |
| 4 | U2 en verde | `uv sync --frozen && make -C identity-edge check` (de 10:02:47 a 10:14:05) | pasa: `2537 passed in 647.81s`, `ca4 exit 0`. Los únicos «Skipped» del log son `Skipped: 0` de kubeconform |
| 5 | U1 sigue cumpliendo, en serie después de CA-4 | `make -C platform check-local` (de 10:14:05 a 10:16:01, en el mismo shell al terminar CA-4) | pasa: `ca5 exit 0`, `0 chart(s) failed`, `247 archivos Markdown sin enlaces rotos` |

## Cierre de F-04 y F-05
| Mutación | Corrida | Resultado | Lectura |
|---|---|---|---|
| Localizador de 08e29d2 (`STEP`/`NEXT_STEP` como cadenas y `text[text.index(STEP):text.index(NEXT_STEP)]`) con las pruebas de 30e30f3 | `-k "checkbox or state"` | `18 failed, 7 deselected in 0.24s`; entre los fallos está `[[X]- (U02-T14)-[ ]]` | **F-04 cerrado**: coincide con el conteo de la bitácora (`18 failed, 7 deselected`) y con los ids que cita |
| El mismo localizador con las pruebas de 32a7244 | `-k "checkbox or state"` | `18 failed, 8 deselected in 0.17s` | sigue en rojo con el código actual. El octavo deseleccionado es el caso nuevo de F-05 |
| El mismo localizador con las pruebas de 32a7244, suite completa | suite completa | `25 failed, 1 passed` | |
| Sin `^` solo en STEP (el diff de mi copia muestra solo la línea 21) | suite completa | `1 failed, 25 passed`; el que falla es `test_an_indented_mention_of_step_13_before_step_13_does_not_start_the_block` | **F-05 cerrado**: coincide con la bitácora |

## Regresiones: las mutaciones de las rondas 1 y 2, repetidas sobre 32a7244
| Mutación | Suite completa | `-k "checkbox or state"` | Comparado con la ronda 2 |
|---|---|---|---|
| Sin `^` en NEXT_STEP | `1 failed, 25 passed` | `18 passed` | igual (F-02) |
| Solo `[ ]` en STEP y en NEXT_STEP | `25 failed, 1 passed` | `18 failed` | igual |
| Solo `[ x]` (sin `X`) en los dos | `10 failed, 16 passed` | `10 failed, 8 passed` | igual (F-03) |
| Solo `[ x]` (sin `X`) solo en NEXT_STEP | `6 failed, 20 passed` | `6 failed, 12 passed` | igual |
| Paso 14 cerrado en el plan como `- [x] **Paso 14 — …** (U02-T15)` | `26 passed` | — | compatible con U02-T15 |

## Hallazgos
No queda ningún hallazgo en pie. Dos observaciones que no bloquean y no son hallazgos sobre el diff:
- **Pruebas usadas para el rojo de F-04.** La bitácora corrió el rojo con las pruebas de 30e30f3, que eran las actuales cuando se registró. El caso de CA-2 no cambió en 32a7244. Yo también lo reproduje con las de 32a7244 (`18 failed, 8 deselected`).
- **Mi subdirectorio del scratchpad ya estaba ocupado.** El codificador dejó `ca4.log`, `ca5.log`, `good.py` y `old/` en `scratchpad/U02-T16-r3/`, el directorio que se me asignó. Para no pisarlo, usé `U02-T16-r3/rev/`. Revisé el contenido de `old/`: ahora tiene el localizador bueno, así que ya no permite comprobar su rojo de F-04. Por eso lo reproduje por mi cuenta desde git.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Las ya registradas siguen igual: el CI no corre identity-edge, y el chart keycloakx está en CANDIDATAS.md:88.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r3/rev/ca4.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r3/rev/ca5.log
- Script de mutaciones: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r3/rev/scripts/mut.py
- Copia de las mutaciones: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r3/rev/vectra-risk

```
VEREDICTO: VERDE
-|-|Sin hallazgos ROJO ni NARANJA en pie
INFORME: revisiones/U02-T16/ronda-3.md
```
