# Entidades de dominio — U3 `decision-registry`

Decisiones del plan (`decision-registry-functional-design-plan.md`, Q1–Q10 = A). Los tipos
de la API (`RegistryEntryIn`, `RegistryEntry`, `RegistryAck`, payloads) son de U0
(domain-entities §5) y no se redefinen aquí; esta unidad define cómo se **almacenan,
encadenan, anclan, proyectan y verifican**.

---

## 1. Tabla `registry_entries` (`registry-db`)

| Columna | Tipo | Notas |
|---|---|---|
| `seq` | `bigint` PK | Contiguo desde 0 (génesis); `seq = cabeza + 1` |
| `idempotency_key` | `uuid` `UNIQUE` | Del cliente (Q5); para `genesis` y `checkpoint` la genera el registro |
| `entry_type` | `text` | Catálogo de U0 §5.2, incluidos `genesis` y `checkpoint` |
| `case_id` | `uuid` nulo | Índice |
| `model_version_id`, `policy_version_id` | `text` nulos | Índices |
| `actor_kind`, `actor_id`, `actor_role` | `text` | `actor_id` = `sub` (usuario o servicio) o `system` |
| `occurred_at` | `timestamptz` | Del cliente, ±5 min (Q9) |
| `recorded_at` | `timestamptz` | De la base, no decreciente (Q9) |
| `correlation_id` | `text` | `trace-id` W3C (U0) |
| `contract_version` | `text` | Versión SemVer del contrato de U0 con que se escribió (Q2) |
| `canonical` | `bytea` | Bytes JCS exactos de la entrada (Q2, Q3); ≤ 64 KiB (Q10) |
| `prev_hash` | `bytea(32)` | Hash de `seq − 1`; 32 bytes en cero para la génesis |
| `hash` | `bytea(32)` | `SHA-256(prev_hash ‖ canonical)` (Q3) |

Índices de `registry_entries`: `seq` (llave), `case_id`, `idempotency_key` (único), `entry_type` y **`recorded_at`**, este último para el `aggregator reset`, que busca la primera entrada de los últimos 181 días (quinta revisión del FD de U9, 2026-10-10).

Las columnas fuera de `canonical` existen **solo para consultar**. La fuente de verdad es
`canonical`, y el verificador comprueba que las columnas coinciden con él (BR-U3-06).

### 1.1 Contenido de `canonical` (Q3)
Objeto JCS con: `seq`, `entry_type`, `idempotency_key`, `actor`, `occurred_at`,
`recorded_at`, `correlation_id`, `case_id?`, `model_version_id?`, `policy_version_id?`,
`contract_version` y `payload`.

### 1.2 Roles de base de datos

| Rol | Permisos | Usado por |
|---|---|---|
| `registry_app` | `INSERT`, `SELECT` sobre `registry_entries`; `SELECT` sobre la vista de cabeza; **sin** `UPDATE`, `DELETE` ni `TRUNCATE`; sobre `integrity_checks`, solo `INSERT` (la solicitud) y `SELECT` (BR-U3-13b; segunda revisión del Infrastructure Design de U10, 2026-10-10) | decision-registry-service (F42) |
| `registry_verifier` | Solo `SELECT` (incluido `SELECT` explícito sobre `monitoring_daily`, `monitoring_entry_totals`, `monitoring_invalid` y `monitoring_watermark`; **no** sobre `monitoring_case_index`; segunda revisión del FD de U9, 2026-10-08) y `SELECT` sobre `integrity_checks`. **No** escribe en ninguna tabla: lo usa también el pool `projections` de la API (segunda revisión del Infrastructure Design de U10, 2026-10-10) | Pool `projections` de decision-registry-service (réplica); CLI y CronJobs de verificación y archivo (lectura en `-ro`); `restore-drill` (solo lectura) (celda restituida, pendientes abiertos, 2026-10-10) |
| `registry_ondemand` | `SELECT` sobre `integrity_checks` y `registry_entries`; `INSERT` (la `full` mensual que se encola sola) y `UPDATE` por columna (`status`, `started_at`, `finished_at`, `heartbeat_at`, `progress_*`, `report`, `reason`) sobre `integrity_checks`; nada más (segunda revisión del Infrastructure Design de U10, 2026-10-10) | Solo la CLI en los CronJobs de verificación (`registry-verify-ondemand`), para escribir el estado en la primaria; la API **no** lo tiene, y `restore-drill` tampoco, porque es de solo lectura (celda sobrante retirada, pendientes abiertos, 2026-10-10) |
| `registry_health` | `pg_monitor` (solo estadísticas; sin acceso a `registry_entries`) | Readiness del servicio: comprueba que haya un standby síncrono (agregado por U3 NFR Design Q1, P-U3-01) |
| `registry_migrator` | DDL | Job de migración (F44), solo en un sync aprobado |
| `registry_aggregator` | `SELECT` sobre `registry_entries`; `SELECT`, `INSERT`, `UPDATE` y `DELETE` **solo** sobre las cinco tablas derivadas de §1.3; sin `TRUNCATE` | `registry-aggregator` (F107; BR-U3-17, precisado el 2026-10-08 por U9 FD) |

Además, un trigger `BEFORE UPDATE OR DELETE OR TRUNCATE` lanza una excepción (BR-U3-02).
`registry_migrator` es dueño de las tablas derivadas y las vacía en una reconstrucción (BR-U3-17).

### 1.3 Tablas derivadas de monitoreo (BR-U3-17; revisión del FD de U9, 2026-10-08, H6)

Ninguna está bajo el trigger de solo-anexar: se reconstruyen desde la cadena. Retención:
180 días: por `day` en las tablas que lo tienen, y por `evaluated_at` en `monitoring_case_index` (tercera revisión del FD de U9, 2026-10-10).

| Tabla | Columnas | Llave y restricciones |
|---|---|---|
| `monitoring_daily` | `population` (`modelo \| humana`), `model_version_id`, `day` (fecha UTC del momento de negocio), `attribute`, `group`, `band`, `result` (`outcome` o `final_outcome`), `decision` (`sigue \| se_aparta \| resuelve_revision`, o `-` en `modelo`, porque la columna es parte de la llave; la proyección lo devuelve como nulo), `count` | PK (`population`, `model_version_id`, `day`, `attribute`, `group`, `band`, `result`, `decision`); `CHECK (count >= 0)`; `CHECK` de cada valor contra el catálogo de U0 §2.2 |
| `monitoring_entry_totals` | `population`, `model_version_id` (`-` para una decisión cuya recomendación no existe o no es una `recommendation`: fila no atribuible; cuarta revisión del FD de U9, 2026-10-10), `day`, `total`, `invalid` | PK (`population`, `model_version_id`, `day`); `CHECK (total >= 0 AND invalid >= 0 AND invalid <= total)` |
| `monitoring_case_index` | `case_id`, `counted_seq?` (nulo si una decisión fijó el caso sobre una recomendación inválida; sexta revisión del FD de U9, 2026-10-10), `evaluated_at`, `fixed_by_decision` (`bool`). Sin etiquetas, versión, día ni resultado: se releen de `registry_entries` por `counted_seq` al restar (segunda revisión del FD de U9, 2026-10-08) | PK (`case_id`); es interna: ninguna proyección la expone |
| `monitoring_invalid` | `seq`, `population`, `model_version_id`, `day`, `reason` | PK (`seq`) |
| `monitoring_watermark` | `id`, `last_seq`, `updated_at` | PK (`id`), `CHECK (id = 1)`; una sola fila |

## 2. Checkpoints (Q1)

### 2.1 `Checkpoint` (payload de `entry_type = checkpoint`)

| Campo | Contenido |
|---|---|
| `checkpoint_seq` | `seq` de la última entrada cubierta |
| `checkpoint_hash` | `hash` de esa entrada (hex) |
| `signature` | Ed25519 sobre `JCS({checkpoint_seq, checkpoint_hash, recorded_at})` |
| `key_fingerprint` | SHA-256 de la llave pública |

- La entrada `checkpoint` también se encadena: queda en la cadena **y** se copia como objeto `checkpoints/{checkpoint_seq}.json` a un bucket con object lock (WORM).
- La firma la hace la bóveda (Vault Transit en kind; la bóveda o el HSM del banco en producción): la llave privada **nunca** sale de ella (U3 NFR Q5). `registry-db` y sus roles no tienen acceso a la bóveda ni al bucket.

### 2.2 Llave de checkpoints
- La huella de la llave pública activa está en la entrada `genesis`.
- Si se rota la llave, el registro escribe una entrada `checkpoint` con la llave nueva que lleva también la firma de la anterior sobre la huella nueva (*cross-signing*), y así la cadena de llaves se puede verificar desde la génesis.

## 3. Proyecciones de lectura (Q6)

| Proyección | Para | Entradas | Campos |
|---|---|---|---|
| `full` | `cro`, `cumplimiento` (BFF) | Todas | Todos, incluido `canonical` |
| `explanation` | explainability (`registry:read:explanation`) | Una `recommendation` por `seq`, filtrada por `case_id` (BR-U7-13) | `seq`, `case_id`, `model_version_id`, `payload.explanation` |
| ~~`monitoring`~~ **retirada** (sin consumidor desde el FD de U9) | — | `recommendation`, `human_decision` | `recommendation`: `case_id`, `model_version_id`, `policy_version_id`, `score`, `confidence`, `outcome`, `reasons`, `monitoring_labels`, `evaluated_at`, `recorded_at`, `seq`. `human_decision`: `case_id`, `decision`, `final_outcome`, `recommendation_entry_id`, `decided_at`, `recorded_at` |
| `metrics` | product-metrics (`registry:read:metrics`) | `recommendation`, `human_decision`, `explanation_view` | `entry_type`, `case_id`, `outcome`, `decision`, `final_outcome`, `used_factors`, `explanation_viewed_before`, `actor_role`, `recorded_at`, `seq`, `recommendation_entry_id`, `evaluated_at`, `decided_at`, `viewed_at`; en `recommendation`, además `model_version_id`, `channel`, `received_at` y `attempt`; en `recommendation`, también `first_evaluation`; en `human_decision`, además `recommendation: {seq, outcome, model_version_id, evaluated_at, received_at, channel, attempt, first_evaluation} \| null`, resuelta **en el servidor** por `recommendation_entry_id` (`null` si no existe o no es una `recommendation`), como `delivery_status` (U11 BR-U11-01; FD de U11, 2026-10-10). Filtros: rango de `recorded_at` y `seq >` (lectura incremental de U11); además `entry_type`, `seq_after`, `limit` (≤ 1 000; más → 422) y `next_seq_after` en la respuesta (`null` en la última página), según `EntryFilter` de U0 §9.6 y el Paso 8 del plan de U3 (pendientes consolidados, segunda tanda, 2026-10-10) |
| `monitoring_daily` | bias (`registry:read:monitoring`) | Conteos de la tabla derivada (BR-U3-17), no entradas | U9 domain-entities §1.2: por cada rango pedido (hasta 12), la **suma en el servidor** de los conteos marginales por (población, versión, atributo, grupo, banda, resultado, decisión), sin el día ni la combinación de etiquetas, (segunda revisión del FD de U9, 2026-10-08); `versions` con `first_day` y `last_day` por versión y población; `totals` por rango (`range_id`, `total_entries`, `invalid_entries`); servida por `POST /v1/monitoring/daily:query` (rangos con `from_day ≤ to_day`, si no → 422; séptima revisión del FD de U9, 2026-10-10); `unattributable_invalid`, un **solo** valor por solicitud sobre el `unattributable_range` pedido (0 si no se pidió) (las filas `'-'`: decisiones sin recomendación atribuible; quinta revisión del FD de U9, valor único en la sexta revisión del FD de U9, 2026-10-10); hasta 100 `invalid_seqs`; `watermark_seq` y `lag_seconds` (precisado el 2026-10-08 por U9 FD; alineado con U0 §9.4 `MonitoringWindow` en la tercera revisión del FD de U9, 2026-10-10) |
| `monitoring_freezes` | bias y `verification-reader` de U12 (`registry:read:monitoring`) | `freeze` y `frozen_resolution` | `freeze`: `seq`, `freeze_id`, `model_version_id`, `frozen_at`, `recorded_at` (del sobre de la entrada en `GET /v1/entries`; `FreezeRecord` de `GET /v1/monitoring/freezes` no lo lleva y no cambia; pendientes consolidados, 2026-10-10) (para la latencia de RT-2 de U12; pendientes posteriores al cierre, 2026-10-10), `context_package` (el `FreezeContext` con `data_sources` e `initial_disparity`); `frozen_resolution`: `seq`, `model_version_id`, `action`, `recorded_at` (la reactivación tiene efecto al confirmarse, BR-U4-17; revisión del FD de U9, 2026-10-08, H1) (precisado el 2026-10-08 por U9 FD) |

- bias usa `monitoring_daily` y `monitoring_freezes`; la proyección `monitoring` por filas queda sin consumidor y se retira en el plan de U3 (precisado el 2026-10-08 por U9 FD).
- `analista` no tiene proyección: sus vistas vienen de case-service.
- Las proyecciones llevan el momento de negocio (`evaluated_at`, `decided_at`, `viewed_at`) además de `recorded_at`. Un reintento tardío puede separar `recorded_at` hasta 24 h del hecho, así que U9 y U11 deben medir con el momento de negocio (precisado el 2026-10-06, revisión del FD de U8).
- `seq` y `recommendation_entry_id` se agregaron a `explanation`, `monitoring` y `metrics` para que el resumen al solicitante, U9 y U11 usen solo la recomendación entregada (P-U7-03) (precisado el 2026-10-03 por U7 NFR Design Q3).
- Ninguna proyección distinta de `full` incluye `feature_vector`, `justification`, `narrative` fuera de `explanation`, ni `actor_id`.

## 4. Expediente (Q7)

### 4.1 `RegistryDossier` (lo que devuelve el registro)

| Campo | Contenido |
|---|---|
| `case_id` | — |
| `entries` | Todas las entradas del caso en orden de `seq`, con `canonical` en base64 (la narrativa se reproduce byte a byte) y sus campos decodificados. Cada `recommendation` lleva `delivery_status` (`entregada` \| `no_entregada` \| `pendiente_de_decision`), calculado al leer y nunca guardado (BR-U3-14) (precisado el 2026-10-03 por U7 NFR Design Q3) |
| `integrity` | `IntegrityStatus` del tramo (§4.2) |
| `last_full_verification` | `{check_id, finished_at, result: integra \| inconsistente} \| null`: la fila más reciente de `integrity_checks` con `mode = full` y `status = terminada` (§5.0; revisión del Infrastructure Design de U10, 2026-10-10) |

### 4.2 `IntegrityStatus`
`status` (`verified` \| `not_verified`), `from_checkpoint_seq`, `to_checkpoint_seq` (o
`head`), `entries_checked`, `first_inconsistent_seq?`, `reason?` (`hash` \| `link` \|
`checkpoint_signature` \| `checkpoint_mismatch` \| `seq_gap` \| `column_mismatch`).

La forma de `RegistryDossier` e `IntegrityStatus` vive en U0 §9.6 (BR-U0-93; revisión del FD de U10, 2026-10-10, B1).

### 4.3 `Dossier` del BFF
`RegistryDossier` más los identificadores directos del caso traídos de case-service, solo
para `cro` y `cumplimiento`; es `ConsoleDossier` de U0 §9.5 (revisión del FD de U10, 2026-10-10). El registro **no** llama a case-service ni recibe
identificadores (sin flujo hacia datos de identificación).

## 5. Informe del verificador (Q8)

### 5.0 Tabla `integrity_checks` (BR-U3-13b; NFR Design de U10, Q3; rediseñada en la revisión del Infrastructure Design de U10, 2026-10-10)

| Columna | Tipo | Notas |
|---|---|---|
| `check_id` | `uuid` | Llave |
| `mode` | `full` \| `range` | — |
| `from_seq`, `to_seq` | `bigint?` | Solo en `range` |
| `requested_by` | `text` | `sub` del CRO, o `cron` para la `full` mensual |
| `requested_at`, `started_at?`, `finished_at?`, `heartbeat_at?` | `timestamptz` | — |
| `status` | `pendiente` \| `en_curso` \| `terminada` \| `fallida` | Máquina de estados de business-logic-model §2.6 |
| `progress_checked`, `progress_total` | `bigint` | `progress_checked ≤ progress_total` (`CHECK`) |
| `report` | `jsonb?` | `IntegrityReport`; obligatorio en `terminada` (`CHECK`) |
| `reason` | `interrumpida` \| `error_de_ejecucion` \| `plazo_vencido` \| `null` | Obligatorio en `fallida` y prohibido en los demás (`CHECK`) |

- Índice único parcial sobre una expresión constante con `status IN ('pendiente', 'en_curso')`: una sola verificación activa, de cualquier modo.
- **Permisos** (segunda revisión del Infrastructure Design de U10, 2026-10-10): `registry_app` solo `INSERT` (la solicitud) y `SELECT`; `registry_verifier` solo `SELECT` (lo comparte la API); `registry_ondemand` (solo los CronJobs de verificación) `INSERT` y `UPDATE` por columna. Nadie tiene `DELETE` ni `TRUNCATE`.
- No es evidencia (BR-U3-01, 02): es el estado de una operación. Define `last_full_verification` (§4.1).

### `IntegrityReport`
`mode` (`incremental` \| `nightly` \| `full` \| `range`), `from_seq`, `to_seq`, `entries_checked`,
`checkpoints_checked`, `result` (`integra` \| `inconsistente` \| `error`),
`first_inconsistent_seq?`, `reason?`, `started_at`, `finished_at`.

| Código de salida de la CLI | Significado |
|---|---|
| `0` | `integra` |
| `1` | `inconsistente` (informa el primer `seq` y el motivo) |
| `2` | `error` de ejecución (no se pudo verificar) |

## 6. Parámetros

| Parámetro | Valor | Regla |
|---|---|---|
| Intervalo de checkpoint | 1 h; una verificación completa no firma (el checkpoint siguiente la cubre; revisión del Infrastructure Design de U10, 2026-10-10) | BR-U3-08 |
| Verificación bajo demanda | `registry-verify-ondemand` cada minuto; barrido de filas `en_curso` con latido de más de 2 min; tramos de ≤ 10 000 entradas | BR-U3-13b |
| Llaves de *advisory lock* | Append: `pg_advisory_xact_lock(1448214529)` (`0x56520001`); reconstrucción del agregador: `pg_try_advisory_lock(1448214530)` (`0x56520002`). Constantes en `vectra_registry.locks`; una prueba verifica que son distintas (revisión del Infrastructure Design de U10, 2026-10-10) | BR-U3-04, 17 |
| Lectura en el standby | `hot_standby_feedback = on`, `max_standby_streaming_delay = 2s`; un tramo cancelado se reintenta hasta 3 veces | BR-U3-13b |
| Verificación incremental | Cada 15 min | BR-U3-11 |
| Verificación `nightly` | Cada noche | BR-U3-11 |
| Verificación `full` | Cada mes, bajo demanda y en `restore-drill` | BR-U3-11 |
| Margen de `occurred_at` | ±5 min | BR-U3-05 |
| Tamaño máximo de `canonical` | 64 KiB (alerta a 48 KiB) | BR-U3-07 |
