# Ronda 1 — U12-T04

VEREDICTO: NO-VERDE

Revisé la rama `tarea/U12-T04` en f3873bd contra ac9f86c (hoy `origin/main` es ac9f86c). El hash de la tarea coincide (a15e8c9e…). Todas las suites pasan. Aun así quedan **4 ROJO**: tres en los guiones y PR preparados (fallarían o mentirían delante del público) y uno en CA-16. Al terminar, el worktree quedó limpio (`git status --short` vacío) y HEAD sigue en f3873bd. Ningún contenedor mío quedó vivo. El Keycloak `u12t02-keycloak-e0867936`, «Up 2 minutes» al cierre, es de otro agente y no lo toqué.

## Guion frente al repositorio
| Demo | Pasos comprobados | Lo que no coincide |
|---|---|---|
| D1 `journey-7-3.md` | 6 de 6. F22: `git apply --check` limpio; se van exactamente los 5 recursos; `generate.py --check`=0; revertir deja el árbol limpio. `rt3 --packages-dir/--rt3b-dir/--closing` existen. `analista-2` tiene el rol `analista`. `/casos` tiene `entry:true`, y `list_cases` no filtra por usuario. `FailClosedPersistente` existe. Los verify 1 a 5 existen | **F-01**: el paso 6 («la alerta se apaga») y `journey-7-3.sh 4` no pueden pasar. Además, «≥ 19,3 min» debería ser «12,4 a 19,3 min» (`rt3.py:63`) |
| D2 `journey-7-4.md` | 8 de 8. `cumplimiento-2` tiene el rol; `/congelamientos/:freezeId` es solo de `cumplimiento`. `cro` puede leer modelos (`role-endpoint-matrix.md:40` y `:65`, BFF y governance). Las opciones de `rt2` existen | **F-02**: `proxy.patch.tpl` no aplica con el modelo de referencia ya promovido. **F-03**: el cierre no es ejecutable (falta `post-activation-pr`, falta `mark-active` de M1, `rt2` se queda 1 h esperando) y `journey-7-4.sh 4` da OK aunque la referencia no esté activa |
| D3 `rt-5.md` | 6 de 6. Job `rt5-demo-<runId>` en `vectra-app`. El log trae `-> 403 l5d-proxy-error: `. La expresión de `CoreWriteAttempt` da ≈ 5 min en `firing`, sin `for:`. Series correctas. Línea 68: verde y 4 rojos (abajo) | nada |
| D4 `dashboard.md` | 5 de 5. Las 4 expresiones son idénticas a `product.json`. El uid y la carpeta existen. Hay pods con `name=grafana` y el secreto `grafana-admin` existe. La barrera de las 23:00 está | La estimación de `decisions` no cuenta la espera nueva: leer 2 000 casos a menos de 20/s son más de 100 s, y el plazo puede llegar a 1 800 s (AMARILLO) |

Sin `verify` hay **6** pasos, no 8: D1-2, D2-1, D2-2, D2-5, D2-6 y D4-1. Justificados: D1-2, D2-1, D2-5 y D2-6. **No justificados**: D2-2 y D4-1 dicen «no observable», pero lo que dejan está en `manifest.json`, y los `verify` pueden leer ese archivo (`lib.sh` ya lo lee). AMARILLO.

**Mis mutaciones sobre los guiones** (en el worktree; cada una deshecha con `git checkout`):
- **Detecta:** namespace `vectra-servings` (`journey-7-3.md:10`); opción `--reactivacion` (`:28`); `rt2 --closing`, una opción de otra sección; `ruta /sesgo`, diferida; `cro-2` en `/congelamientos/:freezeId`.
- **Detecta por un motivo distinto:** `/fallos` sin la convención `ruta` solo cae por una frase escrita a mano en la prueba; `` `/expedientes` `` cae como «ruta citada que no existe».
- **No detecta:** el Job renombrado `rt5-probe-<runId>`; `rt2` antes de `rt2-setup` (D2, pasos 2 y 4 intercambiados); `rt5` antes del PR de `runId`. La prueba **no comprueba el orden** de los pasos.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Estructura e imports | literal de CA-1 | pasa: `11 kept`, `OK` |
| 2, 5, 6–14 | pruebas de la tarea | `make -C system-verification check` | pasa: 921 + 734, 0 omitidas, 21 m 46 s (carga 2,2→3,1), semillas 2579030150 y 153801887, cobertura 94,31 %; `report`/`sampler` al 100 % |
| 3 | PR preparados | `apply --check`, `generate --check`, `policy-chart` ×6 | pasa sobre `main`; **falla en el estado de la demo** (F-02) |
| 4 | Verbos y shellcheck | dentro de `check` + sonda | pasa |
| 15 | Realm | grep (`reparacion=1`) + `test_oidc_headless` real | pasa |
| 16 | Cobertura sin pragmas nuevos | `git diff … \| grep pragma` | **falla** (F-04). Ramas: cli 91,2 %, manifest y store 100 % |
| 17–21 | trazabilidad, enlaces, plan, alcance | literales | pasan (solo INF-U12-05; `fuera=1`; Makefile 1 línea; `evidence/` solo `.gitkeep`) |

Línea 68 de `case-management/Makefile`: `policy-chart` da rc=0 en la base y con `ejemplo.patch` aplicado (3,1 s). Da rc=2 en la línea del `grep`, con `runId` en `staging`, `prod`, `chart/values.yaml` y `values-kind.yaml`. El `runId` lo puse como comentario, para que el rojo saliera del `grep` y no de `conftest`.

Las 33 fallas de `platform/network/tests` (33 fallan, 178 pasan) son del entorno, no del diff: falta `envoy-gateway` en `.charts` y el diff toca 0 archivos de `platform/`.

## Hallazgos
### F-01 · ROJO · `demos/journey-7-3.md` (paso 6) y `verify/journey-7-3.sh:33-40` · La alerta no se apaga al revertir F22
- El gauge `vectra_cases_failclosed_persistent` cuenta `SELECT count(*) … WHERE state = 'no_disponible'` (`db_gauges.py:34`).
- Los 5 casos de sonda solo salen de `no_disponible` con un `retry` del CRO (`api.py:246-252`). `rt3_closing` no los reintenta: crea uno nuevo (`rt3.py:592`).
- Tras el paso 6 el gauge sigue ≥ 5 y la alerta sigue en `firing`. `journey-7-3.sh 4` imprime «NO ES LO ESPERADO» siempre.
- El propio guion lo contradice en «Qué deja sucio»: «siguen activos en D2 y D4».

### F-02 · ROJO · `demos/prs/proxy-staging/proxy.patch.tpl` y `rt3-staging/*.tpl` · Las plantillas no aplican en el estado de la demo
- El contexto exige `-inferenceServices: []`. Pero el prerrequisito de D1 y D2 es «modelo de referencia activo», y eso pasa por `create-promotion-pr M1` (`paso-20-kind.md`, 5.4), que deja una entrada `prod`.
- Lo comprobé con `vectra_promotion.values.promote(...)` sobre una copia del archivo de values, en el scratchpad: `git apply --check` → `patch failed: …/model-serving.yaml:1` para `proxy` y para `RT3-a`.
- La prueba de CA-3 solo las aplica sobre `main`, donde la lista está vacía.

### F-03 · ROJO · `demos/journey-7-4.md` (pasos 3, 7 y 8) y `verify/journey-7-4.sh 4` · El cierre de D2 no es ejecutable y el verify da OK sin serlo
- El paso 3 no incluye `post-activation-pr`, así que M1 queda en `prod`. Entonces el `rollback-pr` del paso 7 falla (`values.restore` → `PromotionError entry_not_found:inactive`, reproducido). Tampoco hace falta, porque la entrada de M1 nunca pasó a `inactive`.
- El guion omite `mark-active` de M1. `_wait_closing` (`rt2.py:940`) espera `referencia == activo` hasta `--operator-timeout` (3 600 s). Siguiendo el guion, `rt2` se queda colgado 1 h antes de escribir las evidencias, y el proxy sesgado sigue activo para lo que venga después.
- `journey-7-4.sh 4` solo mira que el `isvc` esté `Ready`: da OK con M1 `inactivo` en governance.

### F-04 · ROJO · `cli.py:850` y `cli.py:856` · Dos `# pragma: no cover` nuevos; la bitácora dice que no hay ninguno
- CA-16 exige «Sin `# pragma: no cover` nuevos».
- En la base, `cli.py` tenía 60 bytes. El diff agrega `_live_factory  # pragma: no cover` y `if __name__ … # pragma: no cover`.
- La evidencia de la bitácora es falsa. El arreglo es trivial: sin las dos marcas, las ramas de `cli` siguen en 91 %.

### F-05 · NARANJA · `scenarios/demos.py:76` + `rt3.informative` · `journey-7-3` lee la alerta en el instante de la escalada
- `FailClosedPersistente` necesita el gauge (cada 30 s), el raspado y `for: 1m` después del **primer** caso escalado.
- `rt3` lee una sola vez, cuando ve el **último** caso escalado (sondeo cada 60 s).
- Con una simulación Monte Carlo (jitter de ±20 %, intervalos de 30 s), en ≈ 14 % de las corridas la alerta todavía no está en `firing`: `journey-7-3` = `no ejecutado`, US-111 = `no ejecutado` y `journey-7-3.sh 5` falla. Hay que sondear la alerta unos minutos después de la escalada.

### F-06 · NARANJA · `cli.py:640-650` · `rt3 --closing`, el paso 6 de D1, sin ninguna prueba
- La cobertura muestra 641-650 sin cubrir.
- Además reescribe el registro `rt3` del manifiesto (resultado, código y nota) con el del cierre. Si el cierre sale `no ejecutado`, `rt3` queda `interrumpida`, y un `all` o un `rt3` posterior repite RT-3 entero.

### F-07 · NARANJA · `evidence.py:132-213` · F-N4 corregido solo en texto plano
Mis cuatro casos de la ronda 2, en los dos órdenes, quedan limpios. `{"code": "conflict_state"}`, `http_code=500&…` y un HAR `Accept` quedan intactos. Pero:
- **El mismo HAR dentro de una cadena JSON fuga** (`scratchpad/rev/embedded.log`). Así es como `Store` escribe toda evidencia: `json.dumps({"output": …})`. En la base fugaba igual, así que no es regresión, pero la enmienda no protege lo que de verdad se escribe.
- También fugan: un apóstrofo en la misma línea (`it's {…}`), `name` con `\u0065` y un objeto sin cerrar.
- **Coste cuadrático** con rachas de `\"` fuera de una cadena: 16 KB tardan 5,6 s y 200 KB pasaron de 4 min (`big.log`). Un JSON real de 1 MB tarda 0,4 s. No lanza excepciones.

### F-08 · NARANJA · `scenarios/rt2.py:418` / `cli.py:696` · `PresenterReactivation` no tiene prueba del `since`
- `since = started_at` acepta una `frozen_resolution` de un ensayo anterior en el mismo directorio (`--redo` o un modo `tool` previo) como si fuera la del presentador. Lo correcto es mirar desde el `recorded_at` del congelamiento actual, como hace `verify_reactivation`.
- Mi mutación `since=now` no hace caer ninguna prueba con limpieza: `test_cli.py` se cuelga al 100 % de CPU hasta el `timeout` de 600 s.
- El resto se comporta como se pide: si el presentador no reactiva, `no ejecutado`, retomable en `reactivacion` (probado). Si reactiva otra versión, se ignora y vence el plazo. Si resuelve con `investigar`, `falla`.

### F-09 · NARANJA · `live.py` (0 %) · El docstring cita `tests/unit/test_live.py`, que no existe
- `LiveBackend` ya acepta `runner=` y `vault_transport=`: el armado se puede probar sin clúster.
- Riesgos para kind:
  - `simulator()` usa la ruta literal `reference-model/.out` en todo lo que no es `decisions`.
  - En `all`, `_execute` reemplaza `self.backend` sin cerrar el anterior (navegador y port-forwards).
  - Cada `OidcClient` nuevo pierde `_last_window`, y con eso la protección contra reusar el TOTP.

### F-10 · NARANJA · `cli.py:709-710` · `rt2` interrumpida por una excepción pierde la retoma
`state-rt2.json` solo se escribe cuando `run_rt2` termina. Con Ctrl-C durante la espera del presentador, la siguiente corrida empieza en `celdas` y reenvía el lote. El archivo sí pasa por el filtro y no guarda tokens (lo prueba `test_demo_evidence_…state_files…`).

### AMARILLO
- La prueba de mundo cerrado no ve el orden de los pasos ni nombres fuera de las convenciones (el Job renombrado de mis mutaciones).
- Detector de verbos: una línea añadida cuyo contenido empieza por `++` se lee como cabecera `+++` y se salta (`kubectl delete` pasa). En `Dockerfile`, `kubectl @x delete` se acepta (inofensivo). `k\ubectl` se acepta: es una evasión con intención, ya anotada en candidatas. El resto de las formas (`VAR=$(… delete)`, `watch`, `nohup`, bloque de código en Markdown, `python -c`, heredoc) siguen prohibidas (`verbs.log`).
- `scrub` borra `"name":"Cookie"` además del valor.
- La prueba estática no ve un `open(f, modo_variable)`.
- `test_scenarios_contract.py:95` sigue diciendo que «`cumplimiento-1` lee modelos».
- El README de `promocion` no dice que `rollback-pr` exige el `post-activation-pr` previo.

## Lo demás que pediste, verificado
- **`--help`**: las 14 secciones, `all` y la general dan 0, con 0 `connect`, 0 `Popen` y 0 archivos escritos. No se importan `playwright` ni `pyarrow`.
- **Barreras**: quitar `check_section`, quitar `check_decisions` o forzar el modo `tool` en `presenter`: las tres mutaciones hacen caer una prueba.
- **`Store`**: un secreto, una semilla en una URL `otpauth://` y un JWT quedan bloqueados, sin archivo ni temporal. Aparte de `store.py` no hay escrituras en `src/` (la de `k8s_read` es un `PIPE`).
- **Enmiendas**:
  - (a) La reparación del realm no existe y `test_oidc_headless.py` pasa contra Keycloak real.
  - (b) F-N1: el stderr del proceso, capturado en un archivo, quedó vacío (0 bytes). Quitando el `except` del manejador, la prueba cae con «Error occurred in event listener».
  - (c) F-N4: ver F-07.
  - (d) F-04: la prueba `decisions` pasa con el reloj falso.

## Tareas candidatas (defectos reales fuera de alcance)
- El filtro de evidencias no ve HAR dentro de cadenas JSON (anterior a esta tarea; ver F-07).
- Grafana sin OIDC (U1) sigue abierta.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/`:
- `check.log`
- `fn4.log`, `r2cases.log`, `embedded.log`, `embedded_base.log`, `big.log`
- `verbs.log`, `help.log`, `store.log`
- `fn1.err`, `fn1-mut.out`
- `pc-*.log`, `network-tests.log`, `trace-head.log`, `cov.json`

```
VEREDICTO: NO-VERDE
ROJO|demos/journey-7-3.md paso 6 y verify/journey-7-3.sh 4|La alerta no se apaga al revertir F22: el verify falla siempre
ROJO|demos/prs/proxy-staging/proxy.patch.tpl (y rt3-staging)|Las plantillas no aplican con el modelo de referencia ya promovido
ROJO|demos/journey-7-4.md pasos 3, 7 y 8|El cierre de D2 no es ejecutable (falta post-activation-pr y mark-active) y el verify 4 da OK sin serlo
ROJO|cli.py:850,856 (CA-16)|Dos pragma no cover nuevos; la bitácora dice que no hay ninguno
NARANJA|scenarios/demos.py:76|journey-7-3 lee FailClosedPersistente antes del for: 1m (≈ 14 % no ejecutado)
NARANJA|cli.py:640-650|rt3 --closing sin prueba; reescribe el registro de rt3
NARANJA|evidence.py:132-213|F-N4 no cubre HAR dentro de cadenas JSON; coste cuadrático
NARANJA|scenarios/rt2.py:418|PresenterReactivation since=started_at sin prueba; la mutación cuelga la suite
NARANJA|live.py|0 %, cita una prueba inexistente; fuga de backends en all
NARANJA|cli.py:709-710|rt2 pierde la retoma ante una excepción
INFORME: revisiones/U12-T04/ronda-1.md
```
