# U04-T01 — Esqueleto y migraciones de `governance`

**Unidad:** U4 `governance`
**Historias que implementa:** US-305 (sin reactivación automática), en su parte de datos. Prepara los datos de US-306 (participa), que la demo difiere en el servicio.
**Depende de:** U0 y U1 en `main`. Esta tarea es código estático y pruebas con Testcontainers, así que no necesita U2, U3, U5, U6 ni U9 en kind (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6).
**Rama:** `tarea/U04-T01`, creada desde `origin/main` (`0a5c990`, con U03-T04 ya fusionado). Corre en paralelo con U03-T05 y U09-T01.

Bloques A y B del plan de U4 (Pasos 1 y 2), fusionados en una sola tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 («A+B · C · D (8–11) · …», P-2). Los dos pasos entran **completos** (E): el alcance los marca E (§3, U4) y la enmienda dice «1–7 · E · Completos. La migración 2 se queda entera (el `freeze` y el registro leen `data_sources`)» (§3, U4). Rige el ritmo RL-1 a RL-5: una tarea por bloque fusionado, máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 1 y 2 del plan. Texto del plan, sin recortes:

- [ ] **Paso 1 — Esqueleto de `governance/`**
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con extras separados: el servicio **sin** librerías de inferencia y `validation_job` con ONNX Runtime, `xgboost` y `lightgbm`.
  - `validation_job` depende además de `vectra_disparity` (librería de U9, ruta del workspace; doble mientras no exista) para la disparidad inicial y el modo `source_comparison` (tercera revisión del FD de U9, 2026-10-10).
  - Contrato de import-linter: `model_fsm`, `policy`, `serving_config` y `registration` sin E/S; ningún módulo del servicio importa librerías de inferencia.
  - Diseño: NFR-U4-24.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config governance/.importlinter && make -C governance check` sobre el esqueleto.

- [ ] **Paso 2 — Migraciones de `governance-db`**
  - Tablas de domain-entities §1–§5 (incluidos `archived_uri` y `archived_at`); índice único parcial «una sola versión `activo` o `congelado`»; una sola política `activa`; tabla única `transitions` para modelo, política y fuente, con `entity_type` y `entity_id`, e índice único parcial `(entity_type, entity_id, transition_number) WHERE status <> 'abandonada'` (precisado el 2026-10-06, revisión del FD de U8); columnas `unit_id`, `kind` (`cambio_estado` \| `compensacion`) y estado `descartada` (precisado el 2026-10-06, revisión del FD de U8).
  - Triggers `guard_unfreeze` y `guard_freeze` (P-U4-06).
  - `validation_runs.mode` (`validacion` por omisión en las filas existentes), `source_id`, `baseline_version_id`; `model_versions.source_candidate_for`; `data_sources.pre_post_report` (segunda revisión del FD de U9, 2026-10-08).
  - `NOTIFY serving_config` al confirmar.
  - Grants de `gov_app`, `gov_migrator` y `gov_archiver` (permiso por columna); los roles los crea U1 (cuarta revisión de coherencia entre unidades, 2026-10-31); sin `DELETE` en tablas de historia.
  - Diseño: BR-U4-02, 03; NFR-U4-30; P-U4-01, 06; INF-U4-03. Historia: US-305.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_migrations.py` (Testcontainers):
    - una transición `descartada` con `n = 5` → otra inserción con `n = 5` en la misma entidad viola el índice (el `n` sigue reservado); una `abandonada` con `n = 5` → se puede insertar otra con `n = 5` (precisado el 2026-10-06, revisión del FD de U8);
    - un `UPDATE` directo `congelado → activo` → excepción; con la variable fijada pero sin transición de cumplimiento → excepción; con la variable apuntando a una `frozen_resolution` confirmada de **otra** versión, o a una fila de `transitions` de política o de fuente → excepción (precisado el 2026-10-06, revisión del FD de U8);
    - dos versiones `activo` → violación del índice;
    - la migración de `validation_runs` deja `mode = validacion` en las filas existentes; `mode = source_comparison` sin `source_id` → violación del `CHECK` (segunda revisión del FD de U9, 2026-10-08);
    - `gov_archiver` no puede cambiar `state`;
    - ningún rol tiene `DELETE` sobre `model_versions`, `policies`, `data_sources` ni `transitions`;
    - una transición de política y una de fuente con el mismo `entity_id` textual y el mismo `n` → llaves distintas; dos pendientes de la misma política con el mismo `n` → violación del índice.

Precisiones:

- **Estructura de §1, entera.** Crea todos los directorios y archivos del árbol de §1 del plan, sin omitir ninguno:
  - `governance/Makefile`, `governance/pyproject.toml`, `governance/.importlinter` y `governance/alembic.ini`.
  - `governance/src/vectra_governance/` con `__init__.py` y los diez módulos del árbol, vacíos salvo un docstring: `model_fsm.py`, `policy.py`, `serving_config.py`, `registration.py` (los puros), `evidence.py`, `background.py`, `convergence.py`, `pools.py`, `api.py` y `k8s_jobs.py`. Import-linter necesita que existan para contratarlos.
  - `governance/migrations/` (Alembic: tablas, índices parciales, triggers, grants y `NOTIFY`).
  - `governance/promotion_tool/`, `governance/validation_job/`, `governance/archive_job/` y `governance/ci/`.
  - `governance/chart/`, `governance/observability/`, `governance/runbooks/` y `governance/docs/`.
  - `governance/tests/unit/`, `tests/property/`, `tests/integration/`, `tests/examples/` y `tests/load/`. **`tests/load/` va aunque la carga quede diferida por T3**: el error de U2 fue omitir `tests/e2e/` y `tests/load/`.
  - Lo que esta tarea no llena se crea vacío con `.gitkeep`. Lo llenan los bloques siguientes. `test ! -d governance/frontend` (Paso 21) debe seguir siendo cierto.
- **Nombres.** El proyecto se llama `vectra-governance`, como `vectra-decision-registry` en U3. El extra del job se llama `validation`. El plan no fija estos dos nombres; si eliges otros, regístralo en la bitácora y ajusta los comandos de CA-2.
- **Extras (NFR-U4-24).** Las dependencias base del servicio (`psycopg[binary]`, `alembic`, `vectra-contracts`, `vectra-common` y lo que necesite el servicio según el plan) **no** incluyen `onnxruntime`, `xgboost` ni `lightgbm`. Esas tres van solo en el extra `validation`. Versiones fijadas con `==`, como en U3 y U5.
- **`vectra_disparity`.** Es un miembro del workspace de U9 (`bias-monitoring/disparity/`, plan de U9 §1 y Paso 1) que hoy **no existe** en `origin/main`.
  - Si al crear la rama ya existe, declárala en el extra `validation` como dependencia del workspace (`{ workspace = true }`).
  - Si no existe, **no** crees `bias-monitoring/` ni un paquete con ese nombre: es territorio de U9. Deja en `pyproject.toml` un comentario que nombre la dependencia pendiente, el Paso 13 y la tarea U9 A+B (enmienda §5.3). El doble lo usa el código del Paso 13 (Bloque E), y esta tarea no tiene código que lo llame. Regístralo en la bitácora. Ver la ambigüedad A-1 de las notas.
- **Contratos de import-linter**, los dos con `KEPT`:
  1. `model_fsm`, `policy`, `serving_config` y `registration` sin E/S: la misma lista de módulos prohibidos que `decision-registry/.importlinter` (`psycopg`, `alembic`, `sqlalchemy`, `httpx`, `requests`, `socket`, `urllib`, `http`, `subprocess`, `os`, `pathlib`, `asyncio`, etc.), más `kubernetes`.
  2. Ningún módulo de `vectra_governance` importa `onnxruntime`, `xgboost` ni `lightgbm`.
- **`Makefile`.** `check` corre `ruff`, `mypy --strict`, `lint-imports` y las pruebas (`HYPOTHESIS_PROFILE=ci`), como `decision-registry/Makefile`. Crece con los pasos siguientes.
- **Alembic.** Migraciones con Alembic, como dice §1. `env.py` toma la URL de `sqlalchemy.url` o de `GOVERNANCE_DATABASE_URL`, como U3 con `REGISTRY_DATABASE_URL`. La migración la corre `gov_migrator`, que es el dueño de la base según U1 (`platform/data/chart/values.yaml`, `governance-db.owner`).
- **`validation_runs.mode` en dos revisiones.** El caso «deja `mode = validacion` en las filas existentes» exige filas previas. Crea `validation_runs` sin `mode` en una revisión y agrega `mode`, `source_id`, `baseline_version_id` y el `CHECK` en la siguiente. La prueba hace `upgrade` hasta la revisión previa, inserta filas, hace `upgrade head` y lee `mode` de vuelta. El `CHECK` es el de domain-entities §2.1: en `source_comparison`, `source_id` y `baseline_version_id` son obligatorios; en `validacion`, nulos.
- **Llave de idempotencia.** `idempotency_key = UUIDv5(entity_type:entity_id, n)` (domain-entities §1.3; BR-U4-17). El caso «llaves distintas» lee de vuelta las dos llaves con `SELECT`. Si la llave la calcula la migración (columna generada o trigger), la prueba lo comprueba en SQL. Si la calcula el servicio (Bloque C o D), la prueba calcula los dos valores con `uuid.uuid5` y comprueba que se pueden insertar los dos. Documenta tu elección en la bitácora.
- **Triggers (P-U4-06).** Copia la tabla de P-U4-06 tal cual: las variables `vectra.frozen_resolution` y `vectra.freeze`, y las condiciones de `transitions` (fila `confirmada`, `entity_type = model_version`, `entity_id` igual a la versión que se actualiza, `kind = cambio_estado`, `from_state = congelado`, `to_state` igual al estado nuevo y actor con rol `cumplimiento`; para `freeze`, actor `bias-monitoring-job`). `guard_unfreeze` también rechaza los cambios de `investigation`. La verificación de P-U4-06 incluye el camino legítimo: la variable fijada con una transición confirmada de cumplimiento de **esa** versión → éxito. Ese caso va en la prueba, porque sin él un trigger que rechaza todo pasaría los casos negativos.
- **Sin `DELETE` (NFR-U4-30).** «Ningún rol» incluye a `gov_migrator`. Como es el dueño de las tablas, tiene `DELETE` implícito. La migración le revoca `DELETE` sobre las tablas de historia, y la prueba lo lee con `has_table_privilege(<rol>, <tabla>, 'DELETE')` para `gov_app`, `gov_archiver` y `gov_migrator`.
- **`gov_archiver` (INF-U4-03).** `SELECT` sobre `model_versions` y `transitions`, y `UPDATE (archived_uri, archived_at)` sobre `model_versions`. Sin permiso sobre `state`.
- **`NOTIFY` (P-U4-01).** «La transacción que confirma una transición termina con `NOTIFY serving_config, '<etag>'`». El plan pone el `NOTIFY` en la migración. La forma recomendada es un trigger sobre `serving_config` que hace `pg_notify('serving_config', NEW.etag)`, que PostgreSQL entrega al confirmar. Si eliges otra forma, regístralo. La prueba hace `LISTEN serving_config` desde otra conexión, actualiza la fila, confirma y lee la notificación con su `etag`. Antes de confirmar no debe llegar nada.
- **Una sola política `activa`.** El índice parcial va en el alcance, aunque el plan no le pone una viñeta de aceptación. Agrega el caso «dos políticas `activa` → violación del índice».
- **Sin semillas.** La migración no inserta políticas ni versiones de modelo. Una semilla de política viola BR-U4-17, BR-U4-12 y «sin atajo» (enmienda §5.1). La génesis de `serving_config` (una fila, domain-entities §5) se decide con el diseño: si la creas en la migración, sus campos quedan nulos hasta la primera transición confirmada.
- **Roles.** Los crea U1 (`platform/data/chart/values.yaml`: `governance-db.roles` = `gov_app`, `gov_archiver`, `gov_migrator`). En Testcontainers créalos con los nombres y atributos que lee `decision-registry/tests/integration/registry_pg.py` de U1, sin duplicarlos a mano. Puedes reutilizar ese patrón o extraerlo, pero no modifiques el código de U3.
- **Workspace.** Agrega `governance` a `[tool.uv.workspace].members` y `vectra-governance = { workspace = true }` a `[tool.uv.sources]` del `pyproject.toml` raíz, y regenera `uv.lock`. Si al abrir el PR ya se fusionó otra tarea que tocó el workspace, el orquestador rebasa y vuelve a correr `uv lock`.
- **Plan.** Marca `[x]` los Pasos 1 y 2, con `(U04-T01)`.

**Fuera** (la enmienda no recorta nada de A+B; esto es lo que pertenece a otras tareas):

- La lógica de `model_fsm`, `policy`, `serving_config` y `registration` (Bloque C, Pasos 3–7, tarea U4 C).
- La evidencia en dos fases, el reconciliador, los barridos, la convergencia en memoria, los pools y los endpoints (Bloque D, Pasos 8–11). Ningún handler, ni siquiera los de `frozen-resolution` o `freeze` que fijan las variables de los triggers.
- `promotion_tool` y `validation_job` (Pasos 12 y 13), y con ellos el doble de `vectra_disparity`.
- Scripts de CI (Paso 14, **D** por T4: alcance §3, U4) y `model-archive` (Paso 15, **D** por T5). Sus directorios `ci/` y `archive_job/` se crean vacíos.
- El chart, el hook de migración, flujos y RBAC (Paso 16), alertas y runbooks (Paso 17), la Application (Paso 18) y la verificación en kind (Paso 20).
- Lo que la enmienda difiere de US-306 en los pasos siguientes (`data-sources*`, `comparisons`, `decision`, `source-counts`, `compare_source`, `start_source_comparison` y la rama `source_comparison` del barrido y del job; §3, U4, Pasos 8, 10 y 13). **No** se recortan sus columnas ni sus tablas en esta tarea: la migración 2 se queda entera (§3, U4, fila 1–7).
- Cambios a los roles, a los clusters o al chart de U1, y al código de U3. Si algo falta allí, detente y repórtalo.

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md` (§1 y Pasos 1–2)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, §3 U4 y §6)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U4, §4, §5.1 y §6)
- `aidlc-docs/construction/governance/functional-design/domain-entities.md` (§1–§5) y `business-rules.md` (BR-U4-02, 03, 12, 17)
- `aidlc-docs/construction/governance/nfr-requirements/nfr-requirements.md` (NFR-U4-24, 30) y `tech-stack-decisions.md`
- `aidlc-docs/construction/governance/nfr-design/nfr-design-patterns.md` (P-U4-01, P-U4-06)
- `aidlc-docs/construction/governance/infrastructure-design/infrastructure-design.md` (INF-U4-03)
- `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md` (§1 y Paso 1, solo para ubicar `vectra_disparity`)
- `platform/data/chart/values.yaml` y `platform/data/chart/templates/clusters.yaml` (imagen de PostgreSQL y roles de `governance-db`)
- `decision-registry/pyproject.toml`, `decision-registry/Makefile`, `decision-registry/.importlinter`, `decision-registry/alembic.ini`, `decision-registry/migrations/env.py` y `decision-registry/tests/integration/registry_pg.py`, como ejemplo de miembro del workspace con Alembic y Testcontainers
- `pyproject.toml` raíz y `uv.lock`

## Criterios de aceptación

- [ ] **CA-1** — Esqueleto, dependencias y contratos de imports (Paso 1; NFR-U4-24).
  ```bash
  uv sync --frozen && uv run lint-imports --config governance/.importlinter
  ```
  Esperado: código 0, con los dos contratos `KEPT`: «`model_fsm`, `policy`, `serving_config` y `registration` sin E/S» y «el servicio no importa librerías de inferencia». **Rojo primero:** un `import psycopg` en `policy.py` y un `import xgboost` en `api.py` hacen fallar cada uno su contrato.

- [ ] **CA-2** — Extras separados: el servicio sin librerías de inferencia y el job con ellas (Paso 1; NFR-U4-24). Se lee del `uv.lock` real.
  ```bash
  uv export --frozen --package vectra-governance --no-dev --no-hashes | grep -Eic '^(onnxruntime|xgboost|lightgbm)=='
  uv export --frozen --package vectra-governance --extra validation --no-dev --no-hashes | grep -Eic '^(onnxruntime|xgboost|lightgbm)=='
  ```
  Esperado: `0` en el primero y `3` en el segundo.

- [ ] **CA-3** — Estructura de §1 entera.
  ```bash
  for p in Makefile pyproject.toml .importlinter alembic.ini migrations promotion_tool validation_job archive_job ci chart observability runbooks docs \
    tests/unit tests/property tests/integration tests/examples tests/load \
    src/vectra_governance/{__init__,model_fsm,policy,serving_config,registration,evidence,background,convergence,pools,api,k8s_jobs}.py; do
    test -e governance/$p || echo "FALTA $p"; done; test ! -d governance/frontend && echo OK-sin-frontend
  ```
  Esperado: ninguna línea `FALTA` y la línea `OK-sin-frontend`.

- [ ] **CA-4** — Migraciones: cada viñeta de la aceptación del Paso 2 es un caso, más los casos de las precisiones.
  ```bash
  uv run pytest governance/tests/integration/test_migrations.py -v
  ```
  Esperado: todos pasan. La salida muestra un caso por viñeta del plan:
  1. `descartada` con `n = 5` reserva el `n`, y `abandonada` lo libera;
  2. trigger `guard_unfreeze`: `UPDATE` directo, variable sin transición, transición de otra versión, y fila de política o de fuente, cada uno con excepción;
  3. dos versiones `activo` violan el índice;
  4. `mode = validacion` en las filas existentes, y `source_comparison` sin `source_id` viola el `CHECK`;
  5. `gov_archiver` no puede cambiar `state`;
  6. ningún rol tiene `DELETE` sobre las cuatro tablas;
  7. llaves distintas entre política y fuente, y dos pendientes de la misma política violan el índice.

  Además, los casos de las precisiones: el camino legítimo de `guard_unfreeze` pasa, `guard_freeze` rechaza sin la transición de `bias-monitoring-job`, dos políticas `activa` violan el índice, y el `NOTIFY` llega con el `etag` solo al confirmar.

  La lectura de vuelta es con SQL real contra el contenedor: `SELECT` de la tabla, `pg_indexes`, `has_table_privilege` o `information_schema.column_privileges`. No vale el código de salida de Alembic.

- [ ] **CA-5** — Lectura de vuelta independiente con `psql` sobre un PostgreSQL de prueba (la misma versión que U1). La corre el revisor tal cual.
  ```bash
  docker run -d --rm --name gov-ca5 -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17.9-trixie
  until docker exec gov-ca5 pg_isready -U postgres -q; do sleep 1; done
  docker exec gov-ca5 psql -U postgres -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE gov_migrator LOGIN PASSWORD 'm'" -c "CREATE ROLE gov_app LOGIN" -c "CREATE ROLE gov_archiver LOGIN" \
    -c "CREATE DATABASE governance OWNER gov_migrator"
  GOVERNANCE_DATABASE_URL=postgresql://gov_migrator:m@localhost:55432/governance \
    uv run alembic -c governance/alembic.ini upgrade head
  docker exec gov-ca5 psql -U postgres -d governance \
    -c "\dt" \
    -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexdef LIKE '%UNIQUE%WHERE%'" \
    -c "SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE NOT tgisinternal ORDER BY 1" \
    -c "SELECT r, t FROM unnest(ARRAY['gov_app','gov_archiver','gov_migrator']) r, unnest(ARRAY['model_versions','policies','data_sources','transitions']) t WHERE has_table_privilege(r, t, 'DELETE')" \
    -c "SELECT column_name FROM information_schema.column_privileges WHERE grantee = 'gov_archiver' AND table_name = 'model_versions' AND privilege_type = 'UPDATE' ORDER BY 1"
  docker rm -f gov-ca5
  ```
  Esperado:
  - `\dt` lista `model_versions`, `transitions`, `validation_runs`, `policies`, `data_sources` y `serving_config`, además de `alembic_version`.
  - Hay tres índices únicos parciales: la versión `activo`/`congelado`, la política `activa` y `transitions` con `WHERE (status <> 'abandonada')`.
  - Aparecen los triggers `guard_unfreeze`, `guard_freeze` y el del `NOTIFY` (o el nombre que registre la bitácora).
  - La consulta de `DELETE` devuelve `(0 rows)`.
  - `gov_archiver` tiene `UPDATE` solo sobre `archived_at` y `archived_uri`.

- [ ] **CA-6** — `check` de la unidad (RL-4; aceptación del Paso 1).
  ```bash
  make -C governance check
  ```
  Esperado: código 0. Corre lint, `mypy --strict`, import-linter y las pruebas de la unidad, incluida la de migraciones.

- [ ] **CA-7** — U1 sigue en verde, porque el diff toca el workspace y `uv.lock` (RL-4).
  ```bash
  make -C platform check
  ```
  Esperado: código 0.

## Plan de pruebas

- `governance/tests/integration/test_migrations.py`: un caso por viñeta del Paso 2 y los casos de las precisiones (camino legítimo de `guard_unfreeze`, `guard_freeze`, política `activa` única y `NOTIFY` al confirmar).
- El fixture de Testcontainers toma la imagen y los roles de `platform/data/` y usa una base por prueba, como U3.
- **Rojo primero**, registrado en `bitacoras/U04-T01.md`:
  - CA-1: el import prohibido en un módulo puro y en uno del servicio;
  - CA-2: `xgboost` en las dependencias base da `1` en el primer comando;
  - al menos tres casos de CA-4: sin `guard_unfreeze`, el `UPDATE` directo pasa; con el índice de `transitions` sin el `WHERE`, la `abandonada` bloquea el `n`; sin el `REVOKE` al dueño, `gov_migrator` aparece con `DELETE`.

## Notas

- Archivos que se modifican en su sitio: `pyproject.toml` raíz, `uv.lock` y `aidlc-docs/construction/plans/governance-code-generation-plan.md` (casillas de los Pasos 1 y 2). Nada de duplicados con sufijo.
- Docker está disponible para Testcontainers. U1 usa la imagen de CloudNativePG `17.9-system-trixie`, que no trae el entrypoint de Docker. Usa la oficial de la misma versión (`postgres:17.9-trixie`), como U3.
- **US-306 y P-1.** La enmienda difiere US-306 en el servicio. P-1 deja que sus rutas conserven el handler (opción a o b, decisión pendiente para U4 US-306). Nada de eso toca esta tarea: la enmienda dice expresamente «La migración 2 se queda entera», y `model_versions.data_sources` lo lee el `freeze` (§3, U4, y §5.1). Por eso `data_sources`, `pre_post_report`, `source_candidate_for`, `validation_runs.mode`/`source_id`/`baseline_version_id` y `entity_type = data_source` entran completos. El invariante de `source_candidate_for` en PBT-U4-01 se difiere (P-5), pero eso es del Paso 8, no de la columna.
- **A-1 (arbitrada por el orquestador, 2026-11-09).** El Paso 1 pide «`vectra_disparity` (ruta del workspace; doble mientras no exista)», pero hoy no existe, y `uv sync --frozen` no admite un miembro inexistente. U09-T01 la crea en paralelo con esta tarea. Si al abrir el PR ya está fusionada en `main`, el orquestador integra `main` y la declaras en el extra `validation`. Si no, queda el comentario de las precisiones y la dependencia entra con el Paso 13 (Bloque E), que es el primero que la usa.
- **A-2 (menor).** domain-entities §2.2 define `ValidationReport` sin nombre de tabla. Guárdalo como columna JSON de `validation_runs` o como tabla propia, según el diseño, y registra la elección. La lee el Paso 10 (`PUT /v1/models/{id}/validation-report`).
