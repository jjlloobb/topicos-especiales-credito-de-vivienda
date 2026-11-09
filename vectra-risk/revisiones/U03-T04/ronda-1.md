# Ronda 1 — U03-T04

VEREDICTO: NO-VERDE

No hay ningún ROJO. Queda en pie un NARANJA (F-01). Con el ritmo RL de la demo (solo un ROJO bloquea), la decisión de fusionar es del orquestador. Yo no suavizo el veredicto: un NARANJA en pie significa NO-VERDE.

## Criterios de aceptación, verificados por mí (worktree en `4c1e94c`, limpio antes y después)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | CLI | `uv run pytest decision-registry/tests/integration/test_cli.py -v -rs` | pasa: 38 passed en 17,97 s, 0 omitidas. Faltan los casos de `checkpoint`, y la bitácora lo dice |
| 2 | Agregador | `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_aggregator.py decision-registry/tests/integration/test_aggregator.py -v -rs --hypothesis-show-statistics` | pasa: 23 passed en 148,5 s. PBT-U3-09 corrió 500 ejemplos, ninguno falló (103,9 s); el caso de 20 000 entradas tarda 11,3 s, así que el tiempo es real |
| 3 | Bóveda y chart | `uv run pytest decision-registry/tests/unit/test_vault_policies.py -v` y luego `helm template decision-registry decision-registry/chart \| conftest test --policy decision-registry/chart/policy -` | pasa: 15 passed y 174/174 en conftest, código 0. Los 0,06 s de la primera se explican porque solo parsea HCL; aparte, `test_cli.py` aplica las 5 políticas a un Vault real y prueba `sign` y `read` con cada token |
| 4a | `make -C decision-registry check` | el mismo | pasa, EXIT=0: ruff y mypy limpios, 534 passed en 568 s, conftest 174+5, Kyverno pass 8 / fail 0, conftest de U1 42+3 |
| 4b | `make -C platform check` | el mismo | **EXIT=2, por el entorno**: `check-tools` exige `platform/.tools/bin/k6` y `egctl`, y no están instalados en el worktree (tampoco en el checkout principal). El resto de `check-local` pasó: ruff, 784 passed, helm lint. Corrí a mano todos los pasos de `check-tools` menos el `test -x`: kyverno test 81/81, promtool, rego_fixtures, conftest prod 707/3/322, kyverno apply 45/0, actionlint y check-integration 309/0. Todo pasa. El diff no toca `platform/`. Ver F-04 |

Mutación hecha por mí en una copia del scratchpad (el worktree no se tocó): saqué el `UPDATE monitoring_watermark` de la transacción del lote. Resultado: `test_si_falla_el_avance_de_la_marca_tambien_se_deshacen_los_conteos` FAILED, 1 failed y 2 passed. La mutación muere.

## Checkpoint: el vacío de diseño es real
- BR-U3-08 (`business-rules.md:81-84`) ordena firmar `JCS({checkpoint_seq, checkpoint_hash, recorded_at})` en el paso 1 y agregar la entrada en el paso 2.
- El payload de domain-entities §2.1 (`domain-entities.md:67-76`) no lleva `recorded_at` propio. Así que el `recorded_at` es la columna de la entrada, y BR-U3-04, pasos 1 y 2, junto con BR-U3-05, la fijan dentro del lock del append, después de la firma.
- `verify.py:203` (de U03-T03) firma y comprueba con `body["recorded_at"]`, es decir, con el de la propia entrada.
- §2.2 y BR-U3-10 no cuentan otro orden.

Ningún texto resuelve qué `recorded_at` se firma. El codificador se detuvo bien. Las opciones A a D de `CANDIDATAS.md` son coherentes. Decide el usuario.

## Alcance: no hay desborde
- `archive.py`, `worm.py` y `vault.py` los necesita `archive --month` (subida, descarga y `verify --source archive`) y la comparación con el bucket WORM de `verify`. Los dos son Paso 11 dentro del alcance.
- Las políticas HCL de checkpoint y archive las pide la tarea («firma solo para checkpoint y archivo»). La de `registry-verify` solo da `read` de la llave pública, que es lo que usa `verify`.
- `chart/templates/` contiene solo `aggregator-cronjob.yaml` y `serviceaccounts.yaml`. No hay CronJobs diferidos ni `chart-rebuild/`, y no se tocan `reference-model/` ni `platform/`.

## Hallazgos
### F-01 · NARANJA · `chart/templates/aggregator-cronjob.yaml:22` y `chart/policy/aggregator.rego:73-77` · `backoffLimit: 0` contradice INF-U3-03
`infrastructure-design.md:49` dice: «Todos los CronJobs: `concurrencyPolicy: Forbid`, sidecar nativo …, `restartPolicy: Never`, `backoffLimit: 1`». La fila de `registry-aggregator` (línea 46) no lo cambia. El chart pone `backoffLimit: 0`, la regla rego **exige** 0 («deadline: backoffLimit es 0») y `test_chart.py:145` fija ese valor. No hay ninguna cita de diseño que lo respalde. El `backoffLimit: 0` del diseño es de los Jobs `registry-aggregator-rebuild/reset` (líneas 44-45), no del CronJob. Hay que pasarlo a 1 y ajustar la regla, o citar una revisión de diseño que lo cambie.

### F-02 · AMARILLO · `cli.py` (`main`, `cmd_archive`) · un fallo de archivo se reporta como `RegistryVerificationFailed`
Cuando falla la bóveda o el bucket durante `archive`, la salida es 2 con el evento `RegistryVerificationFailed` (`test_cli.py:329-335` lo afirma). Para el archivo, el diseño tiene `ArchiveExportFailed` (runbook `archive-export-failed`), que solo se emite en la verificación de vuelta. Las alertas son del Paso 14 (diferido), pero el nombre del evento ya queda fijado aquí.

### F-03 · AMARILLO · `aggregator.py:363` (`lag_seconds`) · duplica `queries.monitoring_lag`
Es la misma consulta y la misma regla de atraso que el gauge del servicio (`health.py:35`, `queries.py:194`), en una versión síncrona. Si alguna cambia, las dos divergen.

### F-04 · AMARILLO (entorno, no del diff) · CA-4b · faltan `k6` y `egctl` en `platform/.tools/bin`
Por eso `make -C platform check` sale con 2 en la puerta `test -x`. Lo sustantivo pasa (tabla de arriba). El codificador no corrió CA-4b y lo declaró. Para cerrar CA-4 de forma literal, el orquestador puede correr `platform/install-tools.sh` en el worktree.

### F-05 · AMARILLO · `bitacoras/U03-T04.md:39` · el rojo primero quedó registrado solo para una regla
El plan de pruebas pide una mutación por regla. La bitácora registra solo la de `sign` en la API y dice que el resto «lo vio la sesión interrumpida». Yo verifiqué la de la marca de agua (muere). Las de `verify` → 0 y `reset` con `registry_aggregator` siguen sin registro de rojo, aunque los casos existen y afirman el código y el estado.

### F-06 · AMARILLO · `chart/templates/aggregator-cronjob.yaml:17-19,37-39` · literales sin cita en la plantilla
`startingDeadlineSeconds: 60`, `successfulJobsHistoryLimit: 1`, `failedJobsHistoryLimit: 3` y `runAsUser/runAsGroup: 65532` están fijos en la plantilla, sin cita de diseño y fuera de `values.yaml`. No son visibles para el usuario, así que no llegan a NARANJA.

## Tareas candidatas (defectos reales fuera de alcance)
- Decisión de diseño sobre qué `recorded_at` firma el checkpoint (BR-U3-08 contra BR-U3-04/05). Ya está en `CANDIDATAS.md` y bloquea `checkpoint.py` y sus dos casos.
- Instalar `k6` y `egctl` en los worktrees de revisión, o hacer que `check-tools` diga qué binario falta.
- Las otras 8 candidatas del codificador en `CANDIDATAS.md` (`anchor_seq`, estado de `incremental`, `sslmode`, auth por SA, imagen, `check-chart` de U1, imagen MinIO, paquete `tests/property`) me parecen bien fundadas.

## Rutas de transcripciones largas
Todas están en el scratchpad `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/`:
- `make-check.log`
- `platform-check.log`
- `platform-tools-sin-k6.log`
- `ca1.log`
- `ca2.log`
- La copia mutada está en `mut/`.

```
VEREDICTO: NO-VERDE
NARANJA|decision-registry/chart/templates/aggregator-cronjob.yaml:22|backoffLimit 0 contradice INF-U3-03 (backoffLimit: 1 en todos los CronJobs)
INFORME: revisiones/U03-T04/ronda-1.md
```
