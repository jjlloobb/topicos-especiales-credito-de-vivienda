# Ronda 1 — U02-T16

VEREDICTO: NO-VERDE

Comprobaciones previas: `git hash-object` del archivo de la tarea da ffc1f3bbc7dd918551ac62bdd0250484506d9f54, que es el hash esperado. El diff 90f438c..6c2b2e8 toca solo `identity-edge/tests/unit/test_e2e_inventory.py` y `bitacoras/U02-T16.md`, así que no hay desborde de alcance. Al terminar, el worktree está limpio y en 6c2b2e8, según `git status --short`, que no muestra nada. Las mutaciones las hice en una exportación con `git archive` dentro del scratchpad, no en el worktree.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | La prueba pasa con el plan de main (Paso 13 en `[x]`) | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa: `14 passed in 1.89s` |
| 2 | Un caso localiza el bloque **sobre el texto del plan** en los estados `[ ]`/`[x]`, con y sin sufijo, y con el Paso 14 en los dos estados; el bloque es el mismo | `... -q -k "checkbox or state"` | el comando pasa (`8 passed, 6 deselected in 0.03s`), pero el caso no cumple lo que pide el criterio (ver F-01). El rojo contra el localizador viejo sí lo reproduje: `6 failed, 2 passed`, igual que la bitácora |
| 3 | Si se borra del plan una viñeta del Paso 13 que está en INVENTORY, la prueba falla | en la copia: `sed -i '/429 con \`Retry-After\`/d'` y aparte `sed -i '/refresh reusado → sesión revocada/d'` | pasa: `3 failed, 11 passed` y `4 failed, 10 passed`; sin la mutación, `14 passed` |
| 4 | U2 vuelve a verde | `uv sync --frozen && make -C identity-edge check` | pasa: `2525 passed in 718.80s`, `ca4 exit 0`, ninguna prueba omitida (los únicos `Skipped` del log son `Skipped: 0` de kubeconform) |
| 5 | U1 sigue cumpliendo, en serie después de CA-4 | `make -C platform check-local` | pasa: `ca5 exit 0`, `243 archivos Markdown sin enlaces rotos`, `0 chart(s) failed` |

Otras comprobaciones, todas en la copia:
- Plan con el Paso 13 en `[ ]` sin sufijo y el Paso 14 en `[x]`: `14 passed`.
- Paso 14 como `- [x] **Paso 14 — …** (U02-T15)`, que es el estado que dejará U02-T15: `14 passed`. NEXT_STEP acepta los dos estados.
- La versión de la prueba en 08e29d2 contra el plan actual: `5 failed, 1 passed`. Reproduce el rojo de la bitácora.
- Si STEP o NEXT_STEP solo aceptan `[ ]`, el caso nuevo falla 4 de 8. El caso parametrizado sí distingue el defecto.

## Hallazgos

### F-01 · ROJO · CA-2 · El caso de los estados del checkbox no corre sobre el texto del plan ni compara el bloque entre estados
`test_e2e_inventory.py:128-135` (`test_block_location_does_not_depend_on_checkbox_state`) arma un texto sintético de cinco líneas: `**Paso 12 — Otro**`, un cuerpo de dos viñetas y `**Paso 14 — Carga**`. Luego compara `step_13_block(text)` con un valor esperado distinto en cada combinación, porque el esperado incluye la marca y el sufijo de esa combinación.

CA-2 pide dos cosas que el caso no hace:
- Que la localización se ejecute **sobre el texto del plan**, el `PLAN` real con los encabezados de los Pasos 13 y 14 reescritos en cada estado.
- Que en todos los casos **el bloque que obtiene sea el mismo**.

Así como está, ninguna aserción relaciona los estados del checkbox con el plan real ni con las 12 viñetas que se extraen de él. El comportamiento es correcto, porque con mis mutaciones del plan real todo pasa. Lo que no se cumple es el criterio tal como está escrito: la prueba que pedía no existe.

Corrección esperada: leer `PLAN`, reescribir las líneas de los encabezados de los Pasos 13 y 14 según los parámetros, y verificar que `plan_bullets(variante) == plan_bullets()`, es decir, el mismo resultado de 12 viñetas en todos los casos. Si se quiere comparar el bloque en sí, hay que hacerlo sin la línea del encabezado. `plan_bullets(text=...)` ya admite texto inyectado, pero ninguna prueba lo usa.

### F-02 · AMARILLO · test_e2e_inventory.py:21-22 · El ancla `^` no está cubierta por ninguna prueba
Quité el `^` de NEXT_STEP en la copia y la suite siguió en `14 passed`. El comentario de la línea 20 dice que el patrón está anclado al inicio de línea, pero ninguna prueba falla si se pierde el ancla. Hoy el plan menciona «Paso 14» en las líneas 278 y siguientes, después del Paso 14, así que no importa. Bastaría un caso con una mención `- [ ] **Paso 14` sangrada dentro del Paso 13.

### F-03 · AMARILLO · test_e2e_inventory.py:21-22 · `[X]` en mayúscula no se acepta
Markdown/GFM también acepta `[X]` como casilla marcada, y el patrón `\[[ x]\]` lo rechaza. El orquestador usa `[x]`, así que no rompe nada hoy. Es solo fragilidad.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Revisé `identity-edge/tests/unit/test_skeleton.py`, `identity-edge/tests/strategies/envoy_gateway_design.py` y `platform/tests/test_unit_plans.py`: ninguno busca el literal `- [ ] **Paso`. La falta del chart keycloakx en un worktree nuevo ya está en CANDIDATAS.md:88, como dice la bitácora. Como lo había preparado el codificador, CA-4 corrió con `.tools` y `.charts/keycloakx` ya presentes (no los vuelve a instalar).
- Ya registrada en la tarea: el CI no corre las pruebas de identity-edge.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r1/ca4.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r1/ca5.log
- Copia usada para las mutaciones: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T16-r1/mut/vectra-risk

```
VEREDICTO: NO-VERDE
ROJO|CA-2 (test_e2e_inventory.py:128-135)|El caso de los estados del checkbox no corre sobre el texto del plan ni compara el bloque entre estados
INFORME: revisiones/U02-T16/ronda-1.md
```
