# Ronda 1 — U04-T04

VEREDICTO: VERDE

Bajo RL-1..RL-5 (`demo-kind-alcance.md` §6), solo un ROJO bloquea. No hay ningún ROJO. Los dos NARANJA (F-01, F-02) y los AMARILLO pasan a ser candidatas.
Revisado: `git diff origin/main...tarea/U04-T04` (merge-base `453719f`, punta `c2881fa`), 17 archivos, +2967/-38.

## Criterios de aceptación, verificados por mí (ejecuciones nuevas, desde `vectra-risk/`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `create_app` con las 21 rutas; 403 por scope | `uv run pytest governance/tests/integration/test_api_app.py -v` (dentro de CA-2) | pasa: 24 pruebas. Rutas == `REGISTRY["governance-service"]`. Los 7 `RouteContract` con scopes (los conté en el registro) dan 403. Además, 403 por rol en las 14 restantes, y 401 sin token |
| 2 | Aceptación del Paso 10, sin la línea diferida | `uv run pytest governance/tests/integration/test_api_*.py -v -p no:cacheprovider` | pasa: **81 passed en 19.76 s, 0 omitidas** (Testcontainers real; el tiempo es coherente). Leen el estado de vuelta con SQL y la cadena del doble del registro. RT-3 a/c/d dan 422 sin filas ni cadena; b da 200 y queda `registrado`. `feature-spec` == `feature_spec.json` byte a byte. 304 con `If-None-Match`. Manifiesto del Job leído del doble: `vectra-staging`, 86400/7200/0 |
| 3 | El contrato no cambia | `make -C contracts openapi && git diff --exit-code contracts/openapi/` | pasa: rc=0, sin diff |
| 4 | `api-summary.md` y trazabilidad `--section api` | `test -s …/api-summary.md && uv run python platform/tests/test_traceability.py --unit governance --section api` | pasa: rc=0, «34 identificadores con trazabilidad». Grep: BR-U4-03/05/07/08/12/13/15 están en `test_api_*`; BR-U4-16/17 están en otras pruebas de governance |
| 5a | `make -C governance check` | igual | pasa: rc=0. ruff y mypy limpios. import-linter: 2 contratos cumplidos. **258 passed en 135.8 s**. promtool se omite por el Makefile |
| 5a' | promtool aparte | `promtool test rules governance/observability/tests/*.yaml`, con el binario del checkout principal (v3.15.1 == `PROMETHEUS_VERSION` de `tools.env`) | pasa: SUCCESS |
| 5b | `make -C platform check` | igual, y después el plan B de la tarea | pasa por el plan B que prevé la tarea: `test_links` dice «351 archivos sin enlaces rotos» y después `check-tools` falla (Makefile:42) porque `platform/.tools` no existe en el worktree; con `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib` salen **274 passed** |
| — | Regla «sin fallos nuevos» de `--all` | `test_traceability.py --all` en la punta y en un `git archive` del merge-base | rc=1 en ambos. La punta no tiene fallos nuevos: desaparece `INF-U4-05: sin trazabilidad`. Las otras diferencias del archivo base vienen de archivos fuera de `vectra-risk/`, no de este diff |

## Punto a juzgar: estados HTTP 200/204 del contrato frente a 201/200 del texto
**Dictamen: el codificador tiene razón. No es un hallazgo contra el código.**
- Revisé el OpenAPI de U0 (`contracts/openapi/governance-service.yaml`) leyendo las respuestas de cada ruta. `POST /v1/models` solo declara `200`. `approval`, `activation`, `freeze`, `frozen-resolution`, `decision`, `validation-report`, `source-counts` y `policies/{id}/approval` declaran `204`. El codegen (`contracts/tools/codegen.py:86`) solo emite 200/204 y los alternos que declara el `RouteContract`; no existe forma de declarar 201.
- La tarea prohíbe cambiar U0, y CA-3 exige el contrato sin diff. Responder 201 o 200 con cuerpo violaría el contrato que consumen el BFF y U9.
- El plan ya aplica el mismo criterio en otra viñeta del Paso 10: «`bias-monitoring-job` → 204 (el contrato no tiene cuerpo de respuesta)». El «→ 200» de la aprobación y el «(b) → 201» de la tarea son imprecisiones del texto, no requisitos.
- Severidad: **AMARILLO sobre la especificación**, no sobre el diff. Candidata: corregir en el plan y en la tarea «`cro` aprueba → 200» por 204 y «(b) → 201» por 200. La decisión quedó registrada en la bitácora, en el docstring de `api.py` y en `api-summary.md:68`.

## Hallazgos
### F-01 · NARANJA · `evidence.py` `fit_freeze_package` (último paso) y `fit_report` (tercer paso) · Reglas de reducción inventadas que se apartan del diseño
- **`fit_freeze_package`.** BR-U4-15 define dos pasos: más de 60 KiB, agregadas; más de 64 KiB, ids. El diseño afirma que con eso «el evento cabe siempre». El código agrega un tercer paso que no está en el diseño: cambia `before` y `last_7_days` por `"sin_datos"`, vacía `implicated` y marca `truncated`. Eso borra del evento de auditoría las mediciones que justifican el congelamiento. Además contradice U9 BR-U9-15 (`bias-monitoring/functional-design/business-rules.md:116`), que exige conservar «siempre las agregadas, las bandas y el atributo disparador».
- **`fit_report`.** El tercer paso borra las `bands` de `pre` y `post`. BR-U4-13 dice «sin las celdas», y U9 (línea 131) exige conservar «siempre las agregadas, las bandas y `delta`».
- **Sin prueba.** Ninguna prueba ejercita estas ramas: grep de `sin_datos` y `truncated` en `test_api_freeze.py` sin resultados.
- **Qué corresponde.** Si el diseño tiene una brecha (el caso de que el evento siga superando 64 KiB), hay que escalarla, no resolverla con una regla propia. No rompe ningún CA. Candidata.

### F-02 · NARANJA · `api.py:238,260,265,387,522` · `reason_code` visibles al usuario incrustados como literales
`manifest_not_found`, `source_unknown`, `source_not_approved`, `justification_required` y `attributes_must_be_the_four_without_repeat` son literales en los puntos de decisión, sin un catálogo. Es la misma clase que la candidata ya abierta de U04-T03 («literales de `evidence.py`»), y los motivos internos de `ConflictState` en `evidence.py` también entran en ella. Hay precedente en el repositorio (`decision-registry/append.py`). Candidata: agruparla con la de U04-T03.

### F-03 · AMARILLO · `k8s_jobs.py` `job_manifest` y `api.py` `ApiConfig` · valores de despliegue en el código
`priorityClassName: "vectra-low"`, los recursos `250m/512Mi/1/1Gi` y el `callback_url` por defecto (`http://governance-service.vectra-app.svc:8080`) son literales. Deberían venir del chart o de INF-U4-01 (Pasos 13 y 16). No son visibles al usuario.

### F-04 · AMARILLO · `evidence.py` `propose_source` · el evento `propuesta` no se emite
La decisión está razonada en la bitácora (una transición produce un evento). El diseño enumera `propuesta`; hay que decidir si se quita de allí. Es la misma candidata (4) del codificador.

## Tareas candidatas (defectos reales fuera de alcance)
- Corregir en el plan (Paso 10) y en la tarea los estados: aprobación 204, registro 200 (punto a juzgar).
- F-01: escalar al diseño qué pasa si el evento `freeze` o el `PrePostReport` siguen superando el límite tras los pasos del diseño; quitar o alinear las ramas inventadas y probarlas.
- F-02: catálogo de `reason_code` y motivos de 409 de governance, junto con la candidata de literales de U04-T03.
- Las del codificador: cliente S3 real de F47 y `build_app` por entorno (Paso 16); RBAC `get inferenceservices` en `vectra-staging` para K01; bytes crudos de `feature_spec.json` para paquetes no canónicos; evento `propuesta`.

## Alcance y estado del worktree
- Desborde: ninguno. El plan solo cambia las dos casillas indicadas. No se toca U0, U1, U3, U5 ni U9 (`git diff --stat`).
- Worktree limpio después de mis ejecuciones (`git status --short` vacío). Este informe es el único archivo nuevo y no tiene commit.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ca2.txt (CA-2, `-v`)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ca5gov.txt (`make -C governance check`)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/trace_head.txt y trace_base.txt (`--all`)
