# Decisiones del loop

Las cuatro preguntas de la sección 13 del módulo 6. La evidencia está en `revisiones/`, `bitacoras/` y los PR 31 a 37.

## 1. Un empujón de vuelta del codificador, arbitrado

En la ronda 2 de `U01-T03`, el revisor marcó F-04: la prueba de F130 solo miraba `vectra-observability`, así que un flujo con el mismo id en otro namespace también pasaba. El codificador respondió que no era propio de F130, porque cualquier flujo tiene la misma laxitud, y que endurecerlo era una prueba genérica del inventario (`revisiones/U01-T03/ronda-2-respuesta.md`).

**Le di la razón.** La mutación N17 del revisor lo confirmaba: el hueco está en la forma de probar todos los flujos, no en el diff. El hallazgo se cerró y pasó a `CANDIDATAS.md`.

En la misma ronda decidí lo contrario con F-03. F130 rompía `test_flow_ports_are_really_open[alertmanager]` en `platform/tests/test_integration.py`, fuera de los archivos que nombraba la tarea. **No lo acepté como fuera de alcance**, porque era una regresión causada por el propio diff y habría dejado `make check-local` en rojo. Entró en la ronda 3.

La regla que usé: lo que el diff rompe es del diff; lo que ya estaba flojo antes es candidata.

En `U01-T04` el empujón fue el contrario. La tarea dejaba `seed-vault.sh` fuera de alcance, y el codificador encontró que CA-2 no podía pasar porque el script dejaba el `port-forward` huérfano: `kill` mataba el subshell, no a `kubectl`. No tocó el script. Hizo commit con la prueba en rojo, sin `xfail`, y pidió decisión.

**Lo metí en el alcance** (`revisiones/U01-T04/arbitraje-ronda-1.md`). La tarea preveía ese caso, CA-2 era su propio criterio y el arreglo era de una línea. El revisor confirmó después el defecto con un sustituto de `kubectl` que no dependía del falso de la prueba.

## 2. La tarea que más rondas costó

`U01-T03` y `U01-T06` costaron 3 rondas cada una. La de `U01-T03` es la que apunta a un problema de especificación, y el problema fue mío:

- **Ronda 1:** la prueba pasaba con puertos cruzados, otro origen u otros destinos (mutaciones M1, M2 y M3). El criterio CA-1 decía «con esos puertos», pero no exigía atar puerto, origen y destino.
- **Ronda 2:** los criterios solo corrían `platform/network/tests`. Un flujo nuevo podía cumplirlos todos y romper `test_integration.py`, que corre en CI.

Las tareas de flujos deben incluir `pytest platform/tests/test_integration.py` con charts entre sus criterios. Quedó en `CANDIDATAS.md`.

`U01-T02` costó 2 rondas y también tenía un error mío: la nota decía que el chart ejecuta los comandos «sin shell», y es falso. El codificador lo detectó, y la ronda 1 salió NO-VERDE por otra razón: el overlay de kind, que es lo que de verdad corre, no tenía cobertura.

`U01-T06` tuvo otra causa: el retrabajo de la ronda 1 dejó pruebas que no pasaban por ningún tiempo agotado real, y el revisor lo demostró con mutaciones que sobrevivían. La especificación estaba bien; el codificador tardó en cubrirla.

## 3. Un hallazgo del revisor que no habría visto yo

En la ronda 1 de `U01-T06`, el codificador añadió reintentos ante tiempos agotados a todas las llamadas a Grafana, también al `POST /api/folders`. El revisor vio que, si Grafana crea la carpeta y la respuesta se pierde, el reintento recibe un 409 y el script informa un fallo sobre una creación exitosa. Lo comprobó contra Grafana real: un UID duplicado responde 409.

Los criterios pasaban y el diff se veía correcto. Yo lo habría aprobado.

El revisor tampoco fue complaciente consigo mismo: en `U01-T03` retiró una candidata suya sobre `test_traceability`, al ver que era un artefacto de sus copias.

## 4. Costo en tokens de la ola en paralelo

La ola 2 (`U01-T03`, `U01-T05`, `U01-T06`) usó **unos 989.000 tokens** entre subagentes, contra 300.000 que estimé. La diferencia la explican las rondas: dos tareas necesitaron 3. Los revisores gastaron más que los codificadores, porque corren mutaciones y repiten cada comando.

**No medí la ola en serie**, así que no tengo la comparación directa. Lo que sí se puede afirmar:

- Cada subagente trabaja en su propio contexto, así que correrlos en serie habría costado casi lo mismo en tokens de subagentes. El paralelo ahorró tiempo de reloj, no tokens.
- El costo extra del paralelo está en el orquestador: arbitrar tres tareas a la vez obliga a sostener tres informes en su contexto. Por eso el contrato limita a 3.
- La tercera tanda (`U01-T02` y `U01-T04`, en paralelo, 2 rondas cada una) sumó unos 676.000 tokens según los contadores de las notificaciones. Si las reanudaciones de un mismo subagente acumulan, la cifra real se acerca a 340.000; no lo verifiqué.
- En una ola, los hallazgos de una tarea no informan a las demás. La lección de `U01-T03` sobre `test_integration.py` llegó tarde para reescribir criterios de otras tareas de la misma ola.

## Límites que declaro

- Los tres papeles corrieron en **una sola sesión de Claude Code**: el orquestador es la sesión principal, y codificador y revisor son subagentes con su propio contexto (`sonnet` y `opus`). Los contratos de `.claude/agents/` no estaban registrados en esa sesión, así que sus límites de herramientas se aplicaron **por instrucción**, no por configuración.
- Cada codificador trabajó en su worktree. Al cerrar cada ronda, los worktrees quedaron sin cambios fuera del commit.
- Ningún agente fusionó: todos los PR los aprobó y fusionó una persona.
- Ningún cambio del loop se aplicó a un clúster.
