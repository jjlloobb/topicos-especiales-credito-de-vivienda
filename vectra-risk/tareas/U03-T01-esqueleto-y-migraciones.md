# U03-T01 — Esqueleto y migraciones de `decision-registry`

**Unidad:** U3 `decision-registry`
**Historias que implementa:** US-401 (append-only encadenado), en su parte de datos.
**Depende de:** U0 y U1 en `main`. U2 no cierra todavía su verificación en kind, pero esta tarea no la necesita: es código estático y pruebas con Testcontainers (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6).

Bloques A y B del plan de U3 (Pasos 1 y 2). Los dos entran **completos** en el alcance de la demo (E). Rige el ritmo RL-1 a RL-5: una tarea por bloque, máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 1 y 2 del plan. Texto del plan, sin recortes:

- [ ] **Paso 1 — Esqueleto de `decision-registry/`**
  - Directorios de §1; `pyproject.toml` (miembro del workspace, psycopg 3, `cryptography`, `zstandard`, `hvac` o cliente HTTP de Transit vía `deps.call`); `Makefile` con `check`; perfiles de Hypothesis de U0; contrato de import-linter: `chain`, `verify` y `projections` sin E/S.
  - Diseño: NFR-U3-50; P-U3-05.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config decision-registry/.importlinter && make -C decision-registry check` sobre el esqueleto.

- [ ] **Paso 2 — Migraciones de `registry-db`**
  - Copia íntegra del Paso 2 de `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`: tabla `registry_entries` particionada por rango de `seq`; grants de `registry_app`, `registry_verifier`, `registry_ondemand`, `registry_health` y `registry_migrator` (los roles los crea U1); trigger `BEFORE UPDATE OR DELETE OR TRUNCATE`; índices; génesis; índice por `recorded_at`; las cinco tablas derivadas `monitoring_*`; rol `registry_aggregator`; `idempotency_key` del checkpoint como `UUIDv5`; tabla `integrity_checks` con sus `CHECK` y el índice único parcial.
  - Diseño: BR-U3-01, 02, 10; NFR-U3-31, 42; P-U3-06; INF-U3-05; domain-entities §1, §1.2, §1.3 y §5.0. Historia: US-401.
  - **Aceptación**: todos los casos que lista el plan para `uv run pytest decision-registry/tests/integration/test_migrations.py` (Testcontainers), uno por viñeta.

Precisiones:
- **Estructura de §1.** Crea solo los directorios y archivos que estos dos pasos usan: `src/vectra_registry/` con `__init__.py` y módulos vacíos para `chain`, `verify` y `projections` (para que import-linter tenga qué contratar), `migrations/`, `tests/{unit,property,integration,examples}`, `Makefile`, `pyproject.toml` y `.importlinter`. Los demás directorios de §1 (`chart/`, `chart-rebuild/`, `vault-policies/`, `observability/`, `runbooks/`, `docs/`, `tests/load`, `tests/bench`) se crean vacíos con `.gitkeep`. Los llenan los bloques siguientes.
- **Roles.** Los crea U1 (`platform/data/`). En la prueba de Testcontainers, crea los roles con los mismos nombres y atributos que el SQL de U1. Léelo de `platform/data/` en vez de duplicarlo, si se puede. Si U1 no tiene uno de los roles que usa el Paso 2 (`registry_ondemand`, `registry_aggregator`), **detente y repórtalo**.
- **Alembic.** Migraciones con Alembic, como dice §1. La génesis la inserta una migración.
- **Workspace.** Agrega `decision-registry` a `[tool.uv.workspace].members` del `pyproject.toml` raíz y regenera `uv.lock`. Si al abrir el PR ya se fusionó otra tarea que tocó el workspace (U05-T01), el orquestador rebasa y vuelve a correr `uv lock`.
- **Plan.** Marca `[x]` los Pasos 1 y 2, con `(U03-T01)`.

**Fuera:**
- Lógica de `chain`, `verify` y `projections` (Bloque C), el servicio, la CLI, los CronJobs y el chart.
- Cambios a los roles o al chart de U1. Si algo falta allí, se reporta.
- Pasos D del alcance de la demo para U3 (14 y 17).

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md` (§1 y Pasos 1–2)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (U3 y §6)
- `aidlc-docs/construction/decision-registry/functional-design/domain-entities.md` y `business-rules.md`
- `aidlc-docs/construction/decision-registry/nfr-requirements/` y `nfr-design/nfr-design-patterns.md` (P-U3-05, P-U3-06)
- `aidlc-docs/construction/decision-registry/infrastructure-design/infrastructure-design.md` (INF-U3-05)
- `platform/data/` (roles de U1 en CloudNativePG)
- `contracts/python/` (perfiles de Hypothesis y utilidades de U0), `identity-edge/pyproject.toml` y `identity-edge/Makefile` como ejemplo de miembro del workspace

## Criterios de aceptación

- [ ] **CA-1** — Esqueleto, dependencias y contrato de imports.
  ```bash
  uv sync --frozen && uv run lint-imports --config decision-registry/.importlinter
  ```
  Esperado: código 0, con el contrato «`chain`, `verify` y `projections` sin E/S» listado como `KEPT`. **Rojo primero:** un `import psycopg` en `chain.py` hace fallar el contrato.

- [ ] **CA-2** — Migraciones: cada viñeta de la aceptación del Paso 2 es un caso.
  ```bash
  uv run pytest decision-registry/tests/integration/test_migrations.py -v
  ```
  Esperado: todos pasan. La salida muestra un caso por cada viñeta del plan: permisos de `registry_app`, trigger contra superusuario, génesis única con `seq = 0`, partición `DEFAULT`, permisos de `registry_aggregator`, y `integrity_checks` con sus `CHECK`, el índice parcial y los permisos de `registry_app`, `registry_verifier` y `registry_ondemand`. La lectura de vuelta es con SQL real contra el contenedor (`SELECT` de `pg_class`, `information_schema` o la tabla), no con el código de salida de Alembic.

- [ ] **CA-3** — `check` de la unidad.
  ```bash
  make -C decision-registry check
  ```
  Esperado: código 0. Incluye lint, import-linter y las pruebas de la unidad.

- [ ] **CA-4** — U1 sigue en verde, por si el diff toca algo que U1 barre (workspace o trazabilidad).
  ```bash
  make -C platform check
  ```
  Esperado: código 0.

## Plan de pruebas

- `tests/integration/test_migrations.py`, con un caso por viñeta del Paso 2.
- Rojo primero de CA-1 (import prohibido) y de al menos dos casos de CA-2: por ejemplo, sin el trigger, el `UPDATE` de superusuario pasa; o con `UPDATE` concedido a `registry_app`, el caso falla. Regístralo en `bitacoras/U03-T01.md`.

## Notas

- Archivos que se modifican en su sitio: `pyproject.toml` raíz, `uv.lock`, el plan de U3.
- Docker está disponible para Testcontainers. La imagen de PostgreSQL es la misma versión que usa U1 en CloudNativePG; tómala de `platform/data/`.
