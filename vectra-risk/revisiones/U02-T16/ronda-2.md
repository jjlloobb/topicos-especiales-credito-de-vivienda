# Ronda 2 — U02-T16

VEREDICTO: NO-VERDE

El código cierra F-01, F-02 y F-03, y los cinco criterios pasan cuando los corro yo. Queda un ROJO de evidencia: CA-2 pide que la bitácora muestre en rojo el caso nuevo contra 08e29d2, y esa corrida no está. Para cerrarlo basta con registrarla. Yo ya la reproduje: `18 failed`.

Comprobaciones previas:
- **Hash de la tarea:** `git hash-object` da ffc1f3bbc7dd918551ac62bdd0250484506d9f54, el esperado.
- **Alcance:** el retrabajo f49cdbb..30e30f3 toca solo `identity-edge/tests/unit/test_e2e_inventory.py` y `bitacoras/U02-T16.md`. El plan no cambió. No hay desborde.
- **Estado al terminar:** el worktree queda limpio (`git status --short` vacío) y en 30e30f3.
- **Mutaciones:** las hice en una copia sacada con `git archive 30e30f3` al scratchpad, y las corrí con el `.venv` del worktree.
- **Contención:** CA-4 tardó 829 s, contra 719 s en la ronda 1. La carga subió de 1,90 a 2,97 mientras corría el check de U02-T15. Todo pasó igual, sin fallos de tiempo.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Pasa con el plan de main (Paso 13 en `[x]`) | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa: `25 passed in 2.41s`, ninguna omitida (`-rs` sin líneas de skip) |
| 2 | Localización sobre el plan real en todos los estados; mismo bloque | `... -q -k "checkbox or state"` | el comando pasa: `18 passed, 7 deselected in 0.06s`. Los 0,06 s se explican porque solo lee un archivo local. La parte de la bitácora no se cumple (F-04) |
| 3 | Borrar una viñeta del Paso 13 que está en INVENTORY hace fallar la prueba | en la copia: `sed -i '/429 con \`Retry-After\`/d'` y aparte `sed -i '/refresh reusado → sesión revocada/d'` | pasa: `3 failed, 22 passed` y `4 failed, 21 passed`; sin mutación, `25 passed` |
| 4 | U2 en verde | `uv sync --frozen && make -C identity-edge check` | pasa: `2536 passed in 829.07s`, `ca4 exit 0`. Los únicos «Skipped» del log son `Skipped: 0` de kubeconform |
| 5 | U1 sigue cumpliendo, en serie después de CA-4 | `make -C platform check-local` (empezó 09:43:12, cuando CA-4 terminó) | pasa: `ca5 exit 0`, `0 chart(s) failed`, `245 archivos Markdown sin enlaces rotos` |

## Cierre de F-01 a F-03, con mis mutaciones en la copia
| Mutación | Corrida | Resultado | Lectura |
|---|---|---|---|
| Localizador viejo de 08e29d2 (`text.index("- [ ] **Paso 13 …")` / `"- [ ] **Paso 14"`) con las pruebas nuevas | `-k "checkbox or state"` | `18 failed` | **F-01 cerrado**: el caso corre sobre `PLAN` reescrito y exige `plan_bullets(variante) == plan_bullets()` |
| Localizador viejo de 08e29d2, suite completa | suite completa | `24 failed, 1 passed` | |
| Sin `^` en NEXT_STEP | `-k indented` | `1 failed` | **F-02 cerrado** para NEXT_STEP |
| Sin `^` en NEXT_STEP, suite completa | suite completa | `1 failed, 24 passed` | |
| Solo `[ ]` en STEP y NEXT_STEP | `-k "checkbox or state"` | `18 failed` | detecta el defecto original |
| Solo `[ ]` en STEP y NEXT_STEP, suite completa | suite completa | `24 failed, 1 passed` | |
| Solo `[ x]` (sin `X`) en los dos | `-k "checkbox or state"` | `10 failed, 8 passed` | **F-03 cerrado** |
| Solo `[ x]` (sin `X`) solo en NEXT_STEP | `-k "checkbox or state"` | `6 failed, 12 passed` | |
| Paso 14 cerrado como `- [x] **Paso 14 — …** (U02-T15)` | suite completa | `25 passed` | compatible con U02-T15 |
| Sin `^` solo en STEP | suite completa | `25 passed` | ver F-05 |

## Hallazgos

### F-04 · ROJO · CA-2 / bitacoras/U02-T16.md (Ronda 2) · Falta en la bitácora el rojo del caso nuevo contra 08e29d2
CA-2 dice: «La bitácora muestra la corrida en rojo de ese caso contra la versión de 08e29d2». El arbitraje lo repite para F-01: «Rojo contra la versión de 08e29d2 en la bitácora».

En la Ronda 2, la bitácora solo muestra rojo contra el código de la ronda 1, que ya aceptaba `[ x]`: `10 failed, 9 passed`, y todos los fallos son por `[X]`. Esa corrida no demuestra que el caso detecte el defecto real, que es `[x]` contra un localizador que solo conoce `[ ]`.

El rojo contra 08e29d2 que hay en la bitácora es de la Ronda 1 (`6 failed, 2 passed, 6 deselected`, 8 combinaciones). Corresponde al caso sintético, que esta ronda borró. No pudo salir del diff actual, que tiene 18 combinaciones y 7 deseleccionadas.

Yo reproduje el rojo correcto: con el localizador de 08e29d2 y las pruebas de 30e30f3, `-k "checkbox or state"` da `18 failed, 7 deselected in 0.21s`. Así que el comportamiento está bien y lo que falta es la evidencia que exige el criterio. Para corregirlo, hay que registrar esa corrida con su comando y su salida.

### F-05 · AMARILLO · test_e2e_inventory.py:21 · El `^` de STEP sigue sin prueba
Quité solo el `^` de STEP y la suite siguió en `25 passed`. El caso de F-02 inserta una mención sangrada del Paso 14 y cubre solo NEXT_STEP. El comentario de la línea 20 dice que los dos patrones están anclados. Hoy no tiene efecto, porque el plan no tiene una mención sangrada del encabezado del Paso 13. Lo cubriría un caso análogo con `  - [ ] **Paso 13 — Especificación de las pruebas de extremo a extremo**` sangrado antes del Paso 13.

Una nota sobre mi método: en mi primera pasada, un reemplazo de texto quitó también el `^` de NEXT_STEP, porque `STEP = re.compile(r"^- \[` es subcadena de `NEXT_STEP = …`. Lo repetí con un `sed` limitado a la línea `^STEP`, y el resultado de 25 passed es el de esa corrida.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Las ya registradas siguen igual: el CI no corre identity-edge, y el chart keycloakx está en CANDIDATAS.md:88.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r2/ca4.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r2/ca5.log
- Copia de las mutaciones: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r2/mut/vectra-risk

```
VEREDICTO: NO-VERDE
ROJO|CA-2 (bitacoras/U02-T16.md, Ronda 2)|Falta en la bitácora el rojo del caso nuevo contra 08e29d2
INFORME: revisiones/U02-T16/ronda-2.md
```
