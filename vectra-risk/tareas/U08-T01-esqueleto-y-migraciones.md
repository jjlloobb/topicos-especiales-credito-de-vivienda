# U08-T01 — Esqueleto, constantes y migraciones de `case-management`

**Unidad:** U8 `case-management`
**Historias que implementa:** US-603 (Paso 1: el cliente del core solo con `GET`). Los Pasos 2 y 3 no tienen historia propia en la trazabilidad del plan (§3), pero el Paso 3 sostiene BR-U8-02, 12 y 20 en la base.
**Depende de:** U0 y U1 en `main`:
- U0: `vectra_contracts` y `vectra_common`;
- U1: los cuatro roles de `case-db` (`platform/data/chart/values.yaml`, `clusters.case-db`: base `case`, dueño `case_migrator`, roles `case_app`, `case_migrator`, `case_retention` y `case_worker`).

Es código estático y pruebas con Testcontainers, sin clúster. No necesita U3, U4 ni U7 en kind: en el grafo son dependencias de runtime, y RL-5 permite empezar el código estático antes (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6).
**Se despacha** ya: U0 y U1 están en `main`. Puede correr en paralelo con otras unidades (RL-5).
**Rama:** `tarea/U08-T01`, desde `origin/main`.

Bloques A y B del plan de U8 (`aidlc-docs/construction/plans/case-management-code-generation-plan.md`, Pasos 1 a 3). Es la tarea «A+B» de `demo-recorte-funcional.md` §4 y §8 («U8: A+B · C · D (9–13) · E+F (14, 15, 17, 18) · G+cierre (19–23, 25, 26)»). Los tres pasos entran **completos** (E): la enmienda dice «1–7 · E · E · Completos (`retry` y `vencido` en `case_fsm` por PBT-U8-01)» (§3, U8). Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

**Antes de despachar:** P-1 y P-2 (al final) están abiertas. Cada una tiene una recomendación; si la persona no dice otra cosa, rige la recomendación.

---

## Alcance

**Dentro:** los Pasos 1 a 3 del plan. Es el texto del plan, sin recortes:

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `case-management/`**
  - Directorios de §1; `pyproject.toml` (dos miembros del workspace: `vectra_case` y `core_banking_mock`) que dependen de `vectra_contracts` y `vectra_common`.
  - Contratos de import-linter:
    - `case_fsm`, `backoff`, `decision` y `views` no importan `db`, `httpx` ni `vectra_common.deps` (funciones puras);
    - ningún módulo importa `httpx` fuera de `vectra_common.deps` (P-U0-07);
    - ninguno importa librerías de circuit breaking (NFR-U8-34).
  - Prueba estática: el cliente del core (`credit`) no tiene ningún método distinto de `GET` (NFR-U8-43, BR-U8-22).
  - Diseño: BR-U8-06, 22; NFR-U8-34, 43; P-U8-02. Historia: US-603.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config case-management/.importlinter && make -C case-management check` sobre el esqueleto; `uv run pytest case-management/tests/unit/test_core_client_readonly.py`.

- [ ] **Paso 2 — Constantes tipadas**
  - `vectra_case/config.py`:
    - timeouts de NFR-U8-30 (`serving-config` 500 ms, `feature_spec` 1 s, scoring 7 s, registro 2,5 s, core 500 ms);
    - pools de P-U8-02 (scoring 16, governance 4 y 2, registro 10, core 10), `RECONCILER_CONCURRENCY = 4` y pool de `case-db` ≤ 5;
    - umbrales del circuit breaker (≥ 50 % en 20 llamadas dentro de 30 s; semiabierto a los 10 s);
    - backoff (BR-U8-07), arrendamiento de 30 s, sondeo 400 ms ± 100 ms y semáforo de 16 (P-U8-01);
    - lotes (100 en barridos y reconciliador, 500 en la retención), abandono a las 24 h (BR-U8-18), gracia del worker de 20 s (INF-U8-06).
  - Values (no constantes): URLs y audiencias, telemetría, `allowTestScenarios`, `core.enabled`, `coreMock.enabled`, `retention.*` (INF-U8-07).
  - Diseño: INF-U8-07; P-U8-01, 02; NFR-U8-30, 31.
  - **Aceptación**: `uv run pytest case-management/tests/unit/test_config.py`:
    - `WORKER_WORST_CASE (15,5 s) < LEASE (30 s)`;
    - `WORKER_WORST_CASE < WORKER_SHUTDOWN_GRACE (20 s) < terminationGracePeriodSeconds (30 s)`;
    - `RECONCILER_CONCURRENCY (4) < REGISTRY_POOL (10)`;
    - ninguna constante se lee de variables de entorno.

### Bloque B — Base de datos

- [ ] **Paso 3 — Migraciones de `case-db`**
  - Tablas de domain-entities §1–§3, con:
    - el índice único parcial «un trabajo vivo por caso» en `evaluation_jobs` y `CHECK (attempt BETWEEN 0 AND 6)`;
    - la clave única (`case_id`, `user_id`) en `explanation_views`;
    - el índice único parcial de `decisions` por `case_id` (`state` `pendiente_registro` o `confirmada`);
    - el índice único parcial de `evidence_outbox`: `UNIQUE (idempotency_key) WHERE state <> 'abandonada'` (domain-entities §3.1);
    - la columna `cases.ever_degraded boolean NOT NULL DEFAULT false` (FD de U11; pendientes posteriores al cierre, 2026-10-10), que solo el worker escribe (`case_worker`, en su `UPDATE` por columna; `case_app` no la tiene), y un trigger `guard_ever_degraded` que impide volverla a `false`; prueba de migraciones: el worker la pone en `true` → éxito, `case_app` → error de permisos, volver a `false` → excepción del trigger (pendientes consolidados, 2026-10-10).
  - Grants de `case_app`, `case_worker`, `case_retention` y `case_migrator` (los roles los crea U1; cuarta revisión de coherencia entre unidades, 2026-10-31), con los permisos por tabla y por columna de `logical-components.md` §1 (INF-U8-01): `UPDATE` por columna de `case_app` y `case_worker` sobre `cases`; `SELECT` por columna de `case_retention`.
  - Tabla `case_transitions (from_state, to_state, db_role)` con las filas de INF-U8-01 y trigger `guard_transition` (`BEFORE INSERT OR UPDATE OF state`, `SECURITY DEFINER`, dueño `case_migrator`, `SET search_path = pg_catalog, public`, compara con `session_user`).
  - Trigger `guard_vencido` (`SECURITY INVOKER`) y tabla `retention_settings` de una fila, escrita con `INSERT … ON CONFLICT (id) DO UPDATE` desde los values, sin tocar `created_at` (P-U8-05).
  - RLS en `evidence_outbox`: `worker_fail_closed_only` (`FOR INSERT TO case_worker WITH CHECK (entry_type = 'fail_closed')`) y `app_all` para `case_app` (INF-U8-01).
  - Las cadenas de conexión apuntan a la base `case` (revisión de consistencia entre unidades, 2026-11-01), usan `sslmode=verify-full`, y cada proceso se conecta con su rol, sin `SET ROLE` ni pooler (P-U1-08; `guard_transition` depende de `session_user`). Ver P-2.
  - Diseño: BR-U8-02, 12, 20; INF-U8-01; P-U8-05; NFR-U8-40, 41.
  - **Aceptación**: `uv run pytest case-management/tests/migrations` (Testcontainers, cada caso con el rol real):
    - `case_worker` lee `decisions`, borra `case_identifiers` o escribe `vencido` → error; `case_app` hace `DELETE` sobre `evaluation_jobs` → error;
    - `case_app` escribe `recommendation`, `recommendation_entry_id`, `last_cause` o `escalation_count` → error de permisos; `INSERT` de un caso en `listo` o con `recommendation` → excepción de `guard_transition`;
    - para cada fila de `case_transitions`, el rol indicado hace la transición; otro rol o un par ausente → excepción; ningún rol de la aplicación lee ni escribe `case_transitions`;
    - `case_worker` inserta `fail_closed` en `evidence_outbox` → éxito; `human_decision` o `explanation_view` → error de RLS; `case_app` inserta los tres → éxito;
    - `case_worker` repite el `INSERT` de `fail_closed` con la misma llave, sin `RETURNING` ni `ON CONFLICT` y dentro de un `SAVEPOINT` → `unique_violation`, vuelta al `SAVEPOINT` y el resto de la transacción confirma (BR-U8-09);
    - `case_worker` intenta `INSERT … RETURNING` u `ON CONFLICT DO UPDATE` sobre `evidence_outbox` → error de permisos (documenta por qué el código no los usa);
    - con una `human_decision` `abandonada` (decisión y evidencia), `case_app` inserta la decisión nueva y su evidencia con la **misma** llave → sin choque; una segunda fila viva con esa llave → `unique_violation`;
    - el orden del conflicto tras un abandono (BR-U8-18): pasar la nueva a `abandonada` y después la anterior a `confirmada`, en una transacción → éxito; el orden inverso → `unique_violation`;
    - `evaluation_jobs.attempt = 7` → violación del `CHECK`;
    - `case_app` escribe `vencido` → excepción; `case_retention` escribe `vencido` en un caso de 1 año → excepción, en uno de 2 años y 1 día → éxito; `case_retention` escribe `listo` → excepción;
    - `case_retention` y `case_app` escriben en `retention_settings` → error; cambiar `retention.undecided_years` y migrar → el trigger aplica el valor nuevo y `created_at` no cambia.

### Precisiones

- **Estructura de §1, entera.** El esqueleto crea **todo** el árbol «Estructura de destino» del plan (§1):
  - `case-management/` con `Makefile`, `pyproject.toml`, `.importlinter` y `alembic.ini` (como U4);
  - `src/vectra_case/` con `__init__.py`, `config.py` (Paso 2) y los demás módulos de §1 como **módulos vacíos** con docstring, para que import-linter tenga qué contratar: `case_fsm.py`, `backoff.py`, `decision.py`, `views.py`, `db.py`, `metrics.py`, `intake.py`, `evidence.py`, `sweeps.py`, `credit.py`, `db_gauges.py`, `api.py`, `app.py`, `governance_client.py`, `job_queue.py`, `evaluation.py`, `worker.py` y `retention.py`;
  - `migrations/` (Alembic: `env.py` y `versions/`);
  - `core_banking_mock/` con su `pyproject.toml`, `src/core_banking_mock/` con `__init__.py`, `app.py`, `auth.py` y `metrics.py` vacíos, y `fixtures/`. `fixtures/credits.json` es del Paso 17, así que `fixtures/` va con `.gitkeep`. También `core_banking_mock/tests/`, porque la aceptación del Paso 17 lo nombra;
  - `chart/templates/`, `policies/conftest/`, `observability/rules/`, `observability/rules/tests/`, `observability/runbooks/`, `docs/` y `tools/`;
  - `tests/unit/`, `tests/property/`, `tests/migrations/`, `tests/integration/`, `tests/doubles/` y `tests/load/`. **`tests/load/` va aunque k6 quede diferido (T3).** El error de U2 fue omitir `tests/e2e/` y `tests/load/`. §1 no lista `tests/e2e/`, así que no se crea.

  Lo que esta tarea no llena se crea vacío con `.gitkeep`. **No** se crean `Chart.yaml`, plantillas ni `values.yaml` (Paso 20), ni el `Dockerfile` (Paso 19), ni `check_openapi.py` (Paso 22), ni `frontend/` (Paso 25: `test ! -d case-management/frontend`).
- **Dos miembros del workspace.**
  - `case-management/pyproject.toml` es el paquete `vectra-case`, con `vectra-contracts`, `vectra-common`, `psycopg[binary]`, `alembic` y `sqlalchemy`, como U4 en `governance/migrations/env.py`.
  - `case-management/core_banking_mock/pyproject.toml` es el paquete `core-banking-mock`, con `vectra-common` (que ya trae FastAPI).
  - Versiones fijadas con `==`, como U3 y U4.
  - Agrega los dos a `[tool.uv.workspace].members` y a `[tool.uv.sources]` del `pyproject.toml` raíz. Regenera `uv.lock`.
  - Las herramientas de prueba (Testcontainers, Hypothesis y pytest-cov) ya están en el grupo `dev` de la raíz; agrega solo lo que falte.
  - Si eliges otros nombres de paquete, regístralo en la bitácora y ajusta los comandos.
  - Si al abrir el PR ya se fusionó otra tarea que tocó el workspace, el orquestador rebasa y vuelve a correr `uv lock`.
- **Contratos de import-linter.** Los tres del plan, con `KEPT`:
  1. `case_fsm`, `backoff`, `decision` y `views` no importan `vectra_case.db`, `httpx` ni `vectra_common.deps`. Como son «funciones puras», el contrato también prohíbe la lista de E/S de `governance/.importlinter` (`psycopg`, `sqlalchemy`, `alembic`, `socket`, `subprocess`, `os`, `pathlib`, `asyncio`, etc.).
  2. Ningún módulo de `vectra_case` ni de `core_banking_mock` importa `httpx`. `vectra_common.deps` es de U0 y queda fuera del contrato.
  3. Ninguno importa librerías de circuit breaking. Mínimo: `pybreaker`, `circuitbreaker`, `aiobreaker` y `purgatory`. Ninguna está instalada. Si import-linter no acepta prohibir un paquete que no está en el grafo, regístralo en la bitácora con la salida y cubre ese contrato con una prueba de AST en `tests/unit/` que haga lo mismo. Además, el SBOM del Paso 19 vuelve a comprobarlo.
- **`test_core_client_readonly.py` (NFR-U8-43, BR-U8-22).**
  - Analiza con `ast` el módulo `vectra_case/credit.py`. Falla si encuentra:
    - una llamada a un método HTTP distinto de `get`/`GET` (`post`, `put`, `patch`, `delete`, `request` con otro método);
    - un literal de método distinto de `GET` pasado a `deps.call` o a un cliente.
  - Hoy `credit.py` está vacío y la prueba pasa. La escritura real del cliente es del Paso 12 (U08-T03); la prueba queda como guardia.
  - **Rojo primero:** un `client.post(...)` temporal en `credit.py` la hace fallar. Regístralo en la bitácora antes de quitarlo.
- **`config.py` (Paso 2; INF-U8-07).**
  - `WORKER_WORST_CASE` se **calcula** desde las constantes: `serving-config` + `feature_spec` + scoring + scoring con el reintento por 401 = 0,5 + 1 + 7 + 7 = 15,5 s (`nfr-design-patterns.md`, P-U8-01). No va escrito a mano.
  - `terminationGracePeriodSeconds` (30 s) es un campo del chart (Paso 20, U08-T05). En esta tarea es una constante documentada en `config.py` (por ejemplo `WORKER_TERMINATION_GRACE = 30`). La prueba del chart del Paso 20 comprueba que el render la usa.
  - La prueba «ninguna constante se lee de variables de entorno» cambia el entorno y comprueba que nada cambia. Además busca `os.environ` y `getenv` en `config.py`.
  - Los values (`allowTestScenarios`, `core.enabled`, `coreMock.enabled`, `retention.*`, URLs y audiencias) **no** se definen como constantes. Llegan al chart en el Paso 20.
- **Roles y Testcontainers.**
  - Los roles salen de `platform/data/chart/values.yaml` (`clusters.case-db.roles`, base `case`, dueño `case_migrator`) y se crean con `login`. No se duplican a mano.
  - La imagen de PostgreSQL es la de la versión de CloudNativePG de U1, como en `governance/tests/integration/governance_pg.py`. Copia ese patrón a `case-management/tests/migrations/` (por ejemplo `case_pg.py`). No importes las pruebas de U4.
  - La migración la corre `case_migrator` como dueño de la base. Las pruebas se conectan **con cada rol real** (`session_user`), nunca como superusuario: `guard_transition` en `INSERT` exige `session_user = case_app`, así que los casos de prueba se crean como `case_app`. Las fechas pasadas (1 año, 2 años y 1 día) se fijan con `created_at` explícito en ese `INSERT`.
- **Alembic.** `env.py` como el de U4: SQL plano, sin modelos, `transaction_per_migration=True`, y URL de `sqlalchemy.url` o de `CASE_DATABASE_URL`. `env.py` no agrega `SET ROLE` ni cambia el usuario de la URL.
- **`case_transitions` y su comparación con `case_fsm`.**
  - Las filas son las 16 de la tabla de INF-U8-01, expandidas a pares:
    - 8 de `case_worker`: {`en_evaluacion`, `en_sincronizacion`} × {`listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`};
    - 2 de `case_app` hacia `en_evaluacion`, desde `modelo_congelado` y desde `no_disponible`;
    - 1 de `case_app`: `listo` → `decidido`;
    - 5 de `case_retention` hacia `vencido`.
  - Decláralas en la revisión como **una constante literal de Python** (por ejemplo `CASE_TRANSITIONS`). Así U08-T02 (Paso 4) puede cargar la revisión por ruta y comparar la tabla de `case_fsm` sin el rol y sin la fila de creación (— → `en_evaluacion`, que cubre la rama `INSERT` del trigger).
  - `guard_transition` solo compara en `UPDATE` cuando `NEW.state <> OLD.state`. Por eso el par `en_sincronizacion` → `en_sincronizacion` está en la tabla, pero no dispara el trigger.
- **`guard_vencido`.** Copia la tabla de P-U8-05 tal cual (cuatro filas, `SECURITY INVOKER`, `current_user`). Lee los plazos de `retention_settings`, nunca de constantes.
- **`retention_settings` desde los values.** Ver **P-1**. El plan exige que cambiar `retention.undecided_years` y volver a migrar aplique el valor nuevo. Una revisión de Alembic que ya corrió no vuelve a correr, así que el `INSERT … ON CONFLICT (id) DO UPDATE` no puede vivir solo dentro de una revisión versionada.
  - Valores por omisión de P-U8-05: `decided_years = 10`, `undecided_years = 2` y `intake_keys_days = 30`.
  - La prueba lee de vuelta `created_at` y `updated_at` antes y después de la segunda migración.
- **Cada caso de la aceptación es una prueba con nombre propio.** Así el revisor las ubica una por una. Los casos de `ever_degraded` del primer punto del Paso 3 van también, con sus tres resultados: el worker la pone en `true` → éxito; `case_app` → error de permisos; volver a `false` → excepción del trigger, también como dueño.
- **Privilegios leídos de vuelta.** «Ningún rol de la aplicación lee ni escribe `case_transitions`» se comprueba de dos formas: con el intento real, y con `has_table_privilege(<rol>, 'case_transitions', 'SELECT')`, que debe dar `false` para `case_app`, `case_worker` y `case_retention`, y lo mismo con `INSERT`.
- **`make -C case-management check`.** Corre en orden:
  1. `ruff check` y `ruff format --check`;
  2. `mypy --strict` sobre `case-management/src` y `case-management/core_banking_mock/src`;
  3. `lint-imports`;
  4. las pruebas con `HYPOTHESIS_PROFILE=ci`, incluidas las de migraciones con Testcontainers (Docker local, sin clúster; AUTONOMIA-01).

  Usa `case-management/pytest.ini` y `coveragerc` propios, como U5 y U9 (`[tool.coverage.run] source` de la raíz solo mide U0). Termina en 0.
- **Plan.** Marca `[x]` los Pasos 1 a 3 con `(U08-T01)`.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **El código de los Bloques C a I** (Pasos 4 a 26): `case_fsm`, `backoff`, `decision`, `views` y los servicios, `core-banking-mock`, el chart, el Job de migración, las alertas, la documentación y las Applications. Sus módulos quedan vacíos con docstring.
- **El Job de migración y los values de Helm** (Paso 20, U08-T05). En esta tarea solo se fija cómo recibe la migración los tres plazos (P-1), y se prueba con Testcontainers.
- **El render con `sslmode=verify-full`** (Paso 20; P-2).
- **La CLI `case-retention`** (Paso 16, D por la enmienda). Los grants de `case_retention` y `guard_vencido` sí entran, porque son del Paso 3.
- **La función de purga de `intake_keys`** (P-5 de la enmienda: va al Paso 9, U08-T03). La tabla `intake_keys` y su clave única sí entran.
- **`mutmut`** (Paso 8, U08-T02, diferido).
- **Cambios a U0, a U1 o a otras unidades.** Si falta un rol o un atributo en U1, o un tipo de U0 no encaja, se reporta, no se corrige aquí.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (§1, Bloques A y B, §3, «Reglas de admisión»)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U8, §4, §5.2, §6 P-5, §8)
- `aidlc-docs/construction/case-management/functional-design/domain-entities.md` (§1–§3)
- `aidlc-docs/construction/case-management/functional-design/business-rules.md` (BR-U8-02, 06, 07, 09, 12, 18, 20, 22)
- `aidlc-docs/construction/case-management/nfr-requirements/nfr-requirements.md` (NFR-U8-30, 31, 34, 40, 41, 43) y `tech-stack-decisions.md`
- `aidlc-docs/construction/case-management/nfr-design/logical-components.md` (§1, «Tablas de `case-db` y roles») y `nfr-design-patterns.md` (P-U8-01, 02, 05)
- `aidlc-docs/construction/case-management/infrastructure-design/infrastructure-design.md` (INF-U8-01, 06, 07)
- `platform/data/chart/values.yaml` y `platform/data/chart/templates/clusters.yaml` (roles de `case-db`)
- `governance/migrations/env.py`, `governance/alembic.ini`, `governance/tests/integration/governance_pg.py`, `governance/tests/integration/test_migrations.py`, `governance/Makefile` y `governance/.importlinter` como ejemplo
- `reference-model/pytest.ini` y `reference-model/coveragerc` como ejemplo de configuración por unidad
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (`CaseState`, `LocalCause`) y `contracts/tests/conftest.py` (perfiles de Hypothesis)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`.

- [ ] **CA-1** — Esqueleto, dependencias y los tres contratos de imports (Paso 1; NFR-U8-34; P-U0-07).
  ```bash
  uv sync --frozen && uv run lint-imports --config case-management/.importlinter
  ```
  Esperado: código 0, con los tres contratos listados como `KEPT`. **Rojo primero:** un `import httpx` en `views.py`, un `import vectra_case.db` en `case_fsm.py` y un `import pybreaker` en `worker.py` hacen fallar su contrato. Regístralo y quítalos.

- [ ] **CA-2** — Estructura completa de §1, sin `frontend/`.
  ```bash
  cd case-management && for p in Makefile pyproject.toml .importlinter alembic.ini migrations/env.py migrations/versions src/vectra_case/config.py src/vectra_case/case_fsm.py src/vectra_case/backoff.py src/vectra_case/decision.py src/vectra_case/views.py src/vectra_case/db.py src/vectra_case/metrics.py src/vectra_case/intake.py src/vectra_case/evidence.py src/vectra_case/sweeps.py src/vectra_case/credit.py src/vectra_case/db_gauges.py src/vectra_case/api.py src/vectra_case/app.py src/vectra_case/governance_client.py src/vectra_case/job_queue.py src/vectra_case/evaluation.py src/vectra_case/worker.py src/vectra_case/retention.py core_banking_mock/pyproject.toml core_banking_mock/src/core_banking_mock/app.py core_banking_mock/src/core_banking_mock/auth.py core_banking_mock/src/core_banking_mock/metrics.py core_banking_mock/fixtures core_banking_mock/tests chart/templates policies/conftest observability/rules/tests observability/runbooks docs tools tests/unit tests/property tests/migrations tests/integration tests/doubles tests/load; do test -e "$p" || echo "FALTA $p"; done; test ! -d frontend && echo OK
  ```
  Esperado: ninguna línea `FALTA` y `OK` al final.

- [ ] **CA-3** — El cliente del core no tiene métodos de escritura (Paso 1; NFR-U8-43; BR-U8-22; US-603).
  ```bash
  uv run pytest case-management/tests/unit/test_core_client_readonly.py -v
  ```
  Esperado: pasa, y la bitácora registra el rojo con un `post` temporal.

- [ ] **CA-4** — Constantes tipadas (Paso 2; INF-U8-07; P-U8-01, 02; NFR-U8-30, 31).
  ```bash
  uv run pytest case-management/tests/unit/test_config.py -v
  ```
  Esperado: pasan los cuatro casos del plan, uno por viñeta. `WORKER_WORST_CASE` se calcula desde las constantes y vale 15,5 s. Un caso más comprueba cada valor nombrado del Paso 2 contra el plan: timeouts, pools, `RECONCILER_CONCURRENCY`, pool de `case-db` ≤ 5, breaker, backoff, arrendamiento, sondeo, semáforo, lotes, abandono y gracia. **Rojo primero:** con `LEASE = 15`, el primer caso falla.

- [ ] **CA-5** — Migraciones de `case-db` con los roles reales (Paso 3; BR-U8-02, 12, 20; INF-U8-01; P-U8-05; NFR-U8-40, 41).
  ```bash
  uv run pytest case-management/tests/migrations -v
  ```
  Esperado: código 0. La salida muestra una prueba por cada viñeta de la aceptación del Paso 3 y por cada resultado de `ever_degraded`. Cada caso que cambia estado lee el resultado de vuelta con `SELECT` (estado del caso, filas de `evidence_outbox` y `decisions`, `retention_settings.created_at` y `updated_at`). El caso de `case_transitions` está parametrizado por las 16 filas y por los roles que no corresponden. **Rojo primero:** registra en la bitácora al menos tres:
  - `guard_transition` con `current_user` en lugar de `session_user` deja pasar una transición prohibida;
  - sin la política `worker_fail_closed_only`, `case_worker` inserta una `human_decision`;
  - sin el índice parcial `WHERE state <> 'abandonada'`, el caso de la decisión nueva tras un abandono falla.

- [ ] **CA-6** — Sin `SET ROLE` ni pooler (Paso 3; P-U1-08).
  ```bash
  ! grep -rniE "set role|set session authorization|pgbouncer" case-management/src case-management/migrations && echo OK
  ```
  Esperado: `OK`.

- [ ] **CA-7** — Plan marcado.
  ```bash
  grep -nE "^- \[x\] \*\*Paso [123] " aidlc-docs/construction/plans/case-management-code-generation-plan.md
  ```
  Esperado: tres líneas, cada una con `(U08-T01)`.

- [ ] **CA-8** — `check` de la unidad (RL-4) y de U1, porque el diff toca el workspace.
  ```bash
  make -C case-management check && make -C platform check
  ```
  Esperado: código 0 en los dos. `make -C platform check` necesita `kubeconform`, `egctl` y `k6`, que instala `platform/install-tools.sh`; en U04-T07 faltaban en esta máquina. Si no se pueden instalar, regístralo con la salida y deja que lo corra el revisor o el CI.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_core_client_readonly.py`: la guardia de AST del Paso 1.
- `tests/unit/test_config.py`: las cuatro viñetas del Paso 2, más los valores nombrados.
- `tests/migrations/case_pg.py` (o el nombre que elijas): el contenedor, los roles de U1, la migración como `case_migrator` y una conexión por rol.
- `tests/migrations/test_*.py`: un caso por viñeta del Paso 3, más los tres de `ever_degraded` y el caso de P-1 (cambio de plazo y segunda migración).
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U08-T01.md`. Como mínimo, los de CA-1, CA-3, CA-4 y CA-5. El par falla-pasa es la prueba.

---

## Notas

- Archivos que se **modifican en su sitio**: `pyproject.toml` raíz, `uv.lock` y `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (casillas de los Pasos 1 a 3). Nada de duplicados con sufijo.
- U08-T02 (Bloque C) usa la constante `CASE_TRANSITIONS` de la revisión y los módulos vacíos de esta tarea. No cambies sus nombres después del PR sin avisar.
- Los grants siguen la tabla de `logical-components.md` §1 y las viñetas de INF-U8-01. Si las dos difieren, rige INF-U8-01, que es la más reciente (por ejemplo, `ever_degraded` en el `UPDATE` de `case_worker`). Regístralo en la bitácora.
- `case_worker` no tiene `SELECT` sobre `evidence_outbox`: por eso el `INSERT` es simple y en un `SAVEPOINT`. No agregues `SELECT` para «simplificar».

---

## Preguntas abiertas

- **P-1 — Cómo llega `retention.*` a `retention_settings` en cada migración.** El plan pide un `INSERT … ON CONFLICT (id) DO UPDATE` «desde los values» y que, al cambiar `retention.undecided_years` y migrar, el trigger use el valor nuevo. Una revisión de Alembic ya aplicada no vuelve a correr. El plan no dice dónde vive el upsert ni cómo recibe la migración los tres plazos.
  - **Recomendación:** el upsert va en `migrations/env.py`, después de `run_migrations()` y en la misma conexión de `case_migrator`, así corre en cada ejecución del Job. Los plazos llegan por `RETENTION_DECIDED_YEARS`, `RETENTION_UNDECIDED_YEARS` y `RETENTION_INTAKE_KEYS_DAYS`, que el Job del Paso 20 llena desde `retention.*`. Son values, no constantes de INF-U8-07, así que no chocan con la regla «ninguna constante como variable de entorno». Si falta una de las tres o no es un entero positivo, la migración falla. La primera revisión crea la tabla con los valores por omisión de P-U8-05.
  - **Alternativa:** un módulo `vectra_case/migrate.py` que corre `alembic upgrade head` y después el upsert. Agrega un archivo que §1 no lista.
- **P-2 — `sslmode=verify-full`.** El Paso 3 lo pide en las cadenas de conexión. En esta tarea no hay cadena propia: `env.py` usa la URL que recibe, y Testcontainers no tiene TLS. Además:
  - U3 y U4 quedaron en `sslmode=require` porque la CA de CloudNativePG no está en `vectra-app` (`CANDIDATAS.md`, entrada «U3, chart: `database.sslmode`»; `governance/chart/values.yaml`);
  - U01-T07 exige `verify-full` en los clientes de U1.
  - **Recomendación:** en esta tarea entran solo «cada proceso con su rol» y «sin `SET ROLE` ni pooler» (CA-6). `verify-full` se comprueba en el render del chart del Paso 20 (U08-T05). Antes de esa tarea, la persona decide si U8 usa `verify-full`, con la CA montada en `vectra-app`, o `require`, como U3 y U4, registrado como candidata.

