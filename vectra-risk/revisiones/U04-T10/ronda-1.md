VEREDICTO: VERDE

# Ronda 1 — U04-T10

El revisor corrió los seis criterios de aceptación y los seis pasan. `make -C governance check` dio rc 0 al primer intento: los 6 errores de integración que vio el codificador no se repitieron. Ninguna mutación sobrevivió. No hay hallazgos ROJO ni NARANJA; quedan dos AMARILLO que no bloquean.

## Criterios de aceptación, verificados por el revisor (ejecutados, en el worktree en b0a75b2)

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | El `datasetRef` de kind renderizado es un objeto que el lector acepta | `uv run pytest governance/tests -q -p no:cacheprovider -k "dataset"` | pasa: 12 passed, 599 deselected (10 de `test_dataset_ref.py` y 2 de `test_service_config.py`) |
| 2 | `release.md` sube a la misma ruta que lee U4 | `... -k "release_doc or dataset"` | pasa: 12 passed |
| 3 | Un bucket solo no se despliega | el comando de la tarea, y además `helm template` con los valueFiles reales de kind, staging y prod | rc=1 en los tres entornos con `validation.datasetRef debe ser un objeto s3://<bucket>/<clave> y no un bucket ni otro esquema: "s3://validation-datasets"`. Con los values normales los tres renderizan con rc 0 y `GOVERNANCE_VALIDATION_DATASET="s3://validation-datasets/validation.parquet"` |
| 4 | La guía añade claves y no dice «crea» | el comando de la tarea | pasa: el primer grep no encuentra nada; `keycloak.issuer` aparece en las líneas 52 y 61 |
| 5 | El doble niega los buckets que no están en la política | `uv run pytest governance/tests/unit -q -p no:cacheprovider -k "validation" -rs` | pasa: 79 passed en 55 s, 0 skipped |
| 6 | governance en verde y enlaces | `make -C governance check` (una vez, 5m12s) y `uv run python platform/tests/test_links.py` | pasa: rc 0. ruff; mypy «38 source files»; import-linter «2 kept, 0 broken»; coverage **611 passed, 0 errors, 97,26 %** (umbral 95); `model_fsm`, `policy` y `evidence` al 100 %; policy-chart con 1027 y 10 pruebas; policy-chart-u1 en kind, staging y prod con Kyverno `pass: 19, fail: 0` y conftest 91/91 y 3/3; policy-runbook `pass: 8, fail: 0`; trazabilidad «34 identificadores». test_links: 599 archivos sin enlaces rotos, rc 0 |

**CA-6, fallo de entorno o causado por el cambio.** Con la máquina en la misma carga, la corrida de `check` del revisor no dio ningún error en `test_service_build_app.py` y la cobertura llegó al 97,26 %. El cambio no los causa: el 94,86 % del codificador se debía solo a esas 6 pruebas caídas. Los tres pasos de política que no le corrieron a él sí corrieron y pasaron.

**Incidente con el registro.** El scratchpad se comparte entre agentes y dos escribieron un `check.log` con el mismo nombre; las primeras ~80 líneas quedaron mezcladas. Lo posterior es concluyente (make se detiene en el primer fallo y corrieron la trazabilidad y «Leaving directory» de u04-t10 sin ninguna línea `***`). Para asegurarlo, el revisor repitió `make -C governance lint rules shellcheck policy-chart policy-chart-u1 policy-runbook` en un registro con nombre propio: rc=0, mismos resultados.

**Diseño (solo leído).** El dataset único está respaldado: U5 `functional-design/domain-entities.md:31` (un solo dataset `validation` de 18 000 filas, «Parquet en el bucket `validation-datasets`»); U5 `business-logic-model.md:29`; U4 `business-rules.md:134` (BR-U4-05: `source_comparison` «puntúa el mismo dataset»); U4 `domain-entities.md:64` (`dataset_ref`, sin nada que pida un dataset por versión).

**Barrido del repositorio (ejecutado).** En todo `vectra-risk/`, las cadenas `validation-datasets`, `validation.parquet`, `datasetRef` y `GOVERNANCE_VALIDATION_DATASET`: ningún archivo de values de kind, staging o prod sobrescribe `datasetRef`; `release.md:70` y `:105` usan la ruta nueva; la única ruta discrepante está en pruebas de integración (F-01); `test_validation_job.py:465` usa una ruta de ejemplo genérica para el lector S3, correcto.

**Guía frente a gitops (ejecutado).** En una copia, con los dos digests añadidos a `values/kind/governance.yaml` y regenerado: `generate.py` y `generate.py --check` en rc 0; el diff trae solo `values/kind/governance.yaml` con 5 líneas `+` y ninguna `-`; `apps/kind` no cambia; `helm template` saca las imágenes con los dos digests, `VECTRA_OIDC_ISSUER` público y el `datasetRef` nuevo. Es el «Esperado» de la guía.

**Mutaciones (en una copia, nunca en el worktree).** Todas detectadas:

| Mutación | Pruebas que fallan |
|---|---|
| M1: quitar la comprobación de grants en `MemoryStore` | 2 (las dos negativas, «DID NOT RAISE») |
| M2: `JOB_READ_BUCKETS` sin `model-store` | 1 (`object_unreadable`) |
| M3: `JOB_READ_BUCKETS` con `loki` de más | 1 |
| M4: `service.yaml` vuelve a `.Values.validation.datasetRef` sin el helper | 4 |
| M5: `release.md` con `${MV}` | 1 |
| M6: `values.yaml` vuelve al bucket solo | 3 |
| M7: override de `datasetRef` en `values/kind` | 3 |

**Alcance (ejecutado).** El diff no toca `platform/`. De `reference-model/` solo cambia `docs/release.md`. En `paso-20-kind.md` solo cambia el párrafo «PR de digests», su bloque de comandos y el «Esperado». `git status --short` limpio al terminar.

## Hallazgos

### F-01 · AMARILLO · `governance/tests/integration/test_container_start.py:136` y `test_service_build_app.py:125` · Los fixtures siguen con el bucket solo
Las dos pruebas fijan `"GOVERNANCE_VALIDATION_DATASET": "s3://validation-datasets"`, el valor que la tarea declara inválido. Pasan porque el servicio no valida ese valor (solo lo valida el chart). Conviene pasarlos a `s3://validation-datasets/validation.parquet`.

### F-02 · AMARILLO · tarea, CA-3 · El comando del criterio no carga los values de kind
El `sed` busca `- $values/vectra-risk/`, pero la Application dice `- /vectra-risk/...`, así que no imprime nada y el comando renderiza solo con los values del chart. Da rc=1 de todos modos, y la prueba `test_a_dataset_ref_without_an_object_is_not_deployed` sí usa los valueFiles reales. Es un defecto de la especificación (del orquestador), no del codificador.

### Observación (sin severidad)
`policy-chart-u1` y `policy-runbook` escriben en `platform/.tools/integration/u4*`. En este worktree `platform/.tools` es un enlace al árbol principal: dos revisiones de governance en paralelo se pisarían.

## Tareas candidatas (defectos reales fuera de alcance)
- U4 `test_service_build_app.py`: Testcontainers crea el bucket antes de que MinIO esté listo (`XMinioServerNotInitialized` con la máquina cargada; lo vio el codificador, el revisor no lo reprodujo). Falta esperar y reintentar.
- U4 `aidlc-docs/construction/governance/functional-design/domain-entities.md:64` dice «Dataset de validación del model-store», pero el dataset vive en `validation-datasets`.
- U4: el servicio no valida `GOVERNANCE_VALIDATION_DATASET` al arrancar (`service.py:120`); solo lo protege el chart.
- Bucle: el scratchpad lo comparten agentes en paralelo; los archivos deben llevar el prefijo de la tarea.

```
VEREDICTO: VERDE
AMARILLO|governance/tests/integration/test_container_start.py:136, test_service_build_app.py:125|Fixtures de integración con datasetRef de solo bucket
AMARILLO|tarea CA-3|El sed del comando no carga los values de kind
INFORME: revisiones/U04-T10/ronda-1.md
```
