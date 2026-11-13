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

## 5. Ritmo del loop para la demo (2026-11-08)

`U02-T17` (7 Applications de GitOps) costó unas 12 horas de reloj: 3 rondas, 2 revisiones de código encima de rondas VERDE y 2 PR. La mayor parte se fue en hallazgos NARANJA y AMARILLO sobre pruebas de waves y textos de la tarea, y en `make -C identity-edge check` (≈ 25 min por corrida). Uno de los hallazgos de la revisión de código fue culpa mía: la tabla de la tarea decía que `identity-jobs` incluía `keycloak-config-cli`, y el arbitraje de C-05 heredó ese error.

Con ≈ 170 pasos por delante para la demo, el usuario aprobó las reglas RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: una tarea por bloque, máximo 2 rondas con solo ROJO bloqueante, sin revisión de código extra, `make check` por unidad y hasta 3 codificadores en paralelo. Es un cambio de costo de proceso, no de alcance: el código de cada paso E entra completo.

## 6. `test_traceability.py --all` con unidades en curso (2026-11-09)

En la ronda 2 de `U03-T05`, `--all` salió con rc=1 por 26 identificadores de U4. U4 tiene código a medias en main desde U04-T01, y U3 estaba limpio. El usuario aprobó la regla **«sin fallos nuevos»**. `--all` cuenta como pasado si:
- cada línea que falla es de una unidad sin `evidence/cierre-demo.md`;
- el conjunto de fallos es idéntico al de main en la base de la rama.

El revisor lo comprueba corriendo `--all` también sobre la base. Rige para todas las tareas de la demo. Los cambios de la herramienta están en `CANDIDATAS.md`.

**Enmienda del 2026-11-09 (usuario, arbitraje de la ronda 3 de `U09-T01`).** Tal como estaba, ninguna unidad que empieza a tener código podía cumplir la regla. Desde ahora `--all` cuenta como pasado si **cada** identificador que falla en la rama cumple una de estas condiciones:
- ya fallaba en main, en la base de la rama, y es de una unidad sin `evidence/cierre-demo.md`;
- es nuevo, es de la unidad de la tarea, esa unidad no tiene `evidence/cierre-demo.md` y no pertenece a un paso que la tarea cubre.

Un identificador de un paso que la tarea cubre debe quedar trazado. El revisor corre `--all` en la base y en la rama, y cruza cada fallo nuevo con los pasos de la tarea. Detalle en `revisiones/U09-T01/arbitraje-ronda-3.md`.

## 7. Presupuesto de memoria de kind con U6 (2026-11-09)

El revisor de U06-T02 midió que, con 512 MiB por pod de serving, U6 sube lo pedido en kind de 6,0 GiB a ≈ 8,1 GiB con el modelo activo y a ≈ 10,2 GiB durante una promoción (M1 y M2 en `prod`), y que con U7 y U9–U12 el pico no cabe en la máquina de 14 GiB. El usuario eligió la **opción (c)**:

- en kind, los requests de memoria de los componentes de `model-serving` bajan de 512 a **256 MiB por pod**, con un override en los values de kind del chart de U6; **sin** tocar las 2 réplicas mínimas, el HPA ni los PDB (sigue cumpliendo `require-hpa-bounds`, y el escenario 2 de U6 conserva «nunca menos de 2 réplicas»);
- `BUDGET_GIB` de `platform/tests/test_kind_profile.py` sube a la cifra medida con U6 incluida (≈ 8,3 GiB) y se vuelve a revisar con cada unidad nueva;
- staging y prod no cambian; el escenario de memoria de U06-T03 comprueba en kind que 256 MiB bastan para el modelo de referencia.

Descartadas: (a) solo subir `BUDGET_GIB` (con U7–U12 el pico ≈ 13 GiB no cabe) y (b) DD-3 a con 1 réplica (choca con `require-hpa-bounds` y rompe el escenario 2). Lo aplica U06-T03.

## 8. Verificación en kind consolidada en U12 (2026-11-10)

El usuario preguntó por cuarta vez si se podía trabajar solo en lo necesario para la demo. Aceptó la recomendación: quitar los bloques de verificación en kind de U3, U7, U8, U9, U10 y U11, pasar su cierre a la última tarea de código y hacer la verificación una sola vez en U12 Paso 18, con los ensayos de las cuatro demos. U4 y U6 conservan sus guías de kind (arranque de la política y del modelo, P-7). Pasa de ≈ 33 a ≈ 27 tareas pendientes. Las revisiones por tarea se mantienen. Detalle en `aidlc-docs/construction/plans/demo-recorte-funcional.md` §8.

## 9. Decisiones del 2026-11-12

**U03-T07 aparcada.** Con el tope por solicitud en 1,5 s (espera del pool `projections` menos un margen de 0,5 s), las formas reales de U9 reciben 504 cuando la máquina está cargada: el revisor midió 3 fallos en 17 corridas y `make -C decision-registry check` en exit 2, igual que el codificador. Ningún margen cumple a la vez «la `explanation` concurrente obtiene su conexión» y «la consulta de U9 nunca recibe 504». El usuario decidió aparcar la tarea: no hay ronda 3 ni pull request, y `main` queda sin el tope. Un 504 de U3 al cron de U9 impide el congelamiento (BR-U9-10), que es el centro de la demo D2. La rama `tarea/U03-T07` se conserva en el remoto con sus dos rondas (`revisiones/U03-T07/` en esa rama). La candidata sigue abierta para después de la demo.

**U10, Bloque E partido en dos.** El usuario aprobó partir la SPA en U10-T03 (Pasos 10–12) y U10-T04 (Pasos 13–16); el despliegue y el cierre pasan a U10-T05. U10 queda en 5 tareas (`demo-recorte-funcional.md` §8).

**U10, mecanismo del login.** El diseño se contradecía: P-U10-07 y tech-stack §2 piden `InMemoryWebStorage` para el login, y el Paso 11 pide redirección, que borra la memoria. El usuario decidió: login por redirección, con solo el estado transitorio del flujo (`state`, `code_verifier`, `nonce`) en `sessionStorage`; los tokens y el usuario siguen en memoria (BR-U10-05); la recarga se resuelve con una redirección `prompt=none`, sin iframe; no se usa `signinPopup` ni `signinSilent`. El step-up del Paso 10 no cambia. No se toca U2. Detalle en `revisiones/U10-T03/arbitraje-ronda-1.md`.

**U08-T04, ronda 3 acotada.** Excepción a RL-2 autorizada por el usuario: la ronda 2 cerró el defecto real (el resultado tardío de otro ciclo se aplicaba al caso) y dejó un ROJO de una sola prueba, «`GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0», que es la base de la demo D3. La ronda 3 cubre esa prueba y tres AMARILLO, y nada más (`revisiones/U08-T04/arbitraje-ronda-2.md`).

**U11, memoria en kind.** El usuario eligió la opción (b) de la pregunta P-1 de U11-T03: el request de memoria de `product-metrics` es de 128 MiB **solo en kind**; staging y producción conservan el valor del diseño. Es una excepción anotada a «kind igual a staging», para que el perfil completo quepa en la máquina de la demo (§7).
