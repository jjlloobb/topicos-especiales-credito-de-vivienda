# Ronda 6 — U02-T18

VEREDICTO: VERDE

Las cuatro comprobaciones pasan. La frase nueva del runbook es verdadera según el orden de desalojo del kubelet. Quedan dos AMARILLO y ninguno bloquea. El worktree está limpio al terminar (`git status --short` vacío) y la tarea tiene el hash `d088a48b0a137d67c0ea860f84d1a5e49ddde7fd`, el que me diste.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | La frase del paso 6 es verdadera según el orden de desalojo del kubelet | Comparé el texto con `ronda-5.md` F-02, con `U02-T18-r5-rev-eviction.log` y con el orden del kubelet | pasa |
| 2 | Las cifras salen del render de kind y de `priority-classes.yaml` | `grep` en `identity-edge/keycloak/rendered/kind/keycloak.yaml` y `cat platform/policies/priority-classes.yaml` | pasa |
| 3 | El diff solo toca el runbook y la bitácora | `git diff --stat 0233bb0..3aa8fe8` | pasa: 2 archivos, `bitacoras/U02-T18.md` (+7) y `identity-edge/runbooks/keycloak-down.md` (+1/−1) |
| 4a | Prueba de runbooks | `uv run python platform/tests/test_runbooks.py --root identity-edge` | pasa: `24 alertas con su runbook en regla`, exit 0 |
| 4b | Prueba de enlaces | `uv run python platform/tests/test_links.py` | pasa: `276 archivos Markdown sin enlaces rotos`, exit 0 |

Las dos pruebas tardan unos 0,13 s y 0,16 s. Eso cuadra: solo leen archivos Markdown y YAML del árbol y no dependen de nada externo, así que no es señal de que se hayan saltado.

### Comprobación 1: por qué la frase es verdadera
Ante presión de memoria, el kubelet ordena los pods así:
1. Primero los que usan más que su request de memoria.
2. Después, la prioridad del pod (la más baja cae antes).
3. Al final, cuánto exceden su request.

En el render de kind hay 15 pods sin request de memoria y sin `priorityClassName`: cert-manager (3), trust-manager, cloudnative-pg, external-secrets (2), argo-cd (7) y vault. Ninguna PriorityClass tiene `globalDefault`; lo busqué con `grep -rn globalDefault` y no sale nada, así que su prioridad es 0.
- Con request 0, cualquier uso supera la request, así que esos 15 están siempre en el primer grupo.
- Keycloak lleva `vectra-high` (100000). Si está en ese grupo, esos 15 caen antes que él por prioridad. Si no lo está, caen antes igual, por el primer paso del orden.

La afirmación «antes que él caen los pods de U1 sin request de memoria ni prioridad» se cumple en los dos casos. La frase también se limita bien a los pods sin prioridad. Los dos pods de linkerd tampoco tienen request, pero llevan `vectra-critical` y caerían después de Keycloak; la frase no los menciona y acierta.

### Comprobación 2: de dónde salen las cifras
- `rendered/kind/keycloak.yaml`: `memory: 2Gi` (línea 321, el limit), `memory: 512Mi` (línea 324, la request) y `priorityClassName: vectra-high` (línea 381).
- `priority-classes.yaml`: `vectra-high` vale `100000`.
- El «1 Gi en staging y prod» no cambió y ya lo validó la ronda 5.
- El texto sigue el C-03 enmendado de la tarea (línea 188).

## Hallazgos
### F-01 · AMARILLO · tarea, «Cierre después de la ronda 5», tercer criterio · la base `49db24b` incluye los commits del orquestador
La tarea pide `git diff 49db24b --stat` y espera ver solo el runbook y la bitácora. Ese comando muestra 6 archivos: suma `CANDIDATAS.md`, `revisiones/U02-T18/arbitraje-ronda-1.md`, `revisiones/U02-T18/ronda-5.md` y la propia tarea. Esos cuatro vienen de `0a76e94` y `0233bb0`, que son los commits del orquestador que registran la ronda 5 y el cierre, y no del codificador.
- El criterio, tal como está escrito, no puede cumplirse nunca, porque el commit que lo escribió queda dentro del rango.
- Lo que el criterio busca sí se cumple: `0233bb0..3aa8fe8`, el rango que me pediste, solo toca los dos archivos. No hay desborde.
- Es un defecto del texto de la especificación, no del diff.

### F-02 · AMARILLO · `identity-edge/runbooks/keycloak-down.md:18` · «arranca usando más que su request» no está medido
Esa parte la exige el C-03 enmendado, pero no hay ninguna medición del uso real de Keycloak:
- No la encontré en las bitácoras ni en las revisiones.
- El clúster kind `vectra` no tiene pods en `vectra-identity`.
- `kubectl top` responde `Metrics API not available`.

Es verosímil: `JAVA_OPTS_APPEND=-XX:MaxRAMPercentage=70` con 2 Gi de limit deja que el heap llegue a unos 1,4 Gi. Y la conclusión sobre el orden de desalojo vale igual aunque no fuera cierta, como explico arriba. No bloquea. La tarea de U1 para kind-demo (RD5), que rehace el presupuesto con el uso real, es el sitio natural para medirlo.

## Tareas candidatas (defectos reales fuera de alcance)
- Medir el working set de Keycloak al arrancar en kind dentro de la tarea de U1 para kind-demo (RD5), junto con F-01 y F-03 de la ronda 5, que ya se pasaron allí.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r6-rev/runbooks.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r6-rev/links.log
- Evidencia del desalojo (ronda 5): /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r5-rev/U02-T18-r5-rev-eviction.log

```
VEREDICTO: VERDE
AMARILLO|tarea U02-T18, «Cierre después de la ronda 5»|la base 49db24b del criterio de diff incluye los commits del orquestador
INFORME: revisiones/U02-T18/ronda-6.md
```
