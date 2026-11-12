# Resumen del servicio — U3 `decision-registry`

Bloque D del plan (Pasos 7 a 10). El servicio es la app de `create_app` de U0 (`vectra_common`) con las siete rutas del
`RouteContract` de `decision-registry-service` (`vectra_contracts.routes`, ya versionadas en
`contracts/openapi/decision-registry-service.yaml`). La autenticación, los scopes y roles, el MFA, el límite de cuerpo y los
`Problem` los pone la fábrica; el servicio solo aporta los handlers y el ciclo de vida. Hacia la base usa `psycopg` 3 async: `deps.call`
es para HTTP y la única dependencia HTTP de la unidad (la bóveda) es de los CronJobs, no de la API (P-U3-08).

## Qué reglas cubre cada módulo

| Reglas | Archivo | Pruebas |
|---|---|---|
| BR-U3-01, 02 (solo `INSERT` y `SELECT`; segunda barrera) | `migrations/versions/0001_registry_entries.py` (grants y trigger); el servicio solo usa `registry_app` | `tests/integration/test_append.py` (`test_br_u3_01_*`, `test_br_u3_02_*`), `tests/integration/test_migrations.py` |
| BR-U3-03 (escritores por scope y tipo; `fail_closed` simétrico) | `src/vectra_registry/append.py` (`authorize`, `scope_permits`) | `tests/integration/test_append.py` (`test_br_u3_03_*`), `tests/unit/test_append_rules.py` |
| BR-U3-04 (lock, hash, `INSERT`, `COMMIT` con `remote_apply`) | `src/vectra_registry/append.py` (`append_entry`, `_work`, `_commit`), `src/vectra_registry/locks.py` | `tests/integration/test_append.py` (`test_br_u3_04_*`, `test_p_u3_02_*`), `tests/property/test_append_stateful.py` (PBT-U3-01) |
| BR-U3-05 (`recorded_at` no decreciente; ventana de ±5 min; `check_business_time` solo en llaves nuevas) | `append.py` (`next_recorded_at`, `check_window`, `check_business`) | `test_append.py` (`test_br_u3_05_*`), `tests/property/test_append_time.py` (PBT-U3-07, 08) |
| BR-U3-06 (idempotencia por campos de negocio) | `append.py` (`BUSINESS_FIELDS`, `same_business`) | `test_append.py` (`test_br_u3_06_*`, `test_f_05_*`), `test_append_stateful.py` |
| BR-U3-07 (64 KiB; métrica de tamaño) | `append.py` (`MAX_CANONICAL`, `ENTRY_SIZE`) | `test_append.py` (`test_br_u3_07_*`) |
| BR-U3-13, 13b (resultado y verificación bajo demanda asíncrona) | `src/vectra_registry/dossier.py` (`request_check`, `check_status`) | `tests/integration/test_integrity_api.py`, `test_dossier.py` (`test_br_u3_13_*`) |
| BR-U3-14 (expediente y `delivery_status`) | `dossier.py` (`build_dossier`), `projections.delivery_status` | `tests/integration/test_dossier.py` |
| BR-U3-15 (proyecciones por consumidor, 403 sin datos parciales) | `src/vectra_registry/queries.py` (`list_entries`, `resolve_consumer`) sobre `projections.py` | `tests/integration/test_queries.py`, `tests/property/test_projections.py` |
| BR-U3-16 (actores de los eventos de gobierno, US-404) | `append.py` (`check_governance_actor`) | `test_append.py` (`test_br_u3_16_*`) |
| BR-U3-17 (lectura del agregador: `daily:query`, `freezes`, atraso) | `queries.py` (`monitoring_daily`, `monitoring_freezes`, `monitoring_lag`), `health.py` (`Gauges`) | `test_queries.py` (`test_br_u3_17_*`) |
| P-U3-01 (readiness con standby síncrono, cache de 5 s) | `src/vectra_registry/health.py` (`Health`, `probe`) | `tests/integration/test_health.py` |
| P-U3-02, 04 (tiempos límite y pools) | `append.py` (constantes), `src/vectra_registry/pools.py` | `test_append.py` (`test_p_u3_02_*`, `test_p_u3_04_*`) |
| P-U0-12 (rutas como `RouteContract`) | `api.py` (`handlers`, `create_service_app`) | `tests/unit/test_routes.py` |

## Rutas

| Ruta | Quién | Pool | Qué hace |
|---|---|---|---|
| `POST /v1/entries` | `registry:append:{case,scoring,governance}` (`any_scopes`) | `append` (primaria) | `authorize` (403) -> `check_governance_actor` -> tamaño (413) -> transacción: lock, búsqueda de la llave (ack original o 409), ventana y `check_business_time` solo en llaves nuevas (422), cabeza, `recorded_at`, `canonical`, `hash`, `INSERT`, commit `remote_apply`. 200 con `RegistryAck` |
| `GET /v1/entries` | `registry:read:{explanation,metrics,monitoring}` (`any_scopes`) | `projections` (réplica) | Proyección del consumidor (`explanation`, `metrics`, `monitoring_freezes`); `Page` con `next_seq_after`. Una proyección que ningún scope permite (incluida `full`) es 403 |
| `POST /v1/monitoring/daily:query` | `registry:read:monitoring` (`read_only`) | `projections` | `MonitoringWindow`: conteos sumados en el servidor. Tope por solicitud `QUERY_BUDGET_S` (`queries.py`), derivado del tiempo límite del pool `projections` (`POOL_SIZES`, 2 s) y contado desde que la solicitud obtiene la conexión: antes de cada sentencia, `statement_timeout` = mínimo entre `STATEMENT_TIMEOUT_MS` y lo que queda del presupuesto. Pasarse es 504 `deadline_exceeded` (`DependencyTimeout`) y la conexión vuelve al pool utilizable (U03-T07). La sentencia de rango va sin preparar (el plan genérico degrada la forma sin versión) |
| `GET /v1/monitoring/freezes` | `registry:read:monitoring` | `projections` | `FreezeRecord[]` con las `frozen_resolution` posteriores de la versión |
| `GET /v1/dossiers/{case_id}` | `cro`, `cumplimiento` | `dossier` (primaria) | `RegistryDossier` con verificación `range` y `last_full_verification` |
| `POST /v1/integrity-checks` | `cro` con MFA | `dossier` (primaria) | Solo registra: 202 con `IntegrityCheckRef`, o 200 con la activa y `already_active = true` |
| `GET /v1/integrity-checks/{id}` | `cro` | `dossier` | `IntegrityCheckStatus` |

`/readyz` y `/healthz` van en el puerto 8081 (`app.state.ops_app`). `/readyz` es 200 solo si la primaria responde y hay al menos un
standby `sync` o `quorum` transmitiendo (rol `registry_health`); el resultado vale 5 s y uno más viejo cuenta como no listo.

## Decisiones del Bloque D (el diseño no las fija o las corrige)

| Decisión | Razón |
|---|---|
| `statement_timeout` **no** cubre la espera del commit síncrono: PostgreSQL lo desactiva antes de confirmar. El tope de 2 s lo pone el servicio (`_commit`): al vencer pide `cancel_safe`, el servidor confirma en local con un `WARNING` y suelta el lock, y el servicio responde 503. La fila queda escrita; el reintento con la misma llave la resuelve | P-U3-02 decía «`statement_timeout` (incluye el commit síncrono)»; la prueba con el standby pausado lo contradijo (el 503 llegaba a los 2,5 s del tope total) |
| Un reintento idempotente emite un mensaje transaccional en el WAL (`pg_logical_emit_message`) antes de confirmar, para que su commit espere a la réplica: el ack original no sale hasta que la fila esté en el standby | Sin eso, el reintento de un commit que se canceló por tiempo daría el ack con la fila solo en la primaria |
| BR-U3-16 se aplica en el append: un evento de gobierno de una persona exige `actor.role` (422); un actor de servicio o sistema solo en las excepciones listadas (`bias-monitoring-job`, `model-validation-job`, `governance-service`) (403) | El diseño lo pide; U0 solo valida `acr` y `auth_time` |
| La unicidad de la llave se resuelve por la búsqueda dentro del lock; si una escritura ajena al lock la gana, el `UniqueViolation` repite la búsqueda una vez. No se mira el nombre de ninguna restricción | Candidata de U03-T01, F-05 |
| El payload se guarda como lo vuelca el modelo de U0 (`model_dump`): los campos opcionales de primer nivel ausentes no se escriben y los del payload se conservan con su `null`. Un `date` del payload sale en ISO (`chain._plain`) | Los bytes guardados son los que se hashean (BR-U3-09); `FreezeContext` trae `date` |
| El tramo `range` del expediente va de la cubierta (`checkpoint_seq`) del checkpoint anterior a la primera entrada del caso hasta la **fila** del checkpoint posterior a la última (o la cabeza); `IntegrityStatus.from_checkpoint_seq` es esa cubierta y `to_checkpoint_seq` ese `seq` (o `head`). Se lee en tramos de ≤ 10 000 entradas y se agregan las filas cubiertas por los checkpoints del tramo que queden fuera | El diseño dice «checkpoint anterior -> checkpoint posterior o cabeza» sin precisar el `seq` |
| El servicio recibe las llaves públicas de checkpoints (`ServiceConfig.public_keys`, 32 bytes crudos) sin leer la bóveda ni el bucket; sin la llave de un checkpoint del tramo, el expediente sale `not_verified` con `checkpoint_signature` | La API no firma ni lee el WORM (P-U3-08); de dónde se cargan en el chart es del Bloque F |
| `delivery_status` sale en `metrics` solo para `recommendation`, como en `MetricsProjection` de U0; el diseño (domain-entities §3) solo lo menciona junto a la referencia de `human_decision` | Candidata de U03-T02; la diferencia con el diseño sigue pendiente de corregir allí |
| El pool es propio (`pools.py`, una cola de conexiones `psycopg`): no se agrega `psycopg_pool` al lock del workspace | 5 conexiones por réplica; la espera y la métrica `vectra_registry_pool_wait_seconds{pool}` son lo único que necesita el diseño |
| El gauge `vectra_registry_monitoring_lag_seconds` y las tres métricas de la verificación bajo demanda (P-U3-09) las calcula `Gauges` cada 60 s; la edad de la última `full` sin ninguna `terminada` se cuenta desde la génesis | El diseño no dice qué hacer cuando nunca hubo una `full` |
| Un `Forbidden` de `projections` sale como 403 sin cuerpo parcial | Candidata de U03-T02 |
