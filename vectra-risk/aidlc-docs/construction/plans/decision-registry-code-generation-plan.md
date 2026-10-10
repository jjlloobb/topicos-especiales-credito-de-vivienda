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
- Functional Design: `construction/decision-registry/functional-design/` (BR-U3-01..17, PBT-U3-01..09; BR-U3-17 y PBT-U3-09 agregados por el FD de U9).
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
|   |-- checkpoint.py  archive.py  vault.py  worm.py  aggregator.py
|   `-- cli.py                                    # vectra-registry
|-- migrations/                  # Alembic: esquema, particiones, roles, trigger, génesis
|-- chart/                       # servicio + CronJobs
|-- chart-rebuild/               # Application aparte decision-registry-rebuild: Jobs de reconstrucción (revisión del plan de tareas de U9, 2026-10-10)
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
  - Índice de `registry_entries` por `recorded_at` (para el `aggregator reset`; quinta revisión del FD de U9, 2026-10-10).
  - Las cinco tablas derivadas de domain-entities §1.3: `monitoring_daily` (marginales por atributo), `monitoring_entry_totals`, `monitoring_case_index` (solo `case_id`, `counted_seq`, `evaluated_at` y `fixed_by_decision`), `monitoring_invalid` y `monitoring_watermark`, con sus llaves y `CHECK (count >= 0)`. El trigger de solo-anexar no las cubre (BR-U3-02, 17).
  - Rol `registry_aggregator`: `SELECT` sobre `registry_entries` y escritura solo sobre las tablas derivadas, sin `TRUNCATE`. `registry_verifier`: `SELECT` sobre las tablas derivadas salvo `monitoring_case_index`.
  - La `idempotency_key` del checkpoint es `UUIDv5(NS_CHECKPOINT, "checkpoint:<hora UTC>")`, porque la columna es `uuid` (P-U3-03).
  - (Precisado el 2026-10-08 por el FD de U9 y sus revisiones; frase separada en la tercera revisión del FD de U9, 2026-10-10.)
  - Diseño: BR-U3-01, 02, 10; NFR-U3-31, 42; P-U3-06; INF-U3-05. Historia: US-401.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_migrations.py` (Testcontainers):
    - `UPDATE`, `DELETE` y `TRUNCATE` con `registry_app` → `permission denied`;
    - con el trigger, un `UPDATE` de superusuario → excepción;
    - existe una sola génesis con `seq = 0`;
    - una fila fuera de rango cae en `DEFAULT`;
    - `registry_aggregator` intenta `INSERT` o `UPDATE` sobre `registry_entries` → `permission denied`; escribe en `monitoring_daily` → éxito; `registry_app` escribe en `monitoring_daily` → `permission denied`;
    - tabla `integrity_checks` (domain-entities §5.0; revisión del Infrastructure Design de U10, 2026-10-10) con sus `CHECK` (`terminada` ⇔ `report`; `fallida` ⇔ `reason`; `progress_checked ≤ progress_total`) y el índice único parcial de una sola activa: dos filas `pendiente` → `unique_violation`; `terminada` sin `report` → error; `registry_app` hace `UPDATE` → `permission denied`; `registry_verifier` hace `UPDATE` o `INSERT` → `permission denied` (lo comparte la API); `registry_ondemand` hace `UPDATE` de `status` → éxito y de `requested_by` → `permission denied`; nadie hace `DELETE` (segunda revisión del Infrastructure Design de U10, 2026-10-10).

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
  - Las proyecciones de domain-entities §3 (`full`, `explanation`, `metrics`, `monitoring_daily` y `monitoring_freezes`; la `monitoring` por filas se retira porque ya no tiene consumidor, precisado el 2026-10-08 por U9 FD); un campo o una proyección no permitidos → `Forbidden`, sin datos parciales.
  - Propiedad PBT-U3-06.
  - Diseño: BR-U3-15. Historia: US-403.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_projections.py`.

- [ ] **Paso 6 — Resumen de la lógica pura**
  - `aidlc-docs/construction/decision-registry/code/business-logic-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit decision-registry --section logic` (BR-U3-09..12 y 15 aparecen en las pruebas).

### Bloque D — Servicio

- [ ] **Paso 7 — Append**
  - Autorización por scope, tipo y, en `fail_closed`, forma del payload: scoring sin `local_cause` ni `escalated_at`, case solo con `escalated_at` (BR-U3-03). Tamaño de 64 KiB (BR-U3-07). Idempotencia dentro del lock por **campos de negocio**, sin `occurred_at`, `correlation_id` ni `contract_version` (BR-U3-06). `recorded_at` no decreciente. La ventana de ±5 min de `occurred_at` y `check_business_time` (BR-U0-37) se aplican **solo a llaves nuevas**, después de la búsqueda de idempotencia (BR-U3-05) (precisado el 2026-10-06, revisión del FD de U8).
  - Lock, hash, `INSERT` y commit con `synchronous_commit = remote_apply` (BR-U3-04).
  - Tiempos límite de P-U3-02, sin reintento interno; pools de P-U3-04 (`append` 2, `dossier` 1, `projections` 1, `health` 1).
  - Propiedades PBT-U3-07 y 08, y la **stateful PBT-U3-01** (`RuleBasedStateMachine` contra primaria + standby de Testcontainers).
  - Diseño: BR-U3-03..07, 16; NFR-U3-20, 51; P-U3-02, 04; INF-U3-04. Historias: US-401, US-404.
  - **Aceptación**:
    - `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_append_*.py decision-registry/tests/integration/test_append.py`;
    - standby pausado → 503 en ≤ 2,5 s; reintento con la misma llave → ack original y una sola fila;
    - una `recommendation` nueva con `received_at` de hace 30 días (caso que estuvo congelado) y `evaluated_at` de ahora → aceptada: `received_at` no entra en `check_business_time` (revisión del FD de U11, 2026-10-10);
    - reintento con la misma llave 10 min después, con un `occurred_at`, un `correlation_id` y una `contract_version` nuevos → ack original; una llave nueva con `occurred_at` de hace 6 min → 422; una llave nueva con un momento de negocio de hace 8 días → 422 (`check_business_time` de U0); el reenvío de una llave existente con un momento de negocio de hace 8 días → ack original (BR-U3-05/06 precisadas el 2026-10-06);
    - los 5 tipos de evento de gobierno con actor y rol (US-404);
    - `fail_closed` con `escalated_at` desde `registry:append:scoring` → 403; `fail_closed` con `local_cause` (sin `escalated_at`) desde `registry:append:scoring` → 403; `fail_closed` sin `escalated_at` desde `registry:append:case` → 403; cada scope con su forma correcta → aceptado (BR-U3-03 simétrica, precisado el 2026-10-06, revisión del FD de U8).

- [ ] **Paso 8 — Proyecciones, expediente y verificación bajo demanda**
  - `GET /v1/entries` con la proyección del consumidor (réplica). En `metrics` (FD de U11, 2026-10-10; `first_evaluation` agregado en la revisión del FD de U11): `recommendation` con `model_version_id`, `channel`, `received_at`, `attempt` y `first_evaluation`; cada `human_decision` con su recomendación referenciada resuelta en el servidor (o `null`); filtros por `recorded_at` y `seq >`; paginación por clave: `entry_type`, `recorded_from`, `seq_after` y `limit` (≤ 1 000) en orden de `seq`, con `next_seq_after` en la respuesta (NFR Design de U11, 2026-10-10, P-U11-01). Aceptación adicional: una decisión que referencia una recomendación de hace 60 días trae sus campos aunque la consulta solo pida 36 días de `recorded_at`; una que referencia un `freeze` → `recommendation: null`. Filtros (`EntryFilter`): `case_id`, `entry_type`, `seq`, rango de `recorded_at`; la proyección `explanation` exige `case_id` y `seq` y devuelve como máximo una entrada (BR-U7-13; agregado por U7 NFR Design Q3).
  - Gauge `vectra_registry_monitoring_lag_seconds`, calculado cada 60 s con el pool `projections` (BR-U3-17; segunda revisión del FD de U9, 2026-10-08).
  - `POST /v1/monitoring/daily:query` (`registry:read:monitoring`, réplica; solo lectura, con el `MonitoringQuery` de U0 en el cuerpo; sexta revisión del FD de U9, 2026-10-10): `versions` (primer y último día por versión y población), hasta 12 rangos de días (`from_day ≤ to_day`), **sumados en el servidor**, y el `unattributable_range` opcional, del que devuelve un único `unattributable_invalid` (séptima revisión del FD de U9, 2026-10-10); devuelve conteos por rango, `total_entries`, `invalid_entries`, hasta 100 `invalid_seqs`, `watermark_seq` y el atraso; `GET /v1/monitoring/freezes` (BR-U3-17; precisado el 2026-10-08 por U9 FD).
  - `GET /v1/dossiers/{case_id}` (primaria, solo `cro`/`cumplimiento`), con verificación `range` y `last_full_verification`.
  - `POST /v1/integrity-checks` (`cro` con MFA; `IntegrityCheckRequest` con `mode` y, en `range`, `from_seq` y `to_seq`) **solo registra** la solicitud (BR-U3-13b, rediseñada en la revisión del Infrastructure Design de U10, 2026-10-10): sin otra activa → `INSERT` `pendiente` por el pool `dossier` y 202 con `IntegrityCheckRef`; con otra activa de cualquier modo → 200 con la activa y `already_active = true`. `GET /v1/integrity-checks/{id}` (`cro`) con `IntegrityCheckStatus`. Aceptación adicional en `test_integrity_api.py`: sin otra activa → 202 y fila `pendiente`; con una activa → 200 con su `check_id` y sin fila nueva; un `range` sin `from_seq` → 422; un `analista` → 403.
  - Diseño: BR-U3-13..15; NFR-U3-21, 43; P-U3-05. Historias: US-402, US-403.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_dossier.py test_queries.py test_integrity_api.py`:
    - la narrativa del expediente es byte a byte igual a la guardada;
    - un `analista` recibe 403;
    - un tramo alterado → `not_verified`;
    - proyección `explanation` con un `seq` de otro caso → página vacía (explainability responde 409);
    - un caso con dos `recommendation` y una `human_decision` que referencia la segunda → la primera sale `no_entregada` (P-U7-03, agregado por U7 NFR Design Q3);
    - `POST /v1/monitoring/daily:query` con 12 rangos de 90 días responde dentro del tiempo límite del pool `projections` (2 s) y con unos miles de filas, porque suma en el servidor; una consulta `explanation` concurrente no supera su límite (segunda revisión del FD de U9, 2026-10-08);
    - `registry_verifier` no puede leer `monitoring_case_index` (segunda revisión del FD de U9, 2026-10-08);
    - gauge `vectra_registry_monitoring_lag_seconds`: 0 con la marca igual a la cabeza y el registro sin tráfico durante 2 h; con una entrada pendiente de hace 31 min → > 1800 (tercera revisión del FD de U9, 2026-10-10);
    - `GET /v1/monitoring/freezes`: un `freeze` con una `frozen_resolution` `reactivar` → `resolution.action = reactivar` y `resolution.recorded_at` = el `recorded_at` de la entrada (tercera revisión del FD de U9, 2026-10-10);
    - `versions` devuelve `first_day` y `last_day` por versión y población; `totals` trae una fila por `range_id` (tercera revisión del FD de U9, 2026-10-10);
    - una solicitud con 13 rangos → 422 (tercera revisión del FD de U9, 2026-10-10);
    - `unattributable_invalid`: un solo valor sobre el `unattributable_range` pedido; 0 sin ese rango; no aparece en `totals` (sexta revisión del FD de U9, 2026-10-10);
    - un rango o un `unattributable_range` con `from_day > to_day` → 422 (séptima revisión del FD de U9, 2026-10-10).

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
  - `checkpoint`: cabeza → firma Transit → append con `idempotency_key = UUIDv5(NS_CHECKPOINT, "checkpoint:<hora UTC>")` (la columna es `uuid`) → export WORM y lectura de vuelta.
  - `archive --month`: NDJSON + zstd, manifiesto firmado, subida, descarga y `verify --source archive`.
  - `aggregator run` (BR-U3-17): el comando del CronJob `registry-aggregator`; itera lotes hasta la cabeza o 240 s (quinta revisión del FD de U9, 2026-10-10); con `--until-head` itera sin tope de tiempo (Job de reconstrucción con `runId` del runbook `monitoring-rebuild`; sexta revisión del FD de U9, 2026-10-10).
  - `aggregator reset` (BR-U3-17): solo con `registry_migrator`; la usa el runbook `monitoring-rebuild`.
  - Diseño: BR-U3-08, 11, 13, 17; NFR-U3-04, 12, 40; P-U3-03, 07. Historia: US-402.
  - **Aceptación**: `uv run pytest decision-registry/tests/integration/test_cli.py`, con Testcontainers (PostgreSQL, MinIO con object lock y Vault dev):
    - `exit 0` en una cadena íntegra, `1` en una alterada, `2` con la base caída;
    - dos `checkpoint` en la misma hora → uno;
    - archivo alterado → `exit 1`;
    - Vault caído → los appends siguen y el checkpoint falla con alerta;
    - `aggregator reset` con `registry_migrator` vacía las cuatro tablas, deja `id = 1` con `last_seq` justo antes de la primera entrada de los últimos 181 días (tercera revisión del FD de U9, 2026-10-10); con `registry_aggregator` → `permission denied` (revisión del FD de U9, 2026-10-08).

- [ ] **Paso 12 — CronJobs, identidades y políticas de la bóveda**
  - Los 5 CronJobs (INF-U3-03: `registry-checkpoint`, `registry-verify-incremental`, `registry-verify-nightly`, `registry-verify-ondemand`, que reemplaza a `registry-verify-full`, y `registry-archive`; segunda revisión del Infrastructure Design de U10, 2026-10-10): `concurrencyPolicy: Forbid`, `activeDeadlineSeconds`, sidecar nativo de Linkerd, prioridades.
  - **`registry-verify-ondemand`** (BR-U3-13b; revisión del Infrastructure Design de U10, 2026-10-10): cada minuto, `Forbid`, `activeDeadlineSeconds: 21600`, `vectra-low`, identidad `registry-verify`; `vectra-registry verify --ondemand` hace el barrido, toma la `pendiente` y verifica en tramos de ≤ 10 000 entradas con latido. Ya no hay `registry-verify-full`: el CronJob `registry-verify-ondemand` encola la `full` mensual cuando la última `terminada` tiene más de 30 días (segunda revisión del Infrastructure Design de U10, 2026-10-10). Identidades: `registry_verifier` (réplica) y `registry_ondemand` (primaria, solo `integrity_checks`). Aceptación adicional en `tests/integration/test_ondemand.py` (Testcontainers con primaria y standby, y doble de la bóveda y del bucket): pendiente → `terminada` con `integra`, incluidos los pasos 5 y 6 de BR-U3-12; matar el proceso a mitad → la corrida siguiente la marca `fallida` con `interrumpida` y el cupo se libera; `result = error` → `fallida` con `error_de_ejecucion`; con la última `full` de hace 31 días y otra verificación activa → la `full` se encola en la primera corrida libre; sin activa → se encola y corre en la misma corrida; un tramo cancelado → reintento y termina; `last_full_verification` del expediente = la `full` `terminada` más reciente.
  - Plantillas de los Jobs de reconstrucción con `runId` del runbook `monitoring-rebuild`, en `decision-registry/chart-rebuild/` (revisión del plan de tareas de U9, 2026-10-10; INF-U3-03; séptima revisión del FD de U9, 2026-10-10): `registry-aggregator-rebuild` (`aggregator run --until-head`, rol `registry_aggregator`, `activeDeadlineSeconds: 5400`, `backoffLimit: 0`, `vectra-high`, sidecar nativo) y `registry-aggregator-reset` (`aggregator reset`, credencial de `registry_migrator` por ESO, flujo F108, `activeDeadlineSeconds: 300`, `backoffLimit: 0`, `vectra-normal`, sidecar nativo); los dos suman en la cuota de `vectra-app` mientras corren (U1 Paso 6; octava revisión del FD de U9, 2026-10-10). El `ExternalSecret` de `registry_migrator` del reset va en `chart-rebuild/` y solo con `runId`, en la wave anterior al reset (BR-U3-17; revisión del FD de U10, 2026-10-10, B11). Se renderizan como **Jobs normales** solo con el value `monitoringRebuild.runId` (reset en una `sync-wave` anterior al rebuild, sin `ttlSecondsAfterFinished`), y los dos comandos toman el *advisory lock* de la reconstrucción (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10). Aceptación adicional: `helm template` sin `runId` no renderiza los Jobs y con `runId` los renderiza en orden; en Testcontainers, dos `aggregator reset` a la vez → el segundo termina con error sin cambios; un reset durante un `run --until-head` → error; un reset con un lote del CronJob en curso espera el `FOR UPDATE` y los conteos finales son correctos.
  - **Job `x06-probe-<runId>`** en `decision-registry/chart-rebuild/` (U12 INF-U12-02; Infrastructure Design de U12, 2026-10-10): solo con los values de kind y `probes.runId`; credencial de `registry_app` del `ExternalSecret` existente; intenta `UPDATE registry_entries` y termina con éxito solo con `permission denied`; `backoffLimit: 0`, sidecar nativo, **sin** `ttlSecondsAfterFinished` (se poda al cambiar `probes.runId`); flujo F111. `probes.runId` y `monitoringRebuild.runId` son independientes: sin ninguno de los dos, `chart-rebuild/` no renderiza recursos, y fijar uno no renderiza los del otro. `conftest`: no aparece con los values de staging ni de producción; con solo `probes.runId` no aparecen los Jobs de reconstrucción, y viceversa (revisión del Infrastructure Design de U12, 2026-10-10).
  - **Sexto CronJob, `registry-aggregator`** (cada 5 min, `Forbid`, `activeDeadlineSeconds: 280`, `vectra-high`, sidecar nativo de Linkerd, rol `registry_aggregator`, F107; itera lotes hasta la cabeza o 240 s; segunda revisión del FD de U9, 2026-10-08): BR-U3-17, con la regla de una recomendación por caso, las inválidas y la marca de agua en la misma transacción que los conteos; métrica del atraso para `MonitoringAggregatorStale` (precisado el 2026-10-08 por U9 FD).
  - ServiceAccounts y `ExternalSecret` por identidad (P-U3-08); políticas HCL versionadas (firma solo para checkpoint y archivo).
  - En U1, el Paso 13 (`restore-drill`) reemplaza su doble de prueba por esta CLI.
  - Diseño: BR-U3-17; PBT-U3-09; NFR-U3-24, 35, 42; P-U3-03, 05, 07, 08; INF-U3-02, 03 (tercera revisión del FD de U9, 2026-10-10).
  - **Aceptación**:
    - `helm template` + `conftest test decision-registry/chart/ decision-registry/chart-rebuild/` (límites de tiempo, `Forbid`, anotación de sidecar nativo, sin Secret plano; en `chart-rebuild/`, sin `runId` no hay ningún recurso y con `runId` el orden de waves es `ExternalSecret` → reset → rebuild) (revisión del FD de U10, 2026-10-10, B11);
    - `uv run pytest decision-registry/tests/unit/test_vault_policies.py` (solo las identidades de checkpoint y archivo tienen `sign`; la API ninguna);
    - `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_aggregator.py decision-registry/tests/integration/test_aggregator.py`: PBT-U3-09; matar el proceso entre lotes y reanudar → mismos conteos; 20 000 entradas pendientes → la misma corrida llega a la cabeza; restar relee las etiquetas de `registry_entries` por `counted_seq`; purga: filas de 181 días borradas y de 179 días intactas, y en `monitoring_case_index` por `evaluated_at`; `aggregator run --until-head` con 20 000 entradas pendientes → llega a la cabeza sin el tope de 240 s; con el CronJob y el Job solapados (sin suspender), el `FOR UPDATE` serializa los lotes y los conteos no cambian; `conftest` de las plantillas de los dos Jobs (séptima revisión del FD de U9, 2026-10-10); una `human_decision` que referencia un `seq` inexistente → fila no atribuible y `unattributable_invalid` = 1 en la proyección (quinta revisión del FD de U9, 2026-10-10); una que referencia una entrada `freeze` → igual que inexistente; una sobre una recomendación inválida → el caso queda fijado con `counted_seq = NULL` y una recomendación válida posterior no suma en `modelo` (sexta revisión del FD de U9, 2026-10-10); `monitoring_freezes` con un `reactivar` (tercera revisión del FD de U9, 2026-10-10); una `human_decision` que referencia una recomendación anterior → resta la más reciente y suma la referenciada; una entrada con `region` fuera del catálogo → cuenta como inválida con su `seq`.

### Bloque F — Despliegue y operación

- [ ] **Paso 13 — Chart del servicio, buckets y flujos**
  - Deployment: HPA de 2 a 6, spread por zona, PDB, `vectra-critical`, recursos de INF-U3-03.
  - Values por entorno: buckets (MinIO en kind; S3 del banco en staging y prod) y URL de Transit.
  - `ServiceMonitor` del puerto de métricas del servicio, que incluye el gauge `vectra_registry_monitoring_lag_seconds` (F60; sexta revisión del FD de U9, 2026-10-10).
  - Agregar a `platform/network/flows.yaml` de U1: F111 (`x06-probe` → `registry-db-rw`, solo kind; revisión del Infrastructure Design de U12, 2026-10-10), F42, F96, F97, F98 (kind), F77, F78, F79, F99, F107 (`registry-aggregator` y el Job `registry-aggregator-rebuild` → `registry-db-rw`), F108 (Job `registry-aggregator-reset` → `registry-db-rw`; octava revisión del FD de U9, 2026-10-10) y F75 ampliado.
  - Diseño: NFR-U3-11, 41; INF-U3-01..06.
  - **Aceptación**: `helm template` + `conftest`; `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` (los IDs F77–F79, F96–F99, F107 y F108 de `component-dependency.md` están en `flows.yaml`, y F60 admite el scrape de Prometheus al puerto de métricas de `decision-registry-service`; sexta revisión del FD de U9, 2026-10-10); `conftest`: el `ServiceMonitor` existe y apunta al puerto de métricas.

- [ ] **Paso 14 — Alertas y runbooks**
  - `PrometheusRule` con las 13 alertas de P-U3-09 (incluidas `RegistryOnDemandCheckFailed` y `RegistryOnDemandCheckStuck`, con sus runbooks `registry-ondemand-check-failed` y `registry-ondemand-check-stuck`; revisión del Infrastructure Design de U10, 2026-10-10), incluida `MonitoringAggregatorStale` (que también delata un rebuild fallido, BR-U3-17; runbook `monitoring-rebuild` con el paso de silencio de `MonitoringAggregatorStale` y `MonitoreoSesgoDetenido` (U9) y su vencimiento, más la comprobación de `vectra_bias_last_run_failure{reason}` = `agregador_atrasado` antes de darla por esperada (revisión del FD de U10, 2026-10-10, B12); revisión del NFR Requirements de U9, 2026-10-10 (segunda)) (BR-U3-17: `max(vectra_registry_monitoring_lag_seconds) > 1800` durante 5 min o la serie ausente 15 min; segunda revisión del FD de U9, 2026-10-08); runbooks: `monitoring-aggregator-stale`, `monitoring-rebuild`, `registry-chain-broken`, `registry-default-partition-used`, `checkpoint-missing`, `archive-export-failed`, `registry-partition-missing`, `registry-append-pool-saturated`, `registry-volume-fill-forecast`, `registry-growth-above-forecast` y uno de rotación de la llave de checkpoints (*cross-signing*).
  - `docs/retention.md` (NFR-U3-01..04, con los **[VERIFICAR]**) y `docs/capacity.md` (§3.1 de NFR: volumen esperado frente a capacidad de diseño).
  - Diseño: P-U3-09; NFR-U3-01..04, 30..34.
  - **Aceptación**: `promtool test rules decision-registry/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root decision-registry`; `test -s decision-registry/docs/retention.md && test -s decision-registry/docs/capacity.md`.

- [ ] **Paso 15 — Applications de GitOps**
  - Application en la wave 5 (Job de migración como hook + servicio + CronJobs).
  - **Application aparte `decision-registry-rebuild`** (revisión del Infrastructure Design de U9, 2026-10-10) en la **wave 6**, después de la de U3 en la wave 5, sin auto-sync, con el chart de los Jobs de reconstrucción (`decision-registry/chart-rebuild/`) (solo con `monitoringRebuild.runId`) (revisión del FD de U10, 2026-10-10, B11).
  - `rebuild-history.yaml` en el repositorio GitOps. El check del `runId` es un workflow del **repositorio GitOps** (`.github/workflows/rebuild-runid-check.yml`), obligatorio en la protección de `main`, que corre en cada PR que toca los values de `decision-registry-rebuild`: rechaza un `runId` repetido, uno que no tenga el formato `AAAAMMDD-HHMM` o uno que el mismo PR no agregue a `rebuild-history.yaml`.
  - Diseño: P-U1-12; BR-U3-17.
  - **Aceptación**: `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync`; el render de `decision-registry` no contiene los Jobs de reconstrucción y el de `decision-registry-rebuild` sí (con `runId`); `uv run pytest decision-registry/tests/unit/test_rebuild_runid_check.py` (formato inválido → error; `runId` ya en el historial → error; nuevo sin agregarlo al historial → error; nuevo y agregado → aceptado); `actionlint` del workflow del repositorio GitOps; `test_waves.py` comprueba que `decision-registry-rebuild` está en la wave 6.

### Bloque G — Calidad

- [ ] **Paso 16 — Cobertura, mutación y trazabilidad**
  - Cobertura de ramas ≥ 95 % global y **100 %** en `chain`, `verify` y `append`; `mutmut` en `chain` y `verify`; trazabilidad de cada BR-U3 a una prueba.
  - Diseño: NFR-U3-52.
  - **Aceptación**: `uv run pytest decision-registry/tests --cov --cov-branch --cov-fail-under=95`, el umbral por módulo, `uv run mutmut run` sin sobrevivientes fuera de la allowlist, y `uv run python platform/tests/test_traceability.py --unit decision-registry --all`.

- [ ] **Paso 17 — Benchmarks y especificación de carga**
  - Benchmark de la verificación incremental (NFR-U3-22) con Testcontainers en CI.
  - Script k6 del append a 50 entradas/s con expedientes concurrentes (NFR-U3-20, 21; P-U3-04).
  - Generador de 10 años sintéticos (36 M entradas) para el benchmark `nightly` (NFR-U3-23).
  - Benchmarks del agregador (NFR-U3-24, 35; tercera revisión del FD de U9, 2026-10-10): reconstrucción de ~1,8 M entradas sintéticas (181 días a 10 000/día) en ≤ 1 h; atraso p95 ≤ 10 min con 50 entradas/s y corridas cada 5 min; `monitoring_daily` con 12 rangos de 90 días p95 ≤ 200 ms; tamaño de las tablas derivadas con 180 días y 3 versiones (< 350 000 filas en `monitoring_daily`, ≈ 360 000 en `monitoring_case_index`).
  - Diseño: NFR-U3-20..24, 35; P-U3-04.
  - **Aceptación** (quinta revisión del FD de U9, 2026-10-10, separada por benchmark):
    - `uv run pytest decision-registry/tests/bench/test_verify_incremental.py -m benchmark`: verificación incremental ≤ 30 s (NFR-U3-22);
    - `uv run pytest decision-registry/tests/bench/test_aggregator.py -m benchmark` (CI escalado): 100 000 entradas en el tiempo que, extrapolado, da ≤ 1 h para 1,8 M; pico de memoria del proceso ≤ 70 % del límite de INF-U3-03 con el lote por omisión (si no, se reduce el lote); `monitoring_daily` con 12 rangos p95 ≤ 200 ms; tamaño de las tablas con 180 días y 3 versiones;
    - la reconstrucción completa de ~1,8 M entradas y el atraso p95 ≤ 10 min se miden en kind (Paso 18);
    - `k6 inspect decision-registry/tests/load/append.js` muestra los umbrales p95/p99; `uv run python decision-registry/tests/bench/gen_synthetic.py --dry-run --years 10` informa 36 M entradas.

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
    7. `restore-drill` con la CLI real, verificando contra los checkpoints externos;
    8. agregador: suspender el CronJob 35 min → `MonitoringAggregatorStale` y corridas de bias fallidas por atraso; reanudar → atraso en 0; runbook `monitoring-rebuild` (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10): PR con un `runId` nuevo en la Application `decision-registry-rebuild` y sync manual con prune → Argo CD aplica el reset, espera a que termine y aplica el rebuild → reconstrucción de los últimos 181 días en ≤ 1 h con conteos iguales a los anteriores; se mide si el sync queda en curso hasta el fin del rebuild; un sync posterior con el mismo `runId` no repite nada; un `runId` nuevo poda los Jobs del anterior; durante el rebuild, un sync o un rollback de `decision-registry` no espera al rebuild; un rebuild que vence a los 90 min → el CronJob termina la reconstrucción y el atraso llega a 0; el runbook silencia `MonitoringAggregatorStale` y `MonitoreoSesgoDetenido` (U9) con vencimiento de 2 h y el `runId`; un rebuild que falla a propósito → las dos vuelven al vencer el silencio (revisión del plan de tareas de U9, 2026-10-10); atraso p95 ≤ 10 min durante la prueba de carga (NFR-U3-24).
    9. verificación bajo demanda (revisión del Infrastructure Design de U10, 2026-10-10): el CRO pide una `full` desde la consola → `terminada` con `integra`; borrar el pod de `registry-verify-ondemand` a mitad → `fallida` con `interrumpida` en ≤ 3 min y `RegistryOnDemandCheckFailed`; durante una `full`, la carga de append mantiene el p99 ≤ 200 ms, también con una creación de partición simultánea (lectura en tramos cortos con `remote_apply`);
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
| BR-U3-17 | 2, 5, 8, 11, 12, 13, 14, 17, 18 |
| NFR-U3-01..04 | 11, 14 |
| NFR-U3-11, 12 | 9, 11, 13 |
| NFR-U3-20..23 | 7, 8, 17 |
| NFR-U3-24 | 8, 12, 17, 18 |
| NFR-U3-30..34 | 2, 4, 14 |
| NFR-U3-35 | 2, 12, 17, 18 |
| NFR-U3-40..43 | 2, 8, 11, 12, 13 |
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
| PBT-U3-09 | 12 |

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
