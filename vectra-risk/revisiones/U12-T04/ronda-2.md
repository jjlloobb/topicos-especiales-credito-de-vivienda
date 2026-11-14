# Ronda 2 — U12-T04

VEREDICTO: VERDE

Los cuatro ROJO de la ronda 1 están cerrados: corrí cada caso yo mismo, con la biblioteca real de `promotion-tool` y con mutaciones. Quedan 3 NARANJA nuevos que no hacen fallar ni mentir a ningún guion; con RL-2 van a `CANDIDATAS.md`.

El `make -C system-verification check` completo pasó con rc=0: 982 + 784 pruebas, ninguna omitida, 95,77 % de cobertura, `report`/`sampler` al 100 %, `Contracts: 11 kept`. Semillas 4006433622 y 4197307416. Tardó 117 min de reloj: la máquina pareció suspenderse a mitad (de 08:44 a 10:20 la suite solo llegó al 16 %) y el check de U12-T05 corría a la vez. Carga de 2,3 a 8,2.

**Hay que decirte una cosa sobre esa corrida.** Rompí la regla de un solo Keycloak a la vez. Al empezar había un Keycloak huérfano, `u12t02-keycloak-20bfafe9`, creado a las 07:56 por una corrida anterior; no era mío y ningún proceso vivo lo usaba. Intenté excluir `test_oidc_headless.py` con `PYTEST_ADDOPTS=--deselect`, pero la ruta no coincidió con el id de la prueba y la suite corrió entera. La fixture esperó a que no hubiera Keycloak ajeno (hasta 900 s) y después levantó el suyo, así que hubo un rato con dos.

Estado final: worktree limpio (`git status --short` vacío), HEAD en 2f5b25e, ningún contenedor Keycloak, Prometheus ni Postgres en `docker ps -a`.

Por error escribí mis primeros logs en `scratchpad/r2/`, que es la carpeta de logs del codificador. Solo agregué archivos nuevos; no borré ni sobrescribí ninguno suyo (su `check.log` está intacto). Copié los míos a una carpeta nueva.

## Estado de lo arbitrado
| Hallazgo | Estado | Comando que corrí | Resultado |
|---|---|---|---|
| F-01 ROJO (D1, paso 6) | **cerrado** | leí el guion de D1 completo; `grep retry` en `console/spa/src`; `journey-7-3.sh 4` contra 3 manifiestos | El guion dice lo que pasa: vuelven los 5 recursos, un caso nuevo llega a `listo` y `FailClosedPersistente` sigue en `firing`. No hay acción de reintento en la SPA (`/fallos` con `entry:false`; el BFF sí tiene la ruta). El verify da 0 solo si `closing_rt3=pasa`, y eso exige el caso en `listo` (`rt3.py`, cierre). Da 1 con `no ejecutado` y 2 sin cierre |
| F-02 ROJO (plantillas) | **cerrado** | `entrada.py` en 4 estados: vacío; M1 en `prod` (con `promote`); M1 `inactive` + M2 `prod`; lo mismo más otra entrada `staging`. Luego `git apply`, `helm template` y `values.parse` | Aplica en los 4. `helm` rinde el `isvc` nuevo en `vectra-staging` y deja los de `vectra-serving`. `promotion-tool` vuelve a leer el archivo sin error. Pasa la prueba de verbos. No escribe archivos |
| F-03 ROJO (cierre de D2) | **cerrado** | la secuencia del guion con `vectra_promotion.values`; `journey-7-4.sh 4` en los 6 cruces | Cada orden es admisible en el estado que deja la anterior. `rollback-pr <M1>` ya no da `entry_not_found`. `mark-active <M1>` es admisible. El paso 9 también. El verify da 0 solo con `Ready=True` y `closing_rt2=pasa`; 1 si el cierre es `no ejecutado` o no está `Ready`; 2 si el manifiesto no trae el cierre |
| F-04 ROJO (pragma) | **cerrado** | `git diff ac9f86c..HEAD -- …/src \| grep pragma` | ningún resultado (rc=1) |
| F-05 | **cerrado** | Monte Carlo con lectura cada 30 s hasta 300 s; mutación «leer una vez» | 0 % de `no ejecutado` con raspado y evaluación de 30 s o 60 s; 0,15 % con 120 s. La mutación hace caer 2 pruebas |
| F-06 | **cerrado** | mutación que vuelve al camino viejo | caen 3 pruebas `test_exit_f06_*` |
| F-07 | **cerrado en lo pedido** | `embedded.py`, `r2cases.py`, `big.py` y una sonda de ida y vuelta | El HAR dentro de una cadena JSON sale limpio, en las dos sangrías y en los 5 casos. 16 KB de `\"` tardan 0,02 s y 200 KB, 0,16 s. Los legítimos quedan intactos. Seis evidencias limpias quedan idénticas byte a byte: Unicode, `\u`, `\/`, números grandes, claves repetidas y surrogates sueltos. Quedan residuos (ver N-3) |
| F-08 | **cerrado** | mutación a `floor = self._since` y mutación a `since=now` | La primera hace caer `test_f08_*`. La segunda hace caer una prueba en 103 s y ya **no cuelga** la suite |
| `waits.EPSILON` | **correcto** | mutación `EPSILON=0` | Cae `test_a_deadline_…` en 0,06 s. Con el reloj real no había bucle infinito, porque `time.sleep` siempre avanza `monotonic`; el arreglo cambia como mucho 1 µs. Las pruebas de RT-2, RT-3 y RT-5 pasan (dentro de `check`) |
| F-09 | **cerrado** | `grep` de rutas en `src/`; `cli.main` sin `--delivery`; sonda de `--help` | No queda ninguna ruta literal del repositorio en el código, solo en docstrings y en el texto de ayuda `make -C reference-model release`. `rt3` sin ruta da código 3 `ruta_faltante`. `--help`: 16 códigos 0, sin red ni archivos. `test_live.py` existe y `live.py` está al 99 %. Límite conocido: la ventana TOTP no se comparte **entre procesos**, porque `TOTP_WINDOWS` vive en memoria; dos órdenes seguidas con el mismo usuario dentro de 30 s pueden chocar |
| F-10 | **cerrado para Ctrl-C** | excepción inyectada en 3 fases, más un caso de proceso matado | Interrupción esperando el `freeze` o al presentador: 1 lote, se retoma sin reenviar. A mitad del lote: se reenvía (es inherente). Proceso matado: **reenvía** (N-1). El archivo sigue pasando por `Store` |
| AMARILLO de orden | **cerrado** | mis 3 mutaciones que sobrevivían, más 2 nuevas | Mueren todas: el Job `rt5-probe`, `rt2` antes de `rt2-setup`, `rt5` antes del PR, `mark-active <M1>` antes del `rollback-pr`, y el paso 3 sin `post-activation-pr` |
| AMARILLO D2-2 y D4-1 | **cerrado** | lectura de `journey-7-4.sh 5` y `dashboard.sh 5` | los dos leen el manifiesto |

Alcance: `git diff f3873bd..HEAD` no toca nada fuera de lo permitido (`fuera=1`). No hay `Dockerfile`, README, `Makefile` de la unidad ni `docs/kind`. `uv lock --check` da `Resolved 127`. Enlaces: 591 archivos sin rotos.

## Hallazgos nuevos
### N-1 · NARANJA · `scenarios/rt2.py:1008-1011` · El guardado por fase llega una fase tarde
- `deps.checkpoint(state)` se llama **antes** de `vs.done[phase] = result`. Cada guardado no incluye la fase que acaba de terminar.
- Con Ctrl-C lo tapa el `finally` de `cli.py`. Pero con SIGKILL o SIGTERM, por ejemplo un `docker stop` de la imagen, el último archivo es el posterior al `lote` y no lo marca como hecho: la retoma **reenvía el lote**.
- Reproducido: excepción mientras espera el `freeze` y `state-rt2.json` repuesto al penúltimo guardado → `lotes_antes=1 lotes_despues=2`.
- Arreglo: guardar después de marcar la fase.

### N-2 · NARANJA · `cli.py:826` y `rt2._wait_closing` · Un cierre de D2 vencido no se puede retomar
- Si el operador no hace el paso 7 dentro de `--operator-timeout`, queda `closing_rt2=no ejecutado` y `rt2` queda `terminada`.
- Volver a correr `rt2` responde «ya terminada». `--redo` empieza desde cero: reenvía el lote y necesitaría otro `freeze`.
- No hay un `rt2 --closing`. `journey-7-4.sh 4` dirá la verdad («no está activo»), pero ese estado ya no se puede corregir.

### N-3 · NARANJA · `evidence.py` · Residuos del filtro de HAR
- Un apóstrofo antes del objeto, en la misma línea y dentro de una cadena JSON (`"it's here {…Cookie…}"`), sigue fugando.
- Fugan también un objeto sin cerrar y un anidamiento de 4 o más niveles (el tope es 3, por diseño).
- Son anteriores a esta tarea y no hay ninguna evidencia real con esa forma.

### AMARILLO
- `entrada.py`: un archivo que no existe da un traceback en vez de un mensaje. Un YAML mal formado produce un parche igual (luego `helm` lo detecta).
- `ruta_faltante` se decide después de leer los digests con `kubectl`: hay lecturas antes de que la herramienta se niegue.

## Tareas candidatas
- N-1, N-2 y N-3, y la ventana TOTP entre procesos.

## Rutas
Mis logs de esta ronda, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u12t04-r2/`:
- `check.log`
- `f02.log`, `st/`, `verify4.log`
- `mut.log`, `mut-cli.log`
- `f10.log`, `f10b.log`
- `f07a.log`, `f07b.log`, `big.log`
- `help.log`, `paths.log`

```
VEREDICTO: VERDE
NARANJA|scenarios/rt2.py:1008|El guardado por fase llega una fase tarde: con SIGKILL o SIGTERM se reenvía el lote
NARANJA|cli.py:826 / rt2._wait_closing|Un cierre de D2 vencido no se puede retomar sin --redo
NARANJA|evidence.py|Residuos del HAR: apóstrofo previo, objeto sin cerrar y 4 o más niveles
INFORME: revisiones/U12-T04/ronda-2.md
```
