# Plan de tareas (Code Generation Part 1) — U3 `decision-registry`

**Este plan es la única fuente de verdad para generar el código de U3.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U3. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U3 `decision-registry`: registro append-only encadenado (único componente Critical) |
| Historias (dueña) | US-401 (append-only encadenado), US-402 (verificador), US-403 (expediente), US-404 (eventos de gobierno) |
| Ubicación | `vectra-risk/decision-registry/` (monorepo) y Applications en `vectra-risk-gitops` |
| Datos propios | `registry-db` (cluster de CloudNativePG de U1): esquema, particiones, roles y génesis |
| Depende de | U0 (tipos de registro, JCS, `create_app`, `deps.call`), U1 (plataforma, `restore-drill`, buckets, ESO, observabilidad), U2 (scopes en el realm) |
| Lo consumen | scoring y case (append), governance (eventos), BFF (expediente y verificación), explainability, bias y product-metrics (proyecciones), U1 `restore-drill` (CLI) |

**Diseño de entrada:**
- Functional Design: `construction/decision-registry/functional-design/` (BR-U3-01..16, PBT-U3-01..08).
- NFR Requirements: `construction/decision-registry/nfr-requirements/` (NFR-U3-01..52).
- NFR Design: `construction/decision-registry/nfr-design/` (P-U3-01..09).
- Infrastructure Design: `construction/decision-registry/infrastructure-design/` (INF-U3-01..06).

**AUTONOMIA-01:** las verificaciones **estáticas** y las de integración con Testcontainers
(contenedores locales, sin clúster) corren en CI; las que necesitan el clúster las ejecuta
**un operador en kind** después de un PR aprobado (Paso 18), con la evidencia adjunta al PR.

### Estructura de destino

```text
vectra-risk/decision-registry/
|-- Makefile                     # check
|-- pyproject.toml               # miembro del workspace uv
|-- src/vectra_registry/
|   |-- chain.py  verify.py  projections.py      # funciones puras
|   |-- append.py  dossier.py  api.py  pools.py  health.py
|   |-- checkpoint.py  archive.py  vault.py  worm.py
|   `-- cli.py                                    # vectra-registry
|-- migrations/                  # Alembic: esquema, particiones, roles, trigger, génesis
|-- chart/                       # servicio + CronJobs
|-- vault-policies/              # HCL versionado
|-- observability/               # PrometheusRule + tests
|-- runbooks/
|-- docs/                        # retention.md, capacity.md
`-- tests/  unit/ property/ integration/ examples/ load/ bench/
```

---

## 2. Pasos

### Bloque A — Estructura

- [ ] **Paso 1 — Esqueleto de `decision-registry/`**
  - Directorios de §1; `pyproject.toml` (miembro del workspace, psycopg 3, `cryptography`, `zstandard`, `hvac` o cliente HTTP de Transit vía `deps.call`); `Makefile` con `check`; perfiles de Hypothesis de U0; contrato de import-linter: `chain`, `verify` y `projections` sin E/S.
  - Diseño: NFR-U3-50; P-U3-05.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config decision-registry/.importlinter && make -C decision-registry check` sobre el esqueleto.

### Bloque B — Datos

- [ ] **Paso 2 — Migraciones de `registry-db`**
  - Tabla `registry_entries` (domain-entities §1) **particionada por rango de `seq`**: el año en curso, los dos siguientes y una partición `DEFAULT`.
  - Roles `registry_app`, `registry_verifier`, `registry_health` (`pg_monitor`) y `registry_migrator`, con sus grants: `registry_app` sin `UPDATE`, `DELETE` ni `TRUNCATE`.
  - Trigger `BEFORE UPDATE OR DELETE OR TRUNCATE`; índices (`case_id`, `idempotency_key` único, `entry_type`); entrada **génesis**.
  - Diseño: BR-U3-01, 02, 10; NFR-U3-31, 42; P-U3-06; INF-U3-05. Historia: US-401.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_migrations.py` (Testcontainers):
    - `UPDATE`, `DELETE` y `TRUNCATE` con `registry_app` → `permission denied`;
    - con el trigger, un `UPDATE` de superusuario → excepción;
    - existe una sola génesis con `seq = 0`;
    - una fila fuera de rango cae en `DEFAULT`.

### Bloque C — Lógica pura

- [ ] **Paso 3 — `chain`**
  - `canonicalize` (JCS de U0), `link(prev_hash, canonical)` y `decode`.
  - Propiedades PBT-U3-04 (punto fijo de JCS) y PBT-U3-05 (verificación con un contrato más nuevo).
  - Diseño: BR-U3-09, 10; domain-entities §1.1.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_chain.py`.

- [ ] **Paso 4 — `verify`**
  - Función pura sobre filas y checkpoints, con los modos `incremental`, `nightly` (cadena de checkpoints + 7 días + muestra del 1 % con semilla registrada), `full` y `range`. Detecta los 6 motivos de BR-U3-12 y devuelve `IntegrityReport`.
  - Propiedades PBT-U3-02 (una manipulación) y PBT-U3-03 (reescritura detectada por checkpoint).
  - Diseño: BR-U3-11, 12; NFR-U3-33. Historia: US-402.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_verify.py decision-registry/tests/unit/test_verify_modes.py`.

- [ ] **Paso 5 — `projections`**
  - Las 4 proyecciones de domain-entities §3; un campo o una proyección no permitidos → `Forbidden`, sin datos parciales.
  - Propiedad PBT-U3-06.
  - Diseño: BR-U3-15. Historia: US-403.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_projections.py`.

- [ ] **Paso 6 — Resumen de la lógica pura**
  - `aidlc-docs/construction/decision-registry/code/business-logic-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit decision-registry --section logic` (BR-U3-09..12 y 15 aparecen en las pruebas).

### Bloque D — Servicio

- [ ] **Paso 7 — Append**
  - Autorización por scope y tipo (BR-U3-03), tamaño de 64 KiB (BR-U3-07), idempotencia dentro del lock (BR-U3-06), `recorded_at` no decreciente y margen de `occurred_at` (BR-U3-05).
  - Lock, hash, `INSERT` y commit con `synchronous_commit = remote_apply` (BR-U3-04).
  - Tiempos límite de P-U3-02, sin reintento interno; pools de P-U3-04 (`append` 2, `dossier` 1, `projections` 1, `health` 1).
  - Propiedades PBT-U3-07 y 08, y la **stateful PBT-U3-01** (`RuleBasedStateMachine` contra primaria + standby de Testcontainers).
  - Diseño: BR-U3-03..07, 16; NFR-U3-20, 51; P-U3-02, 04; INF-U3-04. Historias: US-401, US-404.
  - **Aceptación**:
    - `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_append_*.py decision-registry/tests/integration/test_append.py`;
    - standby pausado → 503 en ≤ 2,5 s; reintento con la misma llave → ack original y una sola fila;
    - los 5 tipos de evento de gobierno con actor y rol (US-404).

- [ ] **Paso 8 — Proyecciones, expediente y verificación bajo demanda**
  - `GET /v1/entries` con la proyección del consumidor (réplica). Filtros (`EntryFilter`): `case_id`, `entry_type`, `seq`, rango de `recorded_at`; la proyección `explanation` exige `case_id` y `seq` y devuelve como máximo una entrada (BR-U7-13; agregado por U7 NFR Design Q3).
  - `GET /v1/dossiers/{case_id}` (primaria, solo `cro`/`cumplimiento`), con verificación `range` y `last_full_verification`.
  - `POST /v1/integrity-checks` (`cro` con MFA; una sola `full` a la vez → 409).
  - Diseño: BR-U3-13..15; NFR-U3-21, 43; P-U3-05. Historias: US-402, US-403.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_dossier.py test_queries.py test_integrity_api.py`:
    - la narrativa del expediente es byte a byte igual a la guardada;
    - un `analista` recibe 403;
    - un tramo alterado → `not_verified`;
    - proyección `explanation` con un `seq` de otro caso → página vacía (explainability responde 409);
    - un caso con dos `recommendation` y una `human_decision` que referencia la segunda → la primera sale `no_entregada` (P-U7-03, agregado por U7 NFR Design Q3).

- [ ] **Paso 9 — Readiness y contratos de rutas**
  - Readiness con `registry_health` (standby síncrono, cache de 5 s).
  - Las rutas de U3 se registran como `RouteContract` en el registro de contratos de U0, con scopes, roles y MFA.
  - Diseño: P-U3-01; NFR-U3-11; P-U0-12.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_health.py` (standby detenido → `/readyz` 503 en ≤ 5 s); `make -C contracts openapi && git diff --exit-code contracts/openapi/` incluye las rutas de U3.

- [ ] **Paso 10 — Resumen del servicio**
  - `aidlc-docs/construction/decision-registry/code/api-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit decision-registry --section api` (BR-U3-01..07 y 13..16 aparecen en las pruebas).

### Bloque E — CLI y Jobs

- [ ] **Paso 11 — CLI `vectra-registry`**
  - `verify --mode incremental|nightly|full|range [--source db|archive]` con códigos 0/1/2.
  - `checkpoint`: cabeza → firma Transit → append con `idempotency_key = checkpoint:<hora>` → export WORM y lectura de vuelta.
  - `archive --month`: NDJSON + zstd, manifiesto firmado, subida, descarga y `verify --source archive`.
  - Diseño: BR-U3-08, 11, 13; NFR-U3-04, 12, 40; P-U3-03, 07. Historia: US-402.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_cli.py`, con Testcontainers (PostgreSQL, MinIO con object lock y Vault dev):
    - `exit 0` en una cadena íntegra, `1` en una alterada, `2` con la base caída;
    - dos `checkpoint` en la misma hora → uno;
    - archivo alterado → `exit 1`;
    - Vault caído → los appends siguen y el checkpoint falla con alerta.

- [ ] **Paso 12 — CronJobs, identidades y políticas de la bóveda**
  - Los 5 CronJobs (INF-U3-03): `concurrencyPolicy: Forbid`, `activeDeadlineSeconds`, sidecar nativo de Linkerd, prioridades.
  - ServiceAccounts y `ExternalSecret` por identidad (P-U3-08); políticas HCL versionadas (firma solo para checkpoint y archivo).
  - En U1, el Paso 13 (`restore-drill`) reemplaza su doble de prueba por esta CLI.
  - Diseño: P-U3-03, 05, 07, 08; INF-U3-02, 03.
  - **Aceptación**:
    - `helm template` + `conftest test decision-registry/chart/` (límites de tiempo, `Forbid`, anotación de sidecar nativo, sin Secret plano);
    - `uv run pytest decision-registry/tests/unit/test_vault_policies.py` (solo las identidades de checkpoint y archivo tienen `sign`; la API ninguna).

### Bloque F — Despliegue y operación

- [ ] **Paso 13 — Chart del servicio, buckets y flujos**
  - Deployment: HPA de 2 a 6, spread por zona, PDB, `vectra-critical`, recursos de INF-U3-03.
  - Values por entorno: buckets (MinIO en kind; S3 del banco en staging y prod) y URL de Transit.
  - Agregar a `platform/network/flows.yaml` de U1: F42, F96, F97, F98 (kind), F77, F78, F79, F99, y F75 ampliado.
  - Diseño: NFR-U3-11, 41; INF-U3-01..06.
  - **Aceptación**: `helm template` + `conftest`; `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` (los IDs F77–F79 y F96–F99 de `component-dependency.md` están en `flows.yaml`).

- [ ] **Paso 14 — Alertas y runbooks**
  - `PrometheusRule` con las 11 alertas de P-U3-09; runbooks: `registry-chain-broken`, `registry-default-partition-used`, `checkpoint-missing`, `archive-export-failed`, `registry-partition-missing`, `registry-append-pool-saturated`, `registry-volume-fill-forecast`, `registry-growth-above-forecast` y uno de rotación de la llave de checkpoints (*cross-signing*).
  - `docs/retention.md` (NFR-U3-01..04, con los **[VERIFICAR]**) y `docs/capacity.md` (§3.1 de NFR: volumen esperado frente a capacidad de diseño).
  - Diseño: P-U3-09; NFR-U3-01..04, 30..34.
  - **Aceptación**: `promtool test rules decision-registry/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root decision-registry`; `test -s decision-registry/docs/retention.md && test -s decision-registry/docs/capacity.md`.

- [ ] **Paso 15 — Applications de GitOps**
  - Application en la wave 5 (Job de migración como hook + servicio + CronJobs).
  - Diseño: P-U1-12.
  - **Aceptación**: `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync`.

### Bloque G — Calidad

- [ ] **Paso 16 — Cobertura, mutación y trazabilidad**
  - Cobertura de ramas ≥ 95 % global y **100 %** en `chain`, `verify` y `append`; `mutmut` en `chain` y `verify`; trazabilidad de cada BR-U3 a una prueba.
  - Diseño: NFR-U3-52.
  - **Aceptación**: `uv run pytest decision-registry/tests --cov --cov-branch --cov-fail-under=95`, el umbral por módulo, `uv run mutmut run` sin sobrevivientes fuera de la allowlist, y `uv run python platform/tests/test_traceability.py --unit decision-registry --all`.

- [ ] **Paso 17 — Benchmarks y especificación de carga**
  - Benchmark de la verificación incremental (NFR-U3-22) con Testcontainers en CI.
  - Script k6 del append a 50 entradas/s con expedientes concurrentes (NFR-U3-20, 21; P-U3-04).
  - Generador de 10 años sintéticos (36 M entradas) para el benchmark `nightly` (NFR-U3-23).
  - Diseño: NFR-U3-20..23; P-U3-04.
  - **Aceptación**: `uv run pytest decision-registry/tests/bench -m benchmark` (≤ 30 s); `k6 inspect decision-registry/tests/load/append.js` muestra los umbrales p95/p99; `uv run python decision-registry/tests/bench/gen_synthetic.py --dry-run --years 10` informa 36 M entradas.

### Bloque H — Verificación en kind (con aprobación humana)

- [ ] **Paso 18 — Puerta de aprobación, instalación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–17 aprobado por un humano, sobre U1 y U2 ya instalados en kind.
  - El operador sincroniza la wave 5 y ejecuta, con evidencia:
    1. la prueba de carga k6 (append p95 ≤ 50 ms y p99 ≤ 200 ms a 50 entradas/s; expediente ≤ 2 s);
    2. el benchmark `nightly` con 10 años sintéticos (≤ 30 min);
    3. el fallo de zona: escrituras bloqueadas, readiness en 503, sin acks sin commit;
    4. la bóveda caída: appends normales y `CheckpointMissing`;
    5. el S3 caído: `CheckpointExportFailed`;
    6. la manipulación de superusuario (trigger deshabilitado + recálculo) → `RegistryChainBroken` en la siguiente `incremental`;
    7. `restore-drill` con la CLI real, verificando contra los checkpoints externos.
  - Historias: US-401, US-402, US-403.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con comando, salida y resultado esperado contra el obtenido.

### Bloque I — Cierre

- [ ] **Paso 19 — Frontend: N/A**
  - U3 no tiene interfaz de usuario; el expediente lo muestra la SPA (U10) vía el BFF.
  - **Aceptación**: `test ! -d decision-registry/frontend`.

- [ ] **Paso 20 — Cierre de la unidad**
  - **Aceptación**: `make -C decision-registry check`, que corre en orden las verificaciones estáticas y de integración (Testcontainers) de los Pasos 2–17 y termina en 0. Las de kind (Paso 18) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

Revisada contra las líneas «Diseño» de cada paso antes de presentarla.

| Historia | Pasos |
|---|---|
| US-401 | 2, 7, 18 |
| US-402 | 4, 8, 11, 18 |
| US-403 | 5, 8, 18 |
| US-404 | 7 |

| Diseño | Pasos |
|---|---|
| BR-U3-01, 02 | 2 |
| BR-U3-10 | 2, 3 |
| BR-U3-03..07, 16 | 7 |
| BR-U3-08 | 11 |
| BR-U3-09 | 3 |
| BR-U3-11, 12 | 4, 11 |
| BR-U3-13..15 | 5, 8, 11 |
| NFR-U3-01..04 | 11, 14 |
| NFR-U3-11, 12 | 9, 11, 13 |
| NFR-U3-20..23 | 7, 8, 17 |
| NFR-U3-30..34 | 2, 4, 14 |
| NFR-U3-40..43 | 2, 8, 11, 13 |
| NFR-U3-50..52 | 1, 7, 16 |
| P-U3-01..09 | 1, 2, 7, 8, 9, 11, 12, 14, 17 |
| INF-U3-01..06 | 2, 7, 12, 13 |

| Propiedad | Paso |
|---|---|
| PBT-U3-01 (stateful) | 7 |
| PBT-U3-02, 03 | 4 |
| PBT-U3-04, 05 | 3 |
| PBT-U3-06 | 5 |
| PBT-U3-07, 08 | 7 |

## 4. Cumplimiento de extensiones (plan de tareas U3)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | DDL solo por migración en un sync aprobado (Paso 2); escenarios con clúster ejecutados por el operador (Paso 18) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-05 | Cumple | La API sin egress; F78 con datos seudonimizados y cifrados en la infraestructura del banco; F77, F79 y F99 sin datos de solicitantes (Paso 13) |
| AUTONOMIA-06 | Cumple | Sin ack sin commit síncrono; readiness con standby (Pasos 7, 9) |
| SECURITY-01/05/06/07/08/12/13/14/15 | Cumple | Pasos 2, 5, 7, 8, 11..14 |
| RESILIENCY-05..12, 14, 15 | Cumple | Pasos 7, 9, 11, 13, 14, 18 |
| PBT-01..10 | Cumple | Pasos 3, 4, 5, 7 (incluida la stateful), 16 |
