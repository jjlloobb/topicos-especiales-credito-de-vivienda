# Ronda 1 — U12-T03

VEREDICTO: NO-VERDE

Hay dos ROJO, y los dos son oráculos que dan un resultado falso frente al código real de `origin/main` (7ec1478). Por F-01, RT-3 da `falla` en kind justo cuando el sistema está produciendo la evidencia esperada. Por F-02, la fase «sigue congelada tras 3 corridas más» de RT-2 da `pasa` cuando solo hubo 2 corridas más. Las dos fallas nacen del texto de la tarea (línea 256 para F-01, P-5 y línea 289 para F-02), así que conviene corregir también la especificación. El codificador cumplió los CA. Todo lo demás está verde.

Tarea: blob `fdd6a20387f44d0633e21b8020474d19b0ffbb27`, el hash coincide. Al terminar: HEAD en 151a20b, `git status --short` vacío. No queda ningún contenedor mío: el Prometheus de mi sonda se borró al salir, Ryuk terminó solo y los `postgres` detenidos de antes son ajenos.

## Oráculo frente al sistema real (`origin/main`)

| Oráculo | Lo que lee | Dónde lo produce el sistema | ¿Coincide? |
|---|---|---|---|
| RT-5 | log `rt5-demo: POST <url> -> <código> l5d-proxy-error: <valor>`, `None` sin cabecera; sale con 0 ante cualquier 403 y con 2 si no hay respuesta | `case-management/chart/templates/rt5-demo-job.yaml` (args) | sí; CA-6 ejecuta el guion real |
| RT-5 | `ALERTS{alertname="CoreWriteAttempt",alertstate="firing"}` en [t0, t1+15 min] | `prometheusrule.yaml`: sin `for:`, con `offset 5m` | sí. Evalué la expresión real en Prometheus real con la serie que nace en 1: es >0 durante 285 s desde el nacimiento, dentro de la ventana |
| RT-5 | `sum(inbound_http_authz_deny_total{namespace="vectra-mock",route_name="core-mock-catch-all"})`, máximo ≥ 1; ausente frente a <1 | PodMonitor `linkerd-proxy` (`monitors.yaml:42-52`, `keep inbound_http_authz_.+`; `namespace` lo pone el pod) | sí; distingue ausente, <1 y >0 (ver F-08) |
| RT-5 | `sum(vectra_core_write_attempts_total)` en [started_at, ahora]; ausente = `falla` | `core_banking_mock/metrics.py` (nace en 0) y ServiceMonitor del mock (`servicemonitors.yaml`) | sí |
| RT-5 | `prometheus_tsdb_lowest_timestamp_seconds` ≤ t0 | autoraspado de Prometheus | sí |
| RT-3 | 422 `validation_error` + `invalid_params[name=package]` con los 3 `reason_code` | governance y BFF reales (CA-16 en la cadena real, verde) | sí |
| RT-3 | `CaseDetail.state`, `attempts`, `last_cause`; enumerados | `contracts/.../models/api.py:110-112`, `catalog.py` | los campos sí. **La semántica de `attempts` no** (F-01) |
| RT-3 | «cero `recommendation`» por `metrics` | `projections.py` (`FIELDS["metrics"]["recommendation"]` lleva `model_version_id`) | sí |
| RT-2 | rutas de modelos del BFF, roles y MFA | `console-bff.yaml` y la matriz (CA-15, CA-16 reales) | sí |
| RT-2 | `monitoring_freezes`: `freeze_id`/`action`, `recorded_at`, `context_package` | `projections.py:_freezes`; governance `_freeze_package` y `fit_freeze_package` (`data_sources` y `initial_disparity`; un recorte deja las claves) | sí |
| RT-2 | 3 corridas de bias posteriores al `recorded_at` del `freeze` | U9 `run.py:308-317`: `_freeze_all` **antes** de `finished_at` | **no** (F-02) |
| RT-2 | latencia = `recorded_at` del `freeze` − menor `recorded_at` del lote | las dos marcas son del reloj de U3 | sí; la estación solo filtra `recorded_from` |
| RT-2 | reactivar (204) → `activo` + `frozen_resolution reactivar`; no se recongela | `model_fsm`; U9 `window.last_reactivation` | sí. `Reactivator` es separable (prueba `Waiting`, sin tocar los oráculos) |
| SIM-NORMAL | `RunReport` + `get_case`; `en_evaluacion` al plazo (600 s) = `falla` | U8 y BFF | sí (P-7 a) |

## Criterios de aceptación, verificados por mí

| # | Comando | Resultado |
|---|---|---|
| 22, 1, 18 | `make -C system-verification check` (`uptime` 2.11 → 1.82) | pasa: lint, mypy, `Contracts: 7 kept`, 667 pasan en 625 s (semilla 1999435281), cobertura 95.19 %; 566 pasan en 271 s (semilla 1384385938) con `report` y `sampler` al 100 %; 15 min 05 s. `scenarios/`: 96–100 % por archivo |
| 7, 9, 15, 16 | dentro del `check`: `test_rt5_promql` 7, `test_rt2_cells_real_u5` 5, `test_scenarios_contract` 12, `test_rt3_real_chain` 7 | pasan, sin omitidas |
| 2 | verbos y guard (153), `-k guard` (8), `grep` `limpio=0`; el `--stat` del detector, vacío | pasa |
| 3, 5, 6, 13 | outcome 18; `rt5 and missing` 9; job_script 5 (guion real); filtro 60 + `evidence or leak` 7 | pasan |
| 17 | pruebas unitarias de la tarea | 209 en 36 s reales |
| 19, 24, 25 | `--unit --all`: solo INF-U12-04, 05 y NFR-U12-31; `uv lock --check` en 0; diff fuera de alcance `fuera=1`; `uv.lock`, `pyproject` y `Makefile` sin cambios; 564 Markdown sin enlaces rotos | pasan |
| 20, 21 | las dos filas fechadas sin borrar el texto; plan con solo las 6 casillas | pasan |
| 4, 10, 11, 12, 14 | dentro del `check` (verde) | **pasan como prueba, pero F-01 y F-02 muestran que lo que fijan no es el sistema real** |

## Hallazgos

### F-01 · ROJO · `scenarios/rt3.py:383` (y `:226-238`; `_rt3b` usa el mismo `cases`) · F22 deja de esperar con `attempts ≥ 1` y U8 pone `attempts` al **tomar** el trabajo
U8 escribe `cases.attempts = n` al tomar el trabajo (`case-management/src/vectra_case/job_queue.py:4,80`). El caso sigue en `en_evaluacion` mientras la llamada a scoring está en vuelo (`SCORING_TIMEOUT = 7 s`; el worker sondea cada 0,4 s). `settled()` termina en cuanto todos tienen `attempts ≥ 1`, y entonces `judge_f22` da `falla`:
- con todos en vuelo: `rt3_f22_sin_causa_timeout_o_explainer_unavailable`;
- con uno solo en vuelo: `rt3_f22_caso_sin_estado_final`.

Lo reproduje con el `Rt3Run.cases` real y un BFF que se comporta como U8 (`race.log`): una sola lectura a los 0 s, los 5 en `en_evaluacion/attempts=1`, resultado `falla`. Siete segundos después habrían estado en `en_sincronizacion/timeout`.

La prueba `test_rt3_f22_with_a_state_outside_the_failclosed_or_cases_still_evaluating_fails` fija este comportamiento. El doble (`rt2_world.case_state`) nunca devuelve `en_evaluacion` con intentos. Arreglo sugerido: esperar a `state != en_evaluacion` y, al plazo, el código que ya existe.

### F-02 · ROJO · `scenarios/rt2.py:138-147, 673-688` · «3 corridas más de bias» cuenta la corrida que congeló
En U9 el `freeze` se escribe dentro de la corrida y `finished_at` se fija después (`bias-monitoring/src/vectra_bias/run.py:308-317`). En governance, `send` es síncrono dentro de `freeze`. Por eso el `vectra_bias_last_run_timestamp` de la corrida que congeló es posterior al `recorded_at` del `freeze`, y `count_bias_runs(ts, ok, recorded)` la cuenta. Con la que congeló más 2, devuelve 3 (`edge.log`, caso 10), y la fase da `pasa` unos 15 min antes de lo debido. El doble no lo modela: congela con un temporizador independiente de las corridas. Arreglo sugerido: tomar como referencia la primera marca ≥ `recorded_at` y contar las estrictamente posteriores. Pasa algo parecido, de forma menor, en `no_recongela` con una corrida en vuelo durante la reactivación.

### F-03 · NARANJA · `scenarios/rt5.py:300-308` · `ranged` pide `start > end` en la costura
Si lo que sobra tras un tramo es menor que `step`, el siguiente `cursor` pasa de `end`. En Prometheus real eso es `query_failed:http_400:bad_data`, y el resultado sale `no ejecutado` con un código falso, `rt5_prometheus_no_responde` (`promreal.log`; `seams.log`: extra=7 s → error). Afecta a la ventana del contador si pasan más de 41,7 h. Con dos tramos, en Prometheus real no se pierde ni se duplica ningún punto (13 449 únicos, sin huecos). Mi mutación «saltar un punto en la costura» sobrevive a las unitarias.

### F-04 · NARANJA · `scenarios/rt2.py:848-862` · `RT2-LATENCY` sale `no ejecutado` cuando no llega `freeze` al tope de 2 700 s
El sistema respondió y no detectó en más de 1 800 s, así que debería ser `falla` (la prueba de la línea 757 fija `no ejecutado`). El resultado del elemento es falso, aunque RT-2 sí sale `falla`.

### F-05 · NARANJA · `rt2.py:920-926`, `rt3.py:495-562` · un `port-forward` caído escapa como excepción
`RegistryClient._page` llama a `forward.check()` y lanza `K8sError` (`pf.log`). `run_rt2` captura solo `ApiError` y `ObsError`; `rt3` solo `ApiError`. Lo mismo pasa con `OidcError`. La sección se rompe sin `no ejecutado` ni código y pierde los sub-resultados. Si no se le pasa un `Rt2State`, también pierde la retoma.

### F-06 · AMARILLO · `rt2.py:176-180`, `rt3.py:124-141, 296-303`, `sim_normal.py:139-150` · 401 y 429 se cuentan como `falla`
Son prerrequisitos (sesión o límite de peticiones), no un incumplimiento. El riesgo es bajo porque las sesiones se renuevan solas (`oidc.py:348-366`).

### F-07 · AMARILLO · mutaciones que sobreviven
- Huecos de prueba:
  - `rt3.py:284`: un 403 de RT3-b tratado como `no ejecutado` no lo detecta nadie;
  - `rt2.py:651`: un caso nuevo en un estado que no es `listo` ni `modelo_congelado` no tiene prueba;
  - `rt5.py:190`: comparar la retención con t1 en vez de t0 no lo detecta nadie;
  - la costura de F-03.
- Equivalentes en el sistema real: `rt3.py:172` (la activa ya entra en `changed`), `rt3.py:233` (U8 solo expone `last_cause` en fail-closed), `rt2.py:575` (filtra `recorded_from` en el servidor) y `rt2.py:755` (lo cubre la comprobación de estado posterior).

### F-08 · AMARILLO · `rt5.py:209-215` (literal del plan) · «máximo ≥ 1» no distingue un contador que quedó en ≥ 1 de un ensayo anterior
Pasa si el proxy no se reinició entre ensayos. El log y la alerta, que mide el aumento, lo cubren.

### F-09 · AMARILLO · `outcome.py:65-73` · `combine` no exige que estén presentes los obligatorios
Sin RT3-c en la lista da `pasa` (`edge.log`, caso 7). Hoy `rt3()` no llega a ese caso.

### F-10 · AMARILLO · `code/scenarios.md:111` · dice que RT-5 tiene sub-resultados `no ejecutado`
RT-5 no tiene sub-resultados.

### Regla P-2 (a), comprobada (`edge.log`)
- Los tres 422 y F22 bien, con RT3-b y los dos «desplegados» en `no ejecutado` → `pasa`.
- RT3-b en `falla`, o un «desplegado» en `falla` → `falla`.
- RT3-c en `falla` → `falla`.
- F22 en `no ejecutado` → `no ejecutado`. Está definido; lo prueba `test_rt3_the_registry_not_responding_is_no_ejecutado…`.
- F22 en `no ejecutado` y RT3-b en `falla` → `falla`.

### Mutaciones (29; registro en `mut.log`)
- `rt5`: 5 mueren y 2 sobreviven.
- `rt3`: 4 mueren y 3 sobreviven.
- `rt2`: 7 mueren y 3 sobreviven. Mueren, entre otras: medir desde la última `recommendation`, aceptar otra versión, la frontera 30/29, el `freeze` de otra versión y una corrida con `ok = 0`.
- `sim_normal`: mueren las 5 (`accepted <= sent`, `en_evaluacion` aceptado, causa fuera del catálogo, 5xx como `falla`, menos `case_id` que aceptadas).

## Tareas candidatas (fuera de alcance)
- Texto de la tarea: la línea 256 («`attempts ≥ 1`») y P-5 («posteriores al `recorded_at`») inducen F-01 y F-02. Hay que corregir la especificación, no solo el código.
- RT-5: anclar la serie de denegaciones a su valor antes de t0 (F-08).

## Rutas de transcripciones largas
Todos los logs están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev1/`:
- `check.log`: `make check` completo;
- `race.log`: F-01;
- `edge.log`: P-2 y F-02;
- `seams.log` y `promreal.log`: F-03 y la regla real;
- `pf.log`: F-05;
- `mut.log`: mutaciones;
- `ca_small.log`: CA-2, 3, 5, 6 y 13;
- `misc.log`: lock, enlaces y trazabilidad.

```
VEREDICTO: NO-VERDE
ROJO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt3.py:383|F22 deja de esperar con attempts>=1, que U8 pone al tomar el trabajo: falla falsa
ROJO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:138-147|«3 corridas más de bias» cuenta la corrida que congeló: pasa tras 2
NARANJA|vectra-risk/system-verification/src/vectra_verification/scenarios/rt5.py:300-308|ranged pide start>end en la costura: bad_data y no ejecutado falso
NARANJA|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:848-862|RT2-LATENCY no ejecutado sin freeze al tope de 2700 s
NARANJA|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:920-926|K8sError/OidcError escapan de rt2 y rt3 sin no ejecutado
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:176-180|401 y 429 cuentan como falla
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt3.py:284|mutaciones que sobreviven: 403 de RT3-b, estado de los casos nuevos, retención contra t1
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt5.py:209-215|máximo >= 1 no distingue un contador que quedó de un ensayo anterior
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/outcome.py:65-73|combine no exige que estén presentes los obligatorios
AMARILLO|vectra-risk/aidlc-docs/construction/system-verification/code/scenarios.md:111|RT-5 no tiene sub-resultados
INFORME: revisiones/U12-T03/ronda-1.md
```
